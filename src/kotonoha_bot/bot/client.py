"""Discord Bot Client."""

import logging

import discord
from discord.ext import commands

from ..config import Config

logger = logging.getLogger(__name__)


class KotonohaBot(commands.Bot):
    """Kotonoha Discord Bot."""

    def __init__(self, config: Config | None = None):
        """KotonohaBot を初期化.

        Args:
            config: 設定インスタンス（依存性注入、必須）

        Raises:
            ValueError: config が None の場合
        """
        if config is None:
            raise ValueError("config parameter is required (DI pattern)")
        self.config = config
        intents = discord.Intents.default()
        intents.message_content = True  # メッセージ内容を読み取る権限
        intents.messages = True
        intents.guilds = True

        super().__init__(
            command_prefix=self.config.BOT_PREFIX,
            intents=intents,
            help_command=None,  # デフォルトのhelpコマンドを無効化
        )

    async def on_ready(self):
        """Bot起動時."""
        if self.user is None:
            logger.error("Bot user is None in on_ready event")
            return
        logger.info(f"Logged in as {self.user} (ID: {self.user.id})")
        logger.info(f"Connected to {len(self.guilds)} guilds")

        # ステータス設定
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.listening, name="@メンション"
            )
        )

    async def on_error(self, event_method: str, *_args, **_kwargs):
        """エラーハンドリング."""
        logger.exception(f"Error in {event_method}")
