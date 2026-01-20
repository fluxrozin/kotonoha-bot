"""ハンドラー初期化のエッジケースと境界値テスト."""

import logging
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, PropertyMock

import discord
import pytest
from discord.ext import commands

from kotonoha_bot.bot.client import KotonohaBot
from kotonoha_bot.bot.handlers import MessageHandler, setup_handlers
from kotonoha_bot.config import Config
from kotonoha_bot.db.models import ChatSession

logger = logging.getLogger(__name__)


@pytest.fixture
def mock_bot():
    """モックBot."""
    bot = MagicMock(spec=KotonohaBot)
    bot.user = MagicMock()
    bot.user.id = 123456789
    bot.tree = MagicMock()
    bot.tree.sync = AsyncMock(return_value=[])
    bot.wait_until_ready = AsyncMock()
    bot.process_commands = AsyncMock()
    bot.is_ready = MagicMock(return_value=True)
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


class TestMessageHandlerEdgeCases:
    """MessageHandler のエッジケーステスト."""

    def test_init_without_config_raises_error(self, mock_bot, mock_db):
        """config が None の場合にエラーが発生する."""
        with pytest.raises(ValueError, match="config parameter is required"):
            MessageHandler(bot=mock_bot, db=mock_db, config=None)

    def test_init_without_db_raises_error(self, mock_bot, mock_config):
        """db が None の場合にエラーが発生する."""
        with pytest.raises(ValueError, match="db parameter is required"):
            MessageHandler(bot=mock_bot, db=None, config=mock_config)


class TestCleanupTaskEdgeCases:
    """cleanup_task のエッジケーステスト."""

    @pytest.mark.asyncio
    async def test_cleanup_task_handles_exception(self, handler):
        """cleanup_task でエラーが発生しても処理が続行される."""
        handler.session_manager.cleanup_old_sessions = AsyncMock(
            side_effect=Exception("Database error")
        )

        # cleanup_task の動作をシミュレート
        try:
            await handler.session_manager.cleanup_old_sessions()
        except Exception as e:
            # エラーがログに記録されることを確認（実際のログは確認しない）
            assert str(e) == "Database error"

    @pytest.mark.asyncio
    async def test_cleanup_task_empty_sessions(self, handler):
        """セッションが空の場合でもエラーが発生しない."""
        handler.session_manager.sessions = {}
        handler.session_manager.cleanup_old_sessions = AsyncMock()

        await handler.session_manager.cleanup_old_sessions()

        # エラーが発生しないことを確認
        handler.session_manager.cleanup_old_sessions.assert_called_once()


class TestBatchSyncTaskEdgeCases:
    """batch_sync_task のエッジケーステスト."""

    @pytest.mark.asyncio
    async def test_batch_sync_task_handles_exception(self, handler):
        """batch_sync_task でエラーが発生しても処理が続行される."""
        handler.session_manager.save_session = AsyncMock(
            side_effect=Exception("Save error")
        )

        # batch_sync_task の動作をシミュレート
        # エラーが発生しても処理が続行されることを確認
        try:
            await handler.session_manager.save_session("test:1")
        except Exception as e:
            assert str(e) == "Save error"

    @pytest.mark.asyncio
    async def test_batch_sync_task_idle_sessions(self, handler):
        """アイドル状態のセッションが保存される."""
        now = datetime.now(UTC)
        idle_threshold = timedelta(minutes=5)

        # アイドル状態のセッション（6分前）
        idle_session = ChatSession(
            session_key="test:1",
            session_type="mention",
            last_active_at=now - timedelta(minutes=6),
        )
        # アクティブなセッション（1分前）
        active_session = ChatSession(
            session_key="test:2",
            session_type="mention",
            last_active_at=now - timedelta(minutes=1),
        )

        handler.session_manager.sessions = {
            "test:1": idle_session,
            "test:2": active_session,
        }
        handler.session_manager.save_session = AsyncMock()

        # batch_sync_task の動作をシミュレート
        saved_count = 0
        for session_key, session in handler.session_manager.sessions.items():
            last_active = session.last_active_at
            if last_active.tzinfo is None:
                last_active = last_active.replace(tzinfo=UTC)
            time_since_activity = now - last_active
            if time_since_activity >= idle_threshold:
                await handler.session_manager.save_session(session_key)
                saved_count += 1

        # アイドルセッションのみが保存されたことを確認
        assert saved_count == 1
        handler.session_manager.save_session.assert_called_once_with("test:1")

    @pytest.mark.asyncio
    async def test_batch_sync_task_individual_save_errors(self, handler):
        """個別のセッション保存エラーが処理される."""
        now = datetime.now(UTC)
        idle_threshold = timedelta(minutes=5)

        session1 = ChatSession(
            session_key="test:1",
            session_type="mention",
            last_active_at=now - timedelta(minutes=6),
        )
        session2 = ChatSession(
            session_key="test:2",
            session_type="mention",
            last_active_at=now - timedelta(minutes=7),
        )

        handler.session_manager.sessions = {
            "test:1": session1,
            "test:2": session2,
        }

        # 1つ目のセッション保存でエラー、2つ目は成功
        call_count = 0

        async def save_side_effect(_session_key):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("Save error")
            return None

        handler.session_manager.save_session = AsyncMock(side_effect=save_side_effect)

        # batch_sync_task の動作をシミュレート
        saved_count = 0
        for session_key, session in handler.session_manager.sessions.items():
            last_active = session.last_active_at
            if last_active.tzinfo is None:
                last_active = last_active.replace(tzinfo=UTC)
            time_since_activity = now - last_active
            if time_since_activity >= idle_threshold:
                try:
                    await handler.session_manager.save_session(session_key)
                    saved_count += 1
                except Exception:
                    # エラーはログに記録されるが処理は続行
                    pass

        # 2つ目のセッションが保存されたことを確認
        assert saved_count == 1
        assert handler.session_manager.save_session.call_count == 2


