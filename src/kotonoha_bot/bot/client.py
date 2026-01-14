"""Discord Bot Client"""
import discord
from discord.ext import commands
import logging

from ..config import Config

logger = logging.getLogger(__name__)


class KotonohaBot(commands.Bot):
    """Kotonoha Discord Bot"""

    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True  # メッセージ内容を読み取る権限
        intents.messages = True
        intents.guilds = True

        super().__init__(
            command_prefix=Config.BOT_PREFIX,
            intents=intents,
            help_command=None,  # デフォルトのhelpコマンドを無効化
        )

    async def on_ready(self):
        """Bot起動時"""
        logger.info(f"Logged in as {self.user} (ID: {self.user.id})")
        logger.info(f"Connected to {len(self.guilds)} guilds")

        # ステータス設定
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.listening,
                name="@メンション"
            )
        )

    async def on_error(self, event_method: str, *args, **kwargs):
        """エラーハンドリング"""
        logger.exception(f"Error in {event_method}")
