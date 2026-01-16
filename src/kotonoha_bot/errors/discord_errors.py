"""Discord API エラーの分類"""

import logging

import discord

logger = logging.getLogger(__name__)


class DiscordErrorType:
    """Discord エラーのタイプ"""

    PERMISSION = "permission"  # 権限エラー
    RATE_LIMIT = "rate_limit"  # レート制限
    NOT_FOUND = "not_found"  # リソースが見つからない
    INVALID = "invalid"  # 無効なリクエスト
    SERVER_ERROR = "server_error"  # サーバーエラー
    UNKNOWN = "unknown"  # 不明なエラー


def classify_discord_error(error: Exception) -> str:
    """Discord エラーを分類

    Args:
        error: Discord エラー

    Returns:
        エラータイプ
    """
    if isinstance(error, discord.errors.Forbidden):
        return DiscordErrorType.PERMISSION
    elif isinstance(error, discord.errors.HTTPException):
        if error.status == 429:
            return DiscordErrorType.RATE_LIMIT
        elif error.status == 404:
            return DiscordErrorType.NOT_FOUND
        elif 400 <= error.status < 500:
            return DiscordErrorType.INVALID
        elif error.status >= 500:
            return DiscordErrorType.SERVER_ERROR
    elif isinstance(error, discord.errors.NotFound):
        return DiscordErrorType.NOT_FOUND

    return DiscordErrorType.UNKNOWN


def get_user_friendly_message(error_type: str) -> str:
    """ユーザーフレンドリーなエラーメッセージを取得

    Args:
        error_type: エラータイプ

    Returns:
        エラーメッセージ
    """
    messages = {
        DiscordErrorType.PERMISSION: (
            "すみません。必要な権限がありません。サーバー管理者にご確認ください。"
        ),
        DiscordErrorType.RATE_LIMIT: (
            "すみません。リクエストが多すぎるため、"
            "しばらく待ってから再度お試しください。"
        ),
        DiscordErrorType.NOT_FOUND: ("すみません。リソースが見つかりませんでした。"),
        DiscordErrorType.INVALID: (
            "すみません。リクエストが無効です。もう一度お試しください。"
        ),
        DiscordErrorType.SERVER_ERROR: (
            "すみません。Discord サーバーで問題が発生しています。"
            "しばらく待ってから再度お試しください。"
        ),
        DiscordErrorType.UNKNOWN: (
            "すみません。一時的に反応できませんでした。"
            "少し時間をおいて、もう一度試してみてください。"
        ),
    }

    return messages.get(error_type, messages[DiscordErrorType.UNKNOWN])
