"""AI Provider抽象クラス"""

from abc import ABC, abstractmethod

from ..session.models import Message


class AIProvider(ABC):
    """AI Providerの抽象クラス"""

    @abstractmethod
    async def generate_response(
        self,
        messages: list[Message],
        system_prompt: str | None = None,
        model: str | None = None,
        max_tokens: int | None = None,
    ) -> tuple[str, dict]:
        """応答を生成

        Args:
            messages: 会話履歴
            system_prompt: システムプロンプト
            model: 使用するモデル（オプション）
            max_tokens: 最大トークン数（オプション）

        Returns:
            tuple[str, dict]: (応答テキスト, メタデータ)
            - メタデータには以下のキーが含まれる:
              - "input_tokens": int
              - "output_tokens": int
              - "model": str
        """
        pass
