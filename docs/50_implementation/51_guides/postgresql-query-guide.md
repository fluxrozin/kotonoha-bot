# PostgreSQL クエリガイド

**作成日**: 2026年1月19日  
**バージョン**: 1.22  
**対象プロジェクト**: kotonoha-bot v0.8.0

## 関連ドキュメント

- [スキーマ概要](../../40_design_detailed/42_db-schema-physical/postgresql-schema-overview.md)
- [テーブル定義](../../40_design_detailed/42_db-schema-physical/postgresql-schema-tables.md)
- [インデックス設計](../../40_design_detailed/42_db-schema-physical/postgresql-schema-indexes.md)
- [実装ガイド](./postgresql-implementation-guide.md)

---

## 使用例とクエリ

### 8.1 セッション管理

#### セッションの作成

```sql
-- ⚠️ 注意: id は自動採番されるため、INSERT文には含めない
-- アプリケーション内部での参照は session_key を使用
INSERT INTO sessions (session_key, session_type, channel_id, user_id)
VALUES ('mention:123456789', 'mention', 987654321, 123456789)
ON CONFLICT (session_key) DO NOTHING;
```

#### メッセージの追加

```sql
UPDATE sessions
SET 
    messages = messages || '{"role": "user", "content": "こんにちは"}'::jsonb,
    last_active_at = CURRENT_TIMESTAMP
WHERE session_key = 'mention:123456789';
```

#### セッションの取得

```sql
SELECT * FROM sessions WHERE session_key = 'mention:123456789';
```

#### 非アクティブセッションの検索（アーカイブ対象）

```sql
-- ⚠️ 注意: アプリケーション内部での参照は session_key を使用
-- id は将来的な外部キー参照用に残しておく
SELECT * FROM sessions
WHERE status = 'active'
  AND last_active_at < CURRENT_TIMESTAMP - INTERVAL '1 hour';
```

### 8.2 知識ベース管理

#### ソースの登録

```sql
INSERT INTO knowledge_sources (type, title, uri, metadata, status)
VALUES (
    'discord_session',
    '会話ログ: dev-talk チャンネル',
    'https://discord.com/channels/123/456',
    '{"channel_name": "dev-talk", "participants": [123, 456]}'::jsonb,
    'pending'
)
RETURNING id;
```

#### チャンクの登録（Embedding未処理）

```sql
INSERT INTO knowledge_chunks (source_id, content, location, token_count)
VALUES (
    1,
    '会話の要約テキスト...',
    '{"message_id": 999999999999999999}'::jsonb,
    150
);
```

#### Embeddingの更新

```sql
UPDATE knowledge_chunks
SET embedding = $1::halfvec(1536)
WHERE id = 1;
```

#### ソースのステータス更新

```sql
UPDATE knowledge_sources
SET 
    status = 'completed',
    updated_at = CURRENT_TIMESTAMP
WHERE id = 1;
```

### 8.3 ベクトル検索

#### 基本的な類似度検索

```sql
-- ⚠️ 重要: WHERE c.embedding IS NOT NULL 条件は必須です
-- この条件がないと、HNSWインデックス（idx_chunks_embedding）が使われずフルスキャンになります
SELECT 
    s.type,
    s.title,
    s.uri,
    c.content,
    c.location,
    1 - (c.embedding <=> $1::halfvec(1536)) AS similarity
FROM knowledge_chunks c
JOIN knowledge_sources s ON c.source_id = s.id
WHERE c.embedding IS NOT NULL  -- ⚠️ 必須: HNSWインデックス使用のため
  AND s.status = 'completed'
ORDER BY c.embedding <=> $1::halfvec(1536)
LIMIT 10;
```

#### 類似度閾値を指定した検索

```sql
-- ⚠️ 重要: WHERE c.embedding IS NOT NULL 条件は必須です
SELECT 
    s.type,
    s.title,
    c.content,
    1 - (c.embedding <=> $1::halfvec(1536)) AS similarity
FROM knowledge_chunks c
JOIN knowledge_sources s ON c.source_id = s.id
WHERE c.embedding IS NOT NULL  -- ⚠️ 必須: HNSWインデックス使用のため
  AND s.status = 'completed'
  AND 1 - (c.embedding <=> $1::halfvec(1536)) > 0.7  -- 類似度閾値
ORDER BY similarity DESC
LIMIT 5;
```

#### チャンネルフィルタ付き検索

```sql
-- ⚠️ 重要: WHERE c.embedding IS NOT NULL 条件は必須です
SELECT 
    s.type,
    s.title,
    c.content,
    1 - (c.embedding <=> $1::halfvec(1536)) AS similarity
FROM knowledge_chunks c
JOIN knowledge_sources s ON c.source_id = s.id
WHERE c.embedding IS NOT NULL  -- ⚠️ 必須: HNSWインデックス使用のため
  AND s.status = 'completed'
  AND s.metadata->>'channel_id' = '987654321'::text
ORDER BY c.embedding <=> $1::halfvec(1536)
LIMIT 10;
```

#### ソースタイプフィルタ付き検索（単一指定）

