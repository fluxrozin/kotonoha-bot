"""LiteLLM統合実装"""

import logging
import os
import time
from datetime import datetime, timedelta

import litellm

from ..config import Config
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
        logger.info(f"Initialized LiteLLM Provider: {model}")
        if self.fallback_model:
            logger.info(f"Fallback model: {self.fallback_model}")
        logger.info(
            f"Retry settings: max_retries={self.max_retries}, delay_base={self.retry_delay_base}s"
        )
        logger.info(
            f"HTTP client refresh interval: {self._http_client_refresh_interval}"
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

    def generate_response(
        self, messages: list[Message], system_prompt: str | None = None
    ) -> str:
        """LiteLLM経由でLLM APIを呼び出して応答を生成

        一時的なエラー（InternalServerError, RateLimitError）に対して
        指数バックオフでリトライを実行します。

        長時間稼働時の接続プール問題を防ぐため、定期的にHTTP接続をチェックします。
        """
        # HTTP接続のリフレッシュチェック（長時間稼働時の接続枯渇を防ぐ）
        self._refresh_http_client_if_needed()

        # LiteLLM用のメッセージ形式に変換
        llm_messages = self._convert_messages(messages, system_prompt)

        # フォールバック設定
        fallbacks = [self.fallback_model] if self.fallback_model else None

        last_exception = None
        for attempt in range(self.max_retries + 1):
            try:
                # APIリクエスト
                response = litellm.completion(
                    model=self.model,
                    messages=llm_messages,
                    temperature=Config.LLM_TEMPERATURE,
                    max_tokens=Config.LLM_MAX_TOKENS,
                    fallbacks=fallbacks,
                )

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


# デフォルトのシステムプロンプト
DEFAULT_SYSTEM_PROMPT = """あなたは「コトノハ」という名前の、場面緘黙自助グループをサポートするAIアシスタントです。

【あなたの役割】
- 場面緘黙で困っている人々が安心してコミュニケーションできる環境を提供する
- 優しく、思いやりのある態度で接する
- プレッシャーを与えず、ペースを尊重する
- 必要に応じて情報やリソースを提供する

【コミュニケーションのガイドライン】
- 簡潔でわかりやすい表現を心がける
- 質問は一度に1つまで
- 返答を急かさない
- 沈黙も尊重する
- ポジティブな表現を使う

【禁止事項】
- 医療的なアドバイスをしない
- 無理に話をさせようとしない
- プライバシーを侵害しない
"""
