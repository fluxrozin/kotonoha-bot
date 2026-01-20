# PostgreSQL スキーマ設計書 - 完全なDDLスクリプト

**作成日**: 2026年1月19日  
**バージョン**: 1.22  
**対象プロジェクト**: kotonoha-bot v0.8.0

## 関連ドキュメント

- [概要](./postgresql-schema-overview.md)
- [テーブル定義](./postgresql-schema-tables.md)
- [インデックス設計](./postgresql-schema-indexes.md)
- [クエリガイド](../../50_implementation/51_guides/postgresql-query-guide.md)

---

## 完全なDDLスクリプト

```sql
-- ============================================
-- kotonoha-bot PostgreSQL Schema
-- Version: 1.0
-- Created: 2026-01-19
-- ============================================

-- 拡張機能の有効化
CREATE EXTENSION IF NOT EXISTS vector;

-- ハイブリッド検索用（オプション、将来の拡張用）
-- CREATE EXTENSION IF NOT EXISTS pg_bigm;

-- ENUM型の定義
DO $$ BEGIN
    CREATE TYPE source_type_enum AS ENUM (
        'discord_session',
        'document_file',
        'web_page',
        'image_caption',
        'audio_transcript'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE session_status_enum AS ENUM (
        'active',
        'archived'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE source_status_enum AS ENUM (
        'pending',
        'processing',
        'completed',
        'partial',  -- ⚠️ 改善（データ整合性）: 一部のチャンクがDLQに移動した（検索可能だが不完全）
        'failed'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- sessions テーブル
-- ⚠️ 改善（Strong Recommendation）: id BIGSERIAL PRIMARY KEY を追加し、
-- session_key は UNIQUE NOT NULL に変更
-- 理由: 「新規設計で移行ツールを作らない」という前提であれば、最初から最適解を選ぶべき
-- TEXT型の主キーはインデックスサイズが肥大化し、将来的に外部キー参照を行う際に
-- パフォーマンス（JOIN速度）とストレージ効率が悪化する
CREATE TABLE IF NOT EXISTS sessions (
    id BIGSERIAL PRIMARY KEY,
    session_key TEXT UNIQUE NOT NULL,  -- アプリケーション内部での参照用
    session_type TEXT NOT NULL,
    messages JSONB DEFAULT '[]'::jsonb NOT NULL,
    status session_status_enum DEFAULT 'active',
    guild_id BIGINT,        -- Discord Guild ID（Discord URL生成に必要）
    channel_id BIGINT,
    thread_id BIGINT,
    user_id BIGINT,
    version INT DEFAULT 1,  -- ⚠️ 追加: 楽観的ロック用（更新ごとにインクリメント）
    last_archived_message_index INT DEFAULT 0,
        -- ⚠️ 改善: アーカイブ済みメッセージのインデックス（0=未アーカイブ）
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    last_active_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- knowledge_sources テーブル
CREATE TABLE IF NOT EXISTS knowledge_sources (
    id BIGSERIAL PRIMARY KEY,
    type source_type_enum NOT NULL,
    title TEXT NOT NULL,
    uri TEXT,
    status source_status_enum DEFAULT 'pending',
    error_code TEXT,
        -- ⚠️ 改善（セキュリティ）: エラーコード
        -- （例: 'EMBEDDING_API_TIMEOUT', 'RATE_LIMIT'）
    error_message TEXT,  -- ⚠️ 改善（セキュリティ）: 一般化されたメッセージのみ（詳細なスタックトレースはログのみに出力）
    -- ⚠️ 改善（疎結合）: origin_session_id は外部キーではなく metadata に記録
    -- セッションからアーカイブされたソースの場合、
    -- metadata に origin_session_id と origin_session_key を記録
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- knowledge_chunks テーブル
-- ⚠️ 重要: embedding は NULL許容です
-- Embedding生成前のデータをINSERTし、後でUPDATEするフローを採用
-- 理由: トランザクション分離のため（FOR UPDATE SKIP LOCKED + Tx分離パターン）
-- 検索時は必ず embedding IS NOT NULL 条件を含めること（HNSWインデックス使用のため）
CREATE TABLE IF NOT EXISTS knowledge_chunks (
    id BIGSERIAL PRIMARY KEY,
    source_id BIGINT REFERENCES knowledge_sources(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    embedding halfvec(1536),  -- ⚠️ NULL許容、halfvec固定採用
    location JSONB DEFAULT '{}'::jsonb,
    token_count INT,
    retry_count INT DEFAULT 0,  -- Dead Letter Queue対応
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- knowledge_chunks_dlq テーブル（Dead Letter Queue）
CREATE TABLE IF NOT EXISTS knowledge_chunks_dlq (
    id BIGSERIAL PRIMARY KEY,
    original_chunk_id BIGINT,
    source_id BIGINT,           -- ⚠️ 改善: 元のソースID（外部キー制約なし）
    source_title TEXT,          -- ⚠️ 改善: デバッグ用にソースのタイトルも保存
    content TEXT NOT NULL,
    error_code TEXT,            -- ⚠️ 改善: エラーコードを分離して保存
    error_message TEXT,
    retry_count INT DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    last_retry_at TIMESTAMPTZ
);

-- インデックスの作成
CREATE INDEX IF NOT EXISTS idx_sessions_session_key ON sessions(session_key);
-- アプリケーション内部での参照用
CREATE INDEX IF NOT EXISTS idx_sessions_status ON sessions(status);
CREATE INDEX IF NOT EXISTS idx_sessions_last_active_at
  ON sessions(last_active_at);
CREATE INDEX IF NOT EXISTS idx_sessions_channel_id ON sessions(channel_id);
CREATE INDEX IF NOT EXISTS idx_sessions_archive_candidates
  ON sessions(status, last_active_at)
WHERE status = 'active';

CREATE INDEX IF NOT EXISTS idx_sources_metadata ON knowledge_sources USING gin (metadata);
CREATE INDEX IF NOT EXISTS idx_sources_status ON knowledge_sources(status);
CREATE INDEX IF NOT EXISTS idx_sources_type ON knowledge_sources(type);

CREATE INDEX IF NOT EXISTS idx_chunks_embedding ON knowledge_chunks 
USING hnsw (embedding halfvec_cosine_ops)
WITH (m = 16, ef_construction = 64);

CREATE INDEX IF NOT EXISTS idx_chunks_source_id ON knowledge_chunks(source_id);
-- ⚠️ 重要: この部分インデックスは必須です
-- HNSWインデックス（idx_chunks_embedding）は embedding が NULL でない
-- 場合にのみ有効。検索クエリで embedding IS NOT NULL 条件を忘れると、
-- HNSWインデックスが使われずフルスキャンになる
CREATE INDEX IF NOT EXISTS \
idx_chunks_searchable ON knowledge_chunks(source_id, created_at)
WHERE embedding IS NOT NULL AND token_count > 0;

-- ⚠️ 改善（パフォーマンス）: 処理待ち行列専用の部分インデックス
-- FOR UPDATE SKIP LOCKED を使うクエリは WHERE embedding IS NULL を参照します。
-- knowledge_chunks が数百万件になった際、embedding IS NULL の行を探すのに
-- 時間がかかるとバッチ処理が遅延します。
-- 処理待ち行列専用の部分インデックスを作成することで、ワーカーはテーブル全体を
-- スキャンせず、インデックスのみを見て処理対象を即座に見つけられます。
-- リトライ上限未満（retry_count < 3）のみを含めることで、諦められたチャンクを除外
CREATE INDEX IF NOT EXISTS idx_chunks_queue ON knowledge_chunks(id)
WHERE embedding IS NULL AND retry_count < 3;

-- ハイブリッド検索用インデックス（オプション、将来の拡張用）
-- pg_bigm 拡張を有効化した後に実行
-- CREATE INDEX IF NOT EXISTS idx_chunks_content_trgm ON knowledge_chunks 
-- USING gin (content gin_trgm_ops);

-- 制約の追加
ALTER TABLE sessions 
ADD CONSTRAINT chk_sessions_status 
CHECK (status IN ('active', 'archived'));

ALTER TABLE knowledge_sources 
ADD CONSTRAINT chk_sources_status 
CHECK (status IN ('pending', 'processing', 'completed', 'partial', 'failed'));
```