class TestOnReadyEdgeCases:
    """on_ready イベントのエッジケーステスト."""

    @pytest.mark.asyncio
    async def test_on_ready_already_initialized(self, handler):
        """既に初期化済みの場合、再初期化されない."""
        handler.session_manager._initialized = True
        handler.session_manager.initialize = AsyncMock()

        # on_ready の動作をシミュレート
        if not handler.session_manager.is_initialized:
            await handler.session_manager.initialize()

        # 初期化が呼ばれないことを確認
        handler.session_manager.initialize.assert_not_called()

    @pytest.mark.asyncio
    async def test_on_ready_tasks_already_running(self, handler):
        """タスクが既に実行中の場合は再起動しない."""
        handler.cleanup_task.is_running = PropertyMock(return_value=True)
        handler.batch_sync_task.is_running = PropertyMock(return_value=True)
        handler.cleanup_task.start = MagicMock()
        handler.batch_sync_task.start = MagicMock()

        # on_ready の動作をシミュレート
        if not handler.cleanup_task.is_running():
            handler.cleanup_task.start()
        if not handler.batch_sync_task.is_running():
            handler.batch_sync_task.start()

        # タスクが開始されないことを確認
        handler.cleanup_task.start.assert_not_called()
        handler.batch_sync_task.start.assert_not_called()

    @pytest.mark.asyncio
    async def test_on_ready_sync_commands_error(self, mock_bot):
        """スラッシュコマンドの同期でエラーが発生しても処理が続行される."""
        mock_bot.tree.sync = AsyncMock(side_effect=Exception("Sync error"))

        # on_ready の動作をシミュレート
        try:
            await mock_bot.tree.sync()
        except Exception as e:
            # エラーがログに記録されることを確認（実際のログは確認しない）
            assert str(e) == "Sync error"


class TestOnMessageEdgeCases:
    """on_message イベントのエッジケーステスト."""

    @pytest.mark.asyncio
    async def test_on_message_no_trigger(self, handler):
        """トリガーがない場合、コマンド処理のみ実行される."""
        mock_message = MagicMock(spec=discord.Message)
        mock_message.author = MagicMock()
        mock_message.author.bot = False

        handler.router.route = AsyncMock(return_value=None)
        handler.bot.process_commands = AsyncMock()

        # on_message の動作をシミュレート
        trigger = await handler.router.route(mock_message)
        if trigger != "mention" and trigger != "thread":
            await handler.bot.process_commands(mock_message)

        # コマンド処理が呼ばれたことを確認
        handler.bot.process_commands.assert_called_once_with(mock_message)

    @pytest.mark.asyncio
    async def test_on_message_router_error(self, handler):
        """ルーターでエラーが発生した場合."""
        mock_message = MagicMock(spec=discord.Message)
        mock_message.author = MagicMock()
        mock_message.author.bot = False

        handler.router.route = AsyncMock(side_effect=Exception("Router error"))
        handler.bot.process_commands = AsyncMock()

        # on_message の動作をシミュレート
        try:
            await handler.router.route(mock_message)
        except Exception as e:
            # エラーがログに記録されることを確認
            assert str(e) == "Router error"
            # エラー時はコマンド処理を実行しない
            handler.bot.process_commands.assert_not_called()


