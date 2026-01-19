"""pytest フィクスチャ"""

import logging
import os
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio

# テスト環境ではログファイルを無効化（main.pyのインポート前に設定）
if "LOG_FILE" not in os.environ:
    os.environ["LOG_FILE"] = ""

from kotonoha_bot.db.postgres import PostgreSQLDatabase
from kotonoha_bot.external.embedding import EmbeddingProvider


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """テスト環境のセットアップ（テストセッション開始時に実行）"""
    # 既存のログハンドラーをクリーンアップ
    for handler in logging.root.handlers[:]:
        if hasattr(handler, "close"):
            handler.close()
        logging.root.removeHandler(handler)

    yield

    # テスト終了後にログハンドラーをクリーンアップ
    for handler in logging.root.handlers[:]:
        if hasattr(handler, "close"):
            handler.close()
        logging.root.removeHandler(handler)


# ============================================
# ⚠️ 非推奨: SQLiteフィクスチャ
# ============================================
# プロジェクトはPostgreSQLに移行したため、SQLiteフィクスチャは非推奨です。
# 新しいテストは postgres_db フィクスチャを使用してください。
#
# 既存のSQLiteフィクスチャは後方互換性のため残していますが、
# 将来的に削除される可能性があります。
# ============================================


@pytest.fixture(autouse=True)
def cleanup_log_handlers():
    """テスト後にログハンドラーをクリーンアップ"""
    yield
    # テスト後にすべてのログハンドラーを閉じる
    for handler in logging.root.handlers[:]:
        if hasattr(handler, "close"):
            handler.close()
        logging.root.removeHandler(handler)


# ============================================
# PostgreSQL用テストフィクスチャ（Step 7）
# ============================================


async def _cleanup_test_data(db: PostgreSQLDatabase):
    """テストデータのクリーンアップ

    ⚠️ 注意: TRUNCATE ... CASCADE を使用していますが、並列テスト実行時に相互干渉する可能性があります。
    将来的に pytest-xdist 等で並列テストを行う場合、単一のDBをTRUNCATEし合うとテストが落ちます。

    ⚠️ 改善（テスト時のデータベースクリーンアップ）: 各テストケースをトランザクション内で実行し、
    最後にロールバックする方式（pytest-asyncio のフィクスチャでロールバックパターン）を採用すると、
    より高速で安全です。
    """
    assert db.pool is not None, "Database pool must be initialized"
    async with db.pool.acquire() as conn, conn.transaction():
        # 外部キー制約があるため、順序に注意
        await conn.execute("TRUNCATE knowledge_chunks CASCADE")
        await conn.execute("TRUNCATE knowledge_sources CASCADE")
        await conn.execute("TRUNCATE sessions CASCADE")


@pytest_asyncio.fixture
async def postgres_db():
    """PostgreSQL データベースのフィクスチャ

    ⚠️ 改善: pytest-asyncioを使用した非同期フィクスチャ
    pytest-asyncioを使用することで、非同期関数をフィクスチャとして使用できます

    ⚠️ 改善（テスト時のデータベースクリーンアップ）: 並列テスト実行時の相互干渉を防ぐため、
    ロールバックパターンを使用することを推奨します。

    使用方法:
    ```python
    async def test_example(postgres_db):
        # テストコード
        await postgres_db.save_session(session)
    ```
    """
    # テストDB接続文字列を環境変数から読み込み
    test_db_url = os.getenv(
        "TEST_DATABASE_URL",
        "postgresql://test:test@localhost:5432/test_kotonoha",
    )

    # PostgreSQLDatabaseの初期化
    # テストで個別パラメータが必要な場合に備えて、接続文字列からパースする
    if test_db_url.startswith("postgresql://"):
        # 接続文字列をパースして個別パラメータを抽出
        from urllib.parse import urlparse

        parsed = urlparse(test_db_url)
        db = PostgreSQLDatabase(
            host=parsed.hostname or "localhost",
            port=parsed.port or 5432,
            database=parsed.path.lstrip("/") if parsed.path else "test_kotonoha",
            user=parsed.username or "test",
            password=parsed.password or "test",
        )
    else:
        # 個別パラメータから構築（環境変数から読み込み）
        db = PostgreSQLDatabase(
            host=os.getenv("TEST_POSTGRES_HOST", "localhost"),
            port=int(os.getenv("TEST_POSTGRES_PORT", "5432")),
            database=os.getenv("TEST_POSTGRES_DB", "test_kotonoha"),
            user=os.getenv("TEST_POSTGRES_USER", "test"),
            password=os.getenv("TEST_POSTGRES_PASSWORD", "test"),
        )

    await db.initialize()

    # テスト前のクリーンアップ
    await _cleanup_test_data(db)

    yield db

    # テスト後のクリーンアップ
    await _cleanup_test_data(db)
    await db.close()


