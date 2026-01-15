"""Discord イベントハンドラー"""

import asyncio
import logging
from datetime import datetime, timedelta

import discord
from discord.ext import tasks

from ..ai.litellm_provider import LiteLLMProvider
from ..ai.prompts import DEFAULT_SYSTEM_PROMPT
from ..session.manager import SessionManager
from ..session.models import MessageRole
from ..utils.message_splitter import format_split_messages, split_message
from .client import KotonohaBot

logger = logging.getLogger(__name__)


class MessageHandler:
    """メッセージハンドラー"""

    def __init__(self, bot: KotonohaBot):
        self.bot = bot
        self.session_manager = SessionManager()
        self.ai_provider = LiteLLMProvider()
        # タスクは on_ready イベントで開始する（イベントループが必要なため）

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

    async def handle_mention(self, message: discord.Message):
        """メンション時の処理"""
        # Bot自身のメッセージは無視
        if message.author.bot:
            return

        # Botがメンションされているか確認
        if self.bot.user not in message.mentions:
            return

        logger.info(f"Mention from {message.author} in {message.channel}")

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
                response_text = self.ai_provider.generate_response(
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

                # 最初のメッセージは reply で送信
                if formatted_chunks:
                    await message.reply(formatted_chunks[0])

                    # 残りのメッセージは順次送信
                    for chunk in formatted_chunks[1:]:
                        await message.channel.send(chunk)
                        # レート制限を考慮して少し待機
                        await asyncio.sleep(0.5)

                logger.info(f"Sent response to {message.author}")

        except Exception as e:
            logger.exception(f"Error handling mention: {e}")
            await message.reply(
                "すみません。一時的に反応できませんでした。\n"
                "少し時間をおいて、もう一度試してみてください。"
            )


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

    @bot.event
    async def on_message(message: discord.Message):
        """メッセージ受信時"""
        # Bot自身のメッセージは無視
        if message.author.bot:
            await bot.process_commands(message)
            return

        # メンション処理（メンションされている場合のみ）
        if bot.user in message.mentions:
            await handler.handle_mention(message)
            # メンション処理後はコマンド処理をスキップ（重複応答を防ぐ）
            return

        # コマンド処理（メンションでない場合のみ）
        await bot.process_commands(message)

    logger.info("Event handlers registered")

    return handler
