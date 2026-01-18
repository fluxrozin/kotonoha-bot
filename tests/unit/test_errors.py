"""エラーハンドリングのテスト

⚠️ 注意: PostgreSQL（asyncpg）への移行に伴い、PostgreSQLのエラーにも対応しています。
SQLiteのエラーテストは後方互換性のため残していますが、将来的に削除される可能性があります。
"""

from unittest.mock import MagicMock

import asyncpg
import discord

from kotonoha_bot.errors.database_errors import (
    DatabaseErrorType,
    classify_database_error,
    get_database_error_message,
)
from kotonoha_bot.errors.discord_errors import (
    DiscordErrorType,
    classify_discord_error,
    get_user_friendly_message,
)


class TestDiscordErrors:
    """Discord エラーの分類テスト"""

    def test_classify_permission_error(self):
        """権限エラーの分類"""
        error = MagicMock(spec=discord.errors.Forbidden)
        error_type = classify_discord_error(error)
        assert error_type == DiscordErrorType.PERMISSION

    def test_classify_rate_limit_error(self):
        """レート制限エラーの分類"""
        error = MagicMock(spec=discord.errors.HTTPException)
        error.status = 429
        error_type = classify_discord_error(error)
        assert error_type == DiscordErrorType.RATE_LIMIT

    def test_classify_not_found_error(self):
        """NotFoundエラーの分類"""
        # NotFoundはHTTPExceptionのサブクラスなので、HTTPExceptionとして処理される
        # または、NotFoundとして直接処理される
        # 実際のコードでは、NotFoundはHTTPExceptionの後にチェックされるが、
        # NotFoundはHTTPExceptionのサブクラスなので、HTTPExceptionのチェックが先に実行される
        # そのため、HTTPExceptionとして404ステータスで処理されることを確認
        error = MagicMock(spec=discord.errors.HTTPException)
        error.status = 404
        error_type = classify_discord_error(error)
        assert error_type == DiscordErrorType.NOT_FOUND

    def test_classify_invalid_error(self):
        """無効なリクエストエラーの分類"""
        error = MagicMock(spec=discord.errors.HTTPException)
        error.status = 400
        error_type = classify_discord_error(error)
        assert error_type == DiscordErrorType.INVALID

    def test_classify_server_error(self):
        """サーバーエラーの分類"""
        error = MagicMock(spec=discord.errors.HTTPException)
        error.status = 500
        error_type = classify_discord_error(error)
        assert error_type == DiscordErrorType.SERVER_ERROR

    def test_classify_unknown_error(self):
        """不明なエラーの分類"""
        error = ValueError("Unknown error")
        error_type = classify_discord_error(error)
        assert error_type == DiscordErrorType.UNKNOWN

    def test_get_user_friendly_message_permission(self):
        """権限エラーのメッセージ"""
        message = get_user_friendly_message(DiscordErrorType.PERMISSION)
        assert "権限" in message
        assert "サーバー管理者" in message

    def test_get_user_friendly_message_rate_limit(self):
        """レート制限エラーのメッセージ"""
        message = get_user_friendly_message(DiscordErrorType.RATE_LIMIT)
        assert "リクエストが多すぎる" in message

    def test_get_user_friendly_message_not_found(self):
        """NotFoundエラーのメッセージ"""
        message = get_user_friendly_message(DiscordErrorType.NOT_FOUND)
        assert "見つかりませんでした" in message

    def test_get_user_friendly_message_invalid(self):
        """無効なリクエストエラーのメッセージ"""
        message = get_user_friendly_message(DiscordErrorType.INVALID)
        assert "無効" in message

    def test_get_user_friendly_message_server_error(self):
        """サーバーエラーのメッセージ"""
        message = get_user_friendly_message(DiscordErrorType.SERVER_ERROR)
        assert "Discord サーバー" in message

    def test_get_user_friendly_message_unknown(self):
        """不明なエラーのメッセージ"""
        message = get_user_friendly_message(DiscordErrorType.UNKNOWN)
        assert "一時的に反応できませんでした" in message


