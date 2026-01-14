"""設定管理モジュール"""
import os
from pathlib import Path

from dotenv import load_dotenv

# .envファイルの読み込み
load_dotenv()


class Config:
    """アプリケーション設定"""

    # Discord設定
    DISCORD_TOKEN: str = os.getenv("DISCORD_TOKEN", "")
    BOT_PREFIX: str = os.getenv("BOT_PREFIX", "!")

    # LLM設定（LiteLLM）
    LLM_MODEL: str = os.getenv("LLM_MODEL", "anthropic/claude-3-haiku-20240307")
    LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0.7"))
    LLM_MAX_TOKENS: int = int(os.getenv("LLM_MAX_TOKENS", "2048"))
    LLM_FALLBACK_MODEL: str | None = os.getenv("LLM_FALLBACK_MODEL")

    # データベース設定
    DATABASE_NAME: str = os.getenv("DATABASE_NAME", "sessions.db")
    DATABASE_PATH: Path = Path(f"./data/{DATABASE_NAME}")

    # ログ設定
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # セッション設定
    MAX_SESSIONS: int = 100  # メモリ内の最大セッション数
    SESSION_TIMEOUT_HOURS: int = 24  # セッションのタイムアウト（時間）

    # ヘルスチェック設定
    HEALTH_CHECK_ENABLED: bool = os.getenv("HEALTH_CHECK_ENABLED", "true").lower() == "true"
    HEALTH_CHECK_PORT: int = 8080  # 固定ポート（docker-compose.yml と一致させる必要があります）

    # ログファイル設定
    LOG_FILE: str | None = os.getenv("LOG_FILE")
    LOG_MAX_SIZE: int = int(os.getenv("LOG_MAX_SIZE", "10"))  # MB
    LOG_BACKUP_COUNT: int = int(os.getenv("LOG_BACKUP_COUNT", "5"))

    @classmethod
    def validate(cls) -> None:
        """設定の検証"""
        if not cls.DISCORD_TOKEN:
            raise ValueError("DISCORD_TOKEN is not set")
        if not cls.LLM_MODEL:
            raise ValueError("LLM_MODEL is not set")

        # データディレクトリの作成
        cls.DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)


# 設定の検証
Config.validate()
