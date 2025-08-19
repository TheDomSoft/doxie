"""Jira tools for FastMCP.

Minimal issue management: create and transition issues.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from fastmcp import FastMCP

from doxie.connectors.jira import JiraConnector


def register_jira_tools(mcp: FastMCP, get_state: Callable[[], Any]) -> None:
    """Register Jira tools on the given FastMCP instance.

    Reads config from state.settings.jira (base_url, username, token, verify_ssl).
    """

    def _make_connector(state_obj: Any) -> JiraConnector:
        settings = getattr(state_obj, "settings", None)
        jcfg = getattr(settings, "jira", None)
        base_url = getattr(jcfg, "base_url", None)
        username = getattr(jcfg, "username", None)
        token = getattr(jcfg, "token", None)
        verify_ssl = bool(getattr(jcfg, "verify_ssl", True))
        if not base_url or not username or not token:
            raise RuntimeError(
                "Jira is not configured. Set DOXIE_JIRA__BASE_URL, DOXIE_JIRA__USERNAME, DOXIE_JIRA__TOKEN."
            )
        return JiraConnector(
            base_url=base_url,
            username=username,
            token=token,
            verify_ssl=verify_ssl,
        )

    @mcp.tool
    async def jira_create_issue(
        project_key: str,
        summary: str,
        *,
        description: Optional[str] = None,
        issue_type: str = "Task",
    ) -> Dict[str, Any]:
        """Create a Jira issue.

        Parameters
        ----------
        project_key: str
            Jira project key (e.g., "ENG").
        summary: str
            Short summary (title) of the issue.
        description: str | None
            Optional description.
        issue_type: str
            Issue type name (default: "Task").
        """
        state = get_state()
        conn = _make_connector(state)
        res = await conn.create_issue(
            project_key=project_key, summary=summary, description=description, issue_type=issue_type
        )
        return res

    @mcp.tool
    async def jira_list_transitions(issue: str) -> List[Dict[str, str]]:
        """List available transitions for an issue (id/key and name)."""
        state = get_state()
        conn = _make_connector(state)
        return await conn.get_transitions(issue)

    @mcp.tool
    async def jira_transition_issue(issue: str, transition: str) -> Dict[str, Any]:
        """Transition a Jira issue.

        Parameters
        ----------
        issue: str
            Issue key or id (e.g., "ENG-123").
        transition: str
            Transition id or name (case-insensitive). If a name is provided, it will be resolved.
        """
        state = get_state()
        conn = _make_connector(state)
        return await conn.transition_issue(issue, transition)

    @mcp.tool
    async def jira_list_issues(
        jql: Optional[str] = None,
        *,
        project_key: Optional[str] = None,
        status: Optional[str] = None,
        assignee: Optional[str] = None,
        max_results: Optional[int] = 50,
    ) -> List[Dict[str, Any]]:
        """List/search issues using JQL or simple filters.

        If `jql` is provided, other filters are ignored.

        Note: Some MCP runtimes require all parameters to be present in the
        payload even when optional. If your client enforces this, pass `null`
        for unused optional fields (e.g., `status=null`).
        """
        state = get_state()
        conn = _make_connector(state)
        return await conn.list_issues(
            jql=jql,
            project_key=project_key,
            status=status,
            assignee=assignee,
            max_results=int(max_results or 50),
        )

    @mcp.tool
    async def jira_list_project_issues(
        project_key: str, max_results: int = 50
    ) -> List[Dict[str, Any]]:
        """List recent issues for a project. Simpler wrapper to avoid optional filters.

        Parameters
        ----------
        project_key: str
            Project key, e.g. "SMS".
        max_results: int
            Maximum number of issues to return (default 50).
        """
        state = get_state()
        conn = _make_connector(state)
        return await conn.list_issues(project_key=project_key, max_results=max_results)

    @mcp.tool
    async def jira_list_issues_by_jql(jql: str, max_results: int = 50) -> List[Dict[str, Any]]:
        """List/search issues by explicit JQL. Simpler wrapper to avoid optional filters.

        Parameters
        ----------
        jql: str
            A complete JQL string.
        max_results: int
            Maximum number of issues to return (default 50).
        """
        state = get_state()
        conn = _make_connector(state)
        return await conn.list_issues(jql=jql, max_results=max_results)
