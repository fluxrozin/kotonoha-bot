"""セッション管理"""

import logging
from datetime import datetime, timedelta

from ..config import Config, settings
from ..db.postgres import PostgreSQLDatabase
from .models import ChatSession, MessageRole, SessionType

logger = logging.getLogger(__name__)


class SessionManager:
    """セッション管理クラス

    メモリ内のセッションとPostgreSQLの同期を管理する。
    """

    def __init__(self):
        self.sessions: dict[str, ChatSession] = {}
        # PostgreSQL接続設定
        if settings.database_url:
            self.db = PostgreSQLDatabase(connection_string=settings.database_url)
        elif settings.postgres_host and settings.postgres_db and settings.postgres_user and settings.postgres_password:
            self.db = PostgreSQLDatabase(
                host=settings.postgres_host,
                port=settings.postgres_port,
                database=settings.postgres_db,
                user=settings.postgres_user,
                password=settings.postgres_password,
            )
        else:
            raise ValueError(
                "Either DATABASE_URL or (POSTGRES_HOST, POSTGRES_DB, "
                "POSTGRES_USER, POSTGRES_PASSWORD) must be set"
            )
        self._initialized = False

    async def initialize(self) -> None:
        """セッション管理の初期化（非同期）"""
        if not self._initialized:
            await self.db.initialize()
            await self._load_active_sessions()
            self._initialized = True

    async def _load_active_sessions(self) -> None:
        """アクティブなセッションをPostgreSQLから読み込み"""
        try:
            all_sessions = await self.db.load_all_sessions()
            now = datetime.now()
            timeout = timedelta(hours=settings.session_timeout_hours)

            for session in all_sessions:
                # タイムアウトしていないセッションのみメモリに読み込む
                if now - session.last_active_at < timeout:
                    self.sessions[session.session_key] = session
                    logger.info(f"Loaded session: {session.session_key}")

            logger.info(f"Loaded {len(self.sessions)} active sessions")
        except Exception as e:
            logger.error(f"Failed to load sessions: {e}")

    async def get_session(self, session_key: str) -> ChatSession | None:
        """セッションを取得

        メモリ内にあればそれを返し、なければSQLiteから復元を試みる。
        """
        # メモリ内を確認
        if session_key in self.sessions:
            return self.sessions[session_key]

        # PostgreSQLから復元を試みる
        session = await self.db.load_session(session_key)
        if session:
            self.sessions[session_key] = session
            logger.info(f"Restored session from DB: {session_key}")
            return session

        return None

    async def create_session(
        self, session_key: str, session_type: SessionType, **kwargs
    ) -> ChatSession:
        """新しいセッションを作成"""
        session = ChatSession(
            session_key=session_key, session_type=session_type, **kwargs
        )

        self.sessions[session_key] = session
        await self.db.save_session(session)
        logger.info(f"Created session: {session_key}")

        return session

    async def add_message(
        self, session_key: str, role: MessageRole, content: str
    ) -> None:
        """セッションにメッセージを追加"""
        session = await self.get_session(session_key)
        if not session:
            raise KeyError(f"Session not found: {session_key}")

        session.add_message(role, content)
        logger.debug(f"Added message to session: {session_key}")

    async def save_session(self, session_key: str) -> None:
        """セッションをPostgreSQLに保存"""
        session = self.sessions.get(session_key)
        if not session:
            raise KeyError(f"Session not found: {session_key}")

        await self.db.save_session(session)
        logger.debug(f"Saved session to DB: {session_key}")

    async def save_all_sessions(self) -> None:
        """全セッションをPostgreSQLに保存"""
        for session_key, session in self.sessions.items():
            try:
                await self.db.save_session(session)
                logger.debug(f"Saved session: {session_key}")
            except Exception as e:
                logger.error(f"Failed to save session {session_key}: {e}")

        logger.info(f"Saved {len(self.sessions)} sessions")

    async def cleanup_old_sessions(self) -> None:
        """古いセッションをメモリから削除"""
        now = datetime.now()
        timeout = timedelta(hours=settings.session_timeout_hours)

        to_remove = []
        for session_key, session in self.sessions.items():
            if now - session.last_active_at > timeout:
                # PostgreSQLに保存してからメモリから削除
                try:
                    await self.db.save_session(session)
                    to_remove.append(session_key)
                except Exception as e:
                    logger.error(f"Failed to save session before removal: {e}")

        for session_key in to_remove:
            del self.sessions[session_key]
            logger.info(f"Removed old session: {session_key}")

        if to_remove:
            logger.info(f"Cleaned up {len(to_remove)} old sessions")