class TestDatabaseErrors:
    """データベースエラーの分類テスト

    ⚠️ 注意: PostgreSQL（asyncpg）のエラーを優先的にテストします。
    SQLiteのエラーテストは後方互換性のため残しています。
    """

    # PostgreSQL（asyncpg）のエラーテスト
    def test_classify_postgres_unique_violation_error(self):
        """PostgreSQLのUNIQUE制約違反エラーの分類"""
        error = asyncpg.exceptions.UniqueViolationError(
            "duplicate key value violates unique constraint"
        )
        error_type = classify_database_error(error)
        assert error_type == DatabaseErrorType.INTEGRITY

    def test_classify_postgres_foreign_key_violation_error(self):
        """PostgreSQLの外部キー制約違反エラーの分類"""
        error = asyncpg.exceptions.ForeignKeyViolationError(
            "violates foreign key constraint"
        )
        error_type = classify_database_error(error)
        assert error_type == DatabaseErrorType.INTEGRITY

    def test_classify_postgres_deadlock_error(self):
        """PostgreSQLのデッドロックエラーの分類"""
        error = asyncpg.exceptions.DeadlockDetectedError("deadlock detected")
        error_type = classify_database_error(error)
        assert error_type == DatabaseErrorType.LOCKED

    def test_classify_postgres_lock_not_available_error(self):
        """PostgreSQLのロックエラーの分類"""
        error = asyncpg.exceptions.LockNotAvailableError("could not obtain lock")
        error_type = classify_database_error(error)
        assert error_type == DatabaseErrorType.LOCKED

    def test_classify_postgres_operational_error(self):
        """PostgreSQLの操作エラーの分類"""
        error = asyncpg.exceptions.PostgresError("relation does not exist")
        error_type = classify_database_error(error)
        assert error_type == DatabaseErrorType.OPERATIONAL

    # SQLiteのエラーテスト（後方互換性のため）
    def test_classify_sqlite_locked_error(self):
        """SQLiteのデータベースロックエラーの分類（後方互換性）"""
        try:
            import sqlite3

            error = sqlite3.OperationalError("database is locked")
            error_type = classify_database_error(error)
            assert error_type == DatabaseErrorType.LOCKED
        except ImportError:
            # sqlite3が利用できない場合はスキップ
            pass

    def test_classify_sqlite_integrity_error(self):
        """SQLiteの整合性エラーの分類（後方互換性）"""
        try:
            import sqlite3

            error = sqlite3.IntegrityError("UNIQUE constraint failed")
            error_type = classify_database_error(error)
            assert error_type == DatabaseErrorType.INTEGRITY
        except ImportError:
            # sqlite3が利用できない場合はスキップ
            pass

    def test_classify_sqlite_operational_error(self):
        """SQLiteの操作エラーの分類（後方互換性）"""
        try:
            import sqlite3

            error = sqlite3.OperationalError("no such table")
            error_type = classify_database_error(error)
            assert error_type == DatabaseErrorType.OPERATIONAL
        except ImportError:
            # sqlite3が利用できない場合はスキップ
            pass

    def test_classify_unknown_error(self):
        """不明なエラーの分類"""
        error = ValueError("Unknown error")
        error_type = classify_database_error(error)
        assert error_type == DatabaseErrorType.UNKNOWN

    def test_get_database_error_message_locked(self):
        """データベースロックエラーのメッセージ"""
        message = get_database_error_message(DatabaseErrorType.LOCKED)
        assert "データベースが一時的に使用中" in message

    def test_get_database_error_message_integrity(self):
        """整合性エラーのメッセージ"""
        message = get_database_error_message(DatabaseErrorType.INTEGRITY)
        assert "整合性エラー" in message

    def test_get_database_error_message_operational(self):
        """操作エラーのメッセージ"""
        message = get_database_error_message(DatabaseErrorType.OPERATIONAL)
        assert "データベース操作" in message

    def test_get_database_error_message_unknown(self):
        """不明なエラーのメッセージ"""
        message = get_database_error_message(DatabaseErrorType.UNKNOWN)
        assert "データベースで問題が発生" in message
