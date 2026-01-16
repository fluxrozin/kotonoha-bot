"""エラーハンドリングモジュール"""

from .database_errors import (
    DatabaseErrorType,
    classify_database_error,
    get_database_error_message,
)
from .discord_errors import (
    DiscordErrorType,
    classify_discord_error,
    get_user_friendly_message,
)

__all__ = [
    "DiscordErrorType",
    "classify_discord_error",
    "get_user_friendly_message",
    "DatabaseErrorType",
    "classify_database_error",
    "get_database_error_message",
]
