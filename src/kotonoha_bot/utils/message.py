"""メッセージ処理ユーティリティ."""

import re

import discord

# Discord のメッセージ長制限
DISCORD_MESSAGE_MAX_LENGTH = 2000
DISCORD_EMBED_MAX_LENGTH = 6000

# 分割用の区切り文字（優先順位順）
SPLIT_PATTERNS = [
    r"。\n",  # 句点 + 改行
    r"。",  # 句点
    r"\n\n",  # 段落区切り（空行）
    r"\n",  # 改行
    r"[、，]",  # 読点
    r" ",  # スペース
]


def create_response_embed(
    content: str, model_name: str, rate_limit_usage: float | None = None
) -> discord.Embed:
    """応答メッセージ用のEmbedを作成.

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


def split_message(
    content: str, max_length: int = DISCORD_MESSAGE_MAX_LENGTH
) -> list[str]:
    """メッセージを分割する.

    Args:
        content: 分割するメッセージ
        max_length: 最大文字数（デフォルト: 2000）

    Returns:
        分割されたメッセージのリスト
    """
    if len(content) <= max_length:
        return [content]

    chunks = []
    remaining = content

    while len(remaining) > max_length:
        # 分割位置を探す
        split_pos = find_split_position(remaining, max_length)

        if split_pos == -1:
            # 分割位置が見つからない場合、強制的に max_length で分割
            chunks.append(remaining[:max_length])
            remaining = remaining[max_length:]
        else:
            chunks.append(remaining[:split_pos])
            remaining = remaining[split_pos:].lstrip()

    if remaining:
        chunks.append(remaining)

    return chunks


def find_split_position(text: str, max_length: int) -> int:
    """最適な分割位置を探す.

    Args:
        text: 分割するテキスト
        max_length: 最大文字数

    Returns:
        分割位置（見つからない場合は -1）
    """
    # 最大長の範囲内で、後ろから順に区切り文字を探す
    search_end = min(max_length, len(text))
    search_text = text[:search_end]

    for pattern in SPLIT_PATTERNS:
        matches = list(re.finditer(pattern, search_text))
        if matches:
            # 最後のマッチ位置を返す
            last_match = matches[-1]
            # マッチした文字列の終了位置を返す
            return last_match.end()

    return -1


def format_split_messages(chunks: list[str], total: int) -> list[str]:
    """分割されたメッセージに連番を付与.

    Args:
        chunks: 分割されたメッセージのリスト
        total: 総メッセージ数

    Returns:
        連番が付与されたメッセージのリスト
    """
    if len(chunks) == 1:
        return chunks

    formatted = []
    for i, chunk in enumerate(chunks, 1):
        header = f"**({i}/{total})**\n\n"
        formatted.append(header + chunk)

    return formatted
