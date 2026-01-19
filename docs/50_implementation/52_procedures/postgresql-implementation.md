# PostgreSQL実装の詳細

**作成日**: 2026年1月19日  
**対象プロジェクト**: kotonoha-bot v0.8.0

---

## 目次

1. [概要](#1-概要)
2. [Step 0: 依存関係の確認と設計レビュー](#2-step-0-依存関係の確認と設計レビュー)
3. [Step 1: データベース抽象化レイヤーの実装](#3-step-1-データベース抽象化レイヤーの実装)
4. [Step 2: PostgreSQL 実装の追加](#4-step-2-postgresql-実装の追加)
5. [Step 3: ベクトル検索機能の実装](#5-step-3-ベクトル検索機能の実装)
6. [Step 4: 知識ベーススキーマの実装](#6-step-4-知識ベーススキーマの実装)
7. [Step 6: Docker Compose の更新](#7-step-6-docker-compose-の更新)
8. [動作確認方法](#8-動作確認方法)

---

## 1. 概要

このドキュメントでは、PostgreSQL + pgvector の実装詳細を説明します。

### 1.1 主要なコンポーネント

- **PostgreSQLDatabase**: PostgreSQL + pgvector によるデータベース実装
- **DatabaseProtocol**: セッション管理の抽象化インターフェース
- **KnowledgeBaseProtocol**: 知識ベース管理の抽象化インターフェース

---

## 2. Step 0: 依存関係の確認と設計レビュー

### 2.1 依存関係の追加

```toml
# pyproject.toml
dependencies = [
    # ... 既存の依存関係 ...
    "asyncpg>=0.31.0",          # PostgreSQL非同期ドライバー
    "pgvector>=0.3.0",          # pgvector Pythonライブラリ
    "asyncpg-stubs>=0.31.1",    # asyncpgの型スタブ（dev依存関係）
    "langchain-text-splitters>=1.1.0",  # テキスト分割ライブラリ
    "openai>=2.15.0",           # Embedding API用
    "pydantic-settings>=2.12.0", # 型安全な設定管理
    "tiktoken>=0.12.0",          # トークン数カウント用
    "tenacity>=9.1.2",           # リトライロジック用
    "structlog>=25.5.0",         # 構造化ログ
    "prometheus-client>=0.24.1", # メトリクス収集
    "orjson>=3.11.5",            # 高速JSON処理
    "alembic>=1.13.0",           # スキーママイグレーション管理
]
```

### 2.2 Alembicの初期化

```bash
# Alembicの初期化（プロジェクトルートで実行）
alembic init alembic
```

**生成されるファイル**:

- `alembic.ini`: Alembic設定ファイル
- `alembic/`: マイグレーションスクリプトのディレクトリ
- `alembic/env.py`: マイグレーション実行環境の設定

### 2.3 pydantic-settingsによる環境変数の一元管理

```python
# src/kotonoha_bot/config.py
"""アプリケーション設定（グローバルシングルトン）"""

from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """アプリケーション設定クラス
    
    すべての環境変数を一元管理します。
    型チェックとバリデーションが自動的に行われます。
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )
    
    # データベース設定
    db_pool_min_size: int = 5
    db_pool_max_size: int = 20
    db_command_timeout: int = 60
    
    # PostgreSQL接続設定
    postgres_host: str | None = None
    postgres_port: int = 5432
    postgres_db: str = "kotonoha"
    postgres_user: str = "kotonoha"
    postgres_password: str | None = None
    database_url: str | None = None
    
    # 知識ベース設定
    kb_hnsw_m: int = 16
    kb_hnsw_ef_construction: int = 64
    kb_similarity_threshold: float = 0.7
    kb_default_top_k: int = 10
    
    # ... その他の設定 ...

# グローバルシングルトン
settings = Settings()
```

### 2.4 constants.pyによる定数管理

```python
# src/kotonoha_bot/constants.py
"""定数管理"""

class SearchConstants:
    """検索関連の定数"""
    VECTOR_CAST = "halfvec"  # halfvec固定採用
    VECTOR_DIMENSION = 1536  # OpenAI text-embedding-3-small

class DatabaseConstants:
    """データベース関連の定数"""
    POOL_ACQUIRE_TIMEOUT = 30.0  # 接続取得のタイムアウト（秒）
```

### 2.5 完了基準

- [ ] 依存関係が追加されている
- [ ] `src/kotonoha_bot/config.py`に`Settings`クラスが実装されている
- [ ] `src/kotonoha_bot/constants.py`にすべての定数が定義されている
- [ ] Alembicが初期化されている
- [ ] 初回マイグレーションスクリプトが作成されている

---

## 3. Step 1: データベース抽象化レイヤーの実装

### 3.1 DatabaseProtocolインターフェース

```python
# src/kotonoha_bot/db/base.py
"""データベース抽象化レイヤー"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, TypedDict

if TYPE_CHECKING:
    from ..session.models import ChatSession

class SearchResult(TypedDict):
    """検索結果の型定義"""
    chunk_id: int
    source_id: int
    content: str
    similarity: float
    source_type: str
    title: str
    uri: str | None
    source_metadata: dict | None

class DatabaseProtocol(ABC):
    """セッション管理のみを抽象化するプロトコル"""
    
    @abstractmethod
    async def initialize(self) -> None:
        """データベースの初期化"""
        pass
    
    @abstractmethod
    async def close(self) -> None:
        """データベース接続のクローズ"""
        pass
    
    @abstractmethod
    async def save_session(self, session: "ChatSession") -> None:
        """セッションを保存"""
        pass
    
    @abstractmethod
    async def load_session(self, session_key: str) -> "ChatSession" | None:
        """セッションを読み込み"""
        pass

class KnowledgeBaseProtocol(ABC):
    """知識ベースを別プロトコルとして分離"""
    
    @abstractmethod
    async def similarity_search(
        self,
        query_embedding: list[float],
        top_k: int = 10,
        filters: dict | None = None,
    ) -> list[SearchResult]:
        """類似度検索を実行"""
        pass
    
    @abstractmethod
    async def save_source(
        self,
        source_type: str,
        title: str,
        uri: str | None,
        metadata: dict,
        status: str = "pending",
    ) -> int:
        """知識ソースを保存し、IDを返す"""
        pass
    
    @abstractmethod
    async def save_chunk(
        self,
        source_id: int,
        content: str,
        location: dict | None = None,
        token_count: int | None = None,
    ) -> int:
        """知識チャンクを保存し、IDを返す"""
        pass
```

### 3.2 完了基準

- [ ] `DatabaseProtocol`インターフェースが定義されている
- [ ] `KnowledgeBaseProtocol`インターフェースが定義されている
- [ ] `SearchResult`型定義が定義されている

---

## 4. Step 2: PostgreSQL 実装の追加

### 4.1 PostgreSQLDatabaseクラスの実装

```python
# src/kotonoha_bot/db/postgres.py
"""PostgreSQL データベース実装"""

import asyncpg
import orjson
import structlog
from datetime import datetime
from typing import TYPE_CHECKING

from .base import DatabaseProtocol, KnowledgeBaseProtocol, SearchResult

if TYPE_CHECKING:
    from ..session.models import ChatSession

logger = structlog.get_logger(__name__)

class PostgreSQLDatabase(DatabaseProtocol, KnowledgeBaseProtocol):
    """PostgreSQL データベース（非同期）"""
    
    def __init__(
        self,
        connection_string: str | None = None,
        host: str | None = None,
        port: int | None = None,
        database: str | None = None,
        user: str | None = None,
        password: str | None = None,
    ):
        """PostgreSQL データベースの初期化
        
        ⚠️ 改善（セキュリティ）: 個別パラメータが指定されている場合は、それを使用
        接続文字列にパスワードを含める形式への依存を避ける
        """
        if host and database and user and password:
            self.connection_string = None
            self.host = host
            self.port = port or 5432
            self.database = database
            self.user = user
            self.password = password
        elif connection_string:
            self.connection_string = connection_string
            self.host = None
            self.port = None
            self.database = None
            self.user = None
            self.password = None
        else:
            raise ValueError(
                "Either connection_string or "
                "(host, database, user, password) must be provided"
            )
        self.pool: asyncpg.Pool | None = None
    
    async def _init_connection(self, conn: asyncpg.Connection) -> None:
        """プールの各コネクション初期化時に呼ばれる
        
        ⚠️ 重要: asyncpg.create_pool() の init パラメータには単一の関数しか渡せません。
        pgvectorの型登録とJSONBコーデックの登録を両方行う場合は、このラッパー関数内で
        両方を実行する必要があります。
        """
        # 1. pgvectorの型登録
        from pgvector.asyncpg import register_vector
        await register_vector(conn)
        
        # 2. JSONBコーデックの登録（orjsonを使用）
        def default(obj):
            """orjson の default オプション用の関数"""
            if isinstance(obj, datetime):
                return obj.isoformat()
            raise TypeError(f"Object of type {type(obj)} is not JSON serializable")
        
        await conn.set_type_codec(
            "jsonb",
            encoder=lambda v: orjson.dumps(v, default=default).decode("utf-8"),
            decoder=lambda b: orjson.loads(
                b.encode("utf-8") if isinstance(b, str) else b
            ),
            schema="pg_catalog",
            format="text",
        )
    
    async def initialize(self) -> None:
        """データベースの初期化"""
        from ..config import settings
        from pathlib import Path
        from alembic import command
        from alembic.config import Config
        
        min_size = settings.db_pool_min_size
        max_size = settings.db_pool_max_size
        command_timeout = settings.db_command_timeout
        
        # Alembicマイグレーションの自動適用
        alembic_ini_path = Path("alembic.ini")
        if not alembic_ini_path.exists():
            alembic_ini_path = Path("/app/alembic.ini")
            if not alembic_ini_path.exists():
                raise RuntimeError("alembic.ini not found")
        
        alembic_cfg = Config(str(alembic_ini_path))
        
        # SQLAlchemy URLを設定
        if self.connection_string:
            sqlalchemy_url = self.connection_string.replace(
                "postgresql://", "postgresql+asyncpg://"
            )
        else:
            sqlalchemy_url = (
                f"postgresql+asyncpg://{self.user}:{self.password}@"
                f"{self.host}:{self.port}/{self.database}"
            )
        alembic_cfg.set_main_option("sqlalchemy.url", sqlalchemy_url)
        
        try:
            logger.info("Applying Alembic migrations...")
            command.upgrade(alembic_cfg, "head")
            logger.info("Alembic migrations applied successfully")
        except Exception as e:
            logger.error(f"Failed to apply Alembic migrations: {e}", exc_info=True)
            raise RuntimeError(f"Database migration failed: {e}") from e
        
        # 接続プールを作成
        if self.connection_string:
            self.pool = await asyncpg.create_pool(
                self.connection_string,
                init=self._init_connection,
                min_size=min_size,
                max_size=max_size,
                command_timeout=command_timeout,
            )
        else:
            self.pool = await asyncpg.create_pool(
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.user,
                password=self.password,
                init=self._init_connection,
                min_size=min_size,
                max_size=max_size,
                command_timeout=command_timeout,
            )
        
        # pgvector拡張を有効化
        async with self.pool.acquire() as conn:
            await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
            
            # pg_bigm拡張を有効化（オプション）
            try:
                await conn.execute("CREATE EXTENSION IF NOT EXISTS pg_bigm")
                logger.info("pg_bigm extension enabled for hybrid search")
            except Exception as e:
                logger.warning(f"pg_bigm extension could not be enabled: {e}")
```

### 4.2 セッション管理メソッドの実装

```python
    async def save_session(self, session: "ChatSession") -> None:
        """セッションを保存（トランザクション付き）"""
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    """
                    INSERT INTO sessions
                    (session_key, session_type, messages, status, guild_id,
                     channel_id, thread_id, user_id, version, created_at, last_active_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                    ON CONFLICT (session_key)
                    DO UPDATE SET
                        messages = EXCLUDED.messages,
                        last_active_at = EXCLUDED.last_active_at,
                        status = COALESCE(EXCLUDED.status, sessions.status),
                        guild_id = COALESCE(EXCLUDED.guild_id, sessions.guild_id),
                        version = sessions.version + 1
                """,
                    session.session_key,
                    session.session_type,
                    [msg.to_dict() for msg in session.messages],
                    getattr(session, "status", "active"),
                    getattr(session, "guild_id", None),
                    session.channel_id,
                    getattr(session, "thread_id", None),
                    session.user_id,
                    getattr(session, "version", 1),
                    session.created_at,
                    session.last_active_at,
                )
    
    async def load_session(self, session_key: str) -> "ChatSession" | None:
        """セッションを読み込み"""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM sessions WHERE session_key = $1",
                session_key,
            )
            
            if not row:
                return None
            
            from ..session.models import ChatSession, Message, MessageRole
            
            messages = [
                Message(
                    role=MessageRole(msg["role"]),
                    content=msg["content"],
                    timestamp=datetime.fromisoformat(msg["timestamp"])
                    if msg.get("timestamp")
                    else datetime.now(),
                )
                for msg in row["messages"]
            ]
            
            return ChatSession(
                session_key=row["session_key"],
                session_type=row["session_type"],
                messages=messages,
                status=row.get("status", "active"),
                guild_id=row.get("guild_id"),
                channel_id=row["channel_id"],
                thread_id=row.get("thread_id"),
                user_id=row["user_id"],
                version=row.get("version", 1),
                last_archived_message_index=row.get(
                    "last_archived_message_index", 0
                ),
                created_at=row["created_at"],
                last_active_at=row["last_active_at"],
            )
```

### 4.3 完了基準

- [ ] `PostgreSQLDatabase`クラスが実装されている
- [ ] pgvector拡張が有効化されている
- [ ] JSONBコーデックが実装されている
- [ ] セッション管理メソッドが動作する
- [ ] Alembicマイグレーションが自動適用される

---

## 5. Step 3: ベクトル検索機能の実装

### 5.1 similarity_searchメソッドの実装

```python
    async def similarity_search(
        self,
        query_embedding: list[float],
        top_k: int = 10,
        filters: dict | None = None,
        similarity_threshold: float | None = None,
        apply_threshold: bool = True,
    ) -> list[SearchResult]:
        """類似度検索を実行
        
        ⚠️ 重要: WHERE c.embedding IS NOT NULL 条件は必須です
        この条件がないと、HNSWインデックスが使われずフルスキャンになります。
        """
        from ..config import settings
        from ..constants import SearchConstants, DatabaseConstants
        
        vector_cast = SearchConstants.VECTOR_CAST
        vector_dimension = SearchConstants.VECTOR_DIMENSION
        if similarity_threshold is None:
            similarity_threshold = settings.kb_similarity_threshold
        top_k_limit = top_k or settings.kb_default_top_k
        
        try:
            from asyncio import timeout
            
            async with timeout(DatabaseConstants.POOL_ACQUIRE_TIMEOUT):
                async with self.pool.acquire() as conn:
                    # ベースクエリ
                    # ⚠️ 重要: WHERE c.embedding IS NOT NULL 条件は必須
                    query = f"""
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
                            1 - (c.embedding <=> $1::{vector_cast}({vector_dimension}))
                                as similarity
                        FROM knowledge_chunks c
                        JOIN knowledge_sources s ON c.source_id = s.id
                        WHERE c.embedding IS NOT NULL
                    """
                    
                    params = [query_embedding]
                    param_index = 2
                    
                    # フィルタの適用
                    if filters:
                        # SQLインジェクション対策: Allow-list方式
                        invalid_keys = set(filters.keys()) - ALLOWED_FILTER_KEYS
                        if invalid_keys:
                            raise ValueError(
                                f"Invalid filter keys: {invalid_keys}. "
                                f"Allowed keys: {ALLOWED_FILTER_KEYS}"
                            )
                        
                        if "source_type" in filters:
                            source_type = filters["source_type"]
                            if source_type not in VALID_SOURCE_TYPES:
                                raise ValueError(f"Invalid source_type: {source_type}")
                            query += f" AND s.type = ${param_index}"
                            params.append(source_type)
                            param_index += 1
                        
                        if "source_types" in filters:
                            source_types = filters["source_types"]
                            if not isinstance(source_types, list):
                                raise ValueError("source_types must be a list")
                            invalid_types = set(source_types) - VALID_SOURCE_TYPES
                            if invalid_types:
                                raise ValueError(f"Invalid source_types: {invalid_types}")
                            query += f" AND s.type = ANY(${param_index}::source_type_enum[])"
                            params.append(source_types)
                            param_index += 1
                        
                        if "channel_id" in filters:
                            channel_id = int(filters["channel_id"])
                            query += (
                                f" AND (s.metadata->>'channel_id')::bigint = "
                                f"${param_index}"
                            )
                            params.append(channel_id)
                            param_index += 1
                    
                    # 類似度でソート
                    if apply_threshold:
                        query += f"""
                            AND 1 - (c.embedding <=> $1::{vector_cast}({vector_dimension}))
                                >= ${param_index}
                            ORDER BY c.embedding <=> $1::{vector_cast}({vector_dimension})
                            LIMIT ${param_index + 1}
                        """
                        params.append(similarity_threshold)
                        params.append(min(top_k, top_k_limit))
                    else:
                        query += f"""
                            ORDER BY c.embedding <=> $1::{vector_cast}({vector_dimension})
                            LIMIT ${param_index}
                        """
                        params.append(min(top_k, top_k_limit))
                    
                    # 安全チェック: embedding IS NOT NULL条件の確認
                    query_upper = query.upper()
                    if "EMBEDDING IS NOT NULL" not in query_upper:
                        logger.error(f"Query missing embedding check. Query: {query}")
                        raise ValueError(
                            "CRITICAL: embedding IS NOT NULL condition is missing."
                        )
                    
                    rows = await conn.fetch(query, *params)
        except TimeoutError:
            logger.error("Failed to acquire database connection: pool exhausted")
            raise RuntimeError("Database connection pool exhausted") from None
        
        return [
            SearchResult({
                "source_id": row["source_id"],
                "source_type": row["type"],
                "title": row["title"],
                "uri": row["uri"],
                "source_metadata": row["source_metadata"] or {},
                "chunk_id": row["chunk_id"],
                "content": row["content"],
                "location": row["location"] or {},
                "token_count": row["token_count"],
                "similarity": float(row["similarity"]),
            })
            for row in rows
        ]
```

### 5.2 重要な実装ポイント

#### 5.2.1 halfvec固定採用

```python
from ..constants import SearchConstants
vector_cast = SearchConstants.VECTOR_CAST  # "halfvec"
vector_dimension = SearchConstants.VECTOR_DIMENSION  # 1536

# クエリ内で使用
query = f"""
    SELECT 1 - (c.embedding <=> $1::{vector_cast}({vector_dimension})) as similarity
    FROM knowledge_chunks c
    WHERE c.embedding IS NOT NULL
"""
```

#### 5.2.2 embedding IS NOT NULL条件の強制付与

```python
# 安全チェック: embedding IS NOT NULL条件の確認
query_upper = query.upper()
if "EMBEDDING IS NOT NULL" not in query_upper:
    logger.error(f"Query missing embedding check. Query: {query}")
    raise ValueError("CRITICAL: embedding IS NOT NULL condition is missing.")
```

#### 5.2.3 SQLインジェクション対策

```python
# ENUM値のバリデーション
VALID_SOURCE_TYPES = {
    "discord_session",
    "document_file",
    "web_page",
    "image_caption",
    "audio_transcript",
}

# フィルタキーのAllow-list
ALLOWED_FILTER_KEYS = {
    "source_type",
    "source_types",
    "channel_id",
    "user_id",
}

# バリデーション
if source_type not in VALID_SOURCE_TYPES:
    raise ValueError(f"Invalid source_type: {source_type}")
```

### 5.3 完了基準

- [ ] `similarity_search`メソッドが実装されている
- [ ] `halfvec`固定採用が実装されている
- [ ] `embedding IS NOT NULL`条件が強制付与されている
- [ ] フィルタリング機能が実装されている
- [ ] SQLインジェクション対策が実装されている

---

## 6. Step 4: 知識ベーススキーマの実装

### 6.1 save_sourceメソッドの実装

```python
    async def save_source(
        self,
        source_type: str,
        title: str,
        uri: str | None,
        metadata: dict,
        status: str = "pending",
    ) -> int:
        """知識ソースを保存し、IDを返す"""
        if source_type not in VALID_SOURCE_TYPES:
            raise ValueError(f"Invalid source_type: {source_type}")
        
        async with self.pool.acquire() as conn:
            source_id = await conn.fetchval(
                """
                INSERT INTO knowledge_sources (type, title, uri, metadata, status)
                VALUES ($1, $2, $3, $4::jsonb, $5)
                RETURNING id
            """,
                source_type,
                title,
                uri,
                metadata,
                status,
            )
            
            return source_id
```

### 6.2 save_chunkメソッドの実装

```python
    async def save_chunk(
        self,
        source_id: int,
        content: str,
        location: dict | None = None,
        token_count: int | None = None,
    ) -> int:
        """知識チャンクを保存し、IDを返す
        
        ⚠️ 重要: embedding は NULL で保存されます。
        後で EmbeddingProcessor がバックグラウンドでベクトル化して更新します。
        """
        import tiktoken
        
        # token_countが指定されていない場合は計算
        if token_count is None:
            encoding = tiktoken.encoding_for_model("text-embedding-3-small")
            token_count = len(encoding.encode(content))
        
        location_dict = location or {}
        
        async with self.pool.acquire() as conn:
            chunk_id = await conn.fetchval(
                """
                INSERT INTO knowledge_chunks
                (source_id, content, embedding, location, token_count)
                VALUES ($1, $2, NULL, $3::jsonb, $4)
                RETURNING id
            """,
                source_id,
                content,
                location_dict,
                token_count,
            )
            
            return chunk_id
```

### 6.3 完了基準

- [ ] `save_source`メソッドが実装されている
- [ ] `save_chunk`メソッドが実装されている
- [ ] トークン数カウント機能が実装されている

---

## 7. Step 6: Docker Compose の更新

### 7.1 docker-compose.ymlの更新

```yaml
# docker-compose.yml
services:
  postgres:
    image: pgvector/pgvector:0.8.1-pg18
    container_name: kotonoha-postgres
    environment:
      POSTGRES_USER: kotonoha
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: kotonoha
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U kotonoha"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  kotonoha-bot:
    # ... 既存の設定 ...
    depends_on:
      postgres:
        condition: service_healthy
    environment:
      DATABASE_URL: postgresql://kotonoha:${POSTGRES_PASSWORD}@postgres:5432/kotonoha
      # または個別パラメータ（本番環境推奨）
      POSTGRES_HOST: postgres
      POSTGRES_PORT: 5432
      POSTGRES_DB: kotonoha
      POSTGRES_USER: kotonoha
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}

volumes:
  postgres_data:
```

### 7.2 完了基準

- [ ] PostgreSQLコンテナが追加されている
- [ ] 環境変数が設定されている
- [ ] ヘルスチェックが設定されている

---

## 8. 動作確認方法

### 8.1 PostgreSQLコンテナの起動確認

```bash
# PostgreSQLコンテナを起動
docker compose up -d postgres

# コンテナの状態を確認
docker compose ps

# PostgreSQLのログを確認
docker compose logs postgres

# PostgreSQLに接続して動作確認
docker compose exec postgres psql -U kotonoha -d kotonoha -c "SELECT version();"
```

**確認項目**:

- [ ] PostgreSQLコンテナが正常に起動している（STATUS: healthy）
- [ ] ログにエラーが表示されていない
- [ ] PostgreSQLに接続できる

### 8.2 データベース接続とAlembicマイグレーションの確認

```bash
# Botコンテナを起動
docker compose up -d kotonoha-bot

# Botのログを確認（Alembicマイグレーションが自動実行される）
docker compose logs -f kotonoha-bot
```

**確認項目**:

- [ ] Botが正常に起動している
- [ ] Alembicマイグレーションが自動実行されている
- [ ] データベース接続エラーが発生していない

### 8.3 pgvector拡張の確認

```bash
# pgvector拡張が有効化されているか確認
docker compose exec postgres psql -U kotonoha -d kotonoha \
  -c "SELECT * FROM pg_extension WHERE extname = 'vector';"

# halfvec型が使用可能か確認
docker compose exec postgres psql -U kotonoha -d kotonoha \
  -c "SELECT '[1,2,3]'::halfvec(3);"
```

**確認項目**:

- [ ] pgvector拡張が有効化されている
- [ ] halfvec型が使用可能

### 8.4 セッションの保存・読み込み確認

```bash
# セッションが保存されているか確認
docker compose exec postgres psql -U kotonoha -d kotonoha \
  -c "SELECT session_key, session_type, status, created_at \
      FROM sessions ORDER BY created_at DESC LIMIT 5;"
```

**確認項目**:

- [ ] セッションが`sessions`テーブルに保存されている
- [ ] メッセージが`messages`カラム（JSONB）に保存されている

### 8.5 ベクトル検索の確認

```python
# Pythonスクリプトで実行
import asyncio
from kotonoha_bot.db.postgres import PostgreSQLDatabase
from kotonoha_bot.config import settings

async def test_similarity_search():
    db = PostgreSQLDatabase(connection_string=settings.database_url)
    await db.initialize()
    
    # テスト用のベクトル
    query_embedding = [0.1] * 1536
    
    # ベクトル検索を実行
    results = await db.similarity_search(
        query_embedding=query_embedding,
        top_k=5
    )
    
    print(f"検索結果数: {len(results)}")
    for result in results:
        print(f"  - chunk_id: {result['chunk_id']}, "
              f"similarity: {result['similarity']:.6f}")
    
    await db.close()

asyncio.run(test_similarity_search())
```

**確認項目**:

- [ ] ベクトル検索が正常に動作する
- [ ] 検索結果が返ってくる
- [ ] `similarity`スコアが正しく計算されている

---

## 参考資料

- **Phase 8概要**: [Phase 8実装計画書](phases/phase08.md)
- **スキーマ設計書**: [PostgreSQL スキーマ設計書](../../40_design_detailed/42_db-schema-physical/postgresql-schema-overview.md)
- **Embedding処理**: [Embedding処理詳細](postgresql-embedding-processing.md)
- **セッションアーカイブ**: [セッションアーカイブ詳細](postgresql-session-archiving.md)
- **テスト戦略**: [テスト戦略](postgresql-testing-strategy.md)

---

**作成日**: 2026年1月19日  
**最終更新日**: 2026年1月19日
