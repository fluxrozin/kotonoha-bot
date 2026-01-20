"""AIサービス（抽象化レイヤー）.

AIプロバイダーの抽象化と実装を提供します。
Handler層が具体的なライブラリの例外を知らないように、独自例外にラッピングします。
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass

import anthropic
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from ..config import Config
from ..db.models import Message, MessageRole
from ..errors.ai import (
    AIAuthenticationError,
    AIRateLimitError,
    AIServiceError,
)
from ..rate_limit.monitor import RateLimitMonitor
from ..rate_limit.token_bucket import TokenBucket

logger = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class TokenInfo:
    """トークン使用情報.

    Attributes:
        input_tokens: 入力トークン数
        output_tokens: 出力トークン数
        total_tokens: 合計トークン数
        model_used: 使用したモデル名
        latency_ms: レイテンシ（ミリ秒）

    Note:
        将来的に services/types.py に移動する可能性があります。
        現在は services/ai.py でのみ使用されていますが、Phase 13/14（コスト管理・監査ログ）で
        他のモジュールからも使用される予定です。
    """

    input_tokens: int
    output_tokens: int
    total_tokens: int
    model_used: str
    latency_ms: int

    def __str__(self) -> str:
        """ログ用の文字列表現."""
        return (
            f"TokenInfo(model={self.model_used}, "
            f"input={self.input_tokens}, output={self.output_tokens}, "
            f"total={self.total_tokens}, latency={self.latency_ms}ms)"
        )


class AIProvider(ABC):
    """AI Providerの抽象クラス."""

    @abstractmethod
    async def generate_response(
        self,
        messages: list[Message],
        system_prompt: str | None = None,
        model: str | None = None,
        max_tokens: int | None = None,
    ) -> tuple[str, TokenInfo]:
        """応答を生成.

        Args:
            messages: 会話履歴
            system_prompt: システムプロンプト
            model: 使用するモデル（オプション）
            max_tokens: 最大トークン数（オプション）

        Returns:
            tuple[str, TokenInfo]: (応答テキスト, トークン使用情報)

        Raises:
            AIAuthenticationError: APIキーが無効な場合
            AIRateLimitError: リトライ上限を超えてレート制限にかかった場合
            AIServiceError: AIサービスで予期しないエラーが発生した場合
        """
        pass

    @abstractmethod
    def get_last_used_model(self) -> str:
        """最後に使用したモデル名を取得.

        Returns:
            最後に使用したモデル名（未使用の場合はデフォルトモデル）
        """
        pass

    @abstractmethod
    def get_rate_limit_usage(self, endpoint: str = "claude-api") -> float:
        """レート制限の使用率を取得.

        Args:
            endpoint: エンドポイント名（デフォルト: "claude-api"）

        Returns:
            レート制限の使用率（0.0-1.0）
        """
        pass


class AnthropicProvider(AIProvider):
    """Anthropic SDK を使用した LLM プロバイダー.

    Anthropic SDK を直接使用して Claude API を呼び出す。
    - 開発: claude-haiku-4-5（超低コスト）
    - 本番: claude-opus-4-5（最高品質）

    Attributes:
        model: 使用するモデル名
        client: Anthropic SDK クライアント
        rate_limit_monitor: レート制限モニター
    """

    def __init__(self, model: str | None = None, config: Config | None = None):
        """AnthropicProvider を初期化する.

        Args:
            model: 使用するモデル名（省略時は Config.LLM_MODEL）
            config: 設定インスタンス（依存性注入、必須）

        Raises:
            ValueError: config が None の場合、または ANTHROPIC_API_KEY が設定されていない場合
        """
        if config is None:
            raise ValueError("config parameter is required (DI pattern)")
        self.config = config
        self.model = model or self.config.LLM_MODEL
        self.max_retries = self.config.LLM_MAX_RETRIES
        self.retry_delay_base = self.config.LLM_RETRY_DELAY_BASE

        # Anthropic SDK クライアントの初期化
        api_key = self.config.ANTHROPIC_API_KEY
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY is not set")

        self.client = anthropic.AsyncAnthropic(api_key=api_key)

        # レート制限モニターとトークンバケットの初期化
        self.rate_limit_monitor = RateLimitMonitor(
            window_seconds=self.config.RATE_LIMIT_WINDOW,
            warning_threshold=self.config.RATE_LIMIT_THRESHOLD,
        )
        self.token_bucket = TokenBucket(
            capacity=self.config.RATE_LIMIT_CAPACITY,
            refill_rate=self.config.RATE_LIMIT_REFILL,
        )
        # デフォルトのレート制限を設定（1分間に50リクエスト）
        self.rate_limit_monitor.set_rate_limit(
            "claude-api", limit=50, window_seconds=60
        )

        # 最後に使用したモデル名を追跡
        self._last_used_model: str | None = None

        logger.info(f"Initialized Anthropic Provider: {self.model}")
        logger.info(
            f"Retry settings: max_retries={self.max_retries}, delay_base={self.retry_delay_base}s"
        )
        logger.info(
            f"Rate limit settings: capacity={self.config.RATE_LIMIT_CAPACITY}, "
            f"refill_rate={self.config.RATE_LIMIT_REFILL}/s, "
            f"window={self.config.RATE_LIMIT_WINDOW}s, "
            f"threshold={self.config.RATE_LIMIT_THRESHOLD}"
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type(AIRateLimitError),
        reraise=True,
    )
    async def generate_response(
        self,
        messages: list[Message],
        system_prompt: str | None = None,
        model: str | None = None,
        max_tokens: int | None = None,
    ) -> tuple[str, TokenInfo]:
        """AIプロバイダーを使用して応答を生成する.

        会話履歴を受け取り、設定されたモデル（Claude等）に問い合わせを行う。
        レート制限時は自動的にリトライを行う。

        Args:
            messages: OpenAI形式のメッセージリスト [{"role": "user", "content": "..."}]
            system_prompt: システムプロンプト（省略可）
            model: 使用するモデル名（省略可、デフォルトモデルを使用）
            max_tokens: 最大トークン数（省略可、デフォルト値を使用）

        Returns:
            生成された応答テキストと、トークン使用情報(TokenInfo)のタプル。

        Raises:
            AIAuthenticationError: APIキーが無効な場合
            AIRateLimitError: リトライ上限を超えてレート制限にかかった場合
            AIServiceError: AIサービスで予期しないエラーが発生した場合

        Note:
            リトライ処理は tenacity デコレータで自動的に行われます。
            メソッド内で例外をラッピングしてから raise することで、
            Tenacity が正しくリトライを実行します。
        """
        import time

        start_time = time.time()

        # レート制限チェックとトークン取得
        endpoint = "claude-api"
        self.rate_limit_monitor.record_request(endpoint)
        self.rate_limit_monitor.check_rate_limit(endpoint)

        # トークンバケットからトークンを取得（タイムアウト: 30秒）
        if not await self.token_bucket.wait_for_tokens(tokens=1, timeout=30.0):
            raise AIRateLimitError("Rate limit: Could not acquire token within timeout")

        # Anthropic SDK 用のメッセージ形式に変換
        anthropic_messages = self._convert_messages(messages, system_prompt)

        # 使用するモデルを決定（LiteLLM の形式から Anthropic SDK の形式に変換）
        use_model = self._convert_model_name(model or self.model)
        use_max_tokens = max_tokens or self.config.LLM_MAX_TOKENS

        # 最後に使用したモデル名を保存
        self._last_used_model = use_model

        try:
            # APIリクエスト
            response = await self.client.messages.create(
                model=use_model,
                max_tokens=use_max_tokens,
                temperature=self.config.LLM_TEMPERATURE,
                system=system_prompt,
                messages=anthropic_messages,
            )

            # レスポンスからテキストを取得
            if not response.content or len(response.content) == 0:
                raise AIServiceError("No content in response")

            # Anthropic SDK のレスポンス形式に合わせて処理
            result_text = ""
            for content_block in response.content:
                if content_block.type == "text":
                    result_text += content_block.text

            if not result_text:
                raise AIServiceError("Empty response content")

            # レイテンシを計算
            latency_ms = int((time.time() - start_time) * 1000)

            # TokenInfo を構築
            token_info = TokenInfo(
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                total_tokens=response.usage.input_tokens + response.usage.output_tokens,
                model_used=response.model,
                latency_ms=latency_ms,
            )

            logger.info(
                f"Generated response: {len(result_text)} chars, "
                f"tokens: input={token_info.input_tokens}, "
                f"output={token_info.output_tokens}, "
                f"latency={token_info.latency_ms}ms"
            )

            return result_text, token_info

        except anthropic.AuthenticationError as e:
            # 認証エラー: リトライ不可
            logger.error(f"API authentication error: {e}")
            raise AIAuthenticationError(f"API認証に失敗しました: {e}") from e
        except anthropic.RateLimitError as e:
            # レート制限エラー: リトライ可能（tenacity が処理）
            logger.warning(f"API rate limit error: {e}")
            raise AIRateLimitError(f"レート制限: {e}") from e
        except anthropic.APIError as e:
            # API エラー: リトライ可能なエラーかどうかを判定
            if hasattr(e, "status_code") and e.status_code in [429, 500, 502, 503, 504]:
                # 一時的なエラー: リトライ可能
                logger.warning(f"API error (retryable): {e}")
                raise AIRateLimitError(f"一時的なAPIエラー: {e}") from e
            else:
                # 認証エラーなど、リトライ不可なエラー
                logger.error(f"API error (non-retryable): {e}")
                raise AIServiceError(f"APIエラー: {e}") from e
        except Exception as e:
            # その他の予期しないエラー
            logger.error(f"Unexpected Anthropic API error: {e}")
            raise AIServiceError(f"予期しないエラー: {e}") from e

    def get_last_used_model(self) -> str:
        """最後に使用したモデル名を取得.

        Returns:
            最後に使用したモデル名（未使用の場合はデフォルトモデル）
        """
        return self._last_used_model or self.model

    def get_rate_limit_usage(self, endpoint: str = "claude-api") -> float:
        """レート制限の使用率を取得.

        Args:
            endpoint: API エンドポイント（デフォルト: "claude-api"）

        Returns:
            使用率（0.0-1.0、パーセンテージに変換する場合は * 100）
        """
        _, usage_rate = self.rate_limit_monitor.check_rate_limit(endpoint)
        return usage_rate

    def _convert_model_name(self, model: str) -> str:
        """LiteLLM のモデル名を Anthropic SDK のモデル名に変換.

        Args:
            model: LiteLLM 形式のモデル名（例: "anthropic/claude-haiku-4-5"）

        Returns:
            Anthropic SDK 形式のモデル名（例: "claude-haiku-4-5"）
        """
        # "anthropic/" プレフィックスを削除
        if model.startswith("anthropic/"):
            return model[len("anthropic/") :]
        return model

    def _convert_messages(
        self,
        messages: list[Message],
        system_prompt: str | None,  # noqa: ARG002
    ) -> list[dict]:
        """Anthropic SDK 用のメッセージ形式に変換.

        Args:
            messages: 会話履歴
            system_prompt: システムプロンプト（Anthropic SDK では messages に含めず、system パラメータとして別途渡すため、このメソッド内では未使用）

        Returns:
            Anthropic SDK 形式のメッセージリスト
        """
        anthropic_messages = []

        # 会話履歴を追加（システムプロンプトは messages.create の system パラメータで指定）
        for message in messages:
            role = "user" if message.role == MessageRole.USER else "assistant"
            anthropic_messages.append({"role": role, "content": message.content})

        return anthropic_messages
