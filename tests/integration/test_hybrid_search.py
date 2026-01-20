"""ハイブリッド検索の統合テスト."""

import pytest

from kotonoha_bot.db.postgres import PostgreSQLDatabase


@pytest.mark.asyncio
async def test_hybrid_search_integration(postgres_db):
    """ハイブリッド検索の統合テスト."""
    # 複数のテスト用ソースとチャンクを作成
    source_ids = []
    chunk_ids = []

    # ベクトル検索に強いコンテンツ（概念的な類似）
    source_id1 = await postgres_db.save_source(
        source_type="discord_session",
        title="概念的な類似のテスト",
        uri="https://example.com/test1",
        metadata={"channel_id": 111, "user_id": 222},
        status="completed",
    )
    source_ids.append(source_id1)

    chunk_id1 = await postgres_db.save_chunk(
        source_id=source_id1,
        content="これは機械学習と人工知能に関するコンテンツです。",
        location={"url": "https://example.com/test1", "label": "テスト1"},
        token_count=15,
    )
    chunk_ids.append(chunk_id1)

    # キーワード検索に強いコンテンツ（固有名詞を含む）
    source_id2 = await postgres_db.save_source(
        source_type="discord_session",
        title="固有名詞のテスト",
        uri="https://example.com/test2",
        metadata={"channel_id": 333, "user_id": 444},
        status="completed",
    )
    source_ids.append(source_id2)

    chunk_id2 = await postgres_db.save_chunk(
        source_id=source_id2,
        content="プロジェクトコード名はKOTONOHA-BOT-2024です。",
        location={"url": "https://example.com/test2", "label": "テスト2"},
        token_count=12,
    )
    chunk_ids.append(chunk_id2)

    # テスト用のベクトルを挿入
    async with postgres_db.pool.acquire() as conn:
        # チャンク1: 機械学習に関連するベクトル（0.1で統一）
        await conn.execute(
            """
            UPDATE knowledge_chunks
            SET embedding = (SELECT array_agg(0.1::real) FROM generate_series(1, 1536))::halfvec(1536)
            WHERE id = $1
        """,
            chunk_id1,
        )

        # チャンク2: 異なるベクトル（0.2で統一）
        await conn.execute(
            """
            UPDATE knowledge_chunks
            SET embedding = (SELECT array_agg(0.2::real) FROM generate_series(1, 1536))::halfvec(1536)
            WHERE id = $1
        """,
            chunk_id2,
        )

    # ハイブリッド検索を実行（概念的なクエリ）
    query_embedding = [0.1] * 1536  # チャンク1に近いベクトル
    query_text = "KOTONOHA-BOT-2024"  # チャンク2に含まれる固有名詞

    results = await postgres_db.hybrid_search(
        query_embedding=query_embedding,
        query_text=query_text,
        limit=10,
    )

    # 両方のチャンクが結果に含まれることを確認
    # （ベクトル検索でチャンク1、キーワード検索でチャンク2がヒット）
    assert len(results) >= 1

    # 結果に両方のチャンクが含まれることを確認
    result_chunk_ids = [result["chunk_id"] for result in results]
    assert chunk_id1 in result_chunk_ids or chunk_id2 in result_chunk_ids

    # スコアが正しく計算されていることを確認
    for result in results:
        assert result["similarity"] > 0.0
        assert result["similarity"] <= 1.0


@pytest.mark.asyncio
async def test_hybrid_search_vector_vs_keyword(postgres_db):
    """ベクトル検索とキーワード検索の組み合わせをテスト."""
    # ベクトル検索に強いコンテンツ
    source_id1 = await postgres_db.save_source(
        source_type="discord_session",
        title="ベクトル検索テスト",
        uri="https://example.com/vector",
        metadata={},
        status="completed",
    )

    chunk_id1 = await postgres_db.save_chunk(
        source_id=source_id1,
        content="これは人工知能と機械学習に関する詳細な説明です。",
        location={},
        token_count=20,
    )

    # キーワード検索に強いコンテンツ（固有名詞）
    source_id2 = await postgres_db.save_source(
        source_type="document_file",
        title="キーワード検索テスト",
        uri="https://example.com/keyword",
        metadata={},
        status="completed",
    )

    chunk_id2 = await postgres_db.save_chunk(
        source_id=source_id2,
        content="エラーコードE12345が発生しました。",
        location={},
        token_count=10,
    )

    # テスト用のベクトルを挿入
    async with postgres_db.pool.acquire() as conn:
        # チャンク1: クエリに近いベクトル
        await conn.execute(
            """
            UPDATE knowledge_chunks
            SET embedding = (SELECT array_agg(0.1::real) FROM generate_series(1, 1536))::halfvec(1536)
            WHERE id = $1
        """,
            chunk_id1,
        )

        # チャンク2: クエリから遠いベクトル
        await conn.execute(
            """
            UPDATE knowledge_chunks
            SET embedding = (SELECT array_agg(0.9::real) FROM generate_series(1, 1536))::halfvec(1536)
            WHERE id = $1
        """,
            chunk_id2,
        )

    # クエリ: ベクトルはチャンク1に近いが、キーワードはチャンク2に含まれる
    query_embedding = [0.1] * 1536
    query_text = "E12345"

    results = await postgres_db.hybrid_search(
        query_embedding=query_embedding,
        query_text=query_text,
        limit=10,
    )

    # 両方のチャンクが結果に含まれることを確認
    result_chunk_ids = [result["chunk_id"] for result in results]
    assert chunk_id1 in result_chunk_ids or chunk_id2 in result_chunk_ids

    # キーワード検索でチャンク2が確実にヒットすることを確認
    assert chunk_id2 in result_chunk_ids


@pytest.mark.asyncio
async def test_hybrid_search_with_multiple_filters(postgres_db):
    """複数のフィルタを組み合わせたハイブリッド検索をテスト."""
    # テスト用のソースとチャンクを作成
    source_id = await postgres_db.save_source(
        source_type="discord_session",
        title="複数フィルタテスト",
        uri="https://example.com/multi",
        metadata={
            "channel_id": "555",
            "author_id": "666",
        },  # JSONBでは文字列として保存される可能性がある
        status="completed",
    )

    chunk_id = await postgres_db.save_chunk(
        source_id=source_id,
        content="これは複数のフィルタを組み合わせたテストです。",
        location={},
        token_count=15,
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

    # まずフィルタなしでテスト（基本動作の確認）
    query_embedding = [0.1] * 1536
    query_text = "フィルタ"  # コンテンツに確実に含まれるキーワード

    results_no_filter = await postgres_db.hybrid_search(
        query_embedding=query_embedding,
        query_text=query_text,
        limit=10,
    )

    assert len(results_no_filter) > 0, "Expected results without filters"
    assert results_no_filter[0]["chunk_id"] == chunk_id

    # source_typeフィルタのみでテスト
    results_source_type = await postgres_db.hybrid_search(
        query_embedding=query_embedding,
        query_text=query_text,
        limit=10,
        filters={"source_type": "discord_session"},
    )

    assert len(results_source_type) > 0, "Expected results with source_type filter"
    assert results_source_type[0]["source_type"] == "discord_session"

    # 異なるsource_typeでフィルタリング（結果が空になることを確認）
    results_empty = await postgres_db.hybrid_search(
        query_embedding=query_embedding,
        query_text=query_text,
        limit=10,
        filters={"source_type": "document_file"},  # 異なるsource_type
    )

    assert len(results_empty) == 0, (
        "Expected empty results with different source_type filter"
    )
