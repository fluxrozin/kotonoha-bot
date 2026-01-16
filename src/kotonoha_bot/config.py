"""設定管理モジュール"""

import os
from pathlib import Path

from dotenv import load_dotenv

# .envファイルの読み込み（既存の環境変数は上書きしない）
load_dotenv(override=False)


class Config:
    """アプリケーション設定"""

    # Discord設定
    DISCORD_TOKEN: str = os.getenv("DISCORD_TOKEN", "")
    BOT_PREFIX: str = os.getenv("BOT_PREFIX", "!")

    # LLM設定（LiteLLM）
    LLM_MODEL: str = os.getenv("LLM_MODEL", "anthropic/claude-sonnet-4-5")
    LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0.7"))
    LLM_MAX_TOKENS: int = int(os.getenv("LLM_MAX_TOKENS", "2048"))
    LLM_FALLBACK_MODEL: str | None = os.getenv("LLM_FALLBACK_MODEL")
    # リトライ設定（一時的なエラーに対するリトライ）
    LLM_MAX_RETRIES: int = int(os.getenv("LLM_MAX_RETRIES", "3"))  # 最大リトライ回数
    LLM_RETRY_DELAY_BASE: float = float(
        os.getenv("LLM_RETRY_DELAY_BASE", "1.0")
    )  # 指数バックオフのベース遅延（秒）

    # データベース設定
    DATABASE_NAME: str = os.getenv("DATABASE_NAME", "sessions.db")
    DATABASE_PATH: Path = Path(f"./data/{DATABASE_NAME}")

    # ログ設定
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # セッション設定
    MAX_SESSIONS: int = int(
        os.getenv("MAX_SESSIONS", "100")
    )  # メモリ内の最大セッション数
    SESSION_TIMEOUT_HOURS: int = int(
        os.getenv("SESSION_TIMEOUT_HOURS", "24")
    )  # セッションのタイムアウト（時間）

    # ヘルスチェック設定
    HEALTH_CHECK_ENABLED: bool = (
        os.getenv("HEALTH_CHECK_ENABLED", "true").lower() == "true"
    )
    HEALTH_CHECK_PORT: int = (
        8080  # 固定ポート（docker-compose.yml と一致させる必要があります）
    )

    # ログファイル設定
    LOG_FILE: str | None = os.getenv("LOG_FILE")
    LOG_MAX_SIZE: int = int(os.getenv("LOG_MAX_SIZE", "10"))  # MB
    LOG_BACKUP_COUNT: int = int(os.getenv("LOG_BACKUP_COUNT", "5"))

    # 聞き耳型設定
    EAVESDROP_ENABLED_CHANNELS: str = os.getenv(
        "EAVESDROP_ENABLED_CHANNELS", ""
    )  # カンマ区切りのチャンネルID
    EAVESDROP_JUDGE_MODEL: str = os.getenv(
        "EAVESDROP_JUDGE_MODEL", "anthropic/claude-haiku-4-5"
    )  # 判定用モデル
    EAVESDROP_BUFFER_SIZE: int = int(
        os.getenv("EAVESDROP_BUFFER_SIZE", "20")
    )  # バッファサイズ
    EAVESDROP_MIN_MESSAGES: int = int(
        os.getenv("EAVESDROP_MIN_MESSAGES", "3")
    )  # 判定・応答生成に必要な最低メッセージ数（会話の流れを理解するため）
    EAVESDROP_MIN_INTERVENTION_INTERVAL_MINUTES: int = int(
        os.getenv("EAVESDROP_MIN_INTERVENTION_INTERVAL_MINUTES", "10")
    )  # 介入の最小間隔（分）

    # スレッド型設定
    THREAD_AUTO_ARCHIVE_DURATION: int | None = (
        int(os.getenv("THREAD_AUTO_ARCHIVE_DURATION"))
        if os.getenv("THREAD_AUTO_ARCHIVE_DURATION")
        else None
    )  # スレッドの自動アーカイブ期間（分）
    # 有効な値: 60 (1時間), 1440 (1日), 4320 (3日), 10080 (7日), 43200 (30日)
    # None の場合はサーバーのデフォルト値を使用

    # レート制限設定
    RATE_LIMIT_CAPACITY: int = int(
        os.getenv("RATE_LIMIT_CAPACITY", "50")
    )  # レート制限の上限値（1分間に50リクエストまで）
    RATE_LIMIT_REFILL: float = float(
        os.getenv("RATE_LIMIT_REFILL", "0.8")
    )  # 補充レート（リクエスト/秒、1分間に約48リクエスト）
    RATE_LIMIT_WINDOW: int = int(
        os.getenv("RATE_LIMIT_WINDOW", "60")
    )  # 監視ウィンドウ（秒）
    RATE_LIMIT_THRESHOLD: float = float(
        os.getenv("RATE_LIMIT_THRESHOLD", "0.9")
    )  # 警告閾値（0.0-1.0）

    @classmethod
    def validate(cls, skip_in_test: bool = False) -> None:
        """設定の検証

        Args:
            skip_in_test: テスト環境では True に設定して検証をスキップ
        """
        # テスト環境では検証をスキップ
        if skip_in_test:
            return

        if not cls.DISCORD_TOKEN:
            raise ValueError("DISCORD_TOKEN is not set")
        if not cls.LLM_MODEL:
            raise ValueError("LLM_MODEL is not set")

        # データディレクトリの作成
        cls.DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
