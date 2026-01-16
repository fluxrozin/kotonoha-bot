"""レート制限モニター"""

import logging
from collections import defaultdict
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class RateLimitMonitor:
    """レート制限モニター

    API リクエスト数を追跡し、レート制限の接近を検知する。
    """

    def __init__(self, window_seconds: int = 60, warning_threshold: float = 0.8):
        """初期化

        Args:
            window_seconds: 監視ウィンドウ（秒）
            warning_threshold: 警告閾値（0.0-1.0、レート制限の何%で警告するか）
        """
        self.window_seconds = window_seconds
        self.warning_threshold = warning_threshold
        # リクエスト履歴: キー: エンドポイント、値: タイムスタンプのリスト
        self.request_history: dict[str, list[datetime]] = defaultdict(list)
        # レート制限情報: キー: エンドポイント、値: (制限数, ウィンドウ秒)
        self.rate_limits: dict[str, tuple[int, int]] = {}

    def record_request(self, endpoint: str) -> None:
        """リクエストを記録

        Args:
            endpoint: API エンドポイント（例: "claude-api"）
        """
        now = datetime.now()
        self.request_history[endpoint].append(now)

        # 古い履歴を削除
        cutoff = now - timedelta(seconds=self.window_seconds)
        self.request_history[endpoint] = [
            ts for ts in self.request_history[endpoint] if ts > cutoff
        ]

    def check_rate_limit(self, endpoint: str) -> tuple[bool, float]:
        """レート制限の接近をチェック

        Args:
            endpoint: API エンドポイント

        Returns:
            (警告が必要か, 使用率 0.0-1.0)
        """
        if endpoint not in self.rate_limits:
            return False, 0.0

        limit, window = self.rate_limits[endpoint]
        recent_requests = len(self.request_history[endpoint])
        usage_rate = recent_requests / limit if limit > 0 else 0.0

        if usage_rate >= self.warning_threshold:
            logger.warning(
                f"Rate limit approaching for {endpoint}: "
                f"{recent_requests}/{limit} requests in {window}s "
                f"({usage_rate * 100:.1f}%)"
            )
            return True, usage_rate

        return False, usage_rate

    def set_rate_limit(self, endpoint: str, limit: int, window_seconds: int) -> None:
        """レート制限を設定

        Args:
            endpoint: API エンドポイント
            limit: リクエスト数の制限
            window_seconds: ウィンドウ（秒）
        """
        self.rate_limits[endpoint] = (limit, window_seconds)
        logger.info(
            f"Set rate limit for {endpoint}: {limit} requests per {window_seconds}s"
        )
