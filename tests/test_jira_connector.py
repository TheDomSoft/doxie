import asyncio
from typing import Any, Dict, List

import httpx
import pytest

from doxie.connectors.jira import JiraConnector

# ---------- Helpers ----------


def make_mock_client(responder: Any) -> httpx.AsyncClient:
    transport = httpx.MockTransport(responder)
    return httpx.AsyncClient(
        transport=transport,
        base_url="https://example.atlassian.net",
        headers={"Accept": "application/json", "Content-Type": "application/json"},
    )


def patch_client_with_responder(conn: JiraConnector, responder: Any) -> None:
    # Patch the private _client factory to return our AsyncClient with MockTransport
    def _client() -> httpx.AsyncClient:  # type: ignore[override]
        return make_mock_client(responder)

    # Assign the method on the instance
    setattr(conn, "_client", _client)


# ---------- Tests for search_projects (HTTP behavior + normalization) ----------


@pytest.mark.asyncio
async def test_search_projects_returns_normalized_list() -> None:
    payload = {
        "values": [
            {
                "id": "10010",
                "key": "ENG",
                "name": "Engineering",
                "projectTypeKey": "software",
                "self": "https://example.atlassian.net/rest/api/3/project/10010",
                "irrelevant": "ignored",
            },
            {
                "id": "10020",
                "key": "OPS",
                "name": "Operations",
                "projectTypeKey": "service_desk",
                "self": "https://example.atlassian.net/rest/api/3/project/10020",
            },
        ]
    }

    def responder(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url.path == "/rest/api/3/project/search":
            return httpx.Response(200, json=payload)
        return httpx.Response(404, json={"error": "not found"})

    conn = JiraConnector(base_url="https://example.atlassian.net", username="u", token="t")
    patch_client_with_responder(conn, responder)

    results = await conn.search_projects("eng", max_results=50)
    assert isinstance(results, list)
    assert len(results) == 2
    assert results[0]["id"] == "10010"
    assert results[0]["key"] == "ENG"
    assert results[0]["name"] == "Engineering"
    assert "projectTypeKey" in results[0]
    assert "self" in results[0]


# ---------- Tests for resolve_project_key (logic using mocked search_projects) ----------


@pytest.mark.asyncio
async def test_resolve_project_key_exact_key_case_insensitive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conn = JiraConnector(base_url="https://example.atlassian.net", username="u", token="t")

    async def fake_search_projects(query: str, max_results: int = 50) -> List[Dict[str, Any]]:
        return [
            {"id": "1", "key": "ENG", "name": "Engineering"},
            {"id": "2", "key": "OPS", "name": "Operations"},
        ]

    monkeypatch.setattr(conn, "search_projects", fake_search_projects)

    out = await conn.resolve_project_key("eng")
    assert out["resolved"] is True
    assert out["project"]["key"] == "ENG"


@pytest.mark.asyncio
async def test_resolve_project_key_exact_name_single_match(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = JiraConnector(base_url="https://example.atlassian.net", username="u", token="t")

    async def fake_search_projects(query: str, max_results: int = 50) -> List[Dict[str, Any]]:
        return [
            {"id": "1", "key": "ENG", "name": "Engineering"},
            {"id": "2", "key": "OPS", "name": "Operations"},
        ]

    monkeypatch.setattr(conn, "search_projects", fake_search_projects)

    out = await conn.resolve_project_key("Engineering")
    assert out["resolved"] is True
    assert out["project"]["name"] == "Engineering"
    assert out["project"]["key"] == "ENG"


@pytest.mark.asyncio
async def test_resolve_project_key_ambiguous_exact_name(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = JiraConnector(base_url="https://example.atlassian.net", username="u", token="t")

    async def fake_search_projects(query: str, max_results: int = 50) -> List[Dict[str, Any]]:
        return [
            {"id": "10", "key": "PLAT", "name": "Platform"},
            {"id": "11", "key": "PLTF", "name": "Platform"},
            {"id": "2", "key": "OPS", "name": "Operations"},
        ]

    monkeypatch.setattr(conn, "search_projects", fake_search_projects)

    out = await conn.resolve_project_key("Platform")
    assert out["resolved"] is False
    assert out["project"] is None
    assert isinstance(out["candidates"], list)
    assert len(out["candidates"]) == 2
    assert {c["key"] for c in out["candidates"]} == {"PLAT", "PLTF"}


@pytest.mark.asyncio
async def test_resolve_project_key_single_result_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = JiraConnector(base_url="https://example.atlassian.net", username="u", token="t")

    async def fake_search_projects(query: str, max_results: int = 50) -> List[Dict[str, Any]]:
        return [{"id": "99", "key": "RND", "name": "R&D"}]

    monkeypatch.setattr(conn, "search_projects", fake_search_projects)

    out = await conn.resolve_project_key("something-non-matching")
    assert out["resolved"] is True
    assert out["project"]["key"] == "RND"


@pytest.mark.asyncio
async def test_resolve_project_key_unique_partial_match(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = JiraConnector(base_url="https://example.atlassian.net", username="u", token="t")

    async def fake_search_projects(query: str, max_results: int = 50) -> List[Dict[str, Any]]:
        return [
            {"id": "1", "key": "ENG", "name": "Engineering"},
            {"id": "2", "key": "OPS", "name": "Operations"},
            {"id": "3", "key": "HR", "name": "People"},
        ]

    monkeypatch.setattr(conn, "search_projects", fake_search_projects)

    out = await conn.resolve_project_key("ops")
    assert out["resolved"] is True
    assert out["project"]["key"] == "OPS"


@pytest.mark.asyncio
async def test_resolve_project_key_ambiguous_partials(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = JiraConnector(base_url="https://example.atlassian.net", username="u", token="t")

    async def fake_search_projects(query: str, max_results: int = 50) -> List[Dict[str, Any]]:
        return [
            {"id": "1", "key": "OPS", "name": "Operations"},
            {"id": "2", "key": "DVOP", "name": "DevOps"},
            {"id": "3", "key": "ENG", "name": "Engineering"},
        ]

    monkeypatch.setattr(conn, "search_projects", fake_search_projects)

    out = await conn.resolve_project_key("op")
    assert out["resolved"] is False
    assert out["project"] is None
    # Should prefer partial matches as candidates
    assert {c["key"] for c in out["candidates"]} == {"OPS", "DVOP"}


@pytest.mark.asyncio
async def test_resolve_project_key_empty_input_returns_unresolved() -> None:
    conn = JiraConnector(base_url="https://example.atlassian.net", username="u", token="t")
    out = await conn.resolve_project_key("")
    assert out["resolved"] is False
    assert out["project"] is None
    assert out["candidates"] == []
