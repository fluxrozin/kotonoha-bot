"""AI Provider抽象クラス"""
from abc import ABC, abstractmethod
from typing import List

from ..session.models import Message


class AIProvider(ABC):
    """AI Providerの抽象クラス"""

    @abstractmethod
    def generate_response(
        self,
        messages: List[Message],
        system_prompt: str | None = None
    ) -> str:
        """応答を生成

        Args:
            messages: 会話履歴
            system_prompt: システムプロンプト

        Returns:
            生成された応答テキスト
        """
        pass
