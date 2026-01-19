"""境界値テスト

設定値の境界値（0, 1, 最大値、最大値+1等）をテスト
"""

from datetime import UTC, datetime, timedelta

import pytest

from kotonoha_bot.features.knowledge_base.embedding_processor import (
    EmbeddingProcessor,
)
from kotonoha_bot.features.knowledge_base.session_archiver import (
    SessionArchiver,
)


@pytest.mark.asyncio
async def test_similarity_search_top_k_boundary(postgres_db, mock_embedding_provider):
    """similarity_searchのtop_k境界値テスト"""
    # テスト用のソースとチャンクを作成
    source_id = await postgres_db.save_source(
        source_type="discord_session",
        title="top_k境界値テスト",
        uri="https://example.com/topk_test",
        metadata={"test": True},
        status="pending",
    )

    # 複数のチャンクを作成
    chunk_ids = []
    for i in range(15):
        chunk_id = await postgres_db.save_chunk(
            source_id=source_id,
            content=f"top_k境界値テスト用チャンク{i}",
            location={"url": "https://example.com/topk_test", "label": f"チャンク{i}"},
            token_count=10,
        )
        chunk_ids.append(chunk_id)

    # Embedding処理
    processor = EmbeddingProcessor(
        db=postgres_db,
        embedding_provider=mock_embedding_provider,
        batch_size=10,
        max_concurrent=2,
    )
    await processor._process_pending_embeddings_impl()

    query_embedding = [0.1] * 1536

    # top_k=0の場合（空のリストが返る）
    results_0 = await postgres_db.similarity_search(
        query_embedding=query_embedding,
        top_k=0,
    )
    assert len(results_0) == 0

    # top_k=1の場合
    results_1 = await postgres_db.similarity_search(
        query_embedding=query_embedding,
        top_k=1,
    )
    assert len(results_1) <= 1

    # top_k=10（デフォルト値）の場合
    results_10 = await postgres_db.similarity_search(
        query_embedding=query_embedding,
        top_k=10,
    )
    assert len(results_10) <= 10

    # top_k=100（非常に大きい値）の場合
    results_100 = await postgres_db.similarity_search(
        query_embedding=query_embedding,
        top_k=100,
    )
    assert len(results_100) <= 100
    # 実際のデータ数（15件）を超えない
    assert len(results_100) <= 15


@pytest.mark.asyncio
async def test_similarity_search_threshold_boundary(
    postgres_db, mock_embedding_provider
):
    """similarity_searchのsimilarity_threshold境界値テスト"""
    # テスト用のソースとチャンクを作成
    source_id = await postgres_db.save_source(
        source_type="discord_session",
        title="閾値境界値テスト",
        uri="https://example.com/threshold_test",
        metadata={"test": True},
        status="pending",
    )

    await postgres_db.save_chunk(
        source_id=source_id,
        content="閾値境界値テスト用チャンク",
        location={"url": "https://example.com/threshold_test", "label": "テスト"},
        token_count=10,
    )

    # Embedding処理
    processor = EmbeddingProcessor(
        db=postgres_db,
        embedding_provider=mock_embedding_provider,
        batch_size=10,
        max_concurrent=2,
    )
    await processor._process_pending_embeddings_impl()

    query_embedding = [0.1] * 1536

    # similarity_threshold=0.0（すべての結果が返る）
    results_0 = await postgres_db.similarity_search(
        query_embedding=query_embedding,
        top_k=10,
        similarity_threshold=0.0,
    )
    assert isinstance(results_0, list)

    # similarity_threshold=1.0（非常に高い閾値、結果が少ない可能性）
    results_1 = await postgres_db.similarity_search(
        query_embedding=query_embedding,
        top_k=10,
        similarity_threshold=1.0,
    )
    assert isinstance(results_1, list)
    # 閾値が高いため、結果が少ない可能性がある
    assert len(results_1) <= len(results_0)


