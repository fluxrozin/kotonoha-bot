"""定数の一箇所集約（マジックナンバーの散在を防ぐ）"""


class DatabaseConstants:
    """データベース関連の定数"""

    POOL_ACQUIRE_TIMEOUT = 30.0  # 接続プール取得のタイムアウト（秒）
    GRACEFUL_SHUTDOWN_TIMEOUT = 60.0  # Graceful shutdownのタイムアウト（秒）


class SearchConstants:
    """検索関連の定数"""

    VECTOR_CAST = "halfvec"  # ベクトル型キャスト（halfvec固定採用）
    VECTOR_DIMENSION = 1536  # ベクトル次元数（OpenAI text-embedding-3-small）
    VECTOR_SEARCH_CANDIDATE_LIMIT = 50  # ベクトル検索の候補数（ハイブリッド検索用）
    KEYWORD_SEARCH_LIMIT = 100  # キーワード検索の上限（ハイブリッド検索用）


class BatchConstants:
    """バッチ処理関連の定数"""

    BATCH_INSERT_SIZE = 100  # チャンク一括登録のバッチサイズ
    BATCH_UPDATE_SIZE = 100  # チャンク一括更新のバッチサイズ


class EmbeddingConstants:
    """Embedding処理関連の定数"""

    MAX_RETRY_COUNT = 3  # 最大リトライ回数（デフォルト）


class ArchiveConstants:
    """アーカイブ処理関連の定数"""

    DEFAULT_OVERLAP_MESSAGES = 5  # デフォルトののりしろメッセージ数


class ErrorConstants:
    """エラーコード定数"""

    EMBEDDING_API_TIMEOUT = "EMBEDDING_API_TIMEOUT"
    EMBEDDING_RATE_LIMIT = "EMBEDDING_RATE_LIMIT"
    EMBEDDING_API_ERROR = "EMBEDDING_API_ERROR"
    DATABASE_CONNECTION_ERROR = "DATABASE_CONNECTION_ERROR"
    DATABASE_QUERY_ERROR = "DATABASE_QUERY_ERROR"
