"""SessionArchiver のテスト"""

from datetime import UTC, datetime, timedelta

import pytest

from kotonoha_bot.features.knowledge_base.session_archiver import (
    SessionArchiver,
)
from kotonoha_bot.session.models import ChatSession, Message, MessageRole


@pytest.mark.asyncio
async def test_session_archiver_initialization(postgres_db, mock_embedding_provider):
    """SessionArchiverの初期化テスト"""
    archiver = SessionArchiver(
        db=postgres_db,
        embedding_provider=mock_embedding_provider,
        archive_threshold_hours=1,
    )

    assert archiver.db == postgres_db
    assert archiver.embedding_provider == mock_embedding_provider
    assert archiver.archive_threshold_hours == 1


@pytest.mark.asyncio
async def test_session_archiver_archive_session(postgres_db, mock_embedding_provider):
    """セッションアーカイブのテスト"""
    # テスト用のセッションを作成（1時間以上非アクティブ）
    session = ChatSession(
        session_key="test:session:archiver:001",
        session_type="mention",
        messages=[
            Message(
                role=MessageRole.USER,
                content="これはテスト用のセッションです",
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

    # セッションを保存
    await postgres_db.save_session(session)

    # SessionArchiverを作成
    archiver = SessionArchiver(
        db=postgres_db,
        embedding_provider=mock_embedding_provider,
        archive_threshold_hours=1,
    )

    # セッションを取得してアーカイブ
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
            "test:session:archiver:001",
        )

        assert session_row is not None

        # アーカイブ処理を実行
        await archiver._archive_session_impl(dict(session_row))

    # セッションのステータスが更新されているか確認
    async with postgres_db.pool.acquire() as conn:
        result = await conn.fetchrow(
            """
            SELECT status, jsonb_array_length(messages) as remaining_message_count
            FROM sessions
            WHERE session_key = $1
        """,
            "test:session:archiver:001",
        )

        assert result is not None
        assert result["status"] == "archived"
        # スライディングウィンドウ（のりしろ）が残っているか確認
        assert result["remaining_message_count"] > 0

    # 知識ベースに変換されているか確認
    async with postgres_db.pool.acquire() as conn:
        source_result = await conn.fetchrow(
            """
            SELECT id, title, type, status
            FROM knowledge_sources
            WHERE metadata->>'origin_session_key' = $1
        """,
            "test:session:archiver:001",
        )

        assert source_result is not None
        assert source_result["type"] == "discord_session"

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


@pytest.mark.asyncio
async def test_session_archiver_sliding_window(postgres_db, mock_embedding_provider):
    """スライディングウィンドウ（のりしろ）のテスト"""
    # テスト用のセッションを作成（複数のメッセージ）
    messages = []
    for i in range(10):
        messages.append(
            Message(
                role=MessageRole.USER if i % 2 == 0 else MessageRole.ASSISTANT,
                content=f"メッセージ{i}",
                timestamp=datetime.now(UTC) - timedelta(hours=2),
            )
        )

    session = ChatSession(
        session_key="test:session:sliding:001",
        session_type="mention",
        messages=messages,
        guild_id=123456789,
        channel_id=987654321,
        user_id=111222333,
        last_active_at=datetime.now(UTC) - timedelta(hours=2),
    )

    # セッションを保存
    await postgres_db.save_session(session)

    # SessionArchiverを作成
    archiver = SessionArchiver(
        db=postgres_db,
        embedding_provider=mock_embedding_provider,
        archive_threshold_hours=1,
    )

    # セッションを取得してアーカイブ
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
            "test:session:sliding:001",
        )

        # アーカイブ処理を実行
        await archiver._archive_session_impl(dict(session_row))

    # スライディングウィンドウ（のりしろ）が残っているか確認
    async with postgres_db.pool.acquire() as conn:
        result = await conn.fetchrow(
            """
            SELECT jsonb_array_length(messages) as remaining_message_count
            FROM sessions
            WHERE session_key = $1
        """,
            "test:session:sliding:001",
        )

        assert result is not None
        # のりしろの件数が残っている（デフォルト: 5件）
        assert result["remaining_message_count"] > 0
        assert result["remaining_message_count"] <= 5


@pytest.mark.asyncio
async def test_session_archiver_filtering(postgres_db, mock_embedding_provider):
    """フィルタリングロジックのテスト（短いセッション、Botのみのセッション）"""
    # 短いセッションを作成（フィルタリング対象）
    short_session = ChatSession(
        session_key="test:session:short:001",
        session_type="mention",
        messages=[
            Message(
                role=MessageRole.USER,
                content="短い",
                timestamp=datetime.now(UTC) - timedelta(hours=2),
            )
        ],
        last_active_at=datetime.now(UTC) - timedelta(hours=2),
    )

    # Botのみのセッションを作成（フィルタリング対象）
    bot_only_session = ChatSession(
        session_key="test:session:bot_only:001",
        session_type="mention",
        messages=[
            Message(
                role=MessageRole.ASSISTANT,
                content="Botのみのセッション",
                timestamp=datetime.now(UTC) - timedelta(hours=2),
            )
        ],
        last_active_at=datetime.now(UTC) - timedelta(hours=2),
    )

    # セッションを保存
    await postgres_db.save_session(short_session)
    await postgres_db.save_session(bot_only_session)

    # SessionArchiverを作成
    archiver = SessionArchiver(
        db=postgres_db,
        embedding_provider=mock_embedding_provider,
        archive_threshold_hours=1,
    )

    # セッションを取得してアーカイブを試行
    async with postgres_db.pool.acquire() as conn:
        short_row = await conn.fetchrow(
            """
            SELECT id, session_key, session_type, messages,
                   guild_id, channel_id, thread_id,
                   user_id, last_active_at, version,
                   last_archived_message_index
            FROM sessions
            WHERE session_key = $1
        """,
            "test:session:short:001",
        )

        bot_only_row = await conn.fetchrow(
            """
            SELECT id, session_key, session_type, messages,
                   guild_id, channel_id, thread_id,
                   user_id, last_active_at, version,
                   last_archived_message_index
            FROM sessions
            WHERE session_key = $1
        """,
            "test:session:bot_only:001",
        )

        # アーカイブ処理を実行
        await archiver._archive_session_impl(dict(short_row))
        await archiver._archive_session_impl(dict(bot_only_row))

    # セッションのステータスが'archived'に更新されているが、知識ベースには登録されていないことを確認
    async with postgres_db.pool.acquire() as conn:
        short_result = await conn.fetchrow(
            """
            SELECT status
            FROM sessions
            WHERE session_key = $1
        """,
            "test:session:short:001",
        )

        bot_only_result = await conn.fetchrow(
            """
            SELECT status
            FROM sessions
            WHERE session_key = $1
        """,
            "test:session:bot_only:001",
        )

        assert short_result["status"] == "archived"
        assert bot_only_result["status"] == "archived"

        # 知識ベースに登録されていないことを確認
        source_count = await conn.fetchval(
            """
            SELECT COUNT(*)
            FROM knowledge_sources
            WHERE metadata->>'origin_session_key' IN ($1, $2)
        """,
            "test:session:short:001",
            "test:session:bot_only:001",
        )

        assert source_count == 0
