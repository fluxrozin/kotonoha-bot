# PostgreSQL スキーマ設計書 - インデックス・制約・データ型

**作成日**: 2026年1月19日  
**バージョン**: 1.22  
**対象プロジェクト**: kotonoha-bot v0.8.0

## 関連ドキュメント

- [概要](./postgresql-schema-overview.md)
- [テーブル定義](./postgresql-schema-tables.md)
- [完全なDDLスクリプト](./postgresql-schema-ddl.md)
- [クエリガイド](../../50_implementation/51_guides/postgresql-query-guide.md)

---

## インデックス設計

### 5.1 sessions テーブルのインデックス

```sql
-- session_key での検索用（アプリケーション内部での参照用）
CREATE INDEX idx_sessions_session_key ON sessions(session_key);

-- ステータスでの検索用（アーカイブ対象のセッション検索）
CREATE INDEX idx_sessions_status ON sessions(status);

-- 最終アクティビティ日時での検索用（タイムアウト判定）
CREATE INDEX idx_sessions_last_active_at ON sessions(last_active_at);

-- チャンネルIDでの検索用
CREATE INDEX idx_sessions_channel_id ON sessions(channel_id);

-- アーカイブ対象セッション検索用の複合インデックス（パフォーマンス向上）
CREATE INDEX idx_sessions_archive_candidates ON sessions(status, last_active_at)
WHERE status = 'active';
```

**使用例**:

- `status='active'` かつ `last_active_at < 1時間前` のセッションを検索（アーカイブ処理）
- 特定チャンネルのセッション一覧取得

### 5.2 knowledge_sources テーブルのインデックス

```sql
-- JSONメタデータ内の検索用 (GINインデックス)
CREATE INDEX idx_sources_metadata ON knowledge_sources USING gin (metadata);

-- ステータスでの検索用（処理待ちのソース検索）
CREATE INDEX idx_sources_status ON knowledge_sources(status);

-- タイプでの検索用
CREATE INDEX idx_sources_type ON knowledge_sources(type);
```

**使用例**:

- `status='pending'` のソースを検索（バックグラウンド処理）
- `metadata->>'channel_name' = 'dev-talk'` での検索

### 5.3 knowledge_chunks テーブルのインデックス

```sql
-- ベクトル検索用インデックス (HNSW法)
-- 類似度計算には cosine distance (<=>) を使用
-- パラメータ: m=16 (各ノードの接続数), ef_construction=64 (構築時の探索深さ)
-- NASのメモリリソースを考慮しつつ、精度を確保する設定
-- 注意: 環境変数 KB_HNSW_M と KB_HNSW_EF_CONSTRUCTION で制御可能
-- ⚠️ 重要: halfvec固定採用のため、halfvec_cosine_ops を使用
CREATE INDEX idx_chunks_embedding ON knowledge_chunks 
USING hnsw (embedding halfvec_cosine_ops)
WITH (m = 16, ef_construction = 64);  -- 環境変数から読み込むことを推奨

-- Source IDでの検索用
CREATE INDEX idx_chunks_source_id ON knowledge_chunks(source_id);

-- embedding IS NOT NULL での検索用（検索可能なチャンクのみ取得）
-- ⚠️ 重要: この部分インデックスは必須です
-- 改善: embedding カラム自体を含め、created_at も含めることでソート性能を向上
CREATE INDEX idx_chunks_searchable ON knowledge_chunks(source_id, created_at)
WHERE embedding IS NOT NULL AND token_count > 0;

-- ⚠️ 改善（パフォーマンス）: 処理待ち行列専用の部分インデックス
-- FOR UPDATE SKIP LOCKED を使うクエリは WHERE embedding IS NULL を参照します。
-- knowledge_chunks が数百万件になった際、embedding IS NULL の行を探すのに
-- 時間がかかるとバッチ処理が遅延します。
-- 処理待ち行列専用の部分インデックスを作成することで、ワーカーはテーブル全体を
-- スキャンせず、インデックスのみを見て処理対象を即座に見つけられます。
-- リトライ上限未満（retry_count < 3）のみを含めることで、諦められたチャンクを除外
CREATE INDEX idx_chunks_queue ON knowledge_chunks(id)
WHERE embedding IS NULL AND retry_count < 3;

-- ハイブリッド検索用インデックス（オプション、将来の拡張用）
-- pg_bigm 拡張を有効化した後に実行
-- 部分一致検索や類似文字列検索に使用（固有名詞の検索に有効）
-- CREATE EXTENSION IF NOT EXISTS pg_bigm;
-- CREATE INDEX idx_chunks_content_bigm ON knowledge_chunks
-- USING gin (content gin_bigm_ops);
```

