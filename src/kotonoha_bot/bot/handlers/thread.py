"""スレッド応答ハンドラー。."""

import asyncio
import logging
from typing import Literal, cast

import discord

from kotonoha_bot.bot.client import KotonohaBot
from kotonoha_bot.bot.handlers.mention import MentionHandler
from kotonoha_bot.bot.router import MessageRouter
from kotonoha_bot.config import Config
from kotonoha_bot.db.models import MessageRole
from kotonoha_bot.errors.database import (
    classify_database_error,
    get_database_error_message,
)
from kotonoha_bot.errors.discord import (
    classify_discord_error,
    get_user_friendly_message,
)
from kotonoha_bot.errors.messages import ErrorMessages
from kotonoha_bot.rate_limit.request_queue import RequestPriority, RequestQueue
from kotonoha_bot.services.ai import AIProvider
from kotonoha_bot.services.session import SessionManager
from kotonoha_bot.utils.datetime import format_datetime_for_prompt
from kotonoha_bot.utils.message import (
    create_response_embed,
    format_split_messages,
    split_message,
)
from kotonoha_bot.utils.prompts import DEFAULT_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


class ThreadHandler:
    """スレッド応答ハンドラー."""

    def __init__(
        self,
        bot: KotonohaBot,
        session_manager: SessionManager,
        ai_provider: AIProvider,
        router: MessageRouter,
        request_queue: RequestQueue,
        mention_handler: MentionHandler,
        config: Config | None = None,
    ):
        """ThreadHandler を初期化.

        Args:
            bot: Discord クライアント
            session_manager: セッションマネージャー
            ai_provider: AIプロバイダー
            router: メッセージルーター
            request_queue: リクエストキュー
            mention_handler: メンションハンドラー（フォールバック用）
            config: 設定インスタンス（省略可）
        """
        self.bot = bot
        self.session_manager = session_manager
        self.ai_provider = ai_provider
        self.router = router
        self.request_queue = request_queue
        self.mention_handler = mention_handler
        self.config = config

    async def handle(self, message: discord.Message) -> None:
        """スレッド型の処理（リクエストキューに追加）.

        Args:
            message: Discord メッセージ
        """
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
                    self._process_message,
                    message,
                )
            else:
                # メンション検知時の新規スレッド作成
                if self.bot.user in message.mentions:
                    future = await self.request_queue.enqueue(
                        RequestPriority.THREAD,
                        self._process_creation,
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
                    await self._process_message(message)
                elif self.bot.user in message.mentions:
                    await self._process_creation(message)
            except Exception as inner_e:
                logger.exception(f"Error in fallback thread processing: {inner_e}")

    async def _process_creation(self, message: discord.Message) -> None:
        """スレッド作成処理の実装.

        Args:
            message: Discord メッセージ
        """
        success = await self._create_thread_and_respond(message)
        if not success:
            logger.warning(
                f"Thread creation failed for message {message.id}, but error was not handled"
            )
            await message.reply(ErrorMessages.GENERIC)

    async def _create_thread_and_respond(self, message: discord.Message) -> bool:
        """スレッドを作成して応答.

        Args:
            message: Discord メッセージ

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
                if self.config and self.config.THREAD_AUTO_ARCHIVE_DURATION is not None:
                    # discord.py expects Literal[60, 1440, 4320, 10080] for auto_archive_duration
                    # We cast to the expected type since we validate the value comes from env var
                    thread = await message.create_thread(
                        name=thread_name,
                        auto_archive_duration=cast(
                            Literal[60, 1440, 4320, 10080],
                            self.config.THREAD_AUTO_ARCHIVE_DURATION,
                        ),
                    )
                else:
                    thread = await message.create_thread(name=thread_name)
            except discord.errors.Forbidden:
                # スレッド作成権限がない場合はメンション応答型にフォールバック
                logger.warning(
                    f"No permission to create thread in channel {message.channel.id}, falling back to mention mode"
                )
                await self.mention_handler.handle(message)
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
                            await message.reply(ErrorMessages.GENERIC)
                            return False
                    except Exception as fetch_error:
                        logger.warning(
                            f"Failed to fetch message {message.id} after thread creation error: {fetch_error}"
                        )
                        await message.reply(ErrorMessages.GENERIC)
                        return False
                else:
                    # その他のHTTPException
                    logger.error(f"HTTPException during thread creation: {e}")
                    await message.reply(ErrorMessages.GENERIC)
                    return False
            except Exception as e:
                # 予期しないエラー
                logger.exception(f"Unexpected error during thread creation: {e}")
                await message.reply(ErrorMessages.GENERIC)
                return False

        try:
            # スレッドを記録
            self.router.register_bot_thread(thread.id)

            # セッションキーを生成
            session_key = f"thread:{thread.id}"

            # セッションを取得または作成
            session = await self.session_manager.get_session(session_key)
            if not session:
                # ⚠️ 重要: guild_id は Discord URL生成に必要
                guild_id = thread.guild.id if thread.guild else None
                session = await self.session_manager.create_session(
                    session_key=session_key,
                    session_type="thread",
                    guild_id=guild_id,
                    channel_id=message.channel.id,
                    thread_id=thread.id,
                    user_id=message.author.id,
                )
                logger.info(f"Created new thread session: {session_key}")

            # ユーザーメッセージを追加
            await self.session_manager.add_message(
                session_key=session_key,
                role=MessageRole.USER,
                content=user_message,
            )

            # AI応答を生成
            async with thread.typing():
                # 現在の日付情報を含むシステムプロンプトを生成
                current_date_info = format_datetime_for_prompt()
                system_prompt = DEFAULT_SYSTEM_PROMPT + current_date_info

                # AI応答を生成
                response_text, token_info = await self.ai_provider.generate_response(
                    messages=session.get_conversation_history(),
                    system_prompt=system_prompt,
                )

                # アシスタントメッセージを追加
                await self.session_manager.add_message(
                    session_key=session_key,
                    role=MessageRole.ASSISTANT,
                    content=response_text,
                )

                # セッションを保存
                await self.session_manager.save_session(session_key)

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
            await message.reply(ErrorMessages.GENERIC)
            return False

    async def _process_message(self, message: discord.Message) -> None:
        """既存スレッド内でのメッセージ処理の実装.

        Args:
            message: Discord メッセージ
        """
        # message.channel は既に Thread 型であることが確認済み
        if not isinstance(message.channel, discord.Thread):
            logger.error(f"Expected Thread but got {type(message.channel)}")
            return

        thread = message.channel
        session_key = f"thread:{thread.id}"

        # セッションを取得または作成
        session = await self.session_manager.get_session(session_key)
        if not session:
            # スレッドが既に存在する場合、会話履歴を復元
            # ⚠️ 重要: guild_id は Discord URL生成に必要
            guild_id = thread.guild.id if thread.guild else None
            parent_id = thread.parent_id if thread.parent_id else None
            session = await self.session_manager.create_session(
                session_key=session_key,
                session_type="thread",
                guild_id=guild_id,
                channel_id=parent_id,
                thread_id=thread.id,
                user_id=message.author.id,
            )
            logger.info(f"Created thread session from existing thread: {session_key}")

        # ユーザーメッセージを追加
        await self.session_manager.add_message(
            session_key=session_key,
            role=MessageRole.USER,
            content=message.content,
        )

        # AI応答を生成
        try:
            async with thread.typing():
                # 現在の日付情報を含むシステムプロンプトを生成
                current_date_info = format_datetime_for_prompt()
                system_prompt = DEFAULT_SYSTEM_PROMPT + current_date_info

                # AI応答を生成
                response_text, token_info = await self.ai_provider.generate_response(
                    messages=session.get_conversation_history(),
                    system_prompt=system_prompt,
                )

                # アシスタントメッセージを追加
                await self.session_manager.add_message(
                    session_key=session_key,
                    role=MessageRole.ASSISTANT,
                    content=response_text,
                )

                # セッションを保存
                await self.session_manager.save_session(session_key)

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
                    await message.reply(ErrorMessages.GENERIC)
                except Exception as reply_error:
                    logger.error(f"Failed to send error message: {reply_error}")
