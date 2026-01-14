"""メインエントリーポイント"""
import logging
import signal
import sys

from .bot.client import KotonohaBot
from .bot.handlers import setup_handlers
from .config import Config

# ログ設定
logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ]
)

logger = logging.getLogger(__name__)


def main():
    """メイン関数"""
    logger.info("Starting Kotonoha Bot...")

    # Botインスタンスの作成
    bot = KotonohaBot()

    # イベントハンドラーのセットアップ
    handler = setup_handlers(bot)

    # シグナルハンドラー（Ctrl+C対応）
    def signal_handler(sig, frame):
        logger.info("Shutting down...")
        handler.session_manager.save_all_sessions()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Botの起動
    try:
        bot.run(Config.DISCORD_TOKEN)
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        handler.session_manager.save_all_sessions()
        sys.exit(1)


if __name__ == "__main__":
    main()