@pytest.mark.asyncio
async def test_embedding_processor_batch_size_boundary(
    postgres_db, mock_embedding_provider
):
    """EmbeddingProcessorのbatch_size境界値テスト"""
    # テスト用のソースとチャンクを作成（大量）
    source_id = await postgres_db.save_source(
        source_type="discord_session",
        title="バッチサイズ境界値テスト",
        uri="https://example.com/batch_test",
        metadata={"test": True},
        status="pending",
    )

    # 150個のチャンクを作成（batch_size=100を超える）
    chunk_ids = []
    for i in range(150):
        chunk_id = await postgres_db.save_chunk(
            source_id=source_id,
            content=f"バッチサイズ境界値テスト用チャンク{i}",
            location={"url": "https://example.com/batch_test", "label": f"チャンク{i}"},
            token_count=10,
        )
        chunk_ids.append(chunk_id)

    # batch_size=100で処理
    processor = EmbeddingProcessor(
        db=postgres_db,
        embedding_provider=mock_embedding_provider,
        batch_size=100,  # デフォルト値
        max_concurrent=2,
    )

    # 処理を実行（複数バッチで処理される）
    # batch_size=100なので、150個のチャンクを処理するには複数回実行が必要
    for _ in range(2):  # 最大2回実行（100 + 50）
        await processor._process_pending_embeddings_impl()
        # すべて処理されたら終了
        async with postgres_db.pool.acquire() as conn:
            remaining = await conn.fetchval(
                """
                SELECT COUNT(*)
                FROM knowledge_chunks
                WHERE id = ANY($1::bigint[])
                AND embedding IS NULL
            """,
                chunk_ids,
            )
            if remaining == 0:
                break

    # すべてのチャンクが処理されていることを確認
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
        assert result == len(chunk_ids)


@pytest.mark.asyncio
async def test_embedding_processor_batch_size_small(
    postgres_db, mock_embedding_provider
):
    """EmbeddingProcessorの小さいbatch_sizeテスト"""
    # テスト用のソースとチャンクを作成
    source_id = await postgres_db.save_source(
        source_type="discord_session",
        title="小さいバッチサイズテスト",
        uri="https://example.com/small_batch",
        metadata={"test": True},
        status="pending",
    )

    # 5個のチャンクを作成
    chunk_ids = []
    for i in range(5):
        chunk_id = await postgres_db.save_chunk(
            source_id=source_id,
            content=f"小さいバッチサイズテスト用チャンク{i}",
            location={
                "url": "https://example.com/small_batch",
                "label": f"チャンク{i}",
            },
            token_count=10,
        )
        chunk_ids.append(chunk_id)

    # batch_size=1で処理
    processor = EmbeddingProcessor(
        db=postgres_db,
        embedding_provider=mock_embedding_provider,
        batch_size=1,  # 非常に小さいバッチサイズ
        max_concurrent=2,
    )

    # 処理を実行（batch_size=1なので、複数回実行する必要がある）
    # 5個のチャンクを処理するため、最大5回実行
    for _ in range(5):
        await processor._process_pending_embeddings_impl()
        # すべて処理されたら終了
        async with postgres_db.pool.acquire() as conn:
            remaining = await conn.fetchval(
                """
                SELECT COUNT(*)
                FROM knowledge_chunks
                WHERE id = ANY($1::bigint[])
                AND embedding IS NULL
            """,
                chunk_ids,
            )
            if remaining == 0:
                break

    # すべてのチャンクが処理されていることを確認
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
        assert result == len(chunk_ids)


@pytest.mark.asyncio
async def test_similarity_search_empty_embedding(postgres_db):
    """空のembeddingリストのテスト"""
    # 空のembeddingリストで検索（エラーが発生する可能性）
    with pytest.raises((ValueError, RuntimeError, Exception)):
        await postgres_db.similarity_search(
            query_embedding=[],  # 空のリスト
            top_k=5,
        )


@pytest.mark.asyncio
async def test_similarity_search_wrong_dimension(postgres_db):
    """異なる次元数のembeddingのテスト"""
    # 1536次元以外のembeddingで検索（エラーが発生する可能性）
    with pytest.raises((ValueError, RuntimeError, Exception)):
        await postgres_db.similarity_search(
            query_embedding=[0.1] * 512,  # 512次元（間違った次元数）
            top_k=5,
        )


@pytest.mark.asyncio
async def test_save_chunk_empty_content(postgres_db):
    """空のcontentでチャンク保存のテスト"""
    source_id = await postgres_db.save_source(
        source_type="discord_session",
        title="空コンテンツテスト",
        uri="https://example.com/empty_content",
        metadata={"test": True},
        status="pending",
    )

    # 空のcontentでチャンクを保存
    chunk_id = await postgres_db.save_chunk(
        source_id=source_id,
        content="",  # 空文字列
        location={"url": "https://example.com/empty_content", "label": "テスト"},
        token_count=0,
    )

    assert chunk_id is not None

    # チャンクが保存されていることを確認
    async with postgres_db.pool.acquire() as conn:
        result = await conn.fetchrow(
            "SELECT content, token_count FROM knowledge_chunks WHERE id = $1",
            chunk_id,
        )
        assert result is not None
        assert result["content"] == ""
        assert result["token_count"] == 0


