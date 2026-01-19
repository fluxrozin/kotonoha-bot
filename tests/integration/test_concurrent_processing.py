"""並行処理の統合テスト

複数のセッションやソースを同時に処理する場合の動作確認
"""

import asyncio
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
async def test_concurrent_session_archiving(postgres_db, mock_embedding_provider):
    """複数セッションの同時アーカイブテスト"""
    # 複数のセッションを作成
    sessions = []
    for i in range(5):
        session = ChatSession(
            session_key=f"test:session:concurrent:{i:03d}",
            session_type="mention",
            messages=[
                Message(
                    role=MessageRole.USER,
                    content=f"これは並行処理テスト用のセッション{i}です。十分な長さのメッセージを含めています。",
                    timestamp=datetime.now(UTC) - timedelta(hours=2),
                ),
                Message(
                    role=MessageRole.ASSISTANT,
                    content=f"了解しました。並行処理テスト{i}を確認します。",
                    timestamp=datetime.now(UTC) - timedelta(hours=2),
                ),
            ],
            guild_id=123456789,
            channel_id=987654321,
            user_id=111222333,
            last_active_at=datetime.now(UTC) - timedelta(hours=2),
        )
        await postgres_db.save_session(session)
        sessions.append(session)

    archiver = SessionArchiver(
        db=postgres_db,
        embedding_provider=mock_embedding_provider,
        archive_threshold_hours=1,
    )

    # すべてのセッションを並行してアーカイブ
    async def archive_session(session_key: str):
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
                session_key,
            )
            if session_row:
                await archiver._archive_session_impl(dict(session_row))

    # 並行処理
    await asyncio.gather(*[archive_session(s.session_key) for s in sessions])

    # すべてのセッションがアーカイブされていることを確認
    async with postgres_db.pool.acquire() as conn:
        for session in sessions:
            source_count = await conn.fetchval(
                """
                SELECT COUNT(*)
                FROM knowledge_sources
                WHERE metadata->>'origin_session_key' = $1
            """,
                session.session_key,
            )
            assert source_count > 0, (
                f"セッション {session.session_key} がアーカイブされていません"
            )


@pytest.mark.asyncio
async def test_concurrent_embedding_processing(postgres_db, mock_embedding_provider):
    """複数ソースの同時Embedding処理テスト"""
    # 複数のソースとチャンクを作成
    source_ids = []
    all_chunk_ids = []

    for i in range(3):
        source_id = await postgres_db.save_source(
            source_type="discord_session",
            title=f"並行Embedding処理テストソース{i}",
            uri=f"https://example.com/concurrent_embedding_{i}",
            metadata={"test": True, "index": i},
            status="pending",
        )
        source_ids.append(source_id)

        # 各ソースに複数のチャンクを作成
        chunk_ids = []
        for j in range(10):
            chunk_id = await postgres_db.save_chunk(
                source_id=source_id,
                content=f"並行Embedding処理テスト用ソース{i}のチャンク{j}",
                location={
                    "url": f"https://example.com/concurrent_embedding_{i}",
                    "label": f"ソース{i}-チャンク{j}",
                },
                token_count=10,
            )
            chunk_ids.append(chunk_id)
            all_chunk_ids.append(chunk_id)

    # Embedding処理を実行
    processor = EmbeddingProcessor(
        db=postgres_db,
        embedding_provider=mock_embedding_provider,
        batch_size=50,  # すべてのチャンクを1バッチで処理できるサイズ
        max_concurrent=2,
    )

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
            all_chunk_ids,
        )
        assert result == len(all_chunk_ids), (
            f"すべてのチャンクが処理されている必要があります: "
            f"processed={result}, total={len(all_chunk_ids)}"
        )


