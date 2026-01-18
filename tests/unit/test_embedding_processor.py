"""EmbeddingProcessor のテスト"""

from unittest.mock import AsyncMock

import pytest

from kotonoha_bot.external.embedding.openai_embedding import (
    OpenAIEmbeddingProvider,
)
from kotonoha_bot.features.knowledge_base.embedding_processor import (
    EmbeddingProcessor,
)


@pytest.mark.asyncio
async def test_embedding_processor_initialization(postgres_db, mock_embedding_provider):
    """EmbeddingProcessorの初期化テスト"""
    processor = EmbeddingProcessor(
        db=postgres_db,
        embedding_provider=mock_embedding_provider,
        batch_size=10,
        max_concurrent=2,
    )

    assert processor.db == postgres_db
    assert processor.embedding_provider == mock_embedding_provider
    assert processor.batch_size == 10
    assert processor._semaphore._value == 2


@pytest.mark.asyncio
async def test_embedding_processor_process_pending_chunks(
    postgres_db, mock_embedding_provider
):
    """Embedding処理のテスト"""
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

    # EmbeddingProcessorを作成
    processor = EmbeddingProcessor(
        db=postgres_db,
        embedding_provider=mock_embedding_provider,
        batch_size=10,
        max_concurrent=2,
    )

    # 処理を実行
    await processor._process_pending_embeddings_impl()

    # embeddingが設定されているか確認
    async with postgres_db.pool.acquire() as conn:
        result = await conn.fetchrow(
            """
            SELECT embedding IS NOT NULL as has_embedding
            FROM knowledge_chunks
            WHERE id = $1
        """,
            chunk_id,
        )

        assert result is not None
        assert result["has_embedding"] is True


@pytest.mark.asyncio
async def test_embedding_processor_retry_logic(postgres_db):
    """リトライロジックのテスト"""
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

    # エラーを発生させるモック
    error_provider = AsyncMock(spec=OpenAIEmbeddingProvider)
    error_provider.generate_embeddings_batch = AsyncMock(
        side_effect=Exception("API Error")
    )
    error_provider.get_dimension = lambda: 1536

    processor = EmbeddingProcessor(
        db=postgres_db,
        embedding_provider=error_provider,
        batch_size=10,
        max_concurrent=2,
    )

    # 処理を実行（エラーが発生する）
    await processor._process_pending_embeddings_impl()

    # retry_countがインクリメントされているか確認
    async with postgres_db.pool.acquire() as conn:
        result = await conn.fetchrow(
            """
            SELECT retry_count
            FROM knowledge_chunks
            WHERE id = $1
        """,
            chunk_id,
        )

        assert result is not None
        assert result["retry_count"] > 0


@pytest.mark.asyncio
async def test_embedding_processor_batch_processing(
    postgres_db, mock_embedding_provider
):
    """バッチ処理のテスト"""
    # 複数のチャンクを作成
    source_id = await postgres_db.save_source(
        source_type="discord_session",
        title="テストソース",
        uri="https://example.com/test",
        metadata={"test": True},
        status="pending",
    )

    chunk_ids = []
    for i in range(5):
        chunk_id = await postgres_db.save_chunk(
            source_id=source_id,
            content=f"これはテスト用のチャンク{i}です",
            location={"url": "https://example.com/test", "label": f"テスト{i}"},
            token_count=10,
        )
        chunk_ids.append(chunk_id)

    processor = EmbeddingProcessor(
        db=postgres_db,
        embedding_provider=mock_embedding_provider,
        batch_size=10,
        max_concurrent=2,
    )

    # 処理を実行
    await processor._process_pending_embeddings_impl()

    # すべてのチャンクが処理されているか確認
    async with postgres_db.pool.acquire() as conn:
        results = await conn.fetch(
            """
            SELECT COUNT(*) as processed_count
            FROM knowledge_chunks
            WHERE id = ANY($1::bigint[])
            AND embedding IS NOT NULL
        """,
            chunk_ids,
        )

        assert results[0]["processed_count"] == len(chunk_ids)