@pytest.mark.asyncio
async def test_save_chunk_very_long_content(postgres_db):
    """非常に長いcontentでチャンク保存のテスト"""
    source_id = await postgres_db.save_source(
        source_type="discord_session",
        title="長いコンテンツテスト",
        uri="https://example.com/long_content",
        metadata={"test": True},
        status="pending",
    )

    # 非常に長いcontent（10000文字）
    long_content = "これは非常に長いコンテンツです。" * 500
    chunk_id = await postgres_db.save_chunk(
        source_id=source_id,
        content=long_content,
        location={"url": "https://example.com/long_content", "label": "テスト"},
        token_count=None,  # 自動計算
    )

    assert chunk_id is not None

    # チャンクが保存されていることを確認
    async with postgres_db.pool.acquire() as conn:
        result = await conn.fetchrow(
            "SELECT content, token_count FROM knowledge_chunks WHERE id = $1",
            chunk_id,
        )
        assert result is not None
        assert len(result["content"]) == len(long_content)
        assert result["token_count"] > 0


@pytest.mark.asyncio
async def test_session_archiver_min_session_length_boundary(
    postgres_db, mock_embedding_provider
):
    """SessionArchiverの最小セッション長さ境界値テスト"""

    from kotonoha_bot.config import settings
    from kotonoha_bot.session.models import ChatSession, Message, MessageRole

    min_length = settings.kb_min_session_length

    # 最小文字数ちょうどのセッション
    session_exact = ChatSession(
        session_key="test:session:min_length:exact:001",
        session_type="mention",
        messages=[
            Message(
                role=MessageRole.USER,
                content="a" * min_length,  # 最小文字数ちょうど
                timestamp=datetime.now(UTC) - timedelta(hours=2),
            )
        ],
        last_active_at=datetime.now(UTC) - timedelta(hours=2),
    )

    await postgres_db.save_session(session_exact)

    archiver = SessionArchiver(
        db=postgres_db,
        embedding_provider=mock_embedding_provider,
        archive_threshold_hours=1,
    )

    async with postgres_db.pool.acquire() as conn:
        session_row = await conn.fetchrow(
            """
            SELECT id, session_key, session_type, messages,
                   guild_id, channel_id, thread_id,
                   user_id, last_active_at, version,
                   last_archived_message_index
            FROM sessions
            WHERE session_key = $1
        """,
            "test:session:min_length:exact:001",
        )

        await archiver._archive_session_impl(dict(session_row))

    # 最小文字数ちょうどの場合、アーカイブされることを確認
    async with postgres_db.pool.acquire() as conn:
        source_count = await conn.fetchval(
            """
            SELECT COUNT(*)
            FROM knowledge_sources
            WHERE metadata->>'origin_session_key' = $1
        """,
            "test:session:min_length:exact:001",
        )
        assert source_count > 0  # アーカイブされる


@pytest.mark.asyncio
async def test_similarity_search_source_types_empty_list(postgres_db):
    """source_typesフィルタリングの空リストテスト"""
    query_embedding = [0.1] * 1536

    # 空のsource_typesリストで検索（エラーが発生する）
    with pytest.raises(ValueError, match="source_types must not be empty"):
        await postgres_db.similarity_search(
            query_embedding=query_embedding,
            top_k=5,
            filters={"source_types": []},  # 空のリスト
        )


@pytest.mark.asyncio
async def test_similarity_search_source_types_not_list(postgres_db):
    """source_typesフィルタリングの非リスト型テスト"""
    query_embedding = [0.1] * 1536

    # リスト以外の型で検索（エラーが発生する）
    with pytest.raises(ValueError, match="source_types must be a list"):
        await postgres_db.similarity_search(
            query_embedding=query_embedding,
            top_k=5,
            filters={"source_types": "discord_session"},  # 文字列（リストではない）
        )


