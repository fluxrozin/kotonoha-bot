"""メインエントリーポイント"""

import asyncio
import logging
import signal
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

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
        try:
            log_path = Path(Config.LOG_FILE)
            log_path.parent.mkdir(parents=True, exist_ok=True)

            file_handler = RotatingFileHandler(
                log_path,
                maxBytes=Config.LOG_MAX_SIZE * 1024 * 1024,  # MB to bytes
                backupCount=Config.LOG_BACKUP_COUNT,
                encoding="utf-8",
            )
            file_handler.setFormatter(
                logging.Formatter(
                    "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
                )
            )
            handlers.append(file_handler)
        except (OSError, PermissionError) as e:
            # ログファイルの作成に失敗した場合は警告を出して続行
            logging.warning(
                f"Could not set up file logging to {Config.LOG_FILE}: {e}. "
                "Continuing with console logging only."
            )

    logging.basicConfig(
        level=getattr(logging, Config.LOG_LEVEL),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=handlers,
    )


# ログ設定
setup_logging()
logger = logging.getLogger(__name__)


async def async_main():
    """非同期メイン関数"""
    # 設定の検証
    Config.validate()

    logger.info("Starting Kotonoha Bot...")
    logger.info(f"Log level: {Config.LOG_LEVEL}")
    logger.info(f"LLM Model: {Config.LLM_MODEL}")

    # Botインスタンスの作成
    bot = KotonohaBot()

    # イベントハンドラーのセットアップ
    handler = setup_handlers(bot)

    # ヘルスチェックサーバーの準備（まだ起動しない）
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

    # シャットダウンフラグ
    shutdown_event = asyncio.Event()

    # シグナルハンドラー（Ctrl+C対応）
    def signal_handler(_sig, _frame):
        logger.info("Shutting down...")
        # イベントループにタスクをスケジュール
        try:
            loop = asyncio.get_running_loop()
            loop.call_soon_threadsafe(shutdown_event.set)
        except RuntimeError:
            # イベントループが実行されていない場合
            logger.warning("Event loop not running, forcing exit")
            sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Botの起動
    try:
        async with bot:
            await bot.start(Config.DISCORD_TOKEN)
            # Botの接続が確立されるまで待機
            await bot.wait_until_ready()
            # Botがreadyになったらヘルスチェックサーバーを起動
            health_server.start()
            # シャットダウンシグナルが来るまで待機
            await shutdown_event.wait()
            # シャットダウンイベントが来たら、graceful shutdownを実行
            logger.info("Shutdown signal received, starting graceful shutdown...")
            await shutdown_gracefully(bot, handler, health_server)
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        # エラー時もgraceful shutdownを試みる
        try:
            await shutdown_gracefully(bot, handler, health_server)
        except Exception as shutdown_error:
            logger.exception(f"Error during shutdown: {shutdown_error}")
        raise


async def shutdown_gracefully(
    bot: KotonohaBot, handler, health_server: HealthCheckServer
):
    """適切なシャットダウン処理"""
    logger.info("Starting graceful shutdown...")

    try:
        # ヘルスチェックサーバーを停止
        health_server.stop()

        # セッションを保存
        handler.session_manager.save_all_sessions()

        # Botを切断
        if not bot.is_closed():
            await bot.close()

        logger.info("Graceful shutdown completed")
    except Exception as e:
        logger.exception(f"Error during shutdown: {e}")
    finally:
        # ログハンドラーを閉じる
        for handler_instance in logging.root.handlers[:]:
            handler_instance.close()
            logging.root.removeHandler(handler_instance)


def main():
    """メイン関数"""
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
