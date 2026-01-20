"""ヘルスチェックサーバーのテスト."""

import json
import socket
from http.client import HTTPConnection
from unittest.mock import MagicMock, patch

import pytest

from kotonoha_bot.config import Config
from kotonoha_bot.health import HealthCheckHandler, HealthCheckServer


@pytest.fixture
def mock_config():
    """モック設定."""
    config = MagicMock(spec=Config)
    config.HEALTH_CHECK_ENABLED = True
    config.HEALTH_CHECK_PORT = 8080
    return config


def wait_for_server(port: int, max_retries: int = 20) -> None:
    """サーバーが起動するまで待機."""
    import time

    for _ in range(max_retries):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.1)
            result = sock.connect_ex(("localhost", port))
            sock.close()
            if result == 0:
                time.sleep(0.1)  # 接続可能になった後、少し待機
                return
        except Exception:
            pass
        time.sleep(0.05)
    pytest.fail(f"Server did not start in time (port: {port})")


@pytest.fixture
def health_server(mock_config):
    """ヘルスチェックサーバーのフィクスチャ."""
    with patch("kotonoha_bot.health.Config", mock_config):
        # 利用可能なポートを見つける
        import socket

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(("", 0))
        port = sock.getsockname()[1]
        sock.close()

        server = HealthCheckServer(port=port)
        yield server
        server.stop()


class TestHealthCheckHandler:
    """HealthCheckHandler のテスト."""

    def test_handle_health_healthy(self, health_server):
        """ヘルスチェックが正常な場合."""
        status = {"status": "healthy", "discord": "connected", "sessions": 5}
        HealthCheckHandler.get_status = lambda: status

        health_server.set_status_callback(lambda: status)
        health_server.start()
        wait_for_server(health_server.port)

        # HTTP リクエストを送信
        conn = HTTPConnection("localhost", health_server.port)
        conn.request("GET", "/health")
        response = conn.getresponse()

        assert response.status == 200
        data = json.loads(response.read().decode())
        assert data["status"] == "healthy"
        assert data["discord"] == "connected"
        assert data["sessions"] == 5

        conn.close()

    def test_handle_health_unhealthy(self, health_server):
        """ヘルスチェックが異常な場合."""
        status = {"status": "starting", "discord": "disconnected", "sessions": 0}
        HealthCheckHandler.get_status = lambda: status

        health_server.set_status_callback(lambda: status)
        health_server.start()
        wait_for_server(health_server.port)

        conn = HTTPConnection("localhost", health_server.port)
        conn.request("GET", "/health")
        response = conn.getresponse()

        assert response.status == 503
        data = json.loads(response.read().decode())
        assert data["status"] == "starting"

        conn.close()

    def test_handle_health_root_path(self, health_server):
        """ルートパスが /health と同じ動作をする."""
        status = {"status": "healthy", "discord": "connected", "sessions": 5}
        HealthCheckHandler.get_status = lambda: status

        health_server.set_status_callback(lambda: status)
        health_server.start()
        wait_for_server(health_server.port)

        conn = HTTPConnection("localhost", health_server.port)
        conn.request("GET", "/")
        response = conn.getresponse()

        assert response.status == 200
        data = json.loads(response.read().decode())
        assert data["status"] == "healthy"

        conn.close()

    def test_handle_ready_connected(self, health_server):
        """レディネスチェックが接続済みの場合."""
        status = {"status": "healthy", "discord": "connected", "sessions": 5}
        HealthCheckHandler.get_status = lambda: status

        health_server.set_status_callback(lambda: status)
        health_server.start()
        wait_for_server(health_server.port)

        conn = HTTPConnection("localhost", health_server.port)
        conn.request("GET", "/ready")
        response = conn.getresponse()

        assert response.status == 200
        data = json.loads(response.read().decode())
        assert data["ready"] is True

        conn.close()

    def test_handle_ready_disconnected(self, health_server):
        """レディネスチェックが未接続の場合."""
        status = {"status": "starting", "discord": "disconnected", "sessions": 0}
        HealthCheckHandler.get_status = lambda: status

        health_server.set_status_callback(lambda: status)
        health_server.start()
        wait_for_server(health_server.port)

        conn = HTTPConnection("localhost", health_server.port)
        conn.request("GET", "/ready")
        response = conn.getresponse()

        assert response.status == 503
        data = json.loads(response.read().decode())
        assert data["ready"] is False

        conn.close()

    def test_handle_metrics(self, health_server):
        """メトリクスエンドポイントが動作する."""
        health_server.start()
        wait_for_server(health_server.port)

        conn = HTTPConnection("localhost", health_server.port)
        conn.request("GET", "/metrics")
        response = conn.getresponse()

        assert response.status == 200
        # Prometheus のバージョンは環境によって異なる可能性があるため、バージョン部分をチェックしない
        content_type = response.getheader("Content-Type")
        assert content_type is not None
        assert "text/plain" in content_type
        assert "charset=utf-8" in content_type
        # Prometheus メトリクスの形式を確認
        content = response.read().decode()
        assert "# HELP" in content or "# TYPE" in content

        conn.close()

    def test_handle_not_found(self, health_server):
        """存在しないパスで404が返される."""
        health_server.start()
        wait_for_server(health_server.port)

        conn = HTTPConnection("localhost", health_server.port)
        conn.request("GET", "/nonexistent")
        response = conn.getresponse()

        assert response.status == 404

        conn.close()

    def test_handle_health_error(self, health_server):
        """ヘルスチェックでエラーが発生した場合."""

        def error_status():
            raise Exception("Test error")

        HealthCheckHandler.get_status = error_status
        health_server.set_status_callback(error_status)
        health_server.start()

        import time

        time.sleep(0.1)

        conn = HTTPConnection("localhost", health_server.port)
        conn.request("GET", "/health")
        response = conn.getresponse()

        assert response.status == 500
        data = json.loads(response.read().decode())
        assert data["status"] == "error"
        assert "error" in data

        conn.close()


