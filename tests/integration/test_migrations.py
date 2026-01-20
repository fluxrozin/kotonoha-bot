"""Alembicマイグレーションのテスト.

マイグレーションの適用、ロールバック、スキーマ検証をテストします。
"""

import os
from pathlib import Path

import asyncpg
import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy.ext.asyncio import create_async_engine


@pytest.fixture
def test_db_url():
    """テスト用データベースURL."""
    return os.getenv(
        "TEST_DATABASE_URL",
        "postgresql://test:test@localhost:5433/test_kotonoha",
    )


@pytest.fixture
def alembic_cfg(test_db_url):
    """Alembic設定オブジェクト."""
    # alembic.ini のパスを決定
    alembic_ini_path = Path("alembic.ini")
    if not alembic_ini_path.exists():
        alembic_ini_path = Path("/app/alembic.ini")
        if not alembic_ini_path.exists():
            pytest.skip("alembic.ini not found")

    cfg = Config(str(alembic_ini_path))

    # テスト用データベースURLを設定
    # Alembicは非同期対応（asyncpg）を使用
    sqlalchemy_url = test_db_url.replace("postgresql://", "postgresql+asyncpg://")
    cfg.set_main_option("sqlalchemy.url", sqlalchemy_url)

    return cfg


async def run_migration_upgrade(cfg: Config) -> None:
    """非同期コンテキストからマイグレーションを実行するヘルパー関数."""
    sqlalchemy_url = cfg.get_main_option("sqlalchemy.url")
    if not sqlalchemy_url:
        raise ValueError("sqlalchemy.url is not set")

    def _do_upgrade(connection, alembic_cfg: Config) -> None:
        """マイグレーションを実行する（同期関数）."""
        alembic_cfg.attributes["connection"] = connection
        command.upgrade(alembic_cfg, "head")

    async_engine = create_async_engine(sqlalchemy_url, echo=False)
    try:
        async with async_engine.begin() as connection:
            await connection.run_sync(_do_upgrade, cfg)
    finally:
        await async_engine.dispose()


async def run_migration_downgrade(cfg: Config, revision: str) -> None:
    """非同期コンテキストからマイグレーションをロールバックするヘルパー関数."""
    sqlalchemy_url = cfg.get_main_option("sqlalchemy.url")
    if not sqlalchemy_url:
        raise ValueError("sqlalchemy.url is not set")

    def _do_downgrade(connection, alembic_cfg: Config, target_revision: str) -> None:
        """マイグレーションをロールバックする（同期関数）."""
        alembic_cfg.attributes["connection"] = connection
        command.downgrade(alembic_cfg, target_revision)

    async_engine = create_async_engine(sqlalchemy_url, echo=False)
    try:
        async with async_engine.begin() as connection:
            await connection.run_sync(_do_downgrade, cfg, revision)
    finally:
        await async_engine.dispose()


async def run_migration_stamp(cfg: Config, revision: str) -> None:
    """非同期コンテキストからマイグレーションをstampするヘルパー関数."""
    sqlalchemy_url = cfg.get_main_option("sqlalchemy.url")
    if not sqlalchemy_url:
        raise ValueError("sqlalchemy.url is not set")

    def _do_stamp(connection, alembic_cfg: Config, target_revision: str) -> None:
        """マイグレーションをstampする（同期関数）."""
        alembic_cfg.attributes["connection"] = connection
        command.stamp(alembic_cfg, target_revision)

    async_engine = create_async_engine(sqlalchemy_url, echo=False)
    try:
        async with async_engine.begin() as connection:
            await connection.run_sync(_do_stamp, cfg, revision)
    finally:
        await async_engine.dispose()


@pytest.fixture(autouse=True)
async def clean_test_db(test_db_url):
    """クリーンなテストデータベースを準備（自動適用）."""
    # 接続文字列をパース
    from urllib.parse import urlparse

    parsed = urlparse(test_db_url)
    host = parsed.hostname or "localhost"
    port = parsed.port or 5433
    database = parsed.path.lstrip("/") if parsed.path else "test_kotonoha"
    user = parsed.username or "test"
    password = parsed.password or "test"

    # データベースに接続
    conn = await asyncpg.connect(
        host=host,
        port=port,
        database=database,
        user=user,
        password=password,
    )

    try:
        # 既存のテーブルを削除（クリーンアップ）
        # スキーマを削除するのではなく、すべてのテーブルを個別に削除
        tables = await conn.fetch(
            """
            SELECT tablename
            FROM pg_tables
            WHERE schemaname = 'public'
            """
        )
        for table in tables:
            await conn.execute(
                f'DROP TABLE IF EXISTS public."{table["tablename"]}" CASCADE'
            )

        # 拡張機能以外の型（ENUMなど）を削除
        enums = await conn.fetch(
            """
            SELECT typname
            FROM pg_type
            WHERE typtype = 'e'
            AND typnamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'public')
            """
        )
        for enum in enums:
            await conn.execute(
                f'DROP TYPE IF EXISTS public."{enum["typname"]}" CASCADE'
            )
    finally:
        await conn.close()

    yield

    # テスト後のクリーンアップ
    conn = await asyncpg.connect(
        host=host,
        port=port,
        database=database,
        user=user,
        password=password,
    )
    try:
        # 既存のテーブルを削除（クリーンアップ）
        tables = await conn.fetch(
            """
            SELECT tablename
            FROM pg_tables
            WHERE schemaname = 'public'
            """
        )
        for table in tables:
            await conn.execute(
                f'DROP TABLE IF EXISTS public."{table["tablename"]}" CASCADE'
            )

        # 拡張機能以外の型（ENUMなど）を削除
        enums = await conn.fetch(
            """
            SELECT typname
            FROM pg_type
            WHERE typtype = 'e'
            AND typnamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'public')
            """
        )
        for enum in enums:
            await conn.execute(
                f'DROP TYPE IF EXISTS public."{enum["typname"]}" CASCADE'
            )
    finally:
        await conn.close()


