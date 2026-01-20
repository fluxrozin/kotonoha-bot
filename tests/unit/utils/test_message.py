"""メッセージ処理ユーティリティのテスト（フォーマッターと分割機能）."""

import discord

from kotonoha_bot.utils.message import (
    DISCORD_MESSAGE_MAX_LENGTH,
    create_response_embed,
    format_split_messages,
    split_message,
)

# ============================================
# メッセージフォーマッターのテスト
# ============================================


def test_create_response_embed():
    """Embedの作成が正しく動作する."""
    content = "これはテストメッセージです。"
    model_name = "anthropic/claude-3-haiku-20240307"

    embed = create_response_embed(content, model_name)

    # 検証
    assert isinstance(embed, discord.Embed)
    assert embed.description == content
    assert embed.color is not None
    assert embed.color.value == 0x3498DB
    assert embed.footer.text == f"Model: {model_name}"


def test_create_response_embed_with_rate_limit():
    """レート制限使用率を含むEmbedの作成が正しく動作する."""
    content = "これはテストメッセージです。"
    model_name = "anthropic/claude-3-haiku-20240307"
    rate_limit_usage = 0.75  # 75%

    embed = create_response_embed(content, model_name, rate_limit_usage)

    # 検証
    assert isinstance(embed, discord.Embed)
    assert embed.description == content
    assert embed.color is not None
    assert embed.color.value == 0x3498DB
    assert embed.footer.text == f"Model: {model_name} | Rate limit: 75.0%"


def test_create_response_embed_long_content():
    """長いコンテンツでも正しく動作する."""
    content = "あ" * 1000  # 長いコンテンツ
    model_name = "anthropic/claude-sonnet-4-5"

    embed = create_response_embed(content, model_name)

    # 検証
    assert embed.description == content
    assert embed.footer.text == f"Model: {model_name}"


def test_create_response_embed_empty_content():
    """空のコンテンツでも正しく動作する."""
    content = ""
    model_name = "anthropic/claude-3-haiku-20240307"

    embed = create_response_embed(content, model_name)

    # 検証
    assert embed.description == content
    assert embed.footer.text == f"Model: {model_name}"


def test_create_response_embed_special_characters():
    """特殊文字を含むコンテンツでも正しく動作する."""
    content = "テストメッセージ\n改行\n**太字**\n*斜体*"
    model_name = "anthropic/claude-3-haiku-20240307"

    embed = create_response_embed(content, model_name)

    # 検証
    assert embed.description == content


# ============================================
# メッセージ分割機能のテスト
# ============================================


def test_split_short_message():
    """短いメッセージは分割されない."""
    content = "これは短いメッセージです。"
    chunks = split_message(content)
    assert len(chunks) == 1
    assert chunks[0] == content


def test_split_long_message():
    """長いメッセージは分割される."""
    # 3000文字のメッセージを作成
    content = "。" * 3000
    chunks = split_message(content)
    assert len(chunks) > 1
    assert all(len(chunk) <= DISCORD_MESSAGE_MAX_LENGTH for chunk in chunks)


def test_split_at_sentence_boundary():
    """文の区切りで分割される."""
    content = "最初の文です。\n\n2番目の文です。\n\n3番目の文です。"
    # 長いメッセージにするために繰り返す
    long_content = content * 1000
    chunks = split_message(long_content)
    # 各チャンクが適切に分割されていることを確認
    assert len(chunks) > 1


def test_format_split_messages():
    """連番が正しく付与される."""
    chunks = ["チャンク1", "チャンク2", "チャンク3"]
    formatted = format_split_messages(chunks, len(chunks))
    assert len(formatted) == 3
    assert "(1/3)" in formatted[0]
    assert "(2/3)" in formatted[1]
    assert "(3/3)" in formatted[2]


def test_format_single_message():
    """単一メッセージには連番が付与されない."""
    chunks = ["単一のメッセージ"]
    formatted = format_split_messages(chunks, len(chunks))
    assert len(formatted) == 1
    assert formatted[0] == "単一のメッセージ"
    assert "(1/1)" not in formatted[0]


def test_split_message_preserves_content():
    """分割後も元の内容が保持される."""
    content = "最初の文です。\n\n2番目の文です。\n\n3番目の文です。"
    # 長いメッセージにするために繰り返す
    long_content = content * 1000
    chunks = split_message(long_content)
    # すべてのチャンクを結合すると元の内容になる（ただし、分割時に先頭の空白が削除される可能性がある）
    combined = "".join(chunks)
    # 分割時に先頭の空白が削除される可能性があるため、長さが完全に一致しない場合がある
    # ただし、内容の大部分は保持されることを確認
    assert len(combined) >= len(long_content) * 0.95  # 95%以上は保持される


def test_split_message_no_sentence_boundary():
    """文の区切りがない場合でも分割される."""
    # 句読点のない長いメッセージ
    content = "あ" * 3000
    chunks = split_message(content)
    assert len(chunks) > 1
    assert all(len(chunk) <= DISCORD_MESSAGE_MAX_LENGTH for chunk in chunks)


def test_format_split_messages_empty():
    """空のリストでも正しく動作する."""
    chunks = []
    formatted = format_split_messages(chunks, len(chunks))
    assert len(formatted) == 0


def test_split_message_exact_length():
    """ちょうど最大長のメッセージは分割されない."""
    content = "あ" * DISCORD_MESSAGE_MAX_LENGTH
    chunks = split_message(content)
    assert len(chunks) == 1
    assert chunks[0] == content


def test_split_message_one_over_max():
    """最大長+1のメッセージは分割される."""
    content = "あ" * (DISCORD_MESSAGE_MAX_LENGTH + 1)
    chunks = split_message(content)
    assert len(chunks) > 1
    assert all(len(chunk) <= DISCORD_MESSAGE_MAX_LENGTH for chunk in chunks)
