"""レート制限モニターの警告ログテスト"""

from unittest.mock import patch

from kotonoha_bot.rate_limit.monitor import RateLimitMonitor


class TestRateLimitMonitorWarning:
    """レート制限モニターの警告ログテスト"""

    def test_warning_log_when_threshold_exceeded(self):
        """警告閾値を超えた場合に警告ログが出力される"""
        monitor = RateLimitMonitor(window_seconds=60, warning_threshold=0.8)
        endpoint = "test-endpoint"

        # レート制限を設定
        monitor.set_rate_limit(endpoint, limit=100, window_seconds=60)

        # 警告ログをキャプチャ
        with patch("kotonoha_bot.rate_limit.monitor.logger.warning") as mock_warning:
            # 閾値を超えるリクエストを記録
            for _ in range(90):
                monitor.record_request(endpoint)

            # レート制限をチェック
            should_warn, usage_rate = monitor.check_rate_limit(endpoint)

            # 警告が出力されたことを確認
            assert should_warn is True
            assert usage_rate == 0.9
            mock_warning.assert_called_once()
            # 警告メッセージの内容を確認
            call_args = mock_warning.call_args[0][0]
            assert "Rate limit approaching" in call_args
            assert endpoint in call_args
            assert "90" in call_args
            assert "100" in call_args

    def test_no_warning_log_when_below_threshold(self):
        """警告閾値以下の場合に警告ログが出力されない"""
        monitor = RateLimitMonitor(window_seconds=60, warning_threshold=0.8)
        endpoint = "test-endpoint"

        # レート制限を設定
        monitor.set_rate_limit(endpoint, limit=100, window_seconds=60)

        # 警告ログをキャプチャ
        with patch("kotonoha_bot.rate_limit.monitor.logger.warning") as mock_warning:
            # 閾値以下のリクエストを記録
            for _ in range(50):
                monitor.record_request(endpoint)

            # レート制限をチェック
            should_warn, usage_rate = monitor.check_rate_limit(endpoint)

            # 警告が出力されないことを確認
            assert should_warn is False
            assert usage_rate == 0.5
            mock_warning.assert_not_called()

    def test_warning_log_at_exact_threshold(self):
        """警告閾値ちょうどの場合に警告ログが出力される"""
        monitor = RateLimitMonitor(window_seconds=60, warning_threshold=0.8)
        endpoint = "test-endpoint"

        # レート制限を設定
        monitor.set_rate_limit(endpoint, limit=100, window_seconds=60)

        # 警告ログをキャプチャ
        with patch("kotonoha_bot.rate_limit.monitor.logger.warning") as mock_warning:
            # 閾値ちょうどのリクエストを記録
            for _ in range(80):
                monitor.record_request(endpoint)

            # レート制限をチェック
            should_warn, usage_rate = monitor.check_rate_limit(endpoint)

            # 警告が出力されたことを確認
            assert should_warn is True
            assert usage_rate == 0.8
            mock_warning.assert_called_once()

    def test_warning_log_includes_percentage(self):
        """警告ログにパーセンテージが含まれる"""
        monitor = RateLimitMonitor(window_seconds=60, warning_threshold=0.8)
        endpoint = "test-endpoint"

        # レート制限を設定
        monitor.set_rate_limit(endpoint, limit=100, window_seconds=60)

        # 警告ログをキャプチャ
        with patch("kotonoha_bot.rate_limit.monitor.logger.warning") as mock_warning:
            # 閾値を超えるリクエストを記録
            for _ in range(95):
                monitor.record_request(endpoint)

            # レート制限をチェック
            monitor.check_rate_limit(endpoint)

            # 警告メッセージにパーセンテージが含まれることを確認
            call_args = mock_warning.call_args[0][0]
            assert "%" in call_args
            assert "95.0%" in call_args or "95%" in call_args
