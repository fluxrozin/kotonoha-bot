"""知識ベース保存の統合テスト

知識ソースの作成→チャンクの作成→ステータス更新の一連の流れを確認
"""

import pytest


@pytest.mark.asyncio
async def test_knowledge_base_storage_flow(postgres_db):
    """知識ベース保存の統合テスト

    知識ソースの作成→チャンクの作成→ステータス更新の一連の流れを確認
    """
    # 1. 知識ソースの作成
    source_id = await postgres_db.save_source(
        source_type="discord_session",
        title="統合テスト用ソース",
        uri="https://example.com/integration",
        metadata={"test": True, "integration": True},
        status="pending",
    )

    assert source_id is not None

    # 2. 知識チャンクの作成（複数）
    chunk_ids = []
    for i in range(3):
        chunk_id = await postgres_db.save_chunk(
            source_id=source_id,
            content=f"これは統合テスト用のチャンク{i}です",
            location={
                "url": "https://example.com/integration",
                "label": f"チャンク{i}",
            },
            token_count=20,
        )
        chunk_ids.append(chunk_id)

    assert len(chunk_ids) == 3

    # 3. ソースとチャンクの関連を確認
    async with postgres_db.pool.acquire() as conn:
        result = await conn.fetchrow(
            """
            SELECT
                s.id as source_id,
                s.title,
                s.status,
                COUNT(c.id) as chunk_count
            FROM knowledge_sources s
            LEFT JOIN knowledge_chunks c ON s.id = c.source_id
            WHERE s.id = $1
            GROUP BY s.id, s.title, s.status
        """,
            source_id,
        )

        assert result is not None
        assert result["chunk_count"] == 3
        assert result["status"] == "pending"

    # 4. ソースのステータスを更新
    async with postgres_db.pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE knowledge_sources
            SET status = 'completed'
            WHERE id = $1
        """,
            source_id,
        )

    # 5. 更新後のステータスを確認
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
        assert result["status"] == "completed"


@pytest.mark.asyncio
async def test_knowledge_base_source_chunk_relationship(postgres_db):
    """知識ソースとチャンクの関連性テスト

    外部キー制約が正しく動作していることを確認
    """
    # ソースを作成
    source_id = await postgres_db.save_source(
        source_type="document_file",
        title="関連性テスト用ソース",
        uri="https://example.com/relationship",
        metadata={"test": True},
        status="pending",
    )

    # チャンクを作成
    chunk_id = await postgres_db.save_chunk(
        source_id=source_id,
        content="関連性テスト用のチャンク",
        location={"url": "https://example.com/relationship", "label": "テスト"},
        token_count=10,
    )

    # ソースとチャンクの関連を確認
    async with postgres_db.pool.acquire() as conn:
        result = await conn.fetchrow(
            """
            SELECT
                c.id as chunk_id,
                c.source_id,
                s.title as source_title,
                s.type as source_type
            FROM knowledge_chunks c
            JOIN knowledge_sources s ON c.source_id = s.id
            WHERE c.id = $1
        """,
            chunk_id,
        )

        assert result is not None
        assert result["source_id"] == source_id
        assert result["source_title"] == "関連性テスト用ソース"
        assert result["source_type"] == "document_file"
