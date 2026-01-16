"""Discord イベントハンドラー"""

import asyncio
import logging
from datetime import datetime, timedelta

import discord
from discord.ext import tasks

from ..ai.litellm_provider import LiteLLMProvider
from ..ai.prompts import DEFAULT_SYSTEM_PROMPT
from ..config import Config
from ..eavesdrop.conversation_buffer import ConversationBuffer
from ..eavesdrop.llm_judge import LLMJudge
from ..errors.database_errors import (
    classify_database_error,
    get_database_error_message,
)
from ..errors.discord_errors import (
    classify_discord_error,
    get_user_friendly_message,
)
from ..rate_limit.request_queue import RequestPriority, RequestQueue
from ..router.message_router import MessageRouter
from ..session.manager import SessionManager
from ..session.models import MessageRole
from ..utils.message_formatter import create_response_embed
from ..utils.message_splitter import format_split_messages, split_message
from .client import KotonohaBot

logger = logging.getLogger(__name__)


class MessageHandler:
    """メッセージハンドラー"""

    def __init__(self, bot: KotonohaBot):
        self.bot = bot
        self.session_manager = SessionManager()
        self.ai_provider = LiteLLMProvider()
        # メッセージルーター
        self.router = MessageRouter(bot)
        # 聞き耳型の機能
        self.conversation_buffer = ConversationBuffer(
            max_size=Config.EAVESDROP_BUFFER_SIZE
        )
        self.llm_judge = LLMJudge(self.session_manager, self.ai_provider)
        # リクエストキュー
        self.request_queue = RequestQueue(max_size=100)
        # タスクは on_ready イベントで開始する（イベントループが必要なため）
        # 聞き耳型の有効化（環境変数から読み込み）
        self._load_eavesdrop_channels()

    def cog_unload(self):
        """クリーンアップタスクを停止"""
        self.cleanup_task.cancel()
        self.batch_sync_task.cancel()

    @tasks.loop(hours=1)  # 1時間ごとに実行
    async def cleanup_task(self):
        """定期的なセッションクリーンアップ"""
        try:
            logger.info("Running scheduled session cleanup...")
            self.session_manager.cleanup_old_sessions()
            logger.info("Session cleanup completed")
        except Exception as e:
            logger.error(f"Error during session cleanup: {e}")

    @cleanup_task.before_loop
    async def before_cleanup_task(self):
        """クリーンアップタスク開始前の待機"""
        await self.bot.wait_until_ready()

    @tasks.loop(minutes=5)  # 5分ごとに実行
    async def batch_sync_task(self):
        """定期的なバッチ同期（アイドル状態のセッションを保存）"""
        try:
            logger.info("Running batch sync...")

            # アイドル状態のセッションを保存
            # 最後のアクティビティから5分以上経過しているセッションを保存
            now = datetime.now()
            idle_threshold = timedelta(minutes=5)

            saved_count = 0
            for session_key, session in self.session_manager.sessions.items():
                time_since_activity = now - session.last_active_at
                if time_since_activity >= idle_threshold:
                    try:
                        self.session_manager.save_session(session_key)
                        saved_count += 1
                        logger.debug(f"Saved idle session: {session_key}")
                    except Exception as e:
                        logger.error(f"Failed to save session {session_key}: {e}")

            if saved_count > 0:
                logger.info(f"Batch sync completed: saved {saved_count} idle sessions")
            else:
                logger.debug("Batch sync completed: no idle sessions to save")

        except Exception as e:
            logger.error(f"Error during batch sync: {e}")

    @batch_sync_task.before_loop
    async def before_batch_sync_task(self):
        """バッチ同期タスク開始前の待機"""
        await self.bot.wait_until_ready()

    def _load_eavesdrop_channels(self) -> None:
        """環境変数から聞き耳型の有効チャンネルを読み込み"""
        if Config.EAVESDROP_ENABLED_CHANNELS:
            channel_ids = [
                int(cid.strip())
                for cid in Config.EAVESDROP_ENABLED_CHANNELS.split(",")
                if cid.strip()
            ]
            for channel_id in channel_ids:
                self.router.enable_eavesdrop_for_channel(channel_id)
                logger.info(f"Loaded eavesdrop channel from config: {channel_id}")

    async def handle_mention(self, message: discord.Message):
        """メンション時の処理（リクエストキューに追加）"""
        # Bot自身のメッセージは無視
        if message.author.bot:
            return

        # Botがメンションされているか確認
        if self.bot.user not in message.mentions:
            return

        logger.info(f"Mention from {message.author} in {message.channel}")

        # リクエストキューに追加（優先度: MENTION）
        try:
            future = await self.request_queue.enqueue(
                RequestPriority.MENTION,
                self._process_mention,
                message,
            )
            # 結果を待機（エラーハンドリングは内部で行う）
            await future
        except Exception as e:
            logger.exception(f"Error enqueuing mention request: {e}")
            # キューが満杯などの場合のフォールバック
            try:
                await self._process_mention(message)
            except Exception as inner_e:
                logger.exception(f"Error in fallback mention processing: {inner_e}")

    async def _process_mention(self, message: discord.Message) -> None:
        """メンション処理の実装"""
        try:
            # タイピングインジケーターを表示
            async with message.channel.typing():
                # セッションキーを生成（ユーザーIDベース）
                session_key = f"mention:{message.author.id}"

                # セッションを取得または作成
                session = self.session_manager.get_session(session_key)
                if not session:
                    session = self.session_manager.create_session(
                        session_key=session_key,
                        session_type="mention",
                        channel_id=message.channel.id,
                        user_id=message.author.id,
                    )
                    logger.info(f"Created new session: {session_key}")

                # メンション部分を除去したメッセージ
                user_message = message.content
                for mention in message.mentions:
                    user_message = user_message.replace(f"<@{mention.id}>", "").strip()

                # ユーザーメッセージを追加
                self.session_manager.add_message(
                    session_key=session_key,
                    role=MessageRole.USER,
                    content=user_message,
                )

                # 現在の日付情報を含むシステムプロンプトを生成
                now = datetime.now()
                weekday_names = ["月", "火", "水", "木", "金", "土", "日"]
                current_date_info = (
                    f"\n\n【現在の日付情報】\n"
                    f"現在の日時: {now.strftime('%Y年%m月%d日 %H:%M:%S')}\n"
                    f"今日の曜日: {weekday_names[now.weekday()]}曜日\n"
                    f"日付や曜日に関する質問には、この情報を基に具体的に回答してください。"
                    f"プレースホルダー（[明日の曜日]など）は使用せず、実際の日付や曜日を回答してください。"
                )
                system_prompt = DEFAULT_SYSTEM_PROMPT + current_date_info

                # AI応答を生成
                response_text = await self.ai_provider.generate_response(
                    messages=session.get_conversation_history(),
                    system_prompt=system_prompt,
                )

                # アシスタントメッセージを追加
                self.session_manager.add_message(
                    session_key=session_key,
                    role=MessageRole.ASSISTANT,
                    content=response_text,
                )

                # セッションを保存
                self.session_manager.save_session(session_key)

                # 返信（メッセージ分割対応）
                response_chunks = split_message(response_text)
                formatted_chunks = format_split_messages(
                    response_chunks, len(response_chunks)
                )

                # 使用モデル名とレート制限使用率を取得
                model_name = self.ai_provider.get_last_used_model()
                rate_limit_usage = self.ai_provider.get_rate_limit_usage()

                # 最初のメッセージは reply で送信（フッター付き）
                if formatted_chunks:
                    # 最初のメッセージのみEmbedで送信（フッター付き）
                    embed = create_response_embed(
                        formatted_chunks[0], model_name, rate_limit_usage
                    )
                    await message.reply(embed=embed)

                    # 残りのメッセージは順次送信
                    for chunk in formatted_chunks[1:]:
                        await message.channel.send(chunk)
                        # レート制限を考慮して少し待機
                        await asyncio.sleep(0.5)

                logger.info(f"Sent response to {message.author}")

        except discord.errors.DiscordException as e:
            logger.exception(f"Discord error handling mention: {e}")
            error_type = classify_discord_error(e)
            error_message = get_user_friendly_message(error_type)
            await message.reply(error_message)
        except Exception as e:
            logger.exception(f"Error handling mention: {e}")
            # データベースエラーの可能性をチェック
            if "sqlite" in str(type(e)).lower() or "database" in str(e).lower():
                error_type = classify_database_error(e)
                error_message = get_database_error_message(error_type)
                await message.reply(error_message)
            else:
                await message.reply(
                    "すみません。一時的に反応できませんでした。\n"
                    "少し時間をおいて、もう一度試してみてください。"
                )

    async def handle_thread(self, message: discord.Message):
        """スレッド型の処理（リクエストキューに追加）"""
        # Bot自身のメッセージは無視
        if message.author.bot:
            return

        logger.info(f"Thread message from {message.author} in {message.channel}")

        # リクエストキューに追加（優先度: THREAD）
        try:
            # 既存スレッド内での会話か、新規スレッド作成か判定
            if isinstance(message.channel, discord.Thread):
                # 既存スレッド内での会話
                future = await self.request_queue.enqueue(
                    RequestPriority.THREAD,
                    self._process_thread_message,
                    message,
                )
            else:
                # メンション検知時の新規スレッド作成
                if self.bot.user in message.mentions:
                    future = await self.request_queue.enqueue(
                        RequestPriority.THREAD,
                        self._process_thread_creation,
                        message,
                    )
                else:
                    return  # メンションされていない場合は処理しない

            # 結果を待機（エラーハンドリングは内部で行う）
            await future
        except Exception as e:
            logger.exception(f"Error enqueuing thread request: {e}")
            # キューが満杯などの場合のフォールバック
            try:
                if isinstance(message.channel, discord.Thread):
                    await self._process_thread_message(message)
                elif self.bot.user in message.mentions:
                    await self._process_thread_creation(message)
            except Exception as inner_e:
                logger.exception(f"Error in fallback thread processing: {inner_e}")

    async def _process_thread_creation(self, message: discord.Message) -> None:
        """スレッド作成処理の実装"""
        success = await self._create_thread_and_respond(message)
        if not success:
            logger.warning(
                f"Thread creation failed for message {message.id}, but error was not handled"
            )
            try:
                await message.reply(
                    "すみません。一時的に反応できませんでした。\n"
                    "少し時間をおいて、もう一度試してみてください。"
                )
            except Exception as e:
                logger.exception(f"Error sending fallback error message: {e}")

    async def _create_thread_and_respond(self, message: discord.Message) -> bool:
        """スレッドを作成して応答

        Returns:
            bool: 処理が成功した場合 True、失敗した場合 False
        """
        # スレッド名を生成（ユーザーの質問から端的で短い名前を生成）
        user_message = message.content or ""
        for mention in message.mentions:
            user_message = user_message.replace(f"<@{mention.id}>", "").strip()

        # スレッド名を生成（端的で短い名前、最大50文字）
        # 空になるケース: メンションのみ（@bot だけ）、空白のみ、message.content が None
        if user_message and len(user_message.strip()) >= 1:
            # 改行文字や制御文字を除去し、複数の空白を1つにまとめる
            cleaned_message = " ".join(user_message.split())
            # 端的な名前を生成（最大50文字、文の区切りで切る）
            thread_name = cleaned_message[:50].strip()
            # 文の区切り（。、！、？）で切る
            for delimiter in ["。", "！", "？", ".", "!", "?"]:
                if delimiter in thread_name:
                    thread_name = thread_name.split(delimiter)[0].strip()
                    break
            # スレッド名が短すぎる場合はデフォルト名を使用
            if len(thread_name) < 1:
                thread_name = "会話"
        else:
            # メンションのみや空白のみの場合のデフォルト名
            thread_name = "会話"

        # 既存のスレッドがあるかチェック（race condition対策）
        # 既存スレッドの名前は固定のため更新しない
        if message.thread:
            logger.info(
                f"Thread already exists for message {message.id}, using existing thread (name: {message.thread.name})"
            )
            thread = message.thread
        else:
            # スレッドを作成
            try:
                # 環境変数で設定された場合はその値を使用、未設定の場合はサーバーのデフォルト値を使用
                thread_kwargs = {"name": thread_name}
                if Config.THREAD_AUTO_ARCHIVE_DURATION is not None:
                    thread_kwargs["auto_archive_duration"] = (
                        Config.THREAD_AUTO_ARCHIVE_DURATION
                    )
                thread = await message.create_thread(**thread_kwargs)
            except discord.errors.Forbidden:
                # スレッド作成権限がない場合はメンション応答型にフォールバック
                logger.warning(
                    f"No permission to create thread in channel {message.channel.id}, falling back to mention mode"
                )
                await self.handle_mention(message)
                return True  # メンション応答型にフォールバックしたので成功として扱う
            except discord.errors.HTTPException as e:
                if e.code == 160004:
                    # すでにスレッドが作成されている場合は既存のスレッドを使用
                    # 少し待ってからmessage.threadを再取得
                    await asyncio.sleep(0.5)
                    # メッセージを再取得してスレッドを確認
                    try:
                        updated_message = await message.channel.fetch_message(
                            message.id
                        )
                        if updated_message.thread:
                            logger.info(
                                f"Thread already exists for message {message.id}, using existing thread (after retry, name: {updated_message.thread.name})"
                            )
                            thread = updated_message.thread
                            # 既存スレッドの名前は固定のため更新しない
                        else:
                            logger.warning(
                                f"Thread already exists but not accessible for message {message.id}"
                            )
                            # エラーメッセージを送信してから return
                            await message.reply(
                                "すみません。一時的に反応できませんでした。\n"
                                "少し時間をおいて、もう一度試してみてください。"
                            )
                            return False
                    except Exception as fetch_error:
                        logger.warning(
                            f"Failed to fetch message {message.id} after thread creation error: {fetch_error}"
                        )
                        # エラーメッセージを送信してから return
                        await message.reply(
                            "すみません。一時的に反応できませんでした。\n"
                            "少し時間をおいて、もう一度試してみてください。"
                        )
                        return False
                else:
                    # その他のHTTPExceptionは再発生させる
                    logger.error(f"HTTPException during thread creation: {e}")
                    await message.reply(
                        "すみません。一時的に反応できませんでした。\n"
                        "少し時間をおいて、もう一度試してみてください。"
                    )
                    return False
            except Exception as e:
                # 予期しないエラー
                logger.exception(f"Unexpected error during thread creation: {e}")
                await message.reply(
                    "すみません。一時的に反応できませんでした。\n"
                    "少し時間をおいて、もう一度試してみてください。"
                )
                return False

        try:
            # スレッドを記録
            self.router.register_bot_thread(thread.id)

            # セッションキーを生成
            session_key = f"thread:{thread.id}"

            # セッションを取得または作成
            session = self.session_manager.get_session(session_key)
            if not session:
                session = self.session_manager.create_session(
                    session_key=session_key,
                    session_type="thread",
                    channel_id=message.channel.id,
                    thread_id=thread.id,
                    user_id=message.author.id,
                )
                logger.info(f"Created new thread session: {session_key}")

            # ユーザーメッセージを追加
            self.session_manager.add_message(
                session_key=session_key,
                role=MessageRole.USER,
                content=user_message,
            )

            # AI応答を生成
            async with thread.typing():
                # 現在の日付情報を含むシステムプロンプトを生成
                now = datetime.now()
                weekday_names = ["月", "火", "水", "木", "金", "土", "日"]
                current_date_info = (
                    f"\n\n【現在の日付情報】\n"
                    f"現在の日時: {now.strftime('%Y年%m月%d日 %H:%M:%S')}\n"
                    f"今日の曜日: {weekday_names[now.weekday()]}曜日\n"
                    f"日付や曜日に関する質問には、この情報を基に具体的に回答してください。"
                )
                system_prompt = DEFAULT_SYSTEM_PROMPT + current_date_info

                # AI応答を生成
                response_text = await self.ai_provider.generate_response(
                    messages=session.get_conversation_history(),
                    system_prompt=system_prompt,
                )

                # アシスタントメッセージを追加
                self.session_manager.add_message(
                    session_key=session_key,
                    role=MessageRole.ASSISTANT,
                    content=response_text,
                )

                # セッションを保存
                self.session_manager.save_session(session_key)

                # スレッド内で返信（メッセージ分割対応）
                response_chunks = split_message(response_text)
                formatted_chunks = format_split_messages(
                    response_chunks, len(response_chunks)
                )

                # 使用モデル名とレート制限使用率を取得
                model_name = self.ai_provider.get_last_used_model()
                rate_limit_usage = self.ai_provider.get_rate_limit_usage()

                # 最初のメッセージは reply で送信（フッター付き）
                if formatted_chunks:
                    # 最初のメッセージのみEmbedで送信（フッター付き）
                    embed = create_response_embed(
                        formatted_chunks[0], model_name, rate_limit_usage
                    )
                    await thread.send(embed=embed)

                    # 残りのメッセージは順次送信
                    for chunk in formatted_chunks[1:]:
                        await thread.send(chunk)
                        await asyncio.sleep(0.5)

                logger.info(f"Sent response in thread: {thread.id}")
                return True

        except Exception as e:
            logger.exception(
                f"Error in _create_thread_and_respond after thread creation: {e}"
            )
            # エラーメッセージを送信
            try:
                await message.reply(
                    "すみません。一時的に反応できませんでした。\n"
                    "少し時間をおいて、もう一度試してみてください。"
                )
            except Exception as reply_error:
                logger.error(f"Failed to send error message: {reply_error}")
            return False

    async def _process_thread_message(self, message: discord.Message) -> None:
        """既存スレッド内でのメッセージ処理の実装"""
        # message.channel は既に Thread 型であることが確認済み
        if not isinstance(message.channel, discord.Thread):
            logger.error(f"Expected Thread but got {type(message.channel)}")
            return

        thread = message.channel
        session_key = f"thread:{thread.id}"

        # セッションを取得または作成
        session = self.session_manager.get_session(session_key)
        if not session:
            # スレッドが既に存在する場合、会話履歴を復元
            parent_id = thread.parent_id if thread.parent_id else None
            session = self.session_manager.create_session(
                session_key=session_key,
                session_type="thread",
                channel_id=parent_id,
                thread_id=thread.id,
                user_id=message.author.id,
            )
            logger.info(f"Created thread session from existing thread: {session_key}")

        # ユーザーメッセージを追加
        self.session_manager.add_message(
            session_key=session_key,
            role=MessageRole.USER,
            content=message.content,
        )

        # AI応答を生成
        try:
            async with thread.typing():
                # 現在の日付情報を含むシステムプロンプトを生成
                now = datetime.now()
                weekday_names = ["月", "火", "水", "木", "金", "土", "日"]
                current_date_info = (
                    f"\n\n【現在の日付情報】\n"
                    f"現在の日時: {now.strftime('%Y年%m月%d日 %H:%M:%S')}\n"
                    f"今日の曜日: {weekday_names[now.weekday()]}曜日\n"
                )
                system_prompt = DEFAULT_SYSTEM_PROMPT + current_date_info

                # AI応答を生成
                response_text = await self.ai_provider.generate_response(
                    messages=session.get_conversation_history(),
                    system_prompt=system_prompt,
                )

                # アシスタントメッセージを追加
                self.session_manager.add_message(
                    session_key=session_key,
                    role=MessageRole.ASSISTANT,
                    content=response_text,
                )

                # セッションを保存
                self.session_manager.save_session(session_key)

                # 使用モデル名とレート制限使用率を取得
                model_name = self.ai_provider.get_last_used_model()
                rate_limit_usage = self.ai_provider.get_rate_limit_usage()

                # スレッド内で返信（メッセージ分割対応）
                response_chunks = split_message(response_text)
                formatted_chunks = format_split_messages(
                    response_chunks, len(response_chunks)
                )

                # 最初のメッセージのみEmbedで送信（フッター付き）
                if formatted_chunks:
                    embed = create_response_embed(
                        formatted_chunks[0], model_name, rate_limit_usage
                    )
                    await message.reply(embed=embed)

                    # 残りのメッセージは順次送信
                    for chunk in formatted_chunks[1:]:
                        await thread.send(chunk)
                        await asyncio.sleep(0.5)

                logger.info(f"Sent response in thread: {thread.id}")

        except discord.errors.DiscordException as e:
            logger.exception(f"Discord error handling thread message: {e}")
            error_type = classify_discord_error(e)
            error_message = get_user_friendly_message(error_type)
            try:
                await message.reply(error_message)
            except Exception as reply_error:
                logger.error(f"Failed to send error message: {reply_error}")
        except Exception as e:
            logger.exception(f"Error handling thread message: {e}")
            # データベースエラーの可能性をチェック
            if "sqlite" in str(type(e)).lower() or "database" in str(e).lower():
                error_type = classify_database_error(e)
                error_message = get_database_error_message(error_type)
                try:
                    await message.reply(error_message)
                except Exception as reply_error:
                    logger.error(f"Failed to send error message: {reply_error}")
            else:
                try:
                    await message.reply(
                        "すみません。一時的に反応できませんでした。\n"
                        "少し時間をおいて、もう一度試してみてください。"
                    )
                except Exception as reply_error:
                    logger.error(f"Failed to send error message: {reply_error}")

    async def handle_eavesdrop(self, message: discord.Message):
        """聞き耳型の処理（リクエストキューに追加）"""
        # Bot自身のメッセージは無視
        if message.author.bot:
            return

        # 聞き耳型が有効なチャンネルか確認
        if message.channel.id not in self.router.eavesdrop_enabled_channels:
            return

        logger.debug(f"Eavesdrop message from {message.author} in {message.channel}")

        # リクエストキューに追加（優先度: EAVESDROP - 最高優先度）
        try:
            future = await self.request_queue.enqueue(
                RequestPriority.EAVESDROP,
                self._process_eavesdrop,
                message,
            )
            # 結果を待機（エラーハンドリングは内部で行う）
            await future
        except Exception as e:
            logger.exception(f"Error enqueuing eavesdrop request: {e}")
            # キューが満杯などの場合のフォールバック
            try:
                await self._process_eavesdrop(message)
            except Exception as inner_e:
                logger.exception(f"Error in fallback eavesdrop processing: {inner_e}")

    async def _process_eavesdrop(self, message: discord.Message) -> None:
        """聞き耳型処理の実装"""
        try:
            # 会話ログに追加
            self.conversation_buffer.add_message(message.channel.id, message)

            # 直近のメッセージを取得
            recent_messages = self.conversation_buffer.get_recent_messages(
                message.channel.id, limit=Config.EAVESDROP_BUFFER_SIZE
            )

            # 聞き耳型は会話の流れを理解するため、最低限のメッセージ数が必要
            if len(recent_messages) < Config.EAVESDROP_MIN_MESSAGES:
                logger.debug(
                    f"Not enough messages for eavesdrop (got {len(recent_messages)}, "
                    f"need {Config.EAVESDROP_MIN_MESSAGES})"
                )
                return

            # LLM 判断機能を呼び出し
            response_text = await self.llm_judge.generate_response(
                message.channel.id, recent_messages
            )

            # 応答がある場合のみ投稿
            if response_text:
                # セッションキーを生成
                session_key = f"eavesdrop:{message.channel.id}"

                # セッションを取得または作成
                session = self.session_manager.get_session(session_key)
                if not session:
                    session = self.session_manager.create_session(
                        session_key=session_key,
                        session_type="eavesdrop",
                        channel_id=message.channel.id,
                    )
                    logger.info(f"Created new eavesdrop session: {session_key}")

                # アシスタントメッセージを追加
                self.session_manager.add_message(
                    session_key=session_key,
                    role=MessageRole.ASSISTANT,
                    content=response_text,
                )

                # セッションを保存
                self.session_manager.save_session(session_key)

                # メインチャンネルに直接投稿（メッセージ分割対応）
                response_chunks = split_message(response_text)
                formatted_chunks = format_split_messages(
                    response_chunks, len(response_chunks)
                )

                # 使用モデル名とレート制限使用率を取得
                model_name = self.ai_provider.get_last_used_model()
                rate_limit_usage = self.ai_provider.get_rate_limit_usage()

                # 最初のメッセージを送信（フッター付き）
                if formatted_chunks:
                    # 最初のメッセージのみEmbedで送信（フッター付き）
                    embed = create_response_embed(
                        formatted_chunks[0], model_name, rate_limit_usage
                    )
                    await message.channel.send(embed=embed)

                    # 残りのメッセージは順次送信
                    for chunk in formatted_chunks[1:]:
                        await message.channel.send(chunk)
                        await asyncio.sleep(0.5)

                logger.info(f"Sent eavesdrop response in channel: {message.channel.id}")

        except Exception as e:
            logger.exception(f"Error handling eavesdrop: {e}")
            # 聞き耳型ではエラーメッセージを送信しない（自然な会話参加のため）


