"""main.py のエッジケースと境界値テスト."""

import asyncio
from contextlib import suppress
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from kotonoha_bot.main import async_main, shutdown_gracefully


@pytest.fixture
def mock_bot():
    """モックBot."""
    bot = MagicMock()
    bot.is_ready.return_value = True
    bot.is_closed.return_value = False
    bot.close = AsyncMock()
    bot.start = AsyncMock()
    bot.wait_until_ready = AsyncMock()
    bot.add_cog = AsyncMock()
    bot.tree = MagicMock()
    bot.tree.sync = AsyncMock(return_value=[])
    bot.__aenter__ = AsyncMock(return_value=bot)
    bot.__aexit__ = AsyncMock(return_value=None)
    return bot


@pytest.fixture
def mock_handler():
    """モックハンドラー."""
    handler = MagicMock()
    handler.session_manager = MagicMock()
    handler.session_manager.save_all_sessions = AsyncMock()
    handler.session_manager.sessions = {}
    return handler


@pytest.fixture
def mock_health_server():
    """モックヘルスチェックサーバー."""
    server = MagicMock()
    server.start = Mock()
    server.stop = Mock()
    server.set_status_callback = Mock()
    return server


@pytest.fixture
def mock_db():
    """モックデータベース."""
    db = MagicMock()
    db.initialize = AsyncMock()
    db.close = AsyncMock()
    return db


class TestShutdownGracefullyEdgeCases:
    """shutdown_gracefully のエッジケーステスト."""

    @pytest.mark.asyncio
    async def test_shutdown_with_none_embedding_processor(
        self, mock_bot, mock_handler, mock_health_server, mock_db
    ):
        """embedding_processor が None の場合."""
        await shutdown_gracefully(
            mock_bot,
            mock_handler,
            mock_health_server,
            embedding_processor=None,
            session_archiver=None,
            db=mock_db,
        )

        # ヘルスチェックサーバーが停止される
        mock_health_server.stop.assert_called_once()
        # セッションが保存される
        mock_handler.session_manager.save_all_sessions.assert_called_once()
        # Botが切断される
        mock_bot.close.assert_called_once()
        # データベースが閉じられる
        mock_db.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_shutdown_with_embedding_processor_error(
        self, mock_bot, mock_handler, mock_health_server, mock_db
    ):
        """embedding_processor の graceful_shutdown でエラーが発生した場合."""
        mock_embedding_processor = MagicMock()
        mock_embedding_processor.graceful_shutdown = AsyncMock(
            side_effect=Exception("Shutdown error")
        )

        # エラーが発生しても処理が続行されることを確認
        await shutdown_gracefully(
            mock_bot,
            mock_handler,
            mock_health_server,
            embedding_processor=mock_embedding_processor,
            session_archiver=None,
            db=mock_db,
        )

        # graceful_shutdown が呼ばれたことを確認
        mock_embedding_processor.graceful_shutdown.assert_called_once()
        # データベースが閉じられることを確認（finallyブロックで実行される）
        mock_db.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_shutdown_with_session_archiver_error(
        self, mock_bot, mock_handler, mock_health_server, mock_db
    ):
        """session_archiver の graceful_shutdown でエラーが発生した場合."""
        mock_session_archiver = MagicMock()
        mock_session_archiver.graceful_shutdown = AsyncMock(
            side_effect=Exception("Shutdown error")
        )

        # エラーが発生しても処理が続行されることを確認
        await shutdown_gracefully(
            mock_bot,
            mock_handler,
            mock_health_server,
            embedding_processor=None,
            session_archiver=mock_session_archiver,
            db=mock_db,
        )

        # graceful_shutdown が呼ばれたことを確認
        mock_session_archiver.graceful_shutdown.assert_called_once()
        # データベースが閉じられることを確認（finallyブロックで実行される）
        mock_db.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_shutdown_with_db_close_error(
        self, mock_bot, mock_handler, mock_health_server
    ):
        """データベースの close でエラーが発生した場合、例外が呼び出し元に伝播する."""
        mock_db = MagicMock()
        mock_db.close = AsyncMock(side_effect=Exception("Close error"))

        # close が失敗した場合は例外を握りつぶさず伝播する
        with pytest.raises(Exception, match="Close error"):
            await shutdown_gracefully(
                mock_bot,
                mock_handler,
                mock_health_server,
                embedding_processor=None,
                session_archiver=None,
                db=mock_db,
            )

        # finally 内で close が呼ばれたことを確認
        mock_db.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_shutdown_with_save_all_sessions_error(
        self, mock_bot, mock_handler, mock_health_server, mock_db
    ):
        """save_all_sessions でエラーが発生した場合."""
        mock_handler.session_manager.save_all_sessions = AsyncMock(
            side_effect=Exception("Save error")
        )

        # エラーが発生しても処理が続行されることを確認
        await shutdown_gracefully(
            mock_bot,
            mock_handler,
            mock_health_server,
            embedding_processor=None,
            session_archiver=None,
            db=mock_db,
        )

        # save_all_sessions が呼ばれたことを確認
        mock_handler.session_manager.save_all_sessions.assert_called_once()
        # データベースが閉じられることを確認（finallyブロックで実行される）
        mock_db.close.assert_called_once()


