"""GitHub connector for fetching Markdown docs from repositories.

Minimal implementation using GitHub REST API v3 and raw content URLs.
"""

from __future__ import annotations

import asyncio
import base64
import fnmatch
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional

import httpx

from doxie.parsers.base_parser import ParsedDocument
from doxie.parsers.markdown_parser import MarkdownParser


@dataclass
class GitHubRepo:
    owner: str
    repo: str
    ref: str = "HEAD"


class GitHubConnector:
    def __init__(
        self,
        *,
        api_base_url: str = "https://api.github.com",
        web_base_url: str = "https://github.com",
        raw_base_url: str = "https://raw.githubusercontent.com",
        token: Optional[str] = None,
        timeout: float = 30.0,
    ) -> None:
        self.api_base_url = api_base_url.rstrip("/")
        self.web_base_url = web_base_url.rstrip("/")
        self.raw_base_url = raw_base_url.rstrip("/")
        self.token = token
        self.timeout = timeout
        self._md = MarkdownParser()

    def _headers(self) -> Dict[str, str]:
        h = {"Accept": "application/vnd.github+json"}
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        return h

    async def _get(self, url: str, *, params: Optional[Dict[str, Any]] = None) -> httpx.Response:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(url, headers=self._headers(), params=params)
            resp.raise_for_status()
            return resp

    async def list_tree(self, repo: GitHubRepo) -> List[Dict[str, Any]]:
        """List tree (all files) at a ref using git/trees with recursive=1."""
        url = f"{self.api_base_url}/repos/{repo.owner}/{repo.repo}/git/trees/{repo.ref}"
        resp = await self._get(url, params={"recursive": 1})
        data = resp.json()
        return data.get("tree", []) if isinstance(data, dict) else []

    def _match_any(self, path: str, patterns: Iterable[str]) -> bool:
        path = path.lstrip("/")
        for pat in patterns:
            if fnmatch.fnmatch(path, pat):
                return True
        return False

    def _blob_url(self, repo: GitHubRepo, path: str) -> str:
        return f"{self.web_base_url}/{repo.owner}/{repo.repo}/blob/{repo.ref}/{path.lstrip('/')}"

    def _raw_url(self, repo: GitHubRepo, path: str) -> str:
        return f"{self.raw_base_url}/{repo.owner}/{repo.repo}/{repo.ref}/{path.lstrip('/')}"

    async def _fetch_raw_text(self, url: str) -> str:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(url, headers=self._headers())
            resp.raise_for_status()
            # raw endpoint returns text directly
            return resp.text

    async def fetch_markdown_docs(
        self,
        *,
        owner: str,
        repo: str,
        ref: str = "HEAD",
        include_globs: Optional[List[str]] = None,
        max_files: int = 200,
    ) -> List[ParsedDocument]:
        """Fetch and parse Markdown/MDX docs from a repository.

        include_globs examples: ["README*.md", "docs/**/*.md", "**/*.mdx"].
        If not provided, uses sensible defaults for docs discovery.
        """
        patterns = include_globs or [
            "README.md",
            "README.*",
            "docs/**/*.md",
            "docs/**/*.mdx",
            "**/*.md",
            "**/*.mdx",
        ]
        repo_ref = GitHubRepo(owner=owner, repo=repo, ref=ref or "HEAD")
        tree = await self.list_tree(repo_ref)
        # filter blobs (files) only
        file_paths = [item.get("path") for item in tree if item.get("type") == "blob"]
        file_paths = [p for p in file_paths if isinstance(p, str)]
        # include only matching patterns
        selected = [p for p in file_paths if self._match_any(p, patterns)]
        # prefer unique order, cap to max_files
        selected = selected[: max(0, int(max_files))]

        async def fetch_one(path: str) -> Optional[ParsedDocument]:
            try:
                raw_url = self._raw_url(repo_ref, path)
                text = await self._fetch_raw_text(raw_url)
                doc = self._md.parse_markdown_content(
                    text,
                    metadata={
                        "source": "github",
                        "owner": owner,
                        "repo": repo,
                        "ref": repo_ref.ref,
                        "path": path,
                        "url": self._blob_url(repo_ref, path),
                    },
                )
                return doc
            except Exception:
                return None

        results = await asyncio.gather(*(fetch_one(p) for p in selected))
        return [r for r in results if r is not None]

    # BaseConnector compatibility (not used directly by tools)
    async def fetch_content(self) -> List[ParsedDocument]:  # type: ignore[override]
        return []

    async def sync(self) -> None:  # type: ignore[override]
        return None