```sql
-- ⚠️ 重要: WHERE c.embedding IS NOT NULL 条件は必須です
SELECT 
    s.type,
    s.title,
    c.content,
    1 - (c.embedding <=> $1::halfvec(1536)) AS similarity
FROM knowledge_chunks c
JOIN knowledge_sources s ON c.source_id = s.id
WHERE c.embedding IS NOT NULL  -- ⚠️ 必須: HNSWインデックス使用のため
  AND s.status = 'completed'
  AND s.type = 'discord_session'
ORDER BY c.embedding <=> $1::halfvec(1536)
LIMIT 10;
```

#### ソースタイプフィルタ付き検索（複数指定）

```sql
-- ⚠️ 重要: WHERE c.embedding IS NOT NULL 条件は必須です
-- 複数のソースタイプ（例：「WebとPDFから検索したい」）を同時に指定する場合
SELECT 
    s.type,
    s.title,
    c.content,
    1 - (c.embedding <=> $1::halfvec(1536)) AS similarity
FROM knowledge_chunks c
JOIN knowledge_sources s ON c.source_id = s.id
WHERE c.embedding IS NOT NULL  -- ⚠️ 必須: HNSWインデックス使用のため
  AND s.status = 'completed'
  AND s.type = ANY($2::source_type_enum[])  -- ⚠️ 複数指定: IN句またはANY句を使用
ORDER BY c.embedding <=> $1::halfvec(1536)
LIMIT 10;
```

**使用例**: `$2 = ['web_page', 'document_file']` を指定すると、WebページとPDFファイルの両方から検索します。

#### Python API での使用例

```python
from kotonoha_bot.db.postgres import PostgreSQLDatabase

# データベースの初期化
db = PostgreSQLDatabase(connection_string=settings.database_url)
await db.initialize()

# 基本的な類似度検索（閾値フィルタリングあり）
query_embedding = [0.1] * 1536  # 1536次元のベクトル
results = await db.similarity_search(
    query_embedding=query_embedding,
    top_k=10
)

# カスタム閾値を指定
results = await db.similarity_search(
    query_embedding=query_embedding,
    top_k=10,
    similarity_threshold=0.8  # より厳しい閾値
)

# 閾値フィルタリングを無効化（生の類似度スコアを取得）
results_raw = await db.similarity_search(
    query_embedding=query_embedding,
    top_k=10,
    apply_threshold=False  # 閾値フィルタリングを無効化
)

# フィルタ付き検索
results = await db.similarity_search(
    query_embedding=query_embedding,
    top_k=10,
    filters={
        "source_type": "discord_session",
        "channel_id": 123456789
    }
)

# 複数のソースタイプを指定
results = await db.similarity_search(
    query_embedding=query_embedding,
    top_k=10,
    filters={
        "source_types": ["discord_session", "document_file"]
    }
)
```

**パラメータ説明**:

- `query_embedding` (list[float]): クエリのベクトル（1536次元）
- `top_k` (int): 取得する結果の数（デフォルト: 10）
- `filters` (dict | None): フィルタ条件
  - `source_type`: 単一のソースタイプを指定
  - `source_types`: 複数のソースタイプを指定（リスト）
  - `channel_id`: チャンネルIDでフィルタ
  - `user_id`: ユーザーIDでフィルタ
- `similarity_threshold` (float | None): 類似度閾値。
  `None`の場合は設定値（デフォルト0.7）を使用
- `apply_threshold` (bool): 閾値フィルタリングを適用するか。
  `False`の場合は閾値フィルタリングを無効化し、
  生の類似度スコアを返す（デフォルト: `True`）

### 8.4 バッチ処理用クエリ

#### 処理待ちのソース検索

```sql
SELECT * FROM knowledge_sources
WHERE status = 'pending'
ORDER BY created_at ASC
LIMIT 100;
```

#### Embedding未処理のチャンク検索（並行処理安全版）

**重要**: 複数のワーカープロセスが同時に実行される場合、
`FOR UPDATE SKIP LOCKED` を使用してDBレベルで排他制御を行います。
これにより、アプリケーションレベルのロック（`asyncio.Lock`）に依存せず、
安全にバッチ処理が可能になります。

```sql
-- 取得と同時にロックする（他のワーカーはこの行をスキップする）
SELECT id, source_id, content, token_count
FROM knowledge_chunks
WHERE embedding IS NULL
ORDER BY id ASC
LIMIT 100
FOR UPDATE SKIP LOCKED;
```

**メリット**:

- **DBレベルでの排他制御**: アプリケーションレベルのロック不要
- **スケールアウト対応**: 複数のBotプロセスやワーカーが同時実行可能
- **再起動時の安全性**: Bot再起動や誤った2重起動時も競合が発生しない
- **パフォーマンス**: ロックされた行は自動的にスキップされ、待機しない

**注意**: `FOR UPDATE SKIP LOCKED` はトランザクション内で実行する必要があります。

#### Embedding未処理のチャンク検索（単一プロセス版）

単一プロセスでのみ実行される場合は、以下のシンプルなクエリでも問題ありません：

```sql
SELECT * FROM knowledge_chunks
WHERE embedding IS NULL
ORDER BY created_at ASC
LIMIT 100;
```

#### 処理中のソース検索（タイムアウト判定）

```sql
SELECT * FROM knowledge_sources
WHERE status = 'processing'
  AND updated_at < CURRENT_TIMESTAMP - INTERVAL '30 minutes';
```

---