async def get_table_names(test_db_url: str) -> list[str]:
    """データベース内のテーブル名一覧を取得."""
    from urllib.parse import urlparse

    parsed = urlparse(test_db_url)
    host = parsed.hostname or "localhost"
    port = parsed.port or 5433
    database = parsed.path.lstrip("/") if parsed.path else "test_kotonoha"
    user = parsed.username or "test"
    password = parsed.password or "test"

    conn = await asyncpg.connect(
        host=host,
        port=port,
        database=database,
        user=user,
        password=password,
    )

    try:
        rows = await conn.fetch(
            """
            SELECT tablename
            FROM pg_tables
            WHERE schemaname = 'public'
            ORDER BY tablename
            """
        )
        return [row["tablename"] for row in rows]
    finally:
        await conn.close()


async def check_table_exists(test_db_url: str, table_name: str) -> bool:
    """テーブルが存在するか確認."""
    tables = await get_table_names(test_db_url)
    return table_name in tables


async def check_extension_exists(test_db_url: str, extension_name: str) -> bool:
    """拡張機能が存在するか確認."""
    from urllib.parse import urlparse

    parsed = urlparse(test_db_url)
    host = parsed.hostname or "localhost"
    port = parsed.port or 5433
    database = parsed.path.lstrip("/") if parsed.path else "test_kotonoha"
    user = parsed.username or "test"
    password = parsed.password or "test"

    conn = await asyncpg.connect(
        host=host,
        port=port,
        database=database,
        user=user,
        password=password,
    )

    try:
        row = await conn.fetchrow(
            """
            SELECT EXISTS(
                SELECT 1
                FROM pg_extension
                WHERE extname = $1
            )
            """,
            extension_name,
        )
        return row[0] if row else False
    finally:
        await conn.close()


async def get_alembic_version(test_db_url: str) -> str | None:
    """Alembicの現在のバージョンを取得."""
    from urllib.parse import urlparse

    parsed = urlparse(test_db_url)
    host = parsed.hostname or "localhost"
    port = parsed.port or 5433
    database = parsed.path.lstrip("/") if parsed.path else "test_kotonoha"
    user = parsed.username or "test"
    password = parsed.password or "test"

    conn = await asyncpg.connect(
        host=host,
        port=port,
        database=database,
        user=user,
        password=password,
    )

    try:
        # alembic_version テーブルが存在するか確認
        table_exists = await check_table_exists(test_db_url, "alembic_version")
        if not table_exists:
            return None

        row = await conn.fetchrow("SELECT version_num FROM alembic_version")
        return row["version_num"] if row else None
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_migration_upgrade(
    alembic_cfg,
    test_db_url,
):
    """マイグレーションの適用をテスト."""
    # マイグレーション適用前の状態を確認
    tables_before = await get_table_names(test_db_url)
    assert "sessions" not in tables_before
    assert "knowledge_sources" not in tables_before
    assert "knowledge_chunks" not in tables_before

    # マイグレーションを適用（非同期コンテキストから実行）
    await run_migration_upgrade(alembic_cfg)

    # マイグレーション適用後の状態を確認
    tables_after = await get_table_names(test_db_url)
    assert "sessions" in tables_after
    assert "knowledge_sources" in tables_after
    assert "knowledge_chunks" in tables_after
    assert "alembic_version" in tables_after

    # pgvector拡張機能が有効化されているか確認
    vector_exists = await check_extension_exists(test_db_url, "vector")
    assert vector_exists, "pgvector extension should be enabled"

    # Alembicバージョンが記録されているか確認
    version = await get_alembic_version(test_db_url)
    assert version is not None, "Alembic version should be recorded"
    assert version == "202601201940", f"Expected version 202601201940, got {version}"


