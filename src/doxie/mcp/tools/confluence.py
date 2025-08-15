"""Confluence tools for FastMCP.

These tools use the sources abstraction so the agent is decoupled from
connector details.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from fastmcp import FastMCP

from doxie.parsers.base_parser import ParsedDocument


def _serialize_parsed_document(doc: ParsedDocument) -> Dict[str, Any]:
    return {
        "text": doc.text,
        "sections": [
            {
                "title": s.title,
                "level": s.level,
                "start_offset": s.start_offset,
                "end_offset": s.end_offset,
            }
            for s in doc.sections
        ],
        "metadata": dict(doc.metadata),
    }


def register_confluence_tools(mcp: FastMCP, get_state: Callable[[], Any]) -> None:
    """Register Confluence tools on the given FastMCP instance.

    The `get_state` callable should return an object with attribute
    `confluence_source` that provides `fetch(limit)` and `sync()`.
    """

    @mcp.tool
    async def confluence_fetch(limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Fetch content from Confluence and return serialized parsed documents."""
        state = get_state()
        if state is None or getattr(state, "confluence_source", None) is None:
            raise RuntimeError(
                "Confluence source is not configured. Provide confluence settings in config/.env."
            )
        docs = await state.confluence_source.fetch(limit=limit)
        return [_serialize_parsed_document(d) for d in docs]

    @mcp.tool
    async def confluence_fetch_space(space: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Fetch Confluence pages from a specific space (no persistence).

        Parameters
        ----------
        space: str
            Confluence space key, e.g. "ENG", "DOCS".
        limit: int | None
            Optional maximum number of documents to return.
        """
        state = get_state()
        if state is None or getattr(state, "confluence_source", None) is None:
            raise RuntimeError(
                "Confluence source is not configured. Provide confluence settings in config/.env."
            )
        docs = await state.confluence_source.fetch_by_space(space=space, limit=limit)
        return [_serialize_parsed_document(d) for d in docs]

    @mcp.tool
    async def confluence_sync() -> str:
        """Run a Confluence sync (fetch + persistence + indexing)."""
        state = get_state()
        if state is None or getattr(state, "confluence_source", None) is None:
            raise RuntimeError(
                "Confluence source is not configured. Provide confluence settings in config/.env."
            )
        await state.confluence_source.sync()
        return "ok"
