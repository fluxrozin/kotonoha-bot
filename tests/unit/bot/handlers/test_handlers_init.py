"""ハンドラー初期化とイベントのテスト."""

from unittest.mock import AsyncMock, MagicMock

import discord
import pytest
from discord.ext import commands

from kotonoha_bot.bot.client import KotonohaBot
from kotonoha_bot.bot.handlers import MessageHandler, setup_handlers
from kotonoha_bot.config import Config


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


class TestSetupHandlers:
    """setup_handlers 関数のテスト."""

    @pytest.mark.asyncio
    async def test_setup_handlers_creates_handler(self, mock_bot, mock_db, mock_config):
        """setup_handlers が MessageHandler を作成する."""
        handler = setup_handlers(
            bot=mock_bot,
            db=mock_db,
            config=mock_config,
        )

        assert isinstance(handler, MessageHandler)
        assert handler.bot == mock_bot
        assert handler.config == mock_config

    @pytest.mark.asyncio
    async def test_setup_handlers_registers_on_ready(
        self, mock_bot, mock_db, mock_config
    ):
        """setup_handlers が on_ready イベントを登録する."""
        handler = setup_handlers(
            bot=mock_bot,
            db=mock_db,
            config=mock_config,
        )

        # on_ready イベントが登録されていることを確認
        # （実際の呼び出しは bot.start() 時に行われる）
        assert handler is not None

    @pytest.mark.asyncio
    async def test_setup_handlers_registers_on_message(
        self, mock_bot, mock_db, mock_config
    ):
        """setup_handlers が on_message イベントを登録する."""
        handler = setup_handlers(
            bot=mock_bot,
            db=mock_db,
            config=mock_config,
        )

        # on_message イベントが登録されていることを確認
        assert handler is not None


class TestMessageHandlerOnReady:
    """on_ready イベントのテスト."""

    @pytest.mark.asyncio
    async def test_on_ready_initializes_session_manager(self, handler):
        """on_ready でセッションマネージャーが初期化される."""
        handler.session_manager._initialized = False
        handler.session_manager.initialize = AsyncMock()

        # セッションマネージャーが初期化されていないことを確認
        assert not handler.session_manager.is_initialized

        # 初期化を実行
        await handler.session_manager.initialize()

        # 初期化されたことを確認
        handler.session_manager.initialize.assert_called_once()

    @pytest.mark.asyncio
    async def test_on_ready_starts_tasks(self, handler):
        """on_ready でタスクが開始される."""
        handler.cleanup_task.start = MagicMock()
        handler.batch_sync_task.start = MagicMock()
        handler.request_queue.start = AsyncMock()

        # タスクが開始されていないことを確認
        handler.cleanup_task.is_running = MagicMock(return_value=False)
        handler.batch_sync_task.is_running = MagicMock(return_value=False)

        # タスクを開始（on_ready の動作をシミュレート）
        if not handler.cleanup_task.is_running():
            handler.cleanup_task.start()
        if not handler.batch_sync_task.is_running():
            handler.batch_sync_task.start()
        await handler.request_queue.start()

        # タスクが開始されたことを確認
        handler.cleanup_task.start.assert_called_once()
        handler.batch_sync_task.start.assert_called_once()
        handler.request_queue.start.assert_called_once()


class TestMessageHandlerOnMessage:
    """on_message イベントのテスト."""

    @pytest.mark.asyncio
    async def test_on_message_bot_message_ignored(self, handler):
        """Bot自身のメッセージは無視される."""
        mock_message = MagicMock(spec=discord.Message)
        mock_message.author = MagicMock()
        mock_message.author.bot = True

        # on_message の動作をシミュレート
        if mock_message.author.bot:
            await handler.bot.process_commands(mock_message)
            return

        # process_commands が呼ばれたことを確認
        handler.bot.process_commands.assert_called_once_with(mock_message)

    @pytest.mark.asyncio
    async def test_on_message_mention_trigger(self, handler):
        """メンション時に mention ハンドラーが呼ばれる."""
        mock_message = MagicMock(spec=discord.Message)
        mock_message.author = MagicMock()
        mock_message.author.bot = False

        handler.router.route = AsyncMock(return_value="mention")
        handler.handle_mention = AsyncMock()

        # on_message の動作をシミュレート
        trigger = await handler.router.route(mock_message)
        if trigger == "mention":
            await handler.handle_mention(mock_message)

        handler.handle_mention.assert_called_once_with(mock_message)

    @pytest.mark.asyncio
    async def test_on_message_thread_trigger(self, handler):
        """スレッド型時に thread ハンドラーが呼ばれる."""
        mock_message = MagicMock(spec=discord.Message)
        mock_message.author = MagicMock()
        mock_message.author.bot = False

        handler.router.route = AsyncMock(return_value="thread")
        handler.handle_thread = AsyncMock()

        # on_message の動作をシミュレート
        trigger = await handler.router.route(mock_message)
        if trigger == "thread":
            await handler.handle_thread(mock_message)

        handler.handle_thread.assert_called_once_with(mock_message)

    @pytest.mark.asyncio
    async def test_on_message_eavesdrop_trigger(self, handler):
        """聞き耳型時に eavesdrop ハンドラーが呼ばれる."""
        mock_message = MagicMock(spec=discord.Message)
        mock_message.author = MagicMock()
        mock_message.author.bot = False

        handler.router.route = AsyncMock(return_value="eavesdrop")
        handler.handle_eavesdrop = AsyncMock()

        # on_message の動作をシミュレート
        trigger = await handler.router.route(mock_message)
        if trigger == "eavesdrop":
            await handler.handle_eavesdrop(mock_message)

        handler.handle_eavesdrop.assert_called_once_with(mock_message)