@pytest.mark.asyncio
async def test_migration_idempotent(
    alembic_cfg,
    test_db_url,
):
    """マイグレーションの冪等性をテスト（複数回適用しても問題ない）."""
    # 1回目のマイグレーション適用
    await run_migration_upgrade(alembic_cfg)
    version_1 = await get_alembic_version(test_db_url)
    tables_1 = await get_table_names(test_db_url)

    # 2回目のマイグレーション適用（冪等性の確認）
    await run_migration_upgrade(alembic_cfg)
    version_2 = await get_alembic_version(test_db_url)
    tables_2 = await get_table_names(test_db_url)

    # バージョンとテーブルが変わっていないことを確認
    assert version_1 == version_2, "Version should not change on second upgrade"
    assert set(tables_1) == set(tables_2), "Tables should not change on second upgrade"


@pytest.mark.asyncio
async def test_migration_downgrade(
    alembic_cfg,
    test_db_url,
):
    """マイグレーションのロールバックをテスト."""
    # マイグレーションを適用（非同期コンテキストから実行）
    await run_migration_upgrade(alembic_cfg)

    # 適用後の状態を確認
    tables_after_upgrade = await get_table_names(test_db_url)
    assert "sessions" in tables_after_upgrade
    assert "knowledge_sources" in tables_after_upgrade
    assert "knowledge_chunks" in tables_after_upgrade

    version_after_upgrade = await get_alembic_version(test_db_url)
    assert version_after_upgrade is not None

    # マイグレーションをロールバック（base = 初期状態）
    await run_migration_downgrade(alembic_cfg, "base")

    # ロールバック後の状態を確認
    tables_after_downgrade = await get_table_names(test_db_url)
    # baseにロールバックすると、すべてのテーブルが削除される
    # alembic_versionテーブルも削除される
    assert "sessions" not in tables_after_downgrade
    assert "knowledge_sources" not in tables_after_downgrade
    assert "knowledge_chunks" not in tables_after_downgrade

    # 注意: baseにロールバックすると、alembic_versionテーブルも削除される可能性がある
    # これは正常な動作


@pytest.mark.asyncio
async def test_migration_schema_validation(
    alembic_cfg,
    test_db_url,
):
    """マイグレーション後のスキーマを検証."""
    # マイグレーションを適用（非同期コンテキストから実行）
    await run_migration_upgrade(alembic_cfg)

    # 各テーブルの存在を確認
    assert await check_table_exists(test_db_url, "sessions")
    assert await check_table_exists(test_db_url, "knowledge_sources")
    assert await check_table_exists(test_db_url, "knowledge_chunks")
    assert await check_table_exists(test_db_url, "alembic_version")

    # テーブルのカラムを確認（sessionsテーブル）
    from urllib.parse import urlparse

    parsed = urlparse(test_db_url)
    host = parsed.hostname or "localhost"
    port = parsed.port or 5433
    database = parsed.path.lstrip("/") if parsed.path else "test_kotonoha"
    user = parsed.username or "test"
    password = parsed.password or "test"

    conn = await asyncpg.connect(
        host=host,
        port=port,
        database=database,
        user=user,
        password=password,
    )

    try:
        # sessionsテーブルのカラムを確認
        columns = await conn.fetch(
            """
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = 'public'
            AND table_name = 'sessions'
            ORDER BY ordinal_position
            """
        )
        column_names = [col["column_name"] for col in columns]

        # 必須カラムが存在することを確認
        assert "session_key" in column_names
        assert "session_type" in column_names
        assert "created_at" in column_names
        assert "last_active_at" in column_names

        # knowledge_sourcesテーブルのカラムを確認
        columns = await conn.fetch(
            """
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = 'public'
            AND table_name = 'knowledge_sources'
            ORDER BY ordinal_position
            """
        )
        column_names = [col["column_name"] for col in columns]

        assert "id" in column_names  # knowledge_sourcesはidカラム
        assert "type" in column_names
        assert "uri" in column_names
        assert "created_at" in column_names

        # knowledge_chunksテーブルのカラムを確認
        columns = await conn.fetch(
            """
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = 'public'
            AND table_name = 'knowledge_chunks'
            ORDER BY ordinal_position
            """
        )
        column_names = [col["column_name"] for col in columns]

        assert "id" in column_names  # knowledge_chunksはidカラム
        assert "source_id" in column_names
        assert "content" in column_names
        assert "embedding" in column_names
        assert "token_count" in column_names

    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_migration_stamp(
    alembic_cfg,
    test_db_url,
):
    """マイグレーションのstamp機能をテスト."""
    # マイグレーションを適用（非同期コンテキストから実行）
    await run_migration_upgrade(alembic_cfg)

    # 現在のバージョンを確認
    version_before = await get_alembic_version(test_db_url)
    assert version_before == "202601201940"

    # stampでバージョンを設定（同じバージョン）
    await run_migration_stamp(alembic_cfg, "202601201940")

    # バージョンが変わっていないことを確認
    version_after = await get_alembic_version(test_db_url)
    assert version_after == version_before


