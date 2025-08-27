import json
from typing import Any, Dict, List, Optional, Union

import pytest
from fastmcp import Client, FastMCP

from doxie.config import Settings
from doxie.mcp.tools.github import register_github_tools
from doxie.parsers.base_parser import ParsedDocument


class DummyState:
    def __init__(self) -> None:
        self.settings = Settings()
        # GitHub settings
        self.settings.github.token = "dummy"


def _extract_json_payload(result: Any) -> Union[Dict[str, Any], List[Dict[str, Any]], str]:
    if isinstance(result, (dict, list, str)):
        return result
    content = getattr(result, "content", None)
    if isinstance(content, list) and content:
        for item in content:
            text = getattr(item, "text", None)
            if isinstance(text, str):
                try:
                    return json.loads(text)
                except json.JSONDecodeError:
                    return text
    raise AssertionError("Unable to extract JSON payload from tool result")


@pytest.mark.asyncio
async def test_github_fetch_and_search(monkeypatch: pytest.MonkeyPatch) -> None:
    mcp = FastMCP("test")
    state = DummyState()

    # Patch GitHubConnector.fetch_markdown_docs to return minimal docs
    from doxie.connectors.github import GitHubConnector
    from doxie.mcp.tools import github as tools_github

    async def fake_fetch_markdown_docs(
        self,
        *,
        owner: str,
        repo: str,
        ref: str = "HEAD",
        include_globs: Optional[List[str]] = None,
        max_files: int = 200,
    ) -> List[ParsedDocument]:
        assert owner == "octo" and repo == "hello"
        return [
            ParsedDocument(
                text="Hello World",
                sections=[],
                metadata={"url": "https://github.com/octo/hello/README.md", "source": "github"},
            )
        ]

    monkeypatch.setattr(GitHubConnector, "fetch_markdown_docs", fake_fetch_markdown_docs)

    # Patch search_docs_ephemeral used by the tool
    def fake_search_docs_ephemeral(docs, query: str, k: int = 5):
        assert query == "hello"
        return [
            {
                "title": "README",
                "snippet": "Hello",
                "score": 1.0,
                "url": docs[0].metadata.get("url"),
            }
        ]

    monkeypatch.setattr(tools_github, "search_docs_ephemeral", fake_search_docs_ephemeral)

    register_github_tools(mcp, get_state=lambda: state)

    client = Client(mcp)
    async with client:
        res_fetch = await client.call_tool(
            "github_fetch",
            {
                "owner": "octo",
                "repo": "hello",
                "ref": None,
                "include_globs": ["README*.md"],
                "max_files": 10,
            },
        )
        res_search = await client.call_tool(
            "github_search",
            {
                "owner": "octo",
                "repo": "hello",
                "ref": None,
                "include_globs": None,
                "max_files": None,
                "query": "hello",
                "k": 5,
                "same_host_only": False,
            },
        )

    payload_fetch = _extract_json_payload(res_fetch)
    payload_search = _extract_json_payload(res_search)

    assert isinstance(payload_fetch, list) and payload_fetch
    assert payload_fetch[0]["metadata"]["source"] == "github"
    assert isinstance(payload_search, list) and payload_search
    assert payload_search[0]["title"] == "README"
