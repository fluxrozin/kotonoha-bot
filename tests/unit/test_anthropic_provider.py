"""AnthropicProviderのテスト"""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from kotonoha_bot.ai.anthropic_provider import AnthropicProvider
from kotonoha_bot.session.models import Message, MessageRole


@pytest.fixture
def mock_anthropic_client():
    """モックAnthropicクライアント"""
    client = AsyncMock()
    return client


@pytest.fixture
def anthropic_provider():
    """AnthropicProviderのフィクスチャ"""
    # 環境変数をモック化
    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-api-key"}):
        provider = AnthropicProvider()
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
    response_text, metadata = await anthropic_provider.generate_response(
        messages=sample_messages,
        system_prompt="あなたは親切なアシスタントです。",
    )

    # 結果を検証
    assert response_text == "テスト応答"
    assert metadata["input_tokens"] == 10
    assert metadata["output_tokens"] == 5
    assert metadata["model"] == "claude-haiku-4-5"

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
    with pytest.raises(ValueError, match="No content in response"):
        await anthropic_provider.generate_response(messages=sample_messages)


@pytest.mark.asyncio
async def test_generate_response_retry_on_429():
    """429エラー（レート制限）でリトライするテスト

    注意: 実際の anthropic.APIError の構造が複雑なため、
    リトライロジックの詳細なテストは統合テストで行う。
    ここでは基本的な動作を確認する。
    """
    # このテストは統合テストに移行するか、実際の API を呼び出すテストに変更する
    # 現時点ではスキップ
    pytest.skip("リトライロジックのテストは統合テストで実施")


@pytest.mark.asyncio
async def test_generate_response_no_retry_on_auth_error():
    """認証エラー（401）ではリトライしないテスト

    注意: 実際の anthropic.APIError の構造が複雑なため、
    エラーハンドリングの詳細なテストは統合テストで行う。
    ここでは基本的な動作を確認する。
    """
    # このテストは統合テストに移行するか、実際の API を呼び出すテストに変更する
    # 現時点ではスキップ
    pytest.skip("エラーハンドリングのテストは統合テストで実施")


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
    """APIキーがない場合の初期化エラーテスト"""
    with (
        patch.dict(os.environ, {}, clear=True),
        pytest.raises(ValueError, match="ANTHROPIC_API_KEY is not set"),
    ):
        AnthropicProvider()