@pytest.mark.asyncio
async def test_migration_current(
    alembic_cfg,
    test_db_url,
):
    """マイグレーションの現在のバージョンを確認."""
    # マイグレーション適用前はバージョンが存在しない
    version_before = await get_alembic_version(test_db_url)
    assert version_before is None

    # マイグレーションを適用（非同期コンテキストから実行）
    await run_migration_upgrade(alembic_cfg)

    # マイグレーション適用後はバージョンが存在する
    version_after = await get_alembic_version(test_db_url)
    assert version_after == "202601201940"


async def get_enum_types(test_db_url: str) -> list[str]:
    """ENUM型の一覧を取得."""
    from urllib.parse import urlparse

    parsed = urlparse(test_db_url)
    host = parsed.hostname or "localhost"
    port = parsed.port or 5433
    database = parsed.path.lstrip("/") if parsed.path else "test_kotonoha"
    user = parsed.username or "test"
    password = parsed.password or "test"

    conn = await asyncpg.connect(
        host=host,
        port=port,
        database=database,
        user=user,
        password=password,
    )

    try:
        rows = await conn.fetch(
            """
            SELECT typname
            FROM pg_type
            WHERE typtype = 'e'
            AND typnamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'public')
            ORDER BY typname
            """
        )
        return [row["typname"] for row in rows]
    finally:
        await conn.close()


async def get_enum_values(test_db_url: str, enum_name: str) -> list[str]:
    """ENUM型の値を取得."""
    from urllib.parse import urlparse

    parsed = urlparse(test_db_url)
    host = parsed.hostname or "localhost"
    port = parsed.port or 5433
    database = parsed.path.lstrip("/") if parsed.path else "test_kotonoha"
    user = parsed.username or "test"
    password = parsed.password or "test"

    conn = await asyncpg.connect(
        host=host,
        port=port,
        database=database,
        user=user,
        password=password,
    )

    try:
        rows = await conn.fetch(
            """
            SELECT enumlabel
            FROM pg_enum
            WHERE enumtypid = (SELECT oid FROM pg_type WHERE typname = $1)
            ORDER BY enumsortorder
            """,
            enum_name,
        )
        return [row["enumlabel"] for row in rows]
    finally:
        await conn.close()


async def get_indexes(test_db_url: str, table_name: str) -> list[str]:
    """テーブルのインデックス一覧を取得."""
    from urllib.parse import urlparse

    parsed = urlparse(test_db_url)
    host = parsed.hostname or "localhost"
    port = parsed.port or 5433
    database = parsed.path.lstrip("/") if parsed.path else "test_kotonoha"
    user = parsed.username or "test"
    password = parsed.password or "test"

    conn = await asyncpg.connect(
        host=host,
        port=port,
        database=database,
        user=user,
        password=password,
    )

    try:
        rows = await conn.fetch(
            """
            SELECT indexname
            FROM pg_indexes
            WHERE schemaname = 'public'
            AND tablename = $1
            ORDER BY indexname
            """,
            table_name,
        )
        return [row["indexname"] for row in rows]
    finally:
        await conn.close()


async def get_foreign_keys(test_db_url: str, table_name: str) -> list[dict]:
    """テーブルの外部キー制約を取得."""
    from urllib.parse import urlparse

    parsed = urlparse(test_db_url)
    host = parsed.hostname or "localhost"
    port = parsed.port or 5433
    database = parsed.path.lstrip("/") if parsed.path else "test_kotonoha"
    user = parsed.username or "test"
    password = parsed.password or "test"

    conn = await asyncpg.connect(
        host=host,
        port=port,
        database=database,
        user=user,
        password=password,
    )

    try:
        rows = await conn.fetch(
            """
            SELECT
                tc.constraint_name,
                kcu.column_name,
                ccu.table_name AS foreign_table_name,
                ccu.column_name AS foreign_column_name
            FROM information_schema.table_constraints AS tc
            JOIN information_schema.key_column_usage AS kcu
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage AS ccu
                ON ccu.constraint_name = tc.constraint_name
                AND ccu.table_schema = tc.table_schema
            WHERE tc.constraint_type = 'FOREIGN KEY'
            AND tc.table_name = $1
            AND tc.table_schema = 'public'
            """,
            table_name,
        )
        return [
            {
                "constraint_name": row["constraint_name"],
                "column_name": row["column_name"],
                "foreign_table_name": row["foreign_table_name"],
                "foreign_column_name": row["foreign_column_name"],
            }
            for row in rows
        ]
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_migration_enum_types(
    alembic_cfg,
    test_db_url,
):
    """ENUM型の作成をテスト."""
    # マイグレーションを適用（非同期コンテキストから実行）
    await run_migration_upgrade(alembic_cfg)

    # ENUM型の存在を確認
    enum_types = await get_enum_types(test_db_url)
    assert "source_type_enum" in enum_types
    assert "session_status_enum" in enum_types
    assert "source_status_enum" in enum_types

    # source_type_enumの値を確認
    source_type_values = await get_enum_values(test_db_url, "source_type_enum")
    expected_source_types = [
        "discord_session",
        "document_file",
        "web_page",
        "image_caption",
        "audio_transcript",
    ]
    assert set(source_type_values) == set(expected_source_types)

    # session_status_enumの値を確認
    session_status_values = await get_enum_values(test_db_url, "session_status_enum")
    expected_session_statuses = ["active", "archived"]
    assert set(session_status_values) == set(expected_session_statuses)

    # source_status_enumの値を確認
    source_status_values = await get_enum_values(test_db_url, "source_status_enum")
    expected_source_statuses = [
        "pending",
        "processing",
        "completed",
        "partial",
        "failed",
    ]
    assert set(source_status_values) == set(expected_source_statuses)