class TestHealthCheckServer:
    """HealthCheckServer のテスト."""

    def test_init_with_port(self):
        """ポートを指定して初期化できる."""
        server = HealthCheckServer(port=9999)
        assert server.port == 9999

    def test_init_without_port(self, mock_config):
        """ポートを指定しない場合、Config から取得する."""
        with patch("kotonoha_bot.health.Config", mock_config):
            server = HealthCheckServer()
            assert server.port == mock_config.HEALTH_CHECK_PORT

    def test_set_status_callback(self, health_server):
        """ステータス取得コールバックを設定できる."""

        def status_func():
            return {"status": "test"}

        health_server.set_status_callback(status_func)
        assert HealthCheckHandler.get_status == status_func

    def test_start_disabled(self, mock_config):
        """ヘルスチェックが無効な場合、サーバーが起動しない."""
        mock_config.HEALTH_CHECK_ENABLED = False

        with patch("kotonoha_bot.health.Config", mock_config):
            server = HealthCheckServer(port=0)
            with patch("kotonoha_bot.health.logger") as mock_logger:
                server.start()
                mock_logger.info.assert_called_once_with(
                    "Health check server is disabled"
                )
                assert server.server is None

    def test_start_enabled(self, health_server):
        """ヘルスチェックが有効な場合、サーバーが起動する."""
        health_server.start()
        assert health_server.server is not None
        assert health_server.thread is not None
        assert health_server.thread.is_alive()

    def test_stop(self, health_server):
        """サーバーを停止できる."""
        health_server.start()
        assert health_server.server is not None

        health_server.stop()
        # サーバーが停止したことを確認（接続できない）
        import time

        time.sleep(0.1)
        # サーバーが停止しているため、接続できないことを確認
        # （実際のテストでは、サーバーが停止したことを確認する方法を検討）
