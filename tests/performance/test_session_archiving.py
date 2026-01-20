"""セッションアーカイブ処理のパフォーマンステスト."""

import time
from datetime import datetime, timedelta

import pytest

from kotonoha_bot.db.models import ChatSession, Message, MessageRole
from kotonoha_bot.features.knowledge_base.session_archiver import SessionArchiver


@pytest.mark.asyncio
@pytest.mark.slow
async def test_session_archiving_batch_performance(
    postgres_db, mock_embedding_provider
):
    """セッションアーカイブ処理のバッチパフォーマンステスト

    大量のセッションをバッチでアーカイブし、処理時間を測定する。
    """
    # アーカイブ対象のセッションを作成（閾値時間以上非アクティブ）
    threshold_time = datetime.now() - timedelta(hours=2)
    session_keys = []

    for i in range(50):
        session_key = f"perf_test_session_{i}"
        session_keys.append(session_key)

        # セッションを作成（複数のメッセージを含む）
        messages = [
            Message(
                role=MessageRole.USER if j % 2 == 0 else MessageRole.ASSISTANT,
                content=f"メッセージ{j}の内容です。これはパフォーマンステスト用のメッセージです。",
                timestamp=threshold_time - timedelta(minutes=j),
            )
            for j in range(20)  # 各セッションに20個のメッセージ
        ]

        session = ChatSession(
            session_key=session_key,
            session_type="mention",
            messages=messages,
            channel_id=123456789,
            user_id=987654321,
            created_at=threshold_time - timedelta(hours=3),
            last_active_at=threshold_time,  # 閾値時間以上非アクティブ
        )

        await postgres_db.save_session(session)

    # SessionArchiverを作成
    archiver = SessionArchiver(
        db=postgres_db,
        embedding_provider=mock_embedding_provider,
        archive_threshold_hours=1,
    )

    # 処理時間を測定
    start = time.time()
    await archiver.archive_inactive_sessions()
    elapsed = time.time() - start

    # パフォーマンスアサーション
    # 50個のセッションをバッチでアーカイブ
    assert elapsed < 30.0, (
        f"50個のセッションのアーカイブ処理が30秒以内に完了する必要があります（実際: {elapsed:.3f}秒）"
    )

    # セッションがアーカイブされたことを確認
    async with postgres_db.pool.acquire() as conn:
        archived_count = await conn.fetchval(
            """
            SELECT COUNT(*) FROM sessions
            WHERE session_key LIKE 'perf_test_session_%'
            AND status = 'archived'
        """
        )
        assert archived_count > 0, "セッションがアーカイブされる必要があります"


@pytest.mark.asyncio
@pytest.mark.slow
async def test_session_archiving_concurrent_performance(
    postgres_db, mock_embedding_provider
):
    """セッションアーカイブ処理の並行処理パフォーマンステスト

    複数のセッションを並行してアーカイブし、並行処理の効果を測定する。
    """
    # アーカイブ対象のセッションを作成
    threshold_time = datetime.now() - timedelta(hours=2)
    session_keys = []

    for i in range(100):
        session_key = f"concurrent_perf_test_session_{i}"
        session_keys.append(session_key)

        messages = [
            Message(
                role=MessageRole.USER if j % 2 == 0 else MessageRole.ASSISTANT,
                content=f"メッセージ{j}の内容です。",
                timestamp=threshold_time - timedelta(minutes=j),
            )
            for j in range(10)  # 各セッションに10個のメッセージ
        ]

        session = ChatSession(
            session_key=session_key,
            session_type="mention",
            messages=messages,
            channel_id=123456789,
            user_id=987654321,
            created_at=threshold_time - timedelta(hours=3),
            last_active_at=threshold_time,
        )

        await postgres_db.save_session(session)

    # SessionArchiverを作成
    archiver = SessionArchiver(
        db=postgres_db,
        embedding_provider=mock_embedding_provider,
        archive_threshold_hours=1,
    )

    # 処理時間を測定
    start = time.time()
    await archiver.archive_inactive_sessions()
    elapsed = time.time() - start

    # パフォーマンスアサーション
    # 100個のセッションを並行処理でアーカイブ
    assert elapsed < 60.0, (
        f"100個のセッションの並行アーカイブ処理が60秒以内に完了する必要があります（実際: {elapsed:.3f}秒）"
    )

    # セッションがアーカイブされたことを確認
    async with postgres_db.pool.acquire() as conn:
        archived_count = await conn.fetchval(
            """
            SELECT COUNT(*) FROM sessions
            WHERE session_key LIKE 'concurrent_perf_test_session_%'
            AND status = 'archived'
        """
        )
        assert archived_count > 0, "セッションがアーカイブされる必要があります"


@pytest.mark.asyncio
@pytest.mark.slow
async def test_session_archiving_large_session_performance(
    postgres_db, mock_embedding_provider
):
    """大きなセッションのアーカイブ処理パフォーマンステスト

    大量のメッセージを含むセッションのアーカイブ処理性能を測定する。
    """
    # 大きなセッションを作成（1000個のメッセージ）
    threshold_time = datetime.now() - timedelta(hours=2)
    session_key = "large_session_perf_test"

    messages = [
        Message(
            role=MessageRole.USER if i % 2 == 0 else MessageRole.ASSISTANT,
            content=f"メッセージ{i}の内容です。これは大きなセッションのパフォーマンステスト用のメッセージです。"
            f"メッセージの内容は十分な長さを持っています。",
            timestamp=threshold_time - timedelta(minutes=i),
        )
        for i in range(1000)  # 1000個のメッセージ
    ]

    session = ChatSession(
        session_key=session_key,
        session_type="mention",
        messages=messages,
        channel_id=123456789,
        user_id=987654321,
        created_at=threshold_time - timedelta(hours=3),
        last_active_at=threshold_time,
    )

    await postgres_db.save_session(session)

    # SessionArchiverを作成
    archiver = SessionArchiver(
        db=postgres_db,
        embedding_provider=mock_embedding_provider,
        archive_threshold_hours=1,
    )

    # 処理時間を測定
    start = time.time()
    await archiver.archive_inactive_sessions()
    elapsed = time.time() - start

    # パフォーマンスアサーション
    # 1000個のメッセージを含むセッションのアーカイブ
    assert elapsed < 20.0, (
        f"1000個のメッセージを含むセッションのアーカイブ処理が20秒以内に完了する必要があります（実際: {elapsed:.3f}秒）"
    )

    # セッションがアーカイブされたことを確認
    async with postgres_db.pool.acquire() as conn:
        archived_count = await conn.fetchval(
            """
            SELECT COUNT(*) FROM sessions
            WHERE session_key = $1 AND status = 'archived'
        """,
            session_key,
        )
        assert archived_count == 1, "セッションがアーカイブされる必要があります"
