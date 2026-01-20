"""レート制限機能のテスト"""

import asyncio
from datetime import datetime, timedelta

import pytest

from kotonoha_bot.rate_limit.monitor import RateLimitMonitor
from kotonoha_bot.rate_limit.request_queue import RequestPriority, RequestQueue
from kotonoha_bot.rate_limit.token_bucket import TokenBucket


class TestRateLimitMonitor:
    """レート制限モニターのテスト"""

    def test_record_request(self):
        """リクエストの記録が正しく動作する"""
        monitor = RateLimitMonitor(window_seconds=60, warning_threshold=0.8)
        endpoint = "test-endpoint"

        # リクエストを記録
        monitor.record_request(endpoint)
        monitor.record_request(endpoint)

        # 履歴が記録されているか確認
        assert len(monitor.request_history[endpoint]) == 2

    def test_check_rate_limit_no_limit_set(self):
        """レート制限が設定されていない場合"""
        monitor = RateLimitMonitor()
        endpoint = "test-endpoint"

        should_warn, usage_rate = monitor.check_rate_limit(endpoint)
        assert should_warn is False
        assert usage_rate == 0.0

    def test_check_rate_limit_below_threshold(self):
        """レート制限の閾値以下の場合"""
        monitor = RateLimitMonitor(window_seconds=60, warning_threshold=0.8)
        endpoint = "test-endpoint"

        # レート制限を設定
        monitor.set_rate_limit(endpoint, limit=100, window_seconds=60)

        # リクエストを記録（閾値以下）
        for _ in range(50):
            monitor.record_request(endpoint)

        should_warn, usage_rate = monitor.check_rate_limit(endpoint)
        assert should_warn is False
        assert usage_rate == 0.5

    def test_check_rate_limit_above_threshold(self):
        """レート制限の閾値を超えた場合"""
        monitor = RateLimitMonitor(window_seconds=60, warning_threshold=0.8)
        endpoint = "test-endpoint"

        # レート制限を設定
        monitor.set_rate_limit(endpoint, limit=100, window_seconds=60)

        # リクエストを記録（閾値を超える）
        for _ in range(90):
            monitor.record_request(endpoint)

        should_warn, usage_rate = monitor.check_rate_limit(endpoint)
        assert should_warn is True
        assert usage_rate == 0.9

    def test_old_requests_are_removed(self):
        """古いリクエストが削除される"""
        monitor = RateLimitMonitor(window_seconds=60, warning_threshold=0.8)
        endpoint = "test-endpoint"

        # 古いリクエストを記録（現在時刻から61秒前）
        old_time = datetime.now() - timedelta(seconds=61)
        monitor.request_history[endpoint].append(old_time)

        # 新しいリクエストを記録
        monitor.record_request(endpoint)

        # 古いリクエストが削除されているか確認
        assert len(monitor.request_history[endpoint]) == 1
        assert monitor.request_history[endpoint][0] > old_time