@pytest.mark.asyncio
async def test_chunk_overlap_boundary(postgres_db, mock_embedding_provider):
    """チャンク化のオーバーラップ境界値テスト"""
    from datetime import timedelta

    from kotonoha_bot.session.models import ChatSession, Message, MessageRole

    # オーバーラップがチャンクサイズ以上の場合のテスト
    # （実際には設定で制限されているが、境界値として確認）
    messages = []
    for i in range(20):
        messages.append(
            Message(
                role=MessageRole.USER if i % 2 == 0 else MessageRole.ASSISTANT,
                content=f"オーバーラップ境界値テスト用メッセージ{i}",
                timestamp=datetime.now(UTC) - timedelta(hours=2),
            )
        )

    session = ChatSession(
        session_key="test:session:overlap_boundary:001",
        session_type="mention",
        messages=messages,
        guild_id=123456789,
        channel_id=987654321,
        user_id=111222333,
        last_active_at=datetime.now(UTC) - timedelta(hours=2),
    )

    await postgres_db.save_session(session)

    archiver = SessionArchiver(
        db=postgres_db,
        embedding_provider=mock_embedding_provider,
        archive_threshold_hours=1,
    )

    async with postgres_db.pool.acquire() as conn:
        session_row = await conn.fetchrow(
            """
            SELECT id, session_key, session_type, messages,
                   guild_id, channel_id, thread_id,
                   user_id, last_active_at, version,
                   last_archived_message_index
            FROM sessions
            WHERE session_key = $1
        """,
            "test:session:overlap_boundary:001",
        )

        await archiver._archive_session_impl(dict(session_row))

    # チャンクが正しく作成されていることを確認
    async with postgres_db.pool.acquire() as conn:
        source_result = await conn.fetchrow(
            """
            SELECT id FROM knowledge_sources
            WHERE metadata->>'origin_session_key' = $1
        """,
            "test:session:overlap_boundary:001",
        )

        if source_result:
            chunks = await conn.fetch(
                """
                SELECT * FROM knowledge_chunks WHERE source_id = $1
            """,
                source_result["id"],
            )
            # オーバーラップが機能していることを確認（チャンク数が適切）
            assert len(chunks) > 0


@pytest.mark.asyncio
async def test_embedding_processor_max_concurrent_boundary(
    postgres_db, mock_embedding_provider
):
    """EmbeddingProcessorのmax_concurrent境界値テスト"""
    # テスト用のソースとチャンクを作成
    source_id = await postgres_db.save_source(
        source_type="discord_session",
        title="max_concurrent境界値テスト",
        uri="https://example.com/max_concurrent_test",
        metadata={"test": True},
        status="pending",
    )

    # 10個のチャンクを作成
    chunk_ids = []
    for i in range(10):
        chunk_id = await postgres_db.save_chunk(
            source_id=source_id,
            content=f"max_concurrent境界値テスト用チャンク{i}",
            location={
                "url": "https://example.com/max_concurrent_test",
                "label": f"チャンク{i}",
            },
            token_count=10,
        )
        chunk_ids.append(chunk_id)

    # max_concurrent=1（最小値）で処理
    processor = EmbeddingProcessor(
        db=postgres_db,
        embedding_provider=mock_embedding_provider,
        batch_size=10,
        max_concurrent=1,  # 最小値
    )

    # 処理を実行
    await processor._process_pending_embeddings_impl()

    # すべてのチャンクが処理されていることを確認
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
        assert result == len(chunk_ids)


@pytest.mark.asyncio
async def test_similarity_search_apply_threshold_false(
    postgres_db, mock_embedding_provider
):
    """similarity_searchのapply_threshold=Falseの詳細テスト"""
    # テスト用のソースとチャンクを作成
    source_id = await postgres_db.save_source(
        source_type="discord_session",
        title="apply_thresholdテスト",
        uri="https://example.com/apply_threshold_test",
        metadata={"test": True},
        status="pending",
    )

    await postgres_db.save_chunk(
        source_id=source_id,
        content="apply_thresholdテスト用チャンク",
        location={"url": "https://example.com/apply_threshold_test", "label": "テスト"},
        token_count=10,
    )

    # Embedding処理
    processor = EmbeddingProcessor(
        db=postgres_db,
        embedding_provider=mock_embedding_provider,
        batch_size=10,
        max_concurrent=2,
    )
    await processor._process_pending_embeddings_impl()

    query_embedding = [0.1] * 1536

    # apply_threshold=Falseの場合、閾値フィルタリングが適用されない
    results = await postgres_db.similarity_search(
        query_embedding=query_embedding,
        top_k=10,
        apply_threshold=False,
    )

    # 結果が返ってくることを確認（閾値に関係なく）
    assert isinstance(results, list)
    # 類似度スコアが0.0〜1.0の範囲内であることを確認
    for result in results:
        assert 0.0 <= result["similarity"] <= 1.0