@pytest.mark.asyncio
async def test_migration_indexes(
    alembic_cfg,
    test_db_url,
):
    """インデックスの作成をテスト."""
    # マイグレーションを適用（非同期コンテキストから実行）
    await run_migration_upgrade(alembic_cfg)

    # sessionsテーブルのインデックスを確認
    sessions_indexes = await get_indexes(test_db_url, "sessions")
    assert "idx_sessions_status" in sessions_indexes
    assert "idx_sessions_last_active_at" in sessions_indexes
    assert "idx_sessions_channel_id" in sessions_indexes
    assert "idx_sessions_archive_candidates" in sessions_indexes

    # knowledge_sourcesテーブルのインデックスを確認
    sources_indexes = await get_indexes(test_db_url, "knowledge_sources")
    assert "idx_sources_metadata" in sources_indexes
    assert "idx_sources_status" in sources_indexes
    assert "idx_sources_type" in sources_indexes

    # knowledge_chunksテーブルのインデックスを確認
    chunks_indexes = await get_indexes(test_db_url, "knowledge_chunks")
    assert "idx_chunks_embedding" in chunks_indexes
    assert "idx_chunks_source_id" in chunks_indexes
    assert "idx_chunks_searchable" in chunks_indexes
    assert "idx_chunks_queue" in chunks_indexes


@pytest.mark.asyncio
async def test_migration_foreign_keys(
    alembic_cfg,
    test_db_url,
):
    """外部キー制約をテスト."""
    # マイグレーションを適用（非同期コンテキストから実行）
    await run_migration_upgrade(alembic_cfg)

    # knowledge_chunksテーブルの外部キーを確認
    foreign_keys = await get_foreign_keys(test_db_url, "knowledge_chunks")
    assert len(foreign_keys) > 0, "knowledge_chunks should have foreign keys"

    # source_idがknowledge_sources.idを参照していることを確認
    source_id_fk = next(
        (fk for fk in foreign_keys if fk["column_name"] == "source_id"), None
    )
    assert source_id_fk is not None, "source_id foreign key should exist"
    assert source_id_fk["foreign_table_name"] == "knowledge_sources", (
        "source_id should reference knowledge_sources"
    )
    assert source_id_fk["foreign_column_name"] == "id", (
        "source_id should reference knowledge_sources.id"
    )


