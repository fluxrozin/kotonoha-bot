import logging
import os

from alembic import context
from sqlalchemy import engine_from_config, pool

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# ⚠️ 重要: fileConfig()はアプリケーションのログ設定を上書きするため、
# アプリケーションから呼ばれる場合はスキップする。
# postgres.py から command.upgrade() が呼ばれる場合、すでにログ設定済みなので、
# Alembicのログ設定で上書きしない。
# コマンドラインから直接 alembic upgrade head を実行する場合のみログ設定を適用。
if config.config_file_name is not None:
    # ルートロガーにハンドラーがすでに設定されているかチェック
    # （アプリケーションから呼ばれた場合はハンドラーが存在する）
    root_logger = logging.getLogger()
    if not root_logger.handlers:
        # コマンドラインから直接実行された場合のみfileConfigを適用
        from logging.config import fileConfig

        fileConfig(config.config_file_name)

# 接続文字列の設定
# postgres.py から alembic.command.upgrade() を呼ぶ際に設定されている場合はそれを使用
# その場合、asyncpg形式をpsycopg2形式に変換する必要がある
existing_url = config.get_main_option("sqlalchemy.url")
if existing_url and existing_url != "driver://user:pass@localhost/dbname":
    # postgres.py から設定された URL がある場合
    # asyncpg形式をpsycopg2形式に変換（Alembicは同期接続を使用するため）
    if "+asyncpg" in existing_url:
        sqlalchemy_url = existing_url.replace("+asyncpg", "+psycopg2")
        config.set_main_option("sqlalchemy.url", sqlalchemy_url)
    # それ以外（すでにpsycopg2形式など）はそのまま使用
else:
    # 環境変数から接続文字列を取得
    # Alembicは同期接続を使用するため、psycopg2を使用
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        # asyncpgの接続文字列をpsycopg2形式に変換
        # postgresql://user:pass@host:port/db -> postgresql+psycopg2://...
        sqlalchemy_url = database_url.replace("postgresql://", "postgresql+psycopg2://")
        config.set_main_option("sqlalchemy.url", sqlalchemy_url)
    else:
        # 個別パラメータから接続文字列を構築
        postgres_host = os.getenv("POSTGRES_HOST", "localhost")
        postgres_port = os.getenv("POSTGRES_PORT", "5432")
        postgres_db = os.getenv("POSTGRES_DB", "kotonoha")
        postgres_user = os.getenv("POSTGRES_USER", "kotonoha")
        postgres_password = os.getenv("POSTGRES_PASSWORD", "password")

        sqlalchemy_url = (
            f"postgresql+psycopg2://{postgres_user}:{postgres_password}@"
            f"{postgres_host}:{postgres_port}/{postgres_db}"
        )
        config.set_main_option("sqlalchemy.url", sqlalchemy_url)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
target_metadata = None

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    try:
        with connectable.connect() as connection:
            context.configure(connection=connection, target_metadata=target_metadata)

            with context.begin_transaction():
                context.run_migrations()
    finally:
        # 確実にエンジンを破棄（接続プールがNullPoolでも明示的に閉じる）
        connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
