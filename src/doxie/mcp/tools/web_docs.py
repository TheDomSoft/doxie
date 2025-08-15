"""Web documentation crawling tools for FastMCP.

Fetch and parse public documentation sites starting from a given URL.
No persistence is performed; results are returned directly.
"""

from __future__ import annotations

import asyncio
import re
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
from urllib.parse import urldefrag, urljoin, urlparse

import httpx
from bs4 import BeautifulSoup  # type: ignore[import-untyped]
from fastmcp import FastMCP

from doxie.parsers.base_parser import ParsedDocument
from doxie.parsers.html_parser import HTMLParser
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


def _normalize_url(base: str, href: str) -> Optional[str]:
    if not href:
        return None
    # resolve relative and drop fragments
    abs_url = urljoin(base, href)
    abs_url, _ = urldefrag(abs_url)
    parsed = urlparse(abs_url)
    if parsed.scheme not in ("http", "https"):
        return None
    return abs_url


def _same_host(url: str, root: str) -> bool:
    p1, p2 = urlparse(url), urlparse(root)
    return (p1.hostname or "").lower() == (p2.hostname or "").lower()


def _allowed_by_patterns(
    url: str, include: Optional[List[str]], exclude: Optional[List[str]]
) -> bool:
    if include:
        try:
            if not any(re.search(p, url) for p in include):
                return False
        except re.error:
            # On invalid pattern, ignore include filtering
            pass
    if exclude:
        try:
            if any(re.search(p, url) for p in exclude):
                return False
        except re.error:
            pass
    return True


async def _fetch_page(client: httpx.AsyncClient, url: str) -> Tuple[str, Optional[str]]:
    try:
        resp = await client.get(url)
        ct = resp.headers.get("content-type", "").lower()
        if resp.status_code == 200 and "text/html" in ct:
            return url, resp.text
    except Exception:
        pass
    return url, None


async def _crawl(
    start_url: str,
    *,
    max_pages: int = 20,
    same_host_only: bool = True,
    include_patterns: Optional[List[str]] = None,
    exclude_patterns: Optional[List[str]] = None,
    concurrency: int = 5,
) -> List[Tuple[str, str]]:
    seen: Set[str] = set()
    queue: asyncio.Queue[str] = asyncio.Queue()
    results: List[Tuple[str, str]] = []

    start_url, _ = urldefrag(start_url)
    queue.put_nowait(start_url)
    seen.add(start_url)

    sem = asyncio.Semaphore(concurrency)

    headers = {"User-Agent": "doxie-webdocs-crawler/0.1"}
    async with httpx.AsyncClient(timeout=20.0, headers=headers, follow_redirects=True) as client:

        async def worker() -> None:
            nonlocal results
            while results.__len__() < max_pages:
                try:
                    current = queue.get_nowait()
                except asyncio.QueueEmpty:
                    return
                async with sem:
                    url, html = await _fetch_page(client, current)
                if html:
                    results.append((url, html))
                    # Extract links
                    soup = BeautifulSoup(html, "html.parser")
                    for a in soup.find_all("a", href=True):
                        nxt = _normalize_url(url, a.get("href", ""))
                        if not nxt or nxt in seen:
                            continue
                        if same_host_only and not _same_host(nxt, start_url):
                            continue
                        if not _allowed_by_patterns(nxt, include_patterns, exclude_patterns):
                            continue
                        seen.add(nxt)
                        if len(seen) <= max_pages * 5:  # cap frontier growth a bit
                            queue.put_nowait(nxt)
                queue.task_done()

        workers = [asyncio.create_task(worker()) for _ in range(concurrency)]
        await asyncio.gather(*workers)

    return results[:max_pages]