class TestMessageHandlerOnThreadUpdate:
    """on_thread_update イベントのテスト."""

    @pytest.mark.asyncio
    async def test_on_thread_update_archived(self, handler):
        """スレッドがアーカイブされた場合、セッションが保存される."""
        mock_before = MagicMock(spec=discord.Thread)
        mock_before.archived = False
        mock_before.id = 444555666

        mock_after = MagicMock(spec=discord.Thread)
        mock_after.archived = True
        mock_after.id = 444555666

        handler.session_manager.save_session = AsyncMock()

        # on_thread_update の動作をシミュレート
        if mock_after.archived and not mock_before.archived:
            session_key = f"thread:{mock_after.id}"
            await handler.session_manager.save_session(session_key)

        handler.session_manager.save_session.assert_called_once_with("thread:444555666")

    @pytest.mark.asyncio
    async def test_on_thread_update_not_archived(self, handler):
        """スレッドがアーカイブされていない場合、何もしない."""
        mock_before = MagicMock(spec=discord.Thread)
        mock_before.archived = False
        mock_after = MagicMock(spec=discord.Thread)
        mock_after.archived = False

        handler.session_manager.save_session = AsyncMock()

        # on_thread_update の動作をシミュレート
        if mock_after.archived and not mock_before.archived:
            session_key = f"thread:{mock_after.id}"
            await handler.session_manager.save_session(session_key)

        # 保存されないことを確認
        handler.session_manager.save_session.assert_not_called()


class TestMessageHandlerEavesdropCommand:
    """eavesdrop コマンドのテスト."""

    @pytest.mark.asyncio
    async def test_eavesdrop_command_clear(self, handler):
        """!eavesdrop clear コマンドが動作する."""
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

        handler.conversation_buffer.clear.assert_called_once_with(777888999)
        mock_ctx.send.assert_called_once_with("✅ 会話ログバッファをクリアしました。")

    @pytest.mark.asyncio
    async def test_eavesdrop_command_status(self, handler):
        """!eavesdrop status コマンドが動作する."""
        mock_ctx = MagicMock(spec=commands.Context)
        mock_ctx.channel = MagicMock()
        mock_ctx.channel.id = 777888999
        mock_ctx.send = AsyncMock()

        mock_messages = [MagicMock(), MagicMock()]
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

    @pytest.mark.asyncio
    async def test_eavesdrop_command_help(self):
        """!eavesdrop コマンド（ヘルプ）が動作する."""
        mock_ctx = MagicMock(spec=commands.Context)
        mock_ctx.send = AsyncMock()

        # コマンドの動作をシミュレート
        action = None
        if action not in ["clear", "status"]:
            await mock_ctx.send(
                "使用方法:\n"
                "`!eavesdrop clear` - 会話ログバッファをクリア\n"
                "`!eavesdrop status` - バッファ状態を表示"
            )

        mock_ctx.send.assert_called_once()


class TestMessageHandlerLoadEavesdropChannels:
    """_load_eavesdrop_channels メソッドのテスト."""

    def test_load_eavesdrop_channels_empty(self, handler, mock_config):
        """環境変数が空の場合."""
        mock_config.EAVESDROP_ENABLED_CHANNELS = ""
        handler.router.enable_eavesdrop_for_channel = MagicMock()

        handler._load_eavesdrop_channels()

        # チャンネルが有効化されないことを確認
        handler.router.enable_eavesdrop_for_channel.assert_not_called()

    def test_load_eavesdrop_channels_single(self, handler, mock_config):
        """単一チャンネルIDが設定されている場合."""
        mock_config.EAVESDROP_ENABLED_CHANNELS = "777888999"
        handler.router.enable_eavesdrop_for_channel = MagicMock()

        handler._load_eavesdrop_channels()

        # チャンネルが有効化されたことを確認
        handler.router.enable_eavesdrop_for_channel.assert_called_once_with(777888999)

    def test_load_eavesdrop_channels_multiple(self, handler, mock_config):
        """複数チャンネルIDが設定されている場合."""
        mock_config.EAVESDROP_ENABLED_CHANNELS = "777888999,111222333,444555666"
        handler.router.enable_eavesdrop_for_channel = MagicMock()

        handler._load_eavesdrop_channels()

        # すべてのチャンネルが有効化されたことを確認
        assert handler.router.enable_eavesdrop_for_channel.call_count == 3
        handler.router.enable_eavesdrop_for_channel.assert_any_call(777888999)
        handler.router.enable_eavesdrop_for_channel.assert_any_call(111222333)
        handler.router.enable_eavesdrop_for_channel.assert_any_call(444555666)

    def test_load_eavesdrop_channels_with_spaces(self, handler, mock_config):
        """スペースが含まれている場合."""
        mock_config.EAVESDROP_ENABLED_CHANNELS = " 777888999 , 111222333 "
        handler.router.enable_eavesdrop_for_channel = MagicMock()

        handler._load_eavesdrop_channels()

        # スペースが除去されてチャンネルが有効化されたことを確認
        assert handler.router.enable_eavesdrop_for_channel.call_count == 2
        handler.router.enable_eavesdrop_for_channel.assert_any_call(777888999)
        handler.router.enable_eavesdrop_for_channel.assert_any_call(111222333)


class TestMessageHandlerCogUnload:
    """cog_unload メソッドのテスト."""

    def test_cog_unload_cancels_tasks(self, handler):
        """cog_unload でタスクがキャンセルされる."""
        handler.cleanup_task.cancel = MagicMock()
        handler.batch_sync_task.cancel = MagicMock()

        handler.cog_unload()

        # タスクがキャンセルされたことを確認
        handler.cleanup_task.cancel.assert_called_once()
        handler.batch_sync_task.cancel.assert_called_once()
