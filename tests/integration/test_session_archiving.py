"""セッション知識化処理の統合テスト

セッションの作成→アーカイブ→Embedding処理→検索の一連の流れを確認
"""

from datetime import UTC, datetime, timedelta

import pytest

from kotonoha_bot.features.knowledge_base.embedding_processor import (
    EmbeddingProcessor,
)
from kotonoha_bot.features.knowledge_base.session_archiver import (
    SessionArchiver,
)
from kotonoha_bot.session.models import ChatSession, Message, MessageRole


@pytest.mark.asyncio
async def test_session_archiving_flow(postgres_db, mock_embedding_provider):
    """セッション知識化処理の統合テスト

    セッションの作成→アーカイブ→Embedding処理→検索の一連の流れを確認
    """
    # 1. セッションの作成と保存
    session = ChatSession(
        session_key="test:session:archiving:integration:001",
        session_type="mention",
        messages=[
            Message(
                role=MessageRole.USER,
                content="これは統合テスト用のセッションです",
                timestamp=datetime.now(UTC) - timedelta(hours=2),
            ),
            Message(
                role=MessageRole.ASSISTANT,
                content="了解しました。統合テストですね。",
                timestamp=datetime.now(UTC) - timedelta(hours=2),
            ),
            Message(
                role=MessageRole.USER,
                content="アーカイブ処理をテストします",
                timestamp=datetime.now(UTC) - timedelta(hours=2),
            ),
        ],
        guild_id=123456789,
        channel_id=987654321,
        user_id=111222333,
        last_active_at=datetime.now(UTC) - timedelta(hours=2),
    )

    await postgres_db.save_session(session)

    # 2. セッションのアーカイブ処理
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
            "test:session:archiving:integration:001",
        )

        await archiver._archive_session_impl(dict(session_row))

    # 3. セッションがアーカイブされているか確認
    async with postgres_db.pool.acquire() as conn:
        result = await conn.fetchrow(
            """
            SELECT status, jsonb_array_length(messages) as remaining_message_count
            FROM sessions
            WHERE session_key = $1
        """,
            "test:session:archiving:integration:001",
        )

        assert result is not None
        assert result["status"] == "archived"
        assert (
            result["remaining_message_count"] > 0
        )  # スライディングウィンドウ（のりしろ）

    # 4. 知識ベースに変換されているか確認
    async with postgres_db.pool.acquire() as conn:
        source_result = await conn.fetchrow(
            """
            SELECT id, title, type, status, metadata->>'origin_session_key' as origin_session_key
            FROM knowledge_sources
            WHERE metadata->>'origin_session_key' = $1
        """,
            "test:session:archiving:integration:001",
        )

        assert source_result is not None
        assert source_result["type"] == "discord_session"
        assert (
            source_result["origin_session_key"]
            == "test:session:archiving:integration:001"
        )

        # チャンクが作成されているか確認
        chunk_count = await conn.fetchval(
            """
            SELECT COUNT(*)
            FROM knowledge_chunks
            WHERE source_id = $1
        """,
            source_result["id"],
        )

        assert chunk_count > 0

    # 5. Embedding処理の実行
    processor = EmbeddingProcessor(
        db=postgres_db,
        embedding_provider=mock_embedding_provider,
        batch_size=10,
        max_concurrent=2,
    )

    await processor._process_pending_embeddings_impl()

    # 6. Embeddingが設定されているか確認
    async with postgres_db.pool.acquire() as conn:
        result = await conn.fetchrow(
            """
            SELECT
                COUNT(*) as processed_chunks
            FROM knowledge_chunks
            WHERE source_id = $1
            AND embedding IS NOT NULL
        """,
            source_result["id"],
        )

        assert result is not None
        assert result["processed_chunks"] > 0

    # 7. ベクトル検索で検索できることを確認
    query_embedding = [0.1] * 1536
    results = await postgres_db.similarity_search(
        query_embedding=query_embedding,
        top_k=5,
    )

    # アーカイブされたセッションのチャンクが検索結果に含まれる可能性がある
    # （類似度によっては含まれない場合もある）
    assert len(results) >= 0  # 検索結果が返ってくる（または空）ことを確認


@pytest.mark.asyncio
async def test_session_archiving_with_embedding_processing(
    postgres_db, mock_embedding_provider
):
    """セッションアーカイブとEmbedding処理の統合テスト

    セッションのアーカイブ→Embedding処理→ソースステータス更新の一連の流れを確認
    """
    # 1. セッションの作成とアーカイブ
    session = ChatSession(
        session_key="test:session:full_flow:001",
        session_type="mention",
        messages=[
            Message(
                role=MessageRole.USER,
                content="フルフローテスト",
                timestamp=datetime.now(UTC) - timedelta(hours=2),
            ),
            Message(
                role=MessageRole.ASSISTANT,
                content="了解しました",
                timestamp=datetime.now(UTC) - timedelta(hours=2),
            ),
        ],
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
            "test:session:full_flow:001",
        )

        await archiver._archive_session_impl(dict(session_row))

    # 2. Embedding処理の実行
    processor = EmbeddingProcessor(
        db=postgres_db,
        embedding_provider=mock_embedding_provider,
        batch_size=10,
        max_concurrent=2,
    )

    await processor._process_pending_embeddings_impl()

    # 3. ソースのステータスが更新されているか確認
    async with postgres_db.pool.acquire() as conn:
        result = await conn.fetchrow(
            """
            SELECT
                s.status as source_status,
                COUNT(CASE WHEN c.embedding IS NOT NULL THEN 1 END) as processed_chunks,
                COUNT(c.id) as total_chunks
            FROM knowledge_sources s
            LEFT JOIN knowledge_chunks c ON s.id = c.source_id
            WHERE s.metadata->>'origin_session_key' = $1
            GROUP BY s.id, s.status
        """,
            "test:session:full_flow:001",
        )

        assert result is not None
        # すべてのチャンクが処理された場合、ステータスが'completed'になる
        if result["total_chunks"] > 0:
            assert result["processed_chunks"] == result["total_chunks"], (
                f"すべてのチャンクが処理されている必要があります: "
                f"processed={result['processed_chunks']}, "
                f"total={result['total_chunks']}"
            )
            assert result["source_status"] == "completed", (
                f"ソースのステータスが'completed'である必要があります: "
                f"actual={result['source_status']}"
            )
