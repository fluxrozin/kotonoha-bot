"""ベクトル検索の統合テスト

データ登録→Embedding処理→検索の一連の流れを確認
"""

import pytest

from kotonoha_bot.features.knowledge_base.embedding_processor import (
    EmbeddingProcessor,
)


@pytest.mark.asyncio
async def test_vector_search_integration_flow(postgres_db, mock_embedding_provider):
    """ベクトル検索の統合テスト

    データ登録→Embedding処理→検索の一連の流れを確認
    """
    # 1. 複数の知識ソースとチャンクを作成
    source_ids = []
    chunk_ids = []

    for i in range(3):
        source_id = await postgres_db.save_source(
            source_type="discord_session",
            title=f"検索統合テスト用ソース{i}",
            uri=f"https://example.com/search_integration_{i}",
            metadata={"test": True, "index": i},
            status="pending",
        )
        source_ids.append(source_id)

        # 各ソースに複数のチャンクを作成
        for j in range(2):
            chunk_id = await postgres_db.save_chunk(
                source_id=source_id,
                content=f"これは検索統合テスト用のソース{i}のチャンク{j}です",
                location={
                    "url": f"https://example.com/search_integration_{i}",
                    "label": f"ソース{i}-チャンク{j}",
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
        result = await conn.fetchval(
            """
            SELECT COUNT(*)
            FROM knowledge_chunks
            WHERE id = ANY($1::bigint[])
            AND embedding IS NOT NULL
        """,
            chunk_ids,
        )

        assert result == len(chunk_ids), (
            f"すべてのチャンクがEmbedding処理されている必要があります: "
            f"processed={result}, total={len(chunk_ids)}"
        )

    # 4. ベクトル検索の実行
    query_embedding = [0.1] * 1536
    results = await postgres_db.similarity_search(
        query_embedding=query_embedding,
        top_k=10,
    )

    assert len(results) > 0, "検索結果が返ってくる必要があります"
    assert len(results) <= 10, "検索結果数がtop_k以下である必要があります"

    # 5. 検索結果の整合性を確認
    for result in results:
        assert "chunk_id" in result
        assert "source_id" in result
        assert "content" in result
        assert "similarity" in result
        assert 0.0 <= result["similarity"] <= 1.0, (
            f"類似度スコアが0.0〜1.0の範囲内である必要があります: "
            f"actual={result['similarity']}"
        )


@pytest.mark.asyncio
async def test_vector_search_with_filters_integration(
    postgres_db, mock_embedding_provider
):
    """フィルタリング付きベクトル検索の統合テスト

    データ登録→Embedding処理→フィルタリング付き検索の一連の流れを確認
    """
    # 1. 異なるチャンネルIDのソースとチャンクを作成
    source_id_1 = await postgres_db.save_source(
        source_type="discord_session",
        title="チャンネル1のソース",
        uri="https://example.com/channel1",
        metadata={"channel_id": 111111, "test": True},
        status="pending",
    )

    source_id_2 = await postgres_db.save_source(
        source_type="discord_session",
        title="チャンネル2のソース",
        uri="https://example.com/channel2",
        metadata={"channel_id": 222222, "test": True},
        status="pending",
    )

    await postgres_db.save_chunk(
        source_id=source_id_1,
        content="チャンネル1のチャンク",
        location={"url": "https://example.com/channel1", "label": "チャンク1"},
        token_count=10,
    )

    await postgres_db.save_chunk(
        source_id=source_id_2,
        content="チャンネル2のチャンク",
        location={"url": "https://example.com/channel2", "label": "チャンク2"},
        token_count=10,
    )

    # 2. Embedding処理の実行
    processor = EmbeddingProcessor(
        db=postgres_db,
        embedding_provider=mock_embedding_provider,
        batch_size=10,
        max_concurrent=2,
    )

    await processor._process_pending_embeddings_impl()

    # 3. フィルタリング付き検索（チャンネル1のみ）
    query_embedding = [0.1] * 1536
    results = await postgres_db.similarity_search(
        query_embedding=query_embedding,
        top_k=10,
        filters={"channel_id": 111111},
    )

    # チャンネル1のチャンクのみが返ってくることを確認
    assert len(results) > 0
    for result in results:
        assert result["source_metadata"].get("channel_id") == 111111, (
            f"検索結果はチャンネル1のチャンクのみである必要があります: "
            f"actual_channel_id={result['source_metadata'].get('channel_id')}"
        )

    # 4. フィルタリング付き検索（チャンネル2のみ）
    results2 = await postgres_db.similarity_search(
        query_embedding=query_embedding,
        top_k=10,
        filters={"channel_id": 222222},
    )

    # チャンネル2のチャンクのみが返ってくることを確認
    assert len(results2) > 0
    for result in results2:
        assert result["source_metadata"].get("channel_id") == 222222, (
            f"検索結果はチャンネル2のチャンクのみである必要があります: "
            f"actual_channel_id={result['source_metadata'].get('channel_id')}"
        )


@pytest.mark.asyncio
async def test_vector_search_with_source_type_filter(
    postgres_db, mock_embedding_provider
):
    """ソースタイプフィルタリング付きベクトル検索の統合テスト

    異なるソースタイプのデータを登録→Embedding処理→ソースタイプでフィルタリング検索
    """
    # 1. 異なるソースタイプのソースとチャンクを作成
    source_id_session = await postgres_db.save_source(
        source_type="discord_session",
        title="セッションソース",
        uri="https://example.com/session",
        metadata={"test": True},
        status="pending",
    )

    source_id_document = await postgres_db.save_source(
        source_type="document_file",
        title="ドキュメントソース",
        uri="https://example.com/document",
        metadata={"test": True},
        status="pending",
    )

    await postgres_db.save_chunk(
        source_id=source_id_session,
        content="セッションのチャンク",
        location={"url": "https://example.com/session", "label": "セッションチャンク"},
        token_count=10,
    )

    await postgres_db.save_chunk(
        source_id=source_id_document,
        content="ドキュメントのチャンク",
        location={
            "url": "https://example.com/document",
            "label": "ドキュメントチャンク",
        },
        token_count=10,
    )

    # 2. Embedding処理の実行
    processor = EmbeddingProcessor(
        db=postgres_db,
        embedding_provider=mock_embedding_provider,
        batch_size=10,
        max_concurrent=2,
    )

    await processor._process_pending_embeddings_impl()

    # 3. ソースタイプでフィルタリング検索（discord_sessionのみ）
    query_embedding = [0.1] * 1536
    results = await postgres_db.similarity_search(
        query_embedding=query_embedding,
        top_k=10,
        filters={"source_type": "discord_session"},
    )

    # discord_sessionのチャンクのみが返ってくることを確認
    assert len(results) > 0
    for result in results:
        assert result["source_type"] == "discord_session", (
            f"検索結果はdiscord_sessionのチャンクのみである必要があります: "
            f"actual_source_type={result['source_type']}"
        )
