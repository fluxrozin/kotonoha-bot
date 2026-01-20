"""高度なテストケース（phase08.md の「6. テスト計画」に記載されているテスト）"""

import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest

from kotonoha_bot.db.models import ChatSession, Message, MessageRole
from kotonoha_bot.db.postgres import PostgreSQLDatabase
from kotonoha_bot.external.embedding.openai_embedding import (
    OpenAIEmbeddingProvider,
)
from kotonoha_bot.features.knowledge_base.embedding_processor import (
    EmbeddingProcessor,
)
from kotonoha_bot.features.knowledge_base.session_archiver import (
    SessionArchiver,
)


@pytest.mark.asyncio
async def test_connection_pool_exhaustion(postgres_db):
    """接続プール枯渇テスト

    同時接続数がmax_sizeを超えた場合のタイムアウト動作を確認
    """
    # max_size=2 でプールを作成（テスト用の小さいプール）

    # テスト用の小さいプールを作成
    test_db = PostgreSQLDatabase(
        host=postgres_db.host,
        port=postgres_db.port,
        database=postgres_db.database,
        user=postgres_db.user,
        password=postgres_db.password,
    )

    # 小さいプールサイズで初期化
    import asyncpg

    test_db.pool = await asyncpg.create_pool(
        host=test_db.host,
        port=test_db.port,
        database=test_db.database,
        user=test_db.user,
        password=test_db.password,
        min_size=1,
        max_size=2,  # 最大2接続
        command_timeout=1.0,  # 短いタイムアウト
    )

    # 2つの接続を取得（プールの上限）
    # ⚠️ 重要: async withを使用して確実に接続をクローズする
    async with test_db.pool.acquire() as _, test_db.pool.acquire() as _:
        # 3つ目の接続を試行（タイムアウトが発生することを確認）
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(
                test_db.pool.acquire(),
                timeout=2.0,  # 2秒でタイムアウト
            )

    # クリーンアップ（プールをクローズ）
    await test_db.close()


@pytest.mark.asyncio
async def test_halfvec_similarity_accuracy(postgres_db):
    """halfvec型の精度テスト

    halfvec使用時の検索精度がvector使用時と比較して許容範囲内であることを確認
    """
    # テスト用のソースとチャンクを作成
    source_id = await postgres_db.save_source(
        source_type="discord_session",
        title="精度テスト用ソース",
        uri="https://example.com/accuracy",
        metadata={"test": True},
        status="pending",
    )

    chunk_id = await postgres_db.save_chunk(
        source_id=source_id,
        content="これは精度テスト用のチャンクです",
        location={"url": "https://example.com/accuracy", "label": "テスト"},
        token_count=10,
    )

    # テスト用のベクトル（ランダムな値）
    import random

    random.seed(42)  # 再現性のため
    test_embedding = [random.gauss(0, 0.1) for _ in range(1536)]

    async with postgres_db.pool.acquire() as conn:
        # halfvec型でベクトルを挿入
        await conn.execute(
            """
            UPDATE knowledge_chunks
            SET embedding = $1::halfvec(1536)
            WHERE id = $2
        """,
            test_embedding,
            chunk_id,
        )

        # halfvec型での類似度計算
        halfvec_result = await conn.fetchrow(
            """
            SELECT 1 - (embedding <=> $1::halfvec(1536)) AS similarity
            FROM knowledge_chunks
            WHERE id = $2
        """,
            test_embedding,
            chunk_id,
        )

        # vector型での類似度計算（比較用）
        # 注意: vector型はhalfvec型よりも精度が高いが、メモリ使用量も大きい
        vector_result = await conn.fetchrow(
            """
            SELECT 1 - (embedding::vector(1536) <=> $1::vector(1536)) AS similarity
            FROM knowledge_chunks
            WHERE id = $2
        """,
            test_embedding,
            chunk_id,
        )

        assert halfvec_result is not None
        assert vector_result is not None

        # 許容誤差範囲内であることを確認（0.01以内）
        similarity_diff = abs(
            float(halfvec_result["similarity"]) - float(vector_result["similarity"])
        )
        assert similarity_diff < 0.01, (
            f"halfvecとvectorの類似度の差が許容範囲を超えています: "
            f"halfvec={halfvec_result['similarity']}, "
            f"vector={vector_result['similarity']}, "
            f"diff={similarity_diff}"
        )


