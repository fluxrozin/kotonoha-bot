# Embedding処理の実装詳細

**作成日**: 2026年1月19日  
**対象プロジェクト**: kotonoha-bot v0.8.0

---

## 目次

1. [概要](#1-概要)
2. [Embeddingプロバイダーの実装](#2-embeddingプロバイダーの実装)
3. [EmbeddingProcessorの実装](#3-embeddingprocessorの実装)
4. [重要な実装ポイント](#4-重要な実装ポイント)
5. [依存性注入パターン](#5-依存性注入パターン)
6. [完了基準](#6-完了基準)

---

## 1. 概要

### 1.1 目的と意図

このドキュメントは、**Phase 8: PostgreSQL + pgvector 実装**において、
PostgreSQLの`knowledge_chunks`テーブルに保存されたテキストデータを
ベクトル化（Embedding化）し、pgvectorによる高速な類似度検索を実現するための
バックグラウンド処理システムの実装詳細を説明します。

#### PostgreSQLとの関係性

PostgreSQLの`knowledge_chunks`テーブルには、以下の構造でデータが保存されます：

```sql
CREATE TABLE knowledge_chunks (
    id BIGSERIAL PRIMARY KEY,
    source_id BIGINT REFERENCES knowledge_sources(id),
    content TEXT NOT NULL,              -- 検索対象のテキスト
    embedding halfvec(1536),           -- ベクトルデータ（NULL許容）
    -- ... その他のカラム
);
```

**重要なポイント**:

1. **`embedding`カラムはNULL許容**: テキストデータを先に保存し、
   後からバックグラウンドでベクトル化する設計です
2. **pgvectorによる検索**: `embedding IS NOT NULL`のレコードのみが
   HNSWインデックス（`idx_chunks_embedding`）を使用した高速検索の対象となります
3. **halfvec型の採用**: メモリ使用量を50%削減するため、
   `halfvec(1536)`型を固定採用しています

#### なぜバックグラウンド処理が必要なのか

1. **Botの応答速度維持**: Embedding生成（OpenAI API呼び出し）は
   数秒かかる処理のため、リアルタイムのチャット応答をブロックしないよう
   非同期処理として実装します
2. **PostgreSQL接続プールの保護**: Embedding処理が大量の接続を占有すると、
   通常のチャット応答がタイムアウトするリスクがあるため、
   セマフォによる同時実行数制限を実装します
3. **トランザクション分離**: PostgreSQLのトランザクション内で
   長時間のAPI呼び出しを行うと、ロックが長時間保持されパフォーマンスが
   劣化するため、`FOR UPDATE SKIP LOCKED`パターンとトランザクション分離を採用します

### 1.2 高速保存パターン

PostgreSQLへの書き込みを高速化し、Botの応答速度を維持するため、
以下の3段階のパターンを採用しています：

1. **即時保存**: テキストのみをPostgreSQLに保存（`embedding=NULL`）
   - セッションアーカイブやファイルアップロード時に即座に実行
   - PostgreSQLへの書き込みは高速（数ミリ秒）
2. **バックグラウンド処理**: 定期タスク（`EmbeddingProcessor`）で
   未処理のチャンクをバッチでベクトル化し、PostgreSQLの`embedding`カラムを更新
   - `FOR UPDATE SKIP LOCKED`パターンで複数ワーカーが安全に並列処理可能
3. **検索時**: `similarity_search`メソッドでは
   `embedding IS NOT NULL`条件を強制付与し、HNSWインデックスを使用した
   高速なベクトル検索を実現

### 1.3 主要なコンポーネント

- **EmbeddingProvider**: Embedding生成の抽象化インターフェース
  - 将来、OpenAI以外のプロバイダー（例：Hugging Face）への切り替えが容易
- **OpenAIEmbeddingProvider**: OpenAI API（text-embedding-3-small）を使用した実装
  - リトライロジック（`tenacity`）とバッチ処理による効率化
- **EmbeddingProcessor**: PostgreSQLの`knowledge_chunks`テーブルを監視し、
  バックグラウンドでEmbedding処理を実行するクラス
  - PostgreSQLの`FOR UPDATE SKIP LOCKED`パターンによる安全な並列処理
  - Dead Letter Queue（DLQ）への移動ロジックによるエラー処理

### 1.4 Dead Letter Queue（DLQ）とは

**DLQ（Dead Letter Queue）**は、メッセージキューシステムやバッチ処理システムで
よく使われる概念で、**処理に失敗したメッセージやタスクを保存する場所**です。

#### DLQの目的

このプロジェクトでは、Embedding処理が**最大リトライ回数（デフォルト: 3回）を超えて
失敗したチャンク**を`knowledge_chunks_dlq`テーブルに保存します。

**なぜDLQが必要なのか**:

1. **データ損失の防止**: 処理に失敗したチャンクを削除せずに保存することで、
   後から手動で確認・再処理が可能になります
2. **エラー分析**: エラーコード、エラーメッセージ、リトライ回数などの情報を
   保存することで、問題の原因を分析できます
3. **手動再処理**: 一時的なAPI障害やデータ品質の問題が解決した後、
   DLQに保存されたチャンクを手動で再処理できます

#### PostgreSQLでの実装

PostgreSQLの`knowledge_chunks_dlq`テーブルに以下の情報を保存します：

```sql
CREATE TABLE knowledge_chunks_dlq (
    id BIGSERIAL PRIMARY KEY,
    original_chunk_id BIGINT,        -- 元のチャンクID（参照用）
    source_id BIGINT,                -- 元のソースID
    source_type TEXT,                -- ソースタイプ（discord_session等）
    source_title TEXT,                -- ソースタイトル（デバッグ用）
    content TEXT NOT NULL,            -- 処理対象のテキスト
    error_code TEXT,                  -- エラーコード（例: 'EMBEDDING_API_TIMEOUT'）
    error_message TEXT,               -- 一般化されたエラーメッセージ
    retry_count INT DEFAULT 0,        -- リトライ回数
    created_at TIMESTAMPTZ,          -- DLQへの移動日時
    last_retry_at TIMESTAMPTZ         -- 最終リトライ日時
);
```

#### DLQへの移動タイミング

`EmbeddingProcessor`は、以下の条件を満たすチャンクをDLQに移動します：

1. **最大リトライ回数に達した**: `retry_count >= MAX_RETRY_COUNT`（デフォルト: 3回）
2. **Embedding API呼び出しが失敗**: OpenAI APIのエラー（レート制限、タイムアウト等）
3. **データベースエラー**: PostgreSQLへの書き込みエラー

DLQに移動されたチャンクは、元の`knowledge_chunks`テーブルから削除されます。
これにより、通常の処理フローに影響を与えず、失敗したチャンクのみを
別テーブルで管理できます。

### 1.5 Phase 8における位置づけ

このEmbedding処理システムは、Phase 8の以下の実装ステップと連携します：

- **Step 4: 知識ベーススキーマの実装**: `save_chunk`メソッドで
  `embedding=NULL`の状態でチャンクを保存
- **Step 5: Embedding処理の実装**（本ドキュメント）: バックグラウンドで
  ベクトル化してPostgreSQLを更新
- **Step 3: ベクトル検索機能の実装**: `similarity_search`メソッドで
  `embedding IS NOT NULL`のレコードを検索
- **Step 5.4: セッション知識化バッチ処理**: `SessionArchiver`が
  セッションを`knowledge_chunks`に変換し、Embedding処理の対象となる

---

## 2. Embeddingプロバイダーの実装

### 2.1 EmbeddingProviderインターフェース

```python
# src/kotonoha_bot/external/embedding/__init__.py
"""Embedding プロバイダー抽象化"""

from abc import ABC, abstractmethod

class EmbeddingProvider(ABC):
    """Embedding 生成プロバイダーのインターフェース"""
    
    @abstractmethod
    async def generate_embedding(self, text: str) -> list[float]:
        """テキストからベクトルを生成"""
        pass
    
    @abstractmethod
    async def generate_embeddings_batch(self, texts: list[str]) -> list[list[float]]:
        """複数のテキストをバッチでベクトル化"""
        pass
    
    @abstractmethod
    def get_dimension(self) -> int:
        """ベクトルの次元数を返す"""
        pass
```

### 2.2 OpenAIEmbeddingProviderの実装

```python
# src/kotonoha_bot/external/embedding/openai_embedding.py
"""OpenAI Embedding API プロバイダー"""

import os
import structlog
import openai
from typing import TYPE_CHECKING
from tenacity import (
    retry, stop_after_attempt, wait_exponential, retry_if_exception_type)

if TYPE_CHECKING:
    from . import EmbeddingProvider

logger = structlog.get_logger(__name__)

class OpenAIEmbeddingProvider(EmbeddingProvider):
    """OpenAI text-embedding-3-small を使用（リトライロジック付き）"""
    
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = "text-embedding-3-small"
        self.dimension = 1536
        self._client = openai.AsyncOpenAI(api_key=self.api_key)
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=60),
        retry=retry_if_exception_type(
            (openai.RateLimitError, openai.APITimeoutError)),
        reraise=True,
    )
    async def generate_embedding(self, text: str) -> list[float]:
        """テキストからベクトルを生成（リトライロジック付き）"""
        try:
            response = await self._client.embeddings.create(
                model=self.model,
                input=text,
                dimensions=self.dimension,
            )
            return response.data[0].embedding
        except openai.RateLimitError as e:
            logger.warning(f"Rate limit hit, retrying...: {e}")
            raise
        except openai.APITimeoutError as e:
            logger.warning(f"API timeout, retrying...: {e}")
            raise
        except openai.APIError as e:
            logger.error(f"OpenAI API error: {e}")
            raise
    
    async def generate_embeddings_batch(
        self, texts: list[str]
    ) -> list[list[float]]:
        """複数のテキストをバッチでベクトル化（API効率化）
        
        ⚠️ 改善: OpenAI Embedding APIはバッチリクエストをサポートしているため、
        個別にAPIを呼ぶのではなく、バッチで一度に送信することで効率化します。
        API呼び出し回数を大幅に削減（100回→1回）、レート制限にかかりにくくなります。
        """
        try:
            response = await self._client.embeddings.create(
                model=self.model,
                input=texts,  # リストを直接渡せる
                dimensions=self.dimension,
            )
            return [data.embedding for data in response.data]
        except openai.RateLimitError as e:
            logger.warning(f"Rate limit hit in batch embedding: {e}")
            raise
        except openai.APITimeoutError as e:
            logger.warning(f"API timeout in batch embedding: {e}")
            raise
        except openai.APIError as e:
            logger.error(f"OpenAI API error in batch embedding: {e}")
            raise
    
    def get_dimension(self) -> int:
        """ベクトルの次元数（1536）"""
        return self.dimension
```

### 2.3 完了基準

- [ ] `EmbeddingProvider`インターフェースが定義されている
- [ ] `OpenAIEmbeddingProvider`が実装されている
- [ ] Embedding APIのリトライロジックが実装されている（tenacity使用）
- [ ] バッチ処理メソッドが実装されている

---

## 3. EmbeddingProcessorの実装

### 3.1 クラス構造

```python
# src/kotonoha_bot/features/knowledge_base/embedding_processor.py
"""Embedding処理のバックグラウンドタスク"""

import asyncio
import structlog
from discord.ext import tasks
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...db.postgres import PostgreSQLDatabase
    from ...external.embedding import EmbeddingProvider

logger = structlog.get_logger(__name__)

class EmbeddingProcessor:
    """Embedding処理を管理するクラス"""
    
    def __init__(
        self,
        db: "PostgreSQLDatabase",
        embedding_provider: "EmbeddingProvider",
        batch_size: int | None = None,
        max_concurrent: int | None = None,
    ):
        self.db = db
        self.embedding_provider = embedding_provider
        # 環境変数から設定を読み込み（デフォルト値あり）
        from ..config import settings
        batch_size = batch_size or settings.kb_embedding_batch_size
        max_concurrent = max_concurrent or settings.kb_embedding_max_concurrent
        
        # ⚠️ 重要: セマフォによる同時実行数制限
        # 接続プール枯渇対策: DB_POOL_MAX_SIZEの20〜30%程度に制限
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._lock = asyncio.Lock()  # 競合状態対策
        
        self._interval = settings.kb_embedding_interval_minutes
```

### 3.2 バックグラウンドタスク

```python
    @tasks.loop(minutes=1)  # デフォルト値（start()で動的に変更される）
    async def process_pending_embeddings(self):
        """pending状態のチャンクをバッチでベクトル化
        
        ⚠️ 重要: エラーハンドリングを実装し、例外が発生してもタスクが継続するようにする
        """
        try:
            await self._process_pending_embeddings_impl()
        except Exception as e:
            logger.exception(f"Error in embedding processing: {e}")
            # タスクは継続（次のループで再試行）
    
    @process_pending_embeddings.error
    async def process_pending_embeddings_error(self, error: Exception):
        """タスクエラー時のハンドラ"""
        logger.error(f"Embedding task error: {error}", exc_info=True)
```

### 3.3 処理ロジックの実装

```python
    async def _process_pending_embeddings_impl(self):
        """Embedding処理の実装（エラーハンドリング分離）"""
        # 競合状態対策: asyncio.Lockを使用
        if self._lock.locked():
            logger.debug("Embedding processing already in progress, skipping...")
            return
        
        async with self._lock:
            logger.debug("Starting embedding processing...")
            
            from ..config import settings
            MAX_RETRY_COUNT = settings.kb_embedding_max_retry
            
            # Tx1: 対象チャンクを取得（FOR UPDATE SKIP LOCKEDでロック）
            async with self.db.pool.acquire() as conn:
                async with conn.transaction():
                    pending_chunks = await conn.fetch("""
                        SELECT id, content, source_id
                        FROM knowledge_chunks
                        WHERE embedding IS NULL
                        AND retry_count < $1
                        ORDER BY id ASC
                        LIMIT $2
                        FOR UPDATE SKIP LOCKED
                    """, MAX_RETRY_COUNT, self.batch_size)
            
            if not pending_chunks:
                logger.debug("No pending chunks to process")
                return
            
            logger.info(f"Processing {len(pending_chunks)} pending chunks...")
            
            # No Tx: OpenAI Embedding APIのバッチリクエスト（時間かかる処理）
            texts = [chunk["content"] for chunk in pending_chunks]
            try:
                embeddings = await self._generate_embeddings_batch(texts)
            except Exception as e:
                # Embedding API全体障害時の処理
                error_code = self._classify_error(e)
                logger.error(f"Embedding API failed for batch: {error_code}", exc_info=True)
                # エラー時の更新処理（retry_countをインクリメント）
                await self._handle_embedding_error(pending_chunks, e)
                return
            
            # Tx2: 結果を UPDATE（別トランザクション）
            from ..constants import SearchConstants
            vector_cast = SearchConstants.VECTOR_CAST
            vector_dimension = SearchConstants.VECTOR_DIMENSION
            
            async with self.db.pool.acquire() as conn:
                async with conn.transaction():
                    update_data = [
                        (emb, chunk["id"])
                        for emb, chunk in zip(embeddings, pending_chunks)
                    ]
                    
                    await conn.executemany(f"""
                        UPDATE knowledge_chunks
                        SET embedding = $1::{vector_cast}({vector_dimension}),
                            retry_count = 0
                        WHERE id = $2
                    """, update_data)
            
            # Sourceのステータスも更新
            await self._update_source_status(pending_chunks)
            
            logger.info(f"Successfully processed {len(pending_chunks)} chunks")
```

### 3.4 DLQへの移動ロジック

```python
    async def _move_to_dlq(
        self, conn: asyncpg.Connection, chunk: dict, error: Exception
    ) -> None:
        """チャンクをDead Letter Queueに移動
        
        ⚠️ 改善（セキュリティ）: エラーメッセージの情報漏洩リスクを改善
        エラーコードと一般化されたメッセージのみを保存し、詳細なスタックトレースはログのみに出力します。
        """
        try:
            error_code = self._classify_error(error)
            error_message = self._generalize_error_message(error)
            
            logger.error(
                f"Chunk {chunk['id']} moved to DLQ after "
                f"{chunk.get('retry_count', 0)} retries: {error_code}",
                exc_info=error
            )
            
            # DLQに移動
            source_id = chunk.get("source_id")
            source_info = None
            if source_id:
                source_info = await conn.fetchrow("""
                    SELECT type, title FROM knowledge_sources WHERE id = $1
                """, source_id)
            
            source_type = source_info["type"] if source_info else None
            source_title = source_info["title"] if source_info else None
            
            await conn.execute("""
                INSERT INTO knowledge_chunks_dlq
                (
                    original_chunk_id, source_id, source_type, source_title,
                    content, error_code, error_message, retry_count,
                    last_retry_at
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, CURRENT_TIMESTAMP)
            """, 
                chunk["id"], 
                source_id,
                source_type,
                source_title,
                chunk["content"], 
                error_code,
                error_message, 
                chunk.get("retry_count", 0)
            )
            
            # 元のチャンクを削除
            await conn.execute("""
                DELETE FROM knowledge_chunks WHERE id = $1
            """, chunk["id"])
        except Exception as e:
            logger.error(f"Failed to move chunk {chunk['id']} to DLQ: {e}", exc_info=True)
```

### 3.5 完了基準

- [ ] `EmbeddingProcessor`クラスが実装されている
- [ ] バックグラウンドタスクが動作する
- [ ] `FOR UPDATE SKIP LOCKED`パターンが実装されている
- [ ] トランザクション内でのAPIコールを回避している
- [ ] セマフォによる同時実行数制限が実装されている
- [ ] DLQへの移動ロジックが実装されている
- [ ] Graceful Shutdownが実装されている
- [ ] halfvec固定採用でのembedding更新が正しく動作する

---

## 4. 重要な実装ポイント

### 4.1 トランザクション分離

**パターン**: Tx1 → No Tx → Tx2

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

### 4.2 セマフォによる同時実行数制限

```python
# 接続プール枯渇対策: DB_POOL_MAX_SIZEの20〜30%程度に制限
max_concurrent = max(1, min(5, int(max_pool_size * 0.25)))
self._semaphore = asyncio.Semaphore(max_concurrent)
```

### 4.3 halfvec固定採用

```python
from ..constants import SearchConstants
vector_cast = SearchConstants.VECTOR_CAST  # "halfvec"
vector_dimension = SearchConstants.VECTOR_DIMENSION  # 1536

await conn.executemany(f"""
    UPDATE knowledge_chunks
    SET embedding = $1::{vector_cast}({vector_dimension}),
        retry_count = 0
    WHERE id = $2
""", update_data)
```

---

## 5. 依存性注入パターン

### 5.1 main.pyでの初期化

```python
# src/kotonoha_bot/main.py
from kotonoha_bot.db.postgres import PostgreSQLDatabase
from kotonoha_bot.external.embedding.openai_embedding import OpenAIEmbeddingProvider
from kotonoha_bot.features.knowledge_base.embedding_processor import EmbeddingProcessor

async def main():
    # データベース初期化
    db = PostgreSQLDatabase(connection_string=settings.database_url)
    await db.initialize()
    
    # Embedding プロバイダー初期化
    embedding_provider = OpenAIEmbeddingProvider()
    
    # EmbeddingProcessor初期化
    embedding_processor = EmbeddingProcessor(
        db,
        embedding_provider,
    )
    
    # バックグラウンドタスクを開始
    embedding_processor.start()
    
    try:
        await bot.start(settings.discord_token)
    except KeyboardInterrupt:
        logger.info("Shutting down gracefully...")
    finally:
        # Graceful Shutdown
        await embedding_processor.graceful_shutdown()
        await db.close()
```

### 5.2 Graceful Shutdown

```python
    async def graceful_shutdown(self):
        """Graceful Shutdown: 処理中のタスクが完了するまで待機"""
        logger.info("Stopping embedding processor gracefully...")
        
        # タスクをキャンセル
        self.process_pending_embeddings.cancel()
        
        # 処理中のタスクが完了するまで待機
        try:
            task = getattr(self.process_pending_embeddings, '_task', None)
            if task and not task.done():
                from asyncio import timeout
                async with timeout(30.0):  # 最大30秒待機
                    await task
        except TimeoutError:
            logger.warning("Embedding processing task did not complete within timeout")
        
        logger.info("Embedding processor stopped")
```

---

## 6. 完了基準

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
- [ ] Graceful Shutdownが実装されている

---

## 参考資料

- **Phase 8概要**: [Phase 8実装計画書](phases/phase08.md)
- **PostgreSQL実装**: [PostgreSQL実装詳細](postgresql-implementation.md)
- **テスト戦略**: [テスト戦略](postgresql-testing-strategy.md)

---

**作成日**: 2026年1月19日  
**最終更新日**: 2026年1月19日
