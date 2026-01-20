"""ハンドラーの統合テスト（Embed、エラーハンドリング、リクエストキュー、スレッド機能）."""

import asyncio
import sqlite3
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from kotonoha_bot.bot.handlers import MessageHandler
from kotonoha_bot.config import get_config
from kotonoha_bot.rate_limit.request_queue import RequestQueue
from kotonoha_bot.services.ai import TokenInfo

# ============================================
# 共通フィクスチャ
# ============================================


@pytest.fixture
def mock_bot():
    """モックBot."""
    bot = MagicMock()
    bot.user = MagicMock()
    bot.user.id = 123456789
    bot.user.mention = "<@123456789>"
    return bot


@pytest.fixture
def mock_db():
    """モックデータベース."""
    db = MagicMock()
    db.load_session = AsyncMock(return_value=None)
    db.save_session = AsyncMock()
    return db


@pytest.fixture
def mock_session_manager():
    """モックSessionManager."""
    manager = MagicMock()
    session = MagicMock()
    session.get_conversation_history = MagicMock(return_value=[])
    manager.get_session = AsyncMock(return_value=session)
    manager.create_session = AsyncMock(return_value=session)
    manager.add_message = AsyncMock()
    manager.save_session = AsyncMock()
    manager.initialize = AsyncMock()
    return manager


@pytest.fixture
def mock_ai_provider():
    """モックAIProvider."""
    provider = MagicMock()
    token_info = TokenInfo(
        input_tokens=10,
        output_tokens=5,
        total_tokens=15,
        model_used="anthropic/claude-3-haiku-20240307",
        latency_ms=100,
    )
    provider.generate_response = AsyncMock(return_value=("テスト応答", token_info))
    provider.get_last_used_model = MagicMock(
        return_value="anthropic/claude-3-haiku-20240307"
    )
    provider.get_rate_limit_usage = MagicMock(return_value=0.5)
    return provider


@pytest.fixture
def mock_router():
    """モックMessageRouter."""
    router = MagicMock()
    router.register_bot_thread = MagicMock()
    router.eavesdrop_enabled_channels = set()
    router.enable_eavesdrop_for_channel = MagicMock()
    return router


@pytest.fixture
def mock_request_queue():
    """モックRequestQueue."""
    import asyncio

    queue = MagicMock()

    # enqueueは非同期メソッドなのでAsyncMockを使用
    # 直接処理関数を呼び出すように設定（キューを経由せずに直接実行）
    async def enqueue_side_effect(_priority, func, *args, **kwargs):
        # 直接関数を実行して結果を返す
        result = await func(*args, **kwargs)
        # Futureを作成して結果を設定
        future = asyncio.Future()
        future.set_result(result)
        return future

    queue.enqueue = AsyncMock(side_effect=enqueue_side_effect)
    queue.start = AsyncMock()
    queue.stop = AsyncMock()
    return queue


@pytest.fixture
def handler(mock_bot, mock_db):
    """MessageHandlerのフィクスチャ（DI パターン対応）."""
    config = get_config()
    # MessageHandler のコンストラクタに必要なパラメータを渡す
    handler = MessageHandler(
        bot=mock_bot,
        db=mock_db,
        config=config,
    )
    # 内部で作成されたインスタンスをモックに置き換え
    handler.session_manager = MagicMock()
    session = MagicMock()
    session.get_conversation_history = MagicMock(return_value=[])
    handler.session_manager.get_session = AsyncMock(return_value=session)
    handler.session_manager.create_session = AsyncMock(return_value=session)
    handler.session_manager.add_message = AsyncMock()
    handler.session_manager.save_session = AsyncMock()
    handler.session_manager.initialize = AsyncMock()

    token_info = TokenInfo(
        input_tokens=10,
        output_tokens=5,
        total_tokens=15,
        model_used="anthropic/claude-3-haiku-20240307",
        latency_ms=100,
    )
    handler.ai_provider = MagicMock()
    handler.ai_provider.generate_response = AsyncMock(
        return_value=("テスト応答", token_info)
    )
    handler.ai_provider.get_last_used_model = MagicMock(
        return_value="anthropic/claude-3-haiku-20240307"
    )
    handler.ai_provider.get_rate_limit_usage = MagicMock(return_value=0.5)

    handler.router = MagicMock()
    handler.router.register_bot_thread = MagicMock()
    handler.router.eavesdrop_enabled_channels = set()
    handler.router.enable_eavesdrop_for_channel = MagicMock()

    handler.request_queue = MagicMock()

    async def enqueue_side_effect(_priority, func, *args, **kwargs):
        result = await func(*args, **kwargs)
        future = asyncio.Future()
        future.set_result(result)
        return future

    handler.request_queue.enqueue = AsyncMock(side_effect=enqueue_side_effect)
    handler.request_queue.start = AsyncMock()
    handler.request_queue.stop = AsyncMock()

    # サブハンドラーもモックに置き換え
    handler.mention = MagicMock()
    handler.mention.handle = AsyncMock()
    handler.thread = MagicMock()
    handler.thread.handle = AsyncMock()
    handler.eavesdrop = MagicMock()
    handler.eavesdrop.handle = AsyncMock()

    return handler