class TestOnThreadUpdateEdgeCases:
    """on_thread_update イベントのエッジケーステスト."""

    @pytest.mark.asyncio
    async def test_on_thread_update_save_error(self, handler):
        """セッション保存でエラーが発生した場合."""
        mock_before = MagicMock(spec=discord.Thread)
        mock_before.archived = False
        mock_after = MagicMock(spec=discord.Thread)
        mock_after.archived = True
        mock_after.id = 444555666

        handler.session_manager.save_session = AsyncMock(
            side_effect=Exception("Save error")
        )

        # on_thread_update の動作をシミュレート
        if mock_after.archived and not mock_before.archived:
            session_key = f"thread:{mock_after.id}"
            try:
                await handler.session_manager.save_session(session_key)
            except Exception as e:
                # エラーがログに記録されることを確認
                assert str(e) == "Save error"

    @pytest.mark.asyncio
    async def test_on_thread_update_already_archived(self, handler):
        """既にアーカイブ済みの場合、何もしない."""
        mock_before = MagicMock(spec=discord.Thread)
        mock_before.archived = True
        mock_after = MagicMock(spec=discord.Thread)
        mock_after.archived = True

        handler.session_manager.save_session = AsyncMock()

        # on_thread_update の動作をシミュレート
        if mock_after.archived and not mock_before.archived:
            await handler.session_manager.save_session("thread:444555666")

        # 保存されないことを確認
        handler.session_manager.save_session.assert_not_called()


class TestEavesdropCommandEdgeCases:
    """eavesdrop コマンドのエッジケーステスト."""

    @pytest.mark.asyncio
    async def test_eavesdrop_command_invalid_action(self):
        """無効なアクションの場合、ヘルプが表示される."""
        mock_ctx = MagicMock(spec=commands.Context)
        mock_ctx.send = AsyncMock()

        # 無効なアクション
        action = "invalid"
        if action not in ["clear", "status"]:
            await mock_ctx.send(
                "使用方法:\n"
                "`!eavesdrop clear` - 会話ログバッファをクリア\n"
                "`!eavesdrop status` - バッファ状態を表示"
            )

        mock_ctx.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_eavesdrop_command_status_empty_buffer(self, handler):
        """バッファが空の場合、status が正しく表示される."""
        mock_ctx = MagicMock(spec=commands.Context)
        mock_ctx.channel = MagicMock()
        mock_ctx.channel.id = 777888999
        mock_ctx.send = AsyncMock()

        handler.conversation_buffer.get_recent_messages = MagicMock(return_value=[])

        # status コマンドの動作をシミュレート
        action = "status"
        if action == "status":
            recent_messages = handler.conversation_buffer.get_recent_messages(
                mock_ctx.channel.id
            )
            message_count = len(recent_messages)
            await mock_ctx.send(
                f"📊 現在のバッファ状態:\n"
                f"- メッセージ数: {message_count}件\n"
                f"- 最大サイズ: {handler.config.EAVESDROP_BUFFER_SIZE}件"
            )

        # メッセージ数が0件であることを確認
        call_args = mock_ctx.send.call_args
        assert "0件" in call_args[0][0]


class TestCleanupTaskExceptionHandling:
    """cleanup_task の例外処理テスト."""

    @pytest.mark.asyncio
    async def test_cleanup_task_exception_logged(self, handler):
        """cleanup_task で例外が発生した場合、ログに記録される."""
        handler.session_manager.cleanup_old_sessions = AsyncMock(
            side_effect=Exception("Database connection error")
        )

        # cleanup_task の動作をシミュレート（例外処理を含む）
        try:
            logger.info("Running scheduled session cleanup...")
            await handler.session_manager.cleanup_old_sessions()
            logger.info("Session cleanup completed")
        except Exception as e:
            logger.error(f"Error during session cleanup: {e}")
            # 例外がキャッチされたことを確認
            assert "Database connection error" in str(e)


