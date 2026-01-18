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
docker compose exec postgres psql -U kotonoha -d kotonoha \
  -c "SELECT * FROM pg_extension WHERE extname = 'vector';"

# pgvectorのバージョンを確認
docker compose exec postgres psql -U kotonoha -d kotonoha \
  -c "SELECT extversion FROM pg_extension WHERE extname = 'vector';"

# halfvec型が使用可能か確認
docker compose exec postgres psql -U kotonoha -d kotonoha \
  -c "SELECT '[1,2,3]'::halfvec(3);"
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
docker compose exec postgres psql -U kotonoha -d kotonoha \
  -c "SELECT session_key, session_type, status, created_at \
      FROM sessions ORDER BY created_at DESC LIMIT 5;"

# メッセージが保存されているか確認
docker compose exec postgres psql -U kotonoha -d kotonoha \
  -c "SELECT session_key, jsonb_array_length(messages) as message_count \
      FROM sessions;"
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
docker compose exec -T postgres psql -U kotonoha -d kotonoha <<EOF
INSERT INTO knowledge_sources (type, title, uri, metadata, status)
VALUES (
  'discord_session',
  'テストソース',
  'https://example.com',
  '{"test": true}'::jsonb,
  'pending'
)
RETURNING id, type, title, status;
EOF

# 知識チャンクを手動で作成（テスト用）
docker compose exec -T postgres psql -U kotonoha -d kotonoha <<EOF
INSERT INTO knowledge_chunks (source_id, content, location, token_count)
VALUES (
  1,
  'これはテスト用のチャンクです',
  '{"url": "https://example.com", "label": "テスト"}'::jsonb,
  10
)
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
docker compose exec -T postgres psql -U kotonoha -d kotonoha <<EOF
-- テスト用のベクトル1（すべて0.1の値）
UPDATE knowledge_chunks
SET embedding = (
  SELECT array_agg(0.1::real) FROM generate_series(1, 1536)
)::halfvec(1536)
WHERE id = 1;

-- テスト用のベクトル2（交互に0.1と-0.1の値）を別のチャンクに追加
-- まず、テスト用のソースとチャンクが存在することを確認
-- （存在しない場合は手動で作成する必要があります）
EOF

# ベクトル検索のテスト（Pythonスクリプトで実行）
docker compose exec -T kotonoha-bot python3 <<EOF
import asyncio
import math
from kotonoha_bot.db.postgres import PostgreSQLDatabase
from kotonoha_bot.config import settings

async def test_similarity_search():
    db = PostgreSQLDatabase(connection_string=settings.database_url)
    await db.initialize()
    
    # 閾値を表示
    print(f"類似度閾値: {settings.kb_similarity_threshold}")
    print(f"デフォルトtop_k: {settings.kb_default_top_k}\n")
    
    # テスト1: 完全一致するベクトルで検索（すべて0.1の値）
    print("=== テスト1: 完全一致するベクトルで検索 ===")
    query_embedding = [0.1] * 1536
    
    results = await db.similarity_search(
        query_embedding=query_embedding,
        top_k=5
    )
    
    print(f"検索結果数: {len(results)}")
    for result in results:
        print(f"  - chunk_id: {result['chunk_id']}, "
              f"similarity: {result['similarity']:.6f}, "
              f"content: {result['content'][:50]}..., "
              f"source_type: {result['source_type']}")
    
    # テスト2: 異なる方向のベクトルで検索
    # 注意: すべて同じ値のベクトル（例: [0.2, 0.2, ...]）は
    # 正規化すると同じ方向になるため、コサイン類似度は1.0になります
    # より意味のあるテストのため、交互に異なる値を持つベクトルを使用
    print("\n=== テスト2: 異なる方向のベクトルで検索 ===")
    # 交互に0.1と-0.1の値を持つベクトル（直交に近い方向）
    query_embedding2 = [0.1 if i % 2 == 0 else -0.1 for i in range(1536)]
    
    results2 = await db.similarity_search(
        query_embedding=query_embedding2,
        top_k=5
    )
    
    print(f"検索結果数: {len(results2)}")
    if len(results2) == 0:
        print(
            f"  ⚠️  閾値({settings.kb_similarity_threshold})を下回るため"
            f"結果がありません"
        )
        print(
            f"  実際の類似度を確認するため、"
            f"閾値フィルタリングを無効化して再検索します..."
        )
        # 閾値フィルタリングを無効化して生の類似度スコアを取得
        results2_raw = await db.similarity_search(
            query_embedding=query_embedding2,
            top_k=5,
            apply_threshold=False  # 閾値フィルタリングを無効化
        )
        print(f"  閾値フィルタリングなしの場合の検索結果数: {len(results2_raw)}")
        if results2_raw:
            for result in results2_raw:
                print(f"    - chunk_id: {result['chunk_id']}, "
                      f"similarity: {result['similarity']:.6f}, "
                      f"content: {result['content'][:50]}..., "
                      f"source_type: {result['source_type']}")
                print(
                    f"    閾値との差: "
                    f"{result['similarity'] - "
                    f"settings.kb_similarity_threshold:.6f}"
                )
    else:
        for result in results2:
            print(f"  - chunk_id: {result['chunk_id']}, "
                  f"similarity: {result['similarity']:.6f}, "
                  f"content: {result['content'][:50]}..., "
                  f"source_type: {result['source_type']}")
    
    # テスト3: ランダムなベクトルで検索（実際の使用に近い）
    print("\n=== テスト3: ランダムなベクトルで検索 ===")
    import random
    random.seed(42)  # 再現性のため
    query_embedding3 = [random.gauss(0, 0.1) for _ in range(1536)]
    
    results3 = await db.similarity_search(
        query_embedding=query_embedding3,
        top_k=5
    )
    
    print(f"検索結果数: {len(results3)}")
    if len(results3) == 0:
        print(
            f"  ⚠️  閾値({settings.kb_similarity_threshold})を下回るため"
            f"結果がありません"
        )
        print(
            f"  実際の類似度を確認するため、"
            f"閾値フィルタリングを無効化して再検索します..."
        )
        # 閾値フィルタリングを無効化して生の類似度スコアを取得
        results3_raw = await db.similarity_search(
            query_embedding=query_embedding3,
            top_k=5,
            apply_threshold=False  # 閾値フィルタリングを無効化
        )
        print(f"  閾値フィルタリングなしの場合の検索結果数: {len(results3_raw)}")
        if results3_raw:
            for result in results3_raw:
                print(f"    - chunk_id: {result['chunk_id']}, "
                      f"similarity: {result['similarity']:.6f}, "
                      f"content: {result['content'][:50]}..., "
                      f"source_type: {result['source_type']}")
                print(
                    f"    閾値との差: "
                    f"{result['similarity'] - "
                    f"settings.kb_similarity_threshold:.6f}"
                )
    else:
        for result in results3:
            print(f"  - chunk_id: {result['chunk_id']}, "
                  f"similarity: {result['similarity']:.6f}, "
                  f"content: {result['content'][:50]}..., "
                  f"source_type: {result['source_type']}")
    
    await db.close()

