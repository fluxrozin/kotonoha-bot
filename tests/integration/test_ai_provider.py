"""AnthropicProviderの統合テスト

AnthropicProviderと既存のコードの統合をテストする。
実際のAPI呼び出しはモックを使用し、エラーケースも含めてテストする。
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import anthropic
import pytest

from kotonoha_bot.ai.anthropic_provider import AnthropicProvider
from kotonoha_bot.session.models import Message, MessageRole


@pytest.fixture
def mock_anthropic_response():
    """モックAnthropic APIレスポンス"""
    response = MagicMock()
    response.content = [MagicMock(type="text", text="テスト応答")]
    response.usage = MagicMock(input_tokens=10, output_tokens=5)
    response.model = "claude-haiku-4-5"
    return response


@pytest.fixture
def anthropic_provider_with_mock():
    """モック付きAnthropicProviderのフィクスチャ"""
    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-api-key"}):
        provider = AnthropicProvider()
        # クライアントをモック化
        provider.client = AsyncMock()
        return provider


@pytest.mark.asyncio
async def test_anthropic_provider_integration_with_handlers(
    anthropic_provider_with_mock, mock_anthropic_response
):
    """AnthropicProviderとhandlers.pyの統合テスト

    MessageHandlerで使用されるAnthropicProviderの動作を確認する。
    """
    provider = anthropic_provider_with_mock
    provider.client.messages.create = AsyncMock(return_value=mock_anthropic_response)

    # サンプルメッセージを作成
    messages = [
        Message(role=MessageRole.USER, content="こんにちは"),
        Message(role=MessageRole.ASSISTANT, content="こんにちは！"),
    ]

    # 応答を生成（handlers.pyと同じ形式）
    response_text, metadata = await provider.generate_response(
        messages=messages,
        system_prompt="あなたは親切なアシスタントです。",
    )

    # 結果を検証
    assert response_text == "テスト応答"
    assert metadata["input_tokens"] == 10
    assert metadata["output_tokens"] == 5
    assert metadata["model"] == "claude-haiku-4-5"

    # APIが呼ばれたことを確認
    provider.client.messages.create.assert_called_once()


@pytest.mark.asyncio
async def test_anthropic_provider_api_call_with_mock(
    anthropic_provider_with_mock, mock_anthropic_response
):
    """実際のAPI呼び出し（モックを使用）のテスト

    Anthropic APIの呼び出しが正しく行われることを確認する。
    """
    provider = anthropic_provider_with_mock
    provider.client.messages.create = AsyncMock(return_value=mock_anthropic_response)

    messages = [Message(role=MessageRole.USER, content="テストメッセージ")]

    response_text, metadata = await provider.generate_response(
        messages=messages,
        system_prompt="システムプロンプト",
        model="claude-haiku-4-5",
        max_tokens=100,
    )

    # 応答が正しく返されることを確認
    assert response_text == "テスト応答"
    assert metadata["input_tokens"] == 10
    assert metadata["output_tokens"] == 5

    # API呼び出しの引数を確認
    call_args = provider.client.messages.create.call_args
    assert call_args is not None
    assert call_args.kwargs["model"] == "claude-haiku-4-5"
    assert call_args.kwargs["max_tokens"] == 100
    assert call_args.kwargs["system"] == "システムプロンプト"


@pytest.mark.asyncio
async def test_anthropic_provider_error_handling_rate_limit(
    anthropic_provider_with_mock,
):
    """レート制限エラー（429）の処理テスト

    429エラーが発生した場合、リトライが行われることを確認する。
    """
    provider = anthropic_provider_with_mock

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

    provider.client.messages.create = AsyncMock(
        side_effect=[rate_limit_error, rate_limit_error, success_response]
    )

    messages = [Message(role=MessageRole.USER, content="テスト")]

    # リトライが機能することを確認
    response_text, metadata = await provider.generate_response(messages=messages)

    assert response_text == "成功応答"
    # 3回呼ばれたことを確認（2回のリトライ + 1回の成功）
    assert provider.client.messages.create.call_count == 3


@pytest.mark.asyncio
async def test_anthropic_provider_error_handling_auth_error(
    anthropic_provider_with_mock,
):
    """認証エラー（401）の処理テスト

    401エラーが発生した場合、リトライしないことを確認する。
    """
    provider = anthropic_provider_with_mock

    # 401エラーをシミュレート
    mock_response = MagicMock()
    mock_response.status_code = 401
    auth_error = anthropic.AuthenticationError(
        message="Invalid API key",
        response=mock_response,
        body={},
    )
    auth_error.status_code = 401

    provider.client.messages.create = AsyncMock(side_effect=auth_error)

    messages = [Message(role=MessageRole.USER, content="テスト")]

    # 認証エラーが発生することを確認（リトライしない）
    with pytest.raises(anthropic.AuthenticationError):
        await provider.generate_response(messages=messages)

    # 1回だけ呼ばれたことを確認（リトライしない）
    assert provider.client.messages.create.call_count == 1


@pytest.mark.asyncio
async def test_anthropic_provider_error_handling_api_error(
    anthropic_provider_with_mock,
):
    """APIエラー（500など）の処理テスト

    一時的なAPIエラーが発生した場合、リトライが行われることを確認する。
    """
    provider = anthropic_provider_with_mock

    # 500エラーをシミュレート（APIStatusErrorを使用）
    mock_response = MagicMock()
    mock_response.status_code = 500
    # APIStatusErrorを作成（500エラー用）
    api_error = anthropic.APIStatusError(
        message="Internal server error",
        response=mock_response,
        body={},
    )
    api_error.status_code = 500

    # 最初の2回は500エラー、3回目で成功
    success_response = MagicMock()
    success_response.content = [MagicMock(type="text", text="成功応答")]
    success_response.usage = MagicMock(input_tokens=10, output_tokens=5)
    success_response.model = "claude-haiku-4-5"

    provider.client.messages.create = AsyncMock(
        side_effect=[api_error, api_error, success_response]
    )

    messages = [Message(role=MessageRole.USER, content="テスト")]

    # リトライが機能することを確認
    response_text, metadata = await provider.generate_response(messages=messages)

    assert response_text == "成功応答"
    # 3回呼ばれたことを確認（2回のリトライ + 1回の成功）
    assert provider.client.messages.create.call_count == 3


@pytest.mark.asyncio
async def test_anthropic_provider_error_handling_empty_content(
    anthropic_provider_with_mock,
):
    """空のコンテンツエラーの処理テスト

    空のコンテンツが返された場合、エラーが発生することを確認する。
    """
    provider = anthropic_provider_with_mock

    # 空のコンテンツをシミュレート
    empty_response = MagicMock()
    empty_response.content = []

    provider.client.messages.create = AsyncMock(return_value=empty_response)

    messages = [Message(role=MessageRole.USER, content="テスト")]

    # エラーが発生することを確認
    with pytest.raises(ValueError, match="No content in response"):
        await provider.generate_response(messages=messages)


@pytest.mark.asyncio
async def test_anthropic_provider_metadata_return(
    anthropic_provider_with_mock, mock_anthropic_response
):
    """メタデータの返却テスト

    メタデータが正しく返されることを確認する。
    """
    provider = anthropic_provider_with_mock
    provider.client.messages.create = AsyncMock(return_value=mock_anthropic_response)

    messages = [Message(role=MessageRole.USER, content="テスト")]

    response_text, metadata = await provider.generate_response(messages=messages)

    # メタデータの内容を確認
    assert "input_tokens" in metadata
    assert "output_tokens" in metadata
    assert "model" in metadata
    assert metadata["input_tokens"] == 10
    assert metadata["output_tokens"] == 5
    assert metadata["model"] == "claude-haiku-4-5"


@pytest.mark.asyncio
async def test_anthropic_provider_model_name_conversion(
    anthropic_provider_with_mock, mock_anthropic_response
):
    """モデル名変換の統合テスト

    LiteLLM形式からAnthropic SDK形式への変換が正しく行われることを確認する。
    """
    provider = anthropic_provider_with_mock
    provider.client.messages.create = AsyncMock(return_value=mock_anthropic_response)

    messages = [Message(role=MessageRole.USER, content="テスト")]

    # LiteLLM形式のモデル名を指定
    response_text, metadata = await provider.generate_response(
        messages=messages, model="anthropic/claude-haiku-4-5"
    )

    # モデル名が正しく変換されていることを確認
    call_args = provider.client.messages.create.call_args
    assert call_args.kwargs["model"] == "claude-haiku-4-5"
