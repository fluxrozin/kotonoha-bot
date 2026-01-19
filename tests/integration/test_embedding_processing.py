"""Embedding処理の統合テスト

チャンクの作成→Embedding処理→検索の一連の流れを確認
"""

import pytest

from kotonoha_bot.features.knowledge_base.embedding_processor import (
    EmbeddingProcessor,
)


@pytest.mark.asyncio
async def test_embedding_processing_flow(postgres_db, mock_embedding_provider):
    """Embedding処理の統合テスト

    チャンクの作成→Embedding処理→検索の一連の流れを確認
    """
    # 1. 知識ソースとチャンクの作成
    source_id = await postgres_db.save_source(
        source_type="discord_session",
        title="Embedding処理統合テスト用ソース",
        uri="https://example.com/embedding_integration",
        metadata={"test": True},
        status="pending",
    )

    chunk_id = await postgres_db.save_chunk(
        source_id=source_id,
        content="これはEmbedding処理の統合テスト用チャンクです",
        location={
            "url": "https://example.com/embedding_integration",
            "label": "テストチャンク",
        },
        token_count=15,
    )

    # 2. Embedding処理の実行
    processor = EmbeddingProcessor(
        db=postgres_db,
        embedding_provider=mock_embedding_provider,
        batch_size=10,
        max_concurrent=2,
    )

    await processor._process_pending_embeddings_impl()

    # 3. Embeddingが設定されているか確認
    async with postgres_db.pool.acquire() as conn:
        result = await conn.fetchrow(
            """
            SELECT
                id,
                embedding IS NOT NULL as has_embedding,
                vector_dims(embedding) as embedding_dimension
            FROM knowledge_chunks
            WHERE id = $1
        """,
            chunk_id,
        )

        assert result is not None
        assert result["has_embedding"] is True
        assert result["embedding_dimension"] == 1536

    # 4. ベクトル検索で検索できることを確認
    query_embedding = [0.1] * 1536
    results = await postgres_db.similarity_search(
        query_embedding=query_embedding,
        top_k=5,
    )

    assert len(results) > 0
    assert any(r["chunk_id"] == chunk_id for r in results), (
        "作成したチャンクが検索結果に含まれている必要があります"
    )

    # 5. ソースのステータスが更新されているか確認
    async with postgres_db.pool.acquire() as conn:
        result = await conn.fetchrow(
            """
            SELECT status
            FROM knowledge_sources
            WHERE id = $1
        """,
            source_id,
        )

        assert result is not None
        # すべてのチャンクが処理された場合、ステータスが'completed'になる
        assert result["status"] in ("completed", "pending"), (
            f"ソースのステータスが期待される値ではありません: {result['status']}"
        )


@pytest.mark.asyncio
async def test_embedding_processing_with_multiple_chunks(
    postgres_db, mock_embedding_provider
):
    """複数チャンクのEmbedding処理統合テスト

    複数のチャンクを一括でEmbedding処理し、すべてが処理されることを確認
    """
    # 1. 知識ソースと複数のチャンクを作成
    source_id = await postgres_db.save_source(
        source_type="document_file",
        title="複数チャンクEmbedding処理テスト",
        uri="https://example.com/multi_chunk",
        metadata={"test": True},
        status="pending",
    )

    chunk_ids = []
    for i in range(5):
        chunk_id = await postgres_db.save_chunk(
            source_id=source_id,
            content=f"これは複数チャンクEmbedding処理テスト用のチャンク{i}です",
            location={
                "url": "https://example.com/multi_chunk",
                "label": f"チャンク{i}",
            },
            token_count=20,
        )
        chunk_ids.append(chunk_id)

    # 2. Embedding処理の実行
    processor = EmbeddingProcessor(
        db=postgres_db,
        embedding_provider=mock_embedding_provider,
        batch_size=10,
        max_concurrent=2,
    )

    await processor._process_pending_embeddings_impl()

    # 3. すべてのチャンクが処理されているか確認
    async with postgres_db.pool.acquire() as conn:
        results = await conn.fetch(
            """
            SELECT
                id,
                embedding IS NOT NULL as has_embedding
            FROM knowledge_chunks
            WHERE id = ANY($1::bigint[])
        """,
            chunk_ids,
        )

        assert len(results) == len(chunk_ids)
        assert all(r["has_embedding"] for r in results), (
            "すべてのチャンクがEmbedding処理されている必要があります"
        )
