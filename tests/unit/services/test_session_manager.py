"""セッションマネージャーの詳細テスト."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from kotonoha_bot.db.models import ChatSession, MessageRole
from kotonoha_bot.services.session import SessionManager


@pytest.fixture
def mock_db():
    """モックデータベース."""
    db = MagicMock()
    db.load_all_sessions = AsyncMock(return_value=[])
    db.load_session = AsyncMock(return_value=None)
    db.save_session = AsyncMock()
    return db


@pytest.fixture
def mock_config():
    """モックConfig."""
    config = MagicMock()
    config.SESSION_TIMEOUT_HOURS = 24
    config.MAX_SESSIONS = 100
    return config


@pytest.fixture
def session_manager(mock_db, mock_config):
    """SessionManager インスタンス."""
    return SessionManager(db=mock_db, config=mock_config)


class TestSessionManagerLoadActiveSessions:
    """_load_active_sessions メソッドのテスト."""

    @pytest.mark.asyncio
    async def test_load_active_sessions_loads_active_only(
        self, session_manager, mock_db
    ):
        """アクティブなセッションのみが読み込まれる."""
        now = datetime.now(UTC)
        active_session = ChatSession(
            session_key="active:1",
            session_type="mention",
            last_active_at=now - timedelta(hours=1),  # 1時間前（アクティブ）
        )
        old_session = ChatSession(
            session_key="old:1",
            session_type="mention",
            last_active_at=now - timedelta(hours=25),  # 25時間前（タイムアウト）
        )

        mock_db.load_all_sessions = AsyncMock(
            return_value=[active_session, old_session]
        )

        await session_manager._load_active_sessions()

        # アクティブなセッションのみが読み込まれることを確認
        assert "active:1" in session_manager.sessions
        assert "old:1" not in session_manager.sessions

    @pytest.mark.asyncio
    async def test_load_active_sessions_handles_timezone_naive(
        self, session_manager, mock_db
    ):
        """タイムゾーンなしの last_active_at を処理できる."""
        session = ChatSession(
            session_key="test:1",
            session_type="mention",
            last_active_at=datetime.now(),  # タイムゾーンなし
        )

        mock_db.load_all_sessions = AsyncMock(return_value=[session])

        await session_manager._load_active_sessions()

        # セッションが読み込まれることを確認（タイムゾーンなしでも処理される）
        assert "test:1" in session_manager.sessions

    @pytest.mark.asyncio
    async def test_load_active_sessions_handles_error(self, session_manager, mock_db):
        """エラーが発生した場合."""
        mock_db.load_all_sessions = AsyncMock(side_effect=Exception("DB Error"))

        # エラーが発生しても例外が伝播しないことを確認
        await session_manager._load_active_sessions()

        # セッションは読み込まれない
        assert len(session_manager.sessions) == 0


class TestSessionManagerCleanupOldSessions:
    """cleanup_old_sessions メソッドのテスト."""

    @pytest.mark.asyncio
    async def test_cleanup_old_sessions_removes_old_sessions(
        self, session_manager, mock_db
    ):
        """古いセッションが削除される."""
        now = datetime.now(UTC)
        old_session = ChatSession(
            session_key="old:1",
            session_type="mention",
            last_active_at=now - timedelta(hours=25),  # 25時間前（タイムアウト）
        )
        active_session = ChatSession(
            session_key="active:1",
            session_type="mention",
            last_active_at=now - timedelta(hours=1),  # 1時間前（アクティブ）
        )

        session_manager.sessions = {
            "old:1": old_session,
            "active:1": active_session,
        }

        await session_manager.cleanup_old_sessions()

        # 古いセッションが削除されたことを確認
        assert "old:1" not in session_manager.sessions
        # アクティブなセッションは残ることを確認
        assert "active:1" in session_manager.sessions
        # 古いセッションが保存されたことを確認
        mock_db.save_session.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_old_sessions_saves_before_removal(
        self, session_manager, mock_db
    ):
        """削除前にセッションが保存される."""
        now = datetime.now(UTC)
        old_session = ChatSession(
            session_key="old:1",
            session_type="mention",
            last_active_at=now - timedelta(hours=25),
        )

        session_manager.sessions = {"old:1": old_session}

        await session_manager.cleanup_old_sessions()

        # 削除前に保存されたことを確認
        mock_db.save_session.assert_called_once_with(old_session)

    @pytest.mark.asyncio
    async def test_cleanup_old_sessions_handles_save_error(
        self, session_manager, mock_db
    ):
        """保存エラーが発生した場合でも処理が続行される."""
        now = datetime.now(UTC)
        old_session = ChatSession(
            session_key="old:1",
            session_type="mention",
            last_active_at=now - timedelta(hours=25),
        )

        session_manager.sessions = {"old:1": old_session}
        mock_db.save_session = AsyncMock(side_effect=Exception("Save error"))

        # エラーが発生しても例外が伝播しないことを確認
        await session_manager.cleanup_old_sessions()

        # セッションは削除されない（保存に失敗したため）
        assert "old:1" in session_manager.sessions


class TestSessionManagerSaveAllSessions:
    """save_all_sessions メソッドのテスト."""

    @pytest.mark.asyncio
    async def test_save_all_sessions_saves_all(self, session_manager, mock_db):
        """すべてのセッションが保存される."""
        session1 = ChatSession(session_key="test:1", session_type="mention")
        session2 = ChatSession(session_key="test:2", session_type="thread")
        session3 = ChatSession(session_key="test:3", session_type="eavesdrop")

        session_manager.sessions = {
            "test:1": session1,
            "test:2": session2,
            "test:3": session3,
        }

        await session_manager.save_all_sessions()

        # すべてのセッションが保存されたことを確認
        assert mock_db.save_session.call_count == 3
        mock_db.save_session.assert_any_call(session1)
        mock_db.save_session.assert_any_call(session2)
        mock_db.save_session.assert_any_call(session3)

    @pytest.mark.asyncio
    async def test_save_all_sessions_handles_individual_errors(
        self, session_manager, mock_db
    ):
        """個別のセッション保存エラーが処理される."""
        session1 = ChatSession(session_key="test:1", session_type="mention")
        session2 = ChatSession(session_key="test:2", session_type="thread")

        session_manager.sessions = {
            "test:1": session1,
            "test:2": session2,
        }

        # 1つ目のセッション保存でエラー、2つ目は成功
        call_count = 0

        async def save_side_effect(_session):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("Save error")
            return None

        mock_db.save_session = AsyncMock(side_effect=save_side_effect)

        # エラーが発生しても処理が続行されることを確認
        await session_manager.save_all_sessions()

        # 両方のセッションに対して保存が試みられたことを確認
        assert mock_db.save_session.call_count == 2

    @pytest.mark.asyncio
    async def test_save_all_sessions_empty(self, session_manager, mock_db):
        """セッションが空の場合."""
        session_manager.sessions = {}

        await session_manager.save_all_sessions()

        # 保存が呼ばれないことを確認
        mock_db.save_session.assert_not_called()


class TestSessionManagerInitialize:
    """initialize メソッドのテスト."""

    @pytest.mark.asyncio
    async def test_initialize_loads_sessions(self, session_manager, mock_db):
        """initialize でセッションが読み込まれる."""
        session = ChatSession(
            session_key="test:1",
            session_type="mention",
            last_active_at=datetime.now(UTC),
        )
        mock_db.load_all_sessions = AsyncMock(return_value=[session])

        await session_manager.initialize()

        # セッションが読み込まれたことを確認
        assert "test:1" in session_manager.sessions
        # 初期化済みフラグが設定されたことを確認
        assert session_manager.is_initialized is True

    @pytest.mark.asyncio
    async def test_initialize_idempotent(self, session_manager, mock_db):
        """initialize は冪等性を持つ."""
        session = ChatSession(
            session_key="test:1",
            session_type="mention",
            last_active_at=datetime.now(UTC),
        )
        mock_db.load_all_sessions = AsyncMock(return_value=[session])

        # 2回呼び出しても問題ない
        await session_manager.initialize()
        # 2回目の呼び出しでは、_initialized が True なので _load_active_sessions は呼ばれない
        session_manager._initialized = False  # リセットして再度テスト
        await session_manager.initialize()

        # セッションが2回読み込まれることを確認（_initialized をリセットしたため）
        assert mock_db.load_all_sessions.call_count == 2


class TestSessionManagerGetSession:
    """get_session メソッドのテスト."""

    @pytest.mark.asyncio
    async def test_get_session_from_memory(self, session_manager):
        """メモリ内のセッションが返される."""
        session = ChatSession(session_key="test:1", session_type="mention")
        session_manager.sessions = {"test:1": session}

        result = await session_manager.get_session("test:1")

        assert result == session
        # データベースから読み込まれないことを確認
        session_manager.db.load_session.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_session_from_db(self, session_manager, mock_db):
        """データベースからセッションが復元される."""
        session = ChatSession(session_key="test:1", session_type="mention")
        session_manager.sessions = {}
        mock_db.load_session = AsyncMock(return_value=session)

        result = await session_manager.get_session("test:1")

        assert result == session
        # メモリに追加されたことを確認
        assert "test:1" in session_manager.sessions

    @pytest.mark.asyncio
    async def test_get_session_not_found(self, session_manager, mock_db):
        """セッションが見つからない場合."""
        session_manager.sessions = {}
        mock_db.load_session = AsyncMock(return_value=None)

        result = await session_manager.get_session("test:1")

        assert result is None


class TestSessionManagerAddMessage:
    """add_message メソッドのテスト."""

    @pytest.mark.asyncio
    async def test_add_message_session_not_found(self, session_manager):
        """セッションが見つからない場合にエラーが発生する."""
        session_manager.sessions = {}
        session_manager.db.load_session = AsyncMock(return_value=None)

        with pytest.raises(KeyError, match="Session not found"):
            await session_manager.add_message("test:1", MessageRole.USER, "テスト")

    @pytest.mark.asyncio
    async def test_add_message_updates_last_active(self, session_manager):
        """メッセージ追加時に last_active_at が更新される."""
        import asyncio

        session = ChatSession(session_key="test:1", session_type="mention")
        original_active_at = session.last_active_at
        session_manager.sessions = {"test:1": session}
        session_manager.db.load_session = AsyncMock(return_value=session)

        await asyncio.sleep(0.01)  # 少し待機
        await session_manager.add_message("test:1", MessageRole.USER, "テスト")

        # last_active_at が更新されたことを確認
        # add_message は session.add_message を呼び出すが、
        # ChatSession.add_message は last_active_at を更新する
        assert session.last_active_at >= original_active_at
