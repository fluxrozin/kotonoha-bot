"""ベクトル検索のパフォーマンステスト"""

import time

import pytest


@pytest.mark.asyncio
async def test_vector_search_performance(postgres_db):
    """ベクトル検索の性能測定"""
    # テストデータの準備（複数のチャンクを作成）
    source_id = await postgres_db.save_source(
        source_type="discord_session",
        title="パフォーマンステスト用ソース",
        uri="https://example.com/performance",
        metadata={"test": True},
        status="pending",
    )

    # 10個のチャンクを作成
    chunk_ids = []
    for i in range(10):
        chunk_id = await postgres_db.save_chunk(
            source_id=source_id,
            content=f"これはパフォーマンステスト用のチャンク{i}です",
            location={
                "url": "https://example.com/performance",
                "label": f"テストチャンク{i}",
            },
            token_count=20,
        )
        chunk_ids.append(chunk_id)

    # テスト用のベクトルを挿入
    async with postgres_db.pool.acquire() as conn:
        for chunk_id in chunk_ids:
            # 各チャンクに異なるベクトルを設定（検索の多様性を確保）
            embedding = [0.1 + (i * 0.01) for i in range(1536)]
            await conn.execute(
                """
                UPDATE knowledge_chunks
                SET embedding = $1::halfvec(1536)
                WHERE id = $2
            """,
                embedding,
                chunk_id,
            )

    # 検索実行
    query_embedding = [0.1] * 1536
    start = time.time()
    results = await postgres_db.similarity_search(
        query_embedding=query_embedding,
        top_k=10,
    )
    elapsed = time.time() - start

    # パフォーマンスアサーション
    assert elapsed < 1.0, f"検索が1秒以内に完了する必要があります（実際: {elapsed:.3f}秒）"
    assert len(results) <= 10
    assert len(results) > 0, "検索結果が返ってくる必要があります"


@pytest.mark.asyncio
async def test_vector_search_with_index(postgres_db):
    """HNSWインデックスの効果確認"""
    # 大量のチャンクを作成（インデックスの効果を確認するため）
    source_id = await postgres_db.save_source(
        source_type="discord_session",
        title="インデックステスト用ソース",
        uri="https://example.com/index",
        metadata={"test": True},
        status="pending",
    )

    # 100個のチャンクを作成
    chunk_ids = []
    for i in range(100):
        chunk_id = await postgres_db.save_chunk(
            source_id=source_id,
            content=f"これはインデックステスト用のチャンク{i}です",
            location={"url": "https://example.com/index", "label": f"チャンク{i}"},
            token_count=20,
        )
        chunk_ids.append(chunk_id)

    # テスト用のベクトルを挿入
    async with postgres_db.pool.acquire() as conn:
        for i, chunk_id in enumerate(chunk_ids):
            # 各チャンクに異なるベクトルを設定
            embedding = [0.1 + (i * 0.001) for _ in range(1536)]
            await conn.execute(
                """
                UPDATE knowledge_chunks
                SET embedding = $1::halfvec(1536)
                WHERE id = $2
            """,
                embedding,
                chunk_id,
            )

    # 検索実行（インデックスが使用される）
    query_embedding = [0.1] * 1536
    start = time.time()
    results = await postgres_db.similarity_search(
        query_embedding=query_embedding,
        top_k=10,
    )
    elapsed = time.time() - start

    # パフォーマンスアサーション（インデックスが使用されていれば高速）
    assert elapsed < 0.5, f"インデックス使用時は0.5秒以内に完了する必要があります（実際: {elapsed:.3f}秒）"
    assert len(results) <= 10

    # インデックスの使用状況を確認
    async with postgres_db.pool.acquire() as conn:
        index_usage = await conn.fetchrow(
            """
            SELECT idx_scan, idx_tup_read
            FROM pg_stat_user_indexes
            WHERE indexname LIKE '%embedding%'
            LIMIT 1
        """
        )

        if index_usage:
            # インデックスが使用されていることを確認
            assert index_usage["idx_scan"] > 0, "HNSWインデックスが使用されている必要があります"
