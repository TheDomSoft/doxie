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

    async def list_spaces(self, limit: Optional[int] = None) -> List[dict]:
        """List accessible Confluence spaces (key and name)."""
        return await self._connector.list_spaces(limit=limit)

    async def fetch_for_spaces(
        self, spaces: List[str], limit_per_space: Optional[int] = None
    ) -> List[ParsedDocument]:
        """Fetch documents across multiple spaces without persistence."""
        return await self._connector.fetch_content_for_spaces(
            spaces, limit_per_space=limit_per_space
        )

    async def create_page(
        self,
        *,
        space: str,
        title: str,
        content: str,
        parent_id: Optional[str] = None,
        representation: str = "storage",
    ) -> dict:
        """Create a Confluence page via the connector and return raw API response."""
        return await self._connector.create_page(
            space=space,
            title=title,
            content=content,
            parent_id=parent_id,
            representation=representation,
        )

    async def get_page_id(self, space: str, title: str) -> Optional[str]:
        """Resolve a page ID given space and title."""
        return await self._connector.get_page_id(space, title)

    async def get_page_by_id(self, page_id: str, expand: str = "body.storage") -> dict:
        """Fetch a page by ID via the connector (used for enforcement and updates)."""
        return await self._connector.get_page_by_id(page_id, expand=expand)

    async def update_page(
        self,
        *,
        page_id: str,
        title: Optional[str] = None,
        content: Optional[str] = None,
        parent_id: Optional[str] = None,
        representation: str = "storage",
        minor_edit: bool = False,
        version_comment: Optional[str] = None,
    ) -> dict:
        """Update a Confluence page via the connector and return raw API response."""
        return await self._connector.update_page(
            page_id=page_id,
            title=title,
            content=content,
            parent_id=parent_id,
            representation=representation,
            minor_edit=minor_edit,
            version_comment=version_comment,
        )