### B. 環境変数一覧

**⚠️ 重要**: 本番環境では `DATABASE_URL` にパスワードを含める形式ではなく、
以下のように分離することを推奨します：

```bash
# 推奨: パスワードを分離
POSTGRES_HOST=postgres
POSTGRES_PORT=5433
POSTGRES_DB=kotonoha
POSTGRES_USER=kotonoha
POSTGRES_PASSWORD=<secret>
```

| 環境変数 | 説明 | デフォルト値 |
|---------|------|------------|
| `DATABASE_URL` | PostgreSQL接続文字列（開発環境用） | `postgresql://kotonoha:password@localhost:5433/kotonoha` |
| `POSTGRES_HOST` | PostgreSQLホスト（本番環境推奨） | - |
| `POSTGRES_PORT` | PostgreSQLポート（本番環境推奨） | `5433` |
| `POSTGRES_DB` | データベース名（本番環境推奨） | - |
| `POSTGRES_USER` | ユーザー名（本番環境推奨） | - |
| `POSTGRES_PASSWORD` | パスワード（本番環境推奨、シークレット管理） | - |
| `DB_POOL_MIN_SIZE` | 接続プール最小サイズ | `5` |
| `DB_POOL_MAX_SIZE` | 接続プール最大サイズ | `20` |
| `DB_COMMAND_TIMEOUT` | コマンドタイムアウト（秒） | `60` |
| ~~`KB_USE_HALFVEC`~~ | ~~halfvec使用フラグ~~ | ~~削除（halfvec固定採用）~~ |
| `KB_HNSW_M` | HNSWインデックス m パラメータ | `16` |
| `KB_HNSW_EF_CONSTRUCTION` | HNSWインデックス ef_construction パラメータ | `64` |
| `KB_SIMILARITY_THRESHOLD` | 類似度検索の閾値 | `0.7` |
| `KB_DEFAULT_TOP_K` | デフォルトの検索結果数 | `10` |
| `KB_EMBEDDING_MAX_RETRY` | Embedding処理の最大リトライ回数 | `3` |
| `KB_EMBEDDING_BATCH_SIZE` | Embedding処理のバッチサイズ | `100` |
| `KB_CHUNK_MAX_TOKENS` | チャンクの最大トークン数 | `4000` |
| `KB_CHUNK_OVERLAP_RATIO` | チャンクのオーバーラップ比率 | `0.2` |
| `KB_CHUNK_INSERT_BATCH_SIZE` | チャンク一括登録時のバッチサイズ | `100` |
| `KB_CHUNK_UPDATE_BATCH_SIZE` | チャンク一括更新時のバッチサイズ | `100` |

