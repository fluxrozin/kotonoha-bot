"""メッセージフォーマッター"""

import discord


def create_response_embed(
    content: str, model_name: str, rate_limit_usage: float | None = None
) -> discord.Embed:
    """応答メッセージ用のEmbedを作成

    Args:
        content: 応答テキスト
        model_name: 使用したモデル名
        rate_limit_usage: レート制限の使用率（0.0-1.0、Noneの場合は表示しない）

    Returns:
        Embedオブジェクト
    """
    embed = discord.Embed(
        description=content,
        color=0x3498DB,  # 青色
    )
    # フッターにモデル名とレート制限使用率を表示（英語表記）
    footer_parts = [f"Model: {model_name}"]
    if rate_limit_usage is not None:
        usage_percent = rate_limit_usage * 100
        footer_parts.append(f"Rate limit: {usage_percent:.1f}%")
    embed.set_footer(text=" | ".join(footer_parts))
    return embed
