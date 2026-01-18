# Phase 8: 残りの実装タスクまとめ

**作成日**: 2026年1月19日  
**現在の進捗**: Step 0-4, 6 完了 / Step 5, 7 未実装

---

## 📋 実装状況サマリー

### ✅ 完了済み

- **Step 0**: 依存関係の確認と設計レビュー
  - `pydantic-settings`による設定管理（`config.py`）
  - `constants.py`の作成（定数管理）
  - Alembicの初期化と初回マイグレーション

- **Step 1**: データベース抽象化レイヤー
  - `DatabaseProtocol`インターフェース
  - `KnowledgeBaseProtocol`インターフェース
  - `SearchResult`型定義

- **Step 2**: PostgreSQL実装
  - `PostgreSQLDatabase`クラスの実装
  - `ChatSession`モデルの拡張（status, guild_id, version等）
  - `docker-compose.yml`にPostgreSQLコンテナを追加
  - pgvector拡張の有効化
  - JSONBコーデックの設定

- **Step 3**: ベクトル検索機能
  - `similarity_search`メソッドの実装
  - フィルタリング機能（source_type, channel_id, user_id等）
  - SQLインジェクション対策

- **Step 4**: 知識ベーススキーマ
  - `save_source`メソッドの実装
  - `save_chunk`メソッドの実装
  - トークン数カウント機能

- **Step 6**: Docker Composeの更新
  - PostgreSQLコンテナの追加
  - 環境変数の設定

### ⏳ 未実装（残りの作業）

- **Step 5**: Embedding処理の実装（2-3日）
- **Step 7**: テストと最適化（1-2日）

---

## 🔨 Step 5: Embedding処理の実装（2-3日）

### 5.1 Embeddingプロバイダーの実装

**作業内容**:

1. **`src/kotonoha_bot/external/embedding/__init__.py`** の作成
   - `EmbeddingProvider`抽象基底クラスの定義
   - `generate_embedding`メソッド（単一テキスト）
   - `get_dimension`メソッド

2. **`src/kotonoha_bot/external/embedding/openai_embedding.py`** の作成
   - `OpenAIEmbeddingProvider`クラスの実装
   - `text-embedding-3-small`モデルを使用
   - `tenacity`によるリトライロジック（RateLimitError, APITimeoutError）
   - `generate_embeddings_batch`メソッド（バッチ処理）

**完了基準**:

- [ ] `EmbeddingProvider`インターフェースが定義されている
- [ ] `OpenAIEmbeddingProvider`が実装されている
- [ ] Embedding APIのリトライロジックが実装されている（tenacity使用）
- [ ] バッチ処理メソッドが実装されている

---

### 5.2 バックグラウンドタスクの実装

**作業内容**:

1. **`src/kotonoha_bot/features/knowledge_base/embedding_processor.py`** の作成
   - `EmbeddingProcessor`クラスの実装
   - `@tasks.loop`デコレータによる定期実行タスク
   - `FOR UPDATE SKIP LOCKED`パターンの実装
   - トランザクション内でのAPIコールを回避（Tx1 → No Tx → Tx2）
   - セマフォによる同時実行数制限（DB_POOL_MAX_SIZEの20〜30%）
   - `asyncio.Lock`による競合状態対策
   - Dead Letter Queue（DLQ）への移動ロジック
   - Graceful Shutdownの実装

**重要な実装ポイント**:

- **トランザクション分離**:

  ```python
  # Tx1: FOR UPDATE SKIP LOCKED で対象行を取得し、即コミット
  async with conn.transaction():
      pending_chunks = await conn.fetch("""
          SELECT id, content, source_id
          FROM knowledge_chunks
          WHERE embedding IS NULL AND retry_count < $1
          FOR UPDATE SKIP LOCKED
          LIMIT $2
      """, MAX_RETRY_COUNT, batch_size)
  
  # No Tx: OpenAI API コール（時間かかる処理、トランザクション外）
  embeddings = await self._generate_embeddings_batch(texts)
  
  # Tx2: 結果を UPDATE（別トランザクション）
  async with conn.transaction():
      await conn.executemany("""
          UPDATE knowledge_chunks
          SET embedding = $1::halfvec(1536), retry_count = 0
          WHERE id = $2
      """, update_data)
  ```