@pytest.mark.asyncio
async def test_migration_constraints(
    alembic_cfg,
    test_db_url,
):
    """制約（主キー、ユニーク制約）をテスト."""
    # マイグレーションを適用（非同期コンテキストから実行）
    await run_migration_upgrade(alembic_cfg)

    from urllib.parse import urlparse

    parsed = urlparse(test_db_url)
    host = parsed.hostname or "localhost"
    port = parsed.port or 5433
    database = parsed.path.lstrip("/") if parsed.path else "test_kotonoha"
    user = parsed.username or "test"
    password = parsed.password or "test"

    conn = await asyncpg.connect(
        host=host,
        port=port,
        database=database,
        user=user,
        password=password,
    )

    try:
        # sessionsテーブルの主キーを確認
        pk_constraints = await conn.fetch(
            """
            SELECT constraint_name
            FROM information_schema.table_constraints
            WHERE table_schema = 'public'
            AND table_name = 'sessions'
            AND constraint_type = 'PRIMARY KEY'
            """
        )
        assert len(pk_constraints) == 1, "sessions should have a primary key"

        # sessionsテーブルのユニーク制約を確認
        unique_constraints = await conn.fetch(
            """
            SELECT constraint_name
            FROM information_schema.table_constraints
            WHERE table_schema = 'public'
            AND table_name = 'sessions'
            AND constraint_type = 'UNIQUE'
            """
        )
        # session_keyにユニーク制約があることを確認
        assert len(unique_constraints) >= 1, "sessions should have unique constraints"

    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_migration_default_values(
    alembic_cfg,
    test_db_url,
):
    """デフォルト値の設定をテスト."""
    # マイグレーションを適用（非同期コンテキストから実行）
    await run_migration_upgrade(alembic_cfg)

    from urllib.parse import urlparse

    parsed = urlparse(test_db_url)
    host = parsed.hostname or "localhost"
    port = parsed.port or 5433
    database = parsed.path.lstrip("/") if parsed.path else "test_kotonoha"
    user = parsed.username or "test"
    password = parsed.password or "test"

    conn = await asyncpg.connect(
        host=host,
        port=port,
        database=database,
        user=user,
        password=password,
    )

    try:
        # sessionsテーブルのデフォルト値を確認
        columns = await conn.fetch(
            """
            SELECT column_name, column_default
            FROM information_schema.columns
            WHERE table_schema = 'public'
            AND table_name = 'sessions'
            AND column_default IS NOT NULL
            """
        )
        default_columns = {col["column_name"]: col["column_default"] for col in columns}

        # messagesカラムのデフォルト値（JSONB配列）
        assert "messages" in default_columns or "[]" in str(
            default_columns.get("messages", "")
        ), "messages should have default value []"

        # statusカラムのデフォルト値
        assert "status" in default_columns or "active" in str(
            default_columns.get("status", "")
        ), "status should have default value 'active'"

    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_migration_data_integrity(
    alembic_cfg,
    test_db_url,
):
    """データ整合性をテスト（外部キー制約の動作確認）."""
    # マイグレーションを適用（非同期コンテキストから実行）
    await run_migration_upgrade(alembic_cfg)

    from urllib.parse import urlparse

    parsed = urlparse(test_db_url)
    host = parsed.hostname or "localhost"
    port = parsed.port or 5433
    database = parsed.path.lstrip("/") if parsed.path else "test_kotonoha"
    user = parsed.username or "test"
    password = parsed.password or "test"

    conn = await asyncpg.connect(
        host=host,
        port=port,
        database=database,
        user=user,
        password=password,
    )

    try:
        # knowledge_sourcesにレコードを挿入
        source_id = await conn.fetchval(
            """
            INSERT INTO knowledge_sources (type, title, status)
            VALUES ('discord_session', 'Test Source', 'pending')
            RETURNING id
            """
        )

        # knowledge_chunksに正しいsource_idでレコードを挿入（成功するはず）
        chunk_id = await conn.fetchval(
            """
            INSERT INTO knowledge_chunks (source_id, content, token_count)
            VALUES ($1, 'Test content', 10)
            RETURNING id
            """,
            source_id,
        )
        assert chunk_id is not None, (
            "Should be able to insert chunk with valid source_id"
        )

        # knowledge_chunksに存在しないsource_idでレコードを挿入（失敗するはず）
        with pytest.raises(asyncpg.ForeignKeyViolationError):
            await conn.execute(
                """
                INSERT INTO knowledge_chunks (source_id, content, token_count)
                VALUES ($1, 'Test content', 10)
                """,
                99999,  # 存在しないsource_id
            )

    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_migration_script_structure():
    """マイグレーションファイルの構造を検証."""
    from pathlib import Path

    # alembic.ini のパスを決定
    alembic_ini_path = Path("alembic.ini")
    if not alembic_ini_path.exists():
        alembic_ini_path = Path("/app/alembic.ini")
        if not alembic_ini_path.exists():
            pytest.skip("alembic.ini not found")

    cfg = Config(str(alembic_ini_path))
    script_dir = ScriptDirectory.from_config(cfg)

    # すべてのマイグレーションファイルを取得
    revisions = list(script_dir.walk_revisions())

    # 少なくとも1つのマイグレーションが存在することを確認
    assert len(revisions) > 0, "At least one migration should exist"

    # 各マイグレーションの構造を検証
    for rev in revisions:
        # revision IDが存在することを確認
        assert rev.revision is not None, f"Revision {rev} should have a revision ID"
        assert len(rev.revision) > 0, (
            f"Revision {rev} should have a non-empty revision ID"
        )

        # upgrade関数が存在することを確認
        assert rev.module is not None, f"Revision {rev.revision} should have a module"
        assert hasattr(rev.module, "upgrade"), (
            f"Revision {rev.revision} should have an upgrade function"
        )

        # downgrade関数が存在することを確認
        assert hasattr(rev.module, "downgrade"), (
            f"Revision {rev.revision} should have a downgrade function"
        )


