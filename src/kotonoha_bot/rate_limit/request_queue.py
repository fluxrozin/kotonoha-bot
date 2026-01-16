"""リクエストキュー"""

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import IntEnum

logger = logging.getLogger(__name__)


class RequestPriority(IntEnum):
    """リクエストの優先度"""

    THREAD = 1  # スレッド型（最低優先度）
    MENTION = 2  # メンション応答型（中優先度）
    EAVESDROP = 3  # 聞き耳型（最高優先度）


@dataclass
class QueuedRequest:
    """キューに追加されたリクエスト"""

    priority: RequestPriority
    func: Callable
    args: tuple = field(default_factory=tuple)
    kwargs: dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    future: asyncio.Future | None = None


class RequestQueue:
    """リクエストキュー

    リクエストを優先度順に処理するキュー。
    """

    def __init__(self, max_size: int = 100):
        """初期化

        Args:
            max_size: キューの最大サイズ
        """
        self.max_size = max_size
        self._queue: asyncio.PriorityQueue = asyncio.PriorityQueue(maxsize=max_size)
        self._worker_task: asyncio.Task | None = None
        self._running = False

    async def start(self) -> None:
        """ワーカーを開始"""
        if self._running:
            return

        self._running = True
        self._worker_task = asyncio.create_task(self._worker())
        logger.info("Request queue worker started")

    async def stop(self) -> None:
        """ワーカーを停止"""
        if not self._running:
            return

        self._running = False
        if self._worker_task:
            await self._worker_task
        logger.info("Request queue worker stopped")

    async def enqueue(
        self,
        priority: RequestPriority,
        func: Callable,
        *args,
        **kwargs,
    ) -> asyncio.Future:
        """リクエストをキューに追加

        Args:
            priority: リクエストの優先度
            func: 実行する関数
            *args: 関数の引数
            **kwargs: 関数のキーワード引数

        Returns:
            リクエストの結果を取得する Future
        """
        # キューのサイズをチェック（処理中のリクエストも含む）
        # 注意: qsize()は概算値のため、正確ではない可能性がある
        if self._queue.qsize() >= self.max_size:
            raise RuntimeError(f"Queue is full (max size: {self.max_size})")

        future = asyncio.Future()
        request = QueuedRequest(
            priority=priority,
            func=func,
            args=args,
            kwargs=kwargs,
            future=future,
        )

        # 優先度は高いほど先に処理される（負の値でソート）
        # 同じ優先度の場合は、作成時刻でソート（古い順）
        # タプルの比較: (-priority.value, created_at, request)
        # これにより、同じ優先度でも比較可能になる
        await self._queue.put((-priority.value, request.created_at, request))
        logger.debug(f"Enqueued request with priority {priority.name}")

        return future

    async def _worker(self) -> None:
        """ワーカーループ"""
        while self._running:
            try:
                # キューからリクエストを取得（タイムアウト: 1秒）
                try:
                    _, _, request = await asyncio.wait_for(
                        self._queue.get(), timeout=1.0
                    )
                except TimeoutError:
                    continue

                # リクエストを実行
                try:
                    result = await request.func(*request.args, **request.kwargs)
                    if request.future and not request.future.done():
                        request.future.set_result(result)
                except Exception as e:
                    logger.exception(f"Error executing queued request: {e}")
                    if request.future and not request.future.done():
                        request.future.set_exception(e)

            except Exception as e:
                logger.exception(f"Error in request queue worker: {e}")
