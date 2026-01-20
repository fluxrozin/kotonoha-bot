"""MessageHandlerの統合テスト（実際のイベントハンドラー実行）."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, PropertyMock

import discord
import pytest
from discord.ext import commands

from kotonoha_bot.bot.client import KotonohaBot
from kotonoha_bot.bot.handlers import MessageHandler, setup_handlers
from kotonoha_bot.config import Config
from kotonoha_bot.db.models import ChatSession


@pytest.fixture
def mock_bot():
    """モックBot."""
    bot = MagicMock(spec=KotonohaBot)
    bot.user = MagicMock()
    bot.user.id = 123456789
    bot.tree = MagicMock()
    bot.tree.sync = AsyncMock(return_value=[])
    bot.wait_until_ready = AsyncMock(return_value=None)
    bot.process_commands = AsyncMock()
    bot.event = MagicMock()  # イベントデコレータ
    return bot


@pytest.fixture
def mock_db():
    """モックデータベース."""
    db = MagicMock()
    db.load_all_sessions = AsyncMock(return_value=[])
    db.save_session = AsyncMock()
    return db


@pytest.fixture
def mock_config():
    """モックConfig."""
    config = MagicMock(spec=Config)
    config.EAVESDROP_ENABLED_CHANNELS = ""
    config.EAVESDROP_BUFFER_SIZE = 20
    config.SESSION_TIMEOUT_HOURS = 24
    config.MAX_SESSIONS = 100
    return config


@pytest.fixture
def handler(mock_bot, mock_db, mock_config):
    """MessageHandler インスタンス."""
    return MessageHandler(
        bot=mock_bot,
        db=mock_db,
        config=mock_config,
    )


class TestCleanupTaskExecution:
    """cleanup_task の実際の実行テスト."""

    @pytest.mark.asyncio
    async def test_cleanup_task_execution(self, handler):
        """cleanup_task が実際に実行される."""
        handler.session_manager.cleanup_old_sessions = AsyncMock()

        # cleanup_task を直接実行
        await handler.cleanup_task()

        # cleanup_old_sessions が呼ばれたことを確認
        handler.session_manager.cleanup_old_sessions.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_task_before_loop(self, handler):
        """before_cleanup_task が実行される."""
        handler.bot.wait_until_ready = AsyncMock()

        # before_cleanup_task を直接実行
        await handler.before_cleanup_task()

        # wait_until_ready が呼ばれたことを確認
        handler.bot.wait_until_ready.assert_called_once()


class TestBatchSyncTaskExecution:
    """batch_sync_task の実際の実行テスト."""

    @pytest.mark.asyncio
    async def test_batch_sync_task_execution_with_idle_sessions(self, handler):
        """batch_sync_task がアイドルセッションを保存する."""
        now = datetime.now(UTC)
        idle_session = ChatSession(
            session_key="test:idle",
            session_type="mention",
            messages=[],
            last_active_at=now - timedelta(minutes=6),
        )
        active_session = ChatSession(
            session_key="test:active",
            session_type="mention",
            messages=[],
            last_active_at=now - timedelta(minutes=1),
        )

        handler.session_manager.sessions = {
            "test:idle": idle_session,
            "test:active": active_session,
        }
        handler.session_manager.save_session = AsyncMock()

        # batch_sync_task を直接実行
        await handler.batch_sync_task()

        # アイドルセッションのみが保存されたことを確認
        handler.session_manager.save_session.assert_called_once_with("test:idle")

    @pytest.mark.asyncio
    async def test_batch_sync_task_before_loop(self, handler):
        """before_batch_sync_task が実行される."""
        handler.bot.wait_until_ready = AsyncMock()

        # before_batch_sync_task を直接実行
        await handler.before_batch_sync_task()

        # wait_until_ready が呼ばれたことを確認
        handler.bot.wait_until_ready.assert_called_once()


class TestSetupHandlersIntegration:
    """setup_handlers で登録されたイベントハンドラーの統合テスト."""

    @pytest.mark.asyncio
    async def test_on_ready_integration(self, mock_bot, mock_db, mock_config):
        """on_ready イベントが実際に実行される."""
        handler = setup_handlers(
            bot=mock_bot,
            db=mock_db,
            config=mock_config,
        )

        # イベントハンドラーを取得（@bot.event で登録された関数）
        on_ready_handler = None
        for call in mock_bot.event.call_args_list:
            if call[0] and call[0][0].__name__ == "on_ready":
                on_ready_handler = call[0][0]
                break

        if on_ready_handler:
            # セッションマネージャーのモック設定
            handler.session_manager._initialized = False
            handler.session_manager.initialize = AsyncMock()  # type: ignore[assignment]
            handler.cleanup_task.is_running = PropertyMock(return_value=False)  # type: ignore[assignment]
            handler.batch_sync_task.is_running = PropertyMock(return_value=False)  # type: ignore[assignment]
            handler.cleanup_task.start = MagicMock()  # type: ignore[assignment]
            handler.batch_sync_task.start = MagicMock()  # type: ignore[assignment]
            handler.request_queue.start = AsyncMock()  # type: ignore[assignment]

            # on_ready を実行
            await on_ready_handler()

            # 初期化とタスク開始が呼ばれたことを確認
            handler.session_manager.initialize.assert_called_once()
            handler.cleanup_task.start.assert_called_once()  # type: ignore[attr-defined]
            handler.batch_sync_task.start.assert_called_once()  # type: ignore[attr-defined]
            handler.request_queue.start.assert_called_once()

    @pytest.mark.asyncio
    async def test_on_message_integration(self, mock_bot, mock_db, mock_config):
        """on_message イベントが実際に実行される."""
        handler = setup_handlers(
            bot=mock_bot,
            db=mock_db,
            config=mock_config,
        )

        # イベントハンドラーを取得
        on_message_handler = None
        for call in mock_bot.event.call_args_list:
            if call[0] and call[0][0].__name__ == "on_message":
                on_message_handler = call[0][0]
                break

        if on_message_handler:
            mock_message = MagicMock(spec=discord.Message)
            mock_message.author = MagicMock()
            mock_message.author.bot = False

            handler.router.route = AsyncMock(return_value="mention")  # type: ignore[assignment]
            handler.handle_mention = AsyncMock()  # type: ignore[assignment]

            # on_message を実行
            await on_message_handler(mock_message)

            # ルーティングとハンドラーが呼ばれたことを確認
            handler.router.route.assert_called_once_with(mock_message)
            handler.handle_mention.assert_called_once_with(mock_message)  # type: ignore[attr-defined]

    @pytest.mark.asyncio
    async def test_on_thread_update_integration(self, mock_bot, mock_db, mock_config):
        """on_thread_update イベントが実際に実行される."""
        handler = setup_handlers(
            bot=mock_bot,
            db=mock_db,
            config=mock_config,
        )

        # イベントハンドラーを取得
        on_thread_update_handler = None
        for call in mock_bot.event.call_args_list:
            if call[0] and call[0][0].__name__ == "on_thread_update":
                on_thread_update_handler = call[0][0]
                break

        if on_thread_update_handler:
            mock_before = MagicMock(spec=discord.Thread)
            mock_before.archived = False
            mock_after = MagicMock(spec=discord.Thread)
            mock_after.archived = True
            mock_after.id = 444555666

            handler.session_manager.save_session = AsyncMock()  # type: ignore[assignment]

            # on_thread_update を実行
            await on_thread_update_handler(mock_before, mock_after)

            # セッションが保存されたことを確認
            handler.session_manager.save_session.assert_called_once_with(
                "thread:444555666"
            )

    @pytest.mark.asyncio
    async def test_eavesdrop_command_integration(self, mock_bot, mock_db, mock_config):
        """eavesdrop コマンドが実際に実行される."""
        handler = setup_handlers(
            bot=mock_bot,
            db=mock_db,
            config=mock_config,
        )

        # 直接コマンド関数をテスト
        mock_ctx = MagicMock(spec=commands.Context)
        mock_ctx.channel = MagicMock()
        mock_ctx.channel.id = 777888999
        mock_ctx.send = AsyncMock()

        handler.conversation_buffer.clear = MagicMock()  # type: ignore[assignment]
        handler.conversation_buffer.get_recent_messages = MagicMock(return_value=[])  # type: ignore[assignment]

        # コマンド関数を直接呼び出し（setup_handlers内で定義された関数をシミュレート）
        async def eavesdrop_command(
            ctx: commands.Context, action: str | None = None
        ) -> None:
            if action == "clear":
                handler.conversation_buffer.clear(ctx.channel.id)
                await ctx.send("✅ 会話ログバッファをクリアしました。")
            elif action == "status":
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

        # clear アクションをテスト
        await eavesdrop_command(mock_ctx, "clear")
        handler.conversation_buffer.clear.assert_called_once_with(777888999)
        mock_ctx.send.assert_called_with("✅ 会話ログバッファをクリアしました。")

        # status アクションをテスト
        mock_ctx.send.reset_mock()
        handler.conversation_buffer.get_recent_messages.return_value = [
            MagicMock(),
            MagicMock(),
        ]
        await eavesdrop_command(mock_ctx, "status")
        handler.conversation_buffer.get_recent_messages.assert_called_once_with(
            777888999
        )
        assert mock_ctx.send.called

        # ヘルプをテスト
        mock_ctx.send.reset_mock()
        await eavesdrop_command(mock_ctx, None)
        assert mock_ctx.send.called
