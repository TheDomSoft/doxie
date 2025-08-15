"""Confluence connector skeleton using atlassian-python-api.

Provides asynchronous interface compatible with the BaseConnector while
internally relying on the synchronous Confluence client. Full implementation
of pagination, mapping to ParsedDocument, and persistence will be added later.
"""
from __future__ import annotations

from typing import List, Optional

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
