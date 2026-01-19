# PostgreSQL 実装ガイド

**作成日**: 2026年1月19日  
**バージョン**: 1.22  
**対象プロジェクト**: kotonoha-bot v0.8.0

## 関連ドキュメント

- [スキーマ概要](../../40_design_detailed/42_db-schema-physical/postgresql-schema-overview.md)
- [テーブル定義](../../40_design_detailed/42_db-schema-physical/postgresql-schema-tables.md)
- [インデックス設計](../../40_design_detailed/42_db-schema-physical/postgresql-schema-indexes.md)
- [クエリガイド](./postgresql-query-guide.md)

---

## パフォーマンス考慮事項

### 9.1 インデックス戦略

1. **HNSWインデックス**: ベクトル検索の高速化（`idx_chunks_embedding`）
2. **GINインデックス**:
   - JSONBメタデータの高速検索（`idx_sources_metadata`）
   - ハイブリッド検索用のpg_bigmインデックス（`idx_chunks_content_bigm`、推奨）
3. **B-treeインデックス**: 通常のカラム検索（`status`, `type`, `source_id`など）

### 9.2 クエリ最適化

1. **LIMIT句の使用**: 大量データ取得時は必ずLIMITを指定
2. **部分インデックス**: `embedding IS NOT NULL` 条件での検索を高速化
3. **JOIN最適化**: `knowledge_chunks` と `knowledge_sources` のJOINは外部キーインデックスで高速化

### 9.3 接続プール設定

**推奨設定**（環境変数）:

- `DB_POOL_MIN_SIZE`: 5（最小接続数）
- `DB_POOL_MAX_SIZE`: 20（最大接続数）
- `DB_COMMAND_TIMEOUT`: 60（コマンドタイムアウト秒）

### 9.4 メモリ使用量の最適化

1. **halfvecの使用**: `vector(1536)` の代わりに `halfvec(1536)` を使用（メモリ使用量50%削減）
2. **HNSWパラメータ調整**: `m` と `ef_construction` を環境に応じて調整
3. **定期的なVACUUM**: 不要なデータ削除後のVACUUM実行

### 9.5 並行性制御とロック戦略

#### FOR UPDATE SKIP LOCKED パターン

複数のワーカープロセスが同時に実行される場合、
DBレベルでの排他制御が必須です。
`FOR UPDATE SKIP LOCKED` を使用することで、
アプリケーションレベルのロック（`asyncio.Lock`）に依存せず、
安全にバッチ処理が可能になります。

**問題点（アプリケーションレベルのロック）**:

- 単一のBotプロセスでしか機能しない
- Bot再起動や誤った2重起動時に競合が発生
- スケールアウト時に同じチャンクを同時処理してしまう

**解決策（DBレベルのロック）**:

```sql
-- トランザクション内で実行
BEGIN;

-- 取得と同時にロック（他のワーカーはこの行をスキップ）
SELECT id, source_id, content, token_count
FROM knowledge_chunks
WHERE embedding IS NULL
ORDER BY id ASC
LIMIT 100
FOR UPDATE SKIP LOCKED;

-- Embedding処理後、更新
UPDATE knowledge_chunks
SET embedding = $1::halfvec(1536),
    token_count = $2
WHERE id = $3;

COMMIT;
```

**メリット**:

- **DBレベルでの排他制御**: アプリケーションレベルのロック不要
- **スケールアウト対応**: 複数のBotプロセスやワーカーが同時実行可能
- **再起動時の安全性**: Bot再起動や誤った2重起動時も競合が発生しない
- **パフォーマンス**: ロックされた行は自動的にスキップされ、待機しない

**実装例（Python/asyncpg）**:

```python
async def process_embedding_batch(
    conn: asyncpg.Connection, batch_size: int = 100
):
    """並行処理安全なEmbeddingバッチ処理"""
    async with conn.transaction():
        # FOR UPDATE SKIP LOCKED で取得
        rows = await conn.fetch("""
            SELECT id, source_id, content, token_count
            FROM knowledge_chunks
            WHERE embedding IS NULL
            ORDER BY id ASC
            LIMIT $1
            FOR UPDATE SKIP LOCKED
        """, batch_size)
        
        for row in rows:
            # Embedding処理
            embedding = await generate_embedding(row['content'])
            
            # 更新
            await conn.execute("""
                UPDATE knowledge_chunks
                SET embedding = $1::halfvec(1536),
                    token_count = $2
                WHERE id = $3
            """, embedding, row['token_count'], row['id'])
```

---

## 10. 将来の拡張性

### 10.1 ソースタイプの追加

新しいソースタイプを追加する場合：

```sql
ALTER TYPE source_type_enum ADD VALUE 'video_transcript';
ALTER TYPE source_type_enum ADD VALUE 'code_repository';
```

**注意**: ENUM値の追加は可能ですが、削除は困難です。慎重に設計してください。

### 10.2 テーブルの追加

将来的に以下のテーブル追加を検討：

- **`knowledge_tags`**: タグ管理（マルチタグ対応）
- **`knowledge_relations`**: ソース間の関連性管理
- **`user_preferences`**: ユーザーごとの検索設定

### 10.3 パーティショニング

大規模データに対応するため、時系列パーティショニングを検討：

```sql
-- 月ごとのパーティショニング例
CREATE TABLE knowledge_chunks_2026_01 PARTITION OF knowledge_chunks
FOR VALUES FROM ('2026-01-01') TO ('2026-02-01');
```

