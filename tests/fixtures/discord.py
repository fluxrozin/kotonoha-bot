"""Discord モック用ユーティリティ."""

from unittest.mock import AsyncMock, MagicMock

import discord

from kotonoha_bot.bot.client import KotonohaBot


def create_mock_message(
    content: str = "test message",
    author_id: int = 123456789,
    channel_id: int = 987654321,
    author_bot: bool = False,
    mentions: list | None = None,
    guild_id: int | None = None,
    thread: discord.Thread | None = None,
) -> MagicMock:
    """モックメッセージを作成.

    Args:
        content: メッセージ内容
        author_id: 送信者ID
        channel_id: チャンネルID
        author_bot: Botかどうか
        mentions: メンションリスト
        guild_id: ギルドID
        thread: スレッド（オプション）

    Returns:
        Discord メッセージのモック
    """
    message = MagicMock(spec=discord.Message)
    message.content = content
    message.author.id = author_id
    message.author.bot = author_bot
    message.author.display_name = "TestUser"
    message.author.mention = f"<@{author_id}>"
    message.channel.id = channel_id
    message.channel.typing = MagicMock(return_value=AsyncMock())
    message.channel.send = AsyncMock()
    message.channel.fetch_message = AsyncMock()
    message.mentions = mentions or []
    message.reply = AsyncMock()
    message.create_thread = AsyncMock()
    message.guild = MagicMock() if guild_id else None
    if message.guild:
        message.guild.id = guild_id
    message.thread = thread
    message.id = 111111111111111111
    return message


def create_mock_bot(user_id: int = 999999999) -> MagicMock:
    """モックBotを作成.

    Args:
        user_id: BotのユーザーID

    Returns:
        Discord Botのモック
    """
    bot = MagicMock(spec=KotonohaBot)
    bot.user = MagicMock()
    bot.user.id = user_id
    bot.user.mention = f"<@{user_id}>"
    bot.is_ready = MagicMock(return_value=True)
    bot.is_closed = MagicMock(return_value=False)
    bot.wait_until_ready = AsyncMock()
    bot.close = AsyncMock()
    bot.start = AsyncMock()
    bot.process_commands = AsyncMock()
    bot.tree = MagicMock()
    bot.tree.sync = AsyncMock(return_value=[])
    bot.guilds = []
    return bot


def create_mock_channel(
    channel_id: int = 987654321,
    channel_type: type = discord.TextChannel,
) -> MagicMock:
    """モックチャンネルを作成.

    Args:
        channel_id: チャンネルID
        channel_type: チャンネルタイプ（discord.TextChannel など）

    Returns:
        Discord チャンネルのモック
    """
    channel = MagicMock(spec=channel_type)
    channel.id = channel_id
    channel.typing = MagicMock(return_value=AsyncMock())
    channel.send = AsyncMock()
    channel.fetch_message = AsyncMock()
    return channel
