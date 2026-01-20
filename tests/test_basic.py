"""基本的なテスト"""

from datetime import datetime

from dirty_equals import IsDatetime

from kotonoha_bot.db.models import ChatSession, Message, MessageRole


def test_message_creation():
    """メッセージの作成テスト"""
    message = Message(
        role=MessageRole.USER,
        content="こんにちは",
    )

    assert message.role == MessageRole.USER
    assert message.content == "こんにちは"
    # dirty-equalsを使用してタイムスタンプをチェック（現在時刻の近似値）
    assert message.timestamp == IsDatetime(approx=datetime.now(), delta=5)


def test_message_serialization():
    """メッセージのシリアライゼーションテスト"""
    message = Message(
        role=MessageRole.ASSISTANT,
        content="こんにちは、お元気ですか？",
    )

    # 辞書に変換
    message_dict = message.to_dict()

    assert message_dict["role"] == "assistant"
    assert message_dict["content"] == "こんにちは、お元気ですか？"
    assert "timestamp" in message_dict

    # 辞書から復元
    restored = Message.from_dict(message_dict)

    assert restored.role == MessageRole.ASSISTANT
    assert restored.content == "こんにちは、お元気ですか？"
    assert restored.timestamp == message.timestamp


def test_session_creation():
    """セッションの作成テスト"""
    session = ChatSession(
        session_key="test:123",
        session_type="mention",
        user_id=123,
    )

    assert session.session_key == "test:123"
    assert session.session_type == "mention"
    assert session.user_id == 123
    assert len(session.messages) == 0
    assert session.status == "active"
    assert session.version == 1
    assert session.last_archived_message_index == 0


def test_session_creation_with_all_fields():
    """セッションの全フィールド指定での作成テスト"""
    session = ChatSession(
        session_key="test:456",
        session_type="thread",
        status="archived",
        guild_id=789,
        channel_id=101112,
        thread_id=131415,
        user_id=161718,
        version=2,
        last_archived_message_index=5,
    )

    assert session.session_key == "test:456"
    assert session.session_type == "thread"
    assert session.status == "archived"
    assert session.guild_id == 789
    assert session.channel_id == 101112
    assert session.thread_id == 131415
    assert session.user_id == 161718
    assert session.version == 2
    assert session.last_archived_message_index == 5


def test_add_message_to_session():
    """セッションへのメッセージ追加テスト"""
    session = ChatSession(
        session_key="test:123",
        session_type="mention",
    )

    initial_active_at = session.last_active_at

    session.add_message(MessageRole.USER, "テストメッセージ")

    assert len(session.messages) == 1
    assert session.messages[0].content == "テストメッセージ"
    assert session.messages[0].role == MessageRole.USER
    # メッセージ追加時に last_active_at が更新されることを確認
    assert session.last_active_at >= initial_active_at


def test_session_serialization():
    """セッションのシリアライゼーションテスト"""
    session = ChatSession(
        session_key="test:123",
        session_type="mention",
        status="active",
        guild_id=100,
        channel_id=200,
        thread_id=300,
        user_id=400,
        version=3,
        last_archived_message_index=2,
    )
    session.add_message(MessageRole.USER, "こんにちは")
    session.add_message(MessageRole.ASSISTANT, "こんにちは！")

    # 辞書に変換
    session_dict = session.to_dict()

    # 基本フィールドの確認
    assert session_dict["session_key"] == "test:123"
    assert session_dict["session_type"] == "mention"
    assert session_dict["status"] == "active"
    assert session_dict["guild_id"] == 100
    assert session_dict["channel_id"] == 200
    assert session_dict["thread_id"] == 300
    assert session_dict["user_id"] == 400
    assert session_dict["version"] == 3
    assert session_dict["last_archived_message_index"] == 2

    # メッセージの確認
    assert len(session_dict["messages"]) == 2
    assert session_dict["messages"][0]["role"] == "user"
    assert session_dict["messages"][0]["content"] == "こんにちは"
    assert session_dict["messages"][1]["role"] == "assistant"
    assert session_dict["messages"][1]["content"] == "こんにちは！"

    # タイムスタンプの存在確認
    assert "created_at" in session_dict
    assert "last_active_at" in session_dict

    # 辞書から復元
    restored = ChatSession.from_dict(session_dict)

    # 全フィールドが正しく復元されることを確認
    assert restored.session_key == session.session_key
    assert restored.session_type == session.session_type
    assert restored.status == session.status
    assert restored.guild_id == session.guild_id
    assert restored.channel_id == session.channel_id
    assert restored.thread_id == session.thread_id
    assert restored.user_id == session.user_id
    assert restored.version == session.version
    assert restored.last_archived_message_index == session.last_archived_message_index
    assert restored.created_at == session.created_at
    assert restored.last_active_at == session.last_active_at

    # メッセージが正しく復元されることを確認
    assert len(restored.messages) == 2
    assert restored.messages[0].role == MessageRole.USER
    assert restored.messages[0].content == "こんにちは"
    assert restored.messages[1].role == MessageRole.ASSISTANT
    assert restored.messages[1].content == "こんにちは！"


def test_get_conversation_history():
    """会話履歴取得のテスト"""
    session = ChatSession(
        session_key="test:789",
        session_type="eavesdrop",
    )

    # メッセージを5つ追加
    for i in range(5):
        session.add_message(MessageRole.USER, f"メッセージ{i}")

    # 制限なしで取得
    all_messages = session.get_conversation_history()
    assert len(all_messages) == 5

    # 制限ありで取得
    recent_messages = session.get_conversation_history(limit=3)
    assert len(recent_messages) == 3
    assert recent_messages[0].content == "メッセージ2"
    assert recent_messages[1].content == "メッセージ3"
    assert recent_messages[2].content == "メッセージ4"