asyncio.run(test_similarity_search())
EOF
```

**確認項目**:

- [ ] ベクトル検索が正常に動作する
- [ ] 検索結果が返ってくる
- [ ] `similarity`スコアが正しく計算されている

**注意事項**:

- コサイン類似度はベクトルの**方向**を比較するため、
  すべて同じ値のベクトル（例: `[0.1, 0.1, ..., 0.1]` と
  `[0.2, 0.2, ..., 0.2]`）は正規化すると同じ方向になるため、
  類似度は1.0になります
- より意味のあるテストを行うには、
  異なる方向のベクトル（例: 交互に異なる値を持つベクトル）を使用してください
- テスト2では、交互に0.1と-0.1の値を持つベクトルを使用しており、
  これは元のベクトル（すべて0.1）と直交に近い方向になるため、
  類似度は低くなります

#### 閾値フィルタリングの制御

`similarity_search`メソッドでは、`apply_threshold`パラメータを使用して閾値フィルタリングを制御できます。

##### 基本的な使い方

```python
# デフォルト: 閾値フィルタリングあり（設定値の閾値を使用）
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
```

##### 使用例: 閾値を下回る結果も確認したい場合

```python
# 閾値フィルタリングあり（デフォルト）
results_with_threshold = await db.similarity_search(
    query_embedding=query_embedding,
    top_k=5,
    apply_threshold=True
)

if len(results_with_threshold) == 0:
    print("閾値を下回るため結果がありません")
    # 生の類似度スコアを確認
    results_raw = await db.similarity_search(
        query_embedding=query_embedding,
        top_k=5,
        apply_threshold=False  # 閾値フィルタリングを無効化
    )
    print(f"生の類似度スコア: {[r['similarity'] for r in results_raw]}")
```

**パラメータ説明**:

- `similarity_threshold` (float | None): 類似度閾値。
  `None`の場合は設定値（`KB_SIMILARITY_THRESHOLD`、デフォルト0.7）を使用
- `apply_threshold` (bool): 閾値フィルタリングを適用するか。
  `False`の場合は閾値フィルタリングを無効化し、
  生の類似度スコアを返す（デフォルト: `True`）

**用途**:

- **デバッグ**: 閾値でフィルタリングされる前の生の類似度スコアを確認
- **分析**: 類似度分布の調査や閾値の最適化
- **柔軟な検索**: 用途に応じて閾値を動的に調整

---

### 7. Embedding処理の確認（Step 5実装後）

#### 7.1 バックグラウンドタスクの起動確認

```bash
# Botの起動ログを確認（EmbeddingProcessorが初期化されているか）
docker compose logs kotonoha-bot | grep -i "embedding\|processor"

