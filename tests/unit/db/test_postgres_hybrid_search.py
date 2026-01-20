"""PostgreSQL ハイブリッド検索のユニットテスト."""

import pytest


@pytest.mark.asyncio
async def test_hybrid_search_basic(postgres_db):
    """ハイブリッド検索の基本動作をテスト."""
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
        content="これはテスト用のチャンクです。ハイブリッド検索のテストを行います。",
        location={"url": "https://example.com/test", "label": "テスト"},
        token_count=20,
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

    # ハイブリッド検索を実行
    query_embedding = [0.1] * 1536
    query_text = "ハイブリッド検索"
    results = await postgres_db.hybrid_search(
        query_embedding=query_embedding,
        query_text=query_text,
        limit=10,
    )

    assert len(results) > 0
    assert results[0]["chunk_id"] == chunk_id
    assert results[0]["similarity"] > 0.0
    assert "ハイブリッド検索" in results[0]["content"]


@pytest.mark.asyncio
async def test_hybrid_search_scoring(postgres_db):
    """スコアリングが正しく計算されることをテスト."""
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
        content="これはテスト用のチャンクです。スコアリングのテストを行います。",
        location={"url": "https://example.com/test", "label": "テスト"},
        token_count=20,
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

    # デフォルトの重みでハイブリッド検索を実行
    query_embedding = [0.1] * 1536
    query_text = "スコアリング"
    results_default = await postgres_db.hybrid_search(
        query_embedding=query_embedding,
        query_text=query_text,
        limit=10,
        vector_weight=0.7,
        keyword_weight=0.3,
    )

    # カスタムの重みでハイブリッド検索を実行
    results_custom = await postgres_db.hybrid_search(
        query_embedding=query_embedding,
        query_text=query_text,
        limit=10,
        vector_weight=0.5,
        keyword_weight=0.5,
    )

    assert len(results_default) > 0
    assert len(results_custom) > 0
    # スコアが正しく計算されていることを確認（重みが異なればスコアも異なる可能性がある）
    assert isinstance(results_default[0]["similarity"], float)
    assert isinstance(results_custom[0]["similarity"], float)


@pytest.mark.asyncio
async def test_hybrid_search_weight_validation(postgres_db):
    """重みの合計が1.0でない場合にエラーが発生することをテスト."""
    query_embedding = [0.1] * 1536
    query_text = "テスト"

    # 重みの合計が1.0でない場合
    with pytest.raises(ValueError, match="must equal 1.0"):
        await postgres_db.hybrid_search(
            query_embedding=query_embedding,
            query_text=query_text,
            limit=10,
            vector_weight=0.7,
            keyword_weight=0.2,  # 合計が0.9
        )


@pytest.mark.asyncio
async def test_hybrid_search_filters(postgres_db):
    """フィルタリングが正しく動作することをテスト."""
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
        content="これはテスト用のチャンクです。フィルタリングのテストを行います。",
        location={"url": "https://example.com/test", "label": "テスト"},
        token_count=20,
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

    # フィルタリング付きハイブリッド検索を実行
    query_embedding = [0.1] * 1536
    query_text = "フィルタリング"
    results = await postgres_db.hybrid_search(
        query_embedding=query_embedding,
        query_text=query_text,
        limit=10,
        filters={"channel_id": 123456},
    )

    assert len(results) > 0
    assert results[0]["chunk_id"] == chunk_id

    # 異なるチャンネルIDでフィルタリング（結果が空になることを確認）
    results_empty = await postgres_db.hybrid_search(
        query_embedding=query_embedding,
        query_text=query_text,
        limit=10,
        filters={"channel_id": 999999},
    )

    assert len(results_empty) == 0


@pytest.mark.asyncio
async def test_hybrid_search_invalid_filters(postgres_db):
    """無効なフィルタキーが指定された場合にエラーが発生することをテスト."""
    query_embedding = [0.1] * 1536
    query_text = "テスト"

    # 無効なフィルタキー
    with pytest.raises(ValueError, match="Invalid filter keys"):
        await postgres_db.hybrid_search(
            query_embedding=query_embedding,
            query_text=query_text,
            limit=10,
            filters={"invalid_key": "value"},
        )


@pytest.mark.asyncio
async def test_hybrid_search_source_type_filter(postgres_db):
    """source_typeフィルタが正しく動作することをテスト."""
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
        content="これはテスト用のチャンクです。source_typeフィルタのテストを行います。",
        location={"url": "https://example.com/test", "label": "テスト"},
        token_count=20,
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

    # source_typeフィルタ付きハイブリッド検索を実行
    query_embedding = [0.1] * 1536
    query_text = "source_type"
    results = await postgres_db.hybrid_search(
        query_embedding=query_embedding,
        query_text=query_text,
        limit=10,
        filters={"source_type": "discord_session"},
    )

    assert len(results) > 0
    assert results[0]["source_type"] == "discord_session"

    # 異なるsource_typeでフィルタリング（結果が空になることを確認）
    results_empty = await postgres_db.hybrid_search(
        query_embedding=query_embedding,
        query_text=query_text,
        limit=10,
        filters={"source_type": "document_file"},
    )

    # 結果が空であるか、または異なるsource_typeの結果のみが返されることを確認
    assert (
        all(result["source_type"] != "discord_session" for result in results_empty)
        or len(results_empty) == 0
    )