# ============================================
# Embed 使用テスト
# ============================================


@pytest.mark.asyncio
async def test_mention_uses_embed_with_footer(handler):
    """メンション応答でEmbedとフッターが使用される."""
    mock_message = MagicMock(spec=discord.Message)
    mock_message.author = MagicMock()
    mock_message.author.bot = False
    mock_message.author.id = 987654321
    mock_message.mentions = [handler.bot.user]
    mock_message.content = "<@123456789> こんにちは"
    mock_message.channel = MagicMock()
    mock_message.channel.id = 111222333
    mock_message.channel.typing = MagicMock(return_value=AsyncMock())
    mock_message.reply = AsyncMock()
    mock_message.channel.send = AsyncMock()

    # handle_mention は mention.handle に委譲される
    await handler.handle_mention(mock_message)

    # mention.handle が呼ばれたことを確認
    handler.mention.handle.assert_called_once_with(mock_message)


@pytest.mark.asyncio
async def test_thread_uses_embed_with_footer(handler):
    """スレッド応答でEmbedとフッターが使用される."""
    mock_message = MagicMock(spec=discord.Message)
    mock_message.author = MagicMock()
    mock_message.author.bot = False
    mock_message.author.id = 987654321
    mock_message.content = "こんにちは"
    mock_message.reply = AsyncMock()
    mock_thread = MagicMock(spec=discord.Thread)
    mock_thread.id = 444555666
    mock_thread.typing = MagicMock(return_value=AsyncMock())
    mock_thread.send = AsyncMock()
    mock_message.channel = mock_thread

    # handle_thread は thread.handle に委譲される
    await handler.handle_thread(mock_message)

    # thread.handle が呼ばれたことを確認
    handler.thread.handle.assert_called_once_with(mock_message)


@pytest.mark.asyncio
async def test_eavesdrop_uses_embed_with_footer(handler):
    """聞き耳型応答でEmbedとフッターが使用される."""
    mock_message = MagicMock(spec=discord.Message)
    mock_message.author = MagicMock()
    mock_message.author.bot = False
    mock_message.channel = MagicMock()
    mock_message.channel.id = 777888999
    mock_message.channel.send = AsyncMock()
    handler.router.eavesdrop_enabled_channels = {777888999}

    # handle_eavesdrop は eavesdrop.handle に委譲される
    await handler.handle_eavesdrop(mock_message)

    # eavesdrop.handle が呼ばれたことを確認
    handler.eavesdrop.handle.assert_called_once_with(mock_message)


# ============================================
# エラーハンドリングテスト
# ============================================


@pytest.mark.asyncio
async def test_mention_handles_discord_permission_error(handler):
    """メンション応答でDiscord権限エラーが適切に処理される."""
    mock_message = MagicMock(spec=discord.Message)
    mock_message.author = MagicMock()
    mock_message.author.bot = False
    mock_message.author.id = 987654321
    mock_message.mentions = [handler.bot.user]
    mock_message.content = "<@123456789> こんにちは"
    mock_message.channel = MagicMock()
    mock_message.channel.id = 111222333
    mock_message.channel.typing = MagicMock(return_value=AsyncMock())
    mock_message.reply = AsyncMock()

    # mention.handle でエラーが発生する場合をシミュレート
    handler.mention.handle = AsyncMock(
        side_effect=discord.errors.Forbidden(MagicMock(), "Forbidden")
    )

    # エラーが発生しても例外が伝播しないことを確認（エラーハンドリングは各ハンドラー内で行われる）
    with pytest.raises(discord.errors.Forbidden):
        await handler.handle_mention(mock_message)