### 10.4 ハイブリッド検索（Hybrid Search）の導入

**背景**: ベクトル検索は「概念的な類似」には強いですが、
「固有名詞（例：プロジェクトコード名、特定のエラーコード）」の
完全一致検索には弱いです。
PostgreSQLの強みを生かし、全文検索を組み合わせたハイブリッド検索を
設計段階で考慮することを推奨します。

⚠️ **重要**: 日本語検索においては、**pg_bigm** を強く推奨します。

#### 推奨: pg_bigm 拡張を使用（日本語検索に最適）

**pg_bigm の利点**:

- **2-gram（2文字単位）**: 日本語の多くは2文字以上の熟語で構成されるため、検索漏れがほぼゼロ
- **2文字の単語に対応**: 「設計」「開発」のような2文字の単語も確実に検索可能
- **LIKE演算子の高速化**: PostgreSQL標準の `LIKE '%...%'` 検索を爆速化
- **pg_trgm との違い**: pg_trgm（3-gram）は2文字の単語が検索漏れしたり、精度が出にくい場合がある

**pg_trgm の限界**:

- 3文字単位のため、「設計」「開発」のような2文字の単語の検索が苦手
- ひらがなの助詞などがノイズになりやすい

**Dockerfile での pg_bigm の導入**:

pg_bigm は標準の PostgreSQL イメージには含まれていないため、
pgvector のイメージをベースにして、pg_bigm をコンパイルして追加した
カスタムイメージを作成する必要があります。

```dockerfile
# Dockerfile.postgres

# pgvector の公式イメージ（PostgreSQL 18）をベースに使用
FROM pgvector/pgvector:0.8.1-pg18

# pg_bigm のバージョン
# ⚠️ 注意: GitHubリリースへの依存があり、削除リスクがあります
# 推奨: ソースを自プロジェクトに含めるか、チェックサム検証を追加
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

# pg_bigm のダウンロードとインストール
# ⚠️ ビルドキャッシュ最適化: マルチステージビルドとレイヤーキャッシュを活用
# Stage 1: ビルド環境
FROM pgvector/pgvector:0.8.1-pg18 AS builder

ARG PG_BIGM_VERSION=1.2-20240606
ARG PG_BIGM_CHECKSUM=""

USER root

# ビルド依存関係のインストール（レイヤーキャッシュのため、依存関係の変更が少ない順に配置）
RUN apt-get update && apt-get install -y \
    build-essential \
    postgresql-server-dev-18 \
    wget \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# pg_bigm のダウンロード（ダウンロードとビルドを分離して
# レイヤーキャッシュを活用）
RUN wget -O pg_bigm.tar.gz \
    https://github.com/pgbigm/pg_bigm/archive/refs/tags/\
v${PG_BIGM_VERSION}.tar.gz \
    && if [ -n "$PG_BIGM_CHECKSUM" ]; then \
        echo "$PG_BIGM_CHECKSUM  pg_bigm.tar.gz" | sha256sum -c - || exit 1; \
    fi \
    && mkdir -p /usr/src/pg_bigm \
    && tar -xzf pg_bigm.tar.gz -C /usr/src/pg_bigm --strip-components=1

# pg_bigm のビルド（ソースコードの変更がない限り、このレイヤーはキャッシュされる）
WORKDIR /usr/src/pg_bigm
RUN make USE_PGXS=1 && make USE_PGXS=1 install

# Stage 2: 実行環境（ビルド済みのpg_bigmのみを含む軽量イメージ）
FROM pgvector/pgvector:0.8.1-pg18

USER root

# ビルド済みのpg_bigmをコピー（ビルド依存関係は含めない）
COPY --from=builder \
  /usr/share/postgresql/18/extension/pg_bigm* \
  /usr/share/postgresql/18/extension/
COPY --from=builder \
  /usr/lib/postgresql/18/lib/pg_bigm.so \
  /usr/lib/postgresql/18/lib/

USER postgres

# ⚠️ ビルドキャッシュ最適化のメリット:
# - ビルド依存関係のインストールレイヤーは、依存関係が変更されない限りキャッシュされる
# - pg_bigmのソースコードが変更されない限り、ビルドレイヤーもキャッシュされる
# - 実行環境は軽量で、ビルド依存関係を含まないため、イメージサイズが小さい
# - マルチステージビルドにより、ビルド依存関係を実行環境に含めない
```

**docker-compose.yml の修正**:

```yaml
services:
  postgres:
    # ⚠️ 改善（開発効率）: 開発環境では標準の pgvector イメージを使用
    # pg_bigm のビルドは時間がかかるため、開発中に docker-compose up --build を
    # 頻繁に行うと開発効率が落ちます。
    # 開発環境では ENABLE_HYBRID_SEARCH=false に設定し、標準イメージを使用
    # 本番環境ではカスタムイメージをビルドして使用
    # 
    # 開発環境（ENABLE_HYBRID_SEARCH=false）:
    image: pgvector/pgvector:0.8.1-pg18
    # 
    # 本番環境（ENABLE_HYBRID_SEARCH=true）:
    # build:
    #   context: .
    #   dockerfile: Dockerfile.postgres
    container_name: kotonoha-postgres
    # ... (その他の設定はそのまま)
```

**拡張機能の有効化とインデックス作成**:

```sql
-- pg_bigm 拡張の有効化
CREATE EXTENSION IF NOT EXISTS pg_bigm;

-- knowledge_chunks.content にGINインデックス（pg_bigm）を追加
CREATE INDEX idx_chunks_content_bigm ON knowledge_chunks 
USING gin (content gin_bigm_ops);
```

