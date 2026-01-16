"""ハンドラーのエラーハンドリング統合テスト"""

import sqlite3
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
    return handler


@pytest.mark.asyncio
async def test_mention_handles_discord_permission_error(handler):
    """メンション応答でDiscord権限エラーが適切に処理される"""
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
    # 最初のreply呼び出し（embed送信）でエラーを発生させる
    error = discord.errors.Forbidden(MagicMock(), "Forbidden")
    mock_message.reply = AsyncMock(side_effect=[error, None])

    with (
        patch("kotonoha_bot.bot.handlers.split_message") as mock_split,
        patch("kotonoha_bot.bot.handlers.format_split_messages") as mock_format,
    ):
        mock_split.return_value = ["テスト応答"]
        mock_format.return_value = ["テスト応答"]

        await handler._process_mention(mock_message)

        # エラーメッセージが送信されたことを確認
        mock_message.reply.assert_called()
        # エラーメッセージの内容を確認（権限エラーのメッセージ）
        call_args = mock_message.reply.call_args
        error_message = call_args.args[0] if call_args.args else None
        assert error_message is not None
        assert "権限" in error_message or "サーバー管理者" in error_message


@pytest.mark.asyncio
async def test_mention_handles_database_error(handler):
    """メンション応答でデータベースエラーが適切に処理される"""
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

    # データベースエラーを発生させる
    handler.session_manager.save_session = MagicMock(
        side_effect=sqlite3.OperationalError("database is locked")
    )

    with (
        patch("kotonoha_bot.bot.handlers.split_message") as mock_split,
        patch("kotonoha_bot.bot.handlers.format_split_messages") as mock_format,
    ):
        mock_split.return_value = ["テスト応答"]
        mock_format.return_value = ["テスト応答"]

        await handler._process_mention(mock_message)

        # エラーメッセージが送信されたことを確認
        mock_message.reply.assert_called()
        # エラーメッセージの内容を確認（データベースエラーのメッセージ）
        call_args = mock_message.reply.call_args
        error_message = call_args.args[0] if call_args.args else None
        assert error_message is not None
        assert "データベース" in error_message


@pytest.mark.asyncio
async def test_thread_handles_discord_error(handler):
    """スレッド応答でDiscordエラーが適切に処理される"""
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
    # 最初のreply呼び出し（embed送信）でエラーを発生させる
    # HTTPExceptionのモックを作成（status属性を持つ）
    mock_response = MagicMock()
    mock_response.status = 429  # Too Many Requests
    error = discord.errors.HTTPException(mock_response, "Too Many Requests")
    mock_message.reply = AsyncMock(side_effect=error)
    mock_thread.send = AsyncMock()
    mock_message.channel = mock_thread

    with (
        patch("kotonoha_bot.bot.handlers.split_message") as mock_split,
        patch("kotonoha_bot.bot.handlers.format_split_messages") as mock_format,
    ):
        mock_split.return_value = ["テスト応答"]
        mock_format.return_value = ["テスト応答"]

        await handler._process_thread_message(mock_message)

        # エラーメッセージが送信されたことを確認
        mock_message.reply.assert_called()
        # エラーメッセージの内容を確認（レート制限エラーのメッセージ）
        call_args = mock_message.reply.call_args
        error_message = call_args.args[0] if call_args.args else None
        assert error_message is not None
        assert "リクエストが多すぎる" in error_message or "すみません" in error_message


@pytest.mark.asyncio
async def test_eavesdrop_does_not_send_error_message(handler):
    """聞き耳型応答でエラーが発生してもエラーメッセージを送信しない"""
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
    handler.llm_judge.generate_response = AsyncMock(
        side_effect=Exception("テストエラー")
    )

    await handler._process_eavesdrop(mock_message)

    # エラーメッセージが送信されていないことを確認
    # （聞き耳型ではエラーメッセージを送信しない）
    # 通常の応答メッセージも送信されていないことを確認
    mock_message.channel.send.assert_not_called()


@pytest.mark.asyncio
async def test_mention_handles_generic_error(handler):
    """メンション応答で一般的なエラーが適切に処理される"""
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

    # 一般的なエラーを発生させる
    handler.ai_provider.generate_response = AsyncMock(
        side_effect=ValueError("テストエラー")
    )

    with (
        patch("kotonoha_bot.bot.handlers.split_message") as mock_split,
        patch("kotonoha_bot.bot.handlers.format_split_messages") as mock_format,
    ):
        mock_split.return_value = ["テスト応答"]
        mock_format.return_value = ["テスト応答"]

        await handler._process_mention(mock_message)

        # エラーメッセージが送信されたことを確認
        mock_message.reply.assert_called()
        # エラーメッセージの内容を確認（一般的なエラーのメッセージ）
        call_args = mock_message.reply.call_args
        error_message = call_args.args[0] if call_args.args else None
        assert error_message is not None
        assert (
            "すみません" in error_message
            or "一時的に反応できませんでした" in error_message
        )
