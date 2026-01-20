"""日付・時刻ユーティリティ."""

from datetime import datetime

WEEKDAY_NAMES_JA = ["月", "火", "水", "木", "金", "土", "日"]


def format_datetime_for_prompt() -> str:
    """システムプロンプト用の現在日時情報を生成.

    Returns:
        現在の日時情報を含む文字列
    """
    now = datetime.now()
    return (
        f"\n\n【現在の日付情報】\n"
        f"現在の日時: {now.strftime('%Y年%m月%d日 %H:%M:%S')}\n"
        f"今日の曜日: {WEEKDAY_NAMES_JA[now.weekday()]}曜日\n"
        f"日付や曜日に関する質問には、この情報を基に具体的に回答してください。"
        f"プレースホルダー（[明日の曜日]など）は使用せず、実際の日付や曜日を回答してください。"
    )