def register_web_docs_tools(mcp: FastMCP, get_state: Callable[[], Any]) -> None:  # noqa: ARG001
    """Register web documentation tools on the given FastMCP instance.

    These tools fetch and parse docs without persistence.
    """

    html_parser = HTMLParser()

    @mcp.tool
    async def webdocs_fetch(
        url: str,
        max_pages: Optional[int] = 20,
        same_host_only: bool = True,
        include_patterns: Optional[List[str]] = None,
        exclude_patterns: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Crawl and fetch documentation pages starting from `url`.

        Parameters
        ----------
        url: str
            Starting URL (e.g., "https://google.github.io/adk-docs/").
        max_pages: int | None
            Maximum number of pages to fetch (default 20).
        same_host_only: bool
            If True, restrict crawling to the same host as the starting URL.
        include_patterns: list[str] | None
            Optional regex patterns to include URLs. If provided, only URLs matching any pattern are crawled.
        exclude_patterns: list[str] | None
            Optional regex patterns to exclude URLs.
        """
        start = url.strip()
        if not start:
            raise ValueError("url is required")
        pages = await _crawl(
            start,
            max_pages=max_pages or 20,
            same_host_only=same_host_only,
            include_patterns=include_patterns,
            exclude_patterns=exclude_patterns,
        )
        docs: List[Dict[str, Any]] = []
        for page_url, html in pages:
            doc = html_parser.parse_html_content(html, metadata={"source_url": page_url})
            docs.append(_serialize_parsed_document(doc))
        return docs

    @mcp.tool
    async def webdocs_extract_links(url: str, same_host_only: bool = True) -> List[str]:
        """Extract and return unique links from a page, optionally restricting to same host."""
        start = url.strip()
        if not start:
            raise ValueError("url is required")
        headers = {"User-Agent": "doxie-webdocs-crawler/0.1"}
        async with httpx.AsyncClient(
            timeout=20.0, headers=headers, follow_redirects=True
        ) as client:
            _, html = await _fetch_page(client, start)
        if not html:
            return []
        soup = BeautifulSoup(html, "html.parser")
        out: List[str] = []
        seen: Set[str] = set()
        for a in soup.find_all("a", href=True):
            nxt = _normalize_url(start, a.get("href", ""))
            if not nxt:
                continue
            if same_host_only and not _same_host(nxt, start):
                continue
            if nxt not in seen:
                seen.add(nxt)
                out.append(nxt)
        return out

    @mcp.tool
    async def webdocs_search(
        url: str,
        query: str,
        *,
        max_pages: Optional[int] = 20,
        k: Optional[int] = 5,
        same_host_only: bool = True,
        include_patterns: Optional[List[str]] = None,
        exclude_patterns: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Search web documentation starting from `url` and return top-k snippets with links.

        Fast MVP flow: crawl -> parse -> in-memory index -> search.
        """
        start = (url or "").strip()
        if not start:
            raise ValueError("url is required")
        if not query or not str(query).strip():
            return []

        pages = await _crawl(
            start,
            max_pages=max_pages or 20,
            same_host_only=same_host_only,
            include_patterns=include_patterns,
            exclude_patterns=exclude_patterns,
        )
        docs: List[ParsedDocument] = []
        for page_url, html in pages:
            doc = html_parser.parse_html_content(
                html, metadata={"source_url": page_url, "source": "web"}
            )
            docs.append(doc)

        hits = search_docs_ephemeral(docs, query, k=int(k or 5))
        # Ensure clean JSON shape
        out: List[Dict[str, Any]] = []
        for h in hits:
            out.append(
                {
                    "title": h.get("title", ""),
                    "snippet": h.get("snippet", ""),
                    "score": h.get("score", 0.0),
                    "url": h.get("url", ""),
                    "source": "web",
                }
            )
        return out

    @mcp.tool
    async def webdocs_sitemap(
        url: str,
        *,
        max_pages: Optional[int] = 50,
        same_host_only: bool = True,
        include_patterns: Optional[List[str]] = None,
        exclude_patterns: Optional[List[str]] = None,
    ) -> List[Dict[str, str]]:
        """Return discovered pages with simple titles for quick navigation."""
        start = (url or "").strip()
        if not start:
            raise ValueError("url is required")
        pages = await _crawl(
            start,
            max_pages=max_pages or 50,
            same_host_only=same_host_only,
            include_patterns=include_patterns,
            exclude_patterns=exclude_patterns,
        )
        out: List[Dict[str, str]] = []
        for page_url, html in pages:
            try:
                soup = BeautifulSoup(html, "html.parser")
                # Prefer <title>, fallback to first h1/h2/h3
                title_tag = soup.find("title")
                title = ""
                if title_tag and title_tag.text:
                    title = title_tag.get_text(" ", strip=True)
                if not title:
                    for lvl in (1, 2, 3):
                        h = soup.find(f"h{lvl}")
                        if h and h.text:
                            title = h.get_text(" ", strip=True)
                            break
                out.append({"url": page_url, "title": title or page_url})
            except Exception:
                out.append({"url": page_url, "title": page_url})
        return out
