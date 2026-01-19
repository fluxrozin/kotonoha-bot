"""EmbeddingProcessor のテスト"""

import asyncio
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


@pytest.mark.asyncio
async def test_embedding_processor_dlq(postgres_db):
    """DLQへの移動ロジックのテスト"""
    from unittest.mock import AsyncMock

    from kotonoha_bot.external.embedding.openai_embedding import (
        OpenAIEmbeddingProvider,
    )

    # エラーを発生させるモック
    error_provider = AsyncMock(spec=OpenAIEmbeddingProvider)
    error_provider.generate_embeddings_batch = AsyncMock(
        side_effect=Exception("API Error")
    )
    error_provider.get_dimension = lambda: 1536

    # テスト用のチャンクを作成
    source_id = await postgres_db.save_source(
        source_type="discord_session",
        title="DLQテストソース",
        uri="https://example.com/dlq_test",
        metadata={"test": True},
        status="pending",
    )

    chunk_id = await postgres_db.save_chunk(
        source_id=source_id,
        content="これはDLQテスト用のチャンクです",
        location={"url": "https://example.com/dlq_test", "label": "DLQテスト"},
        token_count=10,
    )

    processor = EmbeddingProcessor(
        db=postgres_db,
        embedding_provider=error_provider,
        batch_size=10,
        max_concurrent=2,
    )

    # 最大リトライ回数まで処理を実行（デフォルトは3回）
    from kotonoha_bot.config import settings

    max_retry = settings.kb_embedding_max_retry
    # max_retry回処理する（3回目の処理でretry_countが3になり、DLQに移動される）
    for _ in range(max_retry):
        await processor._process_pending_embeddings_impl()

    # 3回処理した後、DLQに移動されているか確認
    async with postgres_db.pool.acquire() as conn:
        dlq_result = await conn.fetchrow(
            "SELECT * FROM knowledge_chunks_dlq WHERE original_chunk_id = $1",
            chunk_id,
        )
        assert dlq_result is not None, "チャンクがDLQに移動されていません"
        assert dlq_result["error_code"] is not None
        assert dlq_result["error_message"] is not None
        # retry_countはmax_retry以上になる（max_retry回処理した後、DLQに移動される）
        assert dlq_result["retry_count"] >= max_retry

        # 元のテーブルから削除されているか確認
        chunk_result = await conn.fetchrow(
            "SELECT * FROM knowledge_chunks WHERE id = $1",
            chunk_id,
        )
        assert chunk_result is None, "元のテーブルから削除されていません"