class TestTokenBucket:
    """トークンバケットのテスト"""

    @pytest.mark.asyncio
    async def test_acquire_success(self):
        """トークンの取得が成功する"""
        bucket = TokenBucket(capacity=10, refill_rate=1.0, initial_tokens=10)

        result = await bucket.acquire(tokens=5)
        assert result is True
        assert bucket.tokens == 5

    @pytest.mark.asyncio
    async def test_acquire_insufficient_tokens(self):
        """トークンが不足している場合"""
        bucket = TokenBucket(capacity=10, refill_rate=1.0, initial_tokens=5)

        result = await bucket.acquire(tokens=10)
        assert result is False
        # 浮動小数点の誤差を考慮
        assert abs(bucket.tokens - 5) < 0.01

    @pytest.mark.asyncio
    async def test_refill_tokens(self):
        """トークンが補充される"""
        bucket = TokenBucket(capacity=10, refill_rate=1.0, initial_tokens=0)

        # トークンを消費（不足しているので取得できない）
        result = await bucket.acquire(tokens=5)
        assert result is False
        # トークンが0に近いことを確認（浮動小数点の誤差を考慮）
        assert bucket.tokens < 0.01

        # 1秒待機してトークンを補充
        await asyncio.sleep(1.1)

        # トークンが補充されているか確認
        result = await bucket.acquire(tokens=1)
        assert result is True
        assert bucket.tokens >= 0

    @pytest.mark.asyncio
    async def test_wait_for_tokens_success(self):
        """トークンが利用可能になるまで待機（成功）"""
        bucket = TokenBucket(capacity=10, refill_rate=10.0, initial_tokens=0)

        # トークンが補充されるまで待機
        result = await bucket.wait_for_tokens(tokens=1, timeout=2.0)
        assert result is True

    @pytest.mark.asyncio
    async def test_wait_for_tokens_timeout(self):
        """トークンが利用可能になるまで待機（タイムアウト）"""
        bucket = TokenBucket(capacity=10, refill_rate=0.1, initial_tokens=0)

        # タイムアウトするまで待機
        result = await bucket.wait_for_tokens(tokens=10, timeout=0.5)
        assert result is False

    @pytest.mark.asyncio
    async def test_tokens_do_not_exceed_capacity(self):
        """トークンが容量を超えない"""
        bucket = TokenBucket(capacity=10, refill_rate=100.0, initial_tokens=10)

        # 長時間待機しても容量を超えない
        await asyncio.sleep(0.1)
        await bucket.acquire(tokens=0)  # 補充をトリガー

        assert bucket.tokens <= bucket.capacity

    @pytest.mark.asyncio
    async def test_acquire_zero_tokens(self):
        """0トークンの取得が成功する"""
        bucket = TokenBucket(capacity=10, refill_rate=1.0, initial_tokens=0)

        result = await bucket.acquire(tokens=0)
        assert result is True

    @pytest.mark.asyncio
    async def test_initial_tokens_parameter(self):
        """初期トークン数パラメータが正しく動作する"""
        bucket = TokenBucket(capacity=10, refill_rate=1.0, initial_tokens=5)

        assert bucket.tokens == 5

    @pytest.mark.asyncio
    async def test_refill_rate_affects_tokens(self):
        """補充レートがトークン数に影響する"""
        bucket1 = TokenBucket(capacity=10, refill_rate=1.0, initial_tokens=0)
        bucket2 = TokenBucket(capacity=10, refill_rate=2.0, initial_tokens=0)

        # 1秒待機
        await asyncio.sleep(1.1)

        # 補充をトリガー
        await bucket1.acquire(tokens=0)
        await bucket2.acquire(tokens=0)

        # 補充レートが高い方がトークンが多い
        assert bucket2.tokens > bucket1.tokens

    @pytest.mark.asyncio
    async def test_wait_for_tokens_with_sufficient_tokens(self):
        """十分なトークンがある場合、待機せずに即座に成功する"""
        bucket = TokenBucket(capacity=10, refill_rate=1.0, initial_tokens=10)

        start_time = asyncio.get_event_loop().time()
        result = await bucket.wait_for_tokens(tokens=5, timeout=10.0)
        elapsed = asyncio.get_event_loop().time() - start_time

        assert result is True
        assert elapsed < 0.1  # 即座に成功する


