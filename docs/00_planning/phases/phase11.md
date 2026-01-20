# Phase 11: ハイブリッド検索の実装

**作成日**: 2026年1月19日  
**バージョン**: 1.0  
**対象プロジェクト**: kotonoha-bot v0.9.0  
**前提条件**: Phase 8（PostgreSQL + pgvector 実装）完了済み、全テスト通過

---

## 目次

1. [エグゼクティブサマリー](#1-エグゼクティブサマリー)
2. [目的とスコープ](#2-目的とスコープ)
3. [設計方針](#3-設計方針)
4. [実装ステップ](#4-実装ステップ)
5. [完了基準](#5-完了基準)
6. [テスト計画](#6-テスト計画)
7. [導入・デプロイ手順](#7-導入デプロイ手順)
8. [今後の改善計画](#8-今後の改善計画)

---

## 1. エグゼクティブサマリー

### 1.1 目的

Phase 8で実装したベクトル検索に加えて、pg_bigmを使用したキーワード検索を組み合わせたハイブリッド検索を実装し、検索品質を向上させる。

### 1.2 背景

ベクトル検索は「概念的な類似」には強いですが、「固有名詞（例：プロジェクトコード名、特定のエラーコード）」の完全一致検索には弱いです。日本語検索においては、pg_bigmを使用した2-gram（2文字単位）によるキーワード検索を組み合わせることで、検索精度を大幅に向上させることができます。

### 1.3 主要な実装項目

| 項目 | 内容 |
|------|------|
| pg_bigm拡張の有効化 | Dockerfile.postgresでカスタムイメージを作成 |
| ハイブリッド検索メソッド | ベクトル検索とキーワード検索を組み合わせた検索 |
| スコアリング機能 | ベクトル類似度とキーワードスコアを組み合わせたスコア計算 |
| インデックス最適化 | pg_bigm用のGINインデックスの追加 |

### 1.4 実装期間

約 2-3 日

---

## 2. 目的とスコープ

### 2.1 目的

1. **検索品質の向上**: 固有名詞や特定のキーワードを含む検索の精度向上
2. **日本語検索の最適化**: pg_bigmによる2-gram検索による日本語検索の高速化
3. **ハイブリッド検索の実現**: ベクトル検索とキーワード検索を組み合わせた統合検索

### 2.2 スコープ

- **pg_bigm拡張の有効化**: Dockerfile.postgresでカスタムイメージを作成
- **ハイブリッド検索メソッドの実装**: `PostgreSQLDatabase`クラスに`hybrid_search`メソッドを追加
- **スコアリング機能**: ベクトル類似度とキーワードスコアを組み合わせたスコア計算
- **インデックス最適化**: pg_bigm用のGINインデックスの追加（Alembicマイグレーション）

### 2.3 スコープ外

- **pg_trgmの実装**: 日本語検索においてはpg_bigmを採用（2文字の単語に対応）
- **tsvector（FTS）の実装**: オプションとして将来の拡張に備える（今回は実装しない）
- **Reranking機能**: Phase 12で実装予定

---

## 3. 設計方針

### 3.1 pg_bigmの採用理由

**pg_bigmの利点**:

- **2-gram（2文字単位）**: 日本語の多くは2文字以上の熟語で構成されるため、検索漏れがほぼゼロ
- **2文字の単語に対応**: 「設計」「開発」のような2文字の単語も確実に検索可能
- **LIKE演算子の高速化**: PostgreSQL標準の `LIKE '%...%'` 検索を爆速化
- **pg_trgmとの違い**: pg_trgm（3-gram）は2文字の単語が検索漏れしたり、精度が出にくい場合がある

**pg_trgmの限界**:

- 3文字単位のため、「設計」「開発」のような2文字の単語の検索が苦手
- ひらがなの助詞などがノイズになりやすい

### 3.2 ハイブリッド検索の設計

**UNION ALL方式の採用**:

FULL OUTER JOINは両方のCTEを完全評価するため非効率です。UNION ALLを使用した方が効率的です。

**スコアリング方式**:

- **ベクトル類似度**: 0.7の重み（概念的な類似に強い）
- **キーワードスコア**: 0.3の重み（固有名詞の完全一致に強い）

**実装方針**:

1. ベクトル検索で上位50件を取得（候補を広めに取る）
2. キーワード検索で上位100件を取得（`LIKE '%キーワード%'`で検索）
3. 両方の結果をUNION ALLで結合
4. スコアを合計して降順にソート
5. 上位10件を返す

### 3.3 インデックス設計

**pg_bigm用のGINインデックス**:

```sql
CREATE INDEX idx_chunks_content_bigm ON knowledge_chunks 
USING gin (content gin_bigm_ops);
```

**注意点**:

- インデックスサイズが大きくなる傾向がある（2文字の組み合わせの方が3文字よりも多いため）
- 更新速度が若干遅くなる（バックグラウンド処理のため、ユーザー体験への影響は軽微）

---

## 4. 実装ステップ

### 4.1 実装ステップと完了状況

| Step | 内容 | 期間 | 完了状況 | 詳細ドキュメント |
|------|------|------|---------|------------------|
| 0 | 依存関係の確認と設計レビュー | 0.5日 | ⏳ 未実装 | - |
| 1 | Dockerfile.postgresの作成 | 0.5日 | ⏳ 未実装 | [PostgreSQL実装ガイド](../../50_implementation/51_guides/postgresql-implementation-guide.md#dockerfile-での-pg_bigm-の導入) |
| 2 | pg_bigm拡張の有効化（Alembicマイグレーション） | 0.5日 | ⏳ 未実装 | - |
| 3 | ハイブリッド検索メソッドの実装 | 1日 | ⏳ 未実装 | - |
| 4 | テストの実装 | 0.5日 | ⏳ 未実装 | - |
| **合計** | | **2-3日** | **⏳ 未実装** | |

### 4.2 各ステップの詳細

#### Step 0: 依存関係の確認と設計レビュー

**完了内容**:

- Phase 8の実装状況を確認
- pg_bigmのバージョンと互換性を確認
- 設計方針のレビュー

**確認事項**:

- PostgreSQL 18 + pgvector 0.8.1 が正常に動作していること
- `PostgreSQLDatabase`クラスの`similarity_search`メソッドが実装されていること
- `knowledge_chunks`テーブルが存在すること

#### Step 1: Dockerfile.postgresの作成

**完了内容**:

- `Dockerfile.postgres`の作成
- pg_bigmのビルドとインストール
- マルチステージビルドによる最適化

**実装ファイル**: `Dockerfile.postgres`

**実装手順**:

1. プロジェクトルートに`Dockerfile.postgres`を作成する

   ```bash
   # プロジェクトルートで実行
   touch Dockerfile.postgres
   ```

2. 以下の内容を`Dockerfile.postgres`に記述する

   ```dockerfile
   # Dockerfile.postgres
   
   # Stage 1: ビルド環境
   FROM pgvector/pgvector:0.8.1-pg18 AS builder
   
   ARG PG_BIGM_VERSION=1.2-20240606
   ARG PG_BIGM_CHECKSUM=""  # オプション: チェックサム検証用
   
   USER root
   
   # ビルド依存関係のインストール
   RUN apt-get update && apt-get install -y \
       build-essential \
       postgresql-server-dev-18 \
       wget \
       ca-certificates \
       && rm -rf /var/lib/apt/lists/*
   
   # pg_bigm のダウンロード
   RUN wget -O pg_bigm.tar.gz \
       https://github.com/pgbigm/pg_bigm/archive/refs/tags/v${PG_BIGM_VERSION}.tar.gz \
       && if [ -n "$PG_BIGM_CHECKSUM" ]; then \
           echo "$PG_BIGM_CHECKSUM  pg_bigm.tar.gz" | sha256sum -c - || exit 1; \
       fi \
       && mkdir -p /usr/src/pg_bigm \
       && tar -xzf pg_bigm.tar.gz -C /usr/src/pg_bigm --strip-components=1
   
   # pg_bigm のビルド
   WORKDIR /usr/src/pg_bigm
   RUN make USE_PGXS=1 && make USE_PGXS=1 install
   
   # Stage 2: 実行環境（ビルド済みのpg_bigmのみを含む軽量イメージ）
   FROM pgvector/pgvector:0.8.1-pg18
   
   USER root
   
   # ビルド済みのpg_bigmをコピー
   COPY --from=builder \
     /usr/share/postgresql/18/extension/pg_bigm* \
     /usr/share/postgresql/18/extension/
   COPY --from=builder \
     /usr/lib/postgresql/18/lib/pg_bigm.so \
     /usr/lib/postgresql/18/lib/
   
   USER postgres
   ```

3. ビルドをテストする（オプション）

   ```bash
   # カスタムイメージのビルド（時間がかかる場合がある）
   docker build -f Dockerfile.postgres -t kotonoha-postgres:test .
   ```

**参考**: [PostgreSQL実装ガイド - Dockerfileでのpg_bigmの導入](../../50_implementation/51_guides/postgresql-implementation-guide.md#dockerfile-での-pg_bigm-の導入)

**注意点**:

- pg_bigmのバージョンは`1.2-20240606`を使用
- GitHubリリースへの依存があるため、チェックサム検証を推奨
- 開発環境では標準のpgvectorイメージを使用（ビルド時間の短縮）
- ビルドには10-20分程度かかる場合がある

#### Step 2: pg_bigm拡張の有効化（Alembicマイグレーション）

**完了内容**:

- Alembicマイグレーションファイルの作成
- pg_bigm拡張の有効化
- GINインデックスの作成

**実装手順**:

1. Alembicマイグレーションファイルを作成する

   ```bash
   # プロジェクトルートで実行
   alembic revision -m "add_pg_bigm_extension"
   ```

   このコマンドにより、`alembic/versions/`ディレクトリに新しいマイグレーションファイルが作成される。
   ファイル名は`{revision_id}_add_pg_bigm_extension.py`の形式になる。

2. 作成されたマイグレーションファイルを編集する

   ```python
   """add_pg_bigm_extension

   Revision ID: {revision_id}
   Revises: ca650c17adda
   Create Date: {create_date}

   """
   from typing import Sequence

   from alembic import op
   import sqlalchemy as sa

   # revision identifiers, used by Alembic.
   revision: str = "{revision_id}"
   down_revision: str | Sequence[str] | None = "ca650c17adda"
   branch_labels: str | Sequence[str] | None = None
   depends_on: str | Sequence[str] | None = None


   def upgrade() -> None:
       """Upgrade schema."""
       # pg_bigm拡張の有効化
       op.execute("CREATE EXTENSION IF NOT EXISTS pg_bigm")
       
       # knowledge_chunks.contentにGINインデックス（pg_bigm）を追加
       op.execute("""
           CREATE INDEX IF NOT EXISTS idx_chunks_content_bigm 
           ON knowledge_chunks 
           USING gin (content gin_bigm_ops)
       """)


   def downgrade() -> None:
       """Downgrade schema."""
       # インデックスの削除
       op.execute("DROP INDEX IF EXISTS idx_chunks_content_bigm")
       
       # pg_bigm拡張の削除（注意: 他のテーブルで使用されている場合はエラーになる）
       op.execute("DROP EXTENSION IF EXISTS pg_bigm")
   ```

   **重要**: `down_revision`は、最新のマイグレーションファイルの`revision`IDに設定する必要がある。
   現在の最新マイグレーションは`ca650c17adda`（initial_schema）である。

3. マイグレーションをテストする（開発環境）

   ```bash
   # マイグレーションの適用（開発環境）
   alembic upgrade head
   
   # マイグレーションのロールバック（テスト用）
   alembic downgrade -1
   
   # 再度適用
   alembic upgrade head
   ```

**実装ファイル**: `alembic/versions/{revision_id}_add_pg_bigm_extension.py`

**マイグレーション内容**:

```sql
-- pg_bigm拡張の有効化
CREATE EXTENSION IF NOT EXISTS pg_bigm;

-- knowledge_chunks.contentにGINインデックス（pg_bigm）を追加
CREATE INDEX idx_chunks_content_bigm ON knowledge_chunks 
USING gin (content gin_bigm_ops);
```

**注意点**:

- 既存のデータがある場合、インデックス作成に時間がかかる可能性がある（データ量に応じて数分〜数十分）
- 本番環境ではメンテナンスウィンドウを設けることを推奨
- `down_revision`は必ず最新のマイグレーションの`revision`IDに設定すること
- マイグレーションファイルの`revision`IDは自動生成されるため、手動で変更しないこと

#### Step 3: ハイブリッド検索メソッドの実装

**完了内容**:

- `PostgreSQLDatabase`クラスに`hybrid_search`メソッドを追加
- ベクトル検索とキーワード検索を組み合わせた検索ロジックの実装
- スコアリング機能の実装

**実装ファイル**: `src/kotonoha_bot/db/postgres.py`

**実装手順**:

1. `src/kotonoha_bot/db/postgres.py`を開く

2. `PostgreSQLDatabase`クラス内に`hybrid_search`メソッドを追加する

   ```python
   async def hybrid_search(
       self,
       query_embedding: list[float],
       query_text: str,
       limit: int = 10,
       vector_weight: float = 0.7,
       keyword_weight: float = 0.3,
       filters: dict | None = None,
   ) -> list[SearchResult]:
       """ハイブリッド検索（ベクトル検索 + キーワード検索）
       
       Args:
           query_embedding: クエリのベクトル（1536次元）
           query_text: クエリのテキスト（キーワード検索用）
           limit: 返却する結果の数（デフォルト: 10）
           vector_weight: ベクトル類似度の重み（デフォルト: 0.7）
           keyword_weight: キーワードスコアの重み（デフォルト: 0.3）
           filters: フィルタ条件（source_type, channel_id, user_id等）
       
       Returns:
           検索結果のリスト（スコア順）
       """
       from ..constants import DatabaseConstants, SearchConstants
       
       vector_cast = SearchConstants.VECTOR_CAST
       vector_dimension = SearchConstants.VECTOR_DIMENSION
       
       # 重みの合計が1.0になることを確認
       if abs(vector_weight + keyword_weight - 1.0) > 0.001:
           raise ValueError(
               f"vector_weight ({vector_weight}) + keyword_weight ({keyword_weight}) "
               "must equal 1.0"
           )
       
       # キーワード検索用のLIKEパターンを作成（SQLインジェクション対策）
       # query_textは信頼できる入力として扱う（内部からの呼び出しのみ）
       keyword_pattern = f"%{query_text}%"
       
       try:
           from asyncio import timeout
           
           async with timeout(DatabaseConstants.POOL_ACQUIRE_TIMEOUT):
               async with self._ensure_pool().acquire() as conn:
                   # ベースクエリの構築
                   query = f"""
                       WITH vector_results AS (
                           SELECT 
                               s.id as source_id,
                               s.type,
                               s.title,
                               s.uri,
                               s.metadata as source_metadata,
                               c.id as chunk_id,
                               c.content,
                               c.location,
                               c.token_count,
                               1 - (c.embedding <=> $1::{vector_cast}({vector_dimension})) AS vector_similarity
                           FROM knowledge_chunks c
                           JOIN knowledge_sources s ON c.source_id = s.id
                           WHERE c.embedding IS NOT NULL
                   """
                   
                   params = [query_embedding]
                   param_index = 2
                   
                   # フィルタの適用（ベクトル検索用）
                   if filters:
                       invalid_keys = set(filters.keys()) - ALLOWED_FILTER_KEYS
                       if invalid_keys:
                           raise ValueError(
                               f"Invalid filter keys: {invalid_keys}. "
                               f"Allowed keys: {ALLOWED_FILTER_KEYS}"
                           )
                       
                       if "source_type" in filters:
                           source_type = filters["source_type"]
                           if source_type not in VALID_SOURCE_TYPES:
                               raise ValueError(f"Invalid source_type: {source_type}.")
                           query += f" AND s.type = ${param_index}"
                           params.append(source_type)
                           param_index += 1
                       
                       if "source_types" in filters:
                           source_types = filters["source_types"]
                           if not isinstance(source_types, list):
                               raise ValueError("source_types must be a list")
                           if len(source_types) == 0:
                               raise ValueError("source_types must not be empty")
                           invalid_types = set(source_types) - VALID_SOURCE_TYPES
                           if invalid_types:
                               raise ValueError(f"Invalid source_types: {invalid_types}.")
                           query += f" AND s.type = ANY(${param_index}::source_type_enum[])"
                           params.append(source_types)
                           param_index += 1
                       
                       if "channel_id" in filters:
                           try:
                               channel_id = int(filters["channel_id"])
                           except (ValueError, TypeError) as err:
                               raise ValueError("Invalid channel_id: must be an integer.") from err
                           query += f" AND (s.metadata->>'channel_id')::bigint = ${param_index}"
                           params.append(channel_id)
                           param_index += 1
                       
                       if "user_id" in filters:
                           try:
                               user_id = int(filters["user_id"])
                           except (ValueError, TypeError) as err:
                               raise ValueError("Invalid user_id: must be an integer.") from err
                           query += f" AND (s.metadata->>'author_id')::bigint = ${param_index}"
                           params.append(user_id)
                           param_index += 1
                   
                   query += f"""
                           ORDER BY c.embedding <=> $1::{vector_cast}({vector_dimension})
                           LIMIT 50
                       ),
                       keyword_results AS (
                           SELECT 
                               s.id as source_id,
                               s.type,
                               s.title,
                               s.uri,
                               s.metadata as source_metadata,
                               c.id as chunk_id,
                               c.content,
                               c.location,
                               c.token_count,
                               1.0 AS keyword_score
                           FROM knowledge_chunks c
                           JOIN knowledge_sources s ON c.source_id = s.id
                           WHERE c.content LIKE ${param_index}
                             AND c.embedding IS NOT NULL
                   """
                   
                   params.append(keyword_pattern)
                   param_index += 1
                   
                   # フィルタの適用（キーワード検索用）
                   if filters:
                       if "source_type" in filters:
                           query += f" AND s.type = ${param_index}"
                           params.append(filters["source_type"])
                           param_index += 1
                       if "source_types" in filters:
                           query += f" AND s.type = ANY(${param_index}::source_type_enum[])"
                           params.append(filters["source_types"])
                           param_index += 1
                       if "channel_id" in filters:
                           query += f" AND (s.metadata->>'channel_id')::bigint = ${param_index}"
                           params.append(int(filters["channel_id"]))
                           param_index += 1
                       if "user_id" in filters:
                           query += f" AND (s.metadata->>'author_id')::bigint = ${param_index}"
                           params.append(int(filters["user_id"]))
                           param_index += 1
                   
                   query += f"""
                           LIMIT 100
                       ),
                       combined AS (
                           SELECT 
                               source_id, type, title, uri, source_metadata,
                               chunk_id, content, location, token_count,
                               vector_similarity * {vector_weight} AS score
                           FROM vector_results
                           UNION ALL
                           SELECT 
                               source_id, type, title, uri, source_metadata,
                               chunk_id, content, location, token_count,
                               keyword_score * {keyword_weight} AS score
                           FROM keyword_results
                       )
                       SELECT 
                           source_id, type, title, uri, source_metadata,
                           chunk_id, content, location, token_count,
                           SUM(score) AS combined_score
                       FROM combined
                       GROUP BY source_id, type, title, uri, source_metadata,
                                chunk_id, content, location, token_count
                       ORDER BY combined_score DESC
                       LIMIT ${param_index}
                   """
                   
                   params.append(limit)
                   
                   rows = await conn.fetch(query, *params)
       except TimeoutError:
           logger.error("Failed to acquire database connection: pool exhausted")
           raise RuntimeError("Database connection pool exhausted") from None
       except asyncpg.PostgresConnectionError as e:
           logger.error(f"Database connection failed: {e}")
           raise RuntimeError(f"Database connection failed: {e}") from e
       except Exception as e:
           logger.error(f"Error during hybrid search: {e}", exc_info=True)
           raise
       
       return [
           SearchResult(
               {
                   "source_id": row["source_id"],
                   "source_type": row["type"],
                   "title": row["title"],
                   "uri": row["uri"],
                   "source_metadata": row["source_metadata"] or {},
                   "chunk_id": row["chunk_id"],
                   "content": row["content"],
                   "location": row["location"] or {},
                   "token_count": row["token_count"],
                   "similarity": float(row["combined_score"]),
               }
           )
           for row in rows
       ]
   ```

3. `KnowledgeBaseProtocol`に`hybrid_search`メソッドのシグネチャを追加する（必要に応じて）

   `src/kotonoha_bot/db/base.py`を確認し、`KnowledgeBaseProtocol`に`hybrid_search`メソッドが定義されていない場合は追加する。

**メソッドシグネチャ**:

```python
async def hybrid_search(
    self,
    query_embedding: list[float],
    query_text: str,
    limit: int = 10,
    vector_weight: float = 0.7,
    keyword_weight: float = 0.3,
    filters: dict | None = None,
) -> list[SearchResult]:
    """ハイブリッド検索（ベクトル検索 + キーワード検索）
    
    Args:
        query_embedding: クエリのベクトル（1536次元）
        query_text: クエリのテキスト（キーワード検索用）
        limit: 返却する結果の数（デフォルト: 10）
        vector_weight: ベクトル類似度の重み（デフォルト: 0.7）
        keyword_weight: キーワードスコアの重み（デフォルト: 0.3）
        filters: フィルタ条件（source_type, channel_id, user_id等）
    
    Returns:
        検索結果のリスト（スコア順）
    """
```

**実装ロジック**:

1. ベクトル検索で上位50件を取得（`similarity_search`メソッドのロジックを参考に実装）
2. キーワード検索で上位100件を取得（`LIKE '%キーワード%'`で検索、pg_bigmインデックスが使用される）
3. 両方の結果をUNION ALLで結合
4. スコアを合計して降順にソート
5. 上位`limit`件を返す

**注意点**:

- `embedding IS NOT NULL`条件を必ず付与（HNSWインデックス使用のため）
- キーワード検索にも上限を設ける（巨大なテーブルでのボトルネックを防ぐ）
- SQLインジェクション対策（Allow-list方式）を維持
- `query_text`は内部からの呼び出しのみを想定（外部入力の場合は事前にサニタイズが必要）
- 重みの合計が1.0になることを確認する

#### Step 4: テストの実装

**完了内容**:

- ハイブリッド検索のユニットテスト
- 統合テストの実装
- パフォーマンステストの実施

**実装手順**:

1. **ユニットテストの作成**

   `tests/unit/db/test_postgres_hybrid_search.py`を作成する

   ```python
   """PostgreSQL ハイブリッド検索のユニットテスト."""
   
   import pytest
   from kotonoha_bot.db.postgres import PostgreSQLDatabase
   
   @pytest.mark.asyncio
   async def test_hybrid_search_basic():
       """ハイブリッド検索の基本動作をテスト."""
       # テスト実装
       pass
   
   @pytest.mark.asyncio
   async def test_hybrid_search_scoring():
       """スコアリングが正しく計算されることをテスト."""
       # テスト実装
       pass
   
   @pytest.mark.asyncio
   async def test_hybrid_search_filters():
       """フィルタリングが正しく動作することをテスト."""
       # テスト実装
       pass
   ```

2. **統合テストの作成**

   `tests/integration/test_hybrid_search.py`を作成する

   ```python
   """ハイブリッド検索の統合テスト."""
   
   import pytest
   from kotonoha_bot.db.postgres import PostgreSQLDatabase
   
   @pytest.mark.asyncio
   async def test_hybrid_search_integration():
       """ハイブリッド検索の統合テスト."""
       # テスト実装
       pass
   ```

3. **パフォーマンステストの作成（オプション）**

   `tests/performance/test_hybrid_search_performance.py`を作成する

   ```python
   """ハイブリッド検索のパフォーマンステスト."""
   
   import pytest
   import time
   from kotonoha_bot.db.postgres import PostgreSQLDatabase
   
   @pytest.mark.asyncio
   async def test_hybrid_search_performance():
       """大量データでの検索性能をテスト."""
       # テスト実装
       pass
   ```

**実装ファイル**:

- `tests/unit/db/test_postgres_hybrid_search.py`: ハイブリッド検索のユニットテスト
- `tests/integration/test_hybrid_search.py`: ハイブリッド検索の統合テスト
- `tests/performance/test_hybrid_search_performance.py`: パフォーマンステスト（オプション）

**テスト項目**:

1. **基本機能テスト**:
   - ベクトル検索のみの結果が正しく返されること
   - キーワード検索のみの結果が正しく返されること
   - ハイブリッド検索の結果が正しく返されること
   - スコアリングが正しく計算されること
   - 重みの合計が1.0でない場合にエラーが発生すること

2. **フィルタリングテスト**:
   - `source_type`フィルタが正しく動作すること
   - `channel_id`フィルタが正しく動作すること
   - `user_id`フィルタが正しく動作すること
   - 複数のフィルタを組み合わせた場合に正しく動作すること

3. **エラーハンドリングテスト**:
   - 無効なフィルタキーが指定された場合にエラーが発生すること
   - 無効な`source_type`が指定された場合にエラーが発生すること
   - 接続プールが枯渇した場合に適切なエラーが発生すること

4. **パフォーマンステスト**（オプション）:
   - 大量データ（10万件以上）での検索性能
   - インデックスが正しく使用されていること（EXPLAIN ANALYZE）
   - 検索クエリが1秒以内に完了すること

---

## 5. 完了基準

### 5.1 実装完了基準

- ✅ `Dockerfile.postgres`が作成されている
- ✅ pg_bigm拡張が有効化されている（Alembicマイグレーション）
- ✅ GINインデックス（pg_bigm）が作成されている
- ✅ `hybrid_search`メソッドが実装されている
- ✅ ベクトル検索とキーワード検索が正しく組み合わせられている
- ✅ スコアリングが正しく計算されている
- ✅ フィルタリング機能が正しく動作している
- ✅ テストが実装されている
- ✅ テストが通過する

### 5.2 品質基準

- **パフォーマンス**: 検索クエリが1秒以内に完了すること（10万件のデータで）
- **精度**: 固有名詞を含む検索の精度が向上していること
- **互換性**: 既存の`similarity_search`メソッドが正常に動作すること

---

## 6. テスト計画

### 6.1 ユニットテスト

**テストファイル**: `tests/unit/test_postgres_hybrid_search.py`

**テスト項目**:

1. `hybrid_search`メソッドの基本動作
2. スコアリングの計算ロジック
3. フィルタリング機能
4. エラーハンドリング

### 6.2 統合テスト

**テストファイル**: `tests/integration/test_hybrid_search.py`

**テスト項目**:

1. ベクトル検索とキーワード検索の組み合わせ
2. 大量データでの検索性能
3. インデックスの使用確認（EXPLAIN ANALYZE）

### 6.3 パフォーマンステスト

**テストファイル**: `tests/performance/test_hybrid_search_performance.py`

**テスト項目**:

1. 検索クエリの実行時間測定
2. インデックスサイズの確認
3. メモリ使用量の確認

### 6.4 テスト実行方法

```bash
# 全テスト実行
pytest tests/ -v

# ハイブリッド検索のテストのみ実行
pytest tests/unit/test_postgres_hybrid_search.py -v
pytest tests/integration/test_hybrid_search.py -v

# パフォーマンステスト
pytest tests/performance/test_hybrid_search_performance.py -v

# カバレッジ付きテスト実行
pytest tests/ -v --cov=src/kotonoha_bot --cov-report=term-missing
```

---

## 7. 導入・デプロイ手順

### 7.1 開発環境での導入

**前提条件**:

- Phase 8（PostgreSQL + pgvector 実装）が完了していること
- `docker`と`docker compose`がインストールされていること
- プロジェクトの依存関係がインストールされていること

**導入手順**:

1. **Dockerfile.postgresの作成**

   [Step 1](#step-1-dockerfilepostgresの作成)の手順に従って`Dockerfile.postgres`を作成する。

2. **docker-compose.ymlの確認**

   `docker-compose.yml`を開き、`postgres`サービスの設定を確認する。
   開発環境では標準のpgvectorイメージを使用する（ビルド時間の短縮のため）。

   ```yaml
   services:
     postgres:
       # 開発環境では標準イメージを使用（ビルド時間の短縮）
       image: pgvector/pgvector:0.8.1-pg18
       # 本番環境ではカスタムイメージを使用
       # build:
       #   context: .
       #   dockerfile: Dockerfile.postgres
   ```

   **注意**: 開発環境では`pg_bigm`拡張が利用できないため、ハイブリッド検索は動作しない。
   開発環境でハイブリッド検索をテストする場合は、カスタムイメージをビルドする必要がある。

3. **Alembicマイグレーションファイルの作成**

   [Step 2](#step-2-pg_bigm拡張の有効化alembicマイグレーション)の手順に従ってマイグレーションファイルを作成する。

   ```bash
   # プロジェクトルートで実行
   alembic revision -m "add_pg_bigm_extension"
   ```

   作成されたマイグレーションファイルを編集し、pg_bigm拡張の有効化とインデックスの作成を追加する。

4. **Alembicマイグレーションの適用**

   ```bash
   # Bot起動時に自動適用されます
   # または手動で実行:
   alembic upgrade head
   ```

   **注意**: 開発環境で標準のpgvectorイメージを使用している場合、`pg_bigm`拡張の有効化は失敗するが、
   これは想定された動作である（警告メッセージが表示される）。

5. **hybrid_searchメソッドの実装**

   [Step 3](#step-3-ハイブリッド検索メソッドの実装)の手順に従って`hybrid_search`メソッドを実装する。

6. **テストの実装**

   [Step 4](#step-4-テストの実装)の手順に従ってテストを実装する。

7. **Botの起動と動作確認**

   ```bash
   # Botの起動
   docker compose up kotonoha-bot
   
   # ログを確認し、pg_bigm拡張の有効化が試みられていることを確認
   # （開発環境では警告が表示されるが、これは正常）
   ```

8. **動作確認**

   - 既存の`similarity_search`メソッドが正常に動作することを確認
   - `hybrid_search`メソッドが正常に動作することを確認（本番環境またはカスタムイメージ使用時）
   - テストが通過することを確認

   ```bash
   # テストの実行
   pytest tests/ -v
   
   # ハイブリッド検索のテストのみ実行
   pytest tests/unit/db/test_postgres_hybrid_search.py -v
   pytest tests/integration/test_hybrid_search.py -v
   ```

### 7.2 本番環境でのデプロイ

**前提条件**:

- 開発環境での導入が完了していること
- 本番環境のデータベースにバックアップが取得されていること
- メンテナンスウィンドウが確保されていること

**デプロイ手順**:

1. **カスタムイメージのビルド**

   ```bash
   # プロジェクトルートで実行
   # ビルドには10-20分程度かかる場合がある
   docker build -f Dockerfile.postgres -t kotonoha-postgres:latest .
   
   # ビルドが成功したことを確認
   docker images | grep kotonoha-postgres
   ```

   **注意**: ビルド時間を短縮するため、CI/CDパイプラインでビルドしてレジストリにプッシュすることを推奨する。

2. **docker-compose.ymlの更新**

   `docker-compose.yml`を開き、`postgres`サービスの設定を更新する。

   ```yaml
   services:
     postgres:
       # 本番環境ではカスタムイメージを使用
       image: kotonoha-postgres:latest
       # または build: を使用（毎回ビルドする場合）
       # build:
       #   context: .
       #   dockerfile: Dockerfile.postgres
   ```

   **推奨**: レジストリにプッシュしたイメージを使用する場合

   ```yaml
   services:
     postgres:
       image: ghcr.io/${GITHUB_REPOSITORY}/kotonoha-postgres:latest
       # または
       # image: your-registry.com/kotonoha-postgres:latest
   ```

3. **データベースのメンテナンス**

   - **メンテナンスウィンドウを設ける**: インデックス作成に時間がかかる可能性がある（データ量に応じて数分〜数十分）
   - **バックアップを取得**: デプロイ前に必ずデータベースのバックアップを取得する

   ```bash
   # バックアップの取得例
   docker compose exec postgres pg_dump -U kotonoha kotonoha > backup_$(date +%Y%m%d_%H%M%S).sql
   ```

4. **PostgreSQLコンテナの再起動**

   ```bash
   # 既存のコンテナを停止
   docker compose stop postgres
   
   # コンテナを削除（データはボリュームに保存されているため安全）
   docker compose rm -f postgres
   
   # 新しいイメージでコンテナを起動
   docker compose up -d postgres
   
   # コンテナのログを確認し、正常に起動したことを確認
   docker compose logs postgres
   ```

5. **Alembicマイグレーションの適用**

   ```bash
   # Botコンテナから実行する場合
   docker compose exec kotonoha-bot alembic upgrade head
   
   # または、Bot起動時に自動適用される（推奨）
   ```

   **注意**: インデックス作成には時間がかかる場合がある。ログを確認し、完了を待つ。

6. **動作確認**

   - **pg_bigm拡張の有効化を確認**

     ```bash
     # PostgreSQLコンテナに接続
     docker compose exec postgres psql -U kotonoha -d kotonoha
     
     # 拡張機能の確認
     \dx pg_bigm
     
     # インデックスの確認
     \d+ knowledge_chunks
     ```

   - **ハイブリッド検索の動作確認**

     ```bash
     # Botコンテナのログを確認
     docker compose logs kotonoha-bot | grep -i "hybrid"
     
     # または、Botのヘルスチェックエンドポイントにアクセス
     curl http://localhost:8081/health
     ```

   - **既存機能の動作確認**

     - 既存のベクトル検索（`similarity_search`）が正常に動作することを確認
     - ハイブリッド検索（`hybrid_search`）が正常に動作することを確認

7. **ロールバック手順（問題が発生した場合）**

   ```bash
   # マイグレーションのロールバック
   docker compose exec kotonoha-bot alembic downgrade -1
   
   # または、バックアップから復元
   docker compose exec -T postgres psql -U kotonoha kotonoha < backup_YYYYMMDD_HHMMSS.sql
   ```

**トラブルシューティング**:

- **pg_bigm拡張が有効化されない場合**:
  - カスタムイメージが正しくビルドされているか確認
  - PostgreSQLコンテナのログを確認
  - 手動で拡張機能を有効化してみる: `CREATE EXTENSION IF NOT EXISTS pg_bigm;`

- **インデックス作成に時間がかかる場合**:
  - データ量が多い場合は、バックグラウンドで作成される
  - `CREATE INDEX CONCURRENTLY`を使用する場合は、マイグレーションファイルを修正する必要がある

- **ハイブリッド検索が動作しない場合**:
  - `hybrid_search`メソッドが正しく実装されているか確認
  - テストを実行し、エラーを確認
  - ログを確認し、エラーメッセージを特定

### 7.3 詳細な動作確認手順

**基本的な動作確認**:

1. **pg_bigm拡張の有効化確認**

   ```bash
   # PostgreSQLコンテナに接続
   docker compose exec postgres psql -U kotonoha -d kotonoha
   
   # 拡張機能の一覧を確認
   \dx
   
   # pg_bigm拡張が表示されることを確認
   # 出力例:
   #   Name    | Version | Schema | Description
   #   --------+---------+--------+-------------
   #   pg_bigm | 1.2     | public | ...
   #   vector  | 0.8.1   | public | ...
   ```

2. **インデックスの確認**

   ```sql
   -- PostgreSQLコンテナ内で実行
   \d+ knowledge_chunks
   
   -- インデックスの一覧を確認
   SELECT 
       indexname, 
       indexdef 
   FROM pg_indexes 
   WHERE tablename = 'knowledge_chunks';
   
   -- idx_chunks_content_bigm が表示されることを確認
   ```

3. **ハイブリッド検索の動作確認（Pythonコード）**

   ```python
   # Pythonインタラクティブシェルまたはテストコードで実行
   from kotonoha_bot.db.postgres import PostgreSQLDatabase
   from kotonoha_bot.external.embedding.openai_embedding import OpenAIEmbeddingProvider
   import asyncio
   
   async def test_hybrid_search():
       # データベースの初期化
       db = PostgreSQLDatabase(
           host="localhost",
           port=5432,
           database="kotonoha",
           user="kotonoha",
           password="password"
       )
       await db.initialize()
       
       # Embeddingプロバイダーの初期化
       embedding_provider = OpenAIEmbeddingProvider()
       
       # クエリテキストとベクトルを準備
       query_text = "検索キーワード"
       query_embedding = await embedding_provider.embed_query(query_text)
       
       # ハイブリッド検索を実行
       results = await db.hybrid_search(
           query_embedding=query_embedding,
           query_text=query_text,
           limit=10
       )
       
       # 結果を確認
       print(f"検索結果数: {len(results)}")
       for result in results:
           print(f"スコア: {result.similarity:.4f}, コンテンツ: {result.content[:50]}...")
       
       await db.close()
   
   # 実行
   asyncio.run(test_hybrid_search())
   ```

4. **パフォーマンス確認（EXPLAIN ANALYZE）**

   ```sql
   -- PostgreSQLコンテナ内で実行
   EXPLAIN ANALYZE
   SELECT 
       id, source_id, content
   FROM knowledge_chunks
   WHERE content LIKE '%検索キーワード%'
     AND embedding IS NOT NULL
   LIMIT 100;
   
   -- 実行計画を確認し、以下が表示されることを確認:
   -- - Index Scan using idx_chunks_content_bigm on knowledge_chunks
   -- - Index Scan using idx_chunks_embedding on knowledge_chunks
   ```

5. **既存機能との互換性確認**

   ```python
   # similarity_searchメソッドが正常に動作することを確認
   results = await db.similarity_search(
       query_embedding=query_embedding,
       top_k=10
   )
   assert len(results) > 0, "similarity_search should return results"
   ```

### 7.4 追加のトラブルシューティング

**よくある問題と解決方法**:

1. **スコアリングが正しく計算されない**

   **症状**: ハイブリッド検索の結果のスコアが期待と異なる

   **原因**:
   - 重みの合計が1.0でない
   - スコアリングロジックに誤りがある

   **解決方法**:
   - `vector_weight`と`keyword_weight`の合計が1.0になることを確認
   - テストを実行し、スコアリングロジックを確認
   - デバッグログを有効化し、スコアの計算過程を確認

2. **パフォーマンスが悪い**

   **症状**: ハイブリッド検索の実行時間が長い

   **原因**:
   - インデックスが使用されていない
   - データ量が多い
   - フィルタ条件が適切でない

   **解決方法**:
   - `EXPLAIN ANALYZE`を実行し、インデックスが使用されているか確認
   - インデックスが使用されていない場合は、クエリを最適化
   - 必要に応じて追加のインデックスを作成
   - `limit`パラメータを調整し、取得件数を制限

3. **テストが失敗する**

   **症状**: ハイブリッド検索のテストが失敗する

   **原因**:
   - テストデータが不足している
   - テスト環境でpg_bigm拡張が有効化されていない
   - テストコードに誤りがある

   **解決方法**:
   - テストデータを準備し、十分なデータがあることを確認
   - テスト環境でpg_bigm拡張が有効化されているか確認
   - テストコードを確認し、エラーメッセージを特定
   - モックを使用してテストを簡素化

---

## 8. 今後の改善計画

### 8.1 Phase 12: Rerankingの実装（オプション）

**目的**: Cross-Encoder（Reranker）を使用して検索精度を向上させる

**実装方法**: ベクトル検索の結果を再ランキング

**注意点**: CPU負荷を考慮

### 8.2 スコアリングの最適化

**目的**: ベクトル類似度とキーワードスコアの重みを動的に調整

**実装方法**: クエリの種類に応じて重みを変更

### 8.3 多言語対応

**目的**: 英語やその他の言語での検索精度向上

**実装方法**: 言語ごとに最適な検索方法を選択

---

## 参考資料

- **スキーマ設計書**: [PostgreSQL スキーマ設計書](../../40_design_detailed/42_db-schema-physical/postgresql-schema-overview.md)
- **実装ガイド**: [PostgreSQL実装ガイド](../../50_implementation/51_guides/postgresql-implementation-guide.md)
- **クエリガイド**: [PostgreSQLクエリガイド](../../50_implementation/51_guides/postgresql-query-guide.md)
- **Phase 8実装計画**: [Phase 8実装計画](./phase08.md)

---

**作成日**: 2026年1月19日  
**最終更新日**: 2026年1月19日  
**バージョン**: 1.1  
**作成者**: kotonoha-bot 開発チーム

**更新履歴**:
- v1.1 (2026年1月19日): 導入手順の詳細化、実装手順の追加、動作確認手順の追加、トラブルシューティング情報の追加
- v1.0 (2026年1月19日): 初版作成