**使用例（ハイブリッド検索）**:

pg_bigm の最大の特徴は、PostgreSQL標準の `LIKE` 演算子を使用した中間一致検索が高速になることです。

**推奨実装（UNION ALL方式）**:

FULL OUTER JOINは両方のCTEを完全評価するため非効率です。UNION ALLを使用した方が効率的です。

```sql
-- ベクトル検索とキーワード検索のスコアを組み合わせ（UNION ALL方式）
WITH vector_results AS (
    SELECT 
        id,
        source_id,
        content,
        1 - (embedding <=> $1::halfvec(1536)) AS vector_similarity
    FROM knowledge_chunks
    WHERE embedding IS NOT NULL
    ORDER BY embedding <=> $1::halfvec(1536)
    LIMIT 50  -- 候補を広めに取る
),
keyword_results AS (
    SELECT 
        id,
        source_id,
        content,
        1.0 AS keyword_score  -- ヒットしたらスコア1.0（重み付けで調整）
    FROM knowledge_chunks
    WHERE content LIKE $2  -- pg_bigm インデックスが使用される（$2 は '%検索キーワード%'）
      AND embedding IS NOT NULL  -- ⚠️ 必須: HNSWインデックス使用のため
    LIMIT 100  -- ⚠️ 改善（クエリ効率）: キーワード検索にも上限を設ける（巨大なテーブルでのボトルネックを防ぐ）
),
combined AS (
    SELECT id, source_id, content, vector_similarity * 0.7 AS score 
    FROM vector_results
    UNION ALL
    SELECT id, source_id, content, keyword_score * 0.3 AS score 
    FROM keyword_results
)
SELECT 
    id,
    source_id,
    content,
    SUM(score) AS combined_score
FROM combined
GROUP BY id, source_id, content
ORDER BY combined_score DESC
LIMIT 10;
```

**注意**: FULL OUTER JOIN方式も動作しますが、パフォーマンスが劣るため、UNION ALL方式を推奨します。

**注意点とデメリット**:

1. **インデックスサイズ**: pg_bigm のインデックスは pg_trgm よりも
   大きくなる傾向があります
   （2文字の組み合わせの方が3文字よりも多いため）
   - **対策**: NASのストレージ容量には注意してください。
     ただしテキストデータのみのインデックスなので、
     ベクトルデータ（HNSW）に比べればそこまで巨大にはなりません。

2. **更新速度**: インデックス作成・更新にかかるCPU負荷が若干高いです。
   - **対策**: Botの知識化処理はバックグラウンドで行われるため、ユーザー体験への影響は軽微です。

3. **1文字検索**: pg_bigm は「2文字」のインデックスですが、1文字の検索も可能です（全件スキャンよりはマシですが、少し遅くなります）。
   - **実用上の問題**: 日本語検索において1文字検索（例：「あ」だけ検索）の需要は低いため、実用上は問題ありません。

#### オプション2: tsvector を使用（FTS）

**メリット**: PostgreSQL標準の全文検索機能。言語固有の解析が可能。

```sql
-- 全文検索用カラムの追加
ALTER TABLE knowledge_chunks 
ADD COLUMN content_tsvector tsvector 
GENERATED ALWAYS AS (to_tsvector('japanese', content)) STORED;

-- GINインデックスの作成
CREATE INDEX idx_chunks_content_fts
  ON knowledge_chunks USING gin (content_tsvector);
```

**使用例**:

```sql
-- ベクトル検索と全文検索のハイブリッド
SELECT 
    id,
    source_id,
    content,
    1 - (embedding <=> $1::halfvec(1536)) AS vector_similarity,
    ts_rank(content_tsvector, to_tsquery('japanese', $2)) AS text_rank
FROM knowledge_chunks
WHERE 
    embedding IS NOT NULL
    AND (embedding <=> $1::halfvec(1536) < 0.3  -- ベクトル類似度
         OR content_tsvector @@ to_tsquery('japanese', $2))  -- 全文検索
ORDER BY 
    (1 - (embedding <=> $1::halfvec(1536))) * 0.7 + 
    ts_rank(content_tsvector, to_tsquery('japanese', $2)) * 0.3 DESC
LIMIT 10;
```

#### 推奨実装方針

1. **初期実装**: ベクトル検索のみ（現状）
2. **段階的導入**: `pg_bigm` 拡張を有効化し、インデックスを追加（設計段階で準備）
   - Dockerfile で pg_bigm をビルドしてカスタムイメージを作成
   - docker-compose.yml でカスタムイメージを使用
3. **ハイブリッド検索**: 検索精度の向上が必要になったタイミングで実装

**注意**: `pg_bigm` インデックスは追加のストレージ容量を消費しますが、
日本語検索の精度向上を考慮して設計段階で追加しておくことを強く推奨します。
特に kotonoha-bot のような日本語チャットログを扱うシステムには最適です。

---

## 11. 実装上の注意事項とベストプラクティス

### 11.1 セッションのチャンク化時のフォーマット改善

**問題**: 会話ログを単純に `\n` で結合すると、「誰が何を言ったか」の文脈がベクトル空間上で薄まる可能性があります。

**改善案**: チャンク化する際、以下のいずれかの形式を採用することを推奨します。

#### オプション1: Markdown形式

