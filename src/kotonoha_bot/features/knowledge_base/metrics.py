"""メトリクス収集（Prometheus）"""

from prometheus_client import Counter, Gauge, Histogram

# Embedding処理のメトリクス
embedding_processing_duration = Histogram(
    "embedding_processing_seconds",
    "Time spent processing embeddings",
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0],  # バケット設定
)

pending_chunks_gauge = Gauge(
    "pending_chunks_count",
    "Number of chunks waiting for embedding",
)

embedding_errors_counter = Counter(
    "embedding_errors_total",
    "Total embedding errors",
    ["error_type"],  # エラータイプでラベル付け
)

embedding_processed_counter = Counter(
    "embedding_processed_total",
    "Total embeddings processed successfully",
)

# データベースのメトリクス
db_query_duration = Histogram(
    "db_query_duration_seconds",
    "Database query execution time",
    ["query_type"],  # SELECT, INSERT, UPDATE等でラベル付け
)

db_pool_size = Gauge(
    "db_pool_size",
    "Database connection pool size",
    ["state"],  # 'active', 'idle', 'max'等
)

# セッションアーカイブのメトリクス
session_archive_duration = Histogram(
    "session_archive_seconds",
    "Time spent archiving sessions",
    buckets=[1.0, 5.0, 10.0, 30.0, 60.0],  # バケット設定
)

sessions_archived_counter = Counter(
    "sessions_archived_total",
    "Total sessions archived",
)

sessions_archived_errors_counter = Counter(
    "sessions_archived_errors_total",
    "Total session archive errors",
    ["error_type"],  # エラータイプでラベル付け
)
