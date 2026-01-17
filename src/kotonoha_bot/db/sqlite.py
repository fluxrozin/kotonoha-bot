"""SQLiteデータベース操作"""

import json
import os
from pathlib import Path

import aiosqlite

from ..config import Config
from ..session.models import ChatSession


class DatabaseError(Exception):
    """データベースエラー"""

    pass


class SQLiteDatabase:
    """SQLiteデータベース"""

    def __init__(self, db_path: Path = Config.DATABASE_PATH):
        # パスを絶対パスに解決
        if not db_path.is_absolute():
            db_path = Path.cwd() / db_path
        self.db_path = db_path.resolve()
        # 非同期初期化は呼び出し元で実行（on_ready イベントなど）
        self._initialized = False

    async def initialize(self) -> None:
        """データベースの初期化（非同期）"""
        if not self._initialized:
            await self._init_database()
            self._initialized = True

    async def _init_database(self) -> None:
        """データベースの初期化"""
        try:
            # データベースファイルの親ディレクトリが存在することを確認
            parent_dir = self.db_path.parent
            parent_dir.mkdir(parents=True, exist_ok=True)

            # ディレクトリの書き込み権限を確認
            if not os.access(parent_dir, os.W_OK):
                raise DatabaseError(
                    f"Cannot write to database directory: {parent_dir}\n"
                    f"Please check directory permissions. Current user: {os.getuid()}, "
                    f"Directory owner: {parent_dir.stat().st_uid if parent_dir.exists() else 'N/A'}"
                )

            # データベースファイルへの接続を試行
            async with aiosqlite.connect(str(self.db_path), timeout=30.0) as conn:
                # WALモードを有効化（長時間稼働時のファイルロック問題を回避）
                await conn.execute("PRAGMA journal_mode=WAL")
                # 外部キー制約を有効化
                await conn.execute("PRAGMA foreign_keys=ON")
                # バスシーサイズを増やす（パフォーマンス向上）
                await conn.execute("PRAGMA busy_timeout=30000")  # 30秒
                # sessionsテーブル
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS sessions (
                        session_key TEXT PRIMARY KEY,
                        session_type TEXT NOT NULL,
                        messages TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        last_active_at TEXT NOT NULL,
                        channel_id INTEGER,
                        thread_id INTEGER,
                        user_id INTEGER
                    )
                """)

                # インデックス
                await conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_last_active_at
                    ON sessions(last_active_at)
                """)

                await conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_session_type
                    ON sessions(session_type)
                """)

                await conn.commit()
        except PermissionError as e:
            raise DatabaseError(
                f"Permission denied when accessing database: {self.db_path}\n"
                f"Error: {e}\n"
                f"Please check file and directory permissions."
            ) from e
        except aiosqlite.OperationalError as e:
            raise DatabaseError(
                f"Failed to open database file: {self.db_path}\n"
                f"Error: {e}\n"
                f"Parent directory: {self.db_path.parent}\n"
                f"Parent directory exists: {self.db_path.parent.exists()}\n"
                f"Parent directory writable: {os.access(self.db_path.parent, os.W_OK) if self.db_path.parent.exists() else False}"
            ) from e
        except Exception as e:
            raise DatabaseError(
                f"Unexpected error initializing database: {self.db_path}\nError: {e}"
            ) from e

    async def save_session(self, session: ChatSession) -> None:
        """セッションを保存"""
        try:
            async with aiosqlite.connect(str(self.db_path), timeout=30.0) as conn:
                # WALモードを有効化（長時間稼働時のファイルロック問題を回避）
                await conn.execute("PRAGMA journal_mode=WAL")
                # 外部キー制約を有効化
                await conn.execute("PRAGMA foreign_keys=ON")
                # バスシーサイズを増やす（パフォーマンス向上）
                await conn.execute("PRAGMA busy_timeout=30000")  # 30秒
                messages_json = json.dumps([msg.to_dict() for msg in session.messages])

                await conn.execute(
                    """
                    INSERT OR REPLACE INTO sessions
                    (session_key, session_type, messages, created_at, last_active_at,
                     channel_id, thread_id, user_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        session.session_key,
                        session.session_type,
                        messages_json,
                        session.created_at.isoformat(),
                        session.last_active_at.isoformat(),
                        session.channel_id,
                        session.thread_id,
                        session.user_id,
                    ),
                )

                await conn.commit()
        except aiosqlite.Error as e:
            raise DatabaseError(f"Failed to save session: {e}") from e

    async def load_session(self, session_key: str) -> ChatSession | None:
        """セッションを読み込み"""
        try:
            async with aiosqlite.connect(str(self.db_path), timeout=30.0) as conn:
                # WALモードを有効化（長時間稼働時のファイルロック問題を回避）
                await conn.execute("PRAGMA journal_mode=WAL")
                # 外部キー制約を有効化
                await conn.execute("PRAGMA foreign_keys=ON")
                # バスシーサイズを増やす（パフォーマンス向上）
                await conn.execute("PRAGMA busy_timeout=30000")  # 30秒
                async with conn.execute(
                    """
                    SELECT session_key, session_type, messages, created_at,
                           last_active_at, channel_id, thread_id, user_id
                    FROM sessions
                    WHERE session_key = ?
                """,
                    (session_key,),
                ) as cursor:
                    row = await cursor.fetchone()

                    if not row:
                        return None

                    messages = json.loads(row[2])

                    return ChatSession.from_dict(
                        {
                            "session_key": row[0],
                            "session_type": row[1],
                            "messages": messages,
                            "created_at": row[3],
                            "last_active_at": row[4],
                            "channel_id": row[5],
                            "thread_id": row[6],
                            "user_id": row[7],
                        }
                    )
        except aiosqlite.Error as e:
            raise DatabaseError(f"Failed to load session: {e}") from e

    async def load_all_sessions(self) -> list[ChatSession]:
        """全セッションを読み込み"""
        try:
            async with aiosqlite.connect(str(self.db_path), timeout=30.0) as conn:
                # WALモードを有効化（長時間稼働時のファイルロック問題を回避）
                await conn.execute("PRAGMA journal_mode=WAL")
                # 外部キー制約を有効化
                await conn.execute("PRAGMA foreign_keys=ON")
                # バスシーサイズを増やす（パフォーマンス向上）
                await conn.execute("PRAGMA busy_timeout=30000")  # 30秒
                async with conn.execute("""
                    SELECT session_key, session_type, messages, created_at,
                           last_active_at, channel_id, thread_id, user_id
                    FROM sessions
                    ORDER BY last_active_at DESC
                """) as cursor:
                    sessions = []
                    async for row in cursor:
                        messages = json.loads(row[2])
                        session = ChatSession.from_dict(
                            {
                                "session_key": row[0],
                                "session_type": row[1],
                                "messages": messages,
                                "created_at": row[3],
                                "last_active_at": row[4],
                                "channel_id": row[5],
                                "thread_id": row[6],
                                "user_id": row[7],
                            }
                        )
                        sessions.append(session)

                    return sessions
        except aiosqlite.Error as e:
            raise DatabaseError(f"Failed to load sessions: {e}") from e

    async def delete_session(self, session_key: str) -> None:
        """セッションを削除"""
        try:
            async with aiosqlite.connect(str(self.db_path), timeout=30.0) as conn:
                # WALモードを有効化（長時間稼働時のファイルロック問題を回避）
                await conn.execute("PRAGMA journal_mode=WAL")
                # 外部キー制約を有効化
                await conn.execute("PRAGMA foreign_keys=ON")
                # バスシーサイズを増やす（パフォーマンス向上）
                await conn.execute("PRAGMA busy_timeout=30000")  # 30秒
                await conn.execute(
                    "DELETE FROM sessions WHERE session_key = ?", (session_key,)
                )
                await conn.commit()
        except aiosqlite.Error as e:
            raise DatabaseError(f"Failed to delete session: {e}") from e

    async def close(self) -> None:
        """データベース接続を明示的に閉じる（テスト用）

        aiosqlite は接続プールを自動管理するため、
        通常は明示的に閉じる必要はない。
        テスト環境でのクリーンアップ用。
        """
        # aiosqlite は接続プールを自動管理するため、明示的な close は不要
        pass