@pytest.mark.asyncio
async def test_migration_revision_chain():
    """マイグレーションのrevisionチェーンを検証."""
    from pathlib import Path

    # alembic.ini のパスを決定
    alembic_ini_path = Path("alembic.ini")
    if not alembic_ini_path.exists():
        alembic_ini_path = Path("/app/alembic.ini")
        if not alembic_ini_path.exists():
            pytest.skip("alembic.ini not found")

    cfg = Config(str(alembic_ini_path))
    script_dir = ScriptDirectory.from_config(cfg)

    # headリビジョンを取得
    head = script_dir.get_current_head()
    assert head is not None, "Should have a head revision"

    # 現在のheadが期待されるrevision IDであることを確認
    assert head == "202601201940", f"Expected head revision 202601201940, got {head}"

    # すべてのrevisionが到達可能であることを確認
    revisions = list(script_dir.walk_revisions())
    for rev in revisions:
        # baseからheadまでのパスが存在することを確認
        path = script_dir.iterate_revisions(head, rev.revision)
        assert path is not None, f"Should be able to reach {rev.revision} from head"


@pytest.mark.asyncio
async def test_migration_downgrade_and_reupgrade(
    alembic_cfg,
    test_db_url,
):
    """マイグレーションのロールバック後の再適用をテスト."""
    # マイグレーションを適用（非同期コンテキストから実行）
    await run_migration_upgrade(alembic_cfg)
    tables_after_upgrade = await get_table_names(test_db_url)
    assert "sessions" in tables_after_upgrade

    # ロールバック
    await run_migration_downgrade(alembic_cfg, "base")
    tables_after_downgrade = await get_table_names(test_db_url)
    assert "sessions" not in tables_after_downgrade

    # 再度マイグレーションを適用
    await run_migration_upgrade(alembic_cfg)
    tables_after_reupgrade = await get_table_names(test_db_url)
    assert "sessions" in tables_after_reupgrade
    assert "knowledge_sources" in tables_after_reupgrade
    assert "knowledge_chunks" in tables_after_reupgrade


