"""基本的なテスト"""
import pytest
from datetime import datetime

from src.kotonoha_bot.session.models import Message, MessageRole, ChatSession


def test_message_creation():
    """メッセージの作成テスト"""
    message = Message(
        role=MessageRole.USER,
        content="こんにちは",
    )

    assert message.role == MessageRole.USER
    assert message.content == "こんにちは"
    assert isinstance(message.timestamp, datetime)


def test_session_creation():
    """セッションの作成テスト"""
    session = ChatSession(
        session_key="test:123",
        session_type="mention",
        user_id=123,
    )

    assert session.session_key == "test:123"
    assert session.session_type == "mention"
    assert len(session.messages) == 0


def test_add_message_to_session():
    """セッションへのメッセージ追加テスト"""
    session = ChatSession(
        session_key="test:123",
        session_type="mention",
    )

    session.add_message(MessageRole.USER, "テストメッセージ")

    assert len(session.messages) == 1
    assert session.messages[0].content == "テストメッセージ"


def test_session_serialization():
    """セッションのシリアライゼーションテスト"""
    session = ChatSession(
        session_key="test:123",
        session_type="mention",
    )
    session.add_message(MessageRole.USER, "こんにちは")

    # 辞書に変換
    session_dict = session.to_dict()

    # 辞書から復元
    restored = ChatSession.from_dict(session_dict)

    assert restored.session_key == session.session_key
    assert len(restored.messages) == 1
    assert restored.messages[0].content == "こんにちは"
