"""OpenAIEmbeddingProvider のテスト"""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from kotonoha_bot.external.embedding.openai_embedding import (
    OpenAIEmbeddingProvider,
)


@pytest.fixture
def mock_openai_client():
    """OpenAIクライアントのモック"""
    with patch(
        "kotonoha_bot.external.embedding.openai_embedding.openai.AsyncOpenAI"
    ) as mock:
        client_instance = AsyncMock()
        mock.return_value = client_instance
        yield client_instance


@pytest.fixture
def embedding_provider(mock_openai_client):
    """OpenAIEmbeddingProviderのフィクスチャ"""
    # テスト用のAPIキーを設定
    with patch.dict(os.environ, {"OPENAI_API_KEY": "test-api-key"}):
        provider = OpenAIEmbeddingProvider()
        provider._client = mock_openai_client
        return provider


@pytest.mark.asyncio
async def test_openai_embedding_provider_initialization(embedding_provider):
    """OpenAIEmbeddingProviderの初期化テスト"""
    assert embedding_provider.model == "text-embedding-3-small"
    assert embedding_provider.dimension == 1536
    assert embedding_provider.get_dimension() == 1536


def test_openai_embedding_provider_initialization_without_api_key():
    """APIキーなしでの初期化エラーテスト"""
    with (
        patch.dict(os.environ, {}, clear=True),
        pytest.raises(ValueError, match="OPENAI_API_KEY is not set"),
    ):
        OpenAIEmbeddingProvider()


def test_openai_embedding_provider_initialization_with_custom_api_key():
    """カスタムAPIキーでの初期化テスト"""
    provider = OpenAIEmbeddingProvider(api_key="custom-api-key")
    assert provider.api_key == "custom-api-key"


@pytest.mark.asyncio
async def test_generate_embedding_success(embedding_provider, mock_openai_client):
    """generate_embeddingの成功テスト"""
    # モックのレスポンスを設定
    mock_response = MagicMock()
    mock_response.data = [MagicMock(embedding=[0.1] * 1536)]
    mock_openai_client.embeddings.create = AsyncMock(return_value=mock_response)

    # テスト実行
    result = await embedding_provider.generate_embedding("テストテキスト")

    # 結果の検証
    assert len(result) == 1536
    assert all(isinstance(x, float) for x in result)
    assert all(x == 0.1 for x in result)

    # API呼び出しの検証
    mock_openai_client.embeddings.create.assert_called_once()
    call_args = mock_openai_client.embeddings.create.call_args
    assert call_args.kwargs["model"] == "text-embedding-3-small"
    assert call_args.kwargs["input"] == "テストテキスト"
    assert call_args.kwargs["dimensions"] == 1536


@pytest.mark.asyncio
async def test_generate_embeddings_batch_success(
    embedding_provider, mock_openai_client
):
    """generate_embeddings_batchの成功テスト"""
    # モックのレスポンスを設定
    texts = ["テキスト1", "テキスト2", "テキスト3"]
    mock_response = MagicMock()
    mock_response.data = [
        MagicMock(embedding=[0.1] * 1536),
        MagicMock(embedding=[0.2] * 1536),
        MagicMock(embedding=[0.3] * 1536),
    ]
    mock_openai_client.embeddings.create = AsyncMock(return_value=mock_response)

    # テスト実行
    results = await embedding_provider.generate_embeddings_batch(texts)

    # 結果の検証
    assert len(results) == 3
    assert all(len(embedding) == 1536 for embedding in results)
    assert all(embedding[0] == 0.1 for embedding in [results[0]])
    assert all(embedding[0] == 0.2 for embedding in [results[1]])
    assert all(embedding[0] == 0.3 for embedding in [results[2]])

    # API呼び出しの検証
    mock_openai_client.embeddings.create.assert_called_once()
    call_args = mock_openai_client.embeddings.create.call_args
    assert call_args.kwargs["model"] == "text-embedding-3-small"
    assert call_args.kwargs["input"] == texts
    assert call_args.kwargs["dimensions"] == 1536


@pytest.mark.asyncio
async def test_generate_embedding_rate_limit_error(
    embedding_provider, mock_openai_client
):
    """generate_embeddingのレート制限エラーテスト"""
    import openai

    # レート制限エラーを発生させる
    mock_openai_client.embeddings.create = AsyncMock(
        side_effect=openai.RateLimitError(
            "Rate limit exceeded", response=MagicMock(), body=None
        )
    )

    # リトライロジックが動作することを確認（tenacityがリトライする）
    with pytest.raises(openai.RateLimitError):
        await embedding_provider.generate_embedding("テストテキスト")

    # リトライが試みられたことを確認（複数回呼ばれる可能性がある）
    assert mock_openai_client.embeddings.create.call_count >= 1


