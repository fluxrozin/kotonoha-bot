"""Embedding プロバイダー抽象化."""

from abc import ABC, abstractmethod


class EmbeddingProvider(ABC):
    """Embedding 生成プロバイダーのインターフェース."""

    @abstractmethod
    async def generate_embedding(self, text: str) -> list[float]:
        """テキストからベクトルを生成.

        Args:
            text: ベクトル化するテキスト

        Returns:
            ベクトル（1536次元のリスト）
        """
        pass

    @abstractmethod
    def get_dimension(self) -> int:
        """ベクトルの次元数を返す.

        Returns:
            ベクトルの次元数（例: 1536）
        """
        pass


__all__ = ["EmbeddingProvider"]
