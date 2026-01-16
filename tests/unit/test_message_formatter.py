"""メッセージフォーマッターのテスト"""

import discord

from kotonoha_bot.utils.message_formatter import create_response_embed


def test_create_response_embed():
    """Embedの作成が正しく動作する"""
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
    """レート制限使用率を含むEmbedの作成が正しく動作する"""
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
    """長いコンテンツでも正しく動作する"""
    content = "あ" * 1000  # 長いコンテンツ
    model_name = "anthropic/claude-sonnet-4-5"

    embed = create_response_embed(content, model_name)

    # 検証
    assert embed.description == content
    assert embed.footer.text == f"Model: {model_name}"


def test_create_response_embed_different_models():
    """異なるモデル名でも正しく動作する"""
    test_cases = [
        "anthropic/claude-3-haiku-20240307",
        "anthropic/claude-sonnet-4-5",
        "anthropic/claude-opus-4-5",
    ]

    for model_name in test_cases:
        embed = create_response_embed("テスト", model_name)
        assert embed.footer.text == f"Model: {model_name}"


def test_create_response_embed_rate_limit_percentage():
    """レート制限使用率のパーセンテージ表示が正しく動作する"""
    content = "テスト"
    model_name = "anthropic/claude-3-haiku-20240307"

    # 様々な使用率をテスト
    test_cases = [
        (0.0, "0.0%"),
        (0.25, "25.0%"),
        (0.5, "50.0%"),
        (0.75, "75.0%"),
        (0.99, "99.0%"),
        (1.0, "100.0%"),
    ]

    for usage, expected_percent in test_cases:
        embed = create_response_embed(content, model_name, usage)
        assert embed.footer.text is not None
        assert expected_percent in embed.footer.text
        assert f"Model: {model_name}" in embed.footer.text
        assert "Rate limit:" in embed.footer.text
