"""データモデルのテスト."""

from datetime import datetime

from kotonoha_bot.db.models import ChatSession, Message, MessageRole


class TestMessageRole:
    """MessageRole 列挙型のテスト."""

    def test_message_role_values(self):
        """MessageRole の値が正しい."""
        assert MessageRole.USER.value == "user"
        assert MessageRole.ASSISTANT.value == "assistant"
        assert MessageRole.SYSTEM.value == "system"


class TestMessage:
    """Message データクラスのテスト."""

    def test_message_creation(self):
        """メッセージを作成できる."""
        message = Message(
            role=MessageRole.USER,
            content="テストメッセージ",
        )
        assert message.role == MessageRole.USER
        assert message.content == "テストメッセージ"
        assert isinstance(message.timestamp, datetime)

    def test_message_to_dict(self):
        """メッセージを辞書形式に変換できる."""
        timestamp = datetime(2026, 1, 15, 14, 30, 45)
        message = Message(
            role=MessageRole.ASSISTANT,
            content="応答メッセージ",
            timestamp=timestamp,
        )

        result = message.to_dict()

        assert result["role"] == "assistant"
        assert result["content"] == "応答メッセージ"
        assert result["timestamp"] == timestamp.isoformat()

    def test_message_from_dict(self):
        """辞書からメッセージを作成できる."""
        data = {
            "role": "user",
            "content": "ユーザーメッセージ",
            "timestamp": "2026-01-15T14:30:45",
        }

        message = Message.from_dict(data)

        assert message.role == MessageRole.USER
        assert message.content == "ユーザーメッセージ"
        assert message.timestamp == datetime.fromisoformat("2026-01-15T14:30:45")

    def test_message_round_trip(self):
        """メッセージの往復変換が正しく動作する."""
        original = Message(
            role=MessageRole.SYSTEM,
            content="システムメッセージ",
            timestamp=datetime(2026, 1, 15, 14, 30, 45),
        )

        dict_repr = original.to_dict()
        restored = Message.from_dict(dict_repr)

        assert restored.role == original.role
        assert restored.content == original.content
        assert restored.timestamp == original.timestamp


class TestChatSession:
    """ChatSession データクラスのテスト."""

    def test_chat_session_creation(self):
        """チャットセッションを作成できる."""
        session = ChatSession(
            session_key="test_key",
            session_type="mention",
        )
        assert session.session_key == "test_key"
        assert session.session_type == "mention"
        assert session.messages == []
        assert session.status == "active"
        assert isinstance(session.created_at, datetime)
        assert isinstance(session.last_active_at, datetime)

    def test_chat_session_add_message(self):
        """メッセージを追加できる."""
        session = ChatSession(
            session_key="test_key",
            session_type="thread",
        )
        initial_active_at = session.last_active_at

        session.add_message(MessageRole.USER, "新しいメッセージ")

        assert len(session.messages) == 1
        assert session.messages[0].role == MessageRole.USER
        assert session.messages[0].content == "新しいメッセージ"
        assert session.last_active_at > initial_active_at

    def test_chat_session_get_conversation_history(self):
        """会話履歴を取得できる."""
        session = ChatSession(
            session_key="test_key",
            session_type="eavesdrop",
        )

        # メッセージを追加
        session.add_message(MessageRole.USER, "メッセージ1")
        session.add_message(MessageRole.ASSISTANT, "メッセージ2")
        session.add_message(MessageRole.USER, "メッセージ3")

        # 全履歴を取得
        history = session.get_conversation_history()
        assert len(history) == 3

        # 制限付きで取得
        limited = session.get_conversation_history(limit=2)
        assert len(limited) == 2
        assert limited[0].content == "メッセージ2"
        assert limited[1].content == "メッセージ3"

    def test_chat_session_to_dict(self):
        """チャットセッションを辞書形式に変換できる."""
        session = ChatSession(
            session_key="test_key",
            session_type="mention",
            guild_id=123456789,
            channel_id=987654321,
            user_id=111222333,
        )
        session.add_message(MessageRole.USER, "テスト")

        result = session.to_dict()

        assert result["session_key"] == "test_key"
        assert result["session_type"] == "mention"
        assert result["guild_id"] == 123456789
        assert result["channel_id"] == 987654321
        assert result["user_id"] == 111222333
        assert len(result["messages"]) == 1
        assert result["status"] == "active"
        assert result["version"] == 1

    def test_chat_session_from_dict(self):
        """辞書からチャットセッションを作成できる."""
        data = {
            "session_key": "test_key",
            "session_type": "thread",
            "messages": [
                {
                    "role": "user",
                    "content": "メッセージ1",
                    "timestamp": "2026-01-15T14:30:45",
                },
                {
                    "role": "assistant",
                    "content": "メッセージ2",
                    "timestamp": "2026-01-15T14:31:00",
                },
            ],
            "status": "active",
            "guild_id": 123456789,
            "channel_id": 987654321,
            "user_id": 111222333,
            "version": 2,
            "last_archived_message_index": 0,
            "created_at": "2026-01-15T14:00:00",
            "last_active_at": "2026-01-15T14:31:00",
        }

        session = ChatSession.from_dict(data)

        assert session.session_key == "test_key"
        assert session.session_type == "thread"
        assert len(session.messages) == 2
        assert session.messages[0].content == "メッセージ1"
        assert session.messages[1].content == "メッセージ2"
        assert session.guild_id == 123456789
        assert session.version == 2

    def test_chat_session_round_trip(self):
        """チャットセッションの往復変換が正しく動作する."""
        original = ChatSession(
            session_key="test_key",
            session_type="eavesdrop",
            guild_id=123456789,
            channel_id=987654321,
        )
        original.add_message(MessageRole.USER, "テストメッセージ")
        original.version = 5
        original.last_archived_message_index = 2

        dict_repr = original.to_dict()
        restored = ChatSession.from_dict(dict_repr)

        assert restored.session_key == original.session_key
        assert restored.session_type == original.session_type
        assert restored.guild_id == original.guild_id
        assert restored.channel_id == original.channel_id
        assert len(restored.messages) == len(original.messages)
        assert restored.version == original.version
        assert (
            restored.last_archived_message_index == original.last_archived_message_index
        )

    def test_chat_session_default_values(self):
        """デフォルト値が正しく設定される."""
        session = ChatSession(
            session_key="test_key",
            session_type="mention",
        )

        assert session.status == "active"
        assert session.version == 1
        assert session.last_archived_message_index == 0
        assert session.guild_id is None
        assert session.channel_id is None
        assert session.user_id is None
        assert session.thread_id is None