class TestAsyncMainEdgeCases:
    """async_main のエッジケーステスト."""

    @pytest.mark.asyncio
    async def test_async_main_config_validation_error(self):
        """設定検証でエラーが発生した場合."""
        with (
            patch("kotonoha_bot.main.get_config") as mock_get_config,
        ):
            mock_config = MagicMock()
            mock_config.validate_config = Mock(side_effect=ValueError("Invalid config"))
            mock_get_config.return_value = mock_config

            # エラーが発生することを確認
            with pytest.raises(ValueError, match="Invalid config"):
                await async_main()

    @pytest.mark.asyncio
    async def test_async_main_database_initialization_error(self):
        """データベース初期化でエラーが発生した場合."""
        with (
            patch("kotonoha_bot.main.get_config") as mock_get_config,
            patch("kotonoha_bot.main.PostgreSQLDatabase") as mock_db_class,
            patch("kotonoha_bot.main.settings") as mock_settings,
        ):
            mock_config = MagicMock()
            mock_config.validate_config = Mock()
            mock_config.LOG_LEVEL = "INFO"
            mock_config.LLM_MODEL = "test-model"
            mock_get_config.return_value = mock_config

            mock_settings.database_url = "postgresql://test:test@localhost:5432/test"
            mock_settings.postgres_host = None

            mock_db = MagicMock()
            mock_db.initialize = AsyncMock(side_effect=Exception("DB init error"))
            mock_db_class.return_value = mock_db

            # エラーが発生することを確認
            with pytest.raises(Exception, match="DB init error"):
                await async_main()

    @pytest.mark.asyncio
    async def test_async_main_embedding_provider_error(self):
        """Embedding プロバイダー初期化でエラーが発生した場合."""
        with (
            patch("kotonoha_bot.main.get_config") as mock_get_config,
            patch("kotonoha_bot.main.PostgreSQLDatabase") as mock_db_class,
            patch("kotonoha_bot.main.settings") as mock_settings,
            patch("kotonoha_bot.main.OpenAIEmbeddingProvider") as mock_embedding_class,
        ):
            mock_config = MagicMock()
            mock_config.validate_config = Mock()
            mock_config.LOG_LEVEL = "INFO"
            mock_config.LLM_MODEL = "test-model"
            mock_get_config.return_value = mock_config

            mock_settings.database_url = "postgresql://test:test@localhost:5432/test"
            mock_settings.postgres_host = None

            mock_db = MagicMock()
            mock_db.initialize = AsyncMock()
            mock_db_class.return_value = mock_db

            mock_embedding_class.side_effect = Exception("Embedding init error")

            # エラーが発生することを確認
            with pytest.raises(Exception, match="Embedding init error"):
                await async_main()

    @pytest.mark.asyncio
    async def test_async_main_individual_db_parameters(self):
        """個別のデータベースパラメータを使用する場合."""
        with (
            patch("kotonoha_bot.main.get_config") as mock_get_config,
            patch("kotonoha_bot.main.PostgreSQLDatabase") as mock_db_class,
            patch("kotonoha_bot.main.settings") as mock_settings,
            patch("kotonoha_bot.main.OpenAIEmbeddingProvider"),
            patch("kotonoha_bot.main.KotonohaBot") as mock_bot_class,
            patch("kotonoha_bot.main.setup_handlers") as mock_setup_handlers,
            patch("kotonoha_bot.main.setup_chat_commands") as _mock_setup_commands,
            patch("kotonoha_bot.main.HealthCheckServer") as mock_health_class,
            patch("kotonoha_bot.main.EmbeddingProcessor"),
            patch("kotonoha_bot.main.SessionArchiver"),
            patch(
                "kotonoha_bot.services.session.SessionManager"
            ) as mock_session_manager_class,
        ):
            mock_config = MagicMock()
            mock_config.validate_config = Mock()
            mock_config.LOG_LEVEL = "INFO"
            mock_config.LLM_MODEL = "test-model"
            mock_config.DISCORD_TOKEN = "test-token"
            mock_get_config.return_value = mock_config

            # database_url が None で、個別パラメータが設定されている場合
            mock_settings.database_url = None
            mock_settings.postgres_host = "localhost"
            mock_settings.postgres_port = 5432
            mock_settings.postgres_db = "testdb"
            mock_settings.postgres_user = "testuser"
            mock_settings.postgres_password = "testpass"

            mock_db = MagicMock()
            mock_db.initialize = AsyncMock()
            mock_db_class.return_value = mock_db

            mock_bot = MagicMock()
            mock_bot.__aenter__ = AsyncMock(return_value=mock_bot)
            mock_bot.__aexit__ = AsyncMock(return_value=None)
            mock_bot.start = AsyncMock()
            mock_bot_class.return_value = mock_bot

            mock_handler = MagicMock()
            mock_setup_handlers.return_value = mock_handler

            mock_health = MagicMock()
            mock_health.start = Mock()
            mock_health.set_status_callback = Mock()
            mock_health_class.return_value = mock_health

            mock_session_manager = MagicMock()
            mock_session_manager.initialize = AsyncMock()
            mock_session_manager_class.return_value = mock_session_manager

            # タイムアウトを設定して実行
            # タイムアウトは期待される動作（bot.start() はブロッキング）
            with suppress(TimeoutError, asyncio.CancelledError):
                await asyncio.wait_for(async_main(), timeout=0.1)

            # 個別パラメータでデータベースが作成されたことを確認
            mock_db_class.assert_called_once_with(
                host="localhost",
                port=5432,
                database="testdb",
                user="testuser",
                password="testpass",
            )


