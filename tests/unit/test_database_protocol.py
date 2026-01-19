"""DatabaseProtocol と KnowledgeBaseProtocol のプロトコル準拠テスト

実装クラスがプロトコルを正しく実装していることを確認
"""

from datetime import UTC, datetime

import pytest

from kotonoha_bot.db.base import DatabaseProtocol, KnowledgeBaseProtocol
from kotonoha_bot.db.postgres import PostgreSQLDatabase
from kotonoha_bot.session.models import ChatSession, Message, MessageRole


def test_postgres_database_implements_database_protocol():
    """PostgreSQLDatabaseがDatabaseProtocolを実装していることを確認"""
    assert issubclass(PostgreSQLDatabase, DatabaseProtocol)


def test_postgres_database_implements_knowledge_base_protocol():
    """PostgreSQLDatabaseがKnowledgeBaseProtocolを実装していることを確認"""
    assert issubclass(PostgreSQLDatabase, KnowledgeBaseProtocol)


@pytest.mark.asyncio
async def test_database_protocol_methods_implemented(postgres_db):
    """DatabaseProtocolのすべてのメソッドが実装されていることを確認"""
    # 抽象メソッドが実装されていることを確認（インスタンス化できる = 実装されている）
    assert hasattr(postgres_db, "initialize")
    assert hasattr(postgres_db, "close")
    assert hasattr(postgres_db, "save_session")
    assert hasattr(postgres_db, "load_session")
    assert hasattr(postgres_db, "delete_session")
    assert hasattr(postgres_db, "load_all_sessions")

    # メソッドがコーラブルであることを確認
    assert callable(postgres_db.initialize)
    assert callable(postgres_db.close)
    assert callable(postgres_db.save_session)
    assert callable(postgres_db.load_session)
    assert callable(postgres_db.delete_session)
    assert callable(postgres_db.load_all_sessions)


@pytest.mark.asyncio
async def test_knowledge_base_protocol_methods_implemented(postgres_db):
    """KnowledgeBaseProtocolのすべてのメソッドが実装されていることを確認"""
    # 抽象メソッドが実装されていることを確認
    assert hasattr(postgres_db, "similarity_search")
    assert hasattr(postgres_db, "save_source")
    assert hasattr(postgres_db, "save_chunk")

    # メソッドがコーラブルであることを確認
    assert callable(postgres_db.similarity_search)
    assert callable(postgres_db.save_source)
    assert callable(postgres_db.save_chunk)


@pytest.mark.asyncio
async def test_database_protocol_save_and_load_session(postgres_db):
    """DatabaseProtocolのsave_sessionとload_sessionが正しく動作することを確認"""
    session = ChatSession(
        session_key="test:protocol:001",
        session_type="mention",
        messages=[
            Message(
                role=MessageRole.USER,
                content="プロトコルテスト",
                timestamp=datetime.now(UTC),
            )
        ],
        guild_id=123456789,
        channel_id=987654321,
        user_id=111222333,
    )

    # save_sessionが動作することを確認
    await postgres_db.save_session(session)

    # load_sessionが動作することを確認
    loaded_session = await postgres_db.load_session("test:protocol:001")
    assert loaded_session is not None
    assert loaded_session.session_key == "test:protocol:001"


@pytest.mark.asyncio
async def test_database_protocol_delete_session(postgres_db):
    """DatabaseProtocolのdelete_sessionが正しく動作することを確認"""
    session = ChatSession(
        session_key="test:protocol:delete:001",
        session_type="mention",
        messages=[],
        guild_id=123456789,
        channel_id=987654321,
        user_id=111222333,
    )

    # セッションを保存
    await postgres_db.save_session(session)

    # セッションが存在することを確認
    loaded = await postgres_db.load_session("test:protocol:delete:001")
    assert loaded is not None

    # セッションを削除
    await postgres_db.delete_session("test:protocol:delete:001")

    # セッションが削除されたことを確認
    deleted = await postgres_db.load_session("test:protocol:delete:001")
    assert deleted is None


@pytest.mark.asyncio
async def test_database_protocol_load_all_sessions(postgres_db):
    """DatabaseProtocolのload_all_sessionsが正しく動作することを確認"""
    # 複数のセッションを作成
    for i in range(3):
        session = ChatSession(
            session_key=f"test:protocol:all:{i}",
            session_type="mention",
            messages=[],
            guild_id=123456789,
            channel_id=987654321,
            user_id=111222333,
        )
        await postgres_db.save_session(session)

    # すべてのセッションを読み込み
    all_sessions = await postgres_db.load_all_sessions()

    # 作成したセッションが含まれていることを確認
    session_keys = {s.session_key for s in all_sessions}
    assert "test:protocol:all:0" in session_keys
    assert "test:protocol:all:1" in session_keys
    assert "test:protocol:all:2" in session_keys


@pytest.mark.asyncio
async def test_knowledge_base_protocol_save_source(postgres_db):
    """KnowledgeBaseProtocolのsave_sourceが正しく動作することを確認"""
    source_id = await postgres_db.save_source(
        source_type="discord_session",
        title="プロトコルテスト用ソース",
        uri="https://example.com/protocol",
        metadata={"test": True},
        status="pending",
    )

    assert source_id is not None
    assert isinstance(source_id, int)


@pytest.mark.asyncio
async def test_knowledge_base_protocol_save_chunk(postgres_db):
    """KnowledgeBaseProtocolのsave_chunkが正しく動作することを確認"""
    # まずソースを作成
    source_id = await postgres_db.save_source(
        source_type="discord_session",
        title="プロトコルテスト用ソース",
        uri="https://example.com/protocol",
        metadata={"test": True},
        status="pending",
    )

    # チャンクを保存
    chunk_id = await postgres_db.save_chunk(
        source_id=source_id,
        content="プロトコルテスト用のチャンク",
        location={"url": "https://example.com/protocol", "label": "テスト"},
        token_count=10,
    )

    assert chunk_id is not None
    assert isinstance(chunk_id, int)


@pytest.mark.asyncio
async def test_knowledge_base_protocol_similarity_search(postgres_db):
    """KnowledgeBaseProtocolのsimilarity_searchが正しく動作することを確認"""
    # テスト用のソースとチャンクを作成
    source_id = await postgres_db.save_source(
        source_type="discord_session",
        title="プロトコルテスト用ソース",
        uri="https://example.com/protocol",
        metadata={"test": True},
        status="pending",
    )

    chunk_id = await postgres_db.save_chunk(
        source_id=source_id,
        content="プロトコルテスト用のチャンク",
        location={"url": "https://example.com/protocol", "label": "テスト"},
        token_count=10,
    )

    # テスト用のベクトルを挿入
    async with postgres_db.pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE knowledge_chunks
            SET embedding = (SELECT array_agg(0.1::real) FROM generate_series(1, 1536))::halfvec(1536)
            WHERE id = $1
        """,
            chunk_id,
        )

    # ベクトル検索を実行
    query_embedding = [0.1] * 1536
    results = await postgres_db.similarity_search(
        query_embedding=query_embedding,
        top_k=5,
    )

    # 検索結果が返ってくることを確認
    assert isinstance(results, list)
    assert len(results) > 0

    # 検索結果の構造を確認
    result = results[0]
    assert "chunk_id" in result
    assert "source_id" in result
    assert "content" in result
    assert "similarity" in result
    assert "source_type" in result
    assert "title" in result