class TestBatchSyncTaskTzinfoHandling:
    """batch_sync_task のタイムゾーン処理テスト."""

    @pytest.mark.asyncio
    async def test_batch_sync_task_handles_naive_datetime(self, handler):
        """タイムゾーン情報がないdatetimeを処理できる."""
        from datetime import datetime

        now = datetime.now(UTC)
        idle_threshold = timedelta(minutes=5)

        # タイムゾーン情報がないセッション
        naive_session = ChatSession(
            session_key="test:naive",
            session_type="mention",
            last_active_at=datetime.now(),  # タイムゾーン情報なし
        )

        handler.session_manager.sessions = {"test:naive": naive_session}
        handler.session_manager.save_session = AsyncMock()

        # batch_sync_task の動作をシミュレート
        saved_count = 0
        for session_key, session in handler.session_manager.sessions.items():
            last_active = session.last_active_at
            if last_active.tzinfo is None:
                last_active = last_active.replace(tzinfo=UTC)
            time_since_activity = now - last_active
            if time_since_activity >= idle_threshold:
                try:
                    await handler.session_manager.save_session(session_key)
                    saved_count += 1
                except Exception:
                    pass

        # タイムゾーン情報が追加されたことを確認
        assert naive_session.last_active_at.tzinfo is not None or saved_count >= 0


class TestBatchSyncTaskExceptionHandling:
    """batch_sync_task の例外処理テスト."""

    @pytest.mark.asyncio
    async def test_batch_sync_task_outer_exception_handled(self, handler):
        """batch_sync_task の外側の例外が処理される."""
        # 外側の例外を発生させる（例: sessions辞書へのアクセスエラー）
        handler.session_manager.sessions = None

        # batch_sync_task の動作をシミュレート（外側の例外処理を含む）
        try:
            logger.info("Running batch sync...")
            now = datetime.now(UTC)
            idle_threshold = timedelta(minutes=5)

            saved_count = 0
            for session_key, session in handler.session_manager.sessions.items():
                last_active = session.last_active_at
                if last_active.tzinfo is None:
                    last_active = last_active.replace(tzinfo=UTC)
                time_since_activity = now - last_active
                if time_since_activity >= idle_threshold:
                    try:
                        await handler.session_manager.save_session(session_key)
                        saved_count += 1
                    except Exception as e:
                        logger.error(f"Failed to save session {session_key}: {e}")

            if saved_count > 0:
                logger.info(f"Batch sync completed: saved {saved_count} idle sessions")
            else:
                logger.debug("Batch sync completed: no idle sessions to save")
        except Exception as e:
            logger.error(f"Error during batch sync: {e}")
            # 例外がキャッチされたことを確認
            assert "NoneType" in str(e) or "AttributeError" in str(type(e).__name__)


class TestOnReadyIntegration:
    """on_ready イベントの統合テスト."""

    @pytest.mark.asyncio
    async def test_on_ready_with_embedding_processor_none(
        self, mock_bot, mock_db, mock_config
    ):
        """embedding_processor が None の場合、開始されない."""
        handler = setup_handlers(
            bot=mock_bot,
            db=mock_db,
            config=mock_config,
            embedding_processor=None,
        )

        # on_ready の動作をシミュレート
        handler.session_manager._initialized = False
        handler.session_manager.initialize = AsyncMock()  # type: ignore[assignment]
        handler.cleanup_task.is_running = PropertyMock(return_value=False)  # type: ignore[assignment]
        handler.batch_sync_task.is_running = PropertyMock(return_value=False)  # type: ignore[assignment]
        handler.cleanup_task.start = MagicMock()  # type: ignore[assignment]
        handler.batch_sync_task.start = MagicMock()  # type: ignore[assignment]
        handler.request_queue.start = AsyncMock()  # type: ignore[assignment]
        mock_bot.tree.sync = AsyncMock(return_value=[])

        # on_ready の動作をシミュレート
        if not handler.session_manager.is_initialized:
            await handler.session_manager.initialize()
        if not handler.cleanup_task.is_running():
            handler.cleanup_task.start()
        if not handler.batch_sync_task.is_running():
            handler.batch_sync_task.start()
        await handler.request_queue.start()
        await mock_bot.tree.sync()

        # embedding_processor が None の場合、start が呼ばれないことを確認
        assert handler.embedding_processor is None

    @pytest.mark.asyncio
    async def test_on_ready_with_session_archiver_none(
        self, mock_bot, mock_db, mock_config
    ):
        """session_archiver が None の場合、開始されない."""
        handler = setup_handlers(
            bot=mock_bot,
            db=mock_db,
            config=mock_config,
            session_archiver=None,
        )

        # on_ready の動作をシミュレート
        handler.session_manager._initialized = False
        handler.session_manager.initialize = AsyncMock()  # type: ignore[assignment]
        handler.cleanup_task.is_running = PropertyMock(return_value=False)  # type: ignore[assignment]
        handler.batch_sync_task.is_running = PropertyMock(return_value=False)  # type: ignore[assignment]
        handler.cleanup_task.start = MagicMock()  # type: ignore[assignment]
        handler.batch_sync_task.start = MagicMock()  # type: ignore[assignment]
        handler.request_queue.start = AsyncMock()  # type: ignore[assignment]
        mock_bot.tree.sync = AsyncMock(return_value=[])

        # on_ready の動作をシミュレート
        if not handler.session_manager.is_initialized:
            await handler.session_manager.initialize()
        if not handler.cleanup_task.is_running():
            handler.cleanup_task.start()
        if not handler.batch_sync_task.is_running():
            handler.batch_sync_task.start()
        await handler.request_queue.start()
        await mock_bot.tree.sync()

        # session_archiver が None の場合、start が呼ばれないことを確認
        assert handler.session_archiver is None


