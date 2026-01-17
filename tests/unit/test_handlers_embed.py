"""ハンドラーのEmbed使用テスト"""

from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest

from kotonoha_bot.bot.handlers import MessageHandler


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
    manager.get_session = AsyncMock(return_value=session)
    manager.create_session = AsyncMock(return_value=session)
    manager.add_message = AsyncMock()
    manager.save_session = AsyncMock()
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
    return handler


@pytest.mark.asyncio
async def test_mention_uses_embed_with_footer(handler):
    """メンション応答でEmbedとフッターが使用される"""
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

        await handler._process_mention(mock_message)

        # replyが呼ばれていることを確認
        mock_message.reply.assert_called_once()
        # Embedが使用されていることを確認
        call_args = mock_message.reply.call_args
        assert "embed" in call_args.kwargs
        embed = call_args.kwargs["embed"]
        assert isinstance(embed, discord.Embed)
        # フッターにモデル名が含まれていることを確認
        assert "Model:" in embed.footer.text
        assert "anthropic/claude-3-haiku-20240307" in embed.footer.text


@pytest.mark.asyncio
async def test_thread_uses_embed_with_footer(handler):
    """スレッド応答でEmbedとフッターが使用される"""
    mock_message = MagicMock(spec=discord.Message)
    mock_message.author = MagicMock()
    mock_message.author.bot = False
    mock_message.author.id = 987654321
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

        await handler._process_thread_message(mock_message)

        # message.replyが呼ばれていることを確認
        mock_message.reply.assert_called_once()
        # Embedが使用されていることを確認
        call_args = mock_message.reply.call_args
        assert "embed" in call_args.kwargs
        embed = call_args.kwargs["embed"]
        assert isinstance(embed, discord.Embed)
        # フッターにモデル名が含まれていることを確認
        assert "Model:" in embed.footer.text
        assert "anthropic/claude-3-haiku-20240307" in embed.footer.text


@pytest.mark.asyncio
async def test_eavesdrop_uses_embed_with_footer(handler):
    """聞き耳型応答でEmbedとフッターが使用される"""
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

        await handler._process_eavesdrop(mock_message)

        # channel.sendが呼ばれていることを確認
        mock_message.channel.send.assert_called()
        # Embedが使用されていることを確認
        call_args = mock_message.channel.send.call_args
        assert "embed" in call_args.kwargs
        embed = call_args.kwargs["embed"]
        assert isinstance(embed, discord.Embed)
        # フッターにモデル名が含まれていることを確認
        assert "Model:" in embed.footer.text
        assert "anthropic/claude-3-haiku-20240307" in embed.footer.text


@pytest.mark.asyncio
async def test_mention_message_splitting_first_embed_rest_plain(handler):
    """メンション応答でメッセージ分割時、最初のみEmbed、残りは通常メッセージ"""
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
        # メッセージが3つに分割される場合
        mock_split.return_value = [
            "最初のメッセージ",
            "2番目のメッセージ",
            "3番目のメッセージ",
        ]
        mock_format.return_value = [
            "最初のメッセージ",
            "2番目のメッセージ",
            "3番目のメッセージ",
        ]

        await handler._process_mention(mock_message)

        # 最初のメッセージはEmbedでreply
        mock_message.reply.assert_called_once()
        reply_call = mock_message.reply.call_args
        assert "embed" in reply_call.kwargs
        assert isinstance(reply_call.kwargs["embed"], discord.Embed)

        # 残りのメッセージは通常のメッセージとして送信
        assert mock_message.channel.send.call_count == 2
        send_calls = mock_message.channel.send.call_args_list
        for call in send_calls:
            # Embedは使用されていない（通常のメッセージ）
            assert "embed" not in call.kwargs or call.kwargs.get("embed") is None


@pytest.mark.asyncio
async def test_thread_message_splitting_first_embed_rest_plain(handler):
    """スレッド応答でメッセージ分割時、最初のみEmbed、残りは通常メッセージ"""
    mock_message = MagicMock(spec=discord.Message)
    mock_message.author = MagicMock()
    mock_message.author.bot = False
    mock_message.author.id = 987654321
    mock_message.content = "こんにちは"
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
        # メッセージが3つに分割される場合
        mock_split.return_value = [
            "最初のメッセージ",
            "2番目のメッセージ",
            "3番目のメッセージ",
        ]
        mock_format.return_value = [
            "最初のメッセージ",
            "2番目のメッセージ",
            "3番目のメッセージ",
        ]

        await handler._process_thread_message(mock_message)

        # 最初のメッセージはEmbedでreply
        mock_message.reply.assert_called_once()
        reply_call = mock_message.reply.call_args
        assert "embed" in reply_call.kwargs
        assert isinstance(reply_call.kwargs["embed"], discord.Embed)

        # 残りのメッセージは通常のメッセージとして送信
        assert mock_thread.send.call_count == 2
        send_calls = mock_thread.send.call_args_list
        for call in send_calls:
            # Embedは使用されていない（通常のメッセージ）
            assert "embed" not in call.kwargs or call.kwargs.get("embed") is None


@pytest.mark.asyncio
async def test_eavesdrop_message_splitting_first_embed_rest_plain(handler):
    """聞き耳型応答でメッセージ分割時、最初のみEmbed、残りは通常メッセージ"""
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
        # メッセージが3つに分割される場合
        mock_split.return_value = [
            "最初のメッセージ",
            "2番目のメッセージ",
            "3番目のメッセージ",
        ]
        mock_format.return_value = [
            "最初のメッセージ",
            "2番目のメッセージ",
            "3番目のメッセージ",
        ]

        await handler._process_eavesdrop(mock_message)

        # 最初のメッセージはEmbedで送信
        send_calls = mock_message.channel.send.call_args_list
        first_call = send_calls[0]
        assert "embed" in first_call.kwargs
        assert isinstance(first_call.kwargs["embed"], discord.Embed)

        # 残りのメッセージは通常のメッセージとして送信
        for call in send_calls[1:]:
            # Embedは使用されていない（通常のメッセージ）
            assert "embed" not in call.kwargs or call.kwargs.get("embed") is None