```python
def format_messages_for_knowledge(messages: list[dict]) -> str:
    """会話ログをMarkdown形式でフォーマット"""
    formatted = []
    for msg in messages:
        role = msg['role']
        content = msg['content']
        if role == 'user':
            formatted.append(f"**User**: {content}")
        elif role == 'assistant':
            formatted.append(f"**Assistant**: {content}")
        elif role == 'system':
            formatted.append(f"**System**: {content}")
    return "\n\n".join(formatted)
```

**出力例**:

```txt
**User**: こんにちは

**Assistant**: こんにちは！何かお手伝いできることはありますか？

**User**: Pythonのベストプラクティスを教えて
```

#### オプション2: メタデータに話者情報を含める

```python
def format_messages_for_knowledge(messages: list[dict]) -> tuple[str, dict]:
    """会話ログをフォーマットし、メタデータも返す"""
    content = "\n".join([msg['content'] for msg in messages])
    metadata = {
        "speakers": [msg['role'] for msg in messages],
        "message_count": len(messages),
        "first_speaker": messages[0]['role'] if messages else None
    }
    return content, metadata
```

**メリット**:

- ベクトル空間上で話者の文脈が保持される
- 検索結果の可読性が向上
- メタデータでのフィルタリングが可能

### 11.2 halfvec使用時の型キャスト

**問題**: `halfvec` 固定採用のため、クエリ時の型キャストも
`halfvec` に合わせる必要があります。
pgvectorのバージョンによっては、型の不一致でエラーが発生する可能性があります。

**解決策**: halfvec固定採用のため、SQL構築時に型キャストは `halfvec(1536)` を使用します。

```python
# ⚠️ 重要: halfvec固定採用
VECTOR_TYPE = "halfvec(1536)"

# 検索クエリの構築
async def similarity_search(
    self,
    query_embedding: list[float],
    top_k: int = 10
) -> list[dict]:
    """類似度検索（halfvec固定採用）"""
    query = f"""
        SELECT 
            s.type,
            s.title,
            c.content,
            1 - (c.embedding <=> $1::{VECTOR_TYPE}) AS similarity
        FROM knowledge_chunks c
        JOIN knowledge_sources s ON c.source_id = s.id
        WHERE c.embedding IS NOT NULL
          AND s.status = 'completed'
        ORDER BY c.embedding <=> $1::{VECTOR_TYPE}
        LIMIT $2
    """
    results = await self.pool.fetch(query, query_embedding, top_k)
    return [dict(row) for row in results]
```

**注意**: テーブル定義とクエリの型は `halfvec(1536)` で統一されています。

#### ⚠️ halfvec の入力型処理に関する重要な注意事項

**問題**: SQL文では `$1::halfvec(1536)` とキャストしていますが、
Python側（asyncpg）から渡すパラメータ `query_embedding` は `list[float]` です。
PostgreSQL側で `float[]` から `halfvec` へのキャストは自動で行われますが、
明示的なキャストがないと曖昧さのエラーが出る場合があります。

**解決策**:

1. **明示的な型キャスト**: SQL内で `::halfvec(1536)` と明示的にキャストする（現在の実装で対応済み、halfvec固定採用）

2. **pgvector-python の register_vector の動作**:
   - `pgvector.asyncpg.register_vector()` は `vector` 型と `halfvec` 型の両方をサポートします
   - ⚠️ **重要**: `register_vector()` は通常 `float32` として扱います
   - Python側から `list[float]` を渡すと、PostgreSQL側で
     `float32[] -> halfvec` のキャストが行われるため機能はします
   - ⚠️ **注意**: ドライバ層でのオーバーヘッドが微増しますが、許容範囲内です
   - 明示的な型キャスト（`$1::halfvec(1536)`）により、PostgreSQL側で適切に変換されます

3. **INSERT時の注意**:

   ```python
   # ✅ 正しい実装（明示的なキャスト、halfvec固定）
   vector_cast = "halfvec"
   await conn.execute(f"""
       UPDATE knowledge_chunks
       SET embedding = $1::{vector_cast}(1536)
       WHERE id = $2
   """, embedding_list, chunk_id)
   ```

4. **SELECT時の注意**:

   ```python
   # ✅ 正しい実装（明示的なキャスト）
   query = f"""
       SELECT embedding <=> $1::{vector_cast}(1536) AS distance
       FROM knowledge_chunks
   """
   ```

**テスト時の確認事項**:

⚠️ **重要**: 実装時には必ずhalfvec固定採用でのINSERTとSELECTが通るか確認してください。

```python
# テスト例
async def test_halfvec_insert_and_select():
    """halfvec固定採用でのINSERTとSELECTのテスト"""
    # 環境変数を設定
    # halfvec固定採用のため、環境変数の設定は不要
    
    # テスト用のベクトル
    test_embedding = [0.1] * 1536
    
    # INSERTテスト
    await conn.execute(f"""
        INSERT INTO knowledge_chunks (content, embedding)
        VALUES ($1, $2::{vector_cast}(1536))
    """, "test content", test_embedding)
    
    # SELECTテスト
    result = await conn.fetchrow(f"""
        SELECT embedding <=> $1::{vector_cast}(1536) AS distance
        FROM knowledge_chunks
        WHERE content = 'test content'
    """, test_embedding)
    
    assert result is not None
    assert result['distance'] is not None
```

**トラブルシューティング**:

- **エラー**: "operator is not unique: halfvec <=> unknown"
  - **原因**: 型キャストが不足している
  - **解決**: SQL内で `$1::halfvec(1536)` と明示的にキャストする

