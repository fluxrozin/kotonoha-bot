"""メインエントリーポイント"""

import asyncio
import functools
import logging
import signal
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Callable

import structlog

from .bot.client import KotonohaBot
from .bot.handlers import setup_handlers
from .commands.chat import setup as setup_chat_commands
from .config import Config, settings
from .db.postgres import PostgreSQLDatabase
from .external.embedding.openai_embedding import OpenAIEmbeddingProvider
from .features.knowledge_base.embedding_processor import EmbeddingProcessor
from .features.knowledge_base.session_archiver import SessionArchiver
from .health import HealthCheckServer


def local_timestamper(_, __, event_dict):
    """ローカルタイムゾーンでタイムスタンプを追加するプロセッサー
    
    フォーマット: YYYY-MM-DD HH:MM:SS.mmm (例: 2026-01-18 23:31:34.525)
    """
    # 現在時刻をローカルタイムゾーンで取得
    now = datetime.now().astimezone()
    # 読みやすい形式でフォーマット: YYYY-MM-DD HH:MM:SS.mmm
    event_dict["timestamp"] = now.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]  # ミリ秒まで表示
    return event_dict


def log_function_call(func: Callable) -> Callable:
    """関数の呼び出しをDEBUGログに記録するデコレータ（同期関数用）"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        logger = logging.getLogger(func.__module__)
        func_name = f"{func.__qualname__}"
        logger.debug(f"Calling {func_name}")
        try:
            result = func(*args, **kwargs)
            logger.debug(f"{func_name} completed successfully")
            return result
        except Exception as e:
            logger.debug(f"{func_name} failed: {e}", exc_info=True)
            raise
    return wrapper


def log_async_function_call(func: Callable) -> Callable:
    """非同期関数の呼び出しをDEBUGログに記録するデコレータ"""
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        logger = logging.getLogger(func.__module__)
        func_name = f"{func.__qualname__}"
        logger.debug(f"Calling {func_name}")
        try:
            result = await func(*args, **kwargs)
            logger.debug(f"{func_name} completed successfully")
            return result
        except Exception as e:
            logger.debug(f"{func_name} failed: {e}", exc_info=True)
            raise
    return wrapper


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

    # 標準のloggingフォーマット
    standard_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # コンソールハンドラーにProcessorFormatterを適用（structlog用）
    console_handler = handlers[0]
    structlog_formatter = structlog.stdlib.ProcessorFormatter(
        processor=structlog.dev.ConsoleRenderer(colors=False),
        foreign_pre_chain=[
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            local_timestamper,  # ローカルタイムゾーンを使用
        ],
    )
    console_handler.setFormatter(structlog_formatter)

    logging.basicConfig(
        level=getattr(logging, Config.LOG_LEVEL),
        format=standard_format,
        handlers=handlers,
    )

    # structlogの設定（標準のloggingと統合）
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            local_timestamper,  # ローカルタイムゾーンを使用
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


# ログ設定
setup_logging()
logger = logging.getLogger(__name__)


@log_async_function_call
async def async_main():
    """非同期メイン関数"""
    logger.debug("Starting async_main")
    # 設定の検証
    logger.debug("Validating configuration...")
    Config.validate()
    logger.debug("Configuration validated")

    logger.info("Starting Kotonoha Bot...")
    logger.info(f"Log level: {Config.LOG_LEVEL}")
    logger.info(f"LLM Model: {Config.LLM_MODEL}")

    # データベース初期化
    # ⚠️ 改善（セキュリティ）: DATABASE_URL にパスワードを含める形式への依存を改善
    # 本番環境では個別パラメータを使用し、パスワードを接続文字列に埋め込まない
    logger.debug("Starting database initialization")
    logger.info("Initializing database connection...")
    if settings.database_url:
        # 開発環境用: 接続文字列を使用（後方互換性）
        logger.debug("Using connection string for database")
        db = PostgreSQLDatabase(connection_string=settings.database_url)
    else:
        # 本番環境推奨: 個別パラメータを使用（パスワードを分離）
        logger.debug("Using individual parameters for database connection")
        db = PostgreSQLDatabase(
            host=settings.postgres_host,
            port=settings.postgres_port,
            database=settings.postgres_db,
            user=settings.postgres_user,
            password=settings.postgres_password,
        )
    logger.debug("PostgreSQLDatabase instance created")
    logger.info("Database connection created, initializing...")
    await db.initialize()
    logger.debug("Database initialization completed")
    logger.info("Database initialized successfully")

    # Embedding プロバイダー初期化
    logger.debug("Starting embedding provider initialization")
    logger.info("Initializing embedding provider...")
    try:
        embedding_provider = OpenAIEmbeddingProvider()
        logger.debug(f"OpenAIEmbeddingProvider created: {type(embedding_provider).__name__}")
        logger.info("Embedding provider initialized")
    except Exception as e:
        logger.exception(f"Failed to initialize embedding provider: {e}")
        raise

    # 知識ベース関連の初期化（環境変数から設定を読み込む）
    logger.debug("Starting embedding processor initialization")
    logger.info("Initializing embedding processor...")
    logger.debug(
        f"Embedding processor settings: "
        f"batch_size={settings.kb_embedding_batch_size}, "
        f"max_concurrent={settings.kb_embedding_max_concurrent}, "
        f"interval_minutes={settings.kb_embedding_interval_minutes}"
    )
    try:
        logger.debug("Creating EmbeddingProcessor instance...")
        embedding_processor = EmbeddingProcessor(
            db,
            embedding_provider,
            # batch_size と max_concurrent は環境変数から読み込まれる
        )
        logger.debug("EmbeddingProcessor instance created successfully")
        logger.debug(
            f"EmbeddingProcessor created: batch_size={embedding_processor.batch_size}, "
            f"max_concurrent={embedding_processor._semaphore._value}, "
            f"interval={embedding_processor._interval} minutes"
        )
        logger.info("Embedding processor initialized")
    except Exception as e:
        logger.exception(f"Failed to initialize embedding processor: {e}")
        raise
    
    logger.debug("Starting session archiver initialization")
    logger.info("Initializing session archiver...")
    logger.debug(
        f"Session archiver settings: "
        f"archive_threshold_hours={settings.kb_archive_threshold_hours}, "
        f"archive_interval_hours={settings.kb_archive_interval_hours}, "
        f"batch_size={settings.kb_archive_batch_size}"
    )
    session_archiver = SessionArchiver(
        db,
        embedding_provider,
        # archive_threshold_hours は環境変数から読み込まれる
    )
    logger.debug(
        f"SessionArchiver created: threshold={session_archiver.archive_threshold_hours} hours"
    )
    logger.info("Session archiver initialized")

    # Botインスタンスの作成
    logger.debug("Starting bot instance creation")
    logger.info("Creating bot instance...")
    bot = KotonohaBot()
    logger.debug("KotonohaBot instance created")
    logger.info("Bot instance created")

    # EmbeddingProcessorとSessionArchiverにBotインスタンスを設定
    # ⚠️ 重要: discord.pyの@tasks.loopはBotインスタンスに紐づいている必要があります
    logger.debug("Setting bot instance to background tasks")
    logger.info("Setting bot instance to embedding processor and session archiver...")
    embedding_processor.bot = bot
    session_archiver.bot = bot
    logger.debug("Bot instance set to embedding_processor and session_archiver")
    logger.info("Bot instance set to background tasks")

    # イベントハンドラーのセットアップ（依存性を注入）
    logger.debug("Starting event handlers setup")
    logger.info("Setting up event handlers...")
    handler = setup_handlers(
        bot,
        embedding_processor=embedding_processor,
        session_archiver=session_archiver,
        db=db,  # DBインスタンスを共有（Alembicマイグレーションの重複を防ぐ）
    )
    logger.debug("Event handlers setup completed")
    logger.info("Event handlers set up")

    # スラッシュコマンドを登録
    logger.debug("Starting slash commands registration")
    logger.info("Registering slash commands...")
    await setup_chat_commands(bot, handler)
    logger.debug("Slash commands registration completed")
    logger.info("Slash commands registered")

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

    # シグナルハンドラー（Ctrl+C対応）
    # ⚠️ 重要: bot.start() はブロッキング呼び出しなので、
    # シグナルハンドラーで bot.close() を呼び出すことで接続を切断し、
    # bot.start() を終了させる必要があります。
    def signal_handler(_sig, _frame):
        logger.info("Shutting down...")
        # イベントループにタスクをスケジュール
        try:
            loop = asyncio.get_running_loop()
            # bot.close() を非同期で呼び出す
            # これにより bot.start() がキャンセルされ、async with bot: ブロックが終了する
            loop.create_task(shutdown_gracefully(
                bot,
                handler,
                health_server,
                embedding_processor,
                session_archiver,
                db,
            ))
        except RuntimeError:
            # イベントループが実行されていない場合
            logger.warning("Event loop not running, forcing exit")
            sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # ヘルスチェックサーバーを先に起動（Botの状態に関わらずヘルスチェックに応答するため）
    logger.debug("Starting health check server")
    logger.info("Starting health check server...")
    health_server.start()
    logger.debug("Health check server started")
    logger.info("Health check server started")

    # Botの起動
    # ⚠️ 重要: bot.start() はブロッキング呼び出しです。
    # Discord に接続すると戻ってこないため、bot.start() 後のコードは実行されません。
    # バックグラウンドタスク（EmbeddingProcessor, SessionArchiver）の開始は
    # handlers.py の on_ready イベントハンドラで行います。
    logger.debug("Starting Discord bot")
    logger.info("Starting Discord bot...")
    try:
        logger.debug("Entering bot context")
        async with bot:
            logger.debug("Bot context entered")
            logger.info("Bot context entered, starting Discord connection...")
            logger.debug("Calling bot.start()")
            # bot.start() はブロッキング - 接続が切断されるまで戻らない
            await bot.start(Config.DISCORD_TOKEN)
            # ここには到達しない（正常終了時）
            logger.debug("bot.start() completed - this should not happen normally")
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        # エラー時もgraceful shutdownを試みる
        try:
            await shutdown_gracefully(
                bot,
                handler,
                health_server,
                embedding_processor,
                session_archiver,
                db,
            )
        except Exception as shutdown_error:
            logger.exception(f"Error during shutdown: {shutdown_error}")
        raise


async def shutdown_gracefully(
    bot: KotonohaBot,
    handler,
    health_server: HealthCheckServer,
    embedding_processor: EmbeddingProcessor | None = None,
    session_archiver: SessionArchiver | None = None,
    db: PostgreSQLDatabase | None = None,
):
    """適切なシャットダウン処理"""
    logger.info("Starting graceful shutdown...")

    try:
        # ヘルスチェックサーバーを停止
        health_server.stop()

        # セッションを保存
        await handler.session_manager.save_all_sessions()

        # Graceful Shutdown: 処理中のタスクが完了するまで待機
        # ⚠️ 重要: atexit は非同期では使えないため、signal ハンドリングまたは
        # Discord.py の bot.close() オーバーライドで対応します。
        if embedding_processor:
            await embedding_processor.graceful_shutdown()
        if session_archiver:
            await session_archiver.graceful_shutdown()

        # Botを切断
        if not bot.is_closed():
            await bot.close()

        # データベース接続をクローズ（確実に呼ぶことを忘れないでください）
        if db:
            await db.close()

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
