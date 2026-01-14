"""メインエントリーポイント"""
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import signal
import sys

from .bot.client import KotonohaBot
from .bot.handlers import setup_handlers
from .config import Config
from .health import HealthCheckServer


def setup_logging() -> None:
    """ログ設定のセットアップ"""
    handlers: list[logging.Handler] = [
        logging.StreamHandler(sys.stdout),
    ]

    # ファイルログが設定されている場合
    if Config.LOG_FILE:
        log_path = Path(Config.LOG_FILE)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = RotatingFileHandler(
            log_path,
            maxBytes=Config.LOG_MAX_SIZE * 1024 * 1024,  # MB to bytes
            backupCount=Config.LOG_BACKUP_COUNT,
            encoding="utf-8",
        )
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        )
        handlers.append(file_handler)

    logging.basicConfig(
        level=getattr(logging, Config.LOG_LEVEL),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=handlers,
    )


# ログ設定
setup_logging()
logger = logging.getLogger(__name__)


def main():
    """メイン関数"""
    logger.info("Starting Kotonoha Bot...")
    logger.info(f"Log level: {Config.LOG_LEVEL}")
    logger.info(f"LLM Model: {Config.LLM_MODEL}")

    # Botインスタンスの作成
    bot = KotonohaBot()

    # イベントハンドラーのセットアップ
    handler = setup_handlers(bot)

    # ヘルスチェックサーバーの起動
    health_server = HealthCheckServer()

    def get_health_status() -> dict:
        """ヘルスステータスを取得"""
        discord_connected = bot.is_ready() if bot else False
        return {
            "status": "healthy" if discord_connected else "starting",
            "discord": "connected" if discord_connected else "disconnected",
            "sessions": len(handler.session_manager.sessions) if handler else 0,
        }

    health_server.set_status_callback(get_health_status)
    health_server.start()

    # シグナルハンドラー（Ctrl+C対応）
    def signal_handler(sig, frame):
        logger.info("Shutting down...")
        health_server.stop()
        handler.session_manager.save_all_sessions()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Botの起動
    try:
        bot.run(Config.DISCORD_TOKEN)
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        health_server.stop()
        handler.session_manager.save_all_sessions()
        sys.exit(1)


if __name__ == "__main__":
    main()
