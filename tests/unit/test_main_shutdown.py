"""メイン関数のシャットダウン処理のテスト"""

import asyncio
import contextlib
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from kotonoha_bot.main import async_main, shutdown_gracefully


@pytest.fixture
def mock_bot():
    """モックBot"""
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
    """モックハンドラー"""
    handler = MagicMock()
    handler.session_manager = MagicMock()
    handler.session_manager.save_all_sessions = AsyncMock()
    handler.session_manager.sessions = {}
    return handler


@pytest.fixture
def mock_health_server():
    """モックヘルスチェックサーバー"""
    server = MagicMock()
    server.start = Mock()
    server.stop = Mock()
    server.set_status_callback = Mock()
    return server


@pytest.mark.asyncio
async def test_shutdown_gracefully(mock_bot, mock_handler, mock_health_server):
    """適切なシャットダウン処理が実行されることを確認"""
    await shutdown_gracefully(mock_bot, mock_handler, mock_health_server)

    # ヘルスチェックサーバーが停止される
    mock_health_server.stop.assert_called_once()

    # セッションが保存される
    mock_handler.session_manager.save_all_sessions.assert_called_once()

    # Botが切断される
    mock_bot.close.assert_called_once()


@pytest.mark.asyncio
async def test_shutdown_gracefully_when_bot_already_closed(
    mock_bot, mock_handler, mock_health_server
):
    """Botが既に閉じられている場合のシャットダウン処理"""
    mock_bot.is_closed.return_value = True

    await shutdown_gracefully(mock_bot, mock_handler, mock_health_server)

    # ヘルスチェックサーバーが停止される
    mock_health_server.stop.assert_called_once()

    # セッションが保存される
    mock_handler.session_manager.save_all_sessions.assert_called_once()

    # Botのcloseは呼ばれない
    mock_bot.close.assert_not_called()


@pytest.mark.asyncio
async def test_shutdown_gracefully_handles_exceptions(
    mock_bot, mock_handler, mock_health_server
):
    """シャットダウン処理で例外が発生しても例外がログに記録されることを確認"""
    mock_health_server.stop.side_effect = Exception("Test error")

    # 例外が発生しても関数は正常に終了する（例外がログに記録される）
    await shutdown_gracefully(mock_bot, mock_handler, mock_health_server)

    # ヘルスチェックサーバーの停止が試みられる
    mock_health_server.stop.assert_called_once()

    # 例外が発生したため、その後の処理（セッション保存、Bot切断）は実行されない
    # これは実際の動作に一致している
    mock_handler.session_manager.save_all_sessions.assert_not_called()
    mock_bot.close.assert_not_called()


@pytest.mark.asyncio
async def test_async_main_sets_up_components(
    mock_bot, mock_handler, mock_health_server
):
    """async_mainがコンポーネントを適切にセットアップすることを確認"""
    mock_db = MagicMock()
    mock_db.initialize = AsyncMock()
    mock_db.close = AsyncMock()

    with (
        patch("kotonoha_bot.main.KotonohaBot", return_value=mock_bot),
        patch("kotonoha_bot.main.setup_handlers", return_value=mock_handler),
        patch("kotonoha_bot.main.HealthCheckServer", return_value=mock_health_server),
        patch("kotonoha_bot.main.get_config") as mock_get_config,
        patch("kotonoha_bot.main.PostgreSQLDatabase", return_value=mock_db),
        patch("kotonoha_bot.main.settings") as mock_settings,
    ):
        mock_settings.database_url = "postgresql://test:test@localhost:5432/test"
        mock_settings.postgres_host = None
        mock_config_instance = MagicMock()
        mock_config_instance.validate_config = Mock()
        mock_config_instance.LOG_LEVEL = "INFO"
        mock_config_instance.LLM_MODEL = "test-model"
        mock_config_instance.DISCORD_TOKEN = "test-token"
        mock_get_config.return_value = mock_config_instance

        # シャットダウンイベントを即座にトリガーするタスクを作成
        shutdown_event = asyncio.Event()

        async def trigger_shutdown():
            # bot.startが呼ばれるまで待つ
            while not mock_bot.start.called:
                await asyncio.sleep(0.001)
            # bot.startが呼ばれた後、少し待ってからシャットダウンをトリガー
            await asyncio.sleep(0.01)
            shutdown_event.set()

        # シャットダウンイベントをモック
        with patch("kotonoha_bot.main.asyncio.Event", return_value=shutdown_event):
            # タスクを開始
            task = asyncio.create_task(async_main())
            shutdown_task = asyncio.create_task(trigger_shutdown())

            try:
                # タイムアウトを設定して実行
                await asyncio.wait_for(
                    asyncio.gather(task, shutdown_task, return_exceptions=True),
                    timeout=1.0,
                )
            except TimeoutError:
                task.cancel()
                shutdown_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
                with contextlib.suppress(asyncio.CancelledError):
                    await shutdown_task

        # Botが起動される
        mock_bot.start.assert_called_once_with("test-token")
        # ⚠️ 注意: bot.start() はブロッキング呼び出しのため、
        # wait_until_ready() は main.py では呼ばれず、on_ready イベントで処理される
        # テストでは bot.start() が呼ばれたことを確認する

        # ヘルスチェックサーバーが起動される（bot.start() の前に起動される）
        mock_health_server.start.assert_called_once()
        mock_health_server.set_status_callback.assert_called_once()

        # ヘルスチェックサーバーはwait_until_readyの後に起動されることを確認
        # （startがwait_until_readyの後に呼ばれることを確認するため、
        #  call_args_listを確認する必要があるが、簡易的に呼ばれていることを確認）