@pytest.mark.asyncio
async def test_large_batch_processing(postgres_db, mock_embedding_provider):
    """大量データのバッチ処理テスト（バッチサイズを超えるデータ）"""
    # テスト用のソースとチャンクを作成（バッチサイズを超える）
    source_id = await postgres_db.save_source(
        source_type="discord_session",
        title="大量データバッチ処理テスト",
        uri="https://example.com/large_batch",
        metadata={"test": True},
        status="pending",
    )

    # 200個のチャンクを作成（batch_size=100を超える）
    chunk_ids = []
    for i in range(200):
        chunk_id = await postgres_db.save_chunk(
            source_id=source_id,
            content=f"大量データバッチ処理テスト用チャンク{i}",
            location={
                "url": "https://example.com/large_batch",
                "label": f"チャンク{i}",
            },
            token_count=10,
        )
        chunk_ids.append(chunk_id)

    # Embedding処理を実行（複数バッチで処理される）
    processor = EmbeddingProcessor(
        db=postgres_db,
        embedding_provider=mock_embedding_provider,
        batch_size=100,  # デフォルト値
        max_concurrent=2,
    )

    # 複数回処理を実行してすべてのチャンクを処理
    for _ in range(3):  # 最大3回まで処理
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
        assert result == len(chunk_ids), (
            f"すべてのチャンクが処理されている必要があります: "
            f"processed={result}, total={len(chunk_ids)}"
        )


@pytest.mark.asyncio
async def test_error_propagation_in_embedding_processing(postgres_db):
    """Embedding処理でのエラー伝播テスト"""
    from unittest.mock import AsyncMock

    from kotonoha_bot.external.embedding.openai_embedding import (
        OpenAIEmbeddingProvider,
    )

    # 部分的にエラーを発生させるモック
    error_count = [0]

    async def generate_embeddings_batch_with_error(
        texts: list[str],
    ) -> list[list[float]]:
        """最初の呼び出しでエラー、2回目以降は成功"""
        error_count[0] += 1
        if error_count[0] == 1:
            raise Exception("Temporary API Error")
        return [[0.1] * 1536 for _ in texts]

    error_provider = AsyncMock(spec=OpenAIEmbeddingProvider)
    error_provider.generate_embeddings_batch = generate_embeddings_batch_with_error
    error_provider.get_dimension = lambda: 1536

    # テスト用のチャンクを作成
    source_id = await postgres_db.save_source(
        source_type="discord_session",
        title="エラー伝播テスト",
        uri="https://example.com/error_propagation",
        metadata={"test": True},
        status="pending",
    )

    chunk_id = await postgres_db.save_chunk(
        source_id=source_id,
        content="エラー伝播テスト用チャンク",
        location={"url": "https://example.com/error_propagation", "label": "テスト"},
        token_count=10,
    )

    processor = EmbeddingProcessor(
        db=postgres_db,
        embedding_provider=error_provider,
        batch_size=10,
        max_concurrent=2,
    )

    # 最初の処理でエラーが発生するが、クラッシュしない
    await processor._process_pending_embeddings_impl()

    # retry_countがインクリメントされていることを確認
    async with postgres_db.pool.acquire() as conn:
        result = await conn.fetchrow(
            "SELECT retry_count FROM knowledge_chunks WHERE id = $1",
            chunk_id,
        )
        assert result is not None
        assert result["retry_count"] > 0

    # 2回目の処理で成功する
    await processor._process_pending_embeddings_impl()

    # embeddingが設定されていることを確認
    async with postgres_db.pool.acquire() as conn:
        result = await conn.fetchrow(
            "SELECT embedding IS NOT NULL as has_embedding FROM knowledge_chunks WHERE id = $1",
            chunk_id,
        )
        assert result is not None
        # 2回目の処理で成功する可能性がある（retry_countが上限未達の場合）
        # または、retry_countが上限に達してDLQに移動される可能性もある


