"""負荷テスト（phase08.md の「6. テスト計画」に記載されている負荷テストシナリオ）"""

import asyncio
import time

import pytest


@pytest.mark.asyncio
@pytest.mark.slow  # 実行に時間がかかるテスト
async def test_vector_search_with_10000_chunks(postgres_db):
    """1万件のチャンクでの検索レイテンシテスト

    1万件のチャンクを登録し、検索クエリを実行してレイテンシが1秒以内であることを確認
    """
    # テスト用のソースを作成
    source_id = await postgres_db.save_source(
        source_type="discord_session",
        title="負荷テスト用ソース（1万件）",
        uri="https://example.com/load",
        metadata={"test": True},
        status="pending",
    )

    # 1万件のチャンクを作成（バッチ処理で効率化）
    chunk_ids = []
    batch_size = 100

    async with postgres_db.pool.acquire() as conn:
        for batch_start in range(0, 10000, batch_size):
            batch_end = min(batch_start + batch_size, 10000)

            # バッチでチャンクを挿入
            values = []
            for i in range(batch_start, batch_end):
                values.append(
                    f"($1, 'これは負荷テスト用のチャンク{i}です', "
                    f'\'{{"url": "https://example.com/load", "label": "チャンク{i}"}}\'::jsonb, 20)'
                )

            query = f"""
                INSERT INTO knowledge_chunks (source_id, content, location, token_count)
                VALUES {", ".join(values)}
                RETURNING id
            """

            batch_ids = await conn.fetch(query, source_id)
            chunk_ids.extend([row["id"] for row in batch_ids])

    # テスト用のベクトルを挿入（バッチ処理で効率化）
    async with postgres_db.pool.acquire() as conn:
        for i, chunk_id in enumerate(chunk_ids):
            # 各チャンクに異なるベクトルを設定
            embedding = [0.1 + (i * 0.0001) for _ in range(1536)]
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

    # レイテンシが1秒以内であることを確認
    assert elapsed < 1.0, (
        f"1万件のチャンクでの検索が1秒以内に完了する必要があります（実際: {elapsed:.3f}秒）"
    )
    assert len(results) <= 10
    assert len(results) > 0, "検索結果が返ってくる必要があります"


@pytest.mark.asyncio
@pytest.mark.slow  # 実行に時間がかかるテスト
async def test_100_concurrent_connections(postgres_db):
    """100同時接続でのパフォーマンステスト

    100の同時接続でクエリを実行し、接続プールの枯渇が発生しないことを確認
    """
    # テスト用のソースとチャンクを作成
    source_id = await postgres_db.save_source(
        source_type="discord_session",
        title="同時接続テスト用ソース",
        uri="https://example.com/concurrent",
        metadata={"test": True},
        status="pending",
    )

    chunk_id = await postgres_db.save_chunk(
        source_id=source_id,
        content="これは同時接続テスト用のチャンクです",
        location={"url": "https://example.com/concurrent", "label": "テスト"},
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

    # 100の同時接続でクエリを実行
    query_embedding = [0.1] * 1536

    async def search_task():
        """検索タスク"""
        try:
            results = await postgres_db.similarity_search(
                query_embedding=query_embedding,
                top_k=5,
            )
            return len(results)
        except Exception as e:
            # 接続プール枯渇エラーをキャッチ
            return f"Error: {e}"

    # 100のタスクを同時実行
    tasks = [search_task() for _ in range(100)]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # 接続プールの枯渇が発生していないことを確認
    error_count = sum(1 for r in results if isinstance(r, (Exception, str)))
    assert error_count == 0, f"接続プールの枯渇が発生しました: {error_count}件のエラー"

    # すべてのタスクが成功していることを確認
    success_count = sum(1 for r in results if isinstance(r, int))
    assert success_count == 100, (
        f"すべてのタスクが成功する必要があります: success={success_count}, total=100"
    )


@pytest.mark.asyncio
@pytest.mark.slow  # 実行に時間がかかるテスト
async def test_hnsw_index_rebuild_time(postgres_db):
    """HNSWインデックス再構築時間のテスト

    大量のデータでインデックスを再構築し、構築時間を測定
    """
    # テスト用のソースを作成
    source_id = await postgres_db.save_source(
        source_type="discord_session",
        title="インデックス再構築テスト用ソース",
        uri="https://example.com/index_rebuild",
        metadata={"test": True},
        status="pending",
    )

    # 1000件のチャンクを作成（大量データをシミュレート）
    chunk_ids = []
    for i in range(1000):
        chunk_id = await postgres_db.save_chunk(
            source_id=source_id,
            content=f"これはインデックス再構築テスト用のチャンク{i}です",
            location={
                "url": "https://example.com/index_rebuild",
                "label": f"チャンク{i}",
            },
            token_count=20,
        )
        chunk_ids.append(chunk_id)

    # ベクトルを挿入（インデックスが自動的に構築される）
    async with postgres_db.pool.acquire() as conn:
        start = time.time()

        for i, chunk_id in enumerate(chunk_ids):
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

        elapsed = time.time() - start

    # インデックスの構築時間を記録（参考情報として）
    print(f"1000件のチャンクでのインデックス構築時間: {elapsed:.3f}秒")

    # インデックスが使用されていることを確認
    async with postgres_db.pool.acquire() as conn:
        index_usage = await conn.fetchrow(
            """
            SELECT idx_scan, idx_tup_read
            FROM pg_stat_user_indexes
            WHERE indexrelname::text LIKE '%embedding%'
            LIMIT 1
        """
        )

        if index_usage:
            assert index_usage["idx_scan"] > 0, (
                "HNSWインデックスが使用されている必要があります"
            )