class TestRequestQueue:
    """リクエストキューのテスト"""

    @pytest.mark.asyncio
    async def test_enqueue_and_process(self):
        """リクエストのキューイングと処理"""
        queue = RequestQueue(max_size=10)
        await queue.start()

        # テスト用の関数
        async def test_func(value: int) -> int:
            return value * 2

        # リクエストをキューに追加
        future = await queue.enqueue(RequestPriority.MENTION, test_func, 5)

        # 結果を待機
        result = await future
        assert result == 10

        await queue.stop()

    @pytest.mark.asyncio
    async def test_priority_order(self):
        """優先度順に処理される"""
        queue = RequestQueue(max_size=10)
        await queue.start()

        results = []

        async def test_func(value: int) -> int:
            results.append(value)
            return value

        # 優先度の低い順にキューに追加
        await queue.enqueue(RequestPriority.THREAD, test_func, 1)
        await queue.enqueue(RequestPriority.MENTION, test_func, 2)
        await queue.enqueue(RequestPriority.EAVESDROP, test_func, 3)

        # 処理を待機
        await asyncio.sleep(0.5)

        # 優先度の高い順（EAVESDROP > MENTION > THREAD）に処理される
        assert results == [3, 2, 1]

        await queue.stop()

    @pytest.mark.asyncio
    async def test_queue_processing(self):
        """キューの処理が正しく動作する"""
        queue = RequestQueue(max_size=10)
        await queue.start()

        async def test_func(value: int) -> int:
            return value * 2

        # 複数のリクエストをキューに追加
        future1 = await queue.enqueue(RequestPriority.MENTION, test_func, 5)
        future2 = await queue.enqueue(RequestPriority.THREAD, test_func, 10)

        # 結果を待機
        result1 = await future1
        result2 = await future2

        assert result1 == 10
        assert result2 == 20

        await queue.stop()

    @pytest.mark.asyncio
    async def test_error_handling(self):
        """エラーハンドリング"""
        queue = RequestQueue(max_size=10)
        await queue.start()

        async def failing_func() -> None:
            raise ValueError("Test error")

        # エラーが発生する関数をキューに追加
        future = await queue.enqueue(RequestPriority.MENTION, failing_func)

        # エラーが伝播される
        with pytest.raises(ValueError, match="Test error"):
            await future

        await queue.stop()

    @pytest.mark.asyncio
    async def test_queue_max_size(self):
        """キューの最大サイズ制限"""
        queue = RequestQueue(max_size=2)
        await queue.start()

        async def test_func(value: int) -> int:
            await asyncio.sleep(0.1)  # 処理に時間がかかる
            return value

        # 最大サイズまでキューに追加
        future1 = await queue.enqueue(RequestPriority.MENTION, test_func, 1)
        future2 = await queue.enqueue(RequestPriority.MENTION, test_func, 2)

        # 最大サイズを超えて追加しようとするとエラー
        with pytest.raises(RuntimeError, match="Queue is full"):
            await queue.enqueue(RequestPriority.MENTION, test_func, 3)

        # 既存のリクエストを待機
        await future1
        await future2

        await queue.stop()

    @pytest.mark.asyncio
    async def test_queue_stop_before_start(self):
        """開始前に停止してもエラーが発生しない"""
        queue = RequestQueue(max_size=10)
        await queue.stop()  # 開始前に停止

    @pytest.mark.asyncio
    async def test_queue_double_start(self):
        """二重起動しても問題ない"""
        queue = RequestQueue(max_size=10)
        await queue.start()
        await queue.start()  # 二重起動

        await queue.stop()

    @pytest.mark.asyncio
    async def test_queue_double_stop(self):
        """二重停止しても問題ない"""
        queue = RequestQueue(max_size=10)
        await queue.start()
        await queue.stop()
        await queue.stop()  # 二重停止

    @pytest.mark.asyncio
    async def test_queue_same_priority_order(self):
        """同じ優先度のリクエストは作成時刻順に処理される"""
        queue = RequestQueue(max_size=10)
        await queue.start()

        results = []

        async def test_func(value: int) -> int:
            results.append(value)
            return value

        # 同じ優先度で複数のリクエストを追加
        await queue.enqueue(RequestPriority.MENTION, test_func, 1)
        await asyncio.sleep(0.01)  # 少し待機
        await queue.enqueue(RequestPriority.MENTION, test_func, 2)
        await asyncio.sleep(0.01)
        await queue.enqueue(RequestPriority.MENTION, test_func, 3)

        # 処理を待機
        await asyncio.sleep(0.5)

        # 作成時刻順（1, 2, 3）に処理される
        assert results == [1, 2, 3]

        await queue.stop()