# バックグラウンドタスクが開始されているか確認
docker compose logs kotonoha-bot | grep -i "embedding.*start\|processor.*start"
```

**確認項目**:

- [ ] Bot起動時にEmbeddingProcessorが初期化されている
  （ログに "EmbeddingProcessor initialized" などが表示される）
- [ ] バックグラウンドタスクが開始されている
  （ログに "Starting embedding processing task" などが表示される）

#### 7.2 テスト用チャンクの作成

```bash
# テスト用の知識ソースとチャンクを作成
docker compose exec -T postgres psql -U kotonoha -d kotonoha <<EOF
-- テスト用の知識ソースを作成
INSERT INTO knowledge_sources (type, title, uri, metadata, status)
VALUES (
  'document_file',
  'Embedding処理テスト',
  'https://example.com/test',
  '{"test": true}'::jsonb,
  'pending'
)
RETURNING id, type, title, status;

-- テスト用のチャンクを作成（embedding IS NULLの状態）
INSERT INTO knowledge_chunks (
  source_id, content, location, token_count, embedding, retry_count
)
VALUES 
  ((SELECT id FROM knowledge_sources WHERE title = 'Embedding処理テスト'), 
   'これはEmbedding処理のテスト用チャンクです。', 
   '{"url": "https://example.com/test", "label": "テストチャンク1"}'::jsonb, 
   10, NULL, 0),
  ((SELECT id FROM knowledge_sources WHERE title = 'Embedding処理テスト'), 
   'もう一つのテスト用チャンクです。', 
   '{"url": "https://example.com/test", "label": "テストチャンク2"}'::jsonb, 
   8, NULL, 0)
RETURNING
  id,
  source_id,
  content,
  token_count,
  embedding IS NULL as has_null_embedding;
EOF
```

**確認項目**:

- [ ] テスト用の知識ソースが作成されている
- [ ] テスト用のチャンクが作成されている（`embedding IS NULL`）

#### 7.3 Embedding処理の実行確認

```bash
# バックグラウンドタスクが動作しているか確認（ログをリアルタイムで監視）
docker compose logs -f kotonoha-bot | grep -i "embedding\|processing.*chunk"

# 別のターミナルで、pending状態のチャンクを確認
docker compose exec postgres psql -U kotonoha -d kotonoha -c "
SELECT 
    id, 
    source_id, 
    LEFT(content, 50) as content_preview,
    token_count,
    embedding IS NULL as has_null_embedding,
    retry_count,
    created_at
FROM knowledge_chunks
WHERE embedding IS NULL AND retry_count < 3
ORDER BY created_at ASC
LIMIT 10;
"
```

**確認項目**:

- [ ] ログに "Processing pending chunks..." が表示される（定期的に実行される）
- [ ] ログに "Successfully processed X chunks" が表示される
- [ ] `embedding IS NULL`のチャンクが処理されている

#### 7.4 Embedding処理結果の確認

```bash
# 処理済みのチャンクを確認（embeddingが設定されているか）
docker compose exec postgres psql -U kotonoha -d kotonoha -c "
SELECT 
    id, 
    source_id, 
    LEFT(content, 50) as content_preview,
    token_count,
    embedding IS NOT NULL as has_embedding,
    retry_count,
    created_at
FROM knowledge_chunks
WHERE source_id = (
  SELECT id FROM knowledge_sources WHERE title = 'Embedding処理テスト'
)
ORDER BY id;
"

# embeddingの次元数を確認（1536次元であることを確認）
docker compose exec postgres psql -U kotonoha -d kotonoha -c "
SELECT 
    id,
    pg_typeof(embedding) as embedding_type,
    vector_dims(embedding) as embedding_dimension
FROM knowledge_chunks
WHERE embedding IS NOT NULL
LIMIT 1;
"
```

**確認項目**:

- [ ] 処理後、`embedding`カラムにベクトルが保存されている（`embedding IS NOT NULL`）
- [ ] embeddingの型が`halfvec`である
- [ ] embeddingの次元数が1536である

#### 7.5 リトライロジックの確認

```bash
# エラーが発生した場合のretry_countの確認
docker compose exec postgres psql -U kotonoha -d kotonoha -c "
SELECT 
    id,
    source_id,
    retry_count,
    embedding IS NULL as has_null_embedding,
    created_at
FROM knowledge_chunks
WHERE retry_count > 0
ORDER BY retry_count DESC, created_at DESC
LIMIT 10;
"
```

**確認項目**:

- [ ] エラーが発生した場合、`retry_count`がインクリメントされている
- [ ] `retry_count < 3`のチャンクは再処理の対象になっている

#### 7.6 Dead Letter Queue（DLQ）の確認

```bash
# DLQに移動されたチャンクを確認
docker compose exec postgres psql -U kotonoha -d kotonoha -c "
SELECT 
    dlq.original_chunk_id,
    dlq.source_id,
    s.type as source_type,
    dlq.source_title,
    LEFT(dlq.content, 50) as content_preview,
    dlq.error_code,
    dlq.error_message,
    dlq.retry_count,
    dlq.last_retry_at
FROM knowledge_chunks_dlq dlq
LEFT JOIN knowledge_sources s ON dlq.source_id = s.id
ORDER BY dlq.last_retry_at DESC
LIMIT 10;
"

