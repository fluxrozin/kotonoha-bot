"""日時ユーティリティのテスト."""

from datetime import datetime
from unittest.mock import patch

from kotonoha_bot.utils.datetime import WEEKDAY_NAMES_JA, format_datetime_for_prompt


class TestFormatDatetimeForPrompt:
    """format_datetime_for_prompt 関数のテスト."""

    def test_format_datetime_includes_date(self):
        """日時情報が含まれる."""
        with patch("kotonoha_bot.utils.datetime.datetime") as mock_datetime:
            mock_now = datetime(2026, 1, 15, 14, 30, 45)
            mock_datetime.now.return_value = mock_now

            result = format_datetime_for_prompt()

            assert "2026年01月15日 14:30:45" in result
            assert "現在の日時" in result

    def test_format_datetime_includes_weekday(self):
        """曜日情報が含まれる."""
        with patch("kotonoha_bot.utils.datetime.datetime") as mock_datetime:
            # 2026年1月15日は木曜日（weekday() = 3）
            mock_now = datetime(2026, 1, 15, 14, 30, 45)
            mock_datetime.now.return_value = mock_now

            result = format_datetime_for_prompt()

            assert "木曜日" in result
            assert "今日の曜日" in result

    def test_format_datetime_includes_instruction(self):
        """指示文が含まれる."""
        result = format_datetime_for_prompt()

        assert "日付や曜日に関する質問" in result
        assert "プレースホルダー" in result
        assert "実際の日付や曜日" in result

    def test_format_datetime_different_weekdays(self):
        """異なる曜日で正しく動作する."""
        weekdays = [
            (0, "月"),  # 月曜日
            (1, "火"),  # 火曜日
            (2, "水"),  # 水曜日
            (3, "木"),  # 木曜日
            (4, "金"),  # 金曜日
            (5, "土"),  # 土曜日
            (6, "日"),  # 日曜日
        ]

        for weekday, expected_name in weekdays:
            with patch("kotonoha_bot.utils.datetime.datetime") as mock_datetime:
                # 2026年1月12日（月曜日）を基準に、weekday 分の日数を加算
                base_date = datetime(2026, 1, 12, 12, 0, 0)
                mock_now = datetime.fromordinal(base_date.toordinal() + weekday)
                mock_datetime.now.return_value = mock_now

                result = format_datetime_for_prompt()

                assert f"{expected_name}曜日" in result


class TestWeekdayNames:
    """WEEKDAY_NAMES_JA 定数のテスト."""

    def test_weekday_names_ja_has_correct_length(self):
        """曜日名のリストが7要素である."""
        assert len(WEEKDAY_NAMES_JA) == 7

    def test_weekday_names_ja_has_correct_order(self):
        """曜日名が正しい順序である."""
        expected = ["月", "火", "水", "木", "金", "土", "日"]
        assert expected == WEEKDAY_NAMES_JA
