import json
from typing import Any, Dict, List, Optional, Union

import pytest
from fastmcp import Client, FastMCP

from doxie.config import Settings
from doxie.mcp.tools.confluence import register_confluence_tools
from doxie.parsers.base_parser import ParsedDocument


class DummyState:
    def __init__(self) -> None:
        self.settings = Settings()
        # Minimal Confluence config
        self.settings.confluence.base_url = "https://conf.example.com"
        self.settings.confluence.space = "ENG"
        self.settings.confluence.spaces = "ENG, DOCS"
        # Will be assigned per test
        self.confluence_source = None


def _extract_json_payload(result: Any) -> Union[Dict[str, Any], List[Dict[str, Any]], str]:
    # If already a dict/list, return as-is
    if isinstance(result, (dict, list, str)):
        return result
    # FastMCP Client returns CallToolResult with content list of TextContent
    content = getattr(result, "content", None)
    if isinstance(content, list) and content:
        for item in content:
            text = getattr(item, "text", None)
            if isinstance(text, str):
                try:
                    return json.loads(text)
                except json.JSONDecodeError:
                    # Fallback to raw string (e.g., plain "ok")
                    return text
    raise AssertionError("Unable to extract JSON payload from tool result")


def make_doc(text: str, metadata: Optional[Dict[str, Any]] = None) -> ParsedDocument:
    return ParsedDocument(text=text, sections=[], metadata=metadata or {})


@pytest.mark.asyncio
async def test_confluence_fetch_success_and_default_space_allowed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mcp = FastMCP("test")
    state = DummyState()

    class FakeSource:
        async def fetch(self, limit: Optional[int] = None):
            return [make_doc("Hello", {"source": "confluence", "space": "ENG"})]

    state.confluence_source = FakeSource()
    register_confluence_tools(mcp, get_state=lambda: state)

    client = Client(mcp)
    async with client:
        res = await client.call_tool("confluence_fetch", {"limit": 5})
    payload = _extract_json_payload(res)
    assert isinstance(payload, list)
    assert payload[0]["metadata"]["space"] == "ENG"


@pytest.mark.asyncio
async def test_confluence_fetch_disallowed_default_space(monkeypatch: pytest.MonkeyPatch) -> None:
    mcp = FastMCP("test")
    state = DummyState()
    # Configure allowed spaces to exclude default space
    state.settings.confluence.spaces = "DOCS"

    class FakeSource:
        async def fetch(self, limit: Optional[int] = None):
            return [make_doc("Hello", {"source": "confluence", "space": "ENG"})]

    state.confluence_source = FakeSource()
    register_confluence_tools(mcp, get_state=lambda: state)

    client = Client(mcp)
    async with client:
        with pytest.raises(Exception):
            # PermissionError specifically, but keeping generic to avoid coupling
            await client.call_tool("confluence_fetch", {"limit": 5})


@pytest.mark.asyncio
async def test_confluence_search_allowed_spaces_and_builds_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mcp = FastMCP("test")
    state = DummyState()

    class FakeSource:
        async def fetch_for_spaces(self, spaces: List[str], limit_per_space: Optional[int] = None):
            # Not used because we patch search function, but return docs anyway
            return [
                make_doc("Docs for ENG", {"source": "confluence", "space": "ENG", "page_id": "123"})
            ]

    state.confluence_source = FakeSource()

    # Patch search_docs_ephemeral to produce a hit without URL, forcing tool to construct it
    from doxie.mcp.tools import confluence as tools_conf

    def fake_search_docs_ephemeral(docs, query, k: int = 5):
        return [
            {
                "title": "Welcome",
                "snippet": "ENG home",
                "score": 1.0,
                "url": "",
                "space": "ENG",
                "page_id": "123",
            }
        ]

    monkeypatch.setattr(tools_conf, "search_docs_ephemeral", fake_search_docs_ephemeral)

    register_confluence_tools(mcp, get_state=lambda: state)

    client = Client(mcp)
    async with client:
        res = await client.call_tool(
            "confluence_search",
            {
                "query": "ENG",
                "spaces": ["ENG"],
                "space": None,
                "limit": 10,
                "k": 5,
                "same_host_only": False,
            },
        )
    payload = _extract_json_payload(res)
    assert isinstance(payload, list) and payload
    assert payload[0]["space"] == "ENG"
    # URL should be constructed from base_url, space, and page_id
    assert payload[0]["url"].endswith("/wiki/spaces/ENG/pages/123")