def setup_handlers(bot: KotonohaBot):
    """イベントハンドラーをセットアップ"""
    handler = MessageHandler(bot)

    @bot.event
    async def on_ready():
        """Bot起動完了時"""
        logger.info(f"Bot is ready! Logged in as {bot.user}")
        # イベントループが実行されている状態でタスクを開始
        if not handler.cleanup_task.is_running():
            handler.cleanup_task.start()
            logger.info("Cleanup task started")
        if not handler.batch_sync_task.is_running():
            handler.batch_sync_task.start()
            logger.info("Batch sync task started")
        # リクエストキューを開始
        await handler.request_queue.start()
        logger.info("Request queue started")

    @bot.event
    async def on_message(message: discord.Message):
        """メッセージ受信時"""
        # Bot自身のメッセージは無視
        if message.author.bot:
            await bot.process_commands(message)
            return

        # メッセージルーターで会話の契機を判定
        trigger = await handler.router.route(message)

        # 各方式のハンドラーを呼び出し
        if trigger == "mention":
            await handler.handle_mention(message)
        elif trigger == "thread":
            await handler.handle_thread(message)
        elif trigger == "eavesdrop":
            await handler.handle_eavesdrop(message)

        # コマンド処理（メンションでない場合のみ）
        if trigger != "mention" and trigger != "thread":
            await bot.process_commands(message)

    @bot.event
    async def on_thread_update(before: discord.Thread, after: discord.Thread):
        """スレッド更新時"""
        # アーカイブされた場合
        if after.archived and not before.archived:
            session_key = f"thread:{after.id}"
            try:
                # セッションを保存
                handler.session_manager.save_session(session_key)
                logger.info(f"Saved session on thread archive: {session_key}")
            except Exception as e:
                logger.error(f"Failed to save session on thread archive: {e}")

    @bot.command(name="eavesdrop")
    async def eavesdrop_command(ctx, action: str | None = None):
        """聞き耳型の開発用コマンド

        使用方法:
        !eavesdrop clear - 現在のチャンネルの会話ログバッファをクリア
        !eavesdrop status - 現在のチャンネルのバッファ状態を表示
        """
        # 開発用コマンドなので、管理者権限をチェック（オプション）
        # 必要に応じて権限チェックを追加できます

        if action == "clear":
            # 現在のチャンネルのバッファをクリア
            handler.conversation_buffer.clear(ctx.channel.id)
            await ctx.send("✅ 会話ログバッファをクリアしました。")
            logger.info(f"Cleared conversation buffer for channel: {ctx.channel.id}")
        elif action == "status":
            # 現在のチャンネルのバッファ状態を表示
            recent_messages = handler.conversation_buffer.get_recent_messages(
                ctx.channel.id
            )
            message_count = len(recent_messages)
            await ctx.send(
                f"📊 現在のバッファ状態:\n"
                f"- メッセージ数: {message_count}件\n"
                f"- 最大サイズ: {Config.EAVESDROP_BUFFER_SIZE}件"
            )
        else:
            await ctx.send(
                "使用方法:\n"
                "`!eavesdrop clear` - 会話ログバッファをクリア\n"
                "`!eavesdrop status` - バッファ状態を表示"
            )

    logger.info("Event handlers registered")

    return handler