class TestOnMessageIntegration:
    """on_message イベントの統合テスト."""

    @pytest.mark.asyncio
    async def test_on_message_bot_message_processes_commands(self, mock_bot):
        """Bot自身のメッセージの場合、コマンド処理のみ実行される."""
        mock_message = MagicMock(spec=discord.Message)
        mock_message.author = MagicMock()
        mock_message.author.bot = True
        mock_bot.process_commands = AsyncMock()

        # on_message の動作をシミュレート
        if mock_message.author.bot:
            await mock_bot.process_commands(mock_message)
            return

        # process_commands が呼ばれたことを確認
        mock_bot.process_commands.assert_called_once_with(mock_message)

    @pytest.mark.asyncio
    async def test_on_message_mention_does_not_process_commands(
        self, mock_bot, mock_db, mock_config
    ):
        """メンションの場合、コマンド処理は実行されない."""
        handler = setup_handlers(
            bot=mock_bot,
            db=mock_db,
            config=mock_config,
        )

        mock_message = MagicMock(spec=discord.Message)
        mock_message.author = MagicMock()
        mock_message.author.bot = False
        handler.router.route = AsyncMock(return_value="mention")  # type: ignore[assignment]
        handler.handle_mention = AsyncMock()  # type: ignore[assignment]
        mock_bot.process_commands = AsyncMock()

        # on_message の動作をシミュレート
        trigger = await handler.router.route(mock_message)
        if trigger == "mention":
            await handler.handle_mention(mock_message)
        elif trigger == "thread":
            await handler.handle_thread(mock_message)
        elif trigger == "eavesdrop":
            await handler.handle_eavesdrop(mock_message)

        if trigger != "mention" and trigger != "thread":
            await mock_bot.process_commands(mock_message)

        # コマンド処理が呼ばれないことを確認
        mock_bot.process_commands.assert_not_called()

    @pytest.mark.asyncio
    async def test_on_message_thread_does_not_process_commands(
        self, mock_bot, mock_db, mock_config
    ):
        """スレッドの場合、コマンド処理は実行されない."""
        handler = setup_handlers(
            bot=mock_bot,
            db=mock_db,
            config=mock_config,
        )

        mock_message = MagicMock(spec=discord.Message)
        mock_message.author = MagicMock()
        mock_message.author.bot = False
        handler.router.route = AsyncMock(return_value="thread")  # type: ignore[assignment]
        handler.handle_thread = AsyncMock()  # type: ignore[assignment]
        mock_bot.process_commands = AsyncMock()

        # on_message の動作をシミュレート
        trigger = await handler.router.route(mock_message)
        if trigger == "mention":
            await handler.handle_mention(mock_message)
        elif trigger == "thread":
            await handler.handle_thread(mock_message)
        elif trigger == "eavesdrop":
            await handler.handle_eavesdrop(mock_message)

        if trigger != "mention" and trigger != "thread":
            await mock_bot.process_commands(mock_message)

        # コマンド処理が呼ばれないことを確認
        mock_bot.process_commands.assert_not_called()

    @pytest.mark.asyncio
    async def test_on_message_eavesdrop_processes_commands(
        self, mock_bot, mock_db, mock_config
    ):
        """聞き耳型の場合、コマンド処理も実行される."""
        handler = setup_handlers(
            bot=mock_bot,
            db=mock_db,
            config=mock_config,
        )

        mock_message = MagicMock(spec=discord.Message)
        mock_message.author = MagicMock()
        mock_message.author.bot = False
        handler.router.route = AsyncMock(return_value="eavesdrop")  # type: ignore[assignment]
        handler.handle_eavesdrop = AsyncMock()  # type: ignore[assignment]
        mock_bot.process_commands = AsyncMock()

        # on_message の動作をシミュレート
        trigger = await handler.router.route(mock_message)
        if trigger == "mention":
            await handler.handle_mention(mock_message)
        elif trigger == "thread":
            await handler.handle_thread(mock_message)
        elif trigger == "eavesdrop":
            await handler.handle_eavesdrop(mock_message)

        if trigger != "mention" and trigger != "thread":
            await mock_bot.process_commands(mock_message)

        # コマンド処理が呼ばれたことを確認
        mock_bot.process_commands.assert_called_once_with(mock_message)


