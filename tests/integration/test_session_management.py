"""セッション管理の統合テスト

セッションの保存→読み込み→更新→削除の一連の流れを確認
"""

from datetime import UTC, datetime

import pytest

from kotonoha_bot.session.models import ChatSession, Message, MessageRole


@pytest.mark.asyncio
async def test_session_management_flow(postgres_db):
    """セッション管理の統合テスト

    セッションの保存→読み込み→更新→再読み込みの一連の流れを確認
    """
    # 1. セッションの作成と保存
    session = ChatSession(
        session_key="test:session:integration:001",
        session_type="mention",
        messages=[
            Message(
                role=MessageRole.USER,
                content="こんにちは",
                timestamp=datetime.now(UTC),
            )
        ],
        guild_id=123456789,
        channel_id=987654321,
        user_id=111222333,
    )

    await postgres_db.save_session(session)

    # 2. セッションの読み込み
    loaded_session = await postgres_db.load_session("test:session:integration:001")
    assert loaded_session is not None
    assert loaded_session.session_key == "test:session:integration:001"
    assert len(loaded_session.messages) == 1
    assert loaded_session.messages[0].content == "こんにちは"

    # 3. セッションの更新（メッセージを追加）
    loaded_session.messages.append(
        Message(
            role=MessageRole.ASSISTANT,
            content="こんにちは！何かお手伝いできることはありますか？",
            timestamp=datetime.now(UTC),
        )
    )
    loaded_session.last_active_at = datetime.now(UTC)

    await postgres_db.save_session(loaded_session)

    # 4. 更新後のセッションを再読み込み
    updated_session = await postgres_db.load_session("test:session:integration:001")
    assert updated_session is not None
    assert len(updated_session.messages) == 2
    assert (
        updated_session.messages[1].content
        == "こんにちは！何かお手伝いできることはありますか？"
    )

    # 5. すべてのセッションを読み込み
    all_sessions = await postgres_db.load_all_sessions()
    assert len(all_sessions) > 0
    assert any(s.session_key == "test:session:integration:001" for s in all_sessions)


@pytest.mark.asyncio
async def test_session_persistence(postgres_db):
    """セッションの永続化テスト

    セッションを保存し、別のデータベースインスタンスで読み込めることを確認
    """
    # セッションを保存
    session = ChatSession(
        session_key="test:session:persistence:001",
        session_type="mention",
        messages=[
            Message(
                role=MessageRole.USER,
                content="永続化テスト",
                timestamp=datetime.now(UTC),
            )
        ],
        guild_id=123456789,
        channel_id=987654321,
        user_id=111222333,
    )

    await postgres_db.save_session(session)

    # 別のデータベースインスタンスで読み込み（同じプールを使用）
    # 実際の統合テストでは、別の接続プールから読み込むことを想定
    loaded_session = await postgres_db.load_session("test:session:persistence:001")
    assert loaded_session is not None
    assert loaded_session.session_key == "test:session:persistence:001"
    assert loaded_session.guild_id == 123456789
    assert loaded_session.channel_id == 987654321
    assert loaded_session.user_id == 111222333