class TestSetupLoggingEdgeCases:
    """setup_logging のエッジケーステスト."""

    def test_setup_logging_with_file_logging_error(self):
        """ログファイル設定でエラーが発生した場合、警告を出して続行する."""
        from unittest.mock import MagicMock, patch

        from kotonoha_bot.main import setup_logging

        with (
            patch("kotonoha_bot.main.get_config") as mock_get_config,
            patch("pathlib.Path.mkdir") as mock_mkdir,
            patch("logging.handlers.RotatingFileHandler") as _mock_file_handler,
            patch("logging.warning") as mock_warning,
        ):
            mock_config = MagicMock()
            mock_config.LOG_FILE = "/invalid/path/log.txt"
            mock_config.LOG_MAX_SIZE = 10
            mock_config.LOG_BACKUP_COUNT = 5
            mock_config.LOG_LEVEL = "INFO"
            mock_get_config.return_value = mock_config

            # mkdir で PermissionError を発生させる
            mock_mkdir.side_effect = PermissionError("Permission denied")

            # setup_logging を実行
            setup_logging()

            # 警告が出力されたことを確認
            mock_warning.assert_called_once()
            assert "Could not set up file logging" in str(mock_warning.call_args)

    def test_setup_logging_with_os_error(self):
        """ログファイル設定でOSErrorが発生した場合、警告を出して続行する."""
        from unittest.mock import MagicMock, patch

        from kotonoha_bot.main import setup_logging

        with (
            patch("kotonoha_bot.main.get_config") as mock_get_config,
            patch("pathlib.Path.mkdir") as mock_mkdir,
            patch("logging.warning") as mock_warning,
        ):
            mock_config = MagicMock()
            mock_config.LOG_FILE = "/invalid/path/log.txt"
            mock_config.LOG_MAX_SIZE = 10
            mock_config.LOG_BACKUP_COUNT = 5
            mock_config.LOG_LEVEL = "INFO"
            mock_get_config.return_value = mock_config

            # mkdir で OSError を発生させる
            mock_mkdir.side_effect = OSError("No space left on device")

            # setup_logging を実行
            setup_logging()

            # 警告が出力されたことを確認
            mock_warning.assert_called_once()
            assert "Could not set up file logging" in str(mock_warning.call_args)
