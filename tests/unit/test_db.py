"""データベースのテスト"""

import pytest

from kotonoha_bot.session.models import ChatSession, MessageRole


@pytest.mark.asyncio
async def test_save_and_load_session(db):
    """セッションの保存と読み込みができることを確認"""
    session = ChatSession(
        session_key="test:123",
        session_type="mention",
        user_id=123,
    )
    session.add_message(MessageRole.USER, "こんにちは")
    session.add_message(MessageRole.ASSISTANT, "こんにちは！")

    # 保存
    await db.save_session(session)

    # 読み込み
    loaded = await db.load_session("test:123")
    assert loaded is not None
    assert loaded.session_key == "test:123"
    assert loaded.session_type == "mention"
    assert loaded.user_id == 123
    assert len(loaded.messages) == 2
    assert loaded.messages[0].content == "こんにちは"
    assert loaded.messages[1].content == "こんにちは！"


@pytest.mark.asyncio
async def test_load_nonexistent_session(db):
    """存在しないセッションの読み込みが None を返すことを確認"""
    loaded = await db.load_session("nonexistent:123")
    assert loaded is None


@pytest.mark.asyncio
async def test_delete_session(db):
    """セッションの削除ができることを確認"""
    session = ChatSession(
        session_key="test:delete",
        session_type="mention",
    )
    await db.save_session(session)

    # 削除前は存在する
    assert await db.load_session("test:delete") is not None

    # 削除
    await db.delete_session("test:delete")

    # 削除後は存在しない
    assert await db.load_session("test:delete") is None
