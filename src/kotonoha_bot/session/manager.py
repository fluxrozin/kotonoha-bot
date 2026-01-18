"""セッション管理"""

import logging
from datetime import UTC, datetime, timedelta

from ..config import settings
from ..db.postgres import PostgreSQLDatabase
from .models import ChatSession, MessageRole, SessionType

logger = logging.getLogger(__name__)


class SessionManager:
    """セッション管理クラス

    メモリ内のセッションとPostgreSQLの同期を管理する。
    """

    def __init__(self, db: PostgreSQLDatabase | None = None):
        """セッションマネージャーの初期化

        Args:
            db: 既存のPostgreSQLDatabaseインスタンス（省略時は新規作成）
        """
        self.sessions: dict[str, ChatSession] = {}

        if db is not None:
            # 既存のDBインスタンスを使用（推奨）
            self.db = db
            self._owns_db = False
        else:
            # 後方互換性のため、DBインスタンスを新規作成
            if settings.database_url:
                self.db = PostgreSQLDatabase(connection_string=settings.database_url)
            elif (
                settings.postgres_host
                and settings.postgres_db
                and settings.postgres_user
                and settings.postgres_password
            ):
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
            self._owns_db = True

        self._initialized = False

    async def initialize(self) -> None:
        """セッション管理の初期化（非同期）"""
        if not self._initialized:
            # 自身でDBを作成した場合のみ初期化
            if self._owns_db:
                await self.db.initialize()
            await self._load_active_sessions()
            self._initialized = True

    async def _load_active_sessions(self) -> None:
        """アクティブなセッションをPostgreSQLから読み込み"""
        try:
            all_sessions = await self.db.load_all_sessions()
            now = datetime.now(UTC)
            timeout = timedelta(hours=settings.session_timeout_hours)

            for session in all_sessions:
                # タイムアウトしていないセッションのみメモリに読み込む
                # last_active_at がタイムゾーン付きの場合はそのまま比較
                # タイムゾーンなしの場合は UTC として扱う
                last_active = session.last_active_at
                if last_active.tzinfo is None:
                    last_active = last_active.replace(tzinfo=UTC)
                if now - last_active < timeout:
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
        now = datetime.now(UTC)
        timeout = timedelta(hours=settings.session_timeout_hours)

        to_remove = []
        for session_key, session in self.sessions.items():
            last_active = session.last_active_at
            if last_active.tzinfo is None:
                last_active = last_active.replace(tzinfo=UTC)
            if now - last_active > timeout:
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
