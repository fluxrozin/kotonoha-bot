"""聞き耳型: 会話ログバッファ"""

import logging
from collections import deque

import discord

logger = logging.getLogger(__name__)


class ConversationBuffer:
    """会話ログバッファ

    チャンネルごとの会話ログを一時保存する。
    """

    def __init__(self, max_size: int = 20):
        self.buffers: dict[int, deque[discord.Message]] = {}
        self.max_size = max_size

    def add_message(self, channel_id: int, message: discord.Message) -> None:
        """メッセージを追加

        Args:
            channel_id: チャンネル ID
            message: Discord メッセージ
        """
        if channel_id not in self.buffers:
            self.buffers[channel_id] = deque(maxlen=self.max_size)

        self.buffers[channel_id].append(message)

    def get_recent_messages(
        self, channel_id: int, limit: int | None = None
    ) -> list[discord.Message]:
        """直近のメッセージを取得

        Args:
            channel_id: チャンネル ID
            limit: 取得件数（None の場合は全て）

        Returns:
            メッセージリスト
        """
        if channel_id not in self.buffers:
            return []

        messages = list(self.buffers[channel_id])
        if limit:
            return messages[-limit:]
        return messages

    def clear(self, channel_id: int) -> None:
        """バッファをクリア

        Args:
            channel_id: チャンネル ID
        """
        if channel_id in self.buffers:
            del self.buffers[channel_id]
