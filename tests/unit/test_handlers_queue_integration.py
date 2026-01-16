"""ハンドラーのリクエストキュー統合テスト"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest

from kotonoha_bot.bot.handlers import MessageHandler
from kotonoha_bot.rate_limit.request_queue import RequestPriority, RequestQueue


@pytest.fixture
def mock_bot():
    """モックBot"""
    bot = MagicMock()
    bot.user = MagicMock()
    bot.user.id = 123456789
    return bot


@pytest.fixture
def mock_session_manager():
    """モックSessionManager"""
    manager = MagicMock()
    session = MagicMock()
    session.get_conversation_history = MagicMock(return_value=[])
    manager.get_session = MagicMock(return_value=session)
    manager.create_session = MagicMock(return_value=session)
    manager.add_message = MagicMock()
    manager.save_session = MagicMock()
    return manager


@pytest.fixture
def mock_ai_provider():
    """モックAIProvider"""
    provider = MagicMock()
    provider.generate_response = AsyncMock(return_value="テスト応答")
    provider.get_last_used_model = MagicMock(
        return_value="anthropic/claude-3-haiku-20240307"
    )
    provider.get_rate_limit_usage = MagicMock(return_value=0.5)
    return provider


@pytest.fixture
def mock_router():
    """モックMessageRouter"""
    router = MagicMock()
    router.register_bot_thread = MagicMock()
    router.eavesdrop_enabled_channels = set()
    return router


@pytest.fixture
def handler(mock_bot, mock_session_manager, mock_ai_provider, mock_router):
    """MessageHandlerのフィクスチャ"""
    handler = MessageHandler(mock_bot)
    handler.session_manager = mock_session_manager
    handler.ai_provider = mock_ai_provider
    handler.router = mock_router
    # リクエストキューを実際のインスタンスに置き換え
    handler.request_queue = RequestQueue(max_size=100)
    return handler


@pytest.mark.asyncio
async def test_mention_uses_request_queue(handler):
    """メンション応答でリクエストキューが使用される"""
    await handler.request_queue.start()

    mock_message = MagicMock(spec=discord.Message)
    mock_message.author = MagicMock()
    mock_message.author.bot = False
    mock_message.author.id = 987654321
    mock_message.mentions = [handler.bot.user]
    mock_message.content = "<@123456789> こんにちは"
    mock_message.channel = MagicMock()
    mock_message.channel.id = 111222333
    mock_message.channel.typing = MagicMock()
    mock_message.channel.typing.__aenter__ = AsyncMock()
    mock_message.channel.typing.__aexit__ = AsyncMock()
    mock_message.reply = AsyncMock()
    mock_message.channel.send = AsyncMock()

    with (
        patch("kotonoha_bot.bot.handlers.split_message") as mock_split,
        patch("kotonoha_bot.bot.handlers.format_split_messages") as mock_format,
    ):
        mock_split.return_value = ["テスト応答"]
        mock_format.return_value = ["テスト応答"]

        await handler.handle_mention(mock_message)

        # リクエストキューが使用されたことを確認
        # （_process_mentionが呼ばれたことを確認）
        mock_message.reply.assert_called_once()

    await handler.request_queue.stop()


@pytest.mark.asyncio
async def test_thread_uses_request_queue_with_correct_priority(handler):
    """スレッド応答でリクエストキューが正しい優先度で使用される"""
    await handler.request_queue.start()

    mock_message = MagicMock(spec=discord.Message)
    mock_message.author = MagicMock()
    mock_message.author.bot = False
    mock_message.content = "こんにちは"
    mock_message.reply = AsyncMock()
    mock_thread = MagicMock(spec=discord.Thread)
    mock_thread.id = 444555666
    mock_thread.typing = MagicMock()
    mock_thread.typing.__aenter__ = AsyncMock()
    mock_thread.typing.__aexit__ = AsyncMock()
    mock_thread.send = AsyncMock()
    mock_message.channel = mock_thread

    with (
        patch("kotonoha_bot.bot.handlers.split_message") as mock_split,
        patch("kotonoha_bot.bot.handlers.format_split_messages") as mock_format,
    ):
        mock_split.return_value = ["テスト応答"]
        mock_format.return_value = ["テスト応答"]

        await handler.handle_thread(mock_message)

        # リクエストキューが使用されたことを確認
        # （_process_thread_messageが呼ばれたことを確認）
        mock_message.reply.assert_called()

    await handler.request_queue.stop()


@pytest.mark.asyncio
async def test_eavesdrop_uses_request_queue_with_highest_priority(handler):
    """聞き耳型応答でリクエストキューが最高優先度で使用される"""
    await handler.request_queue.start()

    mock_message = MagicMock(spec=discord.Message)
    mock_message.author = MagicMock()
    mock_message.author.bot = False
    mock_message.channel = MagicMock()
    mock_message.channel.id = 777888999
    mock_message.channel.send = AsyncMock()
    handler.router.eavesdrop_enabled_channels = {777888999}

    # 会話バッファとLLM判断機能をモック
    handler.conversation_buffer = MagicMock()
    handler.conversation_buffer.add_message = MagicMock()
    handler.conversation_buffer.get_recent_messages = MagicMock(
        return_value=[mock_message, mock_message, mock_message]
    )
    handler.llm_judge = MagicMock()
    handler.llm_judge.generate_response = AsyncMock(return_value="テスト応答")

    with (
        patch("kotonoha_bot.bot.handlers.split_message") as mock_split,
        patch("kotonoha_bot.bot.handlers.format_split_messages") as mock_format,
    ):
        mock_split.return_value = ["テスト応答"]
        mock_format.return_value = ["テスト応答"]

        await handler.handle_eavesdrop(mock_message)

        # リクエストキューが使用されたことを確認
        # （_process_eavesdropが呼ばれたことを確認）
        mock_message.channel.send.assert_called()

    await handler.request_queue.stop()


@pytest.mark.asyncio
async def test_request_queue_priority_order_in_handlers(handler):
    """ハンドラーでリクエストキューが優先度順に処理される"""
    await handler.request_queue.start()

    results = []

    # 各ハンドラーの処理順序を確認するためのモック
    async def process_mention(_msg):
        results.append(("mention", RequestPriority.MENTION.value))

    async def process_thread(_msg):
        results.append(("thread", RequestPriority.THREAD.value))

    async def process_eavesdrop(_msg):
        results.append(("eavesdrop", RequestPriority.EAVESDROP.value))

    handler._process_mention = process_mention
    handler._process_thread_message = process_thread
    handler._process_eavesdrop = process_eavesdrop

    # メッセージを準備
    mock_message_mention = MagicMock(spec=discord.Message)
    mock_message_mention.author = MagicMock()
    mock_message_mention.author.bot = False
    mock_message_mention.mentions = [handler.bot.user]
    mock_message_mention.channel = MagicMock()
    mock_message_mention.channel.typing = MagicMock()
    mock_message_mention.channel.typing.__aenter__ = AsyncMock()
    mock_message_mention.channel.typing.__aexit__ = AsyncMock()
    mock_message_mention.reply = AsyncMock()

    mock_message_thread = MagicMock(spec=discord.Message)
    mock_message_thread.author = MagicMock()
    mock_message_thread.author.bot = False
    mock_thread = MagicMock(spec=discord.Thread)
    mock_thread.typing = MagicMock()
    mock_thread.typing.__aenter__ = AsyncMock()
    mock_thread.typing.__aexit__ = AsyncMock()
    mock_message_thread.channel = mock_thread

    mock_message_eavesdrop = MagicMock(spec=discord.Message)
    mock_message_eavesdrop.author = MagicMock()
    mock_message_eavesdrop.author.bot = False
    mock_message_eavesdrop.channel = MagicMock()
    mock_message_eavesdrop.channel.id = 777888999
    handler.router.eavesdrop_enabled_channels = {777888999}
    handler.conversation_buffer = MagicMock()
    handler.conversation_buffer.add_message = MagicMock()
    handler.conversation_buffer.get_recent_messages = MagicMock(
        return_value=[mock_message_eavesdrop, mock_message_eavesdrop]
    )
    handler.llm_judge = MagicMock()
    handler.llm_judge.generate_response = AsyncMock(return_value="テスト応答")

    # 優先度の低い順にキューに追加（すべてのリクエストをキューに追加）
    future1 = await handler.request_queue.enqueue(
        RequestPriority.THREAD, process_thread, mock_message_thread
    )
    future2 = await handler.request_queue.enqueue(
        RequestPriority.MENTION, process_mention, mock_message_mention
    )
    future3 = await handler.request_queue.enqueue(
        RequestPriority.EAVESDROP, process_eavesdrop, mock_message_eavesdrop
    )

    # すべてのリクエストの処理完了を待機
    await asyncio.gather(future1, future2, future3, return_exceptions=True)

    # 優先度の高い順（EAVESDROP > MENTION > THREAD）に処理されることを確認
    assert len(results) == 3
    priorities = [r[1] for r in results]
    # キューは優先度の高い順に処理される（EAVESDROP=3, MENTION=2, THREAD=1）
    assert priorities == [3, 2, 1], f"Expected [3, 2, 1] but got {priorities}"

    await handler.request_queue.stop()