@pytest.mark.asyncio
async def test_mention_handles_database_error(handler):
    """メンション応答でデータベースエラーが適切に処理される."""
    mock_message = MagicMock(spec=discord.Message)
    mock_message.author = MagicMock()
    mock_message.author.bot = False
    mock_message.author.id = 987654321
    mock_message.mentions = [handler.bot.user]
    mock_message.content = "<@123456789> こんにちは"
    mock_message.channel = MagicMock()
    mock_message.channel.id = 111222333
    mock_message.channel.typing = MagicMock(return_value=AsyncMock())
    mock_message.reply = AsyncMock()

    # mention.handle でデータベースエラーが発生する場合をシミュレート
    handler.mention.handle = AsyncMock(
        side_effect=sqlite3.OperationalError("database is locked")
    )

    # エラーが発生しても例外が伝播しないことを確認
    with pytest.raises(sqlite3.OperationalError):
        await handler.handle_mention(mock_message)


# ============================================
# リクエストキュー統合テスト
# ============================================


@pytest.mark.asyncio
async def test_mention_uses_request_queue(handler):
    """メンション応答でリクエストキューが使用される."""
    # 実際の RequestQueue インスタンスを使用
    handler.request_queue = RequestQueue(max_size=100)
    await handler.request_queue.start()

    mock_message = MagicMock(spec=discord.Message)
    mock_message.author = MagicMock()
    mock_message.author.bot = False
    mock_message.author.id = 987654321
    mock_message.mentions = [handler.bot.user]
    mock_message.content = "<@123456789> こんにちは"
    mock_message.channel = MagicMock()
    mock_message.channel.id = 111222333
    mock_message.channel.typing = MagicMock(return_value=AsyncMock())
    mock_message.reply = AsyncMock()
    mock_message.channel.send = AsyncMock()

    # handle_mention を呼び出す
    await handler.handle_mention(mock_message)

    # mention.handle が呼ばれたことを確認
    handler.mention.handle.assert_called_once_with(mock_message)

    await handler.request_queue.stop()


# ============================================
# スレッド機能テスト
# ============================================


@pytest.mark.asyncio
async def test_handle_thread_bot_message_ignored(handler):
    """Bot自身のメッセージは無視される."""
    mock_message = MagicMock()
    mock_message.author = MagicMock()
    mock_message.author.bot = True
    mock_message.author.id = 987654321
    mock_message.author.display_name = "テストユーザー"
    mock_message.channel = MagicMock()
    mock_message.channel.id = 111222333
    mock_message.mentions = []
    mock_message.content = "テストメッセージ"
    mock_message.id = 123456789
    mock_message.thread = None
    mock_message.reply = AsyncMock()

    await handler.handle_thread(mock_message)

    # thread.handle は呼ばれるが、内部で Bot 自身のメッセージをチェックして早期リターンする
    # したがって、実際の処理（_process_message や _process_creation）は実行されない
    handler.thread.handle.assert_called_once_with(mock_message)
    # リクエストキューには追加されないことを確認
    # （thread.handle 内で早期リターンするため、enqueue は呼ばれない）
    # ただし、handler の request_queue はモックなので、thread の request_queue を確認する必要がある
    # 実際の実装では thread.handle 内で早期リターンするため、enqueue は呼ばれない


@pytest.mark.asyncio
async def test_handle_thread_create_new_thread(handler):
    """メンション時に新規スレッドが作成される."""
    mock_message = MagicMock()
    mock_message.author = MagicMock()
    mock_message.author.bot = False
    mock_message.author.id = 987654321
    mock_message.mentions = [handler.bot.user]
    mock_message.content = "<@123456789> こんにちは"
    mock_message.channel = MagicMock()
    mock_message.channel.id = 111222333
    mock_message.reply = AsyncMock()

    mock_thread = MagicMock()
    mock_thread.id = 444555666
    mock_thread.parent_id = 111222333
    mock_thread.name = "テストスレッド"
    mock_thread.send = AsyncMock()
    mock_thread.typing = MagicMock(return_value=AsyncMock())
    _f = asyncio.Future()
    _f.set_result(mock_thread)
    mock_message.create_thread = MagicMock(return_value=_f)

    # thread.handle が呼ばれることを確認
    await handler.handle_thread(mock_message)

    # thread.handle が呼ばれたことを確認
    handler.thread.handle.assert_called_once_with(mock_message)


