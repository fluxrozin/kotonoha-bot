"""AIサービスのテスト."""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from kotonoha_bot.config import get_config
from kotonoha_bot.db.models import Message, MessageRole
from kotonoha_bot.services.ai import AnthropicProvider


@pytest.fixture
def mock_anthropic_client():
    """モックAnthropicクライアント"""
    client = AsyncMock()
    return client


@pytest.fixture
def anthropic_provider():
    """AnthropicProviderのフィクスチャ."""
    # 環境変数をモック化
    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-api-key"}):
        # get_config()のシングルトンインスタンスをリセット
        import kotonoha_bot.config
        # 設定をリセット（シングルトンインスタンスをクリア）
        kotonoha_bot.config._config_instance = None
        config = get_config()
        provider = AnthropicProvider(config=config)
        # クライアントをモック化
        provider.client = AsyncMock()
        return provider


@pytest.fixture
def sample_messages():
    """サンプルメッセージリスト"""
    return [
        Message(role=MessageRole.USER, content="こんにちは"),
        Message(
            role=MessageRole.ASSISTANT,
            content="こんにちは！何かお手伝いできることはありますか？",
        ),
    ]


@pytest.mark.asyncio
async def test_generate_response_success(anthropic_provider, sample_messages):
    """正常な応答生成のテスト"""
    # モックレスポンスを設定
    mock_response = MagicMock()
    mock_response.content = [MagicMock(type="text", text="テスト応答")]
    mock_response.usage = MagicMock(input_tokens=10, output_tokens=5)
    mock_response.model = "claude-haiku-4-5"

    anthropic_provider.client.messages.create = AsyncMock(return_value=mock_response)

    # 応答を生成
    response_text, token_info = await anthropic_provider.generate_response(
        messages=sample_messages,
        system_prompt="あなたは親切なアシスタントです。",
    )

    # 結果を検証
    assert response_text == "テスト応答"
    assert token_info.input_tokens == 10
    assert token_info.output_tokens == 5
    assert token_info.model_used == "claude-haiku-4-5"
    assert token_info.total_tokens == 15

    # APIが呼ばれたことを確認
    anthropic_provider.client.messages.create.assert_called_once()


@pytest.mark.asyncio
async def test_generate_response_empty_content(anthropic_provider, sample_messages):
    """空のコンテンツの場合のテスト"""
    # モックレスポンスを設定（空のコンテンツ）
    mock_response = MagicMock()
    mock_response.content = []

    anthropic_provider.client.messages.create = AsyncMock(return_value=mock_response)

    # エラーが発生することを確認
    from kotonoha_bot.errors.ai import AIServiceError

    with pytest.raises(AIServiceError, match="No content in response"):
        await anthropic_provider.generate_response(messages=sample_messages)


@pytest.mark.asyncio
async def test_generate_response_retry_on_429(anthropic_provider, sample_messages):
    """429エラー（レート制限）でリトライするテスト

    モックを使用してリトライロジックをテストする。
    """
    import anthropic

    # 429エラーをシミュレート
    mock_response = MagicMock()
    mock_response.status_code = 429
    rate_limit_error = anthropic.RateLimitError(
        message="Rate limit exceeded",
        response=mock_response,
        body={},
    )
    rate_limit_error.status_code = 429

    # 最初の2回は429エラー、3回目で成功
    success_response = MagicMock()
    success_response.content = [MagicMock(type="text", text="成功応答")]
    success_response.usage = MagicMock(input_tokens=10, output_tokens=5)
    success_response.model = "claude-haiku-4-5"

    anthropic_provider.client.messages.create = AsyncMock(
        side_effect=[rate_limit_error, rate_limit_error, success_response]
    )

    # リトライが機能することを確認
    response_text, token_info = await anthropic_provider.generate_response(
        messages=sample_messages
    )

    assert response_text == "成功応答"
    # 3回呼ばれたことを確認（2回のリトライ + 1回の成功）
    assert anthropic_provider.client.messages.create.call_count == 3


@pytest.mark.asyncio
async def test_generate_response_no_retry_on_auth_error(
    anthropic_provider, sample_messages
):
    """認証エラー（401）ではリトライしないテスト

    モックを使用してエラーハンドリングをテストする。
    """
    import anthropic

    from kotonoha_bot.errors.ai import AIAuthenticationError

    # 401エラーをシミュレート
    mock_response = MagicMock()
    mock_response.status_code = 401
    auth_error = anthropic.AuthenticationError(
        message="Invalid API key",
        response=mock_response,
        body={},
    )
    auth_error.status_code = 401

    anthropic_provider.client.messages.create = AsyncMock(side_effect=auth_error)

    # 認証エラーが発生することを確認（リトライしない）
    with pytest.raises(AIAuthenticationError):
        await anthropic_provider.generate_response(messages=sample_messages)

    # 1回だけ呼ばれたことを確認（リトライしない）
    assert anthropic_provider.client.messages.create.call_count == 1


@pytest.mark.asyncio
async def test_convert_model_name(anthropic_provider):
    """モデル名の変換テスト"""
    # LiteLLM形式からAnthropic SDK形式に変換
    assert (
        anthropic_provider._convert_model_name("anthropic/claude-haiku-4-5")
        == "claude-haiku-4-5"
    )
    assert (
        anthropic_provider._convert_model_name("anthropic/claude-opus-4-5")
        == "claude-opus-4-5"
    )

    # 既にAnthropic SDK形式の場合はそのまま
    assert (
        anthropic_provider._convert_model_name("claude-haiku-4-5") == "claude-haiku-4-5"
    )


@pytest.mark.asyncio
async def test_convert_messages(anthropic_provider, sample_messages):
    """メッセージ形式の変換テスト"""
    anthropic_messages = anthropic_provider._convert_messages(
        sample_messages, system_prompt="システムプロンプト"
    )

    # メッセージが正しく変換されていることを確認
    assert len(anthropic_messages) == 2
    assert anthropic_messages[0]["role"] == "user"
    assert anthropic_messages[0]["content"] == "こんにちは"
    assert anthropic_messages[1]["role"] == "assistant"
    assert (
        anthropic_messages[1]["content"]
        == "こんにちは！何かお手伝いできることはありますか？"
    )


def test_get_last_used_model(anthropic_provider):
    """最後に使用したモデル名の取得テスト"""
    # 初期状態ではデフォルトモデル
    assert anthropic_provider.get_last_used_model() == anthropic_provider.model

    # モデルを使用した後
    anthropic_provider._last_used_model = "claude-opus-4-5"
    assert anthropic_provider.get_last_used_model() == "claude-opus-4-5"


def test_get_rate_limit_usage(anthropic_provider):
    """レート制限使用率の取得テスト"""
    # レート制限モニターをモック化
    anthropic_provider.rate_limit_monitor.check_rate_limit = MagicMock(
        return_value=(True, 0.5)
    )

    usage = anthropic_provider.get_rate_limit_usage()
    assert usage == 0.5


def test_initialization_without_api_key():
    """APIキーがない場合の初期化エラーテスト."""
    config = get_config()
    # APIキーを一時的に削除
    original_key = config.anthropic_api_key
    config.anthropic_api_key = ""
    try:
        with pytest.raises(ValueError, match="ANTHROPIC_API_KEY is not set"):
            AnthropicProvider(config=config)
    finally:
        config.anthropic_api_key = original_key
