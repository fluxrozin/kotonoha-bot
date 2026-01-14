"""セッション管理のデータモデル"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Literal
from enum import Enum


class MessageRole(str, Enum):
    """メッセージの役割"""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


@dataclass
class Message:
    """メッセージ"""
    role: MessageRole
    content: str
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        """辞書形式に変換"""
        return {
            "role": self.role.value,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Message":
        """辞書から作成"""
        return cls(
            role=MessageRole(data["role"]),
            content=data["content"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
        )


SessionType = Literal["mention", "thread", "eavesdrop"]


@dataclass
class ChatSession:
    """チャットセッション"""
    session_key: str
    session_type: SessionType
    messages: List[Message] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    last_active_at: datetime = field(default_factory=datetime.now)

    # メタデータ
    channel_id: int | None = None
    thread_id: int | None = None
    user_id: int | None = None

    def add_message(self, role: MessageRole, content: str) -> None:
        """メッセージを追加"""
        message = Message(role=role, content=content)
        self.messages.append(message)
        self.last_active_at = datetime.now()

    def get_conversation_history(self, limit: int | None = None) -> List[Message]:
        """会話履歴を取得"""
        if limit:
            return self.messages[-limit:]
        return self.messages

    def to_dict(self) -> dict:
        """辞書形式に変換"""
        return {
            "session_key": self.session_key,
            "session_type": self.session_type,
            "messages": [msg.to_dict() for msg in self.messages],
            "created_at": self.created_at.isoformat(),
            "last_active_at": self.last_active_at.isoformat(),
            "channel_id": self.channel_id,
            "thread_id": self.thread_id,
            "user_id": self.user_id,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ChatSession":
        """辞書から作成"""
        messages = [Message.from_dict(msg) for msg in data["messages"]]
        return cls(
            session_key=data["session_key"],
            session_type=data["session_type"],
            messages=messages,
            created_at=datetime.fromisoformat(data["created_at"]),
            last_active_at=datetime.fromisoformat(data["last_active_at"]),
            channel_id=data.get("channel_id"),
            thread_id=data.get("thread_id"),
            user_id=data.get("user_id"),
        )
