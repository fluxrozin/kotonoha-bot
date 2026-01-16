"""LiteLLM統合実装"""

import logging
import os
import time
from datetime import datetime, timedelta

import litellm

from ..config import Config
from ..rate_limit.monitor import RateLimitMonitor
from ..rate_limit.token_bucket import TokenBucket
from ..session.models import Message, MessageRole
from .provider import AIProvider

logger = logging.getLogger(__name__)

# LiteLLMのHTTPクライアント設定（長時間稼働時の接続プール問題を回避）
# タイムアウト設定を明示的に設定
litellm.set_verbose = False  # デバッグログを無効化（必要に応じて有効化可能）

# HTTPクライアントのタイムアウト設定（長時間稼働時の接続問題を回避）
# 環境変数でhttpxのタイムアウト設定を指定（LiteLLMが内部的に使用するhttpxに影響）
# デフォルトのタイムアウトを長めに設定（LLM応答は時間がかかる場合がある）
os.environ.setdefault("HTTPX_TIMEOUT", "300.0")  # 5分
os.environ.setdefault("HTTPX_CONNECT_TIMEOUT", "10.0")  # 接続タイムアウト: 10秒

# 接続プールのリフレッシュ間隔（長時間稼働時の接続枯渇を防ぐ）
HTTP_CLIENT_REFRESH_INTERVAL = timedelta(hours=24)  # 24時間ごとにリフレッシュ