---

### C. ヘルスチェック実装

**目的**: データベース接続の確認を含むヘルスチェックエンドポイントを実装します。

⚠️ 改善（コード品質）: ヘルスチェックの不完全さを改善します。
pgvector拡張の動作確認が含まれていませんでした。

```python
# src/kotonoha_bot/health.py
"""ヘルスチェック機能（DB接続確認含む）"""

import asyncpg
import structlog
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .db.postgres import PostgreSQLDatabase

logger = structlog.get_logger(__name__)


async def health_check(db: "PostgreSQLDatabase") -> dict:
    """ヘルスチェック（DB接続確認含む）
    
    Returns:
        dict: ヘルスステータス
            - status: "healthy" または "unhealthy"
            - database: "connected" または "disconnected"
            - error: エラーメッセージ（unhealthyの場合）
    """
    try:
        async with db.pool.acquire() as conn:
            # 基本的な接続確認
            await conn.fetchval("SELECT 1")
            
            # ⚠️ 改善: pgvector の動作確認も含める
            # pgvector拡張が正しく動作していることを確認
            # ベクトル演算（<=>演算子）が使用可能であることを確認
            result = await conn.fetchval(
                "SELECT '[1,2,3]'::vector <=> '[1,2,3]'::vector"
            )
            if result is None:
                return {
                    "status": "unhealthy",
                    "database": "connected",
                    "pgvector": "not_working",
                    "error": "pgvector extension not working properly"
                }
            
            # pgvector拡張のバージョン確認（オプション）
            pgvector_version = await conn.fetchval(
                "SELECT extversion FROM pg_extension WHERE extname = 'vector'"
            )
            
        return {
            "status": "healthy",
            "database": "connected",
            "pgvector": "working",
            "pgvector_version": pgvector_version
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}", exc_info=True)
        return {
            "status": "unhealthy",
            "database": "disconnected",
            "error": str(e)
        }
```

**FastAPIエンドポイント例**:

```python
# src/kotonoha_bot/api/health.py
from fastapi import APIRouter, Depends
from ...health import health_check
from ...db.postgres import PostgreSQLDatabase

router = APIRouter()

@router.get("/health")
async def get_health(db: PostgreSQLDatabase = Depends(get_db)):
    """ヘルスチェックエンドポイント"""
    return await health_check(db)
```

**docker-compose.yml のヘルスチェック設定**:

```yaml
services:
  bot:
    # ... その他の設定
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
```

---