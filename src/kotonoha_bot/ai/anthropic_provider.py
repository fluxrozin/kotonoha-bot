"""Anthropic SDK統合実装"""

import asyncio
import logging

import anthropic

from ..config import Config
from ..rate_limit.monitor import RateLimitMonitor
from ..rate_limit.token_bucket import TokenBucket
from ..session.models import Message, MessageRole
from .provider import AIProvider

logger = logging.getLogger(__name__)


class AnthropicProvider(AIProvider):
    """Anthropic SDK を使用した LLM プロバイダー

    Anthropic SDK を直接使用して Claude API を呼び出す。
    - 開発: claude-haiku-4-5（超低コスト）
    - 本番: claude-opus-4-5（最高品質）
    """

    def __init__(self, model: str = Config.LLM_MODEL):
        self.model = model
        self.max_retries = Config.LLM_MAX_RETRIES
        self.retry_delay_base = Config.LLM_RETRY_DELAY_BASE

        # Anthropic SDK クライアントの初期化
        api_key = Config.ANTHROPIC_API_KEY if hasattr(Config, "ANTHROPIC_API_KEY") else None
        if not api_key:
            # 環境変数から直接取得
            import os
            api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY is not set")
        
        self.client = anthropic.AsyncAnthropic(api_key=api_key)

        # レート制限モニターとトークンバケットの初期化
        self.rate_limit_monitor = RateLimitMonitor(
            window_seconds=Config.RATE_LIMIT_WINDOW,
            warning_threshold=Config.RATE_LIMIT_THRESHOLD,
        )
        self.token_bucket = TokenBucket(
            capacity=Config.RATE_LIMIT_CAPACITY,
            refill_rate=Config.RATE_LIMIT_REFILL,
        )
        # デフォルトのレート制限を設定（1分間に50リクエスト）
        self.rate_limit_monitor.set_rate_limit(
            "claude-api", limit=50, window_seconds=60
        )

        # 最後に使用したモデル名を追跡
        self._last_used_model: str | None = None

        logger.info(f"Initialized Anthropic Provider: {model}")
        logger.info(
            f"Retry settings: max_retries={self.max_retries}, delay_base={self.retry_delay_base}s"
        )
        logger.info(
            f"Rate limit settings: capacity={Config.RATE_LIMIT_CAPACITY}, "
            f"refill_rate={Config.RATE_LIMIT_REFILL}/s, "
            f"window={Config.RATE_LIMIT_WINDOW}s, "
            f"threshold={Config.RATE_LIMIT_THRESHOLD}"
        )

    async def generate_response(
        self,
        messages: list[Message],
        system_prompt: str | None = None,
        model: str | None = None,
        max_tokens: int | None = None,
    ) -> tuple[str, dict]:
        """Anthropic SDK 経由で LLM API を呼び出して応答を生成

        Returns:
            tuple[str, dict]: (応答テキスト, メタデータ)
            - メタデータには以下のキーが含まれる:
              - "input_tokens": int
              - "output_tokens": int
              - "model": str
        """
        # レート制限チェックとトークン取得
        endpoint = "claude-api"
        self.rate_limit_monitor.record_request(endpoint)
        self.rate_limit_monitor.check_rate_limit(endpoint)

        # トークンバケットからトークンを取得（タイムアウト: 30秒）
        if not await self.token_bucket.wait_for_tokens(tokens=1, timeout=30.0):
            raise RuntimeError("Rate limit: Could not acquire token within timeout")

        # Anthropic SDK 用のメッセージ形式に変換
        anthropic_messages = self._convert_messages(messages, system_prompt)

        # 使用するモデルを決定（LiteLLM の形式から Anthropic SDK の形式に変換）
        use_model = self._convert_model_name(model or self.model)
        use_max_tokens = max_tokens or Config.LLM_MAX_TOKENS

        # 最後に使用したモデル名を保存
        self._last_used_model = use_model

        # リトライロジック
        last_exception = None
        for attempt in range(self.max_retries + 1):
            try:
                # APIリクエスト
                response = await self.client.messages.create(
                    model=use_model,
                    max_tokens=use_max_tokens,
                    temperature=Config.LLM_TEMPERATURE,
                    system=system_prompt,
                    messages=anthropic_messages,
                )

                # レスポンスからテキストを取得
                if not response.content or len(response.content) == 0:
                    raise ValueError("No content in response")

                # Anthropic SDK のレスポンス形式に合わせて処理
                result_text = ""
                for content_block in response.content:
                    if content_block.type == "text":
                        result_text += content_block.text

                if not result_text:
                    raise ValueError("Empty response content")

                # メタデータを構築
                metadata = {
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens,
                    "model": response.model,
                }

                logger.info(
                    f"Generated response: {len(result_text)} chars, "
                    f"tokens: input={metadata['input_tokens']}, "
                    f"output={metadata['output_tokens']}"
                )

                return result_text, metadata

            except anthropic.APIError as e:
                # API エラー: リトライ可能なエラーかどうかを判定
                if e.status_code in [429, 500, 502, 503, 504]:
                    # 一時的なエラー: リトライ可能
                    last_exception = e
                    if attempt < self.max_retries:
                        delay = self.retry_delay_base * (2**attempt)
                        logger.warning(
                            f"API error (attempt {attempt + 1}/{self.max_retries + 1}): {e}. "
                            f"Retrying in {delay}s..."
                        )
                        await asyncio.sleep(delay)
                    else:
                        logger.error(
                            f"API error after {self.max_retries + 1} attempts: {e}"
                        )
                        raise
                else:
                    # 認証エラーなど、リトライ不可なエラー
                    logger.error(f"API error (non-retryable): {e}")
                    raise

            except Exception as e:
                # その他の予期しないエラー
                logger.error(f"Unexpected Anthropic API error: {e}")
                raise

        # この行には到達しないはずだが、念のため
        if last_exception:
            raise last_exception
        raise RuntimeError("Unexpected error in generate_response")

    def get_last_used_model(self) -> str:
        """最後に使用したモデル名を取得

        Returns:
            最後に使用したモデル名（未使用の場合はデフォルトモデル）
        """
        return self._last_used_model or self.model

    def get_rate_limit_usage(self, endpoint: str = "claude-api") -> float:
        """レート制限の使用率を取得

        Args:
            endpoint: API エンドポイント（デフォルト: "claude-api"）

        Returns:
            使用率（0.0-1.0、パーセンテージに変換する場合は * 100）
        """
        _, usage_rate = self.rate_limit_monitor.check_rate_limit(endpoint)
        return usage_rate

    def _convert_model_name(self, model: str) -> str:
        """LiteLLM のモデル名を Anthropic SDK のモデル名に変換

        Args:
            model: LiteLLM 形式のモデル名（例: "anthropic/claude-haiku-4-5"）

        Returns:
            Anthropic SDK 形式のモデル名（例: "claude-haiku-4-5"）
        """
        # "anthropic/" プレフィックスを削除
        if model.startswith("anthropic/"):
            return model[len("anthropic/"):]
        return model

    def _convert_messages(
        self, messages: list[Message], system_prompt: str | None
    ) -> list[dict]:
        """Anthropic SDK 用のメッセージ形式に変換

        Args:
            messages: 会話履歴
            system_prompt: システムプロンプト（Anthropic SDK では messages に含めない）

        Returns:
            Anthropic SDK 形式のメッセージリスト
        """
        anthropic_messages = []

        # 会話履歴を追加（システムプロンプトは messages.create の system パラメータで指定）
        for message in messages:
            role = "user" if message.role == MessageRole.USER else "assistant"
            anthropic_messages.append({"role": role, "content": message.content})

        return anthropic_messages