- **セマフォによる同時実行数制限**:

  ```python
  # 接続プール枯渇対策: DB_POOL_MAX_SIZEの20〜30%程度に制限
  max_concurrent = max(1, min(5, int(max_pool_size * 0.25)))
  self._semaphore = asyncio.Semaphore(max_concurrent)
  ```

- **DLQへの移動**:

  ```python
  async def _move_to_dlq(self, conn, chunk, error):
      # エラーコードと一般化されたメッセージのみを保存
      error_code = self._classify_error(error)
      error_message = self._generalize_error_message(error)
      # knowledge_chunks_dlq に移動
  ```

**完了基準**:

- [ ] `EmbeddingProcessor`クラスが実装されている
- [ ] バックグラウンドタスクが動作する
- [ ] `FOR UPDATE SKIP LOCKED`パターンが実装されている
- [ ] トランザクション内でのAPIコールを回避している
- [ ] セマフォによる同時実行数制限が実装されている
- [ ] DLQへの移動ロジックが実装されている
- [ ] Graceful Shutdownが実装されている
- [ ] halfvec固定採用でのembedding更新が正しく動作する

---

### 5.3 セッション知識化バッチ処理の実装

**作業内容**:

1. **`src/kotonoha_bot/features/knowledge_base/session_archiver.py`** の作成
   - `SessionArchiver`クラスの実装
   - `@tasks.loop`デコレータによる定期実行タスク（デフォルト: 1時間ごと）
   - 非アクティブなセッション（`last_active_at < 1時間前`）の検索
   - セッションを知識ベースに変換（`knowledge_sources` + `knowledge_chunks`）
   - スライディングウィンドウ（のりしろ）方式の実装
   - 楽観的ロックによる競合状態対策（`version`カラム）
   - トランザクション分離レベル `REPEATABLE READ` の設定
   - メッセージ単位/会話ターン単位でのチャンク化
   - Graceful Shutdownの実装

**重要な実装ポイント**:

- **スライディングウィンドウ（のりしろ）方式**:

  ```python
  # アーカイブ時に短期記憶を「全消去」するのではなく、
  # 「直近の数メッセージ（のりしろ）」を残して更新
  KB_ARCHIVE_OVERLAP_MESSAGES = 5  # デフォルト: 5件
  overlap_messages = messages[-KB_ARCHIVE_OVERLAP_MESSAGES:]
  ```

- **楽観的ロック**:

  ```python
  # tenacityによる自動リトライ（指数バックオフ付き、最大3回）
  @retry(
      stop=stop_after_attempt(3),
      wait=wait_exponential(multiplier=1, min=1, max=10),
      retry=retry_if_exception_type(ValueError),
  )
  async def _archive_session_with_retry():
      # versionカラムを使用した楽観的ロック
      result = await conn.execute("""
          UPDATE sessions
          SET status = 'archived',
              messages = $3::jsonb,
              version = version + 1
          WHERE session_key = $1
          AND version = $2  -- 楽観的ロックチェック
      """, session_key, original_version, overlap_messages)
      
      if result == "UPDATE 0":
          raise ValueError("Session was concurrently updated")
  ```

- **メッセージ単位でのチャンク化**:

  ```python
  # 環境変数からチャンク化戦略を選択
  chunk_strategy = os.getenv("KB_CHAT_CHUNK_STRATEGY", "message_based")
  
  if chunk_strategy == "message_based":
      # メッセージ単位/会話ターン単位でのチャンク化（推奨）
      chunks = self._chunk_messages_by_turns(
          messages_to_archive, MAX_EMBEDDING_TOKENS, encoding)
  ```

- **トランザクション分離レベル**:

  ```python
  # REPEATABLE READ に設定（楽観的ロックのため）
  async with conn.transaction(isolation='repeatable_read'):
      # 1. knowledge_sources に登録
      # 2. knowledge_chunks に登録
      # 3. sessions の status を 'archived' に更新
  ```

**完了基準**:

- [ ] `SessionArchiver`クラスが実装されている
- [ ] 非アクティブなセッションが自動的に知識ベースに変換される
- [ ] スライディングウィンドウ（のりしろ）方式が実装されている
- [ ] 楽観的ロックによる競合状態対策が実装されている
- [ ] トランザクション分離レベルが `REPEATABLE READ` に設定されている
- [ ] メッセージ単位でのチャンク化が実装されている
- [ ] フィルタリングロジック（短いセッション、Botのみのセッション除外）が実装されている
- [ ] Graceful Shutdownが実装されている