# DLQに移動されたチャンクが元のテーブルから削除されているか確認
docker compose exec postgres psql -U kotonoha -d kotonoha -c "
SELECT 
    dlq.original_chunk_id,
    CASE 
        WHEN chunks.id IS NULL THEN '削除済み（正常）'
        ELSE '削除されていない（エラー）'
    END as status
FROM knowledge_chunks_dlq dlq
LEFT JOIN knowledge_chunks chunks ON dlq.original_chunk_id = chunks.id
LIMIT 10;
"
```

**確認項目**:

- [ ] `retry_count >= 3`のチャンクがDLQに移動されている
- [ ] DLQに移動されたチャンクが元の`knowledge_chunks`テーブルから削除されている
- [ ] エラーコードとエラーメッセージが適切に記録されている

#### 7.7 Sourceステータスの更新確認

```bash
# Sourceのステータスが正しく更新されているか確認
docker compose exec postgres psql -U kotonoha -d kotonoha -c "
SELECT 
    s.id,
    s.title,
    s.status,
    COUNT(
      CASE WHEN c.embedding IS NULL AND c.retry_count < 3 THEN 1 END
    ) as pending_chunks,
    COUNT(CASE WHEN c.embedding IS NOT NULL THEN 1 END) as processed_chunks,
    COUNT(CASE WHEN c.retry_count >= 3 THEN 1 END) as failed_chunks,
    (
      SELECT COUNT(*) FROM knowledge_chunks_dlq WHERE source_id = s.id
    ) as dlq_chunks
FROM knowledge_sources s
LEFT JOIN knowledge_chunks c ON s.id = c.source_id
GROUP BY s.id, s.title, s.status
ORDER BY s.id DESC
LIMIT 10;
"
```

**確認項目**:

- [ ] すべてのチャンクが処理された場合、Sourceのステータスが`'completed'`になっている
- [ ] DLQに移動されたチャンクがある場合、Sourceのステータスが`'partial'`になっている
- [ ] 処理中のチャンクがある場合、Sourceのステータスが`'pending'`のままになっている

#### 7.8 バッチ処理の確認

```bash
# バッチサイズの確認（環境変数から読み込まれているか）
docker compose exec kotonoha-bot env | grep -i "KB_EMBEDDING"

# 同時実行数の確認（セマフォの制限が正しく設定されているか）
docker compose logs kotonoha-bot | grep -i "semaphore\|concurrent"
```

**確認項目**:

- [ ] バッチサイズが環境変数から正しく読み込まれている
- [ ] 同時実行数がDB_POOL_MAX_SIZEの20〜30%程度に制限されている

---

### 8. セッション知識化の確認（Step 5実装後）

#### 8.1 バックグラウンドタスクの起動確認

```bash
# Botの起動ログを確認（SessionArchiverが初期化されているか）
docker compose logs kotonoha-bot | grep -i "archiver\|session.*archive"

# バックグラウンドタスクが開始されているか確認
docker compose logs kotonoha-bot | grep -i "archive.*start\|archiver.*start"
```

**確認項目**:

- [ ] Bot起動時にSessionArchiverが初期化されている
- [ ] バックグラウンドタスクが開始されている（ログに "Starting session archiving task" などが表示される）

#### 8.2 テスト用セッションの作成

```bash
# テスト用のセッションを作成（非アクティブなセッションをシミュレート）
docker compose exec -T postgres psql -U kotonoha -d kotonoha <<EOF
-- テスト用のセッションを作成（1時間以上非アクティブ）
INSERT INTO sessions (
    session_key, 
    session_type, 
    messages, 
    status, 
    guild_id, 
    channel_id, 
    user_id, 
    last_active_at,
    version,
    last_archived_message_index
)
VALUES (
    'test:session:archiver:001',
    'mention',
    '[
        {
          "role": "user",
          "content": "これはテスト用のセッションです。",
          "timestamp": "2026-01-19T10:00:00Z"
        },
        {
          "role": "assistant",
          "content": "了解しました。テスト用のセッションですね。",
          "timestamp": "2026-01-19T10:00:05Z"
        },
        {
          "role": "user",
          "content": "アーカイブ処理をテストします。",
          "timestamp": "2026-01-19T10:00:10Z"
        },
        {
          "role": "assistant",
          "content": "アーカイブ処理のテストですね。",
          "timestamp": "2026-01-19T10:00:15Z"
        }
    ]'::jsonb,
    'active',
    123456789,
    987654321,
    111222333,
    NOW() - INTERVAL '2 hours',  -- 2時間前（アーカイブ対象）
    1,
    0
)
RETURNING
  session_key,
  session_type,
  status,
  last_active_at,
  jsonb_array_length(messages) as message_count;
