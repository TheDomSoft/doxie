"""Base source abstractions used by MCP tools.

A `ContentSource` presents a stable interface for tools to interact with
content regardless of the underlying connector implementation.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional

from doxie.parsers.base_parser import ParsedDocument


class ContentSource(ABC):
    """Abstract content source used by MCP tools."""

    @abstractmethod
    async def fetch(self, limit: Optional[int] = None) -> List[ParsedDocument]:
        """Fetch documents from the source, optionally limited."""
        raise NotImplementedError

    @abstractmethod
    async def sync(self) -> None:
        """Run a synchronization pass for this source."""
        raise NotImplementedError
