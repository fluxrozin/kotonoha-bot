"""OpenAI Embedding API プロバイダー"""

import os

import openai
import structlog
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from . import EmbeddingProvider

logger = structlog.get_logger(__name__)


class OpenAIEmbeddingProvider(EmbeddingProvider):
    """OpenAI text-embedding-3-small を使用（リトライロジック付き）"""

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY is not set")
        self.model = "text-embedding-3-small"
        self.dimension = 1536
        self._client = openai.AsyncOpenAI(api_key=self.api_key)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=60),
        retry=retry_if_exception_type((openai.RateLimitError, openai.APITimeoutError)),
        reraise=True,
    )
    async def generate_embedding(self, text: str) -> list[float]:
        """テキストからベクトルを生成（リトライロジック付き）

        Args:
            text: ベクトル化するテキスト

        Returns:
            ベクトル（1536次元のリスト）

        Raises:
            openai.RateLimitError: レート制限エラー
            openai.APITimeoutError: タイムアウトエラー
            openai.APIError: APIエラー
        """
        try:
            response = await self._client.embeddings.create(
                model=self.model,
                input=text,
                dimensions=self.dimension,
            )
            return response.data[0].embedding
        except openai.RateLimitError as e:
            logger.warning(f"Rate limit hit, retrying...: {e}")
            raise
        except openai.APITimeoutError as e:
            logger.warning(f"API timeout, retrying...: {e}")
            raise
        except openai.APIError as e:
            logger.error(f"OpenAI API error: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in generate_embedding: {e}", exc_info=True)
            raise

    async def generate_embeddings_batch(self, texts: list[str]) -> list[list[float]]:
        """複数のテキストをバッチでベクトル化（API効率化）

        ⚠️ 改善: OpenAI Embedding APIはバッチリクエストをサポートしているため、
        個別にAPIを呼ぶのではなく、バッチで一度に送信することで効率化します。
        API呼び出し回数を大幅に削減（100回→1回）、レート制限にかかりにくくなります。

        Args:
            texts: ベクトル化するテキストのリスト

        Returns:
            ベクトルのリスト（各要素は1536次元のリスト）

        Raises:
            openai.RateLimitError: レート制限エラー
            openai.APITimeoutError: タイムアウトエラー
            openai.APIError: APIエラー
        """
        try:
            response = await self._client.embeddings.create(
                model=self.model,
                input=texts,  # リストを直接渡せる
                dimensions=self.dimension,
            )
            return [data.embedding for data in response.data]
        except openai.RateLimitError as e:
            logger.warning(f"Rate limit hit in batch embedding: {e}")
            raise
        except openai.APITimeoutError as e:
            logger.warning(f"API timeout in batch embedding: {e}")
            raise
        except openai.APIError as e:
            logger.error(f"OpenAI API error in batch embedding: {e}")
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error in generate_embeddings_batch: {e}",
                exc_info=True,
            )
            raise

    def get_dimension(self) -> int:
        """ベクトルの次元数（1536）"""
        return self.dimension
