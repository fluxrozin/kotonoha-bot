"""テストデータファクトリー（polyfactory を使用）。"""

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from polyfactory.factories.dataclass_factory import DataclassFactory

if TYPE_CHECKING:
    from kotonoha_bot.db.models import ChatSession, Message, MessageRole, SessionType
else:
    from kotonoha_bot.db.models import ChatSession, Message, MessageRole, SessionType


class MessageFactory(DataclassFactory[Message]):
    """Message のテストデータを生成（polyfactory を使用）。

    Note:
        polyfactory が型ヒントを解析して、自動的にランダムな値を埋めてくれます。
        特定の値だけ固定したい場合のみ記述します。
    """

    __model__ = Message

    @classmethod
    def create_user_message(cls, content: str = "test message") -> Message:
        """ユーザーメッセージを生成.

        Args:
            content: メッセージ内容

        Returns:
            ユーザーメッセージ
        """
        return cls.build(role=MessageRole.USER, content=content)

    @classmethod
    def create_assistant_message(cls, content: str = "test response") -> Message:
        """アシスタントメッセージを生成.

        Args:
            content: メッセージ内容

        Returns:
            アシスタントメッセージ
        """
        return cls.build(role=MessageRole.ASSISTANT, content=content)


class SessionFactory(DataclassFactory[ChatSession]):
    """ChatSession のテストデータを生成（polyfactory を使用）。

    Note:
        polyfactory が型ヒントを解析して、自動的にランダムな値を埋めてくれます。
        特定の値だけ固定したい場合のみ記述します。
    """

    __model__ = ChatSession

    # デフォルト値を固定したい場合のみ記述
    session_key: str = "test_session_123"
    session_type: SessionType = "mention"
    channel_id: int = 123456789
    user_id: int = 987654321
    created_at: datetime = datetime.now(UTC)
    last_active_at: datetime = datetime.now(UTC)

    @classmethod
    def create_with_history(
        cls,
        session_key: str,
        message_count: int = 5,
        **kwargs,
    ) -> ChatSession:
        """会話履歴を持つ ChatSession を生成.

        Args:
            session_key: セッションキー
            message_count: メッセージ数
            **kwargs: その他のパラメータ

        Returns:
            会話履歴を持つ ChatSession
        """
        messages = []
        for i in range(message_count):
            role = MessageRole.USER if i % 2 == 0 else MessageRole.ASSISTANT
            messages.append(
                Message(
                    role=role,
                    content=f"メッセージ {i + 1}",
                    timestamp=datetime.now(UTC),
                )
            )

        return cls.build(session_key=session_key, messages=messages, **kwargs)
