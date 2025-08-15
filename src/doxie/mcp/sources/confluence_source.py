"""Confluence content source wrapping the ConfluenceConnector."""
from __future__ import annotations

from typing import List, Optional

from doxie.connectors.confluence import ConfluenceConnector
from doxie.mcp.sources.base import ContentSource
from doxie.parsers.base_parser import ParsedDocument


class ConfluenceSource(ContentSource):
    """Content source backed by `ConfluenceConnector`."""

    def __init__(self, connector: ConfluenceConnector) -> None:
        self._connector = connector

    async def fetch(self, limit: Optional[int] = None) -> List[ParsedDocument]:
        docs = await self._connector.fetch_content()
        if limit is not None:
            return docs[: max(0, int(limit))]
        return docs

    async def fetch_by_space(self, space: str, limit: Optional[int] = None) -> List[ParsedDocument]:
        """Fetch documents from a specific Confluence space.

        This method does not persist results; it simply returns parsed documents.
        """
        docs = await self._connector.fetch_content(space=space, limit=limit)
        return docs

    async def sync(self) -> None:
        await self._connector.sync()