**⚠️ 重要: `embedding IS NOT NULL` 条件の必須性**:

- **理由**: HNSWインデックス（`idx_chunks_embedding`）は `embedding` が NULL でない場合にのみ有効です
- **リスク**: 検索クエリで `embedding IS NOT NULL` 条件を忘れると、
  HNSWインデックスが使われずフルスキャンになるリスクがあります。
  実装漏れが発生すると、意図せずフルスキャンが発生し、
  本番環境で突然死（タイムアウト）する原因になります。
- **改善案（Strong Recommendation）**:
  - クエリビルダーやラッパー関数（`similarity_search`）側で、強制的にこの条件が付与される仕組みをコードレベルで保証してください
  - アプリケーション実装者の注意深さに依存した設計ではなく、コードレベルで保証することで、実装漏れを防ぎます
  - すべてのベクトル検索クエリで必ず `WHERE embedding IS NOT NULL` を含める必要があります
- **実装時の注意**: クエリ構築時にこの条件を忘れないよう、
  コメントや定数化を推奨しますが、それだけでは不十分です。
  コードレベルで強制付与する仕組みを実装してください

**HNSWインデックスパラメータ説明**:

- **m**: 各ノードの接続数。値が大きいほど精度が上がるが、インデックスサイズと構築時間が増加（デフォルト: 16）
- **ef_construction**: 構築時の探索深さ。値が大きいほど精度が上がるが、構築時間が増加（デフォルト: 64）

**⚠️ 運用上の注意: HNSWインデックスのメモリ消費**:

- **現状**: `m=16`, `ef_construction=64` は初期運用には適切な設定です
- **メモリ消費の特性**:
  - `halfvec` で容量は減りますが、HNSWは高速化のためにグラフ構造をメモリに乗せようとします
  - データ量が増えると、インデックスのメモリ使用量が増加します
- **監視とチューニング**:
  - **初期は問題ありませんが、データが10万件を超えたあたりで監視が必要です**
  - `pg_stat_activity` やコンテナのメモリ使用量を監視してください
  - PostgreSQLの設定（`postgresql.conf`）チューニングが必要になる可能性があります
  - 特に以下のパラメータの調整を検討してください:
    - `maintenance_work_mem`: インデックス構築時のメモリ使用量（デフォルト: 64MB）
      - ⚠️ **重要**: インデックス構築時（INSERT/UPDATE時）とリストア時にOOM Killerが発動する可能性があります
      - NASのメモリが少ない場合、大量のデータを COPY や INSERT した
        直後のインデックス構築でOOM Killerが発動し、
        Postgresプロセスが落ちる可能性があります
      - **推奨設定**: システムメモリの10〜20%程度（最小128MB、最大1GB）
      - 例: NASのメモリが4GBなら、256MB〜512MB程度に抑える
      - **設定方法**:
        - docker-compose.yml:
          `POSTGRES_INITDB_ARGS: --maintenance-work-mem=256MB`
          （初期化時のみ）
        - postgresql.conf: `maintenance_work_mem = 256MB`（実行時も有効、推奨）
        - または: `ALTER SYSTEM SET maintenance_work_mem = '256MB';` +
          `SELECT pg_reload_conf();`
    - `work_mem`: クエリ実行時のメモリ使用量（デフォルト: 4MB）
    - `shared_buffers`: 共有バッファプールのサイズ（デフォルト: 128MB）
- **推奨監視項目**:
  - コンテナのメモリ使用量（`docker stats`）
  - PostgreSQLのメモリ使用量（`pg_stat_activity`）
  - インデックスサイズ（`pg_size_pretty(pg_relation_size('idx_chunks_embedding'))`）
  - クエリ実行時間（`EXPLAIN ANALYZE`）

**⚠️ 重要: HNSWのビルドコストと maintenance_work_mem**:

- **リスク**: 設計書には「データが増えるとメモリを食う」とありますが、
  具体的な危険性は**「インデックス構築時（INSERT/UPDATE時）」と
  「リストア時」**にあります
