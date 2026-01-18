"""データベース抽象化レイヤー"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..session.models import ChatSession


class DatabaseProtocol(ABC):
    """セッション管理のみを抽象化するプロトコル（インターフェース）

    ⚠️ 改善（抽象化の粒度）: セッション管理と知識ベース管理を分離することで、
    抽象化の粒度を均一にし、単一責任の原則に従います。

    知識ベース関連のメソッドは `KnowledgeBaseProtocol` に分離されています。
    """

    @abstractmethod
    async def initialize(self) -> None:
        """データベースの初期化"""
        pass

    @abstractmethod
    async def close(self) -> None:
        """データベース接続のクローズ"""
        pass

    @abstractmethod
    async def save_session(self, session: "ChatSession") -> None:
        """セッションを保存"""
        pass

    @abstractmethod
    async def load_session(self, session_key: str) -> "ChatSession" | None:
        """セッションを読み込み"""
        pass

    @abstractmethod
    async def delete_session(self, session_key: str) -> None:
        """セッションを削除"""
        pass

    @abstractmethod
    async def load_all_sessions(self) -> list["ChatSession"]:
        """すべてのセッションを読み込み"""
        pass


class SearchResult(dict):
    """検索結果の型定義（TypedDictの代替としてdictを継承）"""

    chunk_id: int
    source_id: int
    content: str
    similarity: float
    source_type: str
    title: str
    uri: str | None
    source_metadata: dict | None


class KnowledgeBaseProtocol(ABC):
    """知識ベースを別プロトコルとして分離

    ⚠️ 改善（抽象化の粒度）: 知識ベース関連のメソッドを `DatabaseProtocol` から分離することで、
    抽象化の粒度を均一にし、単一責任の原則に従います。

    セッション管理は `DatabaseProtocol` に、知識ベース管理は `KnowledgeBaseProtocol` に分離されています。
    """

    @abstractmethod
    async def similarity_search(
        self,
        query_embedding: list[float],
        top_k: int = 10,
        filters: dict | None = None,
    ) -> list[SearchResult]:
        """類似度検索を実行"""
        pass

    @abstractmethod
    async def save_source(
        self,
        source_type: str,
        title: str,
        uri: str | None,
        metadata: dict,
        status: str = "pending",
    ) -> int:
        """知識ソースを保存し、IDを返す"""
        pass

    @abstractmethod
    async def save_chunk(
        self,
        source_id: int,
        content: str,
        location: dict | None = None,
        token_count: int | None = None,
    ) -> int:
        """知識チャンクを保存し、IDを返す"""
        pass
