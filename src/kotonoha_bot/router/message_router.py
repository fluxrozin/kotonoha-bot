"""メッセージルーター"""

import logging
from typing import Literal

import discord

logger = logging.getLogger(__name__)

ConversationTrigger = Literal["mention", "thread", "eavesdrop", "none"]


class MessageRouter:
    """メッセージルーター

    メッセージを受信し、会話の契機を判定して適切なハンドラーにルーティングする。
    """

    def __init__(self, bot: discord.Client):
        self.bot = bot
        # スレッド型を有効にするチャンネル（将来的には設定ファイルから読み込む）
        self.thread_enabled_channels: set[int] = set()
        # 聞き耳型を有効にするチャンネル
        self.eavesdrop_enabled_channels: set[int] = set()
        # Botが作成したスレッドのIDを記録
        self.bot_threads: set[int] = set()

    async def route(self, message: discord.Message) -> ConversationTrigger:
        """メッセージをルーティング

        Args:
            message: Discord メッセージ

        Returns:
            会話の契機の種類
        """
        # Bot自身のメッセージは無視
        if message.author.bot:
            return "none"

        # 1. メンション応答型の判定
        if self.bot.user in message.mentions:
            # スレッド型の判定（メンション + スレッド型が有効な場合）
            if await self._should_create_thread(message):
                return "thread"
            return "mention"

        # 2. スレッド型の判定（既存スレッド内での会話）
        if isinstance(message.channel, discord.Thread) and await self._is_bot_thread(
            message.channel
        ):
            return "thread"

        # 3. 聞き耳型の判定
        if await self._should_eavesdrop(message):
            return "eavesdrop"

        return "none"

    async def _should_create_thread(self, message: discord.Message) -> bool:
        """スレッド型を有効にするか判定

        Args:
            message: Discord メッセージ

        Returns:
            スレッド型を有効にする場合 True
        """
        # チャンネルごとの設定を確認
        # 特定のチャンネルが無効化されている場合は False
        if self.thread_enabled_channels:
            return message.channel.id in self.thread_enabled_channels

        # デフォルト: True（スレッド型を有効）
        return True

    async def _is_bot_thread(self, thread: discord.Thread) -> bool:
        """Botによって作成されたスレッドか判定

        Args:
            thread: Discord スレッド

        Returns:
            Botによって作成されたスレッドの場合 True
        """
        # 記録されたスレッドIDを確認
        if thread.id in self.bot_threads:
            return True

        # スレッドの作成者を確認（owner_id が利用可能な場合）
        if (
            hasattr(thread, "owner_id")
            and thread.owner_id is not None
            and self.bot.user
            and self.bot.user.id
        ):
            return thread.owner_id == self.bot.user.id

        # owner_id が None の場合は、owner 属性を確認
        if (
            hasattr(thread, "owner")
            and thread.owner
            and self.bot.user
            and self.bot.user.id
        ):
            return thread.owner.id == self.bot.user.id

        return False

    async def _should_eavesdrop(self, message: discord.Message) -> bool:
        """聞き耳型を有効にするか判定

        Args:
            message: Discord メッセージ

        Returns:
            聞き耳型を有効にする場合 True
        """
        # チャンネルごとの設定を確認
        return message.channel.id in self.eavesdrop_enabled_channels

    def register_bot_thread(self, thread_id: int) -> None:
        """Botが作成したスレッドを記録

        Args:
            thread_id: スレッドID
        """
        self.bot_threads.add(thread_id)
        logger.debug(f"Registered bot thread: {thread_id}")

    def enable_thread_for_channel(self, channel_id: int) -> None:
        """チャンネルでスレッド型を有効化

        Args:
            channel_id: チャンネルID
        """
        self.thread_enabled_channels.add(channel_id)
        logger.info(f"Enabled thread mode for channel: {channel_id}")

    def disable_thread_for_channel(self, channel_id: int) -> None:
        """チャンネルでスレッド型を無効化

        Args:
            channel_id: チャンネルID
        """
        self.thread_enabled_channels.discard(channel_id)
        logger.info(f"Disabled thread mode for channel: {channel_id}")

    def enable_eavesdrop_for_channel(self, channel_id: int) -> None:
        """チャンネルで聞き耳型を有効化

        Args:
            channel_id: チャンネルID
        """
        self.eavesdrop_enabled_channels.add(channel_id)
        logger.info(f"Enabled eavesdrop mode for channel: {channel_id}")

    def disable_eavesdrop_for_channel(self, channel_id: int) -> None:
        """チャンネルで聞き耳型を無効化

        Args:
            channel_id: チャンネルID
        """
        self.eavesdrop_enabled_channels.discard(channel_id)
        logger.info(f"Disabled eavesdrop mode for channel: {channel_id}")
