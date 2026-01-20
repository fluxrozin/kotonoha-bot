"""Embedding処理のパフォーマンステスト."""

import time

import pytest

from kotonoha_bot.features.knowledge_base.embedding_processor import EmbeddingProcessor


@pytest.mark.asyncio
@pytest.mark.slow
async def test_embedding_processing_batch_performance(
    postgres_db, mock_embedding_provider
):
    """Embedding処理のバッチパフォーマンステスト

    大量のチャンクをバッチ処理し、処理時間を測定する。
    """
    # テスト用のソースを作成
    source_id = await postgres_db.save_source(
        source_type="discord_session",
        title="Embedding処理パフォーマンステスト",
        uri="https://example.com/embedding_perf",
        metadata={"test": True},
        status="pending",
    )

    # 500個のチャンクを作成
    chunk_ids = []
    for i in range(500):
        chunk_id = await postgres_db.save_chunk(
            source_id=source_id,
            content=f"これはEmbedding処理パフォーマンステスト用のチャンク{i}です。"
            f"チャンクの内容は十分な長さを持っています。",
            location={
                "url": "https://example.com/embedding_perf",
                "label": f"チャンク{i}",
            },
            token_count=30,
        )
        chunk_ids.append(chunk_id)

    # EmbeddingProcessorを作成
    processor = EmbeddingProcessor(
        db=postgres_db,
        embedding_provider=mock_embedding_provider,
        batch_size=50,
        max_concurrent=5,
    )

    # 処理時間を測定（複数回実行してすべてのチャンクを処理）
    start = time.time()
    max_iterations = 15  # 最大15回のイテレーション
    iteration = 0
    while iteration < max_iterations:
        await processor._process_pending_embeddings_impl()

        # 残りのチャンク数を確認
        async with postgres_db.pool.acquire() as conn:
            pending_count = await conn.fetchval(
                """
                SELECT COUNT(*) FROM knowledge_chunks
                WHERE source_id = $1 AND embedding IS NULL
            """,
                source_id,
            )
            if pending_count == 0:
                break
        iteration += 1

    elapsed = time.time() - start

    # パフォーマンスアサーション
    # 500個のチャンクを50個ずつのバッチで処理する場合、10バッチ
    # 各バッチが並列処理されるため、処理時間は短縮される
    assert elapsed < 15.0, (
        f"500個のチャンクの処理が15秒以内に完了する必要があります（実際: {elapsed:.3f}秒）"
    )

    # すべてのチャンクが処理されたことを確認
    async with postgres_db.pool.acquire() as conn:
        pending_count = await conn.fetchval(
            """
            SELECT COUNT(*) FROM knowledge_chunks
            WHERE source_id = $1 AND embedding IS NULL
        """,
            source_id,
        )
        assert pending_count == 0, (
            f"すべてのチャンクが処理される必要があります（残り: {pending_count}個）"
        )