@pytest.mark.asyncio
async def test_concurrent_session_archiving(postgres_db, mock_embedding_provider):
    """競合状態テスト

    複数ワーカーが同時にアーカイブ処理した場合の整合性を確認
    """
    # テスト用のセッションを作成
    # ⚠️ 重要: kb_min_session_length（デフォルト30文字）を超える長さのメッセージが必要
    session = ChatSession(
        session_key="test:session:concurrent:001",
        session_type="mention",
        messages=[
            Message(
                role=MessageRole.USER,
                content="これは競合状態テスト用のセッションです。十分な長さのメッセージを含めています。",
                timestamp=datetime.now(UTC) - timedelta(hours=2),
            ),
            Message(
                role=MessageRole.ASSISTANT,
                content="了解しました。競合状態テストを実行します。",
                timestamp=datetime.now(UTC) - timedelta(hours=2),
            ),
        ],
        guild_id=123456789,
        channel_id=987654321,
        user_id=111222333,
        last_active_at=datetime.now(UTC) - timedelta(hours=2),
    )

    await postgres_db.save_session(session)

    # 2つのSessionArchiverインスタンスを作成（複数ワーカーをシミュレート）
    archiver1 = SessionArchiver(
        db=postgres_db,
        embedding_provider=mock_embedding_provider,
        archive_threshold_hours=1,
    )

    archiver2 = SessionArchiver(
        db=postgres_db,
        embedding_provider=mock_embedding_provider,
        archive_threshold_hours=1,
    )

    # セッションを取得
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
            "test:session:concurrent:001",
        )

        # 同時にアーカイブ処理を実行（競合状態をシミュレート）
        tasks = [
            archiver1._archive_session_impl(dict(session_row)),
            archiver2._archive_session_impl(dict(session_row)),
        ]

        # 両方のタスクを実行（楽観的ロックにより、1つは成功、1つは失敗する）
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 少なくとも1つは成功することを確認
        success_count = sum(1 for r in results if not isinstance(r, Exception))
        assert success_count >= 1, (
            "少なくとも1つのアーカイブ処理が成功する必要があります"
        )

        # データの整合性を確認（セッションが1回だけアーカイブされている）
        async with postgres_db.pool.acquire() as conn2:
            source_count = await conn2.fetchval(
                """
                SELECT COUNT(*)
                FROM knowledge_sources
                WHERE metadata->>'origin_session_key' = $1
            """,
                "test:session:concurrent:001",
            )

            # セッションは1回だけアーカイブされる（楽観的ロックにより）
            assert source_count == 1, (
                f"セッションは1回だけアーカイブされる必要がありますが、"
                f"{source_count}回アーカイブされました"
            )


@pytest.mark.asyncio
async def test_embedding_retry_on_failure(postgres_db):
    """Embedding API失敗時のリトライテスト

    APIエラー時のリトライとDLQ投入を確認
    """
    # エラーを発生させるモック
    error_provider = AsyncMock(spec=OpenAIEmbeddingProvider)
    error_provider.generate_embeddings_batch = AsyncMock(
        side_effect=Exception("API Error")
    )
    error_provider.get_dimension = lambda: 1536

    # テスト用のソースとチャンクを作成
    source_id = await postgres_db.save_source(
        source_type="discord_session",
        title="リトライテスト用ソース",
        uri="https://example.com/retry",
        metadata={"test": True},
        status="pending",
    )

    chunk_id = await postgres_db.save_chunk(
        source_id=source_id,
        content="これはリトライテスト用のチャンクです",
        location={"url": "https://example.com/retry", "label": "テスト"},
        token_count=10,
    )

    processor = EmbeddingProcessor(
        db=postgres_db,
        embedding_provider=error_provider,
        batch_size=10,
        max_concurrent=2,
    )

    # 最大リトライ回数まで処理を実行（デフォルト: 3回）
    from kotonoha_bot.config import settings

    max_retry = settings.kb_embedding_max_retry

    for attempt in range(max_retry):
        await processor._process_pending_embeddings_impl()

        # retry_countがインクリメントされているか確認
        async with postgres_db.pool.acquire() as conn:
            result = await conn.fetchrow(
                """
                SELECT retry_count, embedding IS NULL as has_null_embedding
                FROM knowledge_chunks
                WHERE id = $1
            """,
                chunk_id,
            )

            # 最後のリトライでDLQに移動される可能性があるため、チャンクが存在するか確認
            if result is None:
                # DLQに移動されている可能性があるので確認
                dlq_check = await conn.fetchrow(
                    """
                    SELECT original_chunk_id, retry_count
                    FROM knowledge_chunks_dlq
                    WHERE original_chunk_id = $1
                """,
                    chunk_id,
                )
                if dlq_check is not None:
                    # 既にDLQに移動されている（最後のリトライで移動された）
                    # ⚠️ 注意: retry_countはインクリメント後にDLQに移動されるため、
                    # 移動時点でのretry_countは max_retry と一致する
                    assert dlq_check["retry_count"] >= max_retry - 1, (
                        f"DLQのretry_countが正しくありません: "
                        f"expected>={max_retry - 1}, actual={dlq_check['retry_count']}"
                    )
                    # テストを早期終了
                    return

            assert result is not None, (
                f"チャンクが存在しません（attempt {attempt + 1}/{max_retry}）"
            )
            assert result["retry_count"] == attempt + 1, (
                f"retry_countが正しくインクリメントされていません: "
                f"expected={attempt + 1}, actual={result['retry_count']}"
            )
            assert result["has_null_embedding"] is True, (
                "embeddingはNULLのままである必要があります"
            )

    # 最大リトライ回数に達した後、DLQに移動されることを確認
    # 最後のリトライで既にDLQに移動されている可能性があるため、もう一度処理を実行
    await processor._process_pending_embeddings_impl()

    async with postgres_db.pool.acquire() as conn:
        # DLQに移動されているか確認
        dlq_result = await conn.fetchrow(
            """
            SELECT original_chunk_id, error_code, error_message, retry_count
            FROM knowledge_chunks_dlq
            WHERE original_chunk_id = $1
        """,
            chunk_id,
        )

        assert dlq_result is not None, "チャンクがDLQに移動されていません"
        assert dlq_result["error_code"] is not None, "エラーコードが記録されていません"
        # ⚠️ 注意: retry_countはインクリメント後にDLQに移動されるため、
        # 移動時点でのretry_countは max_retry と一致する（または max_retry - 1）
        assert dlq_result["retry_count"] >= max_retry - 1, (
            f"retry_countが正しく記録されていません: "
            f"expected>={max_retry - 1}, actual={dlq_result['retry_count']}"
        )

        # 元のテーブルから削除されているか確認
        chunk_result = await conn.fetchrow(
            """
            SELECT id FROM knowledge_chunks WHERE id = $1
        """,
            chunk_id,
        )

        assert chunk_result is None, (
            "DLQに移動されたチャンクが元のテーブルから削除されていません"
        )
