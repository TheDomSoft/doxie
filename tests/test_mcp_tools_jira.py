import json
from typing import Any, Dict, List, Union

import pytest
from fastmcp import Client, FastMCP

from doxie.config import Settings
from doxie.mcp.tools.jira import register_jira_tools


class DummyState:
    def __init__(self) -> None:
        self.settings = Settings()
        # Populate minimal Jira config for connector construction
        self.settings.jira.base_url = "https://example.atlassian.net"
        self.settings.jira.username = "u"
        self.settings.jira.token = "t"


def _extract_json_payload(result: Any) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
    # If already a dict/list, return as-is
    if isinstance(result, (dict, list)):
        return result
    # FastMCP Client returns CallToolResult with content list of TextContent
    content = getattr(result, "content", None)
    if isinstance(content, list) and content:
        # find first textual content
        for item in content:
            text = getattr(item, "text", None)
            if isinstance(text, str):
                try:
                    return json.loads(text)
                except json.JSONDecodeError:
                    continue
    raise AssertionError("Unable to extract JSON payload from tool result")


@pytest.mark.asyncio
async def test_jira_tools_resolve_and_search_project(monkeypatch: pytest.MonkeyPatch) -> None:
    # Arrange MCP and register tools
    mcp = FastMCP("test")
    state = DummyState()
    register_jira_tools(mcp, get_state=lambda: state)

    # Patch JiraConnector used within tools (patch at the tools module import site)
    from doxie.mcp.tools import jira as tools_jira_module

    class FakeConnector:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        async def search_projects(self, query: str, max_results: int = 50) -> List[Dict[str, Any]]:
            return [
                {"id": "1", "key": "ENG", "name": "Engineering"},
                {"id": "2", "key": "OPS", "name": "Operations"},
            ]

        async def resolve_project_key(self, name_or_key: str) -> Dict[str, Any]:
            if name_or_key.lower() == "eng":
                return {
                    "resolved": True,
                    "project": {"id": "1", "key": "ENG", "name": "Engineering"},
                    "candidates": [],
                }
            return {
                "resolved": False,
                "project": None,
                "candidates": [{"id": "2", "key": "OPS", "name": "Operations"}],
            }

    monkeypatch.setattr(tools_jira_module, "JiraConnector", FakeConnector)

    # Act via FastMCP client
    client = Client(mcp)
    async with client:
        res_search = await client.call_tool(
            "jira_search_projects", {"query": "eng", "max_results": 50}
        )
        res_resolve = await client.call_tool("jira_resolve_project_key", {"name_or_key": "eng"})

    # Extract JSON payloads
    search_payload = _extract_json_payload(res_search)
    resolve_payload = _extract_json_payload(res_resolve)

    # Assert search
    assert isinstance(search_payload, list)
    assert {p["key"] for p in search_payload} == {"ENG", "OPS"}

    # Assert resolve
    assert resolve_payload["resolved"] is True
    assert resolve_payload["project"]["key"] == "ENG"