EOF
```

**確認項目**:

- [ ] テスト用のセッションが作成されている
- [ ] セッションの`last_active_at`が1時間以上前になっている
- [ ] セッションの`status`が`'active'`になっている

#### 8.3 アーカイブ処理の実行確認

```bash
# バックグラウンドタスクが動作しているか確認（ログをリアルタイムで監視）
docker compose logs -f kotonoha-bot | grep -i "archiv\|inactive.*session"

# 別のターミナルで、非アクティブなセッションを確認
docker compose exec postgres psql -U kotonoha -d kotonoha -c "
SELECT 
    session_key, 
    session_type, 
    status, 
    last_active_at,
    NOW() - last_active_at as inactive_duration,
    jsonb_array_length(messages) as message_count,
    version,
    last_archived_message_index
FROM sessions
WHERE status = 'active'
AND last_active_at < NOW() - INTERVAL '1 hour'
ORDER BY last_active_at ASC
LIMIT 10;
"
```

**確認項目**:

- [ ] ログに "Archiving inactive sessions..." が表示される（定期的に実行される）
- [ ] ログに "Archived session X as knowledge source Y" が表示される
- [ ] 非アクティブなセッション（`last_active_at < 1時間前`）が検索されている

#### 8.4 アーカイブ結果の確認

```bash
# セッションのステータスが更新されているか確認
docker compose exec postgres psql -U kotonoha -d kotonoha -c "
SELECT 
    session_key,
    status,
    jsonb_array_length(messages) as remaining_message_count,
    last_archived_message_index,
    version
FROM sessions
WHERE session_key = 'test:session:archiver:001';
"

# 知識ベースに変換されたセッションを確認
docker compose exec postgres psql -U kotonoha -d kotonoha -c "
SELECT 
    s.id,
    s.title,
    s.type,
    s.status,
    s.uri,
    s.metadata->>'origin_session_key' as origin_session_key,
    COUNT(c.id) as chunk_count
FROM knowledge_sources s
LEFT JOIN knowledge_chunks c ON s.id = c.source_id
WHERE s.type = 'discord_session'
AND s.metadata->>'origin_session_key' = 'test:session:archiver:001'
GROUP BY s.id, s.title, s.type, s.status, s.uri, s.metadata
ORDER BY s.id DESC;
"
```

**確認項目**:

- [ ] セッションの`status`が`'archived'`に更新されている
- [ ] セッションが`knowledge_sources`テーブルに登録されている
- [ ] セッションが`knowledge_chunks`テーブルにチャンクとして登録されている
- [ ] `metadata`に`origin_session_key`が記録されている

#### 8.5 スライディングウィンドウ（のりしろ）の確認

```bash
# アーカイブ後のセッションのmessagesカラムを確認（のりしろが残っているか）
docker compose exec postgres psql -U kotonoha -d kotonoha -c "
SELECT 
    session_key,
    status,
    jsonb_array_length(messages) as remaining_message_count,
    messages as remaining_messages
FROM sessions
WHERE session_key = 'test:session:archiver:001';
"

# 知識ベースに登録されたチャンクの内容を確認
docker compose exec postgres psql -U kotonoha -d kotonoha -c "
SELECT 
    c.id,
    c.source_id,
    LEFT(c.content, 100) as content_preview,
    c.location->>'label' as chunk_label,
    c.token_count
FROM knowledge_chunks c
JOIN knowledge_sources s ON c.source_id = s.id
WHERE s.metadata->>'origin_session_key' = 'test:session:archiver:001'
ORDER BY c.id;
"
```

**確認項目**:

- [ ] アーカイブ後、`messages`カラムに直近の数メッセージ（のりしろ）が残っている
- [ ] のりしろの件数が環境変数`KB_ARCHIVE_OVERLAP_MESSAGES`（デフォルト: 5件）と一致している
- [ ] 知識ベースに登録されたチャンクに、アーカイブされたメッセージの内容が含まれている

#### 8.6 楽観的ロックの確認

```bash
# 楽観的ロックが正しく動作しているか確認（versionカラムの更新）
docker compose exec postgres psql -U kotonoha -d kotonoha -c "
SELECT 
    session_key,
    status,
    version,
    last_archived_message_index,
    last_active_at,
    created_at
FROM sessions
WHERE session_key = 'test:session:archiver:001';
"
```

**確認項目**:

- [ ] アーカイブ後、`version`カラムがインクリメントされている
- [ ] `last_archived_message_index`が正しく更新されている

#### 8.7 チャンク化戦略の確認

```bash
# チャンク化戦略が正しく適用されているか確認
docker compose exec kotonoha-bot env | grep -i "KB_CHAT_CHUNK"

# チャンクの内容とトークン数を確認
docker compose exec postgres psql -U kotonoha -d kotonoha -c "
SELECT 
    c.id,
    c.source_id,
    LEFT(c.content, 200) as content_preview,
    c.token_count,
    c.location->>'chunk_index' as chunk_index,
    c.location->>'total_chunks' as total_chunks