---

### 5.4 依存性注入パターンの採用

**作業内容**:

1. **`src/kotonoha_bot/main.py`** の更新
   - `PostgreSQLDatabase`の初期化
   - `OpenAIEmbeddingProvider`の初期化
   - `EmbeddingProcessor`の初期化
   - `SessionArchiver`の初期化
   - バックグラウンドタスクの開始
   - Graceful Shutdownの実装

2. **`src/kotonoha_bot/bot/handlers.py`** の更新
   - 依存性注入パターンの採用（`kb_storage`, `embedding_processor`, `session_archiver`）
   - `cog_unload`メソッドでのGraceful Shutdown

**完了基準**:

- [ ] `main.py`で依存性注入が実装されている
- [ ] バックグラウンドタスクが開始される
- [ ] Graceful Shutdownが実装されている

---

## 🧪 Step 7: テストと最適化（1-2日）

### 7.1 PostgreSQL用テストフィクスチャ

**作業内容**:

1. **`tests/conftest.py`** の更新
   - `postgres_db`フィクスチャの追加
   - `postgres_db_with_rollback`フィクスチャの追加（ロールバックパターン）
   - `mock_embedding_provider`フィクスチャの追加
   - pytest-dockerを使用したPostgreSQLコンテナの自動起動

2. **テストケースの作成**
   - `PostgreSQLDatabase`のテスト
   - `EmbeddingProcessor`のテスト
   - `SessionArchiver`のテスト
   - ベクトル検索のテスト

**完了基準**:

- [ ] PostgreSQL用のテストフィクスチャが追加されている
- [ ] すべてのテストが通過する（既存の137テストケース + 新規テスト）
- [ ] 既存の機能が正常に動作する（回帰テスト）
- [ ] OpenAI APIのモックが実装されている（CI/CD対応）

---

### 7.2 パフォーマンステストと最適化

**作業内容**:

1. **パフォーマンステストの実施**
   - ベクトル検索の性能測定
   - HNSWインデックスの効果確認
   - 接続プールの調整

2. **最適化**
   - インデックスの最適化（HNSWパラメータの調整）
   - 接続プールの調整（`min_size`, `max_size`）

**完了基準**:

- [ ] パフォーマンステストが実施されている
- [ ] インデックスの最適化が完了している
- [ ] 接続プールの調整が完了している

---

## 📝 実装時の注意事項

### 重要な実装ポイント

1. **halfvec固定採用**
   - すべてのSQLで `::halfvec(1536)` と明示的にキャスト
   - `constants.py`の`SearchConstants.VECTOR_CAST`を使用

2. **トランザクション内でのAPIコールを回避**
   - Tx1: FOR UPDATE SKIP LOCKED で対象行を取得し、即コミット
   - No Tx: OpenAI API コール（時間かかる処理、トランザクション外）
   - Tx2: 結果を UPDATE（別トランザクション）

3. **セマフォによる同時実行数制限**
   - DB_POOL_MAX_SIZEの20〜30%程度に制限
   - 接続プール枯渇対策

4. **楽観的ロック**
   - `version`カラムを使用
   - tenacityによる自動リトライ（指数バックオフ付き）

5. **Graceful Shutdown**
   - 処理中のタスクが完了するまで待機
   - タイムアウト処理

---

## 🎯 完了基準チェックリスト

### Step 5: Embedding処理

- [ ] `EmbeddingProvider`インターフェースが定義されている
- [ ] `OpenAIEmbeddingProvider`が実装されている
- [ ] Embedding APIのリトライロジックが実装されている
- [ ] `EmbeddingProcessor`クラスが実装されている
- [ ] バックグラウンドタスクが動作する
- [ ] `FOR UPDATE SKIP LOCKED`パターンが実装されている
- [ ] トランザクション内でのAPIコールを回避している
- [ ] セマフォによる同時実行数制限が実装されている
- [ ] DLQへの移動ロジックが実装されている
- [ ] `SessionArchiver`クラスが実装されている
- [ ] スライディングウィンドウ（のりしろ）方式が実装されている
- [ ] 楽観的ロックによる競合状態対策が実装されている
- [ ] メッセージ単位でのチャンク化が実装されている
- [ ] Graceful Shutdownが実装されている

