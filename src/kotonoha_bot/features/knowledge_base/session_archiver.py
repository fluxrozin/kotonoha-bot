"""セッションの知識化処理"""

import asyncio
import random
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

import structlog
import tiktoken
from discord.ext import tasks

if TYPE_CHECKING:
    from ...db.postgres import PostgreSQLDatabase
    from ...external.embedding import EmbeddingProvider

logger = structlog.get_logger(__name__)


class SessionArchiver:
    """セッションを知識ベースに変換するクラス"""

    def __init__(
        self,
        db: PostgreSQLDatabase,
        embedding_provider: EmbeddingProvider,
        bot=None,  # Botインスタンス（tasks.loopに必要）
        archive_threshold_hours: int | None = None,
    ):
        self.db = db
        self.embedding_provider = embedding_provider
        self.bot = bot  # Botインスタンスを保存
        # 環境変数から設定を読み込み（デフォルト値あり）
        from ...config import settings

        self.archive_threshold_hours = (
            archive_threshold_hours or settings.kb_archive_threshold_hours
        )
        logger.debug(
            f"SessionArchiver.__init__: archive_threshold_hours={self.archive_threshold_hours}, "
            f"archive_interval_hours={settings.kb_archive_interval_hours}, "
            f"batch_size={settings.kb_archive_batch_size}"
        )
        self._processing = False
        # ⚠️ 改善（コード品質）: Graceful Shutdownの改善
        # 処理中のアーカイブタスクを追跡するためのセット
        self._processing_sessions: set = set()
        logger.debug("SessionArchiver initialized")

    @tasks.loop(hours=1)  # デフォルト値（start()で動的に変更される）
    async def archive_inactive_sessions(self):
        """非アクティブなセッションを知識ベースに変換"""
        if self._processing:
            logger.debug("Session archiving already in progress, skipping...")
            return

        try:
            self._processing = True
            logger.debug("Starting session archiving...")

            # ⚠️ 改善（コード品質）: pydantic-settings を使用
            from ...config import settings

            # 設定値から閾値とバッチサイズを読み込み
            archive_threshold_hours = self.archive_threshold_hours
            batch_size = settings.kb_archive_batch_size

            # 閾値時間以上非アクティブなセッションを取得
            threshold_time = datetime.now() - timedelta(hours=archive_threshold_hours)

            # 接続プール枯渇時のタイムアウト処理を追加
            try:
                from asyncio import timeout

                # 接続取得にタイムアウトを設定
                async with timeout(30.0):
                    async with self.db.pool.acquire() as conn:
                        inactive_sessions = await conn.fetch(
                            """
                            SELECT id, session_key, session_type, messages,
                                   guild_id, channel_id, thread_id,
                                   user_id, last_active_at, version,
                                   last_archived_message_index
                            FROM sessions
                            WHERE status = 'active'
                            AND last_active_at < $1
                            ORDER BY last_active_at ASC
                            LIMIT $2
                        """,
                            threshold_time,
                            batch_size,
                        )
            except TimeoutError:
                logger.error("Failed to acquire database connection: pool exhausted")
                return
            except Exception as e:
                logger.error(f"Error acquiring connection: {e}", exc_info=True)
                return

            if not inactive_sessions:
                logger.debug("No inactive sessions to archive")
                return

            logger.info(f"Archiving {len(inactive_sessions)} inactive sessions...")

            # ⚠️ 重要: セッションアーカイブの並列処理（高速化）
            # セマフォで同時実行数を制限しつつ並列処理（DBへの負荷に注意）
            # ⚠️ 接続枯渇対策: セマフォの上限を DB_POOL_MAX_SIZE の20〜30%程度に厳密に制限
            max_pool_size = settings.db_pool_max_size
            # 20〜30%程度に制限（最小1、最大5）
            archive_concurrency = max(1, min(5, int(max_pool_size * 0.25)))
            archive_semaphore = asyncio.Semaphore(archive_concurrency)
            logger.debug(
                f"Archive semaphore limit: {archive_concurrency} "
                f"(pool max_size: {max_pool_size})"
            )

            async def _archive_with_limit(session_row):
                """セマフォで制限されたアーカイブ処理"""
                async with archive_semaphore:
                    try:
                        await self._archive_session(session_row)
                    except Exception as e:
                        logger.error(
                            f"Failed to archive session "
                            f"{session_row['session_key']}: {e}",
                            exc_info=True,
                        )

            # 並列処理（return_exceptions=Trueで例外を返す）
            await asyncio.gather(
                *[_archive_with_limit(s) for s in inactive_sessions],
                return_exceptions=True,
            )

            logger.info(f"Successfully archived {len(inactive_sessions)} sessions")

        except Exception as e:
            logger.error(f"Error during session archiving: {e}", exc_info=True)
        finally:
            self._processing = False

    @archive_inactive_sessions.before_loop
    async def before_archive_sessions(self):
        """タスク開始前の待機

        ⚠️ 重要: Bot再起動時のバーストを防ぐため、ランダムな遅延を追加
        現状の「最終アクティブから1時間」のみだと、Bot再起動時に大量のアーカイブ処理が走る可能性があります。
        limit 付きで処理している点は良いですが、起動直後のバーストを防ぐため、
        タスク開始時にランダムな遅延を追加して分散させます。
        """
        if self.bot:
            await self.bot.wait_until_ready()
        logger.info(
            f"Session archiver starting with interval={self.archive_threshold_hours} hours"
        )
        # 0〜60秒のランダムな遅延を追加（起動直後のバーストを防ぐ）
        delay = random.uniform(0, 60)
        logger.debug(f"Archive task will start after {delay:.1f}s delay")
        await asyncio.sleep(delay)

    async def _archive_session(self, session_row: dict):
        """セッションを知識ベースに変換

        ⚠️ 重要: 楽観的ロックの競合時は自動リトライ（tenacity使用）
        Botが高頻度で使われている場合、アーカイブが何度も失敗し続ける可能性があるため、
        競合時のリトライ（バックオフ付き）を実装しています。
        """
        from tenacity import (
            retry,
            retry_if_exception_type,
            stop_after_attempt,
            wait_exponential,
        )

        @retry(
            stop=stop_after_attempt(3),  # 最大3回リトライ
            # 指数バックオフ: 1秒、2秒、4秒
            wait=wait_exponential(multiplier=1, min=1, max=10),
            # ValueError（楽観的ロック競合）のみリトライ
            retry=retry_if_exception_type(ValueError),
            reraise=True,  # 最終的に失敗した場合は例外を再発生
        )
        async def _archive_session_with_retry():
            # ⚠️ 改善: 処理中のタスクを追跡
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
        アーカイブ処理が走り、データが長期記憶へ移動した直後にユーザーが発言すると、
        直前の文脈が短期記憶から消えているため、Botが「何の話でしたっけ？」となってしまう現象を防ぐ。

        改善策: アーカイブ時に短期記憶を「全消去」するのではなく、
        「直近の数メッセージ（のりしろ）」を残して更新（Prune）する設計にします。
        """
        from ...config import settings

        session_key = session_row["session_key"]
        # ⚠️ 注意: JSONBコーデックが設定されていれば、自動的にlist[dict]に変換される
        messages = session_row["messages"]
        original_version = session_row.get("version", 1)
        # ⚠️ 改善: 現在のアーカイブ済み地点を取得
        current_archived_index = session_row.get("last_archived_message_index", 0)

        if not messages:
            logger.debug(f"Skipping empty session: {session_key}")
            return

        # ⚠️ 改善: アーカイブ対象のメッセージを取得（last_archived_message_index 以降のみ）
        # ⚠️ 重要（Critical Bug Fix）: messages配列を切り詰めた場合、
        # last_archived_message_index は 0 にリセットされている
        if current_archived_index >= len(messages):
            logger.warning(
                f"Session {session_key}: "
                f"last_archived_message_index ({current_archived_index}) "
                f"exceeds messages length ({len(messages)}), resetting to 0"
            )
            current_archived_index = 0

        messages_to_archive = messages[current_archived_index:]

        if not messages_to_archive:
            # アーカイブ対象がない場合（すべてアーカイブ済み）、status='archived' に更新して終了
            async with self.db.pool.acquire() as conn, conn.transaction():
                await conn.execute(
                    """
                        UPDATE sessions
                        SET status = 'archived',
                            version = version + 1
                        WHERE session_key = $1
                        AND version = $2
                    """,
                    session_key,
                    original_version,
                )
            return

        # フィルタリング: 短すぎるセッションやBotのみのセッションを除外
        if not self._should_archive_session(messages_to_archive):
            logger.debug(f"Skipping low-value session: {session_key}")
            # アーカイブしないが、last_archived_message_index を更新（再処理を避ける）
            async with self.db.pool.acquire() as conn, conn.transaction():
                await conn.execute(
                    """
                        UPDATE sessions
                        SET status = 'archived',
                            last_archived_message_index = $3,
                            version = version + 1
                        WHERE session_key = $1
                        AND version = $2
                    """,
                    session_key,
                    original_version,
                    len(messages),
                )
            return

        encoding = tiktoken.encoding_for_model("text-embedding-3-small")
        MAX_EMBEDDING_TOKENS = settings.kb_chunk_max_tokens

        # 環境変数からチャンク化戦略を選択
        chunk_strategy = settings.kb_chat_chunk_strategy

        # ⚠️ 改善: アーカイブ対象のメッセージ（messages_to_archive）を使用
        if chunk_strategy == "message_based":
            # ⚠️ 推奨: メッセージ単位/会話ターン単位でのチャンク化
            chunks = self._chunk_messages_by_turns(
                messages_to_archive, MAX_EMBEDDING_TOKENS, encoding
            )
        else:
            # 従来方式: 文字数ベースの分割（フォールバック）
            content = self._format_messages_for_knowledge(messages_to_archive)
            token_count = len(encoding.encode(content))

            if token_count > MAX_EMBEDDING_TOKENS:
                logger.warning(
                    f"Session {session_key} exceeds token limit "
                    f"({token_count} > {MAX_EMBEDDING_TOKENS}), splitting..."
                )
                chunks = self._split_content_by_tokens(
                    content, encoding, MAX_EMBEDDING_TOKENS
                )
            else:
                chunks = [content]

        # タイトルを生成（最初のユーザーメッセージから）
        title = self._generate_title(messages_to_archive)

        # URIを生成（Discord URL）
        uri = self._generate_discord_uri(session_row)

        # メタデータを構築
        session_id = session_row.get("id")
        metadata = {
            "channel_id": session_row.get("channel_id"),
            "thread_id": session_row.get("thread_id"),
            "user_id": session_row.get("user_id"),
            "session_type": session_row["session_type"],
            "archived_at": datetime.now().isoformat(),
            # ⚠️ 改善（疎結合）: 紐付け情報を metadata に記録（外部キー制約なし）
            "origin_session_id": session_id,
            "origin_session_key": session_key,
        }

        # ⚠️ 重要: すべての操作を1つのアトミックなトランザクション内で実行
        async with self.db.pool.acquire() as conn:
            # ⚠️ 重要: トランザクション分離レベルを REPEATABLE READ に設定（楽観的ロックのため）
            async with conn.transaction(isolation="repeatable_read"):
                # 1. knowledge_sources に登録（status='pending'）
                source_id = await conn.fetchval(
                    """
                    INSERT INTO knowledge_sources (type, title, uri, metadata, status)
                    VALUES ($1, $2, $3, $4::jsonb, 'pending')
                    RETURNING id
                """,
                    "discord_session",
                    title,
                    uri,
                    metadata,
                )

                # 2. knowledge_chunks に登録（複数チャンクに対応）
                for i, chunk_content in enumerate(chunks):
                    chunk_token_count = len(encoding.encode(chunk_content))
                    location = {
                        "url": uri,
                        "label": f"チャンク {i + 1}/{len(chunks)}",
                        "session_key": session_key,
                        "chunk_index": i,
                        "total_chunks": len(chunks),
                    }
                    await conn.execute(
                        """
                        INSERT INTO knowledge_chunks
                        (source_id, content, embedding, location, token_count)
                        VALUES ($1, $2, NULL, $3::jsonb, $4)
                    """,
                        source_id,
                        chunk_content,
                        location,
                        chunk_token_count,
                    )

                # アーカイブ済み地点を記録（将来の差分アーカイブ用）
                archived_message_count = len(messages)
                archived_until_timestamp = None
                if messages:
                    last_msg = messages[-1]
                    archived_until_timestamp = last_msg.get("timestamp")
                    if not archived_until_timestamp:
                        archived_until_timestamp = last_msg.get("created_at")

                metadata["archived_message_count"] = archived_message_count
                if archived_until_timestamp:
                    metadata["archived_until_timestamp"] = archived_until_timestamp

                # knowledge_sources の metadata を更新（アーカイブ済み地点を記録）
                await conn.execute(
                    """
                    UPDATE knowledge_sources
                    SET metadata = $1::jsonb
                    WHERE id = $2
                """,
                    metadata,
                    source_id,
                )

                # ⚠️ 改善（会話の分断対策）: スライディングウィンドウ（のりしろ）方式
                KB_ARCHIVE_OVERLAP_MESSAGES = settings.kb_archive_overlap_messages

                # アーカイブ済み地点を計算
                new_archived_index = current_archived_index + len(messages_to_archive)

                # すべてのメッセージがアーカイブ済みかどうかを判定
                all_messages_archived = new_archived_index >= len(messages)

                if all_messages_archived:
                    # すべてのメッセージがアーカイブ済みの場合
                    overlap_messages = (
                        messages[-KB_ARCHIVE_OVERLAP_MESSAGES:]
                        if len(messages) > KB_ARCHIVE_OVERLAP_MESSAGES
                        else messages
                    )

                    reset_index = 0

                    result = await conn.execute(
                        """
                        UPDATE sessions
                        SET status = 'archived',
                            messages = $3::jsonb,
                            last_archived_message_index = $4,
                            version = version + 1
                        WHERE session_key = $1
                        AND status = 'active'
                        AND version = $2
                    """,
                        session_key,
                        original_version,
                        overlap_messages,
                        reset_index,
                    )
                else:
                    # 一部のみアーカイブ済みの場合
                    remaining_messages = messages[new_archived_index:]
                    overlap_messages = (
                        remaining_messages[-KB_ARCHIVE_OVERLAP_MESSAGES:]
                        if len(remaining_messages) > KB_ARCHIVE_OVERLAP_MESSAGES
                        else remaining_messages
                    )

                    reset_index = 0

                    result = await conn.execute(
                        """
                        UPDATE sessions
                        SET messages = $3::jsonb,
                            last_archived_message_index = $4,
                            version = version + 1
                        WHERE session_key = $1
                        AND status = 'active'
                        AND version = $2
                    """,
                        session_key,
                        original_version,
                        overlap_messages,
                        reset_index,
                    )

                # asyncpgのexecuteは "UPDATE N" 形式の文字列を返す
                if result == "UPDATE 0":
                    logger.warning(
                        f"Session {session_key} was updated during archiving, "
                        f"rolling back transaction to prevent duplicate "
                        f"archive (will retry)"
                    )
                    raise ValueError(
                        f"Session {session_key} was concurrently updated, "
                        f"archiving aborted to prevent duplicate"
                    )

        # トランザクションが正常にコミットされた場合のみ、このログが出力されます
        logger.info(
            f"Archived session {session_key} as knowledge source {source_id} "
            f"({len(chunks)} chunks)"
        )

    def _should_archive_session(self, messages: list[dict]) -> bool:
        """セッションをアーカイブすべきか判定（フィルタリング）"""
        from ...config import settings

        # 文字数チェック
        total_length = sum(len(msg.get("content", "")) for msg in messages)
        if total_length < settings.kb_min_session_length:
            return False

        # Botのみのセッションを除外（ユーザー発言がない）
        has_user_message = any(msg.get("role") == "user" for msg in messages)
        if not has_user_message:
            return False

        return True

    def _format_messages_for_knowledge(self, messages: list[dict]) -> str:
        """メッセージを知識ベース用のテキストに整形"""
        formatted = []
        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            formatted.append(f"{role.capitalize()}: {content}")
        return "\n".join(formatted)

    def _chunk_messages_by_turns(
        self,
        messages: list[dict],
        max_tokens: int,
        encoding: tiktoken.Encoding,
    ) -> list[str]:
        """メッセージを会話のターン単位でチャンク化

        ⚠️ 重要（Semantic Issues）: チャットログは「会話の流れ」が重要です。
        単純に文字数で切ると、「ユーザーの質問」と「Botの回答」が別々のチャンクに
        分断されるリスクがあります。これにより、検索精度（質問に対する回答の適合率）が
        著しく低下します。

        改善案: 文字数分割ではなく、「メッセージ単位」または「会話のやり取り（ターン）単位」
        でのグルーピングを推奨します。

        Args:
            messages: メッセージのリスト（各要素は {'role': str, 'content': str}）
            max_tokens: 1チャンクあたりの最大トークン数
            encoding: tiktokenエンコーディング

        Returns:
            チャンク化されたテキストのリスト
        """
        from ...config import settings

        # 環境変数からチャンクサイズ（メッセージ数）を取得
        chunk_size_messages = settings.kb_chat_chunk_size_messages
        overlap_messages = settings.kb_chat_chunk_overlap_messages

        chunks = []
        i = 0

        while i < len(messages):
            # 現在のチャンクに含めるメッセージを取得
            chunk_messages = messages[i : i + chunk_size_messages]

            # チャンクをテキストに整形
            chunk_text = self._format_messages_for_knowledge(chunk_messages)
            chunk_tokens = len(encoding.encode(chunk_text))

            # トークン数が上限を超えている場合、メッセージ数を減らす
            if chunk_tokens > max_tokens:
                # メッセージ数を減らしながら再試行
                reduced_size = max(1, chunk_size_messages - 1)
                chunk_messages = messages[i : i + reduced_size]
                chunk_text = self._format_messages_for_knowledge(chunk_messages)
                chunk_tokens = len(encoding.encode(chunk_text))

                # それでも超える場合は、RecursiveCharacterTextSplitterにフォールバック
                if chunk_tokens > max_tokens:
                    logger.warning(
                        f"Chunk exceeds token limit "
                        f"({chunk_tokens} > {max_tokens}), "
                        f"falling back to RecursiveCharacterTextSplitter"
                    )
                    # フォールバック: 文字数ベースの分割
                    sub_chunks = self._split_content_by_tokens(
                        chunk_text, encoding, max_tokens
                    )
                    chunks.extend(sub_chunks)
                    # 次のチャンクへ（オーバーラップなし）
                    i += reduced_size
                    continue

            chunks.append(chunk_text)

            # スライディングウィンドウ: オーバーラップ分だけ進む
            i += max(1, chunk_size_messages - overlap_messages)

        return chunks

    def _split_content_by_tokens(
        self, content: str, encoding: tiktoken.Encoding, max_tokens: int
    ) -> list[str]:
        """コンテンツをトークン数上限に基づいて分割

        ⚠️ 重要: 自前実装は複雑でバグが発生しやすいため、
        langchain-text-splitters の使用を強く推奨します。

        このメソッドは、langchain-text-splitters が利用できない場合のフォールバック実装です。
        """
        from ...config import settings

        # ⚠️ 推奨: langchain-text-splitters を使用する実装
        try:
            from langchain_text_splitters import RecursiveCharacterTextSplitter

            overlap_ratio = settings.kb_chunk_overlap_ratio

            splitter = RecursiveCharacterTextSplitter(
                chunk_size=max_tokens,
                chunk_overlap=int(max_tokens * overlap_ratio),
                length_function=lambda text: len(encoding.encode(text)),
                separators=["\n\n", "\n", "。", ".", "、", ",", " ", ""],
            )
            return splitter.split_text(content)
        except ImportError:
            # フォールバック: 自前実装（簡易版）
            logger.warning(
                "langchain-text-splitters not available, using fallback implementation"
            )
            return self._split_content_by_tokens_fallback(content, encoding, max_tokens)

    def _split_content_by_tokens_fallback(
        self, content: str, encoding: tiktoken.Encoding, max_tokens: int
    ) -> list[str]:
        """フォールバック実装（簡易版）"""
        from ...config import settings

        tokens = encoding.encode(content)
        if len(tokens) <= max_tokens:
            return [content]

        chunks = []
        start = 0
        overlap_ratio = settings.kb_chunk_overlap_ratio
        overlap_tokens = int(max_tokens * overlap_ratio)

        while start < len(tokens):
            end = min(start + max_tokens, len(tokens))
            chunk_tokens = tokens[start:end]
            chunk_text = encoding.decode(chunk_tokens)

            if end >= len(tokens):
                chunks.append(chunk_text)
                break

            # 簡易分割: 改行や句読点で分割を試みる
            separators = ["\n\n", "\n", "。", ".", "、", ","]
            best_split_pos = len(chunk_text)

            for separator in separators:
                pos = chunk_text.rfind(separator)
                if pos > len(chunk_text) * 0.5:
                    best_split_pos = pos + len(separator)
                    break

            final_chunk = chunk_text[:best_split_pos].strip()
            if final_chunk:
                chunks.append(final_chunk)

            # オーバーラップを考慮して次の開始位置を計算
            if best_split_pos > overlap_tokens:
                overlap_text = chunk_text[
                    best_split_pos - overlap_tokens : best_split_pos
                ]
                overlap_tokens_count = len(encoding.encode(overlap_text))
                start = start + len(encoding.encode(final_chunk)) - overlap_tokens_count
            else:
                start = start + len(encoding.encode(final_chunk))

        return chunks

    def _generate_title(self, messages: list[dict]) -> str:
        """セッションのタイトルを生成"""
        # 最初のユーザーメッセージから生成
        for msg in messages:
            if msg.get("role") == "user":
                content = msg.get("content", "")
                # 最初の50文字をタイトルに
                title = content[:50].strip()
                if len(content) > 50:
                    title += "..."
                return title or "Discord Session"
        return "Discord Session"

    def _generate_discord_uri(self, session_row: dict) -> str | None:
        """Discord URLを生成
        （正しい形式: /channels/{guild_id}/{channel_id}/{message_id}）"""
        channel_id = session_row.get("channel_id")
        thread_id = session_row.get("thread_id")
        guild_id = session_row.get("guild_id")

        if not channel_id:
            return None

        # Guild IDがない場合は、チャンネルIDのみの形式（不完全だが動作する）
        if guild_id:
            if thread_id:
                return (
                    f"https://discord.com/channels/{guild_id}/{channel_id}/{thread_id}"
                )
            else:
                return f"https://discord.com/channels/{guild_id}/{channel_id}"
        else:
            # フォールバック: Guild IDがない場合（将来的に修正が必要）
            logger.warning("Guild ID not found for session, using incomplete URL")
            if thread_id:
                return f"https://discord.com/channels/{channel_id}/{thread_id}"
            else:
                return f"https://discord.com/channels/{channel_id}"

    def start(self):
        """バックグラウンドタスクを開始（動的に間隔を設定）"""
        from ...config import settings

        # 環境変数から読み込んだ間隔を設定
        interval_hours = settings.kb_archive_interval_hours
        logger.info(
            f"Starting session archiver: interval={interval_hours} hours, "
            f"threshold={self.archive_threshold_hours} hours"
        )
        logger.debug(f"Bot instance set: {self.bot is not None}")
        self.archive_inactive_sessions.change_interval(hours=interval_hours)
        logger.debug(f"Changed interval to {interval_hours} hours")
        self.archive_inactive_sessions.start()
        logger.info("Session archiver task started successfully")
        logger.debug(f"Task running: {self.archive_inactive_sessions.is_running()}")

    async def graceful_shutdown(self):
        """Graceful Shutdown: 処理中のタスクが完了するまで待機

        ⚠️ 改善（コード品質）: session_archiverのGraceful Shutdownが
        embedding_processorほど詳細に定義されていませんでした。
        以下の改善を追加します:
        - 処理中のアーカイブタスクの完了待機
        - タイムアウト処理
        - エラーハンドリング
        """
        logger.info("Stopping session archiver gracefully...")

        # タスクをキャンセル
        self.archive_inactive_sessions.cancel()

        # 処理中のタスクが完了するまで待機
        try:
            # タスクが存在する場合、完了を待つ
            task = getattr(self.archive_inactive_sessions, "_task", None)
            if task and not task.done():
                try:
                    from asyncio import timeout

                    # 最大60秒待機
                    async with timeout(60.0):
                        await task
                except TimeoutError:
                    logger.warning(
                        "Session archiving task did not complete within timeout"
                    )
                except asyncio.CancelledError:
                    logger.debug("Session archiving task was cancelled")

            # ⚠️ 改善: 処理中のアーカイブ処理（_archive_session）の完了待機
            if self._processing_sessions:
                logger.info(
                    f"Waiting for {len(self._processing_sessions)} "
                    f"active archive tasks to complete..."
                )
                try:
                    from asyncio import gather, timeout

                    async with timeout(120.0):  # 最大120秒待機（並列処理の場合）
                        await gather(*self._processing_sessions, return_exceptions=True)
                except TimeoutError:
                    logger.warning("Some archive tasks did not complete within timeout")
                except Exception as e:
                    logger.error(
                        f"Error waiting for archive tasks: {e}",
                        exc_info=True,
                    )
        except Exception as e:
            logger.error(f"Error during graceful shutdown: {e}", exc_info=True)

        logger.info("Session archiver stopped")
