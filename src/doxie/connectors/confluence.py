"""Confluence connector skeleton using atlassian-python-api.

Provides asynchronous interface compatible with the BaseConnector while
internally relying on the synchronous Confluence client. Full implementation
of pagination, mapping to ParsedDocument, and persistence will be added later.
"""
from __future__ import annotations

from typing import List, Optional, Dict, Any

from atlassian import Confluence

from doxie.connectors.base_connector import BaseConnector
from doxie.parsers.base_parser import ParsedDocument
from doxie.parsers.html_parser import HTMLParser


class ConfluenceConnector(BaseConnector):
    """Connector for Confluence Cloud/Server.

    Parameters
    ----------
    base_url:
        Base URL of the Confluence instance, e.g. https://your-domain.atlassian.net/wiki
    username:
        Username/email for Confluence (Cloud often uses email).
    token:
        API token (Cloud) or password (Server/DC). Passed as password to the client.
    space:
        Default space key to sync from.
    cloud:
        Whether connecting to Confluence Cloud.
    verify_ssl:
        Whether to verify SSL certificates.
    html_parser:
        Parser used to transform Confluence HTML content to ParsedDocument.
    """

    def __init__(
        self,
        *,
        base_url: str,
        username: Optional[str] = None,
        token: Optional[str] = None,
        space: Optional[str] = None,
        cloud: bool = True,
        verify_ssl: bool = True,
        html_parser: Optional[HTMLParser] = None,
    ) -> None:
        self._client = Confluence(
            url=base_url,
            username=username,
            password=token,
            cloud=cloud,
            verify_ssl=verify_ssl,
        )
        self._space = space
        self._parser = html_parser or HTMLParser()

    async def fetch_content(self, space: Optional[str] = None, limit: Optional[int] = None) -> List[ParsedDocument]:
        """Fetch pages from Confluence and parse to ParsedDocument list.

        Parameters
        ----------
        space: str | None
            Space key to fetch from. If not provided, falls back to the connector's
            default space.
        limit: int | None
            Maximum number of documents to return. Defaults to API/page defaults.

        Notes
        -----
        The underlying client is synchronous; for an MVP we call it directly.
        """
        space_key = space or self._space
        if not space_key:
            return []

        try:
            pages = self._client.get_all_pages_from_space(space_key, start=0, limit=limit or 50)
        except Exception:
            pages = []

        docs: List[ParsedDocument] = []
        for p in pages or []:
            page_id = None
            title = None
            if isinstance(p, dict):
                pid = p.get("id")
                page_id = str(pid) if pid is not None else None
                title = p.get("title")
            if not page_id:
                continue
            try:
                page = self._client.get_page_by_id(page_id, expand="body.storage")
                body_html = ""
                if isinstance(page, dict):
                    body_html = (
                        page.get("body", {}).get("storage", {}).get("value", "")  # type: ignore[assignment]
                    )
            except Exception:
                body_html = ""

            parsed = self._parser.parse_html_content(
                body_html,
                metadata={
                    "source": "confluence",
                    "space": space_key,
                    "page_id": page_id,
                    "title": title or "",
                },
            )
            docs.append(parsed)
            if limit is not None and len(docs) >= int(limit):
                break

        return docs

    async def sync(self) -> None:
        """Run a synchronization pass (fetch + persistence + indexing).

        This skeleton fetches content but does not yet persist or index it.
        """
        _ = await self.fetch_content()
        # TODO: persist to DB and update search index

    async def list_spaces(self, limit: Optional[int] = None) -> List[dict]:
        """List accessible Confluence spaces (key and name).

        Returns a list of dicts: {"key": str, "name": str}
        """
        try:
            spaces = self._client.get_all_spaces(start=0, limit=limit or 50)
        except Exception:
            spaces = []

        results: List[dict] = []
        # The API may return a dict with 'results' or a list of dicts
        items = []
        if isinstance(spaces, dict):
            items = spaces.get("results", [])  # type: ignore[assignment]
        elif isinstance(spaces, list):
            items = spaces

        for s in items or []:
            if not isinstance(s, dict):
                continue
            key = s.get("key") or (s.get("spaceKey") if isinstance(s.get("spaceKey"), str) else None)
            name = s.get("name")
            if key and isinstance(key, str):
                results.append({"key": key, "name": name or ""})

        return results

    async def fetch_content_for_spaces(self, spaces: List[str], limit_per_space: Optional[int] = None) -> List[ParsedDocument]:
        """Fetch content across multiple spaces and return a combined list of docs."""
        all_docs: List[ParsedDocument] = []
        for space in spaces:
            docs = await self.fetch_content(space=space, limit=limit_per_space)
            all_docs.extend(docs)
        return all_docs

    async def create_page(
        self,
        *,
        space: str,
        title: str,
        content: str,
        parent_id: Optional[str] = None,
        representation: str = "storage",
    ) -> Dict[str, Any]:
        """Create a Confluence page in a space.

        Parameters
        ----------
        space: str
            Space key (e.g., "DOCS").
        title: str
            Page title.
        content: str
            Page body in the specified representation.
        parent_id: str | None
            Optional parent page ID to create a child page under.
        representation: str
            Content representation (default: "storage").
        """
        try:
            page = self._client.create_page(
                space=space,
                title=title,
                body=content,
                parent_id=(parent_id or None),
                type="page",
                representation=representation,
            )
        except Exception as e:  # pragma: no cover - bubble up to caller
            raise e
        return page or {}

    async def get_page_by_id(self, page_id: str, expand: str = "body.storage") -> Dict[str, Any]:
        """Fetch a page by ID with optional expand."""
        try:
            page = self._client.get_page_by_id(page_id, expand=expand)
        except Exception as e:
            raise e
        return page or {}

    async def get_page_id(self, space: str, title: str) -> Optional[str]:
        """Return page ID by space and title, if found."""
        try:
            pid = self._client.get_page_id(space, title)
        except Exception:
            pid = None
        if pid is None:
            return None
        return str(pid)

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
    ) -> Dict[str, Any]:
        """Update an existing Confluence page.

        If title is not provided, the current title will be fetched and reused (client requires title).
        If content is None, the existing body will be preserved.
        """
        # Ensure we have a title
        current_title = None
        current_body = None
        if title is None or content is None:
            page = await self.get_page_by_id(page_id, expand="body.storage")
            if isinstance(page, dict):
                current_title = page.get("title")
                current_body = page.get("body", {}).get("storage", {}).get("value", "")
        final_title = title or (current_title or "")
        final_body = content if content is not None else (current_body or "")

        try:
            updated = self._client.update_page(
                page_id=page_id,
                title=final_title,
                body=final_body,
                parent_id=(parent_id or None),
                type="page",
                representation=representation,
                minor_edit=minor_edit,
                version_comment=(version_comment or None),
            )
        except Exception as e:  # pragma: no cover
            raise e
        return updated or {}
