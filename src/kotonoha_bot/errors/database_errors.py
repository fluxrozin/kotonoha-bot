"""データベースエラーの分類"""

import logging
import sqlite3

logger = logging.getLogger(__name__)


class DatabaseErrorType:
    """データベースエラーのタイプ"""

    LOCKED = "locked"  # データベースがロックされている
    INTEGRITY = "integrity"  # 整合性エラー
    OPERATIONAL = "operational"  # 操作エラー
    UNKNOWN = "unknown"  # 不明なエラー


def classify_database_error(error: Exception) -> str:
    """データベースエラーを分類

    Args:
        error: データベースエラー

    Returns:
        エラータイプ
    """
    if isinstance(error, sqlite3.OperationalError):
        error_msg = str(error).lower()
        if "locked" in error_msg or "database is locked" in error_msg:
            return DatabaseErrorType.LOCKED
        return DatabaseErrorType.OPERATIONAL
    elif isinstance(error, sqlite3.IntegrityError):
        return DatabaseErrorType.INTEGRITY

    return DatabaseErrorType.UNKNOWN


def get_database_error_message(error_type: str) -> str:
    """ユーザーフレンドリーなデータベースエラーメッセージを取得

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
