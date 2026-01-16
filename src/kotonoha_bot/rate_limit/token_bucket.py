"""トークンバケットアルゴリズム"""

import asyncio
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class TokenBucket:
    """トークンバケット

    リクエストレートを制御するためのトークンバケットアルゴリズム。
    """

    def __init__(
        self,
        capacity: int,
        refill_rate: float,
        initial_tokens: int | None = None,
    ):
        """初期化

        Args:
            capacity: バケットの容量（最大トークン数）
            refill_rate: 補充レート（トークン/秒）
            initial_tokens: 初期トークン数（None の場合は capacity）
        """
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.tokens = initial_tokens if initial_tokens is not None else capacity
        self.last_refill = datetime.now()
        self._lock = asyncio.Lock()

    async def acquire(self, tokens: int = 1) -> bool:
        """トークンを取得

        Args:
            tokens: 必要なトークン数

        Returns:
            トークンを取得できた場合 True
        """
        async with self._lock:
            # トークンを補充
            await self._refill()

            if self.tokens >= tokens:
                self.tokens -= tokens
                logger.debug(f"Acquired {tokens} tokens, remaining: {self.tokens}")
                return True

            logger.debug(f"Insufficient tokens: need {tokens}, have {self.tokens}")
            return False

    async def wait_for_tokens(
        self, tokens: int = 1, timeout: float | None = None
    ) -> bool:
        """トークンが利用可能になるまで待機

        Args:
            tokens: 必要なトークン数
            timeout: タイムアウト（秒、None の場合は無制限）

        Returns:
            トークンを取得できた場合 True、タイムアウトした場合 False
        """
        start_time = datetime.now()

        while True:
            if await self.acquire(tokens):
                return True

            # タイムアウトチェック
            if timeout is not None:
                elapsed = (datetime.now() - start_time).total_seconds()
                if elapsed >= timeout:
                    logger.warning(f"Timeout waiting for {tokens} tokens")
                    return False

            # 次のトークン補充まで待機
            await asyncio.sleep(1.0 / self.refill_rate)

    async def _refill(self) -> None:
        """トークンを補充"""
        now = datetime.now()
        elapsed = (now - self.last_refill).total_seconds()
        tokens_to_add = elapsed * self.refill_rate

        if tokens_to_add > 0:
            self.tokens = min(self.capacity, self.tokens + tokens_to_add)
            self.last_refill = now
            logger.debug(f"Refilled tokens: {self.tokens}/{self.capacity}")