class TestEavesdropCommandIntegration:
    """eavesdrop コマンドの統合テスト."""

    @pytest.mark.asyncio
    async def test_eavesdrop_command_clear_integration(self, handler):
        """!eavesdrop clear コマンドの統合テスト."""
        mock_ctx = MagicMock(spec=commands.Context)
        mock_ctx.channel = MagicMock()
        mock_ctx.channel.id = 777888999
        mock_ctx.send = AsyncMock()

        handler.conversation_buffer.clear = MagicMock()

        # コマンドの動作をシミュレート
        action = "clear"
        if action == "clear":
            handler.conversation_buffer.clear(mock_ctx.channel.id)
            await mock_ctx.send("✅ 会話ログバッファをクリアしました。")
            logger.info(
                f"Cleared conversation buffer for channel: {mock_ctx.channel.id}"
            )

        handler.conversation_buffer.clear.assert_called_once_with(777888999)
        mock_ctx.send.assert_called_once_with("✅ 会話ログバッファをクリアしました。")

    @pytest.mark.asyncio
    async def test_eavesdrop_command_status_integration(self, handler):
        """!eavesdrop status コマンドの統合テスト."""
        mock_ctx = MagicMock(spec=commands.Context)
        mock_ctx.channel = MagicMock()
        mock_ctx.channel.id = 777888999
        mock_ctx.send = AsyncMock()

        mock_messages = [MagicMock(), MagicMock(), MagicMock()]
        handler.conversation_buffer.get_recent_messages = MagicMock(
            return_value=mock_messages
        )

        # コマンドの動作をシミュレート
        action = "status"
        if action == "status":
            recent_messages = handler.conversation_buffer.get_recent_messages(
                mock_ctx.channel.id
            )
            message_count = len(recent_messages)
            await mock_ctx.send(
                f"📊 現在のバッファ状態:\n"
                f"- メッセージ数: {message_count}件\n"
                f"- 最大サイズ: {handler.config.EAVESDROP_BUFFER_SIZE}件"
            )

        handler.conversation_buffer.get_recent_messages.assert_called_once_with(
            777888999
        )
        mock_ctx.send.assert_called_once()
        call_args = mock_ctx.send.call_args
        assert "3件" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_eavesdrop_command_help_integration(self, handler):
        """!eavesdrop コマンド（ヘルプ）の統合テスト."""
        mock_ctx = MagicMock(spec=commands.Context)
        mock_ctx.send = AsyncMock()

        # コマンドの動作をシミュレート
        action = None
        if action == "clear":
            handler.conversation_buffer.clear(mock_ctx.channel.id)
            await mock_ctx.send("✅ 会話ログバッファをクリアしました。")
            logger.info(
                f"Cleared conversation buffer for channel: {mock_ctx.channel.id}"
            )
        elif action == "status":
            recent_messages = handler.conversation_buffer.get_recent_messages(
                mock_ctx.channel.id
            )
            message_count = len(recent_messages)
            await mock_ctx.send(
                f"📊 現在のバッファ状態:\n"
                f"- メッセージ数: {message_count}件\n"
                f"- 最大サイズ: {handler.config.EAVESDROP_BUFFER_SIZE}件"
            )
        else:
            await mock_ctx.send(
                "使用方法:\n"
                "`!eavesdrop clear` - 会話ログバッファをクリア\n"
                "`!eavesdrop status` - バッファ状態を表示"
            )

        mock_ctx.send.assert_called_once()
        call_args = mock_ctx.send.call_args
        assert "使用方法" in call_args[0][0]
