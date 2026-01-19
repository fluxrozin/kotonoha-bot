"""Embedding処理のバックグラウンドタスク"""

import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, cast

import asyncpg
import structlog
from discord.ext import tasks

from .metrics import (
    embedding_errors_counter,
    embedding_processed_counter,
    embedding_processing_duration,
    pending_chunks_gauge,
)

if TYPE_CHECKING:
    from ...db.postgres import PostgreSQLDatabase
    from ...external.embedding import EmbeddingProvider

logger = structlog.get_logger(__name__)


class EmbeddingProcessor:
    """Embedding処理を管理するクラス"""

    def __init__(
        self,
        db: PostgreSQLDatabase,
        embedding_provider: EmbeddingProvider,
        bot=None,  # Botインスタンス（tasks.loopに必要）
        batch_size: int | None = None,
        max_concurrent: int | None = None,
    ):
        self.db = db
        self.embedding_provider = embedding_provider
        self.bot = bot  # Botインスタンスを保存
        # 環境変数から設定を読み込み（デフォルト値あり）
        from ...config import settings

        self.batch_size = batch_size or settings.kb_embedding_batch_size
        max_concurrent = max_concurrent or settings.kb_embedding_max_concurrent

        logger.info(
            f"EmbeddingProcessor.__init__: batch_size={self.batch_size}, "
            f"max_concurrent={max_concurrent}, "
            f"interval_minutes={settings.kb_embedding_interval_minutes}"
        )

        # ⚠️ 重要: セマフォによる同時実行数制限
        # 接続プール枯渇対策: DB_POOL_MAX_SIZEの20〜30%程度に制限
        # これにより、Embedding処理だけでプールを食い尽くし、通常のチャット応答が
        # タイムアウトするリスクを防ぎます
        self._semaphore = asyncio.Semaphore(max_concurrent)  # レート制限用セマフォ
        self._lock = asyncio.Lock()  # 競合状態対策

        # ⚠️ 重要: @tasks.loop デコレータのパラメータはクラス定義時に評価されるため、
        # 環境変数の遅延読み込みが必要な場合は、__init__で間隔を保存し、
        # start()メソッドでchange_interval()を呼び出します。
        self._interval = settings.kb_embedding_interval_minutes
        logger.info(
            f"EmbeddingProcessor initialized: interval={self._interval} minutes"
        )

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
    async def process_pending_embeddings_error(self, error: BaseException):
        """タスクエラー時のハンドラ"""
        logger.error(f"Embedding task error: {error}", exc_info=True)
        # 必要に応じてアラート送信など

    @process_pending_embeddings.before_loop
    async def before_process_embeddings(self):
        """タスク開始前の待機"""
        if self.bot:
            await self.bot.wait_until_ready()
        logger.info(
            f"Embedding processor starting with interval={self._interval} minutes, "
            f"batch_size={self.batch_size}, max_concurrent={self._semaphore._value}"
        )

    async def _process_pending_embeddings_impl(self):
        """Embedding処理の実装（エラーハンドリング分離）"""
        # 競合状態対策: asyncio.Lockを使用
        if self._lock.locked():
            logger.debug("Embedding processing already in progress, skipping...")
            return

        # メトリクス: 処理時間の計測開始
        start_time = time.time()

        async with self._lock:
            logger.info("Starting embedding processing...")

            # ⚠️ 重要: Dead Letter Queue対応 - retry_countを考慮
            from ...config import settings
            from ...constants import SearchConstants

            MAX_RETRY_COUNT = settings.kb_embedding_max_retry
            vector_cast = SearchConstants.VECTOR_CAST
            vector_dimension = SearchConstants.VECTOR_DIMENSION

            # ⚠️ 重要: トランザクション内でのAPIコールを回避するため、
            # Tx1: FOR UPDATE SKIP LOCKED で対象行を取得し、IDとcontentをメモリに保持して即コミット
            # No Tx: OpenAI API コール（時間かかる）
            # Tx2: 結果を UPDATE

            # Tx1: 対象チャンクを取得（FOR UPDATE SKIP LOCKEDでロック）
            assert self.db.pool is not None, "Database pool must be initialized"
            async with (
                self.db.pool.acquire() as conn,
                conn.transaction(),
            ):
                # FOR UPDATE SKIP LOCKED でロックを取得し、他のプロセスと競合しないようにする
                # ⚠️ 改善（パフォーマンス）: idx_chunks_queue 部分インデックスが使用される
                pending_chunks = await conn.fetch(
                    """
                        SELECT id, content, source_id, retry_count
                        FROM knowledge_chunks
                        WHERE embedding IS NULL
                        AND retry_count < $1
                        ORDER BY id ASC
                        LIMIT $2
                        FOR UPDATE SKIP LOCKED
                    """,
                    MAX_RETRY_COUNT,
                    self.batch_size,
                )
                # トランザクションを即コミット（ロックを解放）

            if not pending_chunks:
                logger.info("No pending chunks to process")
                # メトリクス: pendingチャンク数を更新
                pending_chunks_gauge.set(0)
                return

            logger.info(f"Processing {len(pending_chunks)} pending chunks...")
            # メトリクス: pendingチャンク数を更新
            pending_chunks_gauge.set(len(pending_chunks))

            # No Tx: OpenAI Embedding APIのバッチリクエスト（時間かかる処理）
            # ⚠️ 重要: この時点ではトランザクションを保持していないため、
            # 接続プールが枯渇したり、他のクエリをブロックしない
            texts = [chunk["content"] for chunk in pending_chunks]
            try:
                embeddings = await self._generate_embeddings_batch(texts)
            except Exception as e:
                # Embedding API全体障害時の処理: 失敗したチャンクのretry_countをインクリメント
                error_code = self._classify_error(e)
                logger.error(
                    f"Embedding API failed for batch: {error_code}",
                    exc_info=True,
                )
                # メトリクス: エラーを記録
                embedding_errors_counter.labels(error_type=error_code).inc()
                # Tx2: エラー時の更新（別トランザクション）
                assert self.db.pool is not None, "Database pool must be initialized"
                async with (
                    self.db.pool.acquire() as conn,
                    conn.transaction(),
                ):
                    for chunk in pending_chunks:
                        # retry_countをインクリメント
                        new_retry_count = await conn.fetchval(
                            """
                                UPDATE knowledge_chunks
                                SET retry_count = COALESCE(retry_count, 0) + 1
                                WHERE id = $1
                                RETURNING retry_count
                            """,
                            chunk["id"],
                        )

                        # ⚠️ 改善（データ整合性）: DLQへの移動ロジックを追加
                        if new_retry_count >= MAX_RETRY_COUNT:
                            # retry_countを更新したchunkを渡す
                            chunk_with_updated_retry = dict(chunk)
                            chunk_with_updated_retry["retry_count"] = new_retry_count
                            await self._move_to_dlq(
                                cast(asyncpg.Connection, conn),
                                chunk_with_updated_retry,
                                e,
                            )

                    # retry_countが上限に達したソースはfailedに
                    source_ids = {chunk["source_id"] for chunk in pending_chunks}
                    for source_id in source_ids:
                        failed_count = await conn.fetchval(
                            """
                                SELECT COUNT(*)
                                FROM knowledge_chunks
                                WHERE source_id = $1
                                AND retry_count >= $2
                            """,
                            source_id,
                            MAX_RETRY_COUNT,
                        )

                        if failed_count > 0:
                            error_code = "EMBEDDING_MAX_RETRIES_EXCEEDED"
                            error_message = (
                                f"Embedding failed after {MAX_RETRY_COUNT} retries"
                            )
                            await conn.execute(
                                """
                                    UPDATE knowledge_sources
                                    SET status = 'failed',
                                        error_code = $1,
                                        error_message = $2,
                                        updated_at = CURRENT_TIMESTAMP
                                    WHERE id = $3
                                """,
                                error_code,
                                error_message,
                                source_id,
                            )
                return  # 処理を中断

            # Tx2: 結果を UPDATE（別トランザクション）
            # ⚠️ 重要: APIコールが完了してからトランザクションを開始するため、
            # トランザクションの保持時間が最小限になる
            # 正常に処理されたチャンクのみを更新
            successful_chunks = [
                chunk
                for chunk in pending_chunks
                if chunk.get("retry_count", 0) < MAX_RETRY_COUNT
            ]

            if successful_chunks:
                successful_embeddings = [
                    emb
                    for emb, chunk in zip(embeddings, pending_chunks, strict=False)
                    if chunk.get("retry_count", 0) < MAX_RETRY_COUNT
                ]

                assert self.db.pool is not None, "Database pool must be initialized"
                async with (
                    self.db.pool.acquire() as conn,
                    conn.transaction(),
                ):
                    # ⚠️ 改善（パフォーマンス）: executemany のバッチサイズ制御
                    from ...config import settings

                    update_data = [
                        (emb, chunk["id"])
                        for emb, chunk in zip(
                            successful_embeddings, successful_chunks, strict=True
                        )
                    ]
                    BATCH_SIZE = settings.kb_chunk_update_batch_size

                    for i in range(0, len(update_data), BATCH_SIZE):
                        batch = update_data[i : i + BATCH_SIZE]
                        await conn.executemany(
                            f"""
                                UPDATE knowledge_chunks
                                SET embedding = $1::{vector_cast}({vector_dimension}),
                                    retry_count = 0
                                WHERE id = $2
                            """,
                            batch,
                        )

            # Sourceのステータスも更新
            await self._update_source_status([dict(chunk) for chunk in pending_chunks])

            # メトリクス: 処理時間を記録
            elapsed_time = time.time() - start_time
            embedding_processing_duration.observe(elapsed_time)

            # メトリクス: 処理済みチャンク数を記録
            embedding_processed_counter.inc(len(successful_chunks))

            # メトリクス: pendingチャンク数を更新
            pending_chunks_gauge.set(0)

            logger.info(f"Successfully processed {len(successful_chunks)} chunks")

    async def _generate_embedding_with_limit(self, text: str) -> list[float]:
        """セマフォで制限されたEmbedding生成（レート制限対策）

        ⚠️ 重要: セマフォによる同時実行数制限の実装
        - EmbeddingProcessorの初期化時にセマフォを作成（max_concurrentで制限）
        - このメソッド内で `async with self._semaphore:` を使用して同時実行数を制限
        - 接続プール枯渇対策: DB_POOL_MAX_SIZEの20〜30%程度に制限
        """
        async with self._semaphore:
            result = await self.embedding_provider.generate_embedding(text)
            await asyncio.sleep(0.05)  # APIごとの間隔
            return result

    async def _generate_embeddings_batch(self, texts: list[str]) -> list[list[float]]:
        """複数のテキストをバッチでベクトル化

        ⚠️ 改善: OpenAI Embedding APIはバッチリクエストをサポートしているため、
        個別にAPIを呼ぶのではなく、バッチで一度に送信することで効率化します。
        API呼び出し回数を大幅に削減（100回→1回）、レート制限にかかりにくくなります。
        """
        # OpenAI Embedding APIはバッチリクエストをサポート
        if hasattr(self.embedding_provider, "generate_embeddings_batch"):
            # バッチAPIを使用（推奨）
            batch_method = getattr(
                self.embedding_provider, "generate_embeddings_batch", None
            )
            if batch_method:
                return await cast(
                    Callable[[list[str]], Awaitable[list[list[float]]]], batch_method
                )(texts)
            # hasattrがTrueなのにメソッドが取得できない場合はフォールバック
            logger.warning(
                "generate_embeddings_batch attribute exists but is not callable, "
                "using fallback"
            )

        # フォールバック: 個別に呼び出す（非効率だが動作する）
        logger.warning("Batch embedding API not available, using individual calls")
        embeddings = await asyncio.gather(
            *[self._generate_embedding_with_limit(text) for text in texts]
        )
        return embeddings

    async def _move_to_dlq(
        self, conn: asyncpg.Connection, chunk: dict, error: Exception
    ) -> None:
        """チャンクをDead Letter Queueに移動

        ⚠️ 改善（データ整合性）: knowledge_chunks_dlqテーブルは定義されていますが、
        実際にDLQへ移動するコードが実装計画にありませんでした。
        このメソッドを追加することで、retry_countが上限に達したチャンクを
        DLQに移動し、手動での確認・再処理を可能にします。

        ⚠️ 改善（セキュリティ）: エラーメッセージの情報漏洩リスクを改善
        エラー内容をそのまま保存すると、APIエラーやスタックトレースが含まれる可能性があります。
        エラーコードと一般化されたメッセージのみを保存し、詳細なスタックトレースはログのみに出力します。

        Args:
            conn: データベース接続（トランザクション内）
            chunk: 移動するチャンク（id, source_id, content を含む）
            error: エラーオブジェクト（詳細な情報を含む）
        """
        try:
            # ⚠️ 改善（セキュリティ）: エラーコードと一般化されたメッセージのみを保存
            error_code = self._classify_error(error)
            error_message = self._generalize_error_message(error)

            # 詳細なスタックトレースはログのみに出力（情報漏洩を防ぐ）
            logger.error(
                f"Chunk {chunk['id']} moved to DLQ after "
                f"{chunk.get('retry_count', 0)} retries: {error_code}",
                exc_info=error,  # スタックトレースはログのみ
            )

            # DLQに移動（エラーコードと一般化されたメッセージのみ）
            source_id = chunk.get("source_id")

            # ⚠️ 改善: source_typeとsource_titleを取得（トレーサビリティ向上）
            source_info = None
            if source_id:
                source_info = await conn.fetchrow(
                    """
                    SELECT type, title FROM knowledge_sources WHERE id = $1
                """,
                    source_id,
                )

            source_type = source_info["type"] if source_info else None
            source_title = source_info["title"] if source_info else None

            await conn.execute(
                """
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
                chunk.get("retry_count", 0),
            )

            # ⚠️ 改善（データ整合性）: 元のチャンクを削除（DLQに移動したため、元のテーブルからは削除）
            await conn.execute(
                """
                DELETE FROM knowledge_chunks WHERE id = $1
            """,
                chunk["id"],
            )
        except Exception as e:
            logger.error(
                f"Failed to move chunk {chunk['id']} to DLQ: {e}",
                exc_info=True,
            )

    def _classify_error(self, error: Exception) -> str:
        """エラーを分類してエラーコードを返す

        ⚠️ 改善（セキュリティ）: エラーメッセージの情報漏洩リスクを改善
        エラーオブジェクトからエラーコードを抽出し、一般化されたコードを返します。

        Returns:
            エラーコード（例: 'EMBEDDING_API_TIMEOUT', 'RATE_LIMIT', 'UNKNOWN_ERROR'）
        """
        error_str = str(error).lower()

        # エラータイプとメッセージからエラーコードを分類
        if "timeout" in error_str or "timed out" in error_str:
            return "EMBEDDING_API_TIMEOUT"
        elif "rate limit" in error_str or "429" in error_str:
            return "RATE_LIMIT"
        elif "authentication" in error_str or "401" in error_str:
            return "AUTHENTICATION_ERROR"
        elif "permission" in error_str or "403" in error_str:
            return "PERMISSION_ERROR"
        elif "not found" in error_str or "404" in error_str:
            return "NOT_FOUND"
        elif "server error" in error_str or "500" in error_str:
            return "SERVER_ERROR"
        else:
            return "UNKNOWN_ERROR"

    def _generalize_error_message(self, error: Exception) -> str:
        """エラーメッセージを一般化する

        ⚠️ 改善（セキュリティ）: エラーメッセージの情報漏洩リスクを改善
        詳細なスタックトレースやAPIキーなどの機密情報を含まない、一般化されたメッセージを返します。

        Returns:
            一般化されたエラーメッセージ
        """
        error_code = self._classify_error(error)

        # エラーコードに基づいて一般化されたメッセージを返す
        error_messages = {
            "EMBEDDING_API_TIMEOUT": "Embedding API request timed out",
            "RATE_LIMIT": "Rate limit exceeded",
            "AUTHENTICATION_ERROR": "Authentication failed",
            "PERMISSION_ERROR": "Permission denied",
            "NOT_FOUND": "Resource not found",
            "SERVER_ERROR": "Server error occurred",
            "UNKNOWN_ERROR": "An error occurred during processing",
        }

        return error_messages.get(error_code, "An error occurred during processing")

    async def _update_source_status(self, processed_chunks: list[dict]):
        """Sourceのステータスを更新

        ⚠️ 改善（データ整合性）: knowledge_sources と knowledge_chunks の整合性リスクを改善
        - retry_count >= MAX_RETRY のチャンクが存在する場合の扱いを明確化
        - DLQに移動したチャンクがある場合は 'partial' ステータスを設定
        """
        from ...config import settings

        source_ids = {chunk["source_id"] for chunk in processed_chunks}

        assert self.db.pool is not None, "Database pool must be initialized"
        async with self.db.pool.acquire() as conn:
            for source_id in source_ids:
                MAX_RETRY_COUNT = settings.kb_embedding_max_retry

                # ⚠️ 改善: 完了判定: embedding が NULL で、かつリトライ上限未達のチャンクがないこと
                pending_count = await conn.fetchval(
                    """
                    SELECT COUNT(*) FROM knowledge_chunks
                    WHERE source_id = $1
                      AND embedding IS NULL
                      AND retry_count < $2
                """,
                    source_id,
                    MAX_RETRY_COUNT,
                )

                # ⚠️ 改善: DLQ行きのチャンク数も確認
                dlq_count = await conn.fetchval(
                    """
                    SELECT COUNT(*) FROM knowledge_chunks_dlq
                    WHERE source_id = $1
                """,
                    source_id,
                )

                if pending_count == 0:
                    # ⚠️ 改善: DLQに移動したチャンクがある場合は 'partial'、ない場合は 'completed'
                    new_status = "partial" if dlq_count > 0 else "completed"
                    await conn.execute(
                        """
                        UPDATE knowledge_sources
                        SET status = $1, updated_at = CURRENT_TIMESTAMP
                        WHERE id = $2
                    """,
                        new_status,
                        source_id,
                    )
                    logger.debug(
                        f"Source {source_id} marked as {new_status} "
                        f"(pending: {pending_count}, dlq: {dlq_count})"
                    )

    def start(self):
        """バックグラウンドタスクを開始（動的に間隔を設定）"""
        logger.info(
            f"Starting embedding processor: interval={self._interval} minutes, "
            f"batch_size={self.batch_size}, max_concurrent={self._semaphore._value}"
        )
        logger.debug(f"Bot instance set: {self.bot is not None}")
        # 環境変数から読み込んだ間隔を設定
        self.process_pending_embeddings.change_interval(minutes=self._interval)
        logger.debug(f"Changed interval to {self._interval} minutes")
        self.process_pending_embeddings.start()
        logger.info("Embedding processor task started successfully")
        logger.debug(f"Task running: {self.process_pending_embeddings.is_running()}")

    async def graceful_shutdown(self):
        """Graceful Shutdown: 処理中のタスクが完了するまで待機"""
        logger.info("Stopping embedding processor gracefully...")

        # タスクをキャンセル
        self.process_pending_embeddings.cancel()

        # 処理中のタスクが完了するまで待機
        try:
            # タスクが存在する場合、完了を待つ
            task = getattr(self.process_pending_embeddings, "_task", None)
            if task and not task.done():
                try:
                    from asyncio import timeout

                    async with timeout(30.0):  # 最大30秒待機
                        await task
                except TimeoutError:
                    logger.warning(
                        "Embedding processing task did not complete within timeout"
                    )
                except asyncio.CancelledError:
                    logger.debug("Embedding processing task was cancelled")
        except Exception as e:
            logger.error(f"Error during graceful shutdown: {e}", exc_info=True)

        logger.info("Embedding processor stopped")