FROM knowledge_chunks c
JOIN knowledge_sources s ON c.source_id = s.id
WHERE s.metadata->>'origin_session_key' = 'test:session:archiver:001'
ORDER BY (c.location->>'chunk_index')::int;
"
```

**確認項目**:

- [ ] チャンク化戦略が環境変数から正しく読み込まれている（`KB_CHAT_CHUNK_STRATEGY`）
- [ ] メッセージ単位でのチャンク化が適用されている（`message_based`の場合）
- [ ] 各チャンクのトークン数が`KB_CHUNK_MAX_TOKENS`（デフォルト: 4000）以下になっている

#### 8.8 フィルタリングロジックの確認

```bash
# 短いセッションやBotのみのセッションが除外されているか確認
docker compose exec -T postgres psql -U kotonoha -d kotonoha <<EOF
-- 短いセッション（フィルタリング対象）を作成
INSERT INTO sessions (
    session_key, 
    session_type, 
    messages, 
    status, 
    last_active_at,
    version
)
VALUES (
    'test:session:short:001',
    'mention',
    '[{"role": "user", "content": "短い", '
    '"timestamp": "2026-01-19T10:00:00Z"}]'::jsonb,
    'active',
    NOW() - INTERVAL '2 hours',
    1
);

-- Botのみのセッション（フィルタリング対象）を作成
INSERT INTO sessions (
    session_key, 
    session_type, 
    messages, 
    status, 
    last_active_at,
    version
)
VALUES (
    'test:session:bot_only:001',
    'mention',
    '[
        {
          "role": "assistant",
          "content": "Botのみのセッション",
          "timestamp": "2026-01-19T10:00:00Z"
        }
    ]'::jsonb,
    'active',
    NOW() - INTERVAL '2 hours',
    1
);
EOF

# アーカイブ処理実行後、これらのセッションが除外されているか確認
docker compose exec postgres psql -U kotonoha -d kotonoha -c "
SELECT 
    session_key,
    status,
    jsonb_array_length(messages) as message_count,
    last_active_at
FROM sessions
WHERE session_key IN ('test:session:short:001', 'test:session:bot_only:001');
"
```

**確認項目**:

- [ ] 短いセッション（`KB_MIN_SESSION_LENGTH`未満）がアーカイブされず、`status='archived'`に更新されている
- [ ] Botのみのセッション（ユーザーメッセージがない）がアーカイブされず、`status='archived'`に更新されている
- [ ] これらのセッションは知識ベースに登録されていない

---

### 9. 依存性注入とバックグラウンドタスクの確認

#### 9.1 依存性注入の確認

```bash
# Botの起動ログを確認（依存性注入が正しく行われているか）
docker compose logs kotonoha-bot | \
  grep -i "initializ\|embedding.*provider\|session.*archiver"

# main.pyでの初期化ログを確認
docker compose logs kotonoha-bot | \
  grep -i "postgresql.*database\|openai.*embedding"
```

**確認項目**:

- [ ] `PostgreSQLDatabase`が初期化されている
- [ ] `OpenAIEmbeddingProvider`が初期化されている
- [ ] `EmbeddingProcessor`が初期化されている
- [ ] `SessionArchiver`が初期化されている

#### 9.2 バックグラウンドタスクの開始確認

```bash
# バックグラウンドタスクが開始されているか確認
docker compose logs kotonoha-bot | grep -i "start.*task\|task.*start"

# タスクの実行間隔を確認
docker compose exec kotonoha-bot env | \
  grep -i "KB_EMBEDDING_INTERVAL\|KB_ARCHIVE_INTERVAL"
```

**確認項目**:

- [ ] EmbeddingProcessorのバックグラウンドタスクが開始されている
- [ ] SessionArchiverのバックグラウンドタスクが開始されている
- [ ] タスクの実行間隔が環境変数から正しく読み込まれている

---

### 10. Graceful Shutdownの確認

#### 10.1 正常なシャットダウンの確認

```bash
# Botを停止（SIGTERMシグナルを送信）
docker compose stop kotonoha-bot

# シャットダウンログを確認
docker compose logs kotonoha-bot | tail -50 | \
  grep -i "shutdown\|graceful\|stopping"

# 処理中のタスクが完了するまで待機しているか確認
docker compose logs kotonoha-bot | grep -i "waiting.*task\|task.*complete"
```

**確認項目**:

- [ ] ログに "Starting graceful shutdown..." が表示される
- [ ] ログに "Stopping embedding processor gracefully..." が表示される
- [ ] ログに "Stopping session archiver gracefully..." が表示される
- [ ] 処理中のタスクが完了するまで待機している（タイムアウトエラーが発生していない）
- [ ] データベース接続が正しくクローズされている

#### 10.2 強制停止時の動作確認

```bash
# Botを強制停止（SIGKILL）
docker compose kill kotonoha-bot

# ログを確認（Graceful Shutdownが実行されなかった場合の動作）
docker compose logs kotonoha-bot | tail -20
```

**確認項目**:

- [ ] 強制停止時でも、可能な限りクリーンアップが実行されている
- [ ] データベース接続が適切に処理されている（接続リークが発生していない）

---

### 11. エラーハンドリングの確認

#### 11.1 データベース接続エラーの確認

```bash
# PostgreSQLコンテナを停止して、Botのエラーハンドリングを確認
docker compose stop postgres

