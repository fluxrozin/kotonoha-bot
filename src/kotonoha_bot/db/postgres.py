"""PostgreSQL データベース実装"""

from datetime import datetime
from typing import TYPE_CHECKING

import asyncpg
import orjson
import structlog

from .base import DatabaseProtocol, KnowledgeBaseProtocol, SearchResult

if TYPE_CHECKING:
    from ..session.models import ChatSession

logger = structlog.get_logger(__name__)

# ENUM値のバリデーション（SQLインジェクション対策）
VALID_SOURCE_TYPES = {
    "discord_session",
    "document_file",
    "web_page",
    "image_caption",
    "audio_transcript",
}

# フィルタキーのAllow-list（SQLインジェクション対策）
ALLOWED_FILTER_KEYS = {
    "source_type",
    "source_types",
    "channel_id",
    "user_id",
}


class PostgreSQLDatabase(DatabaseProtocol, KnowledgeBaseProtocol):
    """PostgreSQL データベース（非同期）

    ⚠️ 改善（抽象化の粒度）: `DatabaseProtocol` と `KnowledgeBaseProtocol` の両方を実装することで、
    セッション管理と知識ベース管理を分離し、抽象化の粒度を均一にします。
    """

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

        ⚠️ 改善（セキュリティ）: DATABASE_URL にパスワードを含める形式への依存を改善
        asyncpg はパスワードを別パラメータで渡せるため、接続文字列にパスワードを埋め込む必要はありません。

        Args:
            connection_string: 接続文字列（開発環境用、後方互換性のため残す）
            host: PostgreSQL ホスト（本番環境推奨）
            port: PostgreSQL ポート（デフォルト: 5432）
            database: データベース名
            user: ユーザー名
            password: パスワード（分離して管理）
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
        import os
        from pathlib import Path

        from ..config import settings

        min_size = settings.db_pool_min_size
        max_size = settings.db_pool_max_size
        command_timeout = settings.db_command_timeout

        # Alembicマイグレーションの自動適用（接続プール作成前に実行）
        from alembic import command
        from alembic.config import Config

        # alembic.ini のパスを決定
        # Docker環境では /app/alembic.ini、ローカル環境ではプロジェクトルートの alembic.ini
        alembic_ini_path = Path("alembic.ini")
        if not alembic_ini_path.exists():
            # カレントディレクトリにない場合は /app を試す（Docker環境）
            alembic_ini_path = Path("/app/alembic.ini")
            if not alembic_ini_path.exists():
                raise RuntimeError(
                    f"alembic.ini not found. CWD={os.getcwd()}, "
                    f"Searched: ./alembic.ini, /app/alembic.ini"
                )

        logger.debug(f"Using alembic.ini at: {alembic_ini_path.absolute()}")
        alembic_cfg = Config(str(alembic_ini_path))

        # SQLAlchemy URLを設定（env.pyでpsycopg2に変換される）
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

        # マイグレーション実行後に接続プールを作成
        logger.info(
            f"Creating database connection pool (min={min_size}, max={max_size})..."
        )
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
        logger.info("Database connection pool created successfully")

        # pgvector 拡張を有効化とバージョン確認
        logger.info("Enabling database extensions (pgvector, pg_bigm)...")
        async with self.pool.acquire() as conn:
            await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")

            try:
                await conn.execute("CREATE EXTENSION IF NOT EXISTS pg_bigm")
                logger.info("pg_bigm extension enabled for hybrid search")
            except Exception as e:
                logger.warning(
                    f"pg_bigm extension could not be enabled: {e}. "
                    f"Hybrid search will not be available."
                )

            # pgvector のバージョン確認
            version_row = await conn.fetchrow(
                "SELECT extversion FROM pg_extension WHERE extname = 'vector'"
            )
            if version_row:
                version_str = version_row["extversion"]
                version_parts = version_str.split(".")
                major = int(version_parts[0])
                minor = int(version_parts[1]) if len(version_parts) > 1 else 0

                if major < 0 or (major == 0 and minor < 5):
                    raise RuntimeError(
                        f"pgvector version {version_str} is too old. "
                        "HNSW index requires pgvector 0.5.0 or later. "
                        "Please upgrade pgvector."
                    )
                logger.info(
                    f"pgvector version {version_str} is compatible "
                    f"(HNSW supported, recommended: 0.8.1 for PostgreSQL 18)"
                )
            else:
                logger.warning("pgvector extension version could not be determined")

        logger.info(
            f"Database initialized: pool_size={min_size}-{max_size}, "
            f"command_timeout={command_timeout}s"
        )

    async def close(self) -> None:
        """データベース接続のクローズ
        
        asyncpgのpool.close()は、すべての接続が確実にクローズされるまで待機します。
        """
        if self.pool:
            await self.pool.close()
            self.pool = None

    async def save_session(self, session: ChatSession) -> None:
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
                        -- ⚠️ 注意: last_archived_message_index は更新しない
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

    async def load_session(self, session_key: str) -> ChatSession | None:
        """セッションを読み込み"""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT * FROM sessions WHERE session_key = $1
            """,
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
                last_archived_message_index=row.get("last_archived_message_index", 0),
                created_at=row["created_at"],
                last_active_at=row["last_active_at"],
            )

    async def delete_session(self, session_key: str) -> None:
        """セッションを削除"""
        async with self.pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM sessions WHERE session_key = $1", session_key
            )

    async def load_all_sessions(self) -> list[ChatSession]:
        """すべてのセッションを読み込み"""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT * FROM sessions
                ORDER BY last_active_at DESC
            """)

            from ..session.models import ChatSession, Message, MessageRole

            sessions = []
            for row in rows:
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

                sessions.append(
                    ChatSession(
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
                )

            return sessions

    async def similarity_search(
        self,
        query_embedding: list[float],
        top_k: int = 10,
        filters: dict | None = None,
        similarity_threshold: float | None = None,
        apply_threshold: bool = True,
    ) -> list[SearchResult]:
        """類似度検索を実行

        Args:
            query_embedding: クエリのベクトル（1536次元）
            top_k: 取得する結果の数
            filters: フィルタ条件
                （例: {"source_type": "discord_session", "channel_id": 123}）
            similarity_threshold: 類似度閾値（Noneの場合は設定値を使用）
            apply_threshold: 閾値フィルタリングを適用するか（Falseの場合は生の類似度スコアを返す）

        Returns:
            検索結果のリスト

        Raises:
            ValueError: 無効なsource_typeが指定された場合
        """
        from ..config import settings
        from ..constants import DatabaseConstants, SearchConstants

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
                    # ⚠️ 重要: WHERE c.embedding IS NOT NULL 条件は必須です
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
                            1 - (c.embedding <=> $1::{vector_cast}({vector_dimension})) as similarity
                        FROM knowledge_chunks c
                        JOIN knowledge_sources s ON c.source_id = s.id
                        WHERE c.embedding IS NOT NULL
                    """

                    params = [query_embedding]
                    param_index = 2

                    # フィルタの適用
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
                                raise ValueError(
                                    f"Invalid source_types: {invalid_types}."
                                )

                            query += (
                                f" AND s.type = ANY(${param_index}::source_type_enum[])"
                            )
                            params.append(source_types)
                            param_index += 1

                        if "channel_id" in filters:
                            try:
                                channel_id = int(filters["channel_id"])
                            except (ValueError, TypeError):
                                raise ValueError(
                                    "Invalid channel_id: must be an integer."
                                )
                            query += f" AND (s.metadata->>'channel_id')::bigint = ${param_index}"
                            params.append(channel_id)
                            param_index += 1

                        if "user_id" in filters:
                            try:
                                user_id = int(filters["user_id"])
                            except (ValueError, TypeError):
                                raise ValueError("Invalid user_id: must be an integer.")
                            query += f" AND (s.metadata->>'author_id')::bigint = ${param_index}"
                            params.append(user_id)
                            param_index += 1

                    # 類似度でソート
                    if apply_threshold:
                        # 閾値フィルタリングを適用
                        query += f"""
                            AND 1 - (c.embedding <=> $1::{vector_cast}({vector_dimension})) >= ${param_index}
                            ORDER BY c.embedding <=> $1::{vector_cast}({vector_dimension})
                            LIMIT ${param_index + 1}
                        """
                        params.append(similarity_threshold)
                        params.append(min(top_k, top_k_limit))
                    else:
                        # 閾値フィルタリングを適用せず、生の類似度スコアを返す
                        query += f"""
                            ORDER BY c.embedding <=> $1::{vector_cast}({vector_dimension})
                            LIMIT ${param_index}
                        """
                        params.append(min(top_k, top_k_limit))

                    # 安全チェック
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
        except asyncpg.PostgresConnectionError as e:
            logger.error(f"Database connection failed: {e}")
            raise RuntimeError(f"Database connection failed: {e}") from e
        except Exception as e:
            logger.error(f"Error during similarity search: {e}", exc_info=True)
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
                    "similarity": float(row["similarity"]),
                }
            )
            for row in rows
        ]

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

    async def save_chunk(
        self,
        source_id: int,
        content: str,
        location: dict | None = None,
        token_count: int | None = None,
    ) -> int:
        """知識チャンクを保存し、IDを返す"""
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