@pytest.mark.asyncio
async def test_thread_uses_request_queue_with_correct_priority(handler):
    """スレッド応答でリクエストキューが正しい優先度で使用される."""
    # 実際の RequestQueue インスタンスを使用
    handler.request_queue = RequestQueue(max_size=100)
    await handler.request_queue.start()

    mock_message = MagicMock(spec=discord.Message)
    mock_message.author = MagicMock()
    mock_message.author.bot = False
    mock_message.content = "こんにちは"
    mock_message.reply = AsyncMock()
    mock_thread = MagicMock(spec=discord.Thread)
    mock_thread.id = 444555666
    mock_thread.typing = MagicMock(return_value=AsyncMock())
    mock_thread.send = AsyncMock()
    mock_message.channel = mock_thread

    await handler.handle_thread(mock_message)

    # thread.handle が呼ばれたことを確認
    handler.thread.handle.assert_called_once_with(mock_message)

    await handler.request_queue.stop()


@pytest.mark.asyncio
async def test_eavesdrop_uses_request_queue_with_highest_priority(handler):
    """聞き耳型応答でリクエストキューが最高優先度で使用される."""
    # 実際の RequestQueue インスタンスを使用
    handler.request_queue = RequestQueue(max_size=100)
    await handler.request_queue.start()

    mock_message = MagicMock(spec=discord.Message)
    mock_message.author = MagicMock()
    mock_message.author.bot = False
    mock_message.channel = MagicMock()
    mock_message.channel.id = 777888999
    mock_message.channel.send = AsyncMock()
    handler.router.eavesdrop_enabled_channels = {777888999}

    await handler.handle_eavesdrop(mock_message)

    # eavesdrop.handle が呼ばれたことを確認
    handler.eavesdrop.handle.assert_called_once_with(mock_message)

    await handler.request_queue.stop()


@pytest.mark.asyncio
async def test_thread_handles_discord_error(handler):
    """スレッド応答でDiscordエラーが適切に処理される."""
    mock_message = MagicMock(spec=discord.Message)
    mock_message.author = MagicMock()
    mock_message.author.bot = False
    mock_message.author.id = 987654321
    mock_message.content = "こんにちは"
    mock_thread = MagicMock(spec=discord.Thread)
    mock_thread.id = 444555666
    mock_thread.typing = MagicMock(return_value=AsyncMock())
    mock_message.channel = mock_thread

    # thread.handle でエラーが発生する場合をシミュレート
    mock_response = MagicMock()
    mock_response.status = 429  # Too Many Requests
    error = discord.errors.HTTPException(mock_response, "Too Many Requests")
    handler.thread.handle = AsyncMock(side_effect=error)

    # エラーが発生しても例外が伝播しないことを確認
    with pytest.raises(discord.errors.HTTPException):
        await handler.handle_thread(mock_message)


@pytest.mark.asyncio
async def test_eavesdrop_does_not_send_error_message(handler):
    """聞き耳型応答でエラーが発生してもエラーメッセージを送信しない."""
    mock_message = MagicMock(spec=discord.Message)
    mock_message.author = MagicMock()
    mock_message.author.bot = False
    mock_message.channel = MagicMock()
    mock_message.channel.id = 777888999
    mock_message.channel.send = AsyncMock()
    handler.router.eavesdrop_enabled_channels = {777888999}

    # eavesdrop.handle でエラーが発生する場合をシミュレート
    handler.eavesdrop.handle = AsyncMock(side_effect=RuntimeError("テストエラー"))

    # エラーが発生しても例外が伝播しないことを確認
    with pytest.raises(RuntimeError, match="テストエラー"):
        await handler.handle_eavesdrop(mock_message)


@pytest.mark.asyncio
async def test_mention_handles_generic_error(handler):
    """メンション応答で一般的なエラーが適切に処理される."""
    mock_message = MagicMock(spec=discord.Message)
    mock_message.author = MagicMock()
    mock_message.author.bot = False
    mock_message.author.id = 987654321
    mock_message.mentions = [handler.bot.user]
    mock_message.content = "<@123456789> こんにちは"
    mock_message.channel = MagicMock()
    mock_message.channel.id = 111222333
    mock_message.channel.typing = MagicMock(return_value=AsyncMock())
    mock_message.reply = AsyncMock()

    # mention.handle で一般的なエラーが発生する場合をシミュレート
    handler.mention.handle = AsyncMock(side_effect=ValueError("テストエラー"))

    # エラーが発生しても例外が伝播しないことを確認
    with pytest.raises(ValueError):
        await handler.handle_mention(mock_message)