# Botのログを確認（エラーハンドリングが正しく動作しているか）
docker compose logs -f kotonoha-bot

# エラーメッセージが適切に表示されることを確認
# 期待されるエラー: "Failed to acquire database connection" など

# PostgreSQLコンテナを再起動
docker compose start postgres

# Botが自動的に再接続するか確認
docker compose logs -f kotonoha-bot | grep -i "connect\|reconnect"
```

**確認項目**:

- [ ] データベース接続エラーが適切にハンドリングされている
- [ ] エラーログが適切に出力されている（スタックトレースが含まれている）
- [ ] Botがクラッシュせず、エラーから回復できる
- [ ] PostgreSQL再起動後、Botが自動的に再接続できる

#### 11.2 Embedding APIエラーの確認

```bash
# 無効なAPIキーを設定して、Embedding APIエラーをシミュレート
docker compose exec kotonoha-bot env | grep OPENAI_API_KEY

# エラーが発生した場合のログを確認
docker compose logs kotonoha-bot | grep -i "embedding.*error\|api.*error\|retry"

# retry_countがインクリメントされているか確認
docker compose exec postgres psql -U kotonoha -d kotonoha -c "
SELECT 
    id,
    source_id,
    retry_count,
    embedding IS NULL as has_null_embedding
FROM knowledge_chunks
WHERE retry_count > 0
ORDER BY retry_count DESC, created_at DESC
LIMIT 10;
"
```

**確認項目**:

- [ ] Embedding APIエラーが適切にハンドリングされている
- [ ] エラー発生時、`retry_count`がインクリメントされている
- [ ] リトライロジックが正しく動作している（tenacityによる自動リトライ）
- [ ] 最大リトライ回数に達した場合、DLQに移動されている

#### 11.3 接続プール枯渇の確認

```bash
# 接続プールの設定を確認
docker compose exec kotonoha-bot env | grep -i "DB_POOL"

# 接続プールの使用状況を確認（ログから）
docker compose logs kotonoha-bot | grep -i "pool.*exhaust\|connection.*timeout"

# 注意: 本番環境では実施しないこと
# 大量のリクエストを送信して、接続プール枯渇をシミュレート
```

**確認項目**:

- [ ] 接続プール枯渇時、適切なエラーメッセージが表示される
- [ ] タイムアウトが適切に設定されている
- [ ] セマフォによる同時実行数制限が機能している（接続プール枯渇を防いでいる）

---

### 12. 実際のDiscord Bot経由での動作確認

#### 12.1 セッション作成とメッセージ送信

1. **DiscordサーバーでBotにメンションを送信**
   - Botが応答することを確認
   - 複数のメッセージを送信して、会話履歴を構築

2. **セッションが保存されているか確認**

```bash
# セッションが保存されているか確認
docker compose exec postgres psql -U kotonoha -d kotonoha -c "
SELECT 
    session_key,
    session_type,
    status,
    guild_id,
    channel_id,
    user_id,
    jsonb_array_length(messages) as message_count,
    last_active_at
FROM sessions
WHERE status = 'active'
ORDER BY last_active_at DESC
LIMIT 5;
"
```

**確認項目**:

- [ ] Botが正常に応答する
- [ ] セッションが`sessions`テーブルに保存されている
- [ ] メッセージが`messages`カラム（JSONB）に保存されている
- [ ] `guild_id`が正しく保存されている（Discord URL生成用）

#### 12.2 セッションアーカイブの確認

1. **1時間以上待機**（または環境変数`KB_ARCHIVE_THRESHOLD_HOURS`を短く設定）

2. **アーカイブ処理が実行されるか確認**

```bash
# アーカイブ処理のログを確認
docker compose logs -f kotonoha-bot | grep -i "archiv"

# セッションのステータスが更新されているか確認
docker compose exec postgres psql -U kotonoha -d kotonoha -c "
SELECT 
    session_key,
    status,
    jsonb_array_length(messages) as remaining_message_count,
    last_archived_message_index
FROM sessions
WHERE session_key LIKE 'mention:%'
ORDER BY last_active_at DESC
LIMIT 5;
"
```

**確認項目**:

- [ ] 1時間以上非アクティブなセッションがアーカイブされている
- [ ] セッションが知識ベースに変換されている
- [ ] スライディングウィンドウ（のりしろ）が正しく動作している

#### 12.3 Embedding処理の確認

```bash
# アーカイブされたセッションのチャンクがEmbedding処理されているか確認
docker compose exec postgres psql -U kotonoha -d kotonoha -c "
SELECT 
    s.id as source_id,
    s.title,
    s.status as source_status,
    COUNT(CASE WHEN c.embedding IS NULL THEN 1 END) as pending_chunks,
    COUNT(CASE WHEN c.embedding IS NOT NULL THEN 1 END) as processed_chunks