- **エラー**: "cannot cast type double precision[] to halfvec"
  - **原因**: pgvector-python の型マッピングの問題
  - **解決**: `register_vector()` が正しく呼ばれているか確認し、明示的なキャストを使用する

### 11.3 pgvectorの型登録（asyncpg接続プール）

**問題**: `pgvector` Pythonライブラリを使用する場合、
asyncpgの接続プールの各接続に対して型登録を行う必要があります。
接続プール作成後に1つの接続に対してのみ登録すると、
他の接続では型が認識されません。

**解決策**: `asyncpg.create_pool()` の `init` パラメータを使用して、各接続の初期化時に型登録を行います。

#### ❌ 誤った実装

```python
# 誤り: プール作成後に1つの接続にのみ登録
self.pool = await asyncpg.create_pool(...)
async with self.pool.acquire() as conn:
    await pgvector.asyncpg.register_vector(conn)  # この conn のみに登録される
    # プールの他のコネクションには登録されていない！
```

#### ✅ 正しい実装（pgvector-python公式ドキュメント推奨）

⚠️ **重要**: `asyncpg.create_pool()` の `init` パラメータには単一の関数しか渡せません。
pgvectorの型登録とJSONBコーデックの登録を両方行う場合は、ラッパー関数を作成する必要があります。

```python
async def _init_connection(self, conn: asyncpg.Connection):
    """コネクション初期化用ラッパー（ベクトル登録とJSONBコーデックを両方実行）"""
    # 1. pgvectorの型登録
    from pgvector.asyncpg import register_vector
    await register_vector(conn)
    
    # 2. JSONBコーデックの登録（orjsonを使用する場合）
    import orjson
    await conn.set_type_codec(
        'jsonb',
        encoder=lambda v: orjson.dumps(v).decode('utf-8'),
        decoder=lambda b: orjson.loads(
            b.encode('utf-8') if isinstance(b, str) else b
        ),
        schema='pg_catalog',
        format='text'
    )

async def initialize(self):
    self.pool = await asyncpg.create_pool(
        self.connection_string,
        init=self._init_connection,  # ← これが重要！
        min_size=min_size,
        max_size=max_size,
    )
```

**メリット**:

- **すべての接続で型登録**: プールの各接続が作成される際に自動的に型登録される
- **コードの簡潔性**: SQL内で手動キャストやエンコード/デコードが不要
- **型安全性**: Pythonの型チェッカーが正しく動作
- **JSONB自動変換**: dict/listを直接渡せる（orjsonによる高速処理）

**注意**: `init` パラメータは接続プール作成時に指定する必要があります。
接続プール作成後に個別の接続に対して登録しても、
プール内の他の接続には反映されません。

### 11.4 JSONBの自動変換（asyncpgカスタムコーデック）

**問題**: `asyncpg` で `json.dumps` して文字列として挿入している場合、
コード内で `json.dumps/loads` を書く必要があり、コードが冗長になります。

**解決策**: `asyncpg` のカスタムコーデックを設定することで、
Pythonの `dict` と PostgreSQLの `JSONB` を自動変換できます。

⚠️ **重要**: JSONBコーデックの登録は、pgvectorの型登録と同じ `_init_connection` 関数内で行います。
`asyncpg.create_pool()` の `init` パラメータには単一の関数しか渡せないため、両方を1つのラッパー関数にまとめる必要があります。

