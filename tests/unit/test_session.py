"""セッション管理のテスト"""
import pytest
from kotonoha_bot.session.models import MessageRole


def test_create_session(session_manager):
    """セッションが作成できることを確認"""
    session = session_manager.create_session(
        session_key="test:123",
        session_type="mention",
        user_id=123,
    )

    assert session is not None
    assert session.session_key == "test:123"
    assert session.session_type == "mention"
    assert session.user_id == 123


def test_get_session(session_manager):
    """セッションが取得できることを確認"""
    # セッションを作成
    session_manager.create_session("test:123", "mention")

    # 取得
    session = session_manager.get_session("test:123")
    assert session is not None
    assert session.session_key == "test:123"


def test_add_message(session_manager):
    """メッセージが追加できることを確認"""
    session_manager.create_session("test:123", "mention")
    session_manager.add_message("test:123", MessageRole.USER, "こんにちは")

    session = session_manager.get_session("test:123")
    assert len(session.messages) == 1
    assert session.messages[0].content == "こんにちは"
    assert session.messages[0].role == MessageRole.USER


def test_save_session(session_manager, temp_db_path):
    """セッションが保存できることを確認"""
    session_manager.create_session("test:123", "mention")
    session_manager.add_message("test:123", MessageRole.USER, "テストメッセージ")
    session_manager.save_session("test:123")

    # データベースから直接読み込む
    from kotonoha_bot.db.sqlite import SQLiteDatabase

    new_db = SQLiteDatabase(db_path=temp_db_path)
    loaded_session = new_db.load_session("test:123")
    
    assert loaded_session is not None
    assert loaded_session.session_key == "test:123"
    assert len(loaded_session.messages) == 1
    assert loaded_session.messages[0].content == "テストメッセージ"
