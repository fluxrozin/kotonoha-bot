"""セッション管理"""

import logging
from datetime import datetime, timedelta

from ..config import Config
from ..db.sqlite import SQLiteDatabase
from .models import ChatSession, MessageRole, SessionType

logger = logging.getLogger(__name__)


class SessionManager:
    """セッション管理クラス

    メモリ内のセッションとSQLiteの同期を管理する。
    """

    def __init__(self):
        self.sessions: dict[str, ChatSession] = {}
        self.db = SQLiteDatabase()
        self._load_active_sessions()

    def _load_active_sessions(self) -> None:
        """アクティブなセッションをSQLiteから読み込み"""
        try:
            all_sessions = self.db.load_all_sessions()
            now = datetime.now()
            timeout = timedelta(hours=Config.SESSION_TIMEOUT_HOURS)

            for session in all_sessions:
                # タイムアウトしていないセッションのみメモリに読み込む
                if now - session.last_active_at < timeout:
                    self.sessions[session.session_key] = session
                    logger.info(f"Loaded session: {session.session_key}")

            logger.info(f"Loaded {len(self.sessions)} active sessions")
        except Exception as e:
            logger.error(f"Failed to load sessions: {e}")

    def get_session(self, session_key: str) -> ChatSession | None:
        """セッションを取得

        メモリ内にあればそれを返し、なければSQLiteから復元を試みる。
        """
        # メモリ内を確認
        if session_key in self.sessions:
            return self.sessions[session_key]

        # SQLiteから復元を試みる
        session = self.db.load_session(session_key)
        if session:
            self.sessions[session_key] = session
            logger.info(f"Restored session from DB: {session_key}")
            return session

        return None

    def create_session(
        self, session_key: str, session_type: SessionType, **kwargs
    ) -> ChatSession:
        """新しいセッションを作成"""
        session = ChatSession(
            session_key=session_key, session_type=session_type, **kwargs
        )

        self.sessions[session_key] = session
        self.db.save_session(session)
        logger.info(f"Created session: {session_key}")

        return session

    def add_message(self, session_key: str, role: MessageRole, content: str) -> None:
        """セッションにメッセージを追加"""
        session = self.get_session(session_key)
        if not session:
            raise KeyError(f"Session not found: {session_key}")

        session.add_message(role, content)
        logger.debug(f"Added message to session: {session_key}")

    def save_session(self, session_key: str) -> None:
        """セッションをSQLiteに保存"""
        session = self.sessions.get(session_key)
        if not session:
            raise KeyError(f"Session not found: {session_key}")

        self.db.save_session(session)
        logger.debug(f"Saved session to DB: {session_key}")

    def save_all_sessions(self) -> None:
        """全セッションをSQLiteに保存"""
        for session_key, session in self.sessions.items():
            try:
                self.db.save_session(session)
                logger.debug(f"Saved session: {session_key}")
            except Exception as e:
                logger.error(f"Failed to save session {session_key}: {e}")

        logger.info(f"Saved {len(self.sessions)} sessions")

    def cleanup_old_sessions(self) -> None:
        """古いセッションをメモリから削除"""
        now = datetime.now()
        timeout = timedelta(hours=Config.SESSION_TIMEOUT_HOURS)

        to_remove = []
        for session_key, session in self.sessions.items():
            if now - session.last_active_at > timeout:
                # SQLiteに保存してからメモリから削除
                try:
                    self.db.save_session(session)
                    to_remove.append(session_key)
                except Exception as e:
                    logger.error(f"Failed to save session before removal: {e}")

        for session_key in to_remove:
            del self.sessions[session_key]
            logger.info(f"Removed old session: {session_key}")

        if to_remove:
            logger.info(f"Cleaned up {len(to_remove)} old sessions")