@pytest.mark.asyncio
async def test_confluence_search_disallowed_space(monkeypatch: pytest.MonkeyPatch) -> None:
    mcp = FastMCP("test")
    state = DummyState()

    class FakeSource:
        async def fetch_for_spaces(self, spaces: List[str], limit_per_space: Optional[int] = None):
            return []

    state.confluence_source = FakeSource()

    register_confluence_tools(mcp, get_state=lambda: state)

    client = Client(mcp)
    async with client:
        with pytest.raises(Exception):
            await client.call_tool(
                "confluence_search",
                {
                    "query": "X",
                    "spaces": ["OPS"],
                    "space": None,
                    "limit": 10,
                    "k": 5,
                    "same_host_only": False,
                },
            )


@pytest.mark.asyncio
async def test_confluence_fetch_space_and_list_spaces(monkeypatch: pytest.MonkeyPatch) -> None:
    mcp = FastMCP("test")
    state = DummyState()

    class FakeSource:
        async def fetch_by_space(self, space: str, limit: Optional[int] = None):
            assert space == "ENG"
            return [make_doc("Hello ENG", {"source": "confluence", "space": "ENG"})]

        async def list_spaces(self, limit: Optional[int] = None):
            return [
                {"key": "ENG", "name": "Engineering"},
                {"key": "OPS", "name": "Operations"},
            ]

    state.confluence_source = FakeSource()
    register_confluence_tools(mcp, get_state=lambda: state)

    client = Client(mcp)
    async with client:
        res_fetch_space = await client.call_tool(
            "confluence_fetch_space", {"space": "ENG", "limit": None}
        )
        res_list = await client.call_tool("confluence_list_spaces", {"limit": None})

    payload_fetch_space = _extract_json_payload(res_fetch_space)
    payload_list = _extract_json_payload(res_list)

    assert payload_fetch_space and payload_fetch_space[0]["metadata"]["space"] == "ENG"
    assert payload_list == [{"key": "ENG", "name": "Engineering"}]


