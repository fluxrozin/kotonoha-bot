# セッションアーカイブの実装詳細

**作成日**: 2026年1月19日  
**対象プロジェクト**: kotonoha-bot v0.8.0

---

## 目次

1. [概要](#1-概要)
2. [SessionArchiverの実装](#2-sessionarchiverの実装)
3. [重要な実装ポイント](#3-重要な実装ポイント)
4. [完了基準](#4-完了基準)

---

## 1. 概要

### 1.1 目的と意図

このドキュメントは、**Phase 8: PostgreSQL + pgvector 実装**において、
PostgreSQLの`sessions`テーブル（短期記憶）に保存された非アクティブな
Discord会話セッションを、`knowledge_sources`と`knowledge_chunks`テーブル
（長期記憶）に変換するバックグラウンド処理システムの実装詳細を説明します。

#### PostgreSQLとの関係性

PostgreSQLのスキーマは、**「短期記憶（Sessions）」**と**「長期記憶（Knowledge）」**
の2つのエリアで構成されています：

**短期記憶（`sessions`テーブル）**:

```sql
CREATE TABLE sessions (
    id BIGSERIAL PRIMARY KEY,
    session_key TEXT UNIQUE NOT NULL,
    messages JSONB DEFAULT '[]'::jsonb NOT NULL,  -- 会話履歴
    status session_status_enum DEFAULT 'active',
    version INT DEFAULT 1,  -- 楽観的ロック用
    last_archived_message_index INT DEFAULT 0,
    last_active_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
```

**長期記憶（`knowledge_sources`と`knowledge_chunks`テーブル）**:

```sql
CREATE TABLE knowledge_sources (
    id BIGSERIAL PRIMARY KEY,
    type source_type_enum NOT NULL,  -- 'discord_session'等
    title TEXT NOT NULL,
    uri TEXT,
    status source_status_enum DEFAULT 'pending',
    metadata JSONB DEFAULT '{}'::jsonb
);

CREATE TABLE knowledge_chunks (
    id BIGSERIAL PRIMARY KEY,
    source_id BIGINT REFERENCES knowledge_sources(id),
    content TEXT NOT NULL,              -- 検索対象のテキスト
    embedding halfvec(1536),           -- ベクトルデータ（NULL許容）
    location JSONB DEFAULT '{}'::jsonb,
    token_count INT
);
```

**重要なポイント**:

1. **短期記憶から長期記憶への変換**: 非アクティブなセッションを
   `knowledge_sources`と`knowledge_chunks`に変換することで、
   pgvectorによるベクトル検索の対象となります
2. **スライディングウィンドウ方式**: アーカイブ時に短期記憶を
   全消去せず、直近の数メッセージ（デフォルト: 5件）を残すことで、
   ユーザーが戻ってきた際に文脈が繋がります
3. **Embedding処理との連携**: `knowledge_chunks`に`embedding=NULL`で
   保存し、後で`EmbeddingProcessor`がバックグラウンドでベクトル化します

#### なぜこの処理が必要なのか

1. **pgvector検索の実現**: 会話履歴をベクトル化して`knowledge_chunks`に
   保存することで、`similarity_search`メソッドによる類似度検索が可能になります
2. **ストレージ効率**: `sessions`テーブルの`messages`カラム（JSONB）に
   全履歴を保持し続けると、データベースサイズが肥大化します。
   古い会話を`knowledge_chunks`に移すことで、`sessions`テーブルを
   軽量に保ちます
3. **検索精度の向上**: 会話履歴をチャンク化して保存することで、
   より細かい粒度での検索が可能になり、関連性の高い情報を
   見つけやすくなります

### 1.2 アーキテクチャ上の決定事項

- **アーカイブのトリガー**: 「最終発言から一定時間経過（デフォルト: 1時間）」
  を維持する（ゾンビセッション防止）
- **スライディングウィンドウ（のりしろ）方式**: アーカイブ時に短期記憶を
  ゼロにせず、「直近の数メッセージ（デフォルト: 5件）」を残す処理を実装
- **検索戦略**: Botは常に「現在の短期記憶（のりしろ含む）」＋
  「ベクトル検索結果」の両方を参照して回答を生成する

### 1.3 データフロー

PostgreSQLでの処理フローは以下の通りです：

1. **READ**: PostgreSQLの`sessions`テーブルから
   非アクティブなセッション（`last_active_at < 閾値`）を取得
2. **INSERT (長期記憶)**:
   - `knowledge_sources`テーブルに`type='discord_session'`で登録
   - `knowledge_chunks`テーブルにチャンク化したメッセージを
     `embedding=NULL`で登録（後で`EmbeddingProcessor`が処理）
3. **UPDATE (短期記憶)**: `sessions`テーブルの`messages`カラムを
   「後ろからN件（デフォルト: 5件）」に切り詰めて更新
   - 楽観的ロック（`version`カラム）を使用して競合を防止
   - トランザクション分離レベル`REPEATABLE READ`で実行

これにより、「時間が経てば整理されるが、ユーザーが戻ってきても
直近の文脈は繋がる」という、人間にとって自然な記憶構造を実現できます。

### 1.4 主要なコンポーネント

- **SessionArchiver**: PostgreSQLの`sessions`テーブルを監視し、
  バックグラウンドでセッションアーカイブ処理を実行するクラス
  - PostgreSQLの楽観的ロック（`version`カラム）による競合制御
  - トランザクション分離レベル`REPEATABLE READ`の使用
  - スライディングウィンドウ（のりしろ）方式の実装

### 1.5 Phase 8における位置づけ

このセッションアーカイブシステムは、Phase 8の以下の実装ステップと連携します：

- **Step 2: PostgreSQL実装の追加**: `sessions`テーブルの実装
- **Step 4: 知識ベーススキーマの実装**: `knowledge_sources`と
  `knowledge_chunks`テーブルの実装
- **Step 5: Embedding処理の実装**: `knowledge_chunks`に
  `embedding=NULL`で保存されたチャンクを、`EmbeddingProcessor`が
  バックグラウンドでベクトル化
- **Step 3: ベクトル検索機能の実装**: アーカイブされた会話履歴が
  `similarity_search`メソッドの検索対象となる

---

## 2. SessionArchiverの実装

### 2.1 クラス構造

```python
# src/kotonoha_bot/features/knowledge_base/session_archiver.py
"""セッションの知識化処理"""

import asyncio
import structlog
from datetime import datetime, timedelta
from discord.ext import tasks
from typing import TYPE_CHECKING
import tiktoken

if TYPE_CHECKING:
    from ...db.postgres import PostgreSQLDatabase
    from ...external.embedding import EmbeddingProvider

logger = structlog.get_logger(__name__)

class SessionArchiver:
    """セッションを知識ベースに変換するクラス"""
    
    def __init__(
        self,
        db: "PostgreSQLDatabase",
        embedding_provider: "EmbeddingProvider",
        archive_threshold_hours: int | None = None,
    ):
        self.db = db
        self.embedding_provider = embedding_provider
        from ..config import settings
        self.archive_threshold_hours = archive_threshold_hours or settings.kb_archive_threshold_hours
        self._processing = False
        self._processing_sessions: set = set()
```

### 2.2 バックグラウンドタスク

```python
    @tasks.loop(hours=1)  # デフォルト: 1時間ごと
    async def archive_inactive_sessions(self):
        """非アクティブなセッションを知識ベースに変換"""
        if self._processing:
            logger.debug("Session archiving already in progress, skipping...")
            return
        
        try:
            self._processing = True
            logger.debug("Starting session archiving...")
            
            from ..config import settings
            archive_threshold_hours = settings.kb_archive_threshold_hours
            batch_size = settings.kb_archive_batch_size
            
            # 閾値時間以上非アクティブなセッションを取得
            threshold_time = datetime.now() - timedelta(hours=archive_threshold_hours)
            
            async with self.db.pool.acquire() as conn:
                inactive_sessions = await conn.fetch("""
                    SELECT session_key, session_type, messages,
                           guild_id, channel_id, thread_id,
                           user_id, last_active_at, version,
                           last_archived_message_index
                    FROM sessions
                    WHERE status = 'active'
                    AND last_active_at < $1
                    ORDER BY last_active_at ASC
                    LIMIT $2
                """, threshold_time, batch_size)
            
            if not inactive_sessions:
                logger.debug("No inactive sessions to archive")
                return
            
            logger.info(f"Archiving {len(inactive_sessions)} inactive sessions...")
            
            # ⚠️ 重要: セッションアーカイブの並列処理（高速化）
            # セマフォで同時実行数を制限しつつ並列処理
            from ..config import settings
            max_pool_size = settings.db_pool_max_size
            archive_concurrency = max(1, min(5, int(max_pool_size * 0.25)))
            archive_semaphore = asyncio.Semaphore(archive_concurrency)
            
            async def _archive_with_limit(session_row):
                """セマフォで制限されたアーカイブ処理"""
                async with archive_semaphore:
                    try:
                        await self._archive_session(session_row)
                    except Exception as e:
                        logger.error(
                            f"Failed to archive session "
                            f"{session_row['session_key']}: {e}",
                            exc_info=True)
            
            # 並列処理
            await asyncio.gather(
                *[_archive_with_limit(s) for s in inactive_sessions],
                return_exceptions=True
            )
            
            logger.info(f"Successfully archived {len(inactive_sessions)} sessions")
            
        except Exception as e:
            logger.error(f"Error during session archiving: {e}", exc_info=True)
        finally:
            self._processing = False
```

### 2.3 アーカイブ処理の実装

```python
    async def _archive_session(self, session_row: dict):
        """セッションを知識ベースに変換
        
        ⚠️ 重要: 楽観的ロックの競合時は自動リトライ（tenacity使用）
        """
        from tenacity import (
            retry,
            stop_after_attempt,
            wait_exponential,
            retry_if_exception_type
        )
        
        @retry(
            stop=stop_after_attempt(3),  # 最大3回リトライ
            wait=wait_exponential(multiplier=1, min=1, max=10),
            retry=retry_if_exception_type(ValueError),
            reraise=True
        )
        async def _archive_session_with_retry():
            task = asyncio.create_task(self._archive_session_impl(session_row))
            self._processing_sessions.add(task)
            try:
                return await task
            finally:
                self._processing_sessions.discard(task)
        
        return await _archive_session_with_retry()
    
    async def _archive_session_impl(self, session_row: dict):
        """セッションを知識ベースに変換（実装本体）
        
        ⚠️ 改善（会話の分断対策）: スライディングウィンドウ（のりしろ）方式
        アーカイブ時に短期記憶を「全消去」するのではなく、
        「直近の数メッセージ（のりしろ）」を残して更新（Prune）する設計にします。
        """
        session_key = session_row['session_key']
        messages = session_row['messages']
        original_version = session_row.get('version', 1)
        current_archived_index = session_row.get(
            'last_archived_message_index', 0
        )
        
        if not messages:
            logger.debug(f"Skipping empty session: {session_key}")
            return
        
        # ⚠️ 改善: アーカイブ対象のメッセージを取得（last_archived_message_index 以降のみ）
        messages_to_archive = messages[current_archived_index:]
        
        if not messages_to_archive:
            logger.debug(f"No new messages to archive for session: {session_key}")
            return
        
        # フィルタリングロジック（短いセッション、Botのみのセッション除外）
        from ..config import settings
        MIN_SESSION_LENGTH = settings.kb_min_session_length
        
        # ユーザーメッセージが含まれているか確認
        has_user_message = any(
            msg.get('role') == 'user' for msg in messages_to_archive
        )
        
        # セッションの長さを確認（文字数）
        total_length = sum(
            len(msg.get('content', '')) for msg in messages_to_archive
        )
        
        if not has_user_message:
            logger.debug(f"Skipping bot-only session: {session_key}")
            # ステータスを'archived'に更新（アーカイブ対象外としてマーク）
            async with self.db.pool.acquire() as conn:
                async with conn.transaction():
                    await conn.execute("""
                        UPDATE sessions
                        SET status = 'archived',
                            version = version + 1
                        WHERE session_key = $1
                    """, session_key)
            return
        
        if total_length < MIN_SESSION_LENGTH:
            logger.debug(f"Skipping short session: {session_key} (length: {total_length})")
            # ステータスを'archived'に更新（アーカイブ対象外としてマーク）
            async with self.db.pool.acquire() as conn:
                async with conn.transaction():
                    await conn.execute("""
                        UPDATE sessions
                        SET status = 'archived',
                            version = version + 1
                        WHERE session_key = $1
                    """, session_key)
            return
        
        # スライディングウィンドウ（のりしろ）方式
        from ..config import settings
        OVERLAP_MESSAGES = settings.kb_archive_overlap_messages
        if len(messages) > OVERLAP_MESSAGES:
            overlap_messages = messages[-OVERLAP_MESSAGES:]
        else:
            overlap_messages = messages
        
        # チャンク化
        chunks = self._chunk_messages(messages_to_archive)
        
        # トランザクション分離レベル REPEATABLE READ で実行
        async with self.db.pool.acquire() as conn:
            async with conn.transaction(isolation='repeatable_read'):
                # 1. knowledge_sources に登録
                source_id = await conn.fetchval("""
                    INSERT INTO knowledge_sources (type, title, uri, metadata, status)
                    VALUES ($1, $2, $3, $4, $5)
                    RETURNING id
                """,
                    'discord_session',
                    f"会話ログ: {session_key}",
                    self._generate_discord_url(session_row),
                    {
                        'origin_session_key': session_key,
                        'origin_session_id': session_row.get('id'),
                        'channel_name': session_row.get('channel_id'),
                        'participants': [session_row.get('user_id')],
                        'message_count': len(messages_to_archive)
                    },
                    'pending'
                )
                
                # 2. knowledge_chunks に登録
                for chunk in chunks:
                    await conn.execute("""
                        INSERT INTO knowledge_chunks
                        (source_id, content, location, token_count)
                        VALUES ($1, $2, $3, $4)
                    """,
                        source_id,
                        chunk['content'],
                        chunk.get('location', {}),
                        chunk.get('token_count')
                    )
                
                # 3. sessions の status を 'archived' に更新（楽観的ロック）
                new_archived_index = len(messages) - len(overlap_messages)
                result = await conn.execute("""
                    UPDATE sessions
                    SET status = 'archived',
                        messages = $2::jsonb,
                        version = version + 1,
                        last_archived_message_index = $3
                    WHERE session_key = $1
                    AND version = $4
                """,
                    session_key,
                    overlap_messages,
                    new_archived_index,
                    original_version
                )
                
                if result == "UPDATE 0":
                    raise ValueError("Session was concurrently updated")
        
        logger.info(f"Archived session {session_key} as knowledge source {source_id}")
```

### 2.4 チャンク化の実装

```python
    def _chunk_messages(self, messages: list[dict]) -> list[dict]:
        """メッセージをチャンク化
        
        ⚠️ 改善: メッセージ単位/会話ターン単位でのチャンク化（推奨）
        """
        from ..config import settings
        chunk_strategy = settings.kb_chat_chunk_strategy
        
        if chunk_strategy == "message_based":
            # メッセージ単位/会話ターン単位でのチャンク化（推奨）
            return self._chunk_messages_by_turns(messages)
        else:
            # トークンベースのチャンク化（フォールバック）
            return self._chunk_messages_by_tokens(messages)
    
    def _chunk_messages_by_turns(self, messages: list[dict]) -> list[dict]:
        """会話ターン単位でのチャンク化
        
        会話のターン（user → assistant）を1つのチャンクとして扱います。
        """
        from ..config import settings
        chunk_size_messages = settings.kb_chat_chunk_size_messages
        chunk_overlap_messages = settings.kb_chat_chunk_overlap_messages
        
        chunks = []
        i = 0
        
        while i < len(messages):
            # チャンクサイズ分のメッセージを取得
            chunk_messages = messages[i:i + chunk_size_messages]
            
            # チャンクのコンテンツを生成
            content = self._format_messages_for_knowledge(chunk_messages)
            
            # トークン数をカウント
            encoding = tiktoken.get_encoding("cl100k_base")
            token_count = len(encoding.encode(content))
            
            chunks.append({
                'content': content,
                'location': {
                    'message_start_index': i,
                    'message_end_index': i + len(chunk_messages) - 1,
                    'total_messages': len(messages)
                },
                'token_count': token_count
            })
            
            # オーバーラップ分だけ進む
            i += chunk_size_messages - chunk_overlap_messages
        
        return chunks
    
    def _format_messages_for_knowledge(self, messages: list[dict]) -> str:
        """会話ログをMarkdown形式でフォーマット"""
        formatted = []
        for msg in messages:
            role = msg.get('role', 'unknown')
            content = msg.get('content', '')
            if role == 'user':
                formatted.append(f"**User**: {content}")
            elif role == 'assistant':
                formatted.append(f"**Assistant**: {content}")
            elif role == 'system':
                formatted.append(f"**System**: {content}")
        return "\n\n".join(formatted)
```

---

## 3. 重要な実装ポイント

### 3.1 スライディングウィンドウ（のりしろ）方式

```python
# アーカイブ時に短期記憶を「全消去」するのではなく、
# 「直近の数メッセージ（のりしろ）」を残して更新
from ..config import settings
OVERLAP_MESSAGES = settings.kb_archive_overlap_messages  # デフォルト: 5件
overlap_messages = messages[-OVERLAP_MESSAGES:]
```

### 3.2 楽観的ロック

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

### 3.3 トランザクション分離レベル

```python
# REPEATABLE READ に設定（楽観的ロックのため）
async with conn.transaction(isolation='repeatable_read'):
    # 1. knowledge_sources に登録
    # 2. knowledge_chunks に登録
    # 3. sessions の status を 'archived' に更新
```

### 3.4 メッセージ単位でのチャンク化

```python
# 環境変数からチャンク化戦略を選択
from ..config import settings
chunk_strategy = settings.kb_chat_chunk_strategy

if chunk_strategy == "message_based":
    # メッセージ単位/会話ターン単位でのチャンク化（推奨）
    chunks = self._chunk_messages_by_turns(messages)
```

---

## 4. 完了基準

### Step 5.4: セッション知識化処理

- [ ] `SessionArchiver`クラスが実装されている
- [ ] 非アクティブなセッションが自動的に知識ベースに変換される
- [ ] スライディングウィンドウ（のりしろ）方式が実装されている
- [ ] 楽観的ロック（`version`カラム）が実装されている
- [ ] トランザクション分離レベルが`REPEATABLE READ`に設定されている
- [ ] メッセージ単位でのチャンク化が実装されている
- [ ] フィルタリングロジック（短いセッション、Botのみのセッション除外）が実装されている
- [ ] Graceful Shutdownが実装されている

---

## 参考資料

- **Phase 8概要**: [Phase 8実装計画書](phases/phase08.md)
- **PostgreSQL実装**: [PostgreSQL実装詳細](postgresql-implementation.md)
- **Embedding処理**: [Embedding処理詳細](postgresql-embedding-processing.md)
- **テスト戦略**: [テスト戦略](postgresql-testing-strategy.md)

---

**作成日**: 2026年1月19日  
**最終更新日**: 2026年1月19日