詳細は [11.3 pgvectorの型登録](#113-pgvectorの型登録asyncpg接続プール) の実装例を参照してください。

#### 使用例

```python
# コーデック設定後は、dictを直接渡せる
async def save_session(
    conn: asyncpg.Connection, session_key: str, messages: list[dict]
):
    """セッション保存（orjson.dumps不要）"""
    await conn.execute("""
        INSERT INTO sessions (session_key, messages)
        VALUES ($1, $2::jsonb)
    """, session_key, messages)  # messages は list[dict] を直接渡せる

# 取得時も自動的にdictに変換される
async def load_session(conn: asyncpg.Connection, session_key: str):
    """セッション読み込み（orjson.loads不要）"""
    row = await conn.fetchrow("""
        SELECT messages FROM sessions WHERE session_key = $1
    """, session_key)
    
    if row:
        messages = row['messages']  # 自動的に list[dict] に変換される
        return messages
    return None
```

**メリット**:

- **コードの簡潔性**: `orjson.dumps/loads` が不要
- **型安全性**: Pythonの型チェッカーが正しく動作
- **パフォーマンス**: orjsonによる高速な自動変換

### 11.5 並行性制御のベストプラクティス

#### 推奨パターン: FOR UPDATE SKIP LOCKED

**理由**: アプリケーションレベルのロック（`asyncio.Lock`）では、以下の問題が発生します：

1. **単一プロセス制限**: 単一のBotプロセスでしか機能しない
2. **再起動時の競合**: Bot再起動や誤った2重起動時に同じチャンクを同時処理
3. **スケールアウト不可**: 複数のワーカーが同時実行できない

**解決策**: PostgreSQLの `FOR UPDATE SKIP LOCKED` を使用して、DBレベルで排他制御を行います。

```python
async def process_embedding_batch(
    self,
    batch_size: int = 100
) -> int:
    """並行処理安全なEmbeddingバッチ処理"""
    processed_count = 0
    
    async with self.pool.acquire() as conn:
        async with conn.transaction():
            # FOR UPDATE SKIP LOCKED で取得
            rows = await conn.fetch("""
                SELECT id, source_id, content, token_count
                FROM knowledge_chunks
                WHERE embedding IS NULL
                ORDER BY id ASC
                LIMIT $1
                FOR UPDATE SKIP LOCKED
            """, batch_size)
            
            if not rows:
                return 0
            
            # 各チャンクを処理
            for row in rows:
                try:
                    # Embedding生成
                    embedding = await self._generate_embedding(row['content'])
                    
                    # 更新（型キャストを動的に変更）
                    await conn.execute(f"""
                        UPDATE knowledge_chunks
                        SET embedding = $1::{VECTOR_TYPE},
                            token_count = $2
                        WHERE id = $3
                    """, embedding, row['token_count'], row['id'])
                    
                    processed_count += 1
                except Exception as e:
                    logger.error(f"Failed to process chunk {row['id']}: {e}")
                    # エラー時は次のチャンクに進む
    
    return processed_count
```

**メリット**:

- **DBレベルでの排他制御**: アプリケーションレベルのロック不要
- **スケールアウト対応**: 複数のBotプロセスやワーカーが同時実行可能
- **再起動時の安全性**: Bot再起動や誤った2重起動時も競合が発生しない
- **パフォーマンス**: ロックされた行は自動的にスキップされ、待機しない

**注意**: `FOR UPDATE SKIP LOCKED` はトランザクション内で実行する必要があります。

### 11.6 接続プール管理とバックグラウンドタスク

**問題**: バックグラウンドタスク（セッションアーカイブ処理など）で並列処理を
行う場合、各タスクがDB接続を取得するため、`DB_POOL_MAX_SIZE` が小さい場合、
バックグラウンドタスクだけでプールを食い尽くし、通常のチャット応答
（MessageHandler）がタイムアウトするリスクがあります。

#### 解決策1（推奨）: セマフォによる動的制限

バックグラウンドタスク用のセマフォの上限を `DB_POOL_MAX_SIZE` の20〜30%程度に厳密に制限します。

```python
# セッションアーカイブの並列処理例
import os

max_pool_size = int(os.getenv("DB_POOL_MAX_SIZE", "20"))
# 20〜30%程度に制限（最小1、最大5）
archive_concurrency = max(1, min(5, int(max_pool_size * 0.25)))
archive_semaphore = asyncio.Semaphore(archive_concurrency)
```

**推奨設定**:

- **通常のチャット応答**: プールの70〜80%を確保
- **バックグラウンドタスク**: プールの20〜30%に制限
- **緊急時の余裕**: 10%程度の余裕を持たせる

#### 解決策2（大規模運用時）: 接続プールの分離

バックグラウンドタスク（Embedding, Archive）用の `asyncpg.Pool` と、Web/Bot応答用のプールを分ける選択肢もあります。

```python
# 接続プールの分離例
class PostgreSQLDatabase:
    def __init__(self, connection_string: str):
        self.connection_string = connection_string
        self.pool: asyncpg.Pool | None = None  # Web/Bot応答用
        self.background_pool: asyncpg.Pool | None = None  # バックグラウンドタスク用
    
    async def initialize(self) -> None:
        # Web/Bot応答用プール（通常のサイズ）
        self.pool = await asyncpg.create_pool(
            self.connection_string,
            init=self._init_connection,
            min_size=5,
            max_size=20,
        )
        
        # バックグラウンドタスク用プール（小さいサイズ）
        self.background_pool = await asyncpg.create_pool(
            self.connection_string,
            init=self._init_connection,
            min_size=2,
            max_size=5,  # バックグラウンドタスクは少ない接続で十分
        )
```

**選択基準**:

- **小規模運用（個人Bot）**: セマフォによる動的制限で十分
- **大規模運用（複数ワーカー、高負荷）**: 接続プールの分離を検討

**注意**: 接続プールを分ける場合、運用の複雑さが増すため、まずはセマフォによる制限を試し、必要に応じて分離を検討してください。

### 11.7 楽観的ロックの再試行ロジック

**問題**: 楽観的ロック（`UPDATE ... WHERE last_active_at = old_value`）が
失敗した場合（0件更新）、例外を投げてロールバックしますが、
自動リトライがない場合、Botが高頻度で使われている場合、
アーカイブが何度も失敗し続ける可能性があります。

#### ⚠️ 改善（データ整合性）: versionカラムを使用した楽観的ロック

- **現状の問題**: TIMESTAMPTZの精度（マイクロ秒）で競合検出に依存していると、
  同一マイクロ秒内の更新で誤検知の可能性
  （極めて稀だが理論上あり得る）
- **改善案**: `version`カラム（INT、更新ごとにインクリメント）を追加する方が堅牢です
- **実装**: `UPDATE ... SET version = version + 1
  WHERE version = $expected_version`

**解決策**: `tenacity` ライブラリを使用して、競合時のリトライ（指数バックオフ付き）を実装します。

```python
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type
)

@retry(
    stop=stop_after_attempt(3),  # 最大3回リトライ
    wait=wait_exponential(multiplier=1, min=1, max=10),  # 指数バックオフ: 1秒、2秒、4秒
    retry=retry_if_exception_type(ValueError),  # ValueError（楽観的ロック競合）のみリトライ
    reraise=True  # 最終的に失敗した場合は例外を再発生
)
async def _archive_session_with_retry():
    """楽観的ロック競合時の自動リトライ付きアーカイブ処理"""
    # UPDATE ... WHERE last_active_at = old_value が失敗した場合、
    # ValueError が発生し、自動的にリトライされる
    return await self._archive_session_impl(session_row)
```

**推奨設定**:

- **最大リトライ回数**: 3回
- **バックオフ**: 指数バックオフ（1秒、2秒、4秒）
- **リトライ対象**: 楽観的ロック競合（`ValueError`）のみ

**注意**: リトライ回数が多すぎると、逆に負荷が増加する可能性があるため、適切な上限を設定してください。

### 11.8 PostgreSQL 18 用テストスクリプトの実装

**背景**: PostgreSQL 18は比較的新しいバージョンであるため、
本番環境での安定性を確保するために、
テストスクリプトを充実させる方針を採用しています。

#### テストフィクスチャの実装

**推奨**: `testcontainers-python` を使用して、テスト時にPostgreSQL 18コンテナを自動起動します。

```python
# tests/conftest.py
import pytest
import pytest_asyncio
from testcontainers.postgres import PostgresContainer
from kotonoha_bot.db.postgres import PostgreSQLDatabase

@pytest.fixture(scope="session")
async def postgres_container():
    """テスト用PostgreSQL 18コンテナを起動"""
    with PostgresContainer("pgvector/pgvector:0.8.1-pg18") as postgres:
        yield postgres.get_connection_url()

@pytest_asyncio.fixture
async def postgres_db(postgres_container):
    """PostgreSQL データベースのフィクスチャ"""
    db = PostgreSQLDatabase(postgres_container)
    await db.initialize()
    
    # スキーマの初期化
    await db._create_schema()
    
    yield db
    
    # テスト後のクリーンアップ
    await db.close()
```

#### 重点テスト項目

1. **halfvec型の動作確認**

```python
# tests/unit/test_postgres_halfvec.py
async def test_halfvec_insert_and_search(postgres_db):
    """halfvec型のINSERTと検索のテスト"""
    # テスト用のベクトル
    test_embedding = [0.1] * 1536
    
    # INSERTテスト
    await postgres_db.pool.execute("""
        INSERT INTO knowledge_chunks (content, embedding)
        VALUES ($1, $2::halfvec(1536))
    """, "test content", test_embedding)
    
    # SELECTテスト（類似度検索）
    result = await postgres_db.pool.fetchrow("""
        SELECT embedding <=> $1::halfvec(1536) AS distance
        FROM knowledge_chunks
        WHERE content = 'test content'
    """, test_embedding)
    
    assert result is not None
    assert result['distance'] == 0.0  # 同じベクトルなので距離は0
```

1. **HNSWインデックスの動作確認**

```python
# tests/integration/test_hnsw_index.py
async def test_hnsw_index_performance(postgres_db):
    """HNSWインデックスの性能テスト"""
    # 大量のテストデータを挿入
    test_embeddings = [[0.1 * i] * 1536 for i in range(1000)]
    
    # バッチINSERT
    async with postgres_db.pool.acquire() as conn:
        async with conn.transaction():
            for i, emb in enumerate(test_embeddings):
                await conn.execute("""
                    INSERT INTO knowledge_chunks (content, embedding)
                    VALUES ($1, $2::halfvec(1536))
                """, f"test content {i}", emb)
    
    # インデックスが使用されているか確認（EXPLAIN ANALYZE）
    result = await postgres_db.pool.fetchrow("""
        EXPLAIN ANALYZE
        SELECT * FROM knowledge_chunks
        WHERE embedding IS NOT NULL
        ORDER BY embedding <=> $1::halfvec(1536)
        LIMIT 10
    """, test_embeddings[0])
    
    # インデックススキャンが使用されていることを確認
    assert "Index Scan using idx_chunks_embedding" in str(result)
```

1. **pgvector型登録の確認**

```python
# tests/unit/test_pgvector_registration.py
async def test_pgvector_type_registration(postgres_db):
    """pgvectorの型登録が正しく行われているか確認"""
    # 型登録が行われていれば、halfvec型を直接使用できる
    result = await postgres_db.pool.fetchval("""
        SELECT '[1,2,3]'::halfvec(3) <=> '[1,2,3]'::halfvec(3)
    """)
    
    assert result == 0.0  # 同じベクトルなので距離は0
```

1. **JSONBコーデックの動作確認**

```python
# tests/unit/test_jsonb_codec.py
async def test_jsonb_automatic_conversion(postgres_db):
    """JSONBコーデックが正しく動作しているか確認"""
    test_data = {"key": "value", "number": 123}
    
    # INSERT（dictを直接渡せる）
    await postgres_db.pool.execute("""
        INSERT INTO knowledge_sources (type, title, metadata)
        VALUES ($1, $2, $3::jsonb)
    """, "discord_session", "test", test_data)
    
    # SELECT（自動的にdictに変換される）
    result = await postgres_db.pool.fetchrow("""
        SELECT metadata FROM knowledge_sources WHERE title = 'test'
    """)
    
    assert result['metadata'] == test_data
    assert isinstance(result['metadata'], dict)
```

1. **並行性制御のテスト**

```python
# tests/integration/test_concurrency.py
async def test_for_update_skip_locked(postgres_db):
    """FOR UPDATE SKIP LOCKED の動作確認"""
    # 複数の未処理チャンクを挿入
    for i in range(10):
        await postgres_db.pool.execute("""
            INSERT INTO knowledge_chunks (source_id, content)
            VALUES ($1, $2)
        """, 1, f"test content {i}")
    
    # 2つのトランザクションで同時に取得を試みる
    async with postgres_db.pool.acquire() as conn1:
        async with postgres_db.pool.acquire() as conn2:
            async with conn1.transaction():
                rows1 = await conn1.fetch("""
                    SELECT id FROM knowledge_chunks
                    WHERE embedding IS NULL
                    LIMIT 5
                    FOR UPDATE SKIP LOCKED
                """)
                
                async with conn2.transaction():
                    rows2 = await conn2.fetch("""
                        SELECT id FROM knowledge_chunks
                        WHERE embedding IS NULL
                        LIMIT 5
                        FOR UPDATE SKIP LOCKED
                    """)
            
            # 2つのトランザクションで異なる行が取得されることを確認
            ids1 = {row['id'] for row in rows1}
            ids2 = {row['id'] for row in rows2}
            assert ids1.isdisjoint(ids2)  # 重複がないことを確認
```

#### テスト実行コマンド

```bash
# すべてのPostgreSQLテストを実行
pytest tests/ -k postgres -v

# 統合テストのみ実行
pytest tests/integration/ -v

# カバレッジ付きで実行
pytest tests/ --cov=src/kotonoha_bot --cov-report=term-missing

# PostgreSQL 18コンテナを使用したテスト
docker-compose -f docker-compose.test.yml up -d
pytest tests/integration/test_postgres.py -v
```

#### CI/CDでの自動テスト

GitHub Actionsでの自動テスト設定例：

```yaml
# .github/workflows/ci.yml
name: CI
on: [push, pull_request]

jobs:
  test-postgres18:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: pgvector/pgvector:0.8.1-pg18
        env:
          POSTGRES_PASSWORD: test
          POSTGRES_DB: test_kotonoha
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - run: pip install -e ".[test]"
      - run: pytest tests/ -v --cov=src/kotonoha_bot
```

**推奨テストカバレッジ**: 80%以上（特にPostgreSQL関連のコード）

---

## 12. バックアップ戦略

### 12.1 バックアップ方法の選択

**推奨バックアップ方法**:

1. **pg_dump による定期バックアップ**（小規模〜中規模データ）
   - カスタムフォーマット（圧縮済み）を使用
   - 論理バックアップ（データとスキーマを含む）
   - リストア時にインデックスの再構築が必要

2. **物理バックアップ（WALアーカイブ）**（大規模データ）
   - ファイルシステムレベルのバックアップ
   - リストア時間が短い
   - より複雑な設定が必要

### 12.2 pg_dump によるバックアップ

**基本的なバックアップコマンド**:

```bash
# カスタムフォーマット（推奨、圧縮済み）
pg_dump -U kotonoha -F c -f kotonoha_backup.dump kotonoha

# プレーンテキスト形式（可読性が高い）
pg_dump -U kotonoha -F p -f kotonoha_backup.sql kotonoha
```

**リストアコマンド**:

```bash
# カスタムフォーマットからのリストア
pg_restore -U kotonoha -d kotonoha -c kotonoha_backup.dump

# プレーンテキスト形式からのリストア
psql -U kotonoha -d kotonoha < kotonoha_backup.sql
```

### 12.3 ⚠️ 重要: バックアップとリストアの整合性

#### 課題: pg_dump は論理バックアップです

- **pgvector のデータは復元されますが、インデックスの再構築がリストア時に走るため、リストア時間が非常に長くなる可能性があります**
- HNSWインデックス（`idx_chunks_embedding`）は、データ量に応じて構築時間が増加します
- 10万件を超えるデータの場合、インデックス再構築に数時間かかる可能性があります

#### 対策

1. **小規模データ（〜10万件）**:
   - `pg_dump` による論理バックアップで十分
   - リストア後のインデックス再構築時間を許容範囲として計算に入れておく
   - リストア時間の見積もり:
     - データ量: 10万件 → インデックス再構築: 約30分〜1時間（環境による）
     - データ量: 50万件 → インデックス再構築: 約2〜4時間（環境による）

2. **大規模データ（10万件超）**:
   - **物理バックアップ（WALアーカイブなど）を検討する**
   - ファイルシステムレベルのバックアップ（`pg_basebackup`）
   - リストア時間が大幅に短縮される
   - より複雑な設定と運用が必要

3. **ハイブリッドアプローチ**:
   - 定期的な `pg_dump` による論理バックアップ（データ整合性の確認用）
   - 日次または週次の物理バックアップ（高速リストア用）

**推奨バックアップ戦略**:

```bash
# 日次バックアップ（論理バックアップ）
0 2 * * * pg_dump -U kotonoha -F c \
  -f /backups/kotonoha_$(date +\%Y\%m\%d).dump kotonoha

# 週次物理バックアップ（大規模データの場合）
0 3 * * 0 pg_basebackup -U kotonoha \
  -D /backups/basebackup_$(date +\%Y\%m\%d) -Ft -z -P
```

**リストア時間の見積もり**:

| データ量 | 論理バックアップ（pg_dump） | 物理バックアップ（pg_basebackup） |
|---------|---------------------------|--------------------------------|
| 1万件 | 約5分 | 約2分 |
| 10万件 | 約30分〜1時間 | 約5分 |
| 50万件 | 約2〜4時間 | 約10分 |
| 100万件 | 約4〜8時間 | 約20分 |

**注意**: 上記の時間は環境（CPU、メモリ、ストレージ性能）によって大きく変動します。

---