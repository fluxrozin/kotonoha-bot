"""エラーハンドリングのテスト"""

import sqlite3
from unittest.mock import MagicMock

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
    """データベースエラーの分類テスト"""

    def test_classify_locked_error(self):
        """データベースロックエラーの分類"""
        error = sqlite3.OperationalError("database is locked")
        error_type = classify_database_error(error)
        assert error_type == DatabaseErrorType.LOCKED

    def test_classify_integrity_error(self):
        """整合性エラーの分類"""
        error = sqlite3.IntegrityError("UNIQUE constraint failed")
        error_type = classify_database_error(error)
        assert error_type == DatabaseErrorType.INTEGRITY

    def test_classify_operational_error(self):
        """操作エラーの分類"""
        error = sqlite3.OperationalError("no such table")
        error_type = classify_database_error(error)
        assert error_type == DatabaseErrorType.OPERATIONAL

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
