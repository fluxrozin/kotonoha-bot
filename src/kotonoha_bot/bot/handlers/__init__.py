"""Discord イベントハンドラー（Facade）。."""

import logging
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import discord
from discord.ext import commands, tasks

from kotonoha_bot.bot.client import KotonohaBot
from kotonoha_bot.bot.router import MessageRouter
from kotonoha_bot.config import Config
from kotonoha_bot.rate_limit.request_queue import RequestQueue
from kotonoha_bot.services.ai import AnthropicProvider
from kotonoha_bot.services.eavesdrop import ConversationBuffer, LLMJudge
from kotonoha_bot.services.session import SessionManager

from .eavesdrop import EavesdropHandler
from .mention import MentionHandler
from .thread import ThreadHandler

if TYPE_CHECKING:
    from kotonoha_bot.db.postgres import PostgreSQLDatabase
    from kotonoha_bot.features.knowledge_base.embedding_processor import (
        EmbeddingProcessor,
    )
    from kotonoha_bot.features.knowledge_base.session_archiver import SessionArchiver

logger = logging.getLogger(__name__)


class MessageHandler:
    """メッセージハンドラー（統合Facade）."""

    def __init__(
        self,
        bot: KotonohaBot,
        embedding_processor: EmbeddingProcessor | None = None,
        session_archiver: SessionArchiver | None = None,
        db: PostgreSQLDatabase | None = None,
        config: Config | None = None,
    ):
        """MessageHandler を初期化.

        Args:
            bot: Discord クライアント
            embedding_processor: EmbeddingProcessorインスタンス（依存性注入）
            session_archiver: SessionArchiverインスタンス（依存性注入）
            db: PostgreSQLDatabaseインスタンス（依存性注入、Alembic重複防止）
            config: 設定インスタンス（依存性注入、必須）

        Raises:
            ValueError: config が None の場合
        """
        if config is None:
            raise ValueError("config parameter is required (DI pattern)")
        self.bot = bot
        self.config = config
        # DBインスタンスが渡された場合は使用（Alembicマイグレーションの重複を防ぐ）
        # 注: db は必須（DIパターン）
        if db is None:
            raise ValueError("db parameter is required for SessionManager")
        self.session_manager = SessionManager(db=db, config=self.config)
        self.ai_provider = AnthropicProvider(config=self.config)
        # メッセージルーター
        self.router = MessageRouter(bot)
        # 聞き耳型の機能
        self.conversation_buffer = ConversationBuffer(
            max_size=self.config.EAVESDROP_BUFFER_SIZE
        )
        self.llm_judge = LLMJudge(
            self.session_manager, self.ai_provider, config=self.config
        )
        # リクエストキュー
        self.request_queue = RequestQueue(max_size=100)
        # タスクは on_ready イベントで開始する（イベントループが必要なため）
        # 聞き耳型の有効化（環境変数から読み込み）
        self._load_eavesdrop_channels()

        # 依存性注入（main.pyから渡される）
        self.embedding_processor = embedding_processor
        self.session_archiver = session_archiver

        # 各ハンドラーのインスタンス化（依存を渡す）
        self.mention = MentionHandler(
            self.bot,
            self.session_manager,
            self.ai_provider,
            self.request_queue,
            self.config,
        )
        self.thread = ThreadHandler(
            self.bot,
            self.session_manager,
            self.ai_provider,
            self.router,
            self.request_queue,
            self.mention,
            self.config,
        )
        self.eavesdrop = EavesdropHandler(
            self.bot,
            self.session_manager,
            self.ai_provider,
            self.llm_judge,
            self.conversation_buffer,
            self.router,
            self.request_queue,
            self.config,
        )

    def cog_unload(self) -> None:
        """クリーンアップタスクを停止（Graceful Shutdown）."""
        self.cleanup_task.cancel()
        self.batch_sync_task.cancel()

        # Graceful Shutdown: 処理中のタスクが完了するまで待機
        # 注意: このメソッドは同期的なので、実際のGraceful Shutdownは
        # main.pyのshutdown_gracefully関数で実行されます

    @tasks.loop(hours=1)  # 1時間ごとに実行
    async def cleanup_task(self) -> None:
        """定期的なセッションクリーンアップ."""
        try:
            logger.info("Running scheduled session cleanup...")
            await self.session_manager.cleanup_old_sessions()
            logger.info("Session cleanup completed")
        except Exception as e:
            logger.error(f"Error during session cleanup: {e}")

    @cleanup_task.before_loop
    async def before_cleanup_task(self) -> None:
        """クリーンアップタスク開始前の待機."""
        await self.bot.wait_until_ready()

    @tasks.loop(minutes=5)  # 5分ごとに実行
    async def batch_sync_task(self) -> None:
        """定期的なバッチ同期（アイドル状態のセッションを保存）."""
        try:
            logger.info("Running batch sync...")

            # アイドル状態のセッションを保存
            # 最後のアクティビティから5分以上経過しているセッションを保存
            now = datetime.now(UTC)
            idle_threshold = timedelta(minutes=5)

            saved_count = 0
            for session_key, session in self.session_manager.sessions.items():
                last_active = session.last_active_at
                if last_active.tzinfo is None:
                    last_active = last_active.replace(tzinfo=UTC)
                time_since_activity = now - last_active
                if time_since_activity >= idle_threshold:
                    try:
                        await self.session_manager.save_session(session_key)
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
    async def before_batch_sync_task(self) -> None:
        """バッチ同期タスク開始前の待機."""
        await self.bot.wait_until_ready()

    def _load_eavesdrop_channels(self) -> None:
        """環境変数から聞き耳型の有効チャンネルを読み込み."""
        if self.config.EAVESDROP_ENABLED_CHANNELS:
            channel_ids = [
                int(cid.strip())
                for cid in self.config.EAVESDROP_ENABLED_CHANNELS.split(",")
                if cid.strip()
            ]
            for channel_id in channel_ids:
                self.router.enable_eavesdrop_for_channel(channel_id)
                logger.info(f"Loaded eavesdrop channel from config: {channel_id}")

    async def handle_mention(self, message: discord.Message) -> None:
        """メンション時の処理（Facade）."""
        await self.mention.handle(message)

    async def handle_thread(self, message: discord.Message) -> None:
        """スレッド型の処理（Facade）."""
        await self.thread.handle(message)

    async def handle_eavesdrop(self, message: discord.Message) -> None:
        """聞き耳型の処理（Facade）."""
        await self.eavesdrop.handle(message)


