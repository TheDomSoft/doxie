"""Minimal Jira connector for creating issues and transitioning them.

Uses Jira Cloud/Server REST API via httpx. Auth: email/username + API token for Cloud.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import httpx


class JiraConnector:
    def __init__(
        self,
        *,
        base_url: str,
        username: str,
        token: str,
        verify_ssl: bool = True,
        timeout: float = 30.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.token = token
        self.verify_ssl = verify_ssl
        self.timeout = timeout

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self.base_url,
            auth=(self.username, self.token),
            timeout=self.timeout,
            verify=self.verify_ssl,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
        )

    async def create_issue(
        self,
        *,
        project_key: str,
        summary: str,
        description: Optional[str] = None,
        issue_type: str = "Task",
    ) -> Dict[str, Any]:
        payload = {
            "fields": {
                "project": {"key": project_key},
                "summary": summary,
                "issuetype": {"name": issue_type},
            }
        }
        if description:
            payload["fields"]["description"] = description
        async with self._client() as client:
            resp = await client.post("/rest/api/3/issue", json=payload)
            resp.raise_for_status()
            data = resp.json()
            # Expected keys: id, key, self
            out = {
                "id": data.get("id"),
                "key": data.get("key"),
                "url": f"{self.base_url}/browse/{data.get('key')}" if data.get("key") else None,
            }
            return out

    async def get_transitions(self, issue: str) -> List[Dict[str, str]]:
        async with self._client() as client:
            resp = await client.get(f"/rest/api/3/issue/{issue}/transitions")
            resp.raise_for_status()
            data = resp.json()
            items = data.get("transitions") if isinstance(data, dict) else None
            results: List[Dict[str, str]] = []
            for t in items or []:
                if isinstance(t, dict):
                    tid = str(t.get("id")) if t.get("id") is not None else None
                    name = t.get("name")
                    if tid and isinstance(name, str):
                        results.append({"id": tid, "name": name})
            return results

    async def transition_issue(self, issue: str, transition: str) -> Dict[str, Any]:
        # If caller provided a transition id, use it; else try to resolve by name (case-insensitive)
        transition_id = transition
        if not transition_id.isdigit():
            transitions = await self.get_transitions(issue)
            # exact case-insensitive, then prefix match
            lc = transition.lower()
            match = next((t for t in transitions if t["name"].lower() == lc), None)
            if not match:
                match = next((t for t in transitions if t["name"].lower().startswith(lc)), None)
            if not match:
                names = ", ".join(t["name"] for t in transitions)
                raise ValueError(f"Transition not found: '{transition}'. Available: {names}")
            transition_id = match["id"]
        payload = {"transition": {"id": transition_id}}
        async with self._client() as client:
            resp = await client.post(f"/rest/api/3/issue/{issue}/transitions", json=payload)
            resp.raise_for_status()
        return {"ok": True, "issue": issue, "transition_id": transition_id}

    async def list_issues(
        self,
        *,
        jql: Optional[str] = None,
        project_key: Optional[str] = None,
        status: Optional[str] = None,
        assignee: Optional[str] = None,
        max_results: int = 50,
    ) -> List[Dict[str, Any]]:
        """List/search issues using JQL or simple filters.

        If `jql` is not provided, it will be constructed from the simple filters.
        Returns a list of dicts with id, key, summary, status, assignee, url, created, updated.
        """
        # Build JQL if not provided
        jql_parts: List[str] = []
        if not jql:
            if project_key:
                jql_parts.append(f'project = "{project_key}"')
            if status:
                jql_parts.append(f'status = "{status}"')
            if assignee:
                # assignee can be currentUser() or email/username
                if assignee.lower() == "current" or assignee == "currentUser()":
                    jql_parts.append("assignee = currentUser()")
                else:
                    jql_parts.append(f'assignee = "{assignee}"')
            if not jql_parts:
                # Fallback to something valid; without constraints Jira may return many issues
                jql_parts.append("ORDER BY updated DESC")
            jql = " AND ".join(jql_parts)
        params = {
            "jql": jql,
            "startAt": 0,
            "maxResults": int(max_results),
            "fields": ["summary", "status", "assignee", "created", "updated"],
        }
        async with self._client() as client:
            resp = await client.get("/rest/api/3/search", params=params)
            resp.raise_for_status()
            data = resp.json()
        issues = data.get("issues") if isinstance(data, dict) else None
        results: List[Dict[str, Any]] = []
        for it in issues or []:
            if not isinstance(it, dict):
                continue
            key = it.get("key")
            iid = it.get("id")
            fields = it.get("fields", {}) if isinstance(it.get("fields"), dict) else {}
            summary = fields.get("summary")
            status_name = None
            st = fields.get("status")
            if isinstance(st, dict):
                status_name = st.get("name")
            assignee_name = None
            assignee_email = None
            asg = fields.get("assignee")
            if isinstance(asg, dict):
                assignee_name = asg.get("displayName") or asg.get("name")
                assignee_email = asg.get("emailAddress")
            results.append(
                {
                    "id": iid,
                    "key": key,
                    "summary": summary,
                    "status": status_name,
                    "assignee": assignee_name,
                    "assignee_email": assignee_email,
                    "created": fields.get("created"),
                    "updated": fields.get("updated"),
                    "url": f"{self.base_url}/browse/{key}" if key else None,
                }
            )
        return results
