"""ヘルスチェックサーバー"""

import json
import logging
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread
from typing import Callable

from .config import Config

logger = logging.getLogger(__name__)


class HealthCheckHandler(BaseHTTPRequestHandler):
    """ヘルスチェック用HTTPハンドラー"""

    # クラス変数としてステータス取得関数を保持
    get_status: Callable[[], dict] | None = None

    def log_message(self, format: str, *args) -> None:
        """ログ出力をロガーにリダイレクト"""
        logger.debug(f"Health check: {format % args}")

    def do_GET(self) -> None:
        """GETリクエストの処理"""
        if self.path == "/health" or self.path == "/":
            self._handle_health()
        elif self.path == "/ready":
            self._handle_ready()
        else:
            self.send_error(404, "Not Found")

    def _handle_health(self) -> None:
        """ヘルスチェックエンドポイント"""
        try:
            get_status_func = HealthCheckHandler.get_status
            status = get_status_func() if get_status_func else {"status": "unknown"}
            is_healthy = status.get("status") == "healthy"

            self.send_response(200 if is_healthy else 503)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(status).encode() + b"\n")
        except Exception as e:
            logger.error(f"Health check error: {e}")
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(
                json.dumps({"status": "error", "error": str(e)}).encode() + b"\n"
            )

    def _handle_ready(self) -> None:
        """レディネスチェックエンドポイント"""
        try:
            get_status_func = HealthCheckHandler.get_status
            status = get_status_func() if get_status_func else {"status": "unknown"}
            is_ready = status.get("discord") == "connected"

            self.send_response(200 if is_ready else 503)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"ready": is_ready}).encode() + b"\n")
        except Exception as e:
            logger.error(f"Ready check error: {e}")
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(
                json.dumps({"ready": False, "error": str(e)}).encode() + b"\n"
            )


class HealthCheckServer:
    """ヘルスチェックサーバー"""

    def __init__(self, port: int = Config.HEALTH_CHECK_PORT):
        self.port = port
        self.server: HTTPServer | None = None
        self.thread: Thread | None = None
        self._get_status: Callable[[], dict] | None = None

    def set_status_callback(self, callback: Callable[[], dict]) -> None:
        """ステータス取得コールバックを設定"""
        self._get_status = callback
        HealthCheckHandler.get_status = callback

    def start(self) -> None:
        """サーバーを開始"""
        if not Config.HEALTH_CHECK_ENABLED:
            logger.info("Health check server is disabled")
            return

        try:
            self.server = HTTPServer(("0.0.0.0", self.port), HealthCheckHandler)
            self.thread = Thread(target=self.server.serve_forever, daemon=True)
            self.thread.start()
            logger.info(f"Health check server started on port {self.port}")
        except Exception as e:
            logger.error(f"Failed to start health check server: {e}")

    def stop(self) -> None:
        """サーバーを停止"""
        if self.server:
            self.server.shutdown()
            logger.info("Health check server stopped")
