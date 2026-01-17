"""スラッシュコマンドのテスト"""

from unittest.mock import AsyncMock, MagicMock

import discord
import pytest
from discord.ext import commands

from kotonoha_bot.commands.chat import ChatCommands
from kotonoha_bot.session.models import ChatSession


@pytest.fixture
def mock_bot():
    """モックBot"""
    bot = MagicMock(spec=commands.Bot)
    bot.tree = MagicMock()
    bot.tree.sync = AsyncMock(return_value=[])
    return bot


@pytest.fixture
def mock_handler():
    """モックMessageHandler"""
    handler = MagicMock()
    handler.session_manager = MagicMock()
    handler.session_manager.get_session = AsyncMock()
    handler.session_manager.save_session = AsyncMock()
    handler.router = MagicMock()
    handler.router.register_bot_thread = MagicMock()
    return handler


@pytest.fixture
def chat_commands(mock_bot, mock_handler):
    """ChatCommandsのフィクスチャ"""
    return ChatCommands(mock_bot, mock_handler)


@pytest.mark.asyncio
async def test_chat_reset_thread(chat_commands, mock_handler):
    """/chat reset コマンド（スレッド内）"""
    # モックの設定
    interaction = MagicMock(spec=discord.Interaction)
    interaction.response = MagicMock()
    interaction.response.defer = AsyncMock()
    interaction.followup = MagicMock()
    interaction.followup.send = AsyncMock()
    interaction.channel = MagicMock(spec=discord.Thread)
    interaction.channel.id = 111222333

    # セッションのモック
    mock_session = MagicMock(spec=ChatSession)
    mock_session.messages = [MagicMock(), MagicMock()]
    mock_handler.session_manager.get_session.return_value = mock_session

    # コマンドを実行
    method = (
        chat_commands.chat_reset.callback
        if hasattr(chat_commands.chat_reset, "callback")
        else chat_commands.chat_reset
    )
    await method(chat_commands, interaction)

    # 検証
    interaction.response.defer.assert_called_once_with(ephemeral=True)
    assert len(mock_session.messages) == 0
    mock_handler.session_manager.save_session.assert_called_once()


@pytest.mark.asyncio
async def test_chat_reset_no_session(chat_commands, mock_handler):
    """/chat reset コマンド（セッションが見つからない場合）"""
    # モックの設定
    interaction = MagicMock(spec=discord.Interaction)
    interaction.response = MagicMock()
    interaction.response.defer = AsyncMock()
    interaction.followup = MagicMock()
    interaction.followup.send = AsyncMock()
    interaction.channel = MagicMock(spec=discord.Thread)
    interaction.channel.id = 111222333

    # セッションが見つからない場合
    mock_handler.session_manager.get_session.return_value = None

    # コマンドを実行
    method = (
        chat_commands.chat_reset.callback
        if hasattr(chat_commands.chat_reset, "callback")
        else chat_commands.chat_reset
    )
    await method(chat_commands, interaction)

    # 検証
    interaction.followup.send.assert_called_once()
    call_args = interaction.followup.send.call_args
    assert "会話履歴が見つかりませんでした" in call_args[0][0]


@pytest.mark.asyncio
async def test_chat_status_thread(chat_commands, mock_handler):
    """/chat status コマンド（スレッド内）"""
    # モックの設定
    interaction = MagicMock(spec=discord.Interaction)
    interaction.response = MagicMock()
    interaction.response.defer = AsyncMock()
    interaction.followup = MagicMock()
    interaction.followup.send = AsyncMock()
    interaction.channel = MagicMock(spec=discord.Thread)
    interaction.channel.id = 111222333

    # セッションのモック
    from datetime import datetime

    mock_session = MagicMock(spec=ChatSession)
    mock_session.get_conversation_history = MagicMock(
        return_value=[MagicMock(), MagicMock(), MagicMock()]
    )
    mock_session.created_at = datetime(2026, 1, 15, 10, 30, 0)
    mock_handler.session_manager.get_session.return_value = mock_session

    # コマンドを実行
    method = (
        chat_commands.chat_status.callback
        if hasattr(chat_commands.chat_status, "callback")
        else chat_commands.chat_status
    )
    await method(chat_commands, interaction)

    # 検証
    interaction.response.defer.assert_called_once_with(ephemeral=True)
    interaction.followup.send.assert_called_once()
    call_args = interaction.followup.send.call_args
    assert "スレッド型" in call_args[0][0]
    assert "3件" in call_args[0][0]


@pytest.mark.asyncio
async def test_chat_status_mention(chat_commands, mock_handler):
    """/chat status コマンド（メンション応答型）"""
    # モックの設定
    interaction = MagicMock(spec=discord.Interaction)
    interaction.response = MagicMock()
    interaction.response.defer = AsyncMock()
    interaction.followup = MagicMock()
    interaction.followup.send = AsyncMock()
    interaction.channel = MagicMock(spec=discord.TextChannel)
    interaction.user = MagicMock()
    interaction.user.id = 987654321

    # セッションのモック
    from datetime import datetime

    mock_session = MagicMock(spec=ChatSession)
    mock_session.get_conversation_history = MagicMock(return_value=[])
    mock_session.created_at = datetime(2026, 1, 15, 10, 30, 0)
    mock_handler.session_manager.get_session.return_value = mock_session

    # コマンドを実行
    method = (
        chat_commands.chat_status.callback
        if hasattr(chat_commands.chat_status, "callback")
        else chat_commands.chat_status
    )
    await method(chat_commands, interaction)

    # 検証
    call_args = interaction.followup.send.call_args
    assert "メンション応答型" in call_args[0][0]
