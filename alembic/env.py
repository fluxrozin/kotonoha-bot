"""Alembicマイグレーション環境設定モジュール.

このモジュールは、Alembicによるデータベースマイグレーションの実行環境を設定する。
非同期SQLAlchemy（asyncpg）を使用したPostgreSQLマイグレーションをサポートする。

主な機能:
- 非同期エンジンの作成とマイグレーション実行
- 環境変数または設定ファイルからの接続文字列の取得
- アプリケーションからの呼び出しとコマンドライン実行の両方に対応
"""

import asyncio
import logging
import os

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# ⚠️ 重要: fileConfig()はアプリケーションのログ設定を上書きするため、
# アプリケーションから呼ばれる場合はスキップする。
# postgres.py から command.upgrade() を呼ぶ場合、すでにログ設定済みなので、
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
existing_url = config.get_main_option("sqlalchemy.url")
if existing_url and existing_url != "driver://user:pass@localhost/dbname":
    # postgres.py から設定された URL がある場合はそのまま使用
    # asyncpg形式であることを確認（必要に応じて変換）
    if "+asyncpg" not in existing_url:
        existing_url = existing_url.replace("postgresql://", "postgresql+asyncpg://")
        config.set_main_option("sqlalchemy.url", existing_url)
else:
    # 環境変数から接続文字列を取得
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        # asyncpg形式に変換
        sqlalchemy_url = database_url.replace("postgresql://", "postgresql+asyncpg://")
        config.set_main_option("sqlalchemy.url", sqlalchemy_url)
    else:
        # 個別パラメータから接続文字列を構築
        postgres_host = os.getenv("POSTGRES_HOST", "localhost")
        postgres_port = os.getenv("POSTGRES_PORT", "5432")
        postgres_db = os.getenv("POSTGRES_DB", "kotonoha")
        postgres_user = os.getenv("POSTGRES_USER", "kotonoha")
        postgres_password = os.getenv("POSTGRES_PASSWORD", "password")

        sqlalchemy_url = (
            f"postgresql+asyncpg://{postgres_user}:{postgres_password}@"
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


def do_run_migrations(connection: Connection) -> None:
    """マイグレーションを実行する（同期関数）.

    この関数は非同期接続の run_sync() から呼び出されます。
    """
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def _ensure_test_user_and_database() -> None:
    """テスト用ユーザーとデータベースを自動作成（マイグレーション実行時）.

    環境変数でテスト用の設定が有効な場合、マイグレーション実行前に
    テスト用ユーザーとデータベースを作成します。
    """
    import asyncpg

    # テスト用設定が有効かチェック
    test_admin_user = os.getenv("TEST_POSTGRES_ADMIN_USER")
    test_admin_password = os.getenv("TEST_POSTGRES_ADMIN_PASSWORD")
    if not test_admin_user or not test_admin_password:
        # テスト用設定が無効な場合はスキップ
        return

    # テスト用接続情報を取得
    test_host = os.getenv("TEST_POSTGRES_HOST", "localhost")
    test_port = int(os.getenv("TEST_POSTGRES_PORT", "5432"))
    test_database = os.getenv("TEST_POSTGRES_DB", "test_kotonoha")
    test_user = os.getenv("TEST_POSTGRES_USER", "test")
    test_password = os.getenv("TEST_POSTGRES_PASSWORD", "test")

    try:
        # 管理者権限で接続
        conn = await asyncpg.connect(
            host=test_host,
            port=test_port,
            database="postgres",
            user=test_admin_user,
            password=test_admin_password,
        )

        try:
            # テストユーザーが存在するか確認
            user_exists = await conn.fetchval(
                "SELECT 1 FROM pg_user WHERE usename = $1", test_user
            )

            if not user_exists:
                # テストユーザーを作成
                await conn.execute(
                    f"CREATE USER {test_user} WITH PASSWORD '{test_password}'"
                )

            # テストデータベースが存在するか確認
            db_exists = await conn.fetchval(
                "SELECT 1 FROM pg_database WHERE datname = $1", test_database
            )

            if not db_exists:
                # テストデータベースを作成（所有者をテストユーザーに設定）
                await conn.execute(
                    f"CREATE DATABASE {test_database} OWNER {test_user}"
                )
            else:
                # 既存のデータベースの所有者を確認・更新
                current_owner = await conn.fetchval(
                    "SELECT pg_catalog.pg_get_userbyid(datdba) FROM pg_database WHERE datname = $1",
                    test_database,
                )
                if current_owner != test_user:
                    # 所有者を変更
                    await conn.execute(
                        f"ALTER DATABASE {test_database} OWNER TO {test_user}"
                    )

            # テストユーザーにデータベースへの権限を付与
            await conn.execute(
                f"GRANT ALL PRIVILEGES ON DATABASE {test_database} TO {test_user}"
            )

        finally:
            await conn.close()

    except Exception:
        # ユーザー/DB作成に失敗しても続行（既に存在する可能性があるため）
        pass


async def run_async_migrations() -> None:
    """非同期マイグレーションを実行."""
    # テスト用ユーザーとデータベースを自動作成（設定されている場合）
    await _ensure_test_user_and_database()

    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    非同期エンジンを使用してマイグレーションを実行します。

    接続が提供されている場合（cfg.attributes["connection"]）はそれを使用し、
    ない場合は新規に非同期エンジンを作成して実行します。
    """
    # 接続が提供されている場合（アプリケーションから呼び出される場合）
    connection = config.attributes.get("connection", None)
    if connection is not None:
        # 提供された接続を使用（同期関数として実行）
        do_run_migrations(connection)
        return

    # 接続が提供されていない場合（コマンドライン実行時）
    # イベントループがない場合のみ asyncio.run() を使用
    try:
        asyncio.get_running_loop()
        # 既存のループがある場合はエラー
        raise RuntimeError(
            "Cannot run migrations from within an existing event loop. "
            "Provide a connection via config.attributes['connection'] instead."
        )
    except RuntimeError:
        # イベントループがない場合は新規作成（コマンドライン実行時）
        asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
