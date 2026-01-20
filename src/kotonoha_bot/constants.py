"""定数の一箇所集約（マジックナンバーの散在を防ぐ）."""


class DatabaseConstants:
    """データベース関連の定数."""

    POOL_ACQUIRE_TIMEOUT = 30.0  # 接続プール取得のタイムアウト（秒）


class SearchConstants:
    """検索関連の定数."""

    VECTOR_CAST = "halfvec"  # ベクトル型キャスト（halfvec固定採用）
    VECTOR_DIMENSION = 1536  # ベクトル次元数（OpenAI text-embedding-3-small）
    VECTOR_SEARCH_CANDIDATE_LIMIT = 50  # ベクトル検索の候補数（ハイブリッド検索用）
    KEYWORD_SEARCH_LIMIT = 100  # キーワード検索の上限（ハイブリッド検索用）
