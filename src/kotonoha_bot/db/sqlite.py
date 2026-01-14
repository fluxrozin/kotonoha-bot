"""SQLiteデータベース操作"""
import sqlite3
import json
from pathlib import Path
from typing import List, Optional

from ..session.models import ChatSession
from ..config import Config


class DatabaseError(Exception):
    """データベースエラー"""
    pass


class SQLiteDatabase:
    """SQLiteデータベース"""

    def __init__(self, db_path: Path = Config.DATABASE_PATH):
        self.db_path = db_path
        self._init_database()

    def _init_database(self) -> None:
        """データベースの初期化"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # sessionsテーブル
            cursor.execute("""
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
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_last_active_at
                ON sessions(last_active_at)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_session_type
                ON sessions(session_type)
            """)

            conn.commit()

    def save_session(self, session: ChatSession) -> None:
        """セッションを保存"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                messages_json = json.dumps([msg.to_dict() for msg in session.messages])

                cursor.execute("""
                    INSERT OR REPLACE INTO sessions
                    (session_key, session_type, messages, created_at, last_active_at,
                     channel_id, thread_id, user_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    session.session_key,
                    session.session_type,
                    messages_json,
                    session.created_at.isoformat(),
                    session.last_active_at.isoformat(),
                    session.channel_id,
                    session.thread_id,
                    session.user_id,
                ))

                conn.commit()
        except sqlite3.Error as e:
            raise DatabaseError(f"Failed to save session: {e}")

    def load_session(self, session_key: str) -> Optional[ChatSession]:
        """セッションを読み込み"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT session_key, session_type, messages, created_at,
                           last_active_at, channel_id, thread_id, user_id
                    FROM sessions
                    WHERE session_key = ?
                """, (session_key,))

                row = cursor.fetchone()

                if not row:
                    return None

                messages = json.loads(row[2])

                return ChatSession.from_dict({
                    "session_key": row[0],
                    "session_type": row[1],
                    "messages": messages,
                    "created_at": row[3],
                    "last_active_at": row[4],
                    "channel_id": row[5],
                    "thread_id": row[6],
                    "user_id": row[7],
                })
        except sqlite3.Error as e:
            raise DatabaseError(f"Failed to load session: {e}")

    def load_all_sessions(self) -> List[ChatSession]:
        """全セッションを読み込み"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT session_key, session_type, messages, created_at,
                           last_active_at, channel_id, thread_id, user_id
                    FROM sessions
                    ORDER BY last_active_at DESC
                """)

                sessions = []
                for row in cursor.fetchall():
                    messages = json.loads(row[2])
                    session = ChatSession.from_dict({
                        "session_key": row[0],
                        "session_type": row[1],
                        "messages": messages,
                        "created_at": row[3],
                        "last_active_at": row[4],
                        "channel_id": row[5],
                        "thread_id": row[6],
                        "user_id": row[7],
                    })
                    sessions.append(session)

                return sessions
        except sqlite3.Error as e:
            raise DatabaseError(f"Failed to load sessions: {e}")

    def delete_session(self, session_key: str) -> None:
        """セッションを削除"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM sessions WHERE session_key = ?", (session_key,))
                conn.commit()
        except sqlite3.Error as e:
            raise DatabaseError(f"Failed to delete session: {e}")