@pytest_asyncio.fixture
async def postgres_db_with_rollback():
    """PostgreSQL データベースのフィクスチャ（ロールバックパターン）

    ⚠️ 改善: 各テストケースをトランザクション内で実行し、最後にロールバックする方式
    これにより、並列テスト実行時でも相互干渉が発生しません。
    また、TRUNCATE よりも高速で、テストデータのクリーンアップが不要です。

    使用方法:
    ```python
    async def test_example(postgres_db_with_rollback):
        db, conn = postgres_db_with_rollback
        # テストコード（トランザクション内で実行）
        await conn.execute("INSERT INTO sessions ...")
        # テスト終了時に自動的にロールバックされる
    ```
    """

    # テストDB接続文字列を環境変数から読み込み
    test_db_url = os.getenv(
        "TEST_DATABASE_URL",
        "postgresql://test:test@localhost:5432/test_kotonoha",
    )

    # PostgreSQLDatabaseの初期化
    # テストで個別パラメータが必要な場合に備えて、接続文字列からパースする
    if test_db_url.startswith("postgresql://"):
        # 接続文字列をパースして個別パラメータを抽出
        from urllib.parse import urlparse

        parsed = urlparse(test_db_url)
        db = PostgreSQLDatabase(
            host=parsed.hostname or "localhost",
            port=parsed.port or 5432,
            database=parsed.path.lstrip("/") if parsed.path else "test_kotonoha",
            user=parsed.username or "test",
            password=parsed.password or "test",
        )
    else:
        # 個別パラメータから構築（環境変数から読み込み）
        db = PostgreSQLDatabase(
            host=os.getenv("TEST_POSTGRES_HOST", "localhost"),
            port=int(os.getenv("TEST_POSTGRES_PORT", "5432")),
            database=os.getenv("TEST_POSTGRES_DB", "test_kotonoha"),
            user=os.getenv("TEST_POSTGRES_USER", "test"),
            password=os.getenv("TEST_POSTGRES_PASSWORD", "test"),
        )

    await db.initialize()

    # 各テストケースごとに新しいトランザクションを開始
    assert db.pool is not None, "Database pool must be initialized"
    conn = await db.pool.acquire()
    tx = conn.transaction()
    await tx.start()

    try:
        yield (db, conn)
    finally:
        # テスト終了時にロールバック（データを元に戻す）
        await tx.rollback()
        if db.pool is not None:
            await db.pool.release(conn)
        await db.close()


@pytest.fixture
def mock_embedding_provider():
    """OpenAI API のモック（CI/CDでテストが失敗しないように）

    ⚠️ 改善: より詳細なモック実装例
    - バッチ処理のモック
    - エラーケースのモック
    - レート制限のモック
    """
    provider = AsyncMock(spec=EmbeddingProvider)

    # 基本的なメソッドのモック
    provider.generate_embedding = AsyncMock(return_value=[0.1] * 1536)
    provider.get_dimension = lambda: 1536

    # ⚠️ 改善: バッチ処理のモック
    async def generate_embeddings_batch(texts: list[str]) -> list[list[float]]:
        """バッチ処理のモック"""
        return [[0.1] * 1536 for _ in texts]

    provider.generate_embeddings_batch = generate_embeddings_batch

    # ⚠️ 改善: エラーケースのモック（必要に応じて使用）
    provider.generate_embedding_error = AsyncMock(side_effect=Exception("API Error"))

    return provider


@pytest.fixture
def mock_postgres_pool():
    """PostgreSQL接続プールのモック"""
    pool = AsyncMock()
    conn = AsyncMock()

    # 接続の取得をモック
    async def acquire():
        return conn

    pool.acquire = AsyncMock(return_value=conn)
    pool.__aenter__ = lambda _self: _self  # noqa: ARG001
    pool.__aexit__ = lambda _self, *_: None  # noqa: ARG001

    # 基本的なクエリのモック
    conn.execute = AsyncMock(return_value="OK")
    conn.fetchval = AsyncMock(return_value=1)
    conn.fetchrow = AsyncMock(return_value=None)
    conn.fetch = AsyncMock(return_value=[])
    conn.transaction = MagicMock()

    return pool