@pytest.mark.asyncio
@pytest.mark.slow
async def test_embedding_processing_concurrent_performance(
    postgres_db, mock_embedding_provider
):
    """Embedding処理の並行処理パフォーマンステスト

    複数のソースから同時にEmbedding処理を実行し、並行処理の効果を測定する。
    """
    # 複数のソースを作成
    source_ids = []
    for i in range(5):
        source_id = await postgres_db.save_source(
            source_type="discord_session",
            title=f"並行処理テストソース{i}",
            uri=f"https://example.com/concurrent{i}",
            metadata={"test": True},
            status="pending",
        )
        source_ids.append(source_id)

        # 各ソースに100個のチャンクを作成
        for j in range(100):
            await postgres_db.save_chunk(
                source_id=source_id,
                content=f"これは並行処理テスト用のチャンク{j}です。",
                location={
                    "url": f"https://example.com/concurrent{i}",
                    "label": f"チャンク{j}",
                },
                token_count=20,
            )

    # EmbeddingProcessorを作成（並行処理を有効化）
    processor = EmbeddingProcessor(
        db=postgres_db,
        embedding_provider=mock_embedding_provider,
        batch_size=50,
        max_concurrent=10,  # 高い並行度
    )

    # 処理時間を測定（複数回実行してすべてのチャンクを処理）
    start = time.time()
    max_iterations = 15  # 最大15回のイテレーション
    iteration = 0
    while iteration < max_iterations:
        await processor._process_pending_embeddings_impl()

        # 残りのチャンク数を確認（このテストで作成したソースのみ）
        async with postgres_db.pool.acquire() as conn:
            total_pending = await conn.fetchval(
                """
                SELECT COUNT(*) FROM knowledge_chunks
                WHERE source_id = ANY($1::int[]) AND embedding IS NULL
            """,
                source_ids,
            )
            if total_pending == 0:
                break
        iteration += 1

    elapsed = time.time() - start

    # パフォーマンスアサーション
    # 500個のチャンク（5ソース × 100チャンク）を並行処理
    assert elapsed < 20.0, (
        f"500個のチャンクの並行処理が20秒以内に完了する必要があります（実際: {elapsed:.3f}秒）"
    )

    # すべてのチャンクが処理されたことを確認（このテストで作成したソースのみ）
    async with postgres_db.pool.acquire() as conn:
        total_pending = await conn.fetchval(
            """
            SELECT COUNT(*) FROM knowledge_chunks
            WHERE source_id = ANY($1::int[]) AND embedding IS NULL
        """,
            source_ids,
        )
        assert total_pending == 0, (
            f"すべてのチャンクが処理される必要があります（残り: {total_pending}個）"
        )


@pytest.mark.asyncio
@pytest.mark.slow
async def test_embedding_processing_large_batch_performance(
    postgres_db, mock_embedding_provider
):
    """大量バッチ処理のパフォーマンステスト

    大きなバッチサイズでの処理性能を測定する。
    """
    # テスト用のソースを作成
    source_id = await postgres_db.save_source(
        source_type="discord_session",
        title="大量バッチ処理テスト",
        uri="https://example.com/large_batch",
        metadata={"test": True},
        status="pending",
    )

    # 1000個のチャンクを作成
    chunk_ids = []
    for i in range(1000):
        chunk_id = await postgres_db.save_chunk(
            source_id=source_id,
            content=f"これは大量バッチ処理テスト用のチャンク{i}です。",
            location={
                "url": "https://example.com/large_batch",
                "label": f"チャンク{i}",
            },
            token_count=20,
        )
        chunk_ids.append(chunk_id)

    # EmbeddingProcessorを作成（大きなバッチサイズ）
    processor = EmbeddingProcessor(
        db=postgres_db,
        embedding_provider=mock_embedding_provider,
        batch_size=200,  # 大きなバッチサイズ
        max_concurrent=5,
    )

    # 処理時間を測定（複数回実行してすべてのチャンクを処理）
    start = time.time()
    max_iterations = 10  # 最大10回のイテレーション
    iteration = 0
    while iteration < max_iterations:
        await processor._process_pending_embeddings_impl()

        # 残りのチャンク数を確認
        async with postgres_db.pool.acquire() as conn:
            pending_count = await conn.fetchval(
                """
                SELECT COUNT(*) FROM knowledge_chunks
                WHERE source_id = $1 AND embedding IS NULL
            """,
                source_id,
            )
            if pending_count == 0:
                break
        iteration += 1

    elapsed = time.time() - start

    # パフォーマンスアサーション
    # 1000個のチャンクを200個ずつのバッチで処理する場合、5バッチ
    assert elapsed < 30.0, (
        f"1000個のチャンクの処理が30秒以内に完了する必要があります（実際: {elapsed:.3f}秒）"
    )

    # すべてのチャンクが処理されたことを確認
    async with postgres_db.pool.acquire() as conn:
        pending_count = await conn.fetchval(
            """
            SELECT COUNT(*) FROM knowledge_chunks
            WHERE source_id = $1 AND embedding IS NULL
        """,
            source_id,
        )
        assert pending_count == 0, (
            f"すべてのチャンクが処理される必要があります（残り: {pending_count}個）"
        )