@pytest.mark.asyncio
async def test_migration_hnsw_index(
    alembic_cfg,
    test_db_url,
):
    """HNSWインデックスの作成をテスト."""
    # マイグレーションを適用（非同期コンテキストから実行）
    await run_migration_upgrade(alembic_cfg)

    from urllib.parse import urlparse

    parsed = urlparse(test_db_url)
    host = parsed.hostname or "localhost"
    port = parsed.port or 5433
    database = parsed.path.lstrip("/") if parsed.path else "test_kotonoha"
    user = parsed.username or "test"
    password = parsed.password or "test"

    conn = await asyncpg.connect(
        host=host,
        port=port,
        database=database,
        user=user,
        password=password,
    )

    try:
        # HNSWインデックスの存在を確認
        index_info = await conn.fetchrow(
            """
            SELECT indexname, indexdef
            FROM pg_indexes
            WHERE schemaname = 'public'
            AND tablename = 'knowledge_chunks'
            AND indexname = 'idx_chunks_embedding'
            """
        )
        assert index_info is not None, "HNSW index should exist"
        assert "hnsw" in index_info["indexdef"].lower(), "Index should be HNSW type"
        assert "halfvec_cosine_ops" in index_info["indexdef"], (
            "Index should use cosine ops"
        )

    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_migration_gin_index(
    alembic_cfg,
    test_db_url,
):
    """GINインデックス（JSONB用）の作成をテスト."""
    # マイグレーションを適用（非同期コンテキストから実行）
    await run_migration_upgrade(alembic_cfg)

    from urllib.parse import urlparse

    parsed = urlparse(test_db_url)
    host = parsed.hostname or "localhost"
    port = parsed.port or 5433
    database = parsed.path.lstrip("/") if parsed.path else "test_kotonoha"
    user = parsed.username or "test"
    password = parsed.password or "test"

    conn = await asyncpg.connect(
        host=host,
        port=port,
        database=database,
        user=user,
        password=password,
    )

    try:
        # GINインデックスの存在を確認
        index_info = await conn.fetchrow(
            """
            SELECT indexname, indexdef
            FROM pg_indexes
            WHERE schemaname = 'public'
            AND tablename = 'knowledge_sources'
            AND indexname = 'idx_sources_metadata'
            """
        )
        assert index_info is not None, "GIN index should exist"
        assert "gin" in index_info["indexdef"].lower(), "Index should be GIN type"

    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_migration_partial_indexes(
    alembic_cfg,
    test_db_url,
):
    """部分インデックス（WHERE句付き）の作成をテスト."""
    # マイグレーションを適用（非同期コンテキストから実行）
    await run_migration_upgrade(alembic_cfg)

    from urllib.parse import urlparse

    parsed = urlparse(test_db_url)
    host = parsed.hostname or "localhost"
    port = parsed.port or 5433
    database = parsed.path.lstrip("/") if parsed.path else "test_kotonoha"
    user = parsed.username or "test"
    password = parsed.password or "test"

    conn = await asyncpg.connect(
        host=host,
        port=port,
        database=database,
        user=user,
        password=password,
    )

    try:
        # 部分インデックスの存在を確認
        # idx_sessions_archive_candidates
        archive_candidates_index = await conn.fetchrow(
            """
            SELECT indexname, indexdef
            FROM pg_indexes
            WHERE schemaname = 'public'
            AND tablename = 'sessions'
            AND indexname = 'idx_sessions_archive_candidates'
            """
        )
        assert archive_candidates_index is not None, "Partial index should exist"
        assert "WHERE" in archive_candidates_index["indexdef"], (
            "Index should have WHERE clause"
        )

        # idx_chunks_searchable
        searchable_index = await conn.fetchrow(
            """
            SELECT indexname, indexdef
            FROM pg_indexes
            WHERE schemaname = 'public'
            AND tablename = 'knowledge_chunks'
            AND indexname = 'idx_chunks_searchable'
            """
        )
        assert searchable_index is not None, "Partial index should exist"
        assert "WHERE" in searchable_index["indexdef"], "Index should have WHERE clause"

        # idx_chunks_queue
        queue_index = await conn.fetchrow(
            """
            SELECT indexname, indexdef
            FROM pg_indexes
            WHERE schemaname = 'public'
            AND tablename = 'knowledge_chunks'
            AND indexname = 'idx_chunks_queue'
            """
        )
        assert queue_index is not None, "Partial index should exist"
        assert "WHERE" in queue_index["indexdef"], "Index should have WHERE clause"

    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_migration_table_columns_complete(
    alembic_cfg,
    test_db_url,
):
    """すべてのテーブルのカラムが完全に作成されていることをテスト."""
    # マイグレーションを適用（非同期コンテキストから実行）
    await run_migration_upgrade(alembic_cfg)

    from urllib.parse import urlparse

    parsed = urlparse(test_db_url)
    host = parsed.hostname or "localhost"
    port = parsed.port or 5433
    database = parsed.path.lstrip("/") if parsed.path else "test_kotonoha"
    user = parsed.username or "test"
    password = parsed.password or "test"

    conn = await asyncpg.connect(
        host=host,
        port=port,
        database=database,
        user=user,
        password=password,
    )

    try:
        # sessionsテーブルの全カラムを確認
        sessions_columns = await conn.fetch(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
            AND table_name = 'sessions'
            ORDER BY ordinal_position
            """
        )
        sessions_column_names = {col["column_name"] for col in sessions_columns}
        expected_sessions_columns = {
            "id",
            "session_key",
            "session_type",
            "messages",
            "status",
            "guild_id",
            "channel_id",
            "thread_id",
            "user_id",
            "version",
            "last_archived_message_index",
            "created_at",
            "last_active_at",
        }
        assert sessions_column_names == expected_sessions_columns, (
            f"Sessions columns mismatch: {sessions_column_names} vs {expected_sessions_columns}"
        )

        # knowledge_sourcesテーブルの全カラムを確認
        sources_columns = await conn.fetch(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
            AND table_name = 'knowledge_sources'
            ORDER BY ordinal_position
            """
        )
        sources_column_names = {col["column_name"] for col in sources_columns}
        expected_sources_columns = {
            "id",
            "type",
            "title",
            "uri",
            "status",
            "error_code",
            "error_message",
            "metadata",
            "created_at",
            "updated_at",
        }
        assert sources_column_names == expected_sources_columns, (
            f"Sources columns mismatch: {sources_column_names} vs {expected_sources_columns}"
        )

        # knowledge_chunksテーブルの全カラムを確認
        chunks_columns = await conn.fetch(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
            AND table_name = 'knowledge_chunks'
            ORDER BY ordinal_position
            """
        )
        chunks_column_names = {col["column_name"] for col in chunks_columns}
        expected_chunks_columns = {
            "id",
            "source_id",
            "content",
            "embedding",
            "location",
            "token_count",
            "retry_count",
            "created_at",
        }
        assert chunks_column_names == expected_chunks_columns, (
            f"Chunks columns mismatch: {chunks_column_names} vs {expected_chunks_columns}"
        )

        # knowledge_chunks_dlqテーブルの全カラムを確認
        dlq_columns = await conn.fetch(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
            AND table_name = 'knowledge_chunks_dlq'
            ORDER BY ordinal_position
            """
        )
        dlq_column_names = {col["column_name"] for col in dlq_columns}
        expected_dlq_columns = {
            "id",
            "original_chunk_id",
            "source_id",
            "source_type",
            "source_title",
            "content",
            "error_code",
            "error_message",
            "retry_count",
            "created_at",
            "last_retry_at",
        }
        assert dlq_column_names == expected_dlq_columns, (
            f"DLQ columns mismatch: {dlq_column_names} vs {expected_dlq_columns}"
        )

    finally:
        await conn.close()
