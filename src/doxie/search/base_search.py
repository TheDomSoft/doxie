"""Abstract search interface for indexing and querying documents.

Defines the minimal surface for search backends (e.g., Whoosh), enabling
extensibility and testability via a common contract.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Iterable, List, Protocol


@dataclass(slots=True)
class SearchResult:
    """Represents a single search hit."""

    document_id: int
    score: float
    snippet: str | None = None


class Indexable(Protocol):
    """Minimal protocol for indexable items."""

    id: int
    text: str


class BaseSearch(ABC):
    """Abstract interface for search index implementations."""

    @abstractmethod
    def index_documents(self, items: Iterable[Indexable]) -> None:
        """Index or reindex a batch of documents."""

    @abstractmethod
    def delete_documents(self, ids: Iterable[int]) -> None:
        """Remove documents from the index by their IDs."""

    @abstractmethod
    def search(self, query: str, *, limit: int = 10, offset: int = 0) -> List[SearchResult]:
        """Execute a search query and return ranked results."""
        raise NotImplementedError