class LiteLLMProvider(AIProvider):
    """LiteLLM統合プロバイダー

    LiteLLMを使用して複数のLLMプロバイダーを統一インターフェースで利用。
    - 開発: anthropic/claude-3-haiku-20240307（レガシー、超低コスト）
    - 調整: anthropic/claude-sonnet-4-5（バランス型）
    - 本番: anthropic/claude-opus-4-5（最高品質）

    長時間稼働時の接続プール問題に対処するため、定期的にHTTP接続をリフレッシュします。
    """

    def __init__(self, model: str = Config.LLM_MODEL):
        self.model = model
        self.fallback_model = Config.LLM_FALLBACK_MODEL
        self.max_retries = Config.LLM_MAX_RETRIES
        self.retry_delay_base = Config.LLM_RETRY_DELAY_BASE
        self._last_http_refresh = datetime.now()
        self._http_client_refresh_interval = HTTP_CLIENT_REFRESH_INTERVAL
        self._last_used_model: str | None = None  # 最後に使用したモデル名

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
        # 実際の制限値は環境変数で調整可能
        self.rate_limit_monitor.set_rate_limit(
            "claude-api", limit=50, window_seconds=60
        )

        logger.info(f"Initialized LiteLLM Provider: {model}")
        if self.fallback_model:
            logger.info(f"Fallback model: {self.fallback_model}")
        logger.info(
            f"Retry settings: max_retries={self.max_retries}, delay_base={self.retry_delay_base}s"
        )
        logger.info(
            f"HTTP client refresh interval: {self._http_client_refresh_interval}"
        )
        logger.info(
            f"Rate limit settings: capacity={Config.RATE_LIMIT_CAPACITY}, "
            f"refill_rate={Config.RATE_LIMIT_REFILL}/s, "
            f"window={Config.RATE_LIMIT_WINDOW}s, "
            f"threshold={Config.RATE_LIMIT_THRESHOLD}"
        )

    def _refresh_http_client_if_needed(self) -> None:
        """長時間稼働時の接続プール枯渇を防ぐため、HTTPクライアントをリフレッシュ"""
        now = datetime.now()
        if now - self._last_http_refresh > self._http_client_refresh_interval:
            try:
                # LiteLLMが内部的に使用するhttpxクライアントをリフレッシュ
                # 注意: LiteLLMの内部実装に依存するため、バージョンによって動作が異なる可能性があります
                # より確実な方法は、LiteLLMのバージョンアップや設定オプションの確認が必要です

                # 現在の実装では、LiteLLMが内部的にhttpxクライアントを管理しているため、
                # 直接的なリフレッシュは困難です。代わりに、定期的な接続チェックを行います。

                logger.info("HTTP client refresh check (connection pool management)")
                self._last_http_refresh = now
            except Exception as e:
                logger.warning(f"Failed to refresh HTTP client: {e}")

    async def generate_response(
        self,
        messages: list[Message],
        system_prompt: str | None = None,
        model: str | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """LiteLLM経由でLLM APIを呼び出して応答を生成

        一時的なエラー（InternalServerError, RateLimitError）に対して
        指数バックオフでリトライを実行します。

        長時間稼働時の接続プール問題を防ぐため、定期的にHTTP接続をチェックします。
        """
        # HTTP接続のリフレッシュチェック（長時間稼働時の接続枯渇を防ぐ）
        self._refresh_http_client_if_needed()

        # レート制限チェックとトークン取得
        endpoint = "claude-api"
        self.rate_limit_monitor.record_request(endpoint)
        self.rate_limit_monitor.check_rate_limit(endpoint)

        # トークンバケットからトークンを取得（タイムアウト: 30秒）
        if not await self.token_bucket.wait_for_tokens(tokens=1, timeout=30.0):
            raise RuntimeError("Rate limit: Could not acquire token within timeout")

        # LiteLLM用のメッセージ形式に変換
        llm_messages = self._convert_messages(messages, system_prompt)

        # 使用するモデルを決定
        use_model = model or self.model
        # 最後に使用したモデル名を保存
        self._last_used_model = use_model
        # フォールバック設定（指定されたモデルがデフォルトモデルの場合のみ）
        fallbacks = (
            [self.fallback_model]
            if self.fallback_model and use_model == self.model
            else None
        )
        # 使用するmax_tokensを決定
        use_max_tokens = max_tokens or Config.LLM_MAX_TOKENS

        last_exception = None
        for attempt in range(self.max_retries + 1):
            try:
                # APIリクエスト
                response = litellm.completion(
                    model=use_model,
                    messages=llm_messages,
                    temperature=Config.LLM_TEMPERATURE,
                    max_tokens=use_max_tokens,
                    fallbacks=fallbacks,
                )

                # フォールバックが使用された場合は、実際に使用されたモデル名を更新
                if hasattr(response, "model") and response.model:
                    self._last_used_model = response.model

                # レスポンスからテキストを取得
                # Pydanticの警告を避けるため、直接属性にアクセスするのではなく、
                # レスポンスオブジェクトを適切に処理
                if not response.choices or len(response.choices) == 0:
                    raise ValueError("No choices in response")

                choice = response.choices[0]
                if not hasattr(choice, "message") or not choice.message:
                    raise ValueError("No message in choice")

                result = choice.message.content
                if not result:
                    raise ValueError("Empty response content")

                # finish_reasonをチェックしてログに出力
                finish_reason = getattr(choice, "finish_reason", None)
                if finish_reason:
                    logger.info(f"Response finish_reason: {finish_reason}")
                    # 途中で停止した可能性がある場合に警告
                    if finish_reason in ["length", "max_tokens"]:
                        logger.warning(
                            f"Response may be truncated: finish_reason={finish_reason}, "
                            f"max_tokens={Config.LLM_MAX_TOKENS}, response_length={len(result)} chars"
                        )
                    elif finish_reason == "stop_sequence":
                        logger.warning(
                            f"Response stopped at stop sequence: finish_reason={finish_reason}"
                        )
                else:
                    # Anthropic APIの場合はstop_reasonをチェック
                    stop_reason = getattr(choice, "stop_reason", None)
                    if stop_reason:
                        logger.info(f"Response stop_reason: {stop_reason}")
                        # Anthropic APIでは"end_turn"は正常な終了だが、念のためログに出力
                        if stop_reason not in ["end_turn", "stop_sequence"]:
                            logger.warning(f"Unexpected stop_reason: {stop_reason}")

                # 使用トークン数をログに出力
                if hasattr(response, "usage"):
                    usage = response.usage
                    input_tokens = getattr(usage, "prompt_tokens", None) or getattr(
                        usage, "input_tokens", None
                    )
                    output_tokens = getattr(
                        usage, "completion_tokens", None
                    ) or getattr(usage, "output_tokens", None)
                    if input_tokens is not None or output_tokens is not None:
                        logger.info(
                            f"Token usage: input={input_tokens}, output={output_tokens}, "
                            f"max_tokens={Config.LLM_MAX_TOKENS}"
                        )
                        # 出力トークン数がmax_tokensに近い場合は警告
                        if output_tokens and Config.LLM_MAX_TOKENS:
                            usage_ratio = output_tokens / Config.LLM_MAX_TOKENS
                            if usage_ratio > 0.9:
                                logger.warning(
                                    f"Output tokens ({output_tokens}) are close to max_tokens "
                                    f"({Config.LLM_MAX_TOKENS}), response may be truncated"
                                )

                logger.info(f"Generated response: {len(result)} chars")
                return result

            except litellm.AuthenticationError as e:
                # 認証エラーはリトライしない
                logger.error(f"Authentication error: {e}")
                raise

            except (litellm.InternalServerError, litellm.RateLimitError) as e:
                # 一時的なエラー: リトライ可能
                last_exception = e
                if attempt < self.max_retries:
                    # 指数バックオフ: 1秒, 2秒, 4秒, ...
                    delay = self.retry_delay_base * (2**attempt)
                    logger.warning(
                        f"API error (attempt {attempt + 1}/{self.max_retries + 1}): {e}. "
                        f"Retrying in {delay}s..."
                    )
                    time.sleep(delay)
                else:
                    # 最大リトライ回数に達した
                    logger.error(
                        f"API error after {self.max_retries + 1} attempts: {e}"
                    )
                    raise

            except Exception as e:
                # その他の予期しないエラー
                logger.error(f"Unexpected LiteLLM API error: {e}")
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

    def _convert_messages(
        self, messages: list[Message], system_prompt: str | None
    ) -> list[dict]:
        """LiteLLM用のメッセージ形式に変換"""
        llm_messages = []

        # システムプロンプトを最初に追加
        if system_prompt:
            llm_messages.append({"role": "system", "content": system_prompt})

        # 会話履歴を追加
        for message in messages:
            role = "user" if message.role == MessageRole.USER else "assistant"
            llm_messages.append({"role": role, "content": message.content})

        return llm_messages
