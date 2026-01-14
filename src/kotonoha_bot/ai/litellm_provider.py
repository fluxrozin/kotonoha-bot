"""LiteLLM統合実装"""
import litellm
from typing import List
import logging

from .provider import AIProvider
from ..session.models import Message, MessageRole
from ..config import Config

logger = logging.getLogger(__name__)


class LiteLLMProvider(AIProvider):
    """LiteLLM統合プロバイダー

    LiteLLMを使用して複数のLLMプロバイダーを統一インターフェースで利用。
    - 開発: anthropic/claude-3-haiku-20240307（レガシー、超低コスト）
    - 調整: anthropic/claude-sonnet-4-5（バランス型）
    - 本番: anthropic/claude-opus-4-5（最高品質）
    """

    def __init__(self, model: str = Config.LLM_MODEL):
        self.model = model
        self.fallback_model = Config.LLM_FALLBACK_MODEL
        logger.info(f"Initialized LiteLLM Provider: {model}")
        if self.fallback_model:
            logger.info(f"Fallback model: {self.fallback_model}")

    def generate_response(
        self,
        messages: List[Message],
        system_prompt: str | None = None
    ) -> str:
        """LiteLLM経由でLLM APIを呼び出して応答を生成"""
        try:
            # LiteLLM用のメッセージ形式に変換
            llm_messages = self._convert_messages(messages, system_prompt)

            # フォールバック設定
            fallbacks = [self.fallback_model] if self.fallback_model else None

            # APIリクエスト
            response = litellm.completion(
                model=self.model,
                messages=llm_messages,
                temperature=Config.LLM_TEMPERATURE,
                max_tokens=Config.LLM_MAX_TOKENS,
                fallbacks=fallbacks,
            )

            result = response.choices[0].message.content
            logger.info(f"Generated response: {len(result)} chars")
            return result

        except litellm.RateLimitError as e:
            logger.error(f"Rate limit exceeded: {e}")
            raise
        except litellm.AuthenticationError as e:
            logger.error(f"Authentication error: {e}")
            raise
        except Exception as e:
            logger.error(f"LiteLLM API error: {e}")
            raise

    def _convert_messages(
        self,
        messages: List[Message],
        system_prompt: str | None
    ) -> List[dict]:
        """LiteLLM用のメッセージ形式に変換"""
        llm_messages = []

        # システムプロンプトを最初に追加
        if system_prompt:
            llm_messages.append({
                "role": "system",
                "content": system_prompt
            })

        # 会話履歴を追加
        for message in messages:
            role = "user" if message.role == MessageRole.USER else "assistant"
            llm_messages.append({
                "role": role,
                "content": message.content
            })

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