def setup_handlers(
    bot: KotonohaBot,
    embedding_processor: EmbeddingProcessor | None = None,
    session_archiver: SessionArchiver | None = None,
    db: PostgreSQLDatabase | None = None,
    config: Config | None = None,
) -> MessageHandler:
    """イベントハンドラーをセットアップ.

    Args:
        bot: KotonohaBotインスタンス
        embedding_processor: EmbeddingProcessorインスタンス（依存性注入）
        session_archiver: SessionArchiverインスタンス（依存性注入）
        db: PostgreSQLDatabaseインスタンス（依存性注入、Alembic重複防止）
        config: 設定インスタンス（依存性注入、必須）

    Returns:
        MessageHandler インスタンス（Facade）

    Raises:
        ValueError: config が None の場合
    """
    handler = MessageHandler(
        bot,
        embedding_processor=embedding_processor,
        session_archiver=session_archiver,
        db=db,
        config=config,
    )

    @bot.event
    async def on_ready() -> None:
        """Bot起動完了時."""
        logger.info(f"Bot is ready! Logged in as {bot.user}")
        # セッション管理の初期化（公開APIを使用してチェック）
        if not handler.session_manager.is_initialized:
            await handler.session_manager.initialize()
            logger.info("Session manager initialized")
        else:
            logger.debug("Session manager already initialized")
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

        # スラッシュコマンドを同期（bot.start() 後に application_id が設定されるため）
        try:
            synced = await bot.tree.sync()
            logger.info(f"Synced {len(synced)} slash command(s)")
        except Exception as e:
            logger.error(f"Failed to sync slash commands: {e}")

        # バックグラウンドタスクを開始（EmbeddingProcessor, SessionArchiver）
        # ⚠️ 重要: bot.start() はブロッキング呼び出しのため、
        # main.py の bot.start() 後のコードは実行されません。
        # そのため、バックグラウンドタスクは on_ready で開始する必要があります。
        if handler.embedding_processor is not None:
            handler.embedding_processor.start()
            logger.info("Embedding processor background task started")
        if handler.session_archiver is not None:
            handler.session_archiver.start()
            logger.info("Session archiver background task started")

    @bot.event
    async def on_message(message: discord.Message) -> None:
        """メッセージ受信時."""
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
    async def on_thread_update(before: discord.Thread, after: discord.Thread) -> None:
        """スレッド更新時."""
        # アーカイブされた場合
        if after.archived and not before.archived:
            session_key = f"thread:{after.id}"
            try:
                # セッションを保存
                await handler.session_manager.save_session(session_key)
                logger.info(f"Saved session on thread archive: {session_key}")
            except Exception as e:
                logger.error(f"Failed to save session on thread archive: {e}")

    @bot.command(name="eavesdrop")
    async def eavesdrop_command(
        ctx: commands.Context, action: str | None = None
    ) -> None:
        """聞き耳型の開発用コマンド.

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
                f"- 最大サイズ: {handler.config.EAVESDROP_BUFFER_SIZE}件"
            )
        else:
            await ctx.send(
                "使用方法:\n"
                "`!eavesdrop clear` - 会話ログバッファをクリア\n"
                "`!eavesdrop status` - バッファ状態を表示"
            )

    logger.info("Event handlers registered")

    return handler


__all__ = ["MessageHandler", "setup_handlers"]
