"""データ層（データベース抽象化）."""

from .base import DatabaseProtocol, KnowledgeBaseProtocol, SearchResult
from .models import ChatSession, Message, MessageRole, SessionType

__all__ = [
    "DatabaseProtocol",
    "KnowledgeBaseProtocol",
    "SearchResult",
    "ChatSession",
    "Message",
    "MessageRole",
    "SessionType",
]