@pytest.mark.asyncio
async def test_confluence_get_page_parses_and_enforces_space(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mcp = FastMCP("test")
    state = DummyState()

    class FakeSource:
        async def get_page_by_id(self, page_id: str, expand: str = "body.storage,space"):
            assert page_id == "123"
            return {
                "title": "Welcome",
                "space": {"key": "ENG"},
                "body": {"storage": {"value": "<h1>Hello</h1><p>World</p>"}},
            }

    state.confluence_source = FakeSource()
    register_confluence_tools(mcp, get_state=lambda: state)

    client = Client(mcp)
    async with client:
        res = await client.call_tool(
            "confluence_get_page", {"page_id": "123", "expand": "body.storage,space"}
        )
    payload = _extract_json_payload(res)
    assert payload["metadata"]["space"] == "ENG"
    assert payload["metadata"]["url"].endswith("/wiki/spaces/ENG/pages/123")
    assert "Hello" in payload["text"]


@pytest.mark.asyncio
async def test_confluence_fetch_spaces_and_sync(monkeypatch: pytest.MonkeyPatch) -> None:
    mcp = FastMCP("test")
    state = DummyState()
    # Ensure config.spaces is a CSV string to test parsing path
    state.settings.confluence.spaces = "ENG, DOCS"

    class FakeSource:
        async def fetch_for_spaces(self, spaces: List[str], limit_per_space: Optional[int] = None):
            assert spaces == ["ENG", "DOCS"]
            return [
                make_doc("ENG doc", {"source": "confluence", "space": "ENG"}),
                make_doc("DOCS doc", {"source": "confluence", "space": "DOCS"}),
            ]

        async def sync(self):
            return None

    state.confluence_source = FakeSource()
    register_confluence_tools(mcp, get_state=lambda: state)

    client = Client(mcp)
    async with client:
        res_fetch_spaces = await client.call_tool(
            "confluence_fetch_spaces", {"spaces": None, "limit_per_space": None}
        )
        res_sync = await client.call_tool("confluence_sync", {})

    payload_fetch_spaces = _extract_json_payload(res_fetch_spaces)
    payload_sync = _extract_json_payload(res_sync)

    assert {d["metadata"]["space"] for d in payload_fetch_spaces} == {"ENG", "DOCS"}
    assert payload_sync == "ok"


@pytest.mark.asyncio
async def test_confluence_create_page_and_invalid_format(monkeypatch: pytest.MonkeyPatch) -> None:
    mcp = FastMCP("test")
    state = DummyState()

    class FakeSource:
        async def create_page(
            self,
            *,
            space: str,
            title: str,
            content: str,
            parent_id: Optional[str],
            representation: str,
        ):
            assert space == "ENG"
            assert title == "New Page"
            # representation is always storage in the tool
            assert representation == "storage"
            # content should be HTML (converted from markdown)
            assert "<p>Body</p>" in content
            return {
                "id": "999",
                "type": "page",
                "status": "current",
                "title": title,
                "_links": {"base": "https://conf.example.com", "webui": "/wiki/pages/999"},
            }

    state.confluence_source = FakeSource()
    register_confluence_tools(mcp, get_state=lambda: state)

    client = Client(mcp)
    async with client:
        res = await client.call_tool(
            "confluence_create_page",
            {
                "title": "New Page",
                "content": "Body",
                "space": "ENG",
                "content_format": "markdown",
                "parent_id": None,
            },
        )
        payload = _extract_json_payload(res)
        assert payload["id"] == "999"
        assert payload["url"].endswith("/wiki/pages/999")

        with pytest.raises(Exception):
            await client.call_tool(
                "confluence_create_page",
                {
                    "title": "Bad",
                    "content": "X",
                    "space": "ENG",
                    "content_format": "badfmt",
                    "parent_id": None,
                },
            )


@pytest.mark.asyncio
async def test_confluence_update_page_resolve_and_by_id(monkeypatch: pytest.MonkeyPatch) -> None:
    mcp = FastMCP("test")
    state = DummyState()

    class FakeSource:
        async def get_page_id(self, space: str, title: str):
            assert space == "ENG" and title == "Welcome"
            return "123"

        async def update_page(
            self,
            *,
            page_id: str,
            title: Optional[str],
            content: Optional[str],
            parent_id: Optional[str],
            representation: str,
            minor_edit: bool,
            version_comment: Optional[str],
        ):
            assert page_id in ("123", "456")
            return {
                "id": page_id,
                "type": "page",
                "status": "current",
                "title": title or "Welcome",
                "_links": {"base": "https://conf.example.com", "webui": f"/wiki/pages/{page_id}"},
            }

        async def get_page_by_id(self, page_id: str, expand: str = "space"):
            # For by-id check, ensure allowed space ENG
            return {"space": {"key": "ENG"}}

    state.confluence_source = FakeSource()
    register_confluence_tools(mcp, get_state=lambda: state)

    client = Client(mcp)
    async with client:
        # Resolve by title
        res1 = await client.call_tool(
            "confluence_update_page",
            {
                "page_id": None,
                "space": "ENG",
                "match_title": "Welcome",
                "new_title": "Welcome Updated",
                "content": "Body",
                "content_format": "markdown",
                "parent_id": None,
                "minor_edit": True,
                "version_comment": None,
            },
        )
        p1 = _extract_json_payload(res1)
        assert p1["id"] == "123" and p1["title"] == "Welcome Updated"
        assert p1["url"].endswith("/wiki/pages/123")

        # By page_id path
        res2 = await client.call_tool(
            "confluence_update_page",
            {
                "page_id": "456",
                "space": None,
                "match_title": None,
                "new_title": "Hello",
                "content": "<b>X</b>",
                "content_format": "html",
                "parent_id": None,
                "minor_edit": True,
                "version_comment": None,
            },
        )
        p2 = _extract_json_payload(res2)
        assert p2["id"] == "456" and p2["title"] == "Hello"


@pytest.mark.asyncio
async def test_confluence_update_page_invalid_format_and_unverifiable_space(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mcp = FastMCP("test")
    state = DummyState()

    class FakeSource:
        async def get_page_by_id(self, page_id: str, expand: str = "space"):
            # Simulate failure to fetch page info
            raise RuntimeError("boom")

        async def update_page(self, **kwargs: Any):
            return {}

    state.confluence_source = FakeSource()
    register_confluence_tools(mcp, get_state=lambda: state)

    client = Client(mcp)
    async with client:
        # Invalid format
        with pytest.raises(Exception):
            await client.call_tool(
                "confluence_update_page",
                {
                    "page_id": None,
                    "space": "ENG",
                    "match_title": "Welcome",
                    "new_title": None,
                    "content": "x",
                    "content_format": "bad",
                    "parent_id": None,
                    "minor_edit": True,
                    "version_comment": None,
                },
            )
        # Unverifiable space when page_id provided should error
        with pytest.raises(Exception):
            await client.call_tool(
                "confluence_update_page",
                {
                    "page_id": "123",
                    "space": None,
                    "match_title": None,
                    "new_title": None,
                    "content": None,
                    "content_format": "markdown",
                    "parent_id": None,
                    "minor_edit": True,
                    "version_comment": None,
                },
            )