### Step 7: テストと最適化

- [ ] PostgreSQL用のテストフィクスチャが追加されている
- [ ] すべてのテストが通過する
- [ ] 既存の機能が正常に動作する（回帰テスト）
- [ ] パフォーマンステストが実施されている
- [ ] インデックスの最適化が完了している
- [ ] 接続プールの調整が完了している

---

## ✅ 動作確認方法

### 前提条件

1. **環境変数の設定**
   - `.env`ファイルを作成（`.env.example`を参考に）
   - 必要な環境変数:
     - `DISCORD_TOKEN`: Discord Botのトークン
     - `DATABASE_URL`: PostgreSQL接続文字列（または個別の`POSTGRES_*`環境変数）
     - `POSTGRES_PASSWORD`: PostgreSQLのパスワード（強固なパスワードを推奨）
     - `OPENAI_API_KEY`: OpenAI APIキー（Embedding処理用）

2. **Docker Composeの準備**
   - `docker-compose.yml`が正しく設定されていることを確認

---

### 1. PostgreSQLコンテナの起動確認

```bash
# PostgreSQLコンテナを起動
docker compose up -d postgres

# コンテナの状態を確認
docker compose ps

# PostgreSQLのログを確認（エラーがないか確認）
docker compose logs postgres

# PostgreSQLに接続して動作確認
docker compose exec postgres psql -U kotonoha -d kotonoha -c "SELECT version();"
```

**確認項目**:

- [ ] PostgreSQLコンテナが正常に起動している（STATUS: healthy）
- [ ] ログにエラーが表示されていない
- [ ] PostgreSQLに接続できる

---

### 2. データベース接続とAlembicマイグレーションの確認

```bash
# Botコンテナを起動（PostgreSQLが起動している必要がある）
docker compose up -d kotonoha-bot

# Botのログを確認（Alembicマイグレーションが自動実行される）
docker compose logs -f kotonoha-bot
```

**確認項目**:

- [ ] Botが正常に起動している
- [ ] Alembicマイグレーションが自動実行されている（ログに "Running upgrade" が表示される）
- [ ] データベース接続エラーが発生していない

**手動でマイグレーションを確認する場合**:

```bash
# Alembicの現在のバージョンを確認
docker compose exec kotonoha-bot uv run alembic current

# マイグレーション履歴を確認
docker compose exec kotonoha-bot uv run alembic history

# テーブルが作成されているか確認
docker compose exec postgres psql -U kotonoha -d kotonoha -c "\dt"
```

**期待されるテーブル**:

- `sessions`
- `knowledge_sources`
- `knowledge_chunks`
- `knowledge_chunks_dlq`

---

### 3. pgvector拡張の確認

```bash
# pgvector拡張が有効化されているか確認
docker compose exec postgres psql -U kotonoha -d kotonoha -c "SELECT * FROM pg_extension WHERE extname = 'vector';"

# pgvectorのバージョンを確認
docker compose exec postgres psql -U kotonoha -d kotonoha -c "SELECT extversion FROM pg_extension WHERE extname = 'vector';"

# halfvec型が使用可能か確認
docker compose exec postgres psql -U kotonoha -d kotonoha -c "SELECT '[1,2,3]'::halfvec(3);"
```

**確認項目**:

- [ ] pgvector拡張が有効化されている
- [ ] halfvec型が使用可能

---

### 4. セッションの保存・読み込み確認

**Discord Bot経由での確認**:

1. DiscordサーバーでBotにメンションを送信
2. Botが応答することを確認
3. セッションが保存されているか確認

```bash
# セッションが保存されているか確認
docker compose exec postgres psql -U kotonoha -d kotonoha -c "SELECT session_key, session_type, status, created_at FROM sessions ORDER BY created_at DESC LIMIT 5;"

# メッセージが保存されているか確認
docker compose exec postgres psql -U kotonoha -d kotonoha -c "SELECT session_key, jsonb_array_length(messages) as message_count FROM sessions;"
```

**確認項目**:

- [ ] Botが正常に応答する
- [ ] セッションが`sessions`テーブルに保存されている
- [ ] メッセージが`messages`カラム（JSONB）に保存されている
- [ ] `guild_id`が正しく保存されている（Discord URL生成用）