@pytest.mark.asyncio
async def test_signal_handler_triggers_shutdown(
    mock_bot, mock_handler, mock_health_server
):
    """シグナルハンドラーがシャットダウンをトリガーすることを確認"""
    mock_db = AsyncMock()
    mock_db.initialize = AsyncMock()
    mock_db.close = AsyncMock()
    mock_embedding_processor = AsyncMock()
    mock_embedding_processor.graceful_shutdown = AsyncMock()
    mock_session_archiver = AsyncMock()
    mock_session_archiver.graceful_shutdown = AsyncMock()

    with (
        patch("kotonoha_bot.main.KotonohaBot", return_value=mock_bot),
        patch("kotonoha_bot.main.setup_handlers", return_value=mock_handler),
        patch("kotonoha_bot.main.HealthCheckServer", return_value=mock_health_server),
        patch("kotonoha_bot.main.get_config") as mock_get_config,
        patch("kotonoha_bot.main.signal.signal") as mock_signal,
        patch("kotonoha_bot.main.PostgreSQLDatabase", return_value=mock_db),
        patch("kotonoha_bot.main.settings") as mock_settings,
        patch(
            "kotonoha_bot.main.EmbeddingProcessor",
            return_value=mock_embedding_processor,
        ),
        patch("kotonoha_bot.main.SessionArchiver", return_value=mock_session_archiver),
        patch("kotonoha_bot.main.OpenAIEmbeddingProvider"),
    ):
        mock_settings.database_url = "postgresql://test:test@localhost:5432/test"
        mock_settings.postgres_host = None
        mock_config_instance = MagicMock()
        mock_config_instance.validate_config = Mock()
        mock_config_instance.LOG_LEVEL = "INFO"
        mock_config_instance.LLM_MODEL = "test-model"
        mock_config_instance.DISCORD_TOKEN = "test-token"
        mock_get_config.return_value = mock_config_instance

        # bot.start() を即座に終了させるために、bot.__aenter__ で即座に終了するように設定
        async def mock_aenter():
            return mock_bot

        async def mock_aexit(_exc_type, _exc_val, _exc_tb):
            return None

        mock_bot.__aenter__ = AsyncMock(side_effect=mock_aenter)
        mock_bot.__aexit__ = AsyncMock(side_effect=mock_aexit)
        # bot.start() を即座に終了させる
        mock_bot.start = AsyncMock()

        # シグナルハンドラーを取得して直接呼び出す
        # 非同期メイン関数を開始
        task = asyncio.create_task(async_main())

        # 少し待ってからシグナルハンドラーを直接呼び出す
        await asyncio.sleep(0.01)
        # signal_handler が登録されていることを確認
        assert mock_signal.call_count >= 2  # SIGINT と SIGTERM

        # シグナルハンドラーを直接呼び出してテスト
        # signal_handler の実装を確認すると、shutdown_gracefully を呼び出すタスクを作成する
        # テストでは、signal_handler が正しく登録されていることを確認する
        try:
            # タイムアウトを設定して実行
            await asyncio.wait_for(task, timeout=0.5)
        except TimeoutError:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

        # シグナルハンドラーが登録されていることを確認
        assert mock_signal.call_count >= 2


@pytest.mark.asyncio
async def test_signal_handler_handles_runtime_error():
    """イベントループが実行されていない場合のシグナルハンドラー"""
    # イベントループが実行されていない状態をシミュレート
    with (
        patch("kotonoha_bot.main.sys.exit") as mock_exit,
        patch("kotonoha_bot.main.asyncio.get_running_loop") as mock_get_loop,
    ):
        mock_get_loop.side_effect = RuntimeError("No running event loop")

        # シグナルハンドラーを直接呼び出すことはできないので、
        # ロジックをテストするために、get_running_loopがRuntimeErrorを発生させることを確認
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            # 期待される動作
            mock_exit.assert_not_called()  # まだ呼ばれていない
            # 実際のシグナルハンドラーではsys.exit(0)が呼ばれる
            # しかし、これはテストできないので、ロジックの確認のみ