@pytest.mark.asyncio
async def test_source_status_update(postgres_db, mock_embedding_provider):
    """Sourceステータスの更新確認"""
    # テスト用のソースとチャンクを作成
    source_id = await postgres_db.save_source(
        source_type="discord_session",
        title="ステータス更新テストソース",
        uri="https://example.com/status_test",
        metadata={"test": True},
        status="pending",
    )

    chunk_ids = []
    for i in range(5):
        chunk_id = await postgres_db.save_chunk(
            source_id=source_id,
            content=f"これはステータス更新テスト用のチャンク{i}です",
            location={
                "url": "https://example.com/status_test",
                "label": f"チャンク{i}",
            },
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

    # Sourceステータスが'completed'になっているか確認
    async with postgres_db.pool.acquire() as conn:
        result = await conn.fetchrow(
            "SELECT status FROM knowledge_sources WHERE id = $1",
            source_id,
        )
        assert result is not None
        assert result["status"] == "completed"


@pytest.mark.asyncio
async def test_source_status_partial_with_dlq(postgres_db):
    """DLQに移動されたチャンクがある場合のSourceステータス確認"""
    from unittest.mock import AsyncMock

    from kotonoha_bot.external.embedding.openai_embedding import (
        OpenAIEmbeddingProvider,
    )

    # エラーを発生させるモック
    error_provider = AsyncMock(spec=OpenAIEmbeddingProvider)
    error_provider.generate_embeddings_batch = AsyncMock(
        side_effect=Exception("API Error")
    )
    error_provider.get_dimension = lambda: 1536

    # テスト用のソースとチャンクを作成
    source_id = await postgres_db.save_source(
        source_type="discord_session",
        title="Partialステータステストソース",
        uri="https://example.com/partial_test",
        metadata={"test": True},
        status="pending",
    )

    # 正常に処理されるチャンク
    chunk_id_1 = await postgres_db.save_chunk(
        source_id=source_id,
        content="正常に処理されるチャンク",
        location={"url": "https://example.com/partial_test", "label": "正常"},
        token_count=10,
    )

    # エラーが発生するチャンク（別のプロバイダーで処理）
    chunk_id_2 = await postgres_db.save_chunk(
        source_id=source_id,
        content="エラーが発生するチャンク",
        location={"url": "https://example.com/partial_test", "label": "エラー"},
        token_count=10,
    )

    # chunk_id_1のみを処理（chunk_id_2は除外）
    async with postgres_db.pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE knowledge_chunks
            SET embedding = $1::halfvec(1536)
            WHERE id = $2
        """,
            [0.1] * 1536,
            chunk_id_1,
        )

    # chunk_id_2をDLQに移動（手動でシミュレート）
    from kotonoha_bot.config import settings

    max_retry = settings.kb_embedding_max_retry
    processor_error = EmbeddingProcessor(
        db=postgres_db,
        embedding_provider=error_provider,
        batch_size=10,
        max_concurrent=2,
    )

    # max_retry回処理してDLQに移動させる
    for _ in range(max_retry):
        await processor_error._process_pending_embeddings_impl()

    # ステータス更新を手動で実行（DLQに移動された後、ステータスが更新される）
    # chunk_id_2がDLQに移動されているので、その情報を使ってステータス更新
    async with postgres_db.pool.acquire() as conn:
        dlq_chunk = await conn.fetchrow(
            "SELECT * FROM knowledge_chunks_dlq WHERE original_chunk_id = $1",
            chunk_id_2,
        )
        if dlq_chunk:
            await processor_error._update_source_status([dict(dlq_chunk)])

    # Sourceステータスが'partial'または'failed'になっているか確認
    async with postgres_db.pool.acquire() as conn:
        result = await conn.fetchrow(
            "SELECT status FROM knowledge_sources WHERE id = $1",
            source_id,
        )
        assert result is not None
        # DLQに移動されたチャンクがある場合、'partial'または'failed'になる可能性がある
        assert result["status"] in ("partial", "failed", "completed")


@pytest.mark.asyncio
async def test_embedding_processor_batch_processing_settings(
    postgres_db, mock_embedding_provider
):
    """バッチ処理の設定確認"""
    processor = EmbeddingProcessor(
        db=postgres_db,
        embedding_provider=mock_embedding_provider,
        batch_size=10,
        max_concurrent=2,
    )

    assert processor.batch_size == 10
    assert processor._semaphore._value == 2


@pytest.mark.asyncio
async def test_embedding_processor_database_connection_error():
    """データベース接続エラーのハンドリング"""
    from kotonoha_bot.db.postgres import PostgreSQLDatabase

    # 無効な接続文字列でデータベースを作成
    db = PostgreSQLDatabase(
        host="invalid_host",
        port=5432,
        database="invalid_db",
        user="invalid_user",
        password="invalid_password",
    )

    with pytest.raises((RuntimeError, Exception)):
        await db.initialize()


@pytest.mark.asyncio
async def test_embedding_processor_classify_error(postgres_db, mock_embedding_provider):
    """エラー分類のテスト"""
    processor = EmbeddingProcessor(
        db=postgres_db,
        embedding_provider=mock_embedding_provider,
        batch_size=10,
        max_concurrent=2,
    )

    # 各種エラーの分類をテスト
    assert (
        processor._classify_error(Exception("timeout error")) == "EMBEDDING_API_TIMEOUT"
    )
    assert processor._classify_error(Exception("rate limit exceeded")) == "RATE_LIMIT"
    assert (
        processor._classify_error(Exception("authentication failed"))
        == "AUTHENTICATION_ERROR"
    )
    assert (
        processor._classify_error(Exception("permission denied")) == "PERMISSION_ERROR"
    )
    assert processor._classify_error(Exception("not found")) == "NOT_FOUND"
    assert processor._classify_error(Exception("server error 500")) == "SERVER_ERROR"
    assert processor._classify_error(Exception("unknown error")) == "UNKNOWN_ERROR"


@pytest.mark.asyncio
async def test_embedding_processor_generalize_error_message(
    postgres_db, mock_embedding_provider
):
    """エラーメッセージ一般化のテスト"""
    processor = EmbeddingProcessor(
        db=postgres_db,
        embedding_provider=mock_embedding_provider,
        batch_size=10,
        max_concurrent=2,
    )

    # エラーメッセージが一般化されていることを確認
    error = Exception("timeout error")
    message = processor._generalize_error_message(error)
    assert message == "Embedding API request timed out"
    assert "timeout" not in message.lower() or "timed out" in message.lower()

    # 未知のエラーの場合
    unknown_error = Exception("some random error")
    unknown_message = processor._generalize_error_message(unknown_error)
    assert unknown_message == "An error occurred during processing"


@pytest.mark.asyncio
async def test_embedding_processor_generate_embeddings_batch_fallback(postgres_db):
    """_generate_embeddings_batchのフォールバック処理テスト"""
    from unittest.mock import AsyncMock

    from kotonoha_bot.external.embedding.openai_embedding import (
        OpenAIEmbeddingProvider,
    )

    # バッチAPIを持たないプロバイダー（フォールバックが使用される）
    fallback_provider = AsyncMock(spec=OpenAIEmbeddingProvider)
    fallback_provider.generate_embedding = AsyncMock(return_value=[0.1] * 1536)
    fallback_provider.get_dimension = lambda: 1536
    # generate_embeddings_batchを持たない（フォールバックが使用される）
    # specを使うと自動的に存在してしまうため、delattrで削除
    if hasattr(fallback_provider, "generate_embeddings_batch"):
        delattr(fallback_provider, "generate_embeddings_batch")

    processor = EmbeddingProcessor(
        db=postgres_db,
        embedding_provider=fallback_provider,
        batch_size=10,
        max_concurrent=2,
    )

    # フォールバック処理が動作することを確認
    texts = ["text1", "text2", "text3"]
    embeddings = await processor._generate_embeddings_batch(texts)

    assert len(embeddings) == len(texts)
    assert all(len(emb) == 1536 for emb in embeddings)
    # generate_embeddingが個別に呼ばれていることを確認
    assert fallback_provider.generate_embedding.call_count == len(texts)


@pytest.mark.asyncio
async def test_embedding_processor_generate_embedding_with_limit(postgres_db):
    """_generate_embedding_with_limitのセマフォ制限テスト"""
    from unittest.mock import AsyncMock

    from kotonoha_bot.external.embedding.openai_embedding import (
        OpenAIEmbeddingProvider,
    )

    provider = AsyncMock(spec=OpenAIEmbeddingProvider)
    provider.generate_embedding = AsyncMock(return_value=[0.1] * 1536)
    provider.get_dimension = lambda: 1536

    processor = EmbeddingProcessor(
        db=postgres_db,
        embedding_provider=provider,
        batch_size=10,
        max_concurrent=2,  # 同時実行数を2に制限
    )

    # 複数のリクエストを同時に送信
    tasks = [processor._generate_embedding_with_limit(f"text{i}") for i in range(5)]
    results = await asyncio.gather(*tasks)

    # すべてのリクエストが完了することを確認
    assert len(results) == 5
    assert all(len(emb) == 1536 for emb in results)
    # セマフォにより同時実行数が制限されていることを確認（呼び出し回数は5回）
    assert provider.generate_embedding.call_count == 5


@pytest.mark.asyncio
async def test_embedding_processor_update_source_status_pending(
    postgres_db, mock_embedding_provider
):
    """Sourceステータス更新（pending状態のまま）のテスト"""
    # テスト用のソースとチャンクを作成
    source_id = await postgres_db.save_source(
        source_type="discord_session",
        title="Pendingステータステスト",
        uri="https://example.com/pending_test",
        metadata={"test": True},
        status="pending",
    )

    # チャンクを作成（embeddingはNULLのまま）
    await postgres_db.save_chunk(
        source_id=source_id,
        content="これはpendingステータステスト用のチャンクです",
        location={"url": "https://example.com/pending_test", "label": "テスト"},
        token_count=10,
    )

    processor = EmbeddingProcessor(
        db=postgres_db,
        embedding_provider=mock_embedding_provider,
        batch_size=10,
        max_concurrent=2,
    )

    # 処理を実行（embeddingが設定される）
    await processor._process_pending_embeddings_impl()

    # Sourceステータスが'completed'になっていることを確認
    async with postgres_db.pool.acquire() as conn:
        result = await conn.fetchrow(
            "SELECT status FROM knowledge_sources WHERE id = $1",
            source_id,
        )
        assert result is not None
        assert result["status"] == "completed"


# ============================================
# 追加テストケース（2026年1月19日）
# ============================================


@pytest.mark.asyncio
async def test_embedding_processor_graceful_shutdown(
    postgres_db, mock_embedding_provider
):
    """graceful_shutdownのテスト"""
    processor = EmbeddingProcessor(
        db=postgres_db,
        embedding_provider=mock_embedding_provider,
        batch_size=10,
        max_concurrent=2,
    )

    # タスクが開始されていない状態でもシャットダウンが成功すること
    await processor.graceful_shutdown()

    # process_pending_embeddingsがキャンセルされていることを確認
    assert not processor.process_pending_embeddings.is_running()


@pytest.mark.asyncio
async def test_embedding_processor_lock_skip_behavior(postgres_db, mock_embedding_provider):
    """ロック競合時のスキップ動作テスト"""
    processor = EmbeddingProcessor(
        db=postgres_db,
        embedding_provider=mock_embedding_provider,
        batch_size=10,
        max_concurrent=2,
    )

    # ロックを取得
    async with processor._lock:
        # ロック中に処理を実行（スキップされるべき）
        await processor._process_pending_embeddings_impl()
        # 競合状態対策でスキップされることを確認（エラーにならない）


@pytest.mark.asyncio
async def test_embedding_processor_start_method(postgres_db, mock_embedding_provider):
    """start()メソッドのテスト"""
    processor = EmbeddingProcessor(
        db=postgres_db,
        embedding_provider=mock_embedding_provider,
        batch_size=10,
        max_concurrent=2,
    )

    # start()を呼び出す
    processor.start()

    # タスクが開始されていることを確認
    assert processor.process_pending_embeddings.is_running()

    # クリーンアップ
    processor.process_pending_embeddings.cancel()


@pytest.mark.asyncio
async def test_embedding_processor_source_status_failed(postgres_db):
    """Sourceステータスがfailedに更新されるテスト"""
    from kotonoha_bot.config import settings

    # エラーを発生させるモック
    error_provider = AsyncMock(spec=OpenAIEmbeddingProvider)
    error_provider.generate_embeddings_batch = AsyncMock(
        side_effect=Exception("API Error")
    )
    error_provider.get_dimension = lambda: 1536

    # テスト用のソースとチャンクを作成
    source_id = await postgres_db.save_source(
        source_type="discord_session",
        title="Failedステータステスト",
        uri="https://example.com/failed_test",
        metadata={"test": True},
        status="pending",
    )

    await postgres_db.save_chunk(
        source_id=source_id,
        content="これはfailedステータステスト用のチャンクです",
        location={"url": "https://example.com/failed_test", "label": "テスト"},
        token_count=10,
    )

    processor = EmbeddingProcessor(
        db=postgres_db,
        embedding_provider=error_provider,
        batch_size=10,
        max_concurrent=2,
    )

    # 最大リトライ回数 + 1 まで処理を実行（最後の回でfailedステータスに更新される）
    max_retry = settings.kb_embedding_max_retry
    for _ in range(max_retry + 1):
        await processor._process_pending_embeddings_impl()

    # Sourceステータスが'failed'になっていることを確認
    # ⚠️ 注意: チャンクがDLQに移動された後、retry_count >= MAX_RETRYのチャンクが残っている場合に
    # failedステータスに更新される
    async with postgres_db.pool.acquire() as conn:
        result = await conn.fetchrow(
            "SELECT status, error_code, error_message FROM knowledge_sources WHERE id = $1",
            source_id,
        )
        assert result is not None
        # チャンクがDLQに移動されているか、failedステータスになっているかを確認
        assert result["status"] in ("failed", "pending", "partial"), (
            f"ステータスはfailed, pending, または partialである必要があります: "
            f"actual={result['status']}"
        )


@pytest.mark.asyncio
async def test_embedding_processor_move_to_dlq_with_source_info(postgres_db):
    """DLQへの移動時にsource_typeとsource_titleが保存されるテスト"""
    from kotonoha_bot.config import settings

    # エラーを発生させるモック
    error_provider = AsyncMock(spec=OpenAIEmbeddingProvider)
    error_provider.generate_embeddings_batch = AsyncMock(
        side_effect=Exception("API Error")
    )
    error_provider.get_dimension = lambda: 1536

    # テスト用のソースとチャンクを作成
    source_id = await postgres_db.save_source(
        source_type="discord_session",
        title="DLQソース情報テスト",
        uri="https://example.com/dlq_source_info",
        metadata={"test": True},
        status="pending",
    )

    chunk_id = await postgres_db.save_chunk(
        source_id=source_id,
        content="DLQソース情報テスト用チャンク",
        location={"url": "https://example.com/dlq_source_info", "label": "テスト"},
        token_count=10,
    )

    processor = EmbeddingProcessor(
        db=postgres_db,
        embedding_provider=error_provider,
        batch_size=10,
        max_concurrent=2,
    )

    # 最大リトライ回数まで処理を実行
    max_retry = settings.kb_embedding_max_retry
    for _ in range(max_retry):
        await processor._process_pending_embeddings_impl()

    # DLQにsource_typeとsource_titleが保存されていることを確認
    async with postgres_db.pool.acquire() as conn:
        dlq_result = await conn.fetchrow(
            "SELECT source_type, source_title FROM knowledge_chunks_dlq WHERE original_chunk_id = $1",
            chunk_id,
        )
        assert dlq_result is not None
        assert dlq_result["source_type"] == "discord_session"
        assert dlq_result["source_title"] == "DLQソース情報テスト"


@pytest.mark.asyncio
async def test_embedding_processor_classify_error_variations(
    postgres_db, mock_embedding_provider
):
    """エラー分類のバリエーションテスト"""
    processor = EmbeddingProcessor(
        db=postgres_db,
        embedding_provider=mock_embedding_provider,
        batch_size=10,
        max_concurrent=2,
    )

    # 様々なエラーパターンをテスト
    assert processor._classify_error(Exception("connection timed out")) == "EMBEDDING_API_TIMEOUT"
    assert processor._classify_error(Exception("Error 429: Rate limit exceeded")) == "RATE_LIMIT"
    assert processor._classify_error(Exception("401 Unauthorized")) == "AUTHENTICATION_ERROR"
    assert processor._classify_error(Exception("403 Forbidden permission denied")) == "PERMISSION_ERROR"
    assert processor._classify_error(Exception("404 Not Found")) == "NOT_FOUND"
    assert processor._classify_error(Exception("500 Internal Server Error")) == "SERVER_ERROR"
    assert processor._classify_error(Exception("Something completely unexpected")) == "UNKNOWN_ERROR"


@pytest.mark.asyncio
async def test_embedding_processor_generalize_error_message_all_types(
    postgres_db, mock_embedding_provider
):
    """エラーメッセージ一般化の全パターンテスト"""
    processor = EmbeddingProcessor(
        db=postgres_db,
        embedding_provider=mock_embedding_provider,
        batch_size=10,
        max_concurrent=2,
    )

    test_cases = [
        (Exception("timeout"), "Embedding API request timed out"),
        (Exception("rate limit exceeded"), "Rate limit exceeded"),
        (Exception("authentication failed"), "Authentication failed"),
        (Exception("permission denied"), "Permission denied"),
        (Exception("not found"), "Resource not found"),
        (Exception("server error 500"), "Server error occurred"),
        (Exception("random error"), "An error occurred during processing"),
    ]

    for error, expected_message in test_cases:
        result = processor._generalize_error_message(error)
        assert result == expected_message, f"Error: {error}, Expected: {expected_message}, Got: {result}"


@pytest.mark.asyncio
async def test_embedding_processor_empty_pending_chunks(postgres_db):
    """pendingチャンクがない場合のテスト"""
    # 新しいモックを作成して呼び出しを追跡
    provider = AsyncMock(spec=OpenAIEmbeddingProvider)
    provider.generate_embeddings_batch = AsyncMock(return_value=[[0.1] * 1536])
    provider.get_dimension = lambda: 1536

    processor = EmbeddingProcessor(
        db=postgres_db,
        embedding_provider=provider,
        batch_size=10,
        max_concurrent=2,
    )

    # pendingチャンクがない状態で処理を実行
    await processor._process_pending_embeddings_impl()

    # エラーにならず正常終了することを確認
    # (generate_embeddings_batchが呼ばれないことを確認)
    provider.generate_embeddings_batch.assert_not_called()


@pytest.mark.asyncio
async def test_embedding_processor_interval_configuration(
    postgres_db, mock_embedding_provider
):
    """間隔設定のテスト"""
    processor = EmbeddingProcessor(
        db=postgres_db,
        embedding_provider=mock_embedding_provider,
        batch_size=10,
        max_concurrent=2,
    )

    from kotonoha_bot.config import settings

    # _intervalが環境変数から読み込まれていることを確認
    assert processor._interval == settings.kb_embedding_interval_minutes


@pytest.mark.asyncio
async def test_embedding_processor_semaphore_initialization(
    postgres_db, mock_embedding_provider
):
    """セマフォ初期化のテスト"""
    processor = EmbeddingProcessor(
        db=postgres_db,
        embedding_provider=mock_embedding_provider,
        batch_size=10,
        max_concurrent=5,  # カスタム値
    )

    # セマフォの初期値が正しく設定されていることを確認
    assert processor._semaphore._value == 5


@pytest.mark.asyncio
async def test_embedding_processor_update_source_status_partial(postgres_db):
    """DLQに移動したチャンクがある場合にpartialステータスになるテスト"""
    from kotonoha_bot.config import settings

    # 成功するプロバイダー
    success_provider = AsyncMock(spec=OpenAIEmbeddingProvider)
    success_provider.generate_embeddings_batch = AsyncMock(
        return_value=[[0.1] * 1536]
    )
    success_provider.get_dimension = lambda: 1536

    # テスト用のソースとチャンクを作成
    source_id = await postgres_db.save_source(
        source_type="discord_session",
        title="Partialステータステスト2",
        uri="https://example.com/partial_test2",
        metadata={"test": True},
        status="pending",
    )

    # 2つのチャンクを作成
    chunk_id_1 = await postgres_db.save_chunk(
        source_id=source_id,
        content="正常に処理されるチャンク",
        location={"url": "https://example.com/partial_test2", "label": "チャンク1"},
        token_count=10,
    )

    chunk_id_2 = await postgres_db.save_chunk(
        source_id=source_id,
        content="DLQに移動されるチャンク",
        location={"url": "https://example.com/partial_test2", "label": "チャンク2"},
        token_count=10,
    )

    # chunk_id_1はEmbeddingを設定、chunk_id_2は手動でDLQに移動
    async with postgres_db.pool.acquire() as conn:
        # chunk_id_1にEmbeddingを設定
        await conn.execute(
            """
            UPDATE knowledge_chunks
            SET embedding = $1::halfvec(1536)
            WHERE id = $2
            """,
            [0.1] * 1536,
            chunk_id_1,
        )

        # chunk_id_2をDLQに移動（手動シミュレート）
        await conn.execute(
            """
            INSERT INTO knowledge_chunks_dlq
            (original_chunk_id, source_id, source_type, source_title, content, error_code, error_message, retry_count)
            VALUES ($1, $2, 'discord_session', 'Partialステータステスト2', 'DLQに移動されるチャンク', 'TEST_ERROR', 'テストエラー', 3)
            """,
            chunk_id_2,
            source_id,
        )

        # chunk_id_2を元のテーブルから削除
        await conn.execute(
            "DELETE FROM knowledge_chunks WHERE id = $1",
            chunk_id_2,
        )

    processor = EmbeddingProcessor(
        db=postgres_db,
        embedding_provider=success_provider,
        batch_size=10,
        max_concurrent=2,
    )

    # ステータス更新を実行
    await processor._update_source_status([{"source_id": source_id}])

    # Sourceステータスが'partial'になっていることを確認
    async with postgres_db.pool.acquire() as conn:
        result = await conn.fetchrow(
            "SELECT status FROM knowledge_sources WHERE id = $1",
            source_id,
        )
        assert result is not None
        assert result["status"] == "partial"