---

### 5. 知識ベーススキーマの確認

```bash
# 知識ソースを手動で作成（テスト用）
docker compose exec postgres psql -U kotonoha -d kotonoha <<EOF
INSERT INTO knowledge_sources (type, title, uri, metadata, status)
VALUES ('discord_session', 'テストソース', 'https://example.com', '{"test": true}'::jsonb, 'pending')
RETURNING id, type, title, status;
EOF

# 知識チャンクを手動で作成（テスト用）
docker compose exec postgres psql -U kotonoha -d kotonoha <<EOF
INSERT INTO knowledge_chunks (source_id, content, location, token_count)
VALUES (1, 'これはテスト用のチャンクです', '{"url": "https://example.com", "label": "テスト"}'::jsonb, 10)
RETURNING id, source_id, content, token_count;
EOF

# 知識ソースとチャンクの関連を確認
docker compose exec postgres psql -U kotonoha -d kotonoha -c "
SELECT s.id as source_id, s.title, s.status, COUNT(c.id) as chunk_count
FROM knowledge_sources s
LEFT JOIN knowledge_chunks c ON s.id = c.source_id
GROUP BY s.id, s.title, s.status;
"
```

**確認項目**:

- [ ] 知識ソースが`knowledge_sources`テーブルに保存される
- [ ] 知識チャンクが`knowledge_chunks`テーブルに保存される
- [ ] 外部キー制約が正しく動作している（`source_id`の参照整合性）

---

### 6. ベクトル検索の確認（Step 3実装後）

**注意**: ベクトル検索をテストするには、`embedding`カラムにベクトルデータが必要です。
Step 5（Embedding処理）を実装するか、手動でテスト用のベクトルを挿入する必要があります。

```bash
# テスト用のベクトルを挿入（1536次元のダミーベクトル）
docker compose exec postgres psql -U kotonoha -d kotonoha <<EOF
-- テスト用のベクトル（すべて0.1の値）
UPDATE knowledge_chunks
SET embedding = (SELECT array_agg(0.1::real) FROM generate_series(1, 1536))::halfvec(1536)
WHERE id = 1;
EOF

# ベクトル検索のテスト（Pythonスクリプトで実行）
docker compose exec kotonoha-bot python3 <<EOF
import asyncio
from kotonoha_bot.db.postgres import PostgreSQLDatabase
from kotonoha_bot.config import settings

async def test_similarity_search():
    db = PostgreSQLDatabase(connection_string=settings.database_url)
    await db.initialize()
    
    # テスト用のクエリベクトル（すべて0.1の値）
    query_embedding = [0.1] * 1536
    
    # ベクトル検索を実行
    results = await db.similarity_search(
        query_embedding=query_embedding,
        top_k=5
    )
    
    print(f"検索結果数: {len(results)}")
    for result in results:
        print(f"  - chunk_id: {result['chunk_id']}, similarity: {result['similarity']}")
    
    await db.close()

asyncio.run(test_similarity_search())
EOF
```

**確認項目**:

- [ ] ベクトル検索が正常に動作する
- [ ] 検索結果が返ってくる
- [ ] `similarity`スコアが正しく計算されている

---

### 7. Embedding処理の確認（Step 5実装後）

```bash
# バックグラウンドタスクが動作しているか確認（ログ）
docker compose logs -f kotonoha-bot | grep -i "embedding"

# pending状態のチャンクを確認
docker compose exec postgres psql -U kotonoha -d kotonoha -c "
SELECT COUNT(*) as pending_count
FROM knowledge_chunks
WHERE embedding IS NULL AND retry_count < 3;
"

# 処理済みのチャンクを確認
docker compose exec postgres psql -U kotonoha -d kotonoha -c "
SELECT COUNT(*) as processed_count
FROM knowledge_chunks
WHERE embedding IS NOT NULL;
"

# バックグラウンドタスクの実行状況を確認（ログから）
# "Processing X pending chunks..." が表示されることを確認
```

**確認項目**:

- [ ] バックグラウンドタスクが定期的に実行されている（ログに "Processing pending chunks" が表示される）
- [ ] `embedding IS NULL`のチャンクが処理されている
- [ ] 処理後、`embedding`カラムにベクトルが保存されている
- [ ] エラーが発生した場合、`retry_count`がインクリメントされている
- [ ] `retry_count >= 3`のチャンクがDLQに移動されている

