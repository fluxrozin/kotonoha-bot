"""設定管理モジュール。."""

from pathlib import Path

from dotenv import load_dotenv
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# .envファイルの読み込み（既存の環境変数は上書きしない）
load_dotenv(override=False)


class Config(BaseSettings):
    """アプリケーション設定（Pydantic V2）.

    すべての環境変数を一元管理します。
    型チェックとバリデーションが自動的に行われます。
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,  # 環境変数名は大文字小文字を区別しない
        extra="ignore",  # 未定義の環境変数は無視
    )

    # Discord設定
    discord_token: str = ""
    bot_prefix: str = "!"

    # LLM設定（Anthropic SDK）
    llm_model: str = "claude-sonnet-4-5"
    llm_temperature: float = 0.7
    llm_max_tokens: int = 2048
    llm_fallback_model: str | None = None
    # リトライ設定（一時的なエラーに対するリトライ）
    llm_max_retries: int = 3  # 最大リトライ回数
    llm_retry_delay_base: float = 1.0  # 指数バックオフのベース遅延（秒）

    # データベース設定
    database_name: str = "sessions.db"
    database_path: Path = Path("./data/sessions.db")

    # ログ設定
    log_level: str = "INFO"
    log_file: str | None = None
    log_max_size: int = 10  # MB
    log_backup_count: int = 5

    # セッション設定
    max_sessions: int = 100  # メモリ内の最大セッション数
    session_timeout_hours: int = 24  # セッションのタイムアウト（時間）

    # ヘルスチェック設定
    health_check_enabled: bool = True
    health_check_port: int = (
        8080  # 固定ポート（docker-compose.yml と一致させる必要があります）
    )

    # 聞き耳型設定
    eavesdrop_enabled_channels: str = ""  # カンマ区切りのチャンネルID
    eavesdrop_judge_model: str = "claude-haiku-4-5"  # 判定用モデル
    eavesdrop_buffer_size: int = 20  # バッファサイズ
    eavesdrop_min_messages: int = (
        3  # 判定・応答生成に必要な最低メッセージ数（会話の流れを理解するため）
    )
    eavesdrop_min_intervention_interval_minutes: int = 10  # 介入の最小間隔（分）

    # スレッド型設定
    thread_auto_archive_duration: int | None = (
        None  # スレッドの自動アーカイブ期間（分）
    )
    # 有効な値: 60 (1時間), 1440 (1日), 4320 (3日), 10080 (7日), 43200 (30日)
    # None の場合はサーバーのデフォルト値を使用

    @field_validator("thread_auto_archive_duration", mode="before")
    @classmethod
    def validate_thread_auto_archive_duration(cls, v: str | int | None) -> int | None:
        """空文字列をNoneに変換する."""
        if v == "" or v is None:
            return None
        if isinstance(v, str):
            return int(v)
        return v

    # レート制限設定
    rate_limit_capacity: int = 50  # レート制限の上限値（1分間に50リクエストまで）
    rate_limit_refill: float = 0.8  # 補充レート（リクエスト/秒、1分間に約48リクエスト）
    rate_limit_window: int = 60  # 監視ウィンドウ（秒）
    rate_limit_threshold: float = 0.9  # 警告閾値（0.0-1.0）

    # API キー設定（必須）
    openai_api_key: str = ""
    anthropic_api_key: str = ""

    def model_post_init(self, __context) -> None:
        """モデル初期化後の処理。.

        データベースパスの生成など、初期化後に必要な処理を実行します。
        """
        # データベースパスの生成
        if self.database_name:
            self.database_path = Path(f"./data/{self.database_name}")

    def validate_config(self, skip_in_test: bool = False) -> None:
        """設定の検証。.

        Args:
            skip_in_test: テスト環境では True に設定して検証をスキップ
        """
        # テスト環境では検証をスキップ
        if skip_in_test:
            return

        if not self.discord_token:
            raise ValueError("DISCORD_TOKEN is not set")
        if not self.llm_model:
            raise ValueError("LLM_MODEL is not set")
        if not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY is not set")
        if not self.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY is not set")

        # データディレクトリの作成
        self.database_path.parent.mkdir(parents=True, exist_ok=True)

    # 後方互換性のためのプロパティ（大文字の属性名）
    @property
    def DISCORD_TOKEN(self) -> str:
        """Discord トークン（後方互換性）."""
        return self.discord_token

    @property
    def BOT_PREFIX(self) -> str:
        """Bot プレフィックス（後方互換性）."""
        return self.bot_prefix

    @property
    def LLM_MODEL(self) -> str:
        """LLM モデル（後方互換性）."""
        return self.llm_model

    @property
    def LLM_TEMPERATURE(self) -> float:
        """LLM 温度（後方互換性）."""
        return self.llm_temperature

    @property
    def LLM_MAX_TOKENS(self) -> int:
        """LLM 最大トークン数（後方互換性）."""
        return self.llm_max_tokens

    @property
    def LLM_FALLBACK_MODEL(self) -> str | None:
        """LLM フォールバックモデル（後方互換性）."""
        return self.llm_fallback_model

    @property
    def LLM_MAX_RETRIES(self) -> int:
        """LLM 最大リトライ回数（後方互換性）."""
        return self.llm_max_retries

    @property
    def LLM_RETRY_DELAY_BASE(self) -> float:
        """LLM リトライ遅延ベース（後方互換性）."""
        return self.llm_retry_delay_base

    @property
    def DATABASE_NAME(self) -> str:
        """データベース名（後方互換性）."""
        return self.database_name

    @property
    def DATABASE_PATH(self) -> Path:
        """データベースパス（後方互換性）."""
        return self.database_path

    @property
    def LOG_LEVEL(self) -> str:
        """ログレベル（後方互換性）."""
        return self.log_level

    @property
    def LOG_FILE(self) -> str | None:
        """ログファイル（後方互換性）."""
        return self.log_file

    @property
    def LOG_MAX_SIZE(self) -> int:
        """ログ最大サイズ（後方互換性）."""
        return self.log_max_size

    @property
    def LOG_BACKUP_COUNT(self) -> int:
        """ログバックアップ数（後方互換性）."""
        return self.log_backup_count

    @property
    def MAX_SESSIONS(self) -> int:
        """最大セッション数（後方互換性）."""
        return self.max_sessions

    @property
    def SESSION_TIMEOUT_HOURS(self) -> int:
        """セッションタイムアウト（後方互換性）."""
        return self.session_timeout_hours

    @property
    def HEALTH_CHECK_ENABLED(self) -> bool:
        """ヘルスチェック有効化（後方互換性）."""
        return self.health_check_enabled

    @property
    def HEALTH_CHECK_PORT(self) -> int:
        """ヘルスチェックポート（後方互換性）."""
        return self.health_check_port

    @property
    def EAVESDROP_ENABLED_CHANNELS(self) -> str:
        """聞き耳型有効チャンネル（後方互換性）."""
        return self.eavesdrop_enabled_channels

    @property
    def EAVESDROP_JUDGE_MODEL(self) -> str:
        """聞き耳型判定モデル（後方互換性）."""
        return self.eavesdrop_judge_model

    @property
    def EAVESDROP_BUFFER_SIZE(self) -> int:
        """聞き耳型バッファサイズ（後方互換性）."""
        return self.eavesdrop_buffer_size

    @property
    def EAVESDROP_MIN_MESSAGES(self) -> int:
        """聞き耳型最小メッセージ数（後方互換性）."""
        return self.eavesdrop_min_messages

    @property
    def EAVESDROP_MIN_INTERVENTION_INTERVAL_MINUTES(self) -> int:
        """聞き耳型最小介入間隔（後方互換性）."""
        return self.eavesdrop_min_intervention_interval_minutes

    @property
    def THREAD_AUTO_ARCHIVE_DURATION(self) -> int | None:
        """スレッド自動アーカイブ期間（後方互換性）."""
        return self.thread_auto_archive_duration

    @property
    def RATE_LIMIT_CAPACITY(self) -> int:
        """レート制限容量（後方互換性）."""
        return self.rate_limit_capacity

    @property
    def RATE_LIMIT_REFILL(self) -> float:
        """レート制限補充率（後方互換性）."""
        return self.rate_limit_refill

    @property
    def RATE_LIMIT_WINDOW(self) -> int:
        """レート制限ウィンドウ（後方互換性）."""
        return self.rate_limit_window

    @property
    def RATE_LIMIT_THRESHOLD(self) -> float:
        """レート制限閾値（後方互換性）."""
        return self.rate_limit_threshold

    @property
    def OPENAI_API_KEY(self) -> str:
        """OpenAI API キー（後方互換性）."""
        return self.openai_api_key

    @property
    def ANTHROPIC_API_KEY(self) -> str:
        """Anthropic API キー（後方互換性）."""
        return self.anthropic_api_key


# グローバルインスタンス（main.py でのみ使用）
_config_instance: Config | None = None


def get_config() -> Config:
    """設定インスタンスを取得（main.py でのみ使用）.

    Returns:
        Config インスタンス

    Note:
        テスト容易性のため、main.py 以外では使用しないこと。
        全てのクラスはコンストラクタで config を受け取る。
    """
    global _config_instance
    if _config_instance is None:
        _config_instance = Config()
    return _config_instance


class Settings(BaseSettings):
    """アプリケーション設定クラス（pydantic-settings使用）.

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
    # 有効な値: 60 (1時間), 1440 (1日), 4320 (3日), 10080 (7日), 43200 (30日)
    # None の場合はサーバーのデフォルト値を使用

    @field_validator("thread_auto_archive_duration", mode="before")
    @classmethod
    def validate_thread_auto_archive_duration(cls, v: str | int | None) -> int | None:
        """空文字列をNoneに変換する."""
        if v == "" or v is None:
            return None
        if isinstance(v, str):
            return int(v)
        return v

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
