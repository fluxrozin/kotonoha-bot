"""セッション管理のテスト.

⚠️ 注意: このテストはPostgreSQLを使用します。
SQLiteからPostgreSQLに移行したため、すべてのテストをPostgreSQLに統一しました。
"""

import pytest

from kotonoha_bot.db.models import MessageRole


@pytest.mark.asyncio
async def test_create_session(session_manager):
    """セッションが作成できることを確認."""
    session = await session_manager.create_session(
        session_key="test:123",
        session_type="mention",
        user_id=123,
    )

    assert session is not None
    assert session.session_key == "test:123"
    assert session.session_type == "mention"
    assert session.user_id == 123


@pytest.mark.asyncio
async def test_get_session(session_manager):
    """セッションが取得できることを確認."""
    # セッションを作成
    await session_manager.create_session("test:123", "mention")

    # 取得
    session = await session_manager.get_session("test:123")
    assert session is not None
    assert session.session_key == "test:123"


@pytest.mark.asyncio
async def test_add_message(session_manager):
    """メッセージが追加できることを確認."""
    await session_manager.create_session("test:123", "mention")
    await session_manager.add_message("test:123", MessageRole.USER, "こんにちは")

    session = await session_manager.get_session("test:123")
    if session is None:
        pytest.fail("Session should not be None")
        return  # 型チェッカーのための明示的なreturn
    assert len(session.messages) == 1
    assert session.messages[0].content == "こんにちは"
    assert session.messages[0].role == MessageRole.USER


@pytest.mark.asyncio
async def test_save_session(session_manager, postgres_db):
    """セッションが保存できることを確認."""
    await session_manager.create_session("test:123", "mention")
    await session_manager.add_message("test:123", MessageRole.USER, "テストメッセージ")
    await session_manager.save_session("test:123")

    # データベースから直接読み込む
    loaded_session = await postgres_db.load_session("test:123")

    if loaded_session is None:
        pytest.fail("Loaded session should not be None")
    assert loaded_session.session_key == "test:123"
    assert len(loaded_session.messages) == 1
    assert loaded_session.messages[0].content == "テストメッセージ"