---

### 8. セッション知識化の確認（Step 5実装後）

```bash
# 非アクティブなセッションを確認
docker compose exec postgres psql -U kotonoha -d kotonoha -c "
SELECT session_key, status, last_active_at,
       NOW() - last_active_at as inactive_duration
FROM sessions
WHERE status = 'active'
ORDER BY last_active_at ASC
LIMIT 5;
"

# アーカイブ済みセッションを確認
docker compose exec postgres psql -U kotonoha -d kotonoha -c "
SELECT COUNT(*) as archived_count
FROM sessions
WHERE status = 'archived';
"

# 知識ベースに変換されたセッションを確認
docker compose exec postgres psql -U kotonoha -d kotonoha -c "
SELECT s.id, s.title, s.type, s.status,
       COUNT(c.id) as chunk_count
FROM knowledge_sources s
LEFT JOIN knowledge_chunks c ON s.id = c.source_id
WHERE s.type = 'discord_session'
GROUP BY s.id, s.title, s.type, s.status
ORDER BY s.id DESC
LIMIT 5;
"

# バックグラウンドタスクの実行状況を確認（ログ）
docker compose logs -f kotonoha-bot | grep -i "archiv"
```

**確認項目**:

- [ ] バックグラウンドタスクが定期的に実行されている（ログに "Archiving inactive sessions" が表示される）
- [ ] 非アクティブなセッション（`last_active_at < 1時間前`）が検索されている
- [ ] セッションが`knowledge_sources`と`knowledge_chunks`に変換されている
- [ ] セッションの`status`が`'archived'`に更新されている
- [ ] スライディングウィンドウ（のりしろ）が正しく動作している（`messages`カラムに直近の数メッセージが残っている）

---

### 9. エラーハンドリングの確認

```bash
# データベース接続エラーの確認
# PostgreSQLコンテナを停止して、Botのエラーハンドリングを確認
docker compose stop postgres
docker compose logs -f kotonoha-bot
# エラーメッセージが適切に表示されることを確認

# PostgreSQLコンテナを再起動
docker compose start postgres

# 接続プール枯渇の確認（大量のリクエストを送信してテスト）
# 注意: 本番環境では実施しないこと
```

**確認項目**:

- [ ] データベース接続エラーが適切にハンドリングされている
- [ ] エラーログが適切に出力されている
- [ ] Botがクラッシュせず、エラーから回復できる

---

### 10. パフォーマンス確認

```bash
# インデックスの使用状況を確認
docker compose exec postgres psql -U kotonoha -d kotonoha <<EOF
-- HNSWインデックスの使用状況
SELECT schemaname, tablename, indexname, idx_scan, idx_tup_read, idx_tup_fetch
FROM pg_stat_user_indexes
WHERE indexname LIKE '%embedding%'
ORDER BY idx_scan DESC;
EOF

# テーブルサイズを確認
docker compose exec postgres psql -U kotonoha -d kotonoha -c "
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
"

# 接続プールの使用状況を確認（Botのログから）
docker compose logs kotonoha-bot | grep -i "pool"
```

**確認項目**:

- [ ] HNSWインデックスが使用されている（`idx_scan > 0`）
- [ ] テーブルサイズが適切な範囲内
- [ ] 接続プールが適切に使用されている（エラーが発生していない）

---

### 11. pgAdminでの確認（オプション）

```bash
# pgAdminコンテナを起動
docker compose --profile admin up -d pgadmin

# pgAdminにアクセス
# ブラウザで http://localhost:5050 を開く
# ログイン情報:
#   Email: .envファイルのPGADMIN_EMAIL
#   Password: .envファイルのPGADMIN_PASSWORD
```

**pgAdminでの確認項目**:

- [ ] PostgreSQLサーバーに接続できる
- [ ] テーブルが正しく作成されている
- [ ] データが正しく保存されている
- [ ] インデックスが作成されている

---

## 📚 参考資料

- **実装計画書**: `docs/implementation/phases/phase08.md`
- **スキーマ設計書**: `docs/architecture/postgresql-schema-design.md`
- **実装例**: `docs/implementation/phases/phase08.md` の Step 5 セクション

---

**作成日**: 2026年1月19日  
**最終更新日**: 2026年1月19日
