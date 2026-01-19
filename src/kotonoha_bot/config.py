"""設定管理モジュール"""

import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

# .envファイルの読み込み（既存の環境変数は上書きしない）
load_dotenv(override=False)


class Config:
    """アプリケーション設定"""

    # Discord設定
    DISCORD_TOKEN: str = os.getenv("DISCORD_TOKEN", "")
    BOT_PREFIX: str = os.getenv("BOT_PREFIX", "!")

    # LLM設定（Anthropic SDK）
    LLM_MODEL: str = os.getenv("LLM_MODEL", "claude-sonnet-4-5")
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
        "EAVESDROP_JUDGE_MODEL", "claude-haiku-4-5"
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
    _thread_auto_archive_duration_str = os.getenv("THREAD_AUTO_ARCHIVE_DURATION")
    THREAD_AUTO_ARCHIVE_DURATION: int | None = (
        int(_thread_auto_archive_duration_str)
        if _thread_auto_archive_duration_str is not None
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

        # API キーの検証（環境変数から直接確認）
        if not os.getenv("OPENAI_API_KEY"):
            raise ValueError("OPENAI_API_KEY is not set")
        if not os.getenv("ANTHROPIC_API_KEY"):
            raise ValueError("ANTHROPIC_API_KEY is not set")

        # データディレクトリの作成
        cls.DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)


class Settings(BaseSettings):
    """アプリケーション設定クラス（pydantic-settings使用）

    すべての環境変数を一元管理します。
    型チェックとバリデーションが自動的に行われます。

    ⚠️ Phase 8移行: 既存のConfigクラスから段階的に移行中
    既存コードとの互換性のため、Configクラスも残しています。
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,  # 環境変数名は大文字小文字を区別しない
        extra="ignore",  # 未定義の環境変数は無視
    )

    # ============================================
    # データベース設定
    # ============================================

    # 接続プール設定
    db_pool_min_size: int = 5
    db_pool_max_size: int = 20
    db_command_timeout: int = 60

    # PostgreSQL接続設定（本番環境推奨: パスワードを分離）
    postgres_host: str | None = None
    postgres_port: int = 5432
    postgres_db: str = "kotonoha"
    postgres_user: str = "kotonoha"
    postgres_password: str | None = None

    # 開発環境用（DATABASE_URL、後方互換性のため残す）
    database_url: str | None = None

    # ============================================
    # 知識ベース設定（PostgreSQL + pgvector）
    # ============================================

    # HNSWインデックスパラメータ
    kb_hnsw_m: int = 16
    kb_hnsw_ef_construction: int = 64

    # 検索設定
    kb_similarity_threshold: float = 0.7
    kb_default_top_k: int = 10

    # Embedding処理設定
    kb_embedding_max_retry: int = 3
    kb_embedding_batch_size: int = 100
    kb_embedding_max_concurrent: int = 5
    kb_embedding_interval_minutes: int = 1

    # チャンク登録・更新のバッチサイズ制御
    kb_chunk_insert_batch_size: int = 100
    kb_chunk_update_batch_size: int = 100

    # セッションアーカイブ設定
    kb_archive_threshold_hours: int = 1
    kb_archive_batch_size: int = 10
    kb_archive_interval_hours: int = 1
    kb_min_session_length: int = 30
    kb_archive_overlap_messages: int = 5

    # チャンク分割設定
    kb_chunk_max_tokens: int = 4000
    kb_chunk_overlap_ratio: float = 0.2

    # チャンク化戦略（message_based または token_based）
    kb_chat_chunk_strategy: str = "message_based"
    kb_chat_chunk_size_messages: int = 5
    kb_chat_chunk_overlap_messages: int = 2

    # ============================================
    # Discord設定
    # ============================================

    discord_token: str = ""  # 環境変数から読み込む（空文字列は後でバリデーション）

    # ============================================
    # API キー設定（必須）
    # ============================================

    openai_api_key: str = ""  # 環境変数から読み込む（空文字列は後でバリデーション）
    anthropic_api_key: str = ""  # 環境変数から読み込む（空文字列は後でバリデーション）

    # ============================================
    # その他の設定（既存の設定）
    # ============================================

    # LLM設定
    llm_model: str = "claude-opus-4-5"
    llm_temperature: float = 0.7
    llm_max_tokens: int = 2048

    # Bot設定
    bot_prefix: str = "!"

    # セッション管理設定
    session_timeout_hours: int = 72
    max_sessions: int = 100

    # ログ設定
    log_level: str = "INFO"
    log_file: str = "./logs/run.log"
    log_max_size: int = 10
    log_backup_count: int = 5

    # 聞き耳型設定
    eavesdrop_enabled_channels: str = ""  # カンマ区切りのチャンネルID
    eavesdrop_judge_model: str = "claude-haiku-4-5"
    eavesdrop_buffer_size: int = 20
    eavesdrop_min_messages: int = 3
    eavesdrop_min_intervention_interval_minutes: int = 10

    # スレッド型設定
    thread_auto_archive_duration: int | None = None

    # レート制限設定
    rate_limit_capacity: int = 50
    rate_limit_refill: float = 0.8
    rate_limit_window: int = 60
    rate_limit_threshold: float = 0.9

    # ヘルスチェック設定
    health_check_enabled: bool = True
    health_check_port: int = 8080


# グローバルシングルトン（アプリケーション全体で使用）
settings = Settings()
