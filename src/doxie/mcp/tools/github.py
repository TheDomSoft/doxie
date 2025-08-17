"""GitHub tools for FastMCP.

Provide tools to fetch Markdown docs from a repo and search them ephemerally.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from fastmcp import FastMCP

from doxie.connectors.github import GitHubConnector
from doxie.parsers.base_parser import ParsedDocument
from doxie.search.ephemeral import search_docs_ephemeral


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


def register_github_tools(mcp: FastMCP, get_state: Callable[[], Any]) -> None:
    """Register GitHub tools on the given FastMCP instance.

    Reads config from state.settings.github (token and base URLs).
    """

    def _make_connector(state_obj: Any) -> GitHubConnector:
        settings = getattr(state_obj, "settings", None)
        gcfg = getattr(settings, "github", None)
        return GitHubConnector(
            api_base_url=(getattr(gcfg, "api_base_url", None) or "https://api.github.com"),
            web_base_url=(getattr(gcfg, "web_base_url", None) or "https://github.com"),
            raw_base_url=(
                getattr(gcfg, "raw_base_url", None) or "https://raw.githubusercontent.com"
            ),
            token=getattr(gcfg, "token", None),
        )

    @mcp.tool
    async def github_fetch(
        owner: str,
        repo: str,
        *,
        ref: Optional[str] = None,
        include_globs: Optional[List[str]] = None,
        max_files: Optional[int] = 200,
    ) -> List[Dict[str, Any]]:
        """Fetch Markdown/MDX docs from a GitHub repository.

        Parameters
        ----------
        owner: str
            GitHub organization or user.
        repo: str
            Repository name.
        ref: str | None
            Branch, tag, or commit SHA. Default: HEAD.
        include_globs: list[str] | None
            File include patterns, e.g., ["README*.md", "docs/**/*.md"].
        max_files: int | None
            Cap number of files to fetch (default 200).
        """
        state = get_state()
        conn = _make_connector(state)
        docs = await conn.fetch_markdown_docs(
            owner=owner,
            repo=repo,
            ref=ref or "HEAD",
            include_globs=include_globs,
            max_files=int(max_files or 200),
        )
        return [_serialize_parsed_document(d) for d in docs]

    @mcp.tool
    async def github_search(
        query: str,
        *,
        owner: str,
        repo: str,
        ref: Optional[str] = None,
        include_globs: Optional[List[str]] = None,
        max_files: Optional[int] = 200,
        k: Optional[int] = 5,
        same_host_only: bool = False,
    ) -> List[Dict[str, Any]]:
        """Search a GitHub repo's Markdown docs (no persistence), return snippets with links.

        same_host_only is accepted for interface parity with web tools (ignored here).
        """
        state = get_state()
        conn = _make_connector(state)
        docs = await conn.fetch_markdown_docs(
            owner=owner,
            repo=repo,
            ref=ref or "HEAD",
            include_globs=include_globs,
            max_files=int(max_files or 200),
        )
        hits = search_docs_ephemeral(docs, query, k=int(k or 5))
        out: List[Dict[str, Any]] = []
        for h in hits:
            out.append(
                {
                    "title": h.get("title", ""),
                    "snippet": h.get("snippet", ""),
                    "score": h.get("score", 0.0),
                    "url": h.get("url", ""),
                    "source": "github",
                    "owner": owner,
                    "repo": repo,
                    "ref": ref or "HEAD",
                }
            )
        return out
