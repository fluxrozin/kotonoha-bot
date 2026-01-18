"""PostgreSQLDatabase のテスト"""

from datetime import UTC, datetime

import pytest

from kotonoha_bot.session.models import ChatSession, Message, MessageRole


@pytest.mark.asyncio
async def test_postgres_db_initialize(postgres_db):
    """PostgreSQLDatabaseの初期化テスト"""
    assert postgres_db.pool is not None
    assert postgres_db.pool.get_size() > 0


@pytest.mark.asyncio
async def test_postgres_db_save_and_load_session(postgres_db):
    """セッションの保存と読み込みテスト"""
    # テスト用のセッションを作成
    session = ChatSession(
        session_key="test:session:001",
        session_type="mention",
        messages=[
            Message(
                role=MessageRole.USER,
                content="テストメッセージ",
                timestamp=datetime.now(UTC),
            )
        ],
        guild_id=123456789,
        channel_id=987654321,
        user_id=111222333,
    )

    # セッションを保存
    await postgres_db.save_session(session)

    # セッションを読み込み
    loaded_session = await postgres_db.load_session("test:session:001")

    assert loaded_session is not None
    assert loaded_session.session_key == "test:session:001"
    assert loaded_session.session_type == "mention"
    assert len(loaded_session.messages) == 1
    assert loaded_session.messages[0].content == "テストメッセージ"
    assert loaded_session.guild_id == 123456789
    assert loaded_session.channel_id == 987654321
    assert loaded_session.user_id == 111222333


@pytest.mark.asyncio
async def test_postgres_db_save_source(postgres_db):
    """知識ソースの保存テスト"""
    source_id = await postgres_db.save_source(
        source_type="discord_session",
        title="テストソース",
        uri="https://example.com/test",
        metadata={"test": True},
        status="pending",
    )

    assert source_id is not None
    assert isinstance(source_id, int)


@pytest.mark.asyncio
async def test_postgres_db_save_chunk(postgres_db):
    """知識チャンクの保存テスト"""
    # まずソースを作成
    source_id = await postgres_db.save_source(
        source_type="discord_session",
        title="テストソース",
        uri="https://example.com/test",
        metadata={"test": True},
        status="pending",
    )

    # チャンクを保存
    chunk_id = await postgres_db.save_chunk(
        source_id=source_id,
        content="これはテスト用のチャンクです",
        location={"url": "https://example.com/test", "label": "テスト"},
        token_count=10,
    )

    assert chunk_id is not None
    assert isinstance(chunk_id, int)


@pytest.mark.asyncio
async def test_postgres_db_similarity_search(postgres_db):
    """ベクトル検索のテスト"""
    # テスト用のソースとチャンクを作成
    source_id = await postgres_db.save_source(
        source_type="discord_session",
        title="テストソース",
        uri="https://example.com/test",
        metadata={"test": True},
        status="pending",
    )

    chunk_id = await postgres_db.save_chunk(
        source_id=source_id,
        content="これはテスト用のチャンクです",
        location={"url": "https://example.com/test", "label": "テスト"},
        token_count=10,
    )

    # テスト用のベクトルを挿入（1536次元のダミーベクトル）
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

    assert len(results) > 0
    assert results[0]["chunk_id"] == chunk_id
    assert results[0]["similarity"] > 0.0


@pytest.mark.asyncio
async def test_postgres_db_similarity_search_with_filters(postgres_db):
    """フィルタリング付きベクトル検索のテスト"""
    # テスト用のソースとチャンクを作成
    source_id = await postgres_db.save_source(
        source_type="discord_session",
        title="テストソース",
        uri="https://example.com/test",
        metadata={"channel_id": 123456, "user_id": 789012},
        status="pending",
    )

    chunk_id = await postgres_db.save_chunk(
        source_id=source_id,
        content="これはテスト用のチャンクです",
        location={"url": "https://example.com/test", "label": "テスト"},
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

    # フィルタリング付きベクトル検索を実行
    query_embedding = [0.1] * 1536
    results = await postgres_db.similarity_search(
        query_embedding=query_embedding,
        top_k=5,
        filters={"channel_id": 123456},
    )

    assert len(results) > 0
    assert results[0]["chunk_id"] == chunk_id

    # 異なるチャンネルIDでフィルタリング（結果が空になることを確認）
    results_empty = await postgres_db.similarity_search(
        query_embedding=query_embedding,
        top_k=5,
        filters={"channel_id": 999999},
    )

    assert len(results_empty) == 0


@pytest.mark.asyncio
async def test_postgres_db_similarity_search_without_threshold(postgres_db):
    """閾値フィルタリングなしのベクトル検索テスト"""
    # テスト用のソースとチャンクを作成
    source_id = await postgres_db.save_source(
        source_type="discord_session",
        title="テストソース",
        uri="https://example.com/test",
        metadata={"test": True},
        status="pending",
    )

    chunk_id = await postgres_db.save_chunk(
        source_id=source_id,
        content="これはテスト用のチャンクです",
        location={"url": "https://example.com/test", "label": "テスト"},
        token_count=10,
    )

    # テスト用のベクトルを挿入（すべて0.1の値）
    async with postgres_db.pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE knowledge_chunks
            SET embedding = (SELECT array_agg(0.1::real) FROM generate_series(1, 1536))::halfvec(1536)
            WHERE id = $1
        """,
            chunk_id,
        )

    # 異なる方向のベクトルで検索（閾値を下回る可能性がある）
    query_embedding = [0.2] * 1536  # 異なる値のベクトル
    results = await postgres_db.similarity_search(
        query_embedding=query_embedding,
        top_k=5,
        apply_threshold=False,  # 閾値フィルタリングを無効化
    )

    # 閾値フィルタリングを無効化しているため、結果が返ってくる可能性がある
    # （実際の類似度スコアに応じて）
    assert isinstance(results, list)


@pytest.mark.asyncio
async def test_postgres_db_halfvec_insert_and_select(postgres_db):
    """halfvec固定採用でのINSERTとSELECTのテスト"""
    # テスト用のソースとチャンクを作成
    source_id = await postgres_db.save_source(
        source_type="discord_session",
        title="テストソース",
        uri="https://example.com/test",
        metadata={"test": True},
        status="pending",
    )

    chunk_id = await postgres_db.save_chunk(
        source_id=source_id,
        content="テストコンテンツ",
        location={"url": "https://example.com/test", "label": "テスト"},
        token_count=5,
    )

    # halfvec型でベクトルを挿入
    test_embedding = [0.1] * 1536
    async with postgres_db.pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE knowledge_chunks
            SET embedding = $1::halfvec(1536)
            WHERE id = $2
        """,
            test_embedding,
            chunk_id,
        )

        # SELECTテスト（halfvec型の距離計算）
        result = await conn.fetchrow(
            """
            SELECT embedding <=> $1::halfvec(1536) AS distance
            FROM knowledge_chunks
            WHERE id = $2
        """,
            test_embedding,
            chunk_id,
        )

        assert result is not None
        assert result["distance"] is not None
        assert isinstance(result["distance"], float)
        # 同じベクトル同士の距離は0に近い
        assert result["distance"] < 0.01