@pytest.mark.asyncio
async def test_generate_embedding_timeout_error(embedding_provider, mock_openai_client):
    """generate_embeddingのタイムアウトエラーテスト"""
    import openai

    # タイムアウトエラーを発生させる
    mock_openai_client.embeddings.create = AsyncMock(
        side_effect=openai.APITimeoutError(request=MagicMock())
    )

    # リトライロジックが動作することを確認
    with pytest.raises(openai.APITimeoutError):
        await embedding_provider.generate_embedding("テストテキスト")

    # リトライが試みられたことを確認
    assert mock_openai_client.embeddings.create.call_count >= 1


@pytest.mark.asyncio
async def test_generate_embedding_api_error(embedding_provider, mock_openai_client):
    """generate_embeddingのAPIエラーテスト"""
    import openai

    # APIエラーを発生させる
    mock_openai_client.embeddings.create = AsyncMock(
        side_effect=openai.APIError(message="API error", request=MagicMock(), body=None)
    )

    # エラーが発生することを確認
    with pytest.raises(openai.APIError):
        await embedding_provider.generate_embedding("テストテキスト")


@pytest.mark.asyncio
async def test_generate_embeddings_batch_rate_limit_error(
    embedding_provider, mock_openai_client
):
    """generate_embeddings_batchのレート制限エラーテスト"""
    import openai

    # レート制限エラーを発生させる
    mock_openai_client.embeddings.create = AsyncMock(
        side_effect=openai.RateLimitError(
            "Rate limit exceeded", response=MagicMock(), body=None
        )
    )

    # リトライロジックが動作することを確認
    with pytest.raises(openai.RateLimitError):
        await embedding_provider.generate_embeddings_batch(["テキスト1", "テキスト2"])

    # リトライが試みられたことを確認
    assert mock_openai_client.embeddings.create.call_count >= 1


@pytest.mark.asyncio
async def test_generate_embeddings_batch_timeout_error(
    embedding_provider, mock_openai_client
):
    """generate_embeddings_batchのタイムアウトエラーテスト"""
    import openai

    # タイムアウトエラーを発生させる
    mock_openai_client.embeddings.create = AsyncMock(
        side_effect=openai.APITimeoutError(request=MagicMock())
    )

    # リトライロジックが動作することを確認
    with pytest.raises(openai.APITimeoutError):
        await embedding_provider.generate_embeddings_batch(["テキスト1", "テキスト2"])

    # リトライが試みられたことを確認
    assert mock_openai_client.embeddings.create.call_count >= 1


@pytest.mark.asyncio
async def test_generate_embeddings_batch_api_error(
    embedding_provider, mock_openai_client
):
    """generate_embeddings_batchのAPIエラーテスト"""
    import openai

    # APIエラーを発生させる
    mock_openai_client.embeddings.create = AsyncMock(
        side_effect=openai.APIError("API error", request=MagicMock(), body=None)
    )

    # エラーが発生することを確認
    with pytest.raises(openai.APIError):
        await embedding_provider.generate_embeddings_batch(["テキスト1", "テキスト2"])


@pytest.mark.asyncio
async def test_generate_embedding_unexpected_error(
    embedding_provider, mock_openai_client
):
    """generate_embeddingの予期しないエラーテスト"""
    # 予期しないエラーを発生させる
    mock_openai_client.embeddings.create = AsyncMock(
        side_effect=ValueError("Unexpected error")
    )

    # エラーが発生することを確認
    with pytest.raises(ValueError, match="Unexpected error"):
        await embedding_provider.generate_embedding("テストテキスト")


@pytest.mark.asyncio
async def test_generate_embeddings_batch_unexpected_error(
    embedding_provider, mock_openai_client
):
    """generate_embeddings_batchの予期しないエラーテスト"""
    # 予期しないエラーを発生させる
    mock_openai_client.embeddings.create = AsyncMock(
        side_effect=ValueError("Unexpected error")
    )

    # エラーが発生することを確認
    with pytest.raises(ValueError, match="Unexpected error"):
        await embedding_provider.generate_embeddings_batch(["テキスト1", "テキスト2"])


@pytest.mark.asyncio
async def test_generate_embedding_empty_text(embedding_provider, mock_openai_client):
    """空のテキストでのgenerate_embeddingテスト"""
    # モックのレスポンスを設定
    mock_response = MagicMock()
    mock_response.data = [MagicMock(embedding=[0.0] * 1536)]
    mock_openai_client.embeddings.create = AsyncMock(return_value=mock_response)

    # テスト実行
    result = await embedding_provider.generate_embedding("")

    # 結果の検証
    assert len(result) == 1536
    assert all(x == 0.0 for x in result)


@pytest.mark.asyncio
async def test_generate_embeddings_batch_empty_list(
    embedding_provider, mock_openai_client
):
    """空のリストでのgenerate_embeddings_batchテスト"""
    # モックのレスポンスを設定
    mock_response = MagicMock()
    mock_response.data = []
    mock_openai_client.embeddings.create = AsyncMock(return_value=mock_response)

    # テスト実行
    results = await embedding_provider.generate_embeddings_batch([])

    # 結果の検証
    assert len(results) == 0
