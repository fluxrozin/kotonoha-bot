"""データベースエラーの分類.

⚠️ 注意: PostgreSQL（asyncpg）への移行に伴い、PostgreSQLのエラーにも対応しています。
SQLiteのエラーも後方互換性のためサポートしていますが、将来的に削除される可能性があります。
"""

import logging

logger = logging.getLogger(__name__)

# asyncpgのインポート（オプショナル）
try:
    import asyncpg

    HAS_ASYNCPG = True
except ImportError:
    HAS_ASYNCPG = False

# sqlite3のインポート（後方互換性のため）
try:
    import sqlite3

    HAS_SQLITE = True
except ImportError:
    HAS_SQLITE = False


class DatabaseErrorType:
    """データベースエラーのタイプ."""

    LOCKED = "locked"  # データベースがロックされている
    INTEGRITY = "integrity"  # 整合性エラー
    OPERATIONAL = "operational"  # 操作エラー
    UNKNOWN = "unknown"  # 不明なエラー


def classify_database_error(error: Exception) -> str:
    """データベースエラーを分類.

    ⚠️ 改善: PostgreSQL（asyncpg）のエラーにも対応
    SQLiteのエラーも後方互換性のためサポートしていますが、将来的に削除される可能性があります。

    Args:
        error: データベースエラー

    Returns:
        エラータイプ
    """
    # PostgreSQL（asyncpg）のエラーをチェック
    if HAS_ASYNCPG:
        if isinstance(
            error,
            (
                asyncpg.exceptions.UniqueViolationError,
                asyncpg.exceptions.ForeignKeyViolationError,
                asyncpg.exceptions.NotNullViolationError,
            ),
        ):
            return DatabaseErrorType.INTEGRITY
        elif isinstance(
            error,
            (
                asyncpg.exceptions.DeadlockDetectedError,
                asyncpg.exceptions.LockNotAvailableError,
            ),
        ):
            return DatabaseErrorType.LOCKED
        elif isinstance(error, asyncpg.exceptions.PostgresError):
            error_msg = str(error).lower()
            # ロック関連のエラーメッセージをチェック
            if "lock" in error_msg or "deadlock" in error_msg:
                return DatabaseErrorType.LOCKED
            # 整合性関連のエラーメッセージをチェック
            if (
                "unique" in error_msg
                or "foreign key" in error_msg
                or "constraint" in error_msg
            ):
                return DatabaseErrorType.INTEGRITY
            return DatabaseErrorType.OPERATIONAL

    # SQLiteのエラーをチェック（後方互換性のため）
    if HAS_SQLITE:
        if isinstance(error, sqlite3.OperationalError):
            error_msg = str(error).lower()
            if "locked" in error_msg or "database is locked" in error_msg:
                return DatabaseErrorType.LOCKED
            return DatabaseErrorType.OPERATIONAL
        elif isinstance(error, sqlite3.IntegrityError):
            return DatabaseErrorType.INTEGRITY

    return DatabaseErrorType.UNKNOWN


def get_database_error_message(error_type: str) -> str:
    """ユーザーフレンドリーなデータベースエラーメッセージを取得.

    Args:
        error_type: エラータイプ

    Returns:
        エラーメッセージ
    """
    messages = {
        DatabaseErrorType.LOCKED: (
            "すみません。データベースが一時的に使用中です。"
            "しばらく待ってから再度お試しください。"
        ),
        DatabaseErrorType.INTEGRITY: (
            "すみません。データの整合性エラーが発生しました。もう一度お試しください。"
        ),
        DatabaseErrorType.OPERATIONAL: (
            "すみません。データベース操作で問題が発生しました。"
            "しばらく待ってから再度お試しください。"
        ),
        DatabaseErrorType.UNKNOWN: (
            "すみません。データベースで問題が発生しました。"
            "少し時間をおいて、もう一度試してみてください。"
        ),
    }

    return messages.get(error_type, messages[DatabaseErrorType.UNKNOWN])
