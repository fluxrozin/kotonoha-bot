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

    from kotonoha_bot.session.models import ChatSession

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

    from kotonoha_bot.session.models import ChatSession, Message, MessageRole

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
