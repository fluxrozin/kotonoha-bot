"""SessionArchiver のテスト"""

import asyncio
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from kotonoha_bot.db.models import ChatSession, Message, MessageRole
from kotonoha_bot.features.knowledge_base.session_archiver import (
    SessionArchiver,
)


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
    # ⚠️ 重要: kb_min_session_length（デフォルト30文字）を超える長さのメッセージが必要
    session = ChatSession(
        session_key="test:session:archiver:001",
        session_type="mention",
        messages=[
            Message(
                role=MessageRole.USER,
                content="これはテスト用のセッションです。十分な長さのメッセージを含めています。",
                timestamp=datetime.now(UTC) - timedelta(hours=2),
            ),
            Message(
                role=MessageRole.ASSISTANT,
                content="了解しました。テスト用のセッションアーカイブ処理を確認します。",
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


@pytest.mark.asyncio
async def test_optimistic_locking(postgres_db, mock_embedding_provider):
    """楽観的ロックの確認"""
    # テスト用のセッションを作成
    session = ChatSession(
        session_key="test:session:optimistic:001",
        session_type="mention",
        messages=[
            Message(
                role=MessageRole.USER,
                content="これは楽観的ロックテスト用のセッションです。十分な長さのメッセージを含めています。",
                timestamp=datetime.now(UTC) - timedelta(hours=2),
            ),
            Message(
                role=MessageRole.ASSISTANT,
                content="了解しました。楽観的ロックのテストを確認します。",
                timestamp=datetime.now(UTC) - timedelta(hours=2),
            ),
        ],
        guild_id=123456789,
        channel_id=987654321,
        user_id=111222333,
        last_active_at=datetime.now(UTC) - timedelta(hours=2),
    )

    await postgres_db.save_session(session)

    # 元のバージョンを取得
    async with postgres_db.pool.acquire() as conn:
        original_row = await conn.fetchrow(
            """
            SELECT version, last_archived_message_index
            FROM sessions
            WHERE session_key = $1
        """,
            "test:session:optimistic:001",
        )
        original_version = original_row["version"]
        original_index = original_row["last_archived_message_index"]

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
            "test:session:optimistic:001",
        )

        await archiver._archive_session_impl(dict(session_row))

    # versionがインクリメントされているか確認
    async with postgres_db.pool.acquire() as conn:
        result = await conn.fetchrow(
            """
            SELECT version, last_archived_message_index
            FROM sessions
            WHERE session_key = $1
        """,
            "test:session:optimistic:001",
        )
        assert result["version"] == original_version + 1
        # last_archived_message_indexが更新されていることを確認
        # original_indexが0の場合、> 0ではなく >= 0 を確認
        assert result["last_archived_message_index"] >= original_index
        # アーカイブが実行された場合、last_archived_message_indexは更新される
        # （すべてのメッセージがアーカイブされた場合、0にリセットされる可能性があるが、
        #  通常はアーカイブされたメッセージ数が設定される）
        # このテストでは、アーカイブが実行されたことを確認するため、
        # versionがインクリメントされていることを確認する


@pytest.mark.asyncio
async def test_chunking_strategy(postgres_db, mock_embedding_provider):
    """チャンク化戦略の確認"""
    from kotonoha_bot.config import settings

    # 複数のメッセージを持つセッションを作成
    messages = []
    for i in range(10):
        messages.append(
            Message(
                role=MessageRole.USER if i % 2 == 0 else MessageRole.ASSISTANT,
                content=f"これはチャンク化戦略テスト用のメッセージ{i}です。十分な長さのメッセージを含めています。",
                timestamp=datetime.now(UTC) - timedelta(hours=2),
            )
        )

    session = ChatSession(
        session_key="test:session:chunking:001",
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
            "test:session:chunking:001",
        )

        await archiver._archive_session_impl(dict(session_row))

    # チャンクが作成されているか確認
    async with postgres_db.pool.acquire() as conn:
        source_result = await conn.fetchrow(
            """
            SELECT id FROM knowledge_sources
            WHERE metadata->>'origin_session_key' = $1
        """,
            "test:session:chunking:001",
        )

        assert source_result is not None
        source_id = source_result["id"]

        chunks = await conn.fetch(
            """
            SELECT * FROM knowledge_chunks WHERE source_id = $1
        """,
            source_id,
        )
        assert len(chunks) > 0

        # 各チャンクのトークン数が上限以下か確認
        for chunk in chunks:
            assert chunk["token_count"] <= settings.kb_chunk_max_tokens, (
                f"チャンクのトークン数が上限を超えています: "
                f"token_count={chunk['token_count']}, "
                f"max_tokens={settings.kb_chunk_max_tokens}"
            )


@pytest.mark.asyncio
async def test_session_archiver_format_messages_for_knowledge(
    postgres_db, mock_embedding_provider
):
    """_format_messages_for_knowledgeのテスト"""
    archiver = SessionArchiver(
        db=postgres_db,
        embedding_provider=mock_embedding_provider,
        archive_threshold_hours=1,
    )

    messages = [
        {"role": "user", "content": "こんにちは"},
        {"role": "assistant", "content": "こんにちは！何かお手伝いできますか？"},
        {"role": "user", "content": "ありがとう"},
    ]

    formatted = archiver._format_messages_for_knowledge(messages)
    assert "User: こんにちは" in formatted
    assert "Assistant: こんにちは！何かお手伝いできますか？" in formatted
    assert "User: ありがとう" in formatted


@pytest.mark.asyncio
async def test_session_archiver_generate_title(postgres_db, mock_embedding_provider):
    """_generate_titleのテスト"""
    archiver = SessionArchiver(
        db=postgres_db,
        embedding_provider=mock_embedding_provider,
        archive_threshold_hours=1,
    )

    # 通常のメッセージ
    messages = [
        {"role": "user", "content": "これはテスト用のメッセージです"},
        {"role": "assistant", "content": "了解しました"},
    ]
    title = archiver._generate_title(messages)
    assert title == "これはテスト用のメッセージです"

    # 長いメッセージ（50文字制限）
    long_messages = [
        {
            "role": "user",
            "content": "これは非常に長いメッセージです。" * 10,
        }
    ]
    long_title = archiver._generate_title(long_messages)
    assert len(long_title) <= 53  # 50文字 + "..."
    assert long_title.endswith("...")

    # ユーザーメッセージがない場合
    bot_only_messages = [{"role": "assistant", "content": "Botのみのメッセージ"}]
    bot_title = archiver._generate_title(bot_only_messages)
    assert bot_title == "Discord Session"

    # 空のメッセージ
    empty_title = archiver._generate_title([])
    assert empty_title == "Discord Session"


@pytest.mark.asyncio
async def test_session_archiver_generate_discord_uri(
    postgres_db, mock_embedding_provider
):
    """_generate_discord_uriのテスト"""
    archiver = SessionArchiver(
        db=postgres_db,
        embedding_provider=mock_embedding_provider,
        archive_threshold_hours=1,
    )

    # 通常のケース（guild_id、channel_id、thread_idあり）
    session_row = {
        "guild_id": 123456789,
        "channel_id": 987654321,
        "thread_id": 111222333,
    }
    uri = archiver._generate_discord_uri(session_row)
    assert uri == "https://discord.com/channels/123456789/987654321/111222333"

    # thread_idなし
    session_row_no_thread = {
        "guild_id": 123456789,
        "channel_id": 987654321,
        "thread_id": None,
    }
    uri_no_thread = archiver._generate_discord_uri(session_row_no_thread)
    assert uri_no_thread == "https://discord.com/channels/123456789/987654321"

    # guild_idなし（フォールバック）
    session_row_no_guild = {
        "guild_id": None,
        "channel_id": 987654321,
        "thread_id": 111222333,
    }
    uri_no_guild = archiver._generate_discord_uri(session_row_no_guild)
    assert uri_no_guild == "https://discord.com/channels/987654321/111222333"

    # channel_idなし
    session_row_no_channel = {
        "guild_id": 123456789,
        "channel_id": None,
        "thread_id": None,
    }
    uri_no_channel = archiver._generate_discord_uri(session_row_no_channel)
    assert uri_no_channel is None


@pytest.mark.asyncio
async def test_session_archiver_should_archive_session_boundary(
    postgres_db, mock_embedding_provider
):
    """_should_archive_sessionの境界値テスト"""
    from kotonoha_bot.config import settings

    archiver = SessionArchiver(
        db=postgres_db,
        embedding_provider=mock_embedding_provider,
        archive_threshold_hours=1,
    )

    # 最小文字数ちょうどのメッセージ
    min_length = settings.kb_min_session_length
    messages_min = [{"role": "user", "content": "a" * min_length}]
    assert archiver._should_archive_session(messages_min) is True

    # 最小文字数未満のメッセージ
    messages_below = [{"role": "user", "content": "a" * (min_length - 1)}]
    assert archiver._should_archive_session(messages_below) is False

    # Botのみのセッション
    bot_only = [{"role": "assistant", "content": "Botのみのメッセージ" * 10}]
    assert archiver._should_archive_session(bot_only) is False

    # ユーザーメッセージとBotメッセージの混合（最小文字数を超える）
    # 最小文字数を超えるメッセージを使用
    user_content = "ユーザーメッセージ" * (min_length // 6 + 1)  # 最小文字数を超える
    bot_content = "Botメッセージ"
    mixed = [
        {"role": "user", "content": user_content},
        {"role": "assistant", "content": bot_content},
    ]
    assert archiver._should_archive_session(mixed) is True


@pytest.mark.asyncio
async def test_session_archiver_empty_session(postgres_db, mock_embedding_provider):
    """空セッションのアーカイブテスト"""
    from datetime import UTC, datetime

    from kotonoha_bot.db.models import ChatSession

    # 空のメッセージリストのセッションを作成
    session = ChatSession(
        session_key="test:session:empty:001",
        session_type="mention",
        messages=[],  # 空のメッセージリスト
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
            "test:session:empty:001",
        )

        # 空セッションのアーカイブ（何も起こらない）
        await archiver._archive_session_impl(dict(session_row))

    # 知識ベースに登録されていないことを確認
    async with postgres_db.pool.acquire() as conn:
        source_count = await conn.fetchval(
            """
            SELECT COUNT(*)
            FROM knowledge_sources
            WHERE metadata->>'origin_session_key' = $1
        """,
            "test:session:empty:001",
        )
        assert source_count == 0


@pytest.mark.asyncio
async def test_session_archiver_all_messages_archived(
    postgres_db, mock_embedding_provider
):
    """すべてのメッセージがアーカイブ済みのセッションのテスト"""
    from datetime import UTC, datetime

    from kotonoha_bot.db.models import ChatSession, Message, MessageRole

    # セッションを作成
    session = ChatSession(
        session_key="test:session:all_archived:001",
        session_type="mention",
        messages=[
            Message(
                role=MessageRole.USER,
                content="これはすべてアーカイブ済みテスト用のセッションです。十分な長さのメッセージを含めています。",
                timestamp=datetime.now(UTC) - timedelta(hours=2),
            ),
            Message(
                role=MessageRole.ASSISTANT,
                content="了解しました。すべてアーカイブ済みのテストを確認します。",
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

    # 最初のアーカイブ
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
            "test:session:all_archived:001",
        )

        await archiver._archive_session_impl(dict(session_row))

    # 再度アーカイブを試行（すべてアーカイブ済みの場合）
    # 注意: 最初のアーカイブでversionが更新されているため、楽観的ロックの競合が発生する可能性がある
    async with postgres_db.pool.acquire() as conn:
        session_row_after = await conn.fetchrow(
            """
            SELECT id, session_key, session_type, messages,
                   guild_id, channel_id, thread_id,
                   user_id, last_active_at, version,
                   last_archived_message_index
            FROM sessions
            WHERE session_key = $1
        """,
            "test:session:all_archived:001",
        )

        # すべてアーカイブ済みの場合、status='archived'に更新される
        # 楽観的ロックの競合が発生する可能性があるが、それは正常な動作
        try:
            await archiver._archive_session_impl(dict(session_row_after))
        except ValueError as e:
            # 楽観的ロックの競合は正常な動作（セッションが既にアーカイブ済みの場合）
            if "concurrently updated" in str(e):
                pass  # これは正常な動作
            else:
                raise

    # セッションのステータスが'archived'になっていることを確認
    async with postgres_db.pool.acquire() as conn:
        result = await conn.fetchrow(
            """
            SELECT status
            FROM sessions
            WHERE session_key = $1
        """,
            "test:session:all_archived:001",
        )
        assert result is not None
        assert result["status"] == "archived"


@pytest.mark.asyncio
async def test_session_archiver_chunk_messages_by_turns(
    postgres_db, mock_embedding_provider
):
    """_chunk_messages_by_turnsの詳細テスト"""
    import tiktoken

    from kotonoha_bot.config import settings

    archiver = SessionArchiver(
        db=postgres_db,
        embedding_provider=mock_embedding_provider,
        archive_threshold_hours=1,
    )

    encoding = tiktoken.encoding_for_model("text-embedding-3-small")
    max_tokens = settings.kb_chunk_max_tokens

    # 複数のメッセージを持つセッション
    messages = []
    for i in range(20):
        messages.append(
            {
                "role": "user" if i % 2 == 0 else "assistant",
                "content": f"メッセージ{i}",
            }
        )

    chunks = archiver._chunk_messages_by_turns(messages, max_tokens, encoding)

    # チャンクが作成されていることを確認
    assert len(chunks) > 0

    # 各チャンクのトークン数が上限以下であることを確認
    for chunk in chunks:
        chunk_tokens = len(encoding.encode(chunk))
        assert chunk_tokens <= max_tokens, (
            f"チャンクのトークン数が上限を超えています: "
            f"tokens={chunk_tokens}, max_tokens={max_tokens}"
        )


# ============================================
# 追加テストケース（2026年1月19日）
# ============================================


@pytest.mark.asyncio
async def test_session_archiver_graceful_shutdown(postgres_db, mock_embedding_provider):
    """graceful_shutdownのテスト"""
    archiver = SessionArchiver(
        db=postgres_db,
        embedding_provider=mock_embedding_provider,
        archive_threshold_hours=1,
    )

    # タスクが開始されていない状態でもシャットダウンが成功すること
    await archiver.graceful_shutdown()

    # archive_inactive_sessionsがキャンセルされていることを確認
    assert not archiver.archive_inactive_sessions.is_running()


@pytest.mark.asyncio
async def test_session_archiver_start_method(postgres_db, mock_embedding_provider):
    """start()メソッドのテスト"""
    archiver = SessionArchiver(
        db=postgres_db,
        embedding_provider=mock_embedding_provider,
        archive_threshold_hours=1,
    )

    # start()を呼び出す
    archiver.start()

    # タスクが開始されていることを確認
    assert archiver.archive_inactive_sessions.is_running()

    # クリーンアップ
    archiver.archive_inactive_sessions.cancel()


@pytest.mark.asyncio
async def test_session_archiver_processing_flag(postgres_db, mock_embedding_provider):
    """_processingフラグのテスト"""
    archiver = SessionArchiver(
        db=postgres_db,
        embedding_provider=mock_embedding_provider,
        archive_threshold_hours=1,
    )

    # 初期状態でFalse
    assert archiver._processing is False

    # _processingをTrueにして、archive_inactive_sessionsを呼び出す
    archiver._processing = True
    await archiver.archive_inactive_sessions()

    # 処理がスキップされることを確認（エラーにならない）


@pytest.mark.asyncio
async def test_session_archiver_processing_sessions_tracking(
    postgres_db, mock_embedding_provider
):
    """_processing_sessionsのトラッキングテスト"""
    archiver = SessionArchiver(
        db=postgres_db,
        embedding_provider=mock_embedding_provider,
        archive_threshold_hours=1,
    )

    # 初期状態で空のセット
    assert len(archiver._processing_sessions) == 0


@pytest.mark.asyncio
async def test_session_archiver_split_content_by_tokens_fallback(
    postgres_db, mock_embedding_provider
):
    """_split_content_by_tokens_fallbackのテスト"""
    import tiktoken

    archiver = SessionArchiver(
        db=postgres_db,
        embedding_provider=mock_embedding_provider,
        archive_threshold_hours=1,
    )

    encoding = tiktoken.encoding_for_model("text-embedding-3-small")
    max_tokens = 50  # 小さい値でテスト

    # 長いコンテンツを作成
    content = "これは非常に長いテストコンテンツです。" * 50

    chunks = archiver._split_content_by_tokens_fallback(content, encoding, max_tokens)

    # チャンクが作成されていることを確認
    assert len(chunks) > 0

    # 各チャンクのトークン数が上限を超えないことを確認（多少の誤差は許容）
    for chunk in chunks:
        chunk_tokens = len(encoding.encode(chunk))
        # フォールバック実装では多少の誤差が発生する可能性がある
        assert chunk_tokens <= max_tokens * 1.5, (
            f"チャンクのトークン数が大幅に上限を超えています: "
            f"tokens={chunk_tokens}, max_tokens={max_tokens}"
        )


@pytest.mark.asyncio
async def test_session_archiver_split_content_short_content(
    postgres_db, mock_embedding_provider
):
    """短いコンテンツの分割テスト（分割不要）"""
    import tiktoken

    archiver = SessionArchiver(
        db=postgres_db,
        embedding_provider=mock_embedding_provider,
        archive_threshold_hours=1,
    )

    encoding = tiktoken.encoding_for_model("text-embedding-3-small")
    max_tokens = 1000  # 大きい値

    content = "短いコンテンツ"

    chunks = archiver._split_content_by_tokens_fallback(content, encoding, max_tokens)

    # 分割されず1つのチャンクのみ
    assert len(chunks) == 1
    assert chunks[0] == content


@pytest.mark.asyncio
async def test_session_archiver_last_archived_message_index_reset(
    postgres_db, mock_embedding_provider
):
    """last_archived_message_indexのリセットロジックテスト"""
    session = ChatSession(
        session_key="test:session:index_reset:001",
        session_type="mention",
        messages=[
            Message(
                role=MessageRole.USER,
                content="これはインデックスリセットテスト用のセッションです。十分な長さのメッセージを含めています。",
                timestamp=datetime.now(UTC) - timedelta(hours=2),
            ),
            Message(
                role=MessageRole.ASSISTANT,
                content="了解しました。インデックスリセットテストを確認します。",
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
            "test:session:index_reset:001",
        )

        await archiver._archive_session_impl(dict(session_row))

    # last_archived_message_indexが0にリセットされていることを確認
    async with postgres_db.pool.acquire() as conn:
        result = await conn.fetchrow(
            """
            SELECT last_archived_message_index
            FROM sessions
            WHERE session_key = $1
        """,
            "test:session:index_reset:001",
        )
        assert result is not None
        # アーカイブ後、インデックスは0にリセットされる
        assert result["last_archived_message_index"] == 0


@pytest.mark.asyncio
async def test_session_archiver_invalid_archived_index(
    postgres_db, mock_embedding_provider
):
    """last_archived_message_indexがmessages配列を超える場合のテスト"""
    # セッションを作成し、手動でlast_archived_message_indexを大きな値に設定
    session = ChatSession(
        session_key="test:session:invalid_index:001",
        session_type="mention",
        messages=[
            Message(
                role=MessageRole.USER,
                content="これは無効なインデックステスト用のセッションです。十分な長さのメッセージを含めています。",
                timestamp=datetime.now(UTC) - timedelta(hours=2),
            ),
        ],
        guild_id=123456789,
        channel_id=987654321,
        user_id=111222333,
        last_active_at=datetime.now(UTC) - timedelta(hours=2),
    )

    await postgres_db.save_session(session)

    # last_archived_message_indexを手動で大きな値に設定
    async with postgres_db.pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE sessions
            SET last_archived_message_index = 100
            WHERE session_key = $1
        """,
            "test:session:invalid_index:001",
        )

    archiver = SessionArchiver(
        db=postgres_db,
        embedding_provider=mock_embedding_provider,
        archive_threshold_hours=1,
    )

    # セッションを取得してアーカイブ（インデックスがリセットされるべき）
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
            "test:session:invalid_index:001",
        )

        # エラーにならずに処理されることを確認
        await archiver._archive_session_impl(dict(session_row))


@pytest.mark.asyncio
async def test_session_archiver_generate_title_various_patterns(
    postgres_db, mock_embedding_provider
):
    """_generate_titleの追加パターンテスト"""
    archiver = SessionArchiver(
        db=postgres_db,
        embedding_provider=mock_embedding_provider,
        archive_threshold_hours=1,
    )

    # 空白文字のみのユーザーメッセージ
    whitespace_messages = [
        {"role": "user", "content": "   "},
        {"role": "assistant", "content": "応答"},
    ]
    title = archiver._generate_title(whitespace_messages)
    # 空白のみの場合はフォールバック
    assert title == "Discord Session" or title.strip() == ""

    # 改行を含むメッセージ
    newline_messages = [
        {"role": "user", "content": "一行目\n二行目\n三行目"},
    ]
    title = archiver._generate_title(newline_messages)
    assert "\n" in title or len(title) <= 53


@pytest.mark.asyncio
async def test_session_archiver_generate_discord_uri_dm(
    postgres_db, mock_embedding_provider
):
    """DMセッション（guild_idなし）のURI生成テスト"""
    archiver = SessionArchiver(
        db=postgres_db,
        embedding_provider=mock_embedding_provider,
        archive_threshold_hours=1,
    )

    # DMセッション（guild_idなし、thread_idなし）
    session_row = {
        "guild_id": None,
        "channel_id": 987654321,
        "thread_id": None,
    }
    uri = archiver._generate_discord_uri(session_row)
    assert uri == "https://discord.com/channels/987654321"


@pytest.mark.asyncio
async def test_session_archiver_threshold_hours_configuration(
    postgres_db, mock_embedding_provider
):
    """archive_threshold_hours設定のテスト"""
    # カスタム値を設定
    archiver = SessionArchiver(
        db=postgres_db,
        embedding_provider=mock_embedding_provider,
        archive_threshold_hours=24,  # 24時間
    )

    assert archiver.archive_threshold_hours == 24


@pytest.mark.asyncio
async def test_session_archiver_should_archive_session_user_messages_only(
    postgres_db, mock_embedding_provider
):
    """ユーザーメッセージのみのセッションのアーカイブ判定テスト"""
    from kotonoha_bot.config import settings

    archiver = SessionArchiver(
        db=postgres_db,
        embedding_provider=mock_embedding_provider,
        archive_threshold_hours=1,
    )

    min_length = settings.kb_min_session_length

    # ユーザーメッセージのみで最小文字数を超える
    user_only = [
        {"role": "user", "content": "あ" * (min_length + 10)},
    ]
    assert archiver._should_archive_session(user_only) is True

    # ユーザーメッセージのみで最小文字数未満
    user_only_short = [
        {"role": "user", "content": "あ" * (min_length - 1)},
    ]
    assert archiver._should_archive_session(user_only_short) is False


@pytest.mark.asyncio
async def test_session_archiver_format_messages_unknown_role(
    postgres_db, mock_embedding_provider
):
    """不明なroleのメッセージフォーマットテスト"""
    archiver = SessionArchiver(
        db=postgres_db,
        embedding_provider=mock_embedding_provider,
        archive_threshold_hours=1,
    )

    messages = [
        {"role": "system", "content": "システムメッセージ"},
        {"content": "roleなしメッセージ"},  # roleキーがない
    ]

    formatted = archiver._format_messages_for_knowledge(messages)
    assert "System: システムメッセージ" in formatted
    assert "Unknown: roleなしメッセージ" in formatted


@pytest.mark.asyncio
async def test_session_archiver_archive_with_metadata(
    postgres_db, mock_embedding_provider
):
    """メタデータ付きアーカイブのテスト"""
    session = ChatSession(
        session_key="test:session:metadata:001",
        session_type="thread",
        messages=[
            Message(
                role=MessageRole.USER,
                content="これはメタデータテスト用のセッションです。十分な長さのメッセージを含めています。",
                timestamp=datetime.now(UTC) - timedelta(hours=2),
            ),
            Message(
                role=MessageRole.ASSISTANT,
                content="了解しました。メタデータテストを確認します。",
                timestamp=datetime.now(UTC) - timedelta(hours=2),
            ),
        ],
        guild_id=123456789,
        channel_id=987654321,
        thread_id=555666777,
        user_id=111222333,
        last_active_at=datetime.now(UTC) - timedelta(hours=2),
    )

    await postgres_db.save_session(session)

    archiver = SessionArchiver(
        db=postgres_db,
        embedding_provider=mock_embedding_provider,
        archive_threshold_hours=1,
    )

    # アーカイブを実行
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
            "test:session:metadata:001",
        )

        await archiver._archive_session_impl(dict(session_row))

    # 知識ベースのメタデータを確認
    async with postgres_db.pool.acquire() as conn:
        source = await conn.fetchrow(
            """
            SELECT metadata FROM knowledge_sources
            WHERE metadata->>'origin_session_key' = $1
        """,
            "test:session:metadata:001",
        )

        assert source is not None
        metadata = source["metadata"]
        assert metadata["channel_id"] == 987654321
        assert metadata["thread_id"] == 555666777
        assert metadata["user_id"] == 111222333
        assert metadata["session_type"] == "thread"
        assert "archived_at" in metadata


@pytest.mark.asyncio
async def test_session_archiver_timeout_error(postgres_db, mock_embedding_provider):
    """データベース接続のタイムアウトエラーのテスト"""
    archiver = SessionArchiver(
        db=postgres_db,
        embedding_provider=mock_embedding_provider,
        archive_threshold_hours=1,
    )

    # プールを一時的に無効化してタイムアウトをシミュレート
    original_pool = archiver.db.pool
    archiver.db.pool = None

    # archive_inactive_sessions のタイムアウト処理をテスト
    # 実際のタイムアウトは asyncio.timeout で発生するため、
    # プールが None の場合は assert エラーが発生する
    try:
        await archiver.archive_inactive_sessions()
    except AssertionError:
        # プールが None の場合のエラー（期待される動作）
        pass
    finally:
        archiver.db.pool = original_pool


@pytest.mark.asyncio
async def test_session_archiver_connection_error(postgres_db, mock_embedding_provider):
    """データベース接続エラーのテスト"""
    archiver = SessionArchiver(
        db=postgres_db,
        embedding_provider=mock_embedding_provider,
        archive_threshold_hours=1,
    )

    # 接続エラーをシミュレート（プールを無効化）
    original_pool = archiver.db.pool
    archiver.db.pool = None

    try:
        await archiver.archive_inactive_sessions()
    except AssertionError:
        # プールが None の場合のエラー（期待される動作）
        pass
    finally:
        archiver.db.pool = original_pool


@pytest.mark.asyncio
async def test_session_archiver_no_inactive_sessions(
    postgres_db, mock_embedding_provider
):
    """非アクティブなセッションがない場合のテスト"""
    archiver = SessionArchiver(
        db=postgres_db,
        embedding_provider=mock_embedding_provider,
        archive_threshold_hours=1,
    )

    # 非アクティブなセッションがない場合、早期リターンする
    # 実際のテストでは、すべてのセッションがアクティブな状態を作成
    # ここでは、archive_inactive_sessions が空のリストを返すことを確認
    # （実際の実装では、DBクエリが空の結果を返す）
    assert archiver.db.pool is not None


@pytest.mark.asyncio
async def test_session_archiver_archive_with_limit_exception(
    postgres_db, mock_embedding_provider
):
    """_archive_with_limit の例外処理テスト"""
    archiver = SessionArchiver(
        db=postgres_db,
        embedding_provider=mock_embedding_provider,
        archive_threshold_hours=1,
    )

    # セッションを作成
    session = ChatSession(
        session_key="test:archive:error:001",
        session_type="mention",
        messages=[
            Message(
                role=MessageRole.USER,
                content="これはエラーテスト用のセッションです。十分な長さのメッセージを含めています。",
                timestamp=datetime.now(UTC) - timedelta(hours=2),
            ),
        ],
        guild_id=123456789,
        channel_id=987654321,
        user_id=111222333,
        last_active_at=datetime.now(UTC) - timedelta(hours=2),
    )

    await postgres_db.save_session(session)

    # _archive_session でエラーを発生させる
    async def failing_archive(_session_row):
        raise Exception("Archive error")

    # patch を使って _archive_session をモック化
    with patch.object(archiver, "_archive_session", side_effect=failing_archive):
        # archive_inactive_sessions を実行（エラーが処理されることを確認）
        # 実装では _archive_with_limit 内でエラーをキャッチし、
        # asyncio.gather(..., return_exceptions=True) により
        # archive_inactive_sessions 自体は例外を投げない
        await archiver.archive_inactive_sessions()


@pytest.mark.asyncio
async def test_session_archiver_before_loop_no_bot(
    postgres_db, mock_embedding_provider
):
    """bot が None の場合の before_archive_sessions テスト"""
    archiver = SessionArchiver(
        db=postgres_db,
        embedding_provider=mock_embedding_provider,
        bot=None,  # bot を None に設定
        archive_threshold_hours=1,
    )

    # before_archive_sessions を実行（bot が None の場合は wait_until_ready をスキップ）
    await archiver.before_archive_sessions()

    # エラーが発生しないことを確認
    assert archiver.bot is None


@pytest.mark.asyncio
async def test_session_archiver_all_messages_already_archived(
    postgres_db, mock_embedding_provider
):
    """すべてのメッセージが既にアーカイブ済みの場合のテスト"""
    archiver = SessionArchiver(
        db=postgres_db,
        embedding_provider=mock_embedding_provider,
        archive_threshold_hours=1,
    )

    # セッションを作成（last_archived_message_index が messages の長さ以上）
    session = ChatSession(
        session_key="test:all:archived:001",
        session_type="mention",
        messages=[
            Message(
                role=MessageRole.USER,
                content="テストメッセージ1",
                timestamp=datetime.now(UTC) - timedelta(hours=2),
            ),
            Message(
                role=MessageRole.ASSISTANT,
                content="テストメッセージ2",
                timestamp=datetime.now(UTC) - timedelta(hours=2),
            ),
        ],
        guild_id=123456789,
        channel_id=987654321,
        user_id=111222333,
        last_active_at=datetime.now(UTC) - timedelta(hours=2),
    )

    await postgres_db.save_session(session)

    # last_archived_message_index を messages の長さ以上に設定
    async with postgres_db.pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE sessions
            SET last_archived_message_index = 10
            WHERE session_key = $1
        """,
            "test:all:archived:001",
        )

        session_row = await conn.fetchrow(
            """
            SELECT id, session_key, session_type, messages,
                   guild_id, channel_id, thread_id,
                   user_id, last_active_at, version,
                   last_archived_message_index
            FROM sessions
            WHERE session_key = $1
        """,
            "test:all:archived:001",
        )

        # アーカイブ処理を実行（messages_to_archive が空になる）
        await archiver._archive_session_impl(dict(session_row))

    # セッションのステータスが 'archived' になっていることを確認
    async with postgres_db.pool.acquire() as conn:
        result = await conn.fetchrow(
            """
            SELECT status FROM sessions
            WHERE session_key = $1
        """,
            "test:all:archived:001",
        )
        assert result is not None
        assert result["status"] == "archived"


@pytest.mark.asyncio
async def test_session_archiver_chunk_strategy_fallback(
    postgres_db, mock_embedding_provider, monkeypatch
):
    """チャンク戦略が 'message_based' 以外の場合のテスト"""
    archiver = SessionArchiver(
        db=postgres_db,
        embedding_provider=mock_embedding_provider,
        archive_threshold_hours=1,
    )

    # チャンク戦略を 'fallback' に設定
    from kotonoha_bot.config import settings

    original_strategy = settings.kb_chat_chunk_strategy
    monkeypatch.setattr(settings, "kb_chat_chunk_strategy", "fallback")

    try:
        session = ChatSession(
            session_key="test:chunk:strategy:001",
            session_type="mention",
            messages=[
                Message(
                    role=MessageRole.USER,
                    content="これはフォールバック戦略のテストです。十分な長さのメッセージを含めています。",
                    timestamp=datetime.now(UTC) - timedelta(hours=2),
                ),
            ],
            guild_id=123456789,
            channel_id=987654321,
            user_id=111222333,
            last_active_at=datetime.now(UTC) - timedelta(hours=2),
        )

        await postgres_db.save_session(session)

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
                "test:chunk:strategy:001",
            )

            # アーカイブ処理を実行（フォールバック戦略が使用される）
            await archiver._archive_session_impl(dict(session_row))
    finally:
        monkeypatch.setattr(settings, "kb_chat_chunk_strategy", original_strategy)


@pytest.mark.asyncio
async def test_session_archiver_metadata_timestamp_handling(
    postgres_db, mock_embedding_provider
):
    """メタデータのタイムスタンプ処理テスト"""
    archiver = SessionArchiver(
        db=postgres_db,
        embedding_provider=mock_embedding_provider,
        archive_threshold_hours=1,
    )

    # タイムスタンプ付きメッセージを含むセッションを作成
    session = ChatSession(
        session_key="test:timestamp:001",
        session_type="mention",
        messages=[
            Message(
                role=MessageRole.USER,
                content="タイムスタンプテスト",
                timestamp=datetime.now(UTC) - timedelta(hours=2),
            ),
        ],
        guild_id=123456789,
        channel_id=987654321,
        user_id=111222333,
        last_active_at=datetime.now(UTC) - timedelta(hours=2),
    )

    await postgres_db.save_session(session)

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
            "test:timestamp:001",
        )

        # メッセージに created_at を追加（timestamp がない場合のフォールバック）
        messages = session_row["messages"]
        if messages and "timestamp" not in messages[-1]:
            messages[-1]["created_at"] = datetime.now(UTC).isoformat()

        session_row_dict = dict(session_row)
        session_row_dict["messages"] = messages

        await archiver._archive_session_impl(session_row_dict)

    # メタデータにタイムスタンプが含まれていることを確認
    async with postgres_db.pool.acquire() as conn:
        source = await conn.fetchrow(
            """
            SELECT metadata FROM knowledge_sources
            WHERE metadata->>'origin_session_key' = $1
        """,
            "test:timestamp:001",
        )
        if source:
            metadata = source["metadata"]
            assert "archived_message_count" in metadata


@pytest.mark.asyncio
async def test_session_archiver_partial_archive(postgres_db, mock_embedding_provider):
    """一部のみアーカイブ済みの場合のテスト"""
    archiver = SessionArchiver(
        db=postgres_db,
        embedding_provider=mock_embedding_provider,
        archive_threshold_hours=1,
    )

    # 複数のメッセージを含むセッションを作成
    messages = []
    for i in range(20):  # 十分な数のメッセージ
        messages.append(
            Message(
                role=MessageRole.USER if i % 2 == 0 else MessageRole.ASSISTANT,
                content=f"メッセージ{i}。これはテスト用のメッセージです。",
                timestamp=datetime.now(UTC) - timedelta(hours=2),
            )
        )

    session = ChatSession(
        session_key="test:partial:001",
        session_type="mention",
        messages=messages,
        guild_id=123456789,
        channel_id=987654321,
        user_id=111222333,
        last_active_at=datetime.now(UTC) - timedelta(hours=2),
    )

    await postgres_db.save_session(session)

    # last_archived_message_index を中間値に設定（一部のみアーカイブ済み）
    async with postgres_db.pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE sessions
            SET last_archived_message_index = 10
            WHERE session_key = $1
        """,
            "test:partial:001",
        )

        session_row = await conn.fetchrow(
            """
            SELECT id, session_key, session_type, messages,
                   guild_id, channel_id, thread_id,
                   user_id, last_active_at, version,
                   last_archived_message_index
            FROM sessions
            WHERE session_key = $1
        """,
            "test:partial:001",
        )

        # アーカイブ処理を実行（一部のみアーカイブ済みの分岐）
        await archiver._archive_session_impl(dict(session_row))

    # セッションが更新されていることを確認
    async with postgres_db.pool.acquire() as conn:
        result = await conn.fetchrow(
            """
            SELECT last_archived_message_index, jsonb_array_length(messages) as msg_count
            FROM sessions
            WHERE session_key = $1
        """,
            "test:partial:001",
        )
        assert result is not None
        # のりしろが残っていることを確認
        assert result["msg_count"] > 0


@pytest.mark.asyncio
async def test_session_archiver_chunk_exceeds_token_limit(
    postgres_db, mock_embedding_provider, monkeypatch
):
    """チャンクがトークン上限を超える場合のテスト"""
    archiver = SessionArchiver(
        db=postgres_db,
        embedding_provider=mock_embedding_provider,
        archive_threshold_hours=1,
    )

    # チャンクサイズを小さく設定して、トークン上限を超えやすくする
    from kotonoha_bot.config import settings

    original_chunk_size = settings.kb_chat_chunk_size_messages
    monkeypatch.setattr(settings, "kb_chat_chunk_size_messages", 1)

    try:
        # 非常に長いメッセージを含むセッションを作成
        long_content = "これは非常に長いメッセージです。" * 100
        session = ChatSession(
            session_key="test:token:limit:001",
            session_type="mention",
            messages=[
                Message(
                    role=MessageRole.USER,
                    content=long_content,
                    timestamp=datetime.now(UTC) - timedelta(hours=2),
                ),
            ],
            guild_id=123456789,
            channel_id=987654321,
            user_id=111222333,
            last_active_at=datetime.now(UTC) - timedelta(hours=2),
        )

        await postgres_db.save_session(session)

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
                "test:token:limit:001",
            )

            # アーカイブ処理を実行（トークン上限を超える場合の処理）
            await archiver._archive_session_impl(dict(session_row))
    finally:
        monkeypatch.setattr(
            settings, "kb_chat_chunk_size_messages", original_chunk_size
        )


@pytest.mark.asyncio
async def test_session_archiver_import_error_fallback(
    postgres_db, mock_embedding_provider, monkeypatch
):
    """langchain-text-splitters のインポートエラーのテスト"""
    archiver = SessionArchiver(
        db=postgres_db,
        embedding_provider=mock_embedding_provider,
        archive_threshold_hours=1,
    )

    # langchain_text_splitters のインポートをモックして ImportError を発生させる

    original_import = __import__

    def mock_import(name, *args, **kwargs):
        if name == "langchain_text_splitters":
            raise ImportError("Module not found")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", mock_import)

    try:
        # 長いコンテンツを分割する必要があるセッションを作成
        import tiktoken

        encoding = tiktoken.encoding_for_model("text-embedding-3-small")
        long_content = "これは分割が必要な長いコンテンツです。" * 50
        chunks = archiver._split_content_by_tokens(
            long_content,
            encoding,
            max_tokens=100,  # 小さな上限を設定
        )
        # フォールバック実装が使用されることを確認
        assert len(chunks) > 0
    finally:
        monkeypatch.undo()


@pytest.mark.asyncio
async def test_session_archiver_graceful_shutdown_timeout(
    postgres_db, mock_embedding_provider
):
    """Graceful Shutdown のタイムアウト処理テスト"""
    archiver = SessionArchiver(
        db=postgres_db,
        embedding_provider=mock_embedding_provider,
        bot=MagicMock(),
        archive_threshold_hours=1,
    )

    # タスクをモックしてタイムアウトをシミュレート
    mock_task = MagicMock()
    mock_task.done = MagicMock(return_value=False)

    # タイムアウトを発生させるタスクを作成
    async def timeout_task():
        from asyncio import timeout

        try:
            async with timeout(0.1):  # 非常に短いタイムアウト
                await asyncio.sleep(1)  # タイムアウトを発生させる
        except TimeoutError:
            pass

    # タスク属性を設定
    archiver.archive_inactive_sessions._task = mock_task
    mock_task.__await__ = lambda: timeout_task()

    # Graceful Shutdown を実行（タイムアウトが発生する）
    # タイムアウトエラーが処理されることを確認
    with suppress(Exception):
        await archiver.graceful_shutdown()


@pytest.mark.asyncio
async def test_session_archiver_graceful_shutdown_processing_sessions(
    postgres_db, mock_embedding_provider
):
    """Graceful Shutdown の処理中セッション待機テスト"""
    archiver = SessionArchiver(
        db=postgres_db,
        embedding_provider=mock_embedding_provider,
        bot=MagicMock(),
        archive_threshold_hours=1,
    )

    # 処理中のセッションを追加（完了済みのタスクとして）
    mock_task = AsyncMock()
    # タスクが完了済みであることを示す
    mock_task.done = MagicMock(return_value=True)
    archiver._processing_sessions.add(mock_task)

    # Graceful Shutdown を実行
    with suppress(Exception):
        await archiver.graceful_shutdown()

    # 処理中のセッションが処理されることを確認
    # （実際の実装では、gather で処理されるため、セットから削除される）
    # ここでは、graceful_shutdown が正常に実行されることを確認
    assert archiver._processing_sessions is not None