FROM knowledge_sources s
LEFT JOIN knowledge_chunks c ON s.id = c.source_id
WHERE s.type = 'discord_session'
GROUP BY s.id, s.title, s.status
ORDER BY s.id DESC
LIMIT 10;
"
```

**確認項目**:

- [ ] アーカイブされたセッションのチャンクがEmbedding処理されている
- [ ] 処理後、`embedding`カラムにベクトルが保存されている

#### 12.4 ベクトル検索の確認

```bash
# ベクトル検索が動作するか確認（Pythonスクリプトで実行）
docker compose exec -T kotonoha-bot python3 <<EOF
import asyncio
from kotonoha_bot.db.postgres import PostgreSQLDatabase
from kotonoha_bot.config import settings

async def test_similarity_search():
    if settings.database_url:
        db = PostgreSQLDatabase(connection_string=settings.database_url)
    else:
        db = PostgreSQLDatabase(
            host=settings.postgres_host,
            port=settings.postgres_port,
            database=settings.postgres_db,
            user=settings.postgres_user,
            password=settings.postgres_password,
        )
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
        print(
            f"  - chunk_id: {result['chunk_id']}, "
            f"similarity: {result['similarity']:.4f}"
        )
    
    await db.close()

asyncio.run(test_similarity_search())
EOF
```

**確認項目**:

- [ ] ベクトル検索が正常に動作する
- [ ] 検索結果が返ってくる
- [ ] `similarity`スコアが正しく計算されている

---

### 13. パフォーマンス確認

```bash
# インデックスの使用状況を確認
docker compose exec -T postgres psql -U kotonoha -d kotonoha <<EOF
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

### 14. pgAdminでの確認（オプション）

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

---

## 🔍 トラブルシューティング

### よくある問題と解決方法

#### 問題1: EmbeddingProcessorのバックグラウンドタスクが起動しない

**症状**: ログに "Processing pending chunks" が表示されない

**確認方法**:

```bash
docker compose logs kotonoha-bot | grep -i "embedding.*processor\|task.*start"
```

**解決方法**:

1. 環境変数`KB_EMBEDDING_INTERVAL_MINUTES`が正しく設定されているか確認
2. Botの起動ログでエラーが発生していないか確認
3. `main.py`で`embedding_processor.start()`が呼ばれているか確認

#### 問題2: セッションがアーカイブされない

**症状**: 1時間以上非アクティブなセッションがアーカイブされない

**確認方法**:

```bash
docker compose exec postgres psql -U kotonoha -d kotonoha -c "
SELECT 
    session_key,
    status,
    last_active_at,
    NOW() - last_active_at as inactive_duration
FROM sessions
WHERE status = 'active'
AND last_active_at < NOW() - INTERVAL '1 hour';
"
```

**解決方法**:

1. 環境変数`KB_ARCHIVE_THRESHOLD_HOURS`が正しく設定されているか確認
2. `KB_ARCHIVE_INTERVAL_HOURS`が正しく設定されているか確認
3. Botのログでエラーが発生していないか確認

#### 問題3: Embedding処理が失敗する

**症状**: `retry_count`が増加し続ける、またはDLQに移動される

**確認方法**:

```bash
docker compose logs kotonoha-bot | grep -i "embedding.*error\|api.*error"
docker compose exec postgres psql -U kotonoha -d kotonoha -c "
SELECT 
    id,
    source_id,
    retry_count,
    embedding IS NULL as has_null_embedding
FROM knowledge_chunks
WHERE retry_count > 0
ORDER BY retry_count DESC
LIMIT 10;
"
```

**解決方法**:

1. `OPENAI_API_KEY`が正しく設定されているか確認
2. OpenAI APIのレート制限に達していないか確認
3. ネットワーク接続が正常か確認

#### 問題4: 楽観的ロックの競合が頻発する

**症状**: ログに "Session was concurrently updated" が頻繁に表示される

**確認方法**:

```bash
docker compose logs kotonoha-bot | \
  grep -i "concurrently.*updated\|optimistic.*lock"
```

**解決方法**:

1. `last_archived_message_index`を使用した差分アーカイブが正しく動作しているか確認
2. セッションの更新頻度が高すぎる場合は、アーカイブ間隔を調整
3. 並列処理の同時実行数を調整（`KB_ARCHIVE_BATCH_SIZE`を減らす）

#### 問題5: 接続プールが枯渇する

**症状**: ログに "Connection pool exhausted" が表示される

**確認方法**:

```bash
docker compose logs kotonoha-bot | grep -i "pool.*exhaust\|connection.*timeout"
docker compose exec kotonoha-bot env | grep -i "DB_POOL"
```

**解決方法**:

1. `DB_POOL_MAX_SIZE`を増やす
2. セマフォによる同時実行数制限を調整（`KB_EMBEDDING_MAX_CONCURRENT`を減らす）
3. バックグラウンドタスクの実行間隔を調整

---

**作成日**: 2026年1月19日  
**最終更新日**: 2026年1月19日（動作確認手順を詳細に加筆）