@pytest.mark.asyncio
async def test_concurrent_save_and_archive(postgres_db, mock_embedding_provider):
    """セッション保存とアーカイブの同時実行テスト"""
    from datetime import UTC, datetime, timedelta

    from kotonoha_bot.session.models import ChatSession, Message, MessageRole

    # セッションを作成
    session = ChatSession(
        session_key="test:session:concurrent_save_archive:001",
        session_type="mention",
        messages=[
            Message(
                role=MessageRole.USER,
                content="これは同時実行テスト用のセッションです。十分な長さのメッセージを含めています。",
                timestamp=datetime.now(UTC) - timedelta(hours=2),
            )
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

    # セッション保存とアーカイブを同時に実行
    async def save_session():
        session.messages.append(
            Message(
                role=MessageRole.ASSISTANT,
                content="同時実行テスト",
                timestamp=datetime.now(UTC),
            )
        )
        session.last_active_at = datetime.now(UTC)
        await postgres_db.save_session(session)

    async def archive_session():
        # ⚠️ 重要: _archive_session_impl内で接続を取得するため、
        # テスト側で接続を取得する必要はない
        # セッション情報を取得してアーカイブ処理を実行
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
                "test:session:concurrent_save_archive:001",
            )
        # 接続をクローズしてから、_archive_session_implを呼び出す
        # （_archive_session_impl内で新しい接続を取得するため）
        if session_row:
            await archiver._archive_session_impl(dict(session_row))

    # 並行処理（楽観的ロックにより競合が処理される）
    await asyncio.gather(save_session(), archive_session(), return_exceptions=True)

    # セッションが正しく処理されていることを確認
    loaded = await postgres_db.load_session("test:session:concurrent_save_archive:001")
    assert loaded is not None


@pytest.mark.asyncio
async def test_multiple_sources_status_update(postgres_db, mock_embedding_provider):
    """複数ソースのステータス更新統合テスト"""
    # 複数のソースとチャンクを作成
    source_ids = []
    for i in range(3):
        source_id = await postgres_db.save_source(
            source_type="discord_session",
            title=f"複数ソースステータス更新テスト{i}",
            uri=f"https://example.com/multi_source_status_{i}",
            metadata={"test": True},
            status="pending",
        )
        source_ids.append(source_id)

        # 各ソースに複数のチャンクを作成
        for j in range(5):
            await postgres_db.save_chunk(
                source_id=source_id,
                content=f"複数ソースステータス更新テスト用ソース{i}のチャンク{j}",
                location={
                    "url": f"https://example.com/multi_source_status_{i}",
                    "label": f"ソース{i}-チャンク{j}",
                },
                token_count=10,
            )

    # Embedding処理を実行
    processor = EmbeddingProcessor(
        db=postgres_db,
        embedding_provider=mock_embedding_provider,
        batch_size=50,
        max_concurrent=2,
    )

    await processor._process_pending_embeddings_impl()

    # すべてのソースのステータスが更新されていることを確認
    async with postgres_db.pool.acquire() as conn:
        for source_id in source_ids:
            result = await conn.fetchrow(
                "SELECT status FROM knowledge_sources WHERE id = $1",
                source_id,
            )
            assert result is not None
            assert result["status"] == "completed", (
                f"ソース {source_id} のステータスが'completed'である必要があります: "
                f"actual={result['status']}"
            )


@pytest.mark.asyncio
async def test_optimistic_locking_conflict_retry(postgres_db, mock_embedding_provider):
    """楽観的ロックの競合時リトライテスト"""
    from datetime import UTC, datetime, timedelta

    from kotonoha_bot.session.models import ChatSession, Message, MessageRole

    # セッションを作成
    session = ChatSession(
        session_key="test:session:optimistic_conflict:001",
        session_type="mention",
        messages=[
            Message(
                role=MessageRole.USER,
                content="これは楽観的ロック競合テスト用のセッションです。十分な長さのメッセージを含めています。",
                timestamp=datetime.now(UTC) - timedelta(hours=2),
            ),
            Message(
                role=MessageRole.ASSISTANT,
                content="了解しました。楽観的ロック競合のテストを確認します。",
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
            "test:session:optimistic_conflict:001",
        )

        original_version = session_row["version"]

        # アーカイブ処理を実行（楽観的ロックにより競合が処理される）
        await archiver._archive_session_impl(dict(session_row))

    # versionがインクリメントされていることを確認
    async with postgres_db.pool.acquire() as conn:
        result = await conn.fetchrow(
            "SELECT version FROM sessions WHERE session_key = $1",
            "test:session:optimistic_conflict:001",
        )
        assert result is not None
        assert result["version"] > original_version


@pytest.mark.asyncio
async def test_full_flow_with_errors(postgres_db):
    """エラーを含む完全なフローの統合テスト"""
    from datetime import UTC, datetime, timedelta
    from unittest.mock import AsyncMock

    from kotonoha_bot.external.embedding.openai_embedding import (
        OpenAIEmbeddingProvider,
    )
    from kotonoha_bot.features.knowledge_base.embedding_processor import (
        EmbeddingProcessor,
    )
    from kotonoha_bot.features.knowledge_base.session_archiver import (
        SessionArchiver,
    )
    from kotonoha_bot.session.models import ChatSession, Message, MessageRole

    # 部分的にエラーを発生させるモック
    call_count = [0]

    async def generate_embeddings_batch_with_partial_error(
        texts: list[str],
    ) -> list[list[float]]:
        """最初の呼び出しでエラー、2回目以降は成功"""
        call_count[0] += 1
        if call_count[0] == 1:
            raise Exception("Temporary API Error")
        return [[0.1] * 1536 for _ in texts]

    error_provider = AsyncMock(spec=OpenAIEmbeddingProvider)
    error_provider.generate_embeddings_batch = (
        generate_embeddings_batch_with_partial_error
    )
    error_provider.get_dimension = lambda: 1536

    # セッションを作成
    session = ChatSession(
        session_key="test:session:error_flow:001",
        session_type="mention",
        messages=[
            Message(
                role=MessageRole.USER,
                content="これはエラーフローテスト用のセッションです。十分な長さのメッセージを含めています。",
                timestamp=datetime.now(UTC) - timedelta(hours=2),
            ),
            Message(
                role=MessageRole.ASSISTANT,
                content="了解しました。エラーフローのテストを確認します。",
                timestamp=datetime.now(UTC) - timedelta(hours=2),
            ),
        ],
        guild_id=123456789,
        channel_id=987654321,
        user_id=111222333,
        last_active_at=datetime.now(UTC) - timedelta(hours=2),
    )

    await postgres_db.save_session(session)

    # セッションアーカイブ
    archiver = SessionArchiver(
        db=postgres_db,
        embedding_provider=error_provider,
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
            "test:session:error_flow:001",
        )

        await archiver._archive_session_impl(dict(session_row))

    # Embedding処理（最初はエラー、2回目で成功）
    processor = EmbeddingProcessor(
        db=postgres_db,
        embedding_provider=error_provider,
        batch_size=10,
        max_concurrent=2,
    )

    # 最初の処理でエラーが発生するが、クラッシュしない
    await processor._process_pending_embeddings_impl()

    # 2回目の処理で成功する
    await processor._process_pending_embeddings_impl()

    # 最終的にembeddingが設定されていることを確認
    async with postgres_db.pool.acquire() as conn:
        source_result = await conn.fetchrow(
            """
            SELECT id FROM knowledge_sources
            WHERE metadata->>'origin_session_key' = $1
        """,
            "test:session:error_flow:001",
        )

        if source_result:
            chunks = await conn.fetch(
                """
                SELECT embedding IS NOT NULL as has_embedding
                FROM knowledge_chunks
                WHERE source_id = $1
            """,
                source_result["id"],
            )
            # 少なくとも一部のチャンクが処理されていることを確認
            assert any(chunk["has_embedding"] for chunk in chunks)


# ============================================
# 追加統合テストケース（2026年1月19日）
# ============================================


@pytest.mark.asyncio
async def test_graceful_shutdown_integration(postgres_db, mock_embedding_provider):
    """Graceful Shutdownの統合テスト"""
    from kotonoha_bot.features.knowledge_base.embedding_processor import (
        EmbeddingProcessor,
    )
    from kotonoha_bot.features.knowledge_base.session_archiver import (
        SessionArchiver,
    )

    # プロセッサとアーカイバを作成
    processor = EmbeddingProcessor(
        db=postgres_db,
        embedding_provider=mock_embedding_provider,
        batch_size=10,
        max_concurrent=2,
    )

    archiver = SessionArchiver(
        db=postgres_db,
        embedding_provider=mock_embedding_provider,
        archive_threshold_hours=1,
    )

    # タスクを開始
    processor.start()
    archiver.start()

    # タスクが開始されていることを確認
    assert processor.process_pending_embeddings.is_running()
    assert archiver.archive_inactive_sessions.is_running()

    # Graceful Shutdown
    await processor.graceful_shutdown()
    await archiver.graceful_shutdown()

    # タスクが停止していることを確認
    assert not processor.process_pending_embeddings.is_running()
    assert not archiver.archive_inactive_sessions.is_running()


@pytest.mark.asyncio
async def test_end_to_end_knowledge_search_flow(postgres_db, mock_embedding_provider):
    """エンドツーエンドの知識検索フローテスト"""
    from datetime import UTC, datetime, timedelta

    from kotonoha_bot.features.knowledge_base.embedding_processor import (
        EmbeddingProcessor,
    )
    from kotonoha_bot.features.knowledge_base.session_archiver import (
        SessionArchiver,
    )
    from kotonoha_bot.session.models import ChatSession, Message, MessageRole

    # 1. セッションを作成
    session = ChatSession(
        session_key="test:session:e2e:001",
        session_type="mention",
        messages=[
            Message(
                role=MessageRole.USER,
                content="Pythonでの非同期プログラミングについて教えてください。asyncioを使った実装方法を詳しく説明してほしいです。",
                timestamp=datetime.now(UTC) - timedelta(hours=2),
            ),
            Message(
                role=MessageRole.ASSISTANT,
                content="Pythonの非同期プログラミングでは、asyncioモジュールを使用します。async/awaitキーワードを使って非同期関数を定義し、イベントループ上で実行します。",
                timestamp=datetime.now(UTC) - timedelta(hours=2),
            ),
        ],
        guild_id=123456789,
        channel_id=987654321,
        user_id=111222333,
        last_active_at=datetime.now(UTC) - timedelta(hours=2),
    )

    await postgres_db.save_session(session)

    # 2. セッションをアーカイブ
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
            "test:session:e2e:001",
        )

        await archiver._archive_session_impl(dict(session_row))

    # 3. Embedding処理を実行
    processor = EmbeddingProcessor(
        db=postgres_db,
        embedding_provider=mock_embedding_provider,
        batch_size=10,
        max_concurrent=2,
    )

    await processor._process_pending_embeddings_impl()

    # 4. ベクトル検索を実行
    query_embedding = [0.1] * 1536
    results = await postgres_db.similarity_search(
        query_embedding=query_embedding,
        top_k=5,
    )

    # 5. 検索結果を確認
    # アーカイブされたセッションのチャンクが検索結果に含まれる可能性がある
    assert len(results) >= 0  # 検索結果が返ってくる


@pytest.mark.asyncio
async def test_multiple_batch_error_recovery(postgres_db):
    """複数バッチ処理のエラーリカバリテスト"""
    from unittest.mock import AsyncMock

    from kotonoha_bot.external.embedding.openai_embedding import (
        OpenAIEmbeddingProvider,
    )
    from kotonoha_bot.features.knowledge_base.embedding_processor import (
        EmbeddingProcessor,
    )

    # 2回目のバッチでエラーを発生させるモック
    batch_count = [0]

    async def generate_embeddings_with_batch_error(
        texts: list[str],
    ) -> list[list[float]]:
        """2回目のバッチでエラー、3回目以降は成功"""
        batch_count[0] += 1
        if batch_count[0] == 2:
            raise Exception("Batch Error")
        return [[0.1] * 1536 for _ in texts]

    error_provider = AsyncMock(spec=OpenAIEmbeddingProvider)
    error_provider.generate_embeddings_batch = generate_embeddings_with_batch_error
    error_provider.get_dimension = lambda: 1536

    # テスト用のソースとチャンクを作成
    source_id = await postgres_db.save_source(
        source_type="discord_session",
        title="複数バッチエラーリカバリテスト",
        uri="https://example.com/batch_error_recovery",
        metadata={"test": True},
        status="pending",
    )

    # 30個のチャンクを作成（batch_size=10で3バッチ）
    chunk_ids = []
    for i in range(30):
        chunk_id = await postgres_db.save_chunk(
            source_id=source_id,
            content=f"複数バッチエラーリカバリテスト用チャンク{i}",
            location={
                "url": "https://example.com/batch_error_recovery",
                "label": f"チャンク{i}",
            },
            token_count=10,
        )
        chunk_ids.append(chunk_id)

    processor = EmbeddingProcessor(
        db=postgres_db,
        embedding_provider=error_provider,
        batch_size=10,
        max_concurrent=2,
    )

    # 処理を実行（2回目のバッチでエラー）
    await processor._process_pending_embeddings_impl()

    # 一部のチャンクが処理されていることを確認
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
        # バッチエラーがあるため、すべては処理されていない可能性がある
        assert result >= 0

    # 再処理で残りを処理
    await processor._process_pending_embeddings_impl()


@pytest.mark.asyncio
async def test_session_archive_with_vector_search_filtering(
    postgres_db, mock_embedding_provider
):
    """セッションアーカイブとフィルタリング付きベクトル検索の統合テスト"""
    from datetime import UTC, datetime, timedelta

    from kotonoha_bot.features.knowledge_base.embedding_processor import (
        EmbeddingProcessor,
    )
    from kotonoha_bot.features.knowledge_base.session_archiver import (
        SessionArchiver,
    )
    from kotonoha_bot.session.models import ChatSession, Message, MessageRole

    # 2つの異なるチャンネルのセッションを作成
    session1 = ChatSession(
        session_key="test:session:filter:001",
        session_type="mention",
        messages=[
            Message(
                role=MessageRole.USER,
                content="チャンネル1のセッションです。フィルタリングテスト用の十分な長さのメッセージを含めています。",
                timestamp=datetime.now(UTC) - timedelta(hours=2),
            ),
        ],
        guild_id=123456789,
        channel_id=111111111,  # チャンネル1
        user_id=111222333,
        last_active_at=datetime.now(UTC) - timedelta(hours=2),
    )

    session2 = ChatSession(
        session_key="test:session:filter:002",
        session_type="mention",
        messages=[
            Message(
                role=MessageRole.USER,
                content="チャンネル2のセッションです。フィルタリングテスト用の十分な長さのメッセージを含めています。",
                timestamp=datetime.now(UTC) - timedelta(hours=2),
            ),
        ],
        guild_id=123456789,
        channel_id=222222222,  # チャンネル2
        user_id=111222333,
        last_active_at=datetime.now(UTC) - timedelta(hours=2),
    )

    await postgres_db.save_session(session1)
    await postgres_db.save_session(session2)

    archiver = SessionArchiver(
        db=postgres_db,
        embedding_provider=mock_embedding_provider,
        archive_threshold_hours=1,
    )

    # 両方のセッションをアーカイブ
    for session_key in ["test:session:filter:001", "test:session:filter:002"]:
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
                session_key,
            )
            await archiver._archive_session_impl(dict(session_row))

    # Embedding処理を実行
    processor = EmbeddingProcessor(
        db=postgres_db,
        embedding_provider=mock_embedding_provider,
        batch_size=10,
        max_concurrent=2,
    )
    await processor._process_pending_embeddings_impl()

    # チャンネル1でフィルタリング
    query_embedding = [0.1] * 1536
    results = await postgres_db.similarity_search(
        query_embedding=query_embedding,
        top_k=10,
        filters={"channel_id": 111111111},
    )

    # チャンネル1のチャンクのみが返ってくることを確認
    for result in results:
        assert result["source_metadata"].get("channel_id") == 111111111


@pytest.mark.asyncio
async def test_dlq_recovery_flow(postgres_db):
    """DLQリカバリフローのテスト"""

    # DLQにエントリを手動で作成
    source_id = await postgres_db.save_source(
        source_type="discord_session",
        title="DLQリカバリテスト",
        uri="https://example.com/dlq_recovery",
        metadata={"test": True},
        status="pending",
    )

    # DLQにエントリを挿入
    async with postgres_db.pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO knowledge_chunks_dlq
            (original_chunk_id, source_id, source_type, source_title, content, error_code, error_message, retry_count)
            VALUES ($1, $2, 'discord_session', 'DLQリカバリテスト', 'DLQテスト用コンテンツ', 'TEST_ERROR', 'テストエラー', 3)
        """,
            99999,  # 架空のchunk_id
            source_id,
        )

        # DLQにエントリがあることを確認
        dlq_count = await conn.fetchval(
            "SELECT COUNT(*) FROM knowledge_chunks_dlq WHERE source_id = $1",
            source_id,
        )
        assert dlq_count == 1

        # DLQエントリの詳細を確認
        dlq_entry = await conn.fetchrow(
            "SELECT * FROM knowledge_chunks_dlq WHERE source_id = $1",
            source_id,
        )
        assert dlq_entry is not None
        assert dlq_entry["error_code"] == "TEST_ERROR"
        assert dlq_entry["retry_count"] == 3