- **問題**: NASのメモリが少ない場合、大量のデータを COPY や INSERT した
  直後のインデックス構築でOOM Killerが発動し、
  Postgresプロセスが落ちる可能性があります
- **対策**: docker-compose.yml または postgresql.conf で
  `maintenance_work_mem` を制限してください
  - 例: NASのメモリが4GBなら、256MB〜512MB程度に抑える
  - デフォルトのままだと危険な場合があります
- **設定方法**:
  - **docker-compose.yml**: 環境変数 `POSTGRES_INITDB_ARGS` を使用
  - **postgresql.conf**: `maintenance_work_mem = 256MB` を設定
  - **推奨値**: システムメモリの10〜20%程度（最小128MB、最大1GB）

**使用例**:

- ベクトル類似度検索（`embedding <=> $1`）
- 特定ソースのチャンク一覧取得
- 検索可能なチャンクのみ取得（`embedding IS NOT NULL`）
- ハイブリッド検索（ベクトル検索 + pg_bigm キーワード検索）

---

## 6. 制約とリレーション

### 6.1 外部キー制約

```sql
-- knowledge_chunks.source_id -> knowledge_sources.id
-- 親ソースが削除された場合、子チャンクも自動的に削除される（CASCADE）
ALTER TABLE knowledge_chunks 
ADD CONSTRAINT fk_chunks_source 
FOREIGN KEY (source_id) 
REFERENCES knowledge_sources(id) 
ON DELETE CASCADE;
```

### 6.2 チェック制約

```sql
-- sessions.status は 'active' または 'archived' のみ許可
-- 注意: ENUM型を使用しているため、このCHECK制約は冗長ですが、明示性のために残しています
ALTER TABLE sessions 
ADD CONSTRAINT chk_sessions_status 
CHECK (status IN ('active', 'archived'));

-- knowledge_sources.status は 'pending', 'processing', 'completed',
-- 'partial', 'failed' を許可
-- 注意: ENUM型を使用しているため、このCHECK制約は冗長ですが、明示性のために残しています
ALTER TABLE knowledge_sources 
ADD CONSTRAINT chk_sources_status 
CHECK (status IN ('pending', 'processing', 'completed', 'partial', 'failed'));
```

### 6.3 一意制約

```sql
-- sessions.session_key は一意（UNIQUE制約により保証）
-- sessions.id は主キー（BIGSERIAL、自動採番）
-- アプリケーション内部での参照は session_key を使いつつ、
-- 将来的なリレーション（例：session_tags テーブルなど）は id を使う余地を残す
```

---

## 7. データ型の説明

### 7.1 JSONB

**使用箇所**: `sessions.messages`, `knowledge_sources.metadata`,
`knowledge_chunks.location`

**メリット**:

- 柔軟なスキーマ（ソースタイプごとに異なる属性を格納可能）
- 高速な検索（GINインデックス対応）
- 部分更新が可能

**使用例**:

```sql
-- メタデータ内の検索
SELECT * FROM knowledge_sources 
WHERE metadata->>'channel_name' = 'dev-talk';

-- メタデータの更新
UPDATE knowledge_sources 
SET metadata = jsonb_set(metadata, '{participants}', '[123, 456]'::jsonb)
WHERE id = 1;
```

### 7.2 vector / halfvec

**使用箇所**: `knowledge_chunks.embedding`

**説明**:

- **halfvec(1536)**: 1536次元のベクトル型（float16、4バイト/次元、pgvector 0.7.0以降）を固定採用

**メモリ使用量**:

- `halfvec(1536)`: 約 6KB/レコード（1536 × 4バイト）
- 比較: `vector(1536)` は約 12KB/レコード（1536 × 8バイト）のため、halfvecでメモリ使用量が50%削減

**採用理由**: Synology NASのリソース節約のため、`halfvec` を固定採用（精度への影響は最小限）

**重要**: クエリ時の型キャストは `halfvec` を使用します：

```sql
-- halfvec固定採用
SELECT * FROM knowledge_chunks
WHERE embedding <=> $1::halfvec(1536) < 0.3;
```

### 7.3 TIMESTAMPTZ

**使用箇所**: すべての `*_at` カラム

**説明**: タイムゾーン情報を含むタイムスタンプ型。UTCで保存し、アプリケーション側でタイムゾーン変換を行う。

---