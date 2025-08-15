"""Confluence tools for FastMCP.

These tools use the sources abstraction so the agent is decoupled from
connector details.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

import markdown as md

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

    # Helpers for allowed space enforcement
    def _parse_spaces_csv(val: Any) -> List[str]:
        if isinstance(val, str):
            return [p.strip() for p in val.split(",") if p and p.strip()]
        if isinstance(val, list):
            return [str(p).strip() for p in val if str(p).strip()]
        return []

    def _get_allowed_spaces(state_obj: Any) -> List[str]:
        cfg = getattr(state_obj, "settings", None)
        cfg = getattr(cfg, "confluence", None)
        cfg_spaces_val = getattr(cfg, "spaces", None)
        allowed = _parse_spaces_csv(cfg_spaces_val)
        if not allowed:
            raise RuntimeError(
                "No allowed spaces configured. Set DOXIE_CONFLUENCE__SPACES (comma-separated)."
            )
        return allowed

    def _ensure_space_allowed(space_key: str, allowed: List[str]) -> None:
        if space_key not in allowed:
            raise PermissionError(
                f"Space '{space_key}' is not allowed. Allowed spaces: {', '.join(allowed)}"
            )

    @mcp.tool
    async def confluence_fetch(limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Fetch content from Confluence and return serialized parsed documents."""
        state = get_state()
        if state is None or getattr(state, "confluence_source", None) is None:
            raise RuntimeError(
                "Confluence source is not configured. Provide confluence settings in config/.env."
            )
        # Enforce default space is allowed
        allowed = _get_allowed_spaces(state)
        cfg = getattr(state, "settings", None)
        cfg = getattr(cfg, "confluence", None)
        default_space = getattr(cfg, "space", None)
        if default_space:
            _ensure_space_allowed(default_space, allowed)
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
        allowed = _get_allowed_spaces(state)
        _ensure_space_allowed(space, allowed)
        docs = await state.confluence_source.fetch_by_space(space=space, limit=limit)
        return [_serialize_parsed_document(d) for d in docs]

    @mcp.tool
    async def confluence_list_spaces(limit: Optional[int] = None) -> List[Dict[str, str]]:
        """List allowed Confluence spaces (key, name) per DOXIE_CONFLUENCE__SPACES."""
        state = get_state()
        if state is None or getattr(state, "confluence_source", None) is None:
            raise RuntimeError(
                "Confluence source is not configured. Provide confluence settings in config/.env."
            )
        allowed = _get_allowed_spaces(state)
        spaces = await state.confluence_source.list_spaces(limit=limit)
        # Filter to allowed and ensure consistent shape
        filtered = [s for s in (spaces or []) if isinstance(s, dict) and s.get("key") in allowed]
        return [{"key": s.get("key", ""), "name": s.get("name", "")} for s in filtered]

    @mcp.tool
    async def confluence_fetch_spaces(
        spaces: Optional[List[str]] = None,
        limit_per_space: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch Confluence pages across multiple spaces (no persistence).

        If `spaces` is not provided, uses configured spaces from settings
        (env var `DOXIE_CONFLUENCE__SPACES` as a comma-separated list, e.g. "DOCS, ENG").
        """
        state = get_state()
        if state is None or getattr(state, "confluence_source", None) is None:
            raise RuntimeError(
                "Confluence source is not configured. Provide confluence settings in config/.env."
            )
        allowed = _get_allowed_spaces(state)
        chosen_spaces: Optional[List[str]] = spaces
        if not chosen_spaces:
            # try from config (comma-separated string)
            cfg_confluence = getattr(state, "settings", None)
            cfg_confluence = getattr(cfg_confluence, "confluence", None)
            cfg_spaces_val = getattr(cfg_confluence, "spaces", None)
            parsed: List[str] = []
            if isinstance(cfg_spaces_val, str):
                parsed = [p.strip() for p in cfg_spaces_val.split(",") if p and p.strip()]
            elif isinstance(cfg_spaces_val, list):
                # Backwards compatibility if settings already holds a list
                parsed = [str(p).strip() for p in cfg_spaces_val if str(p).strip()]
            chosen_spaces = parsed
        if not chosen_spaces:
            raise ValueError(
                "No spaces provided. Pass `spaces` param or set DOXIE_CONFLUENCE__SPACES as a comma-separated list."
            )
        # Enforce all requested spaces are allowed
        disallowed = [s for s in chosen_spaces if s not in allowed]
        if disallowed:
            raise PermissionError(
                f"Spaces not allowed: {', '.join(disallowed)}. Allowed: {', '.join(allowed)}"
            )
        docs = await state.confluence_source.fetch_for_spaces(chosen_spaces, limit_per_space=limit_per_space)
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

    @mcp.tool
    async def confluence_create_page(
        title: str,
        content: str,
        space: Optional[str] = None,
        content_format: str = "markdown",
        parent_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a Confluence page in a space.

        Parameters
        ----------
        title: str
            Page title.
        content: str
            Page body text.
        space: str | None
            Confluence space key. If not provided, falls back to configured default space
            (DOXIE_CONFLUENCE__SPACE) or the first from DOXIE_CONFLUENCE__SPACES.
        content_format: str
            One of: "markdown" (default), "html", or "storage".
            markdown -> converted to HTML via Python-Markdown and sent as storage.
            html -> sent as storage.
            storage -> sent as-is.
        parent_id: str | None
            Optional parent page ID to create the page under.
        """
        state = get_state()
        if state is None or getattr(state, "confluence_source", None) is None:
            raise RuntimeError(
                "Confluence source is not configured. Provide confluence settings in config/.env."
            )

        # Resolve space if not provided
        # Normalize empty strings
        space = space or None
        parent_id = parent_id or None

        chosen_space = space
        if not chosen_space:
            cfg = getattr(state, "settings", None)
            cfg = getattr(cfg, "confluence", None)
            chosen_space = getattr(cfg, "space", None)
            if not chosen_space:
                cfg_spaces_val = getattr(cfg, "spaces", None)
                if isinstance(cfg_spaces_val, str):
                    parts = [p.strip() for p in cfg_spaces_val.split(",") if p and p.strip()]
                    chosen_space = parts[0] if parts else None
        if not chosen_space:
            raise ValueError(
                "No space specified. Provide `space` or set DOXIE_CONFLUENCE__SPACE/DOXIE_CONFLUENCE__SPACES."
            )
        # Enforce allowed space for writes
        allowed = _get_allowed_spaces(state)
        _ensure_space_allowed(chosen_space, allowed)

        fmt = (content_format or "markdown").lower()
        representation = "storage"
        body = content or ""
        if fmt == "markdown":
            body = md.markdown(content or "")
        elif fmt == "html":
            body = content or ""
        elif fmt == "storage":
            body = content or ""
        else:
            raise ValueError("Unsupported content_format. Use 'markdown', 'html', or 'storage'.")

        page = await state.confluence_source.create_page(
            space=chosen_space,
            title=title,
            content=body,
            parent_id=parent_id,
            representation=representation,
        )
        # Return useful subset if possible, otherwise raw response
        if isinstance(page, dict):
            out: Dict[str, Any] = {
                "id": page.get("id"),
                "type": page.get("type"),
                "status": page.get("status"),
                "title": page.get("title") or title,
                "space": chosen_space,
            }
            links = page.get("_links", {}) if isinstance(page.get("_links"), dict) else {}
            base = links.get("base", "")
            webui = links.get("webui", "")
            if base or webui:
                out["url"] = f"{base}{webui}"
            return out
        return {"ok": True}

    @mcp.tool
    async def confluence_update_page(
        page_id: Optional[str] = None,
        *,
        space: Optional[str] = None,
        match_title: Optional[str] = None,
        new_title: Optional[str] = None,
        content: Optional[str] = None,
        content_format: str = "markdown",
        parent_id: Optional[str] = None,
        minor_edit: bool = True,
        version_comment: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Update an existing Confluence page.

        You can provide `page_id` directly, or omit it and provide `space` and `match_title`
        to resolve the page by title within the space.

        Parameters
        ----------
        page_id: str | None
            Confluence page ID to update.
        space: str | None
            Space key to search within when resolving by title. If not provided, uses
            DOXIE_CONFLUENCE__SPACE or the first from DOXIE_CONFLUENCE__SPACES.
        match_title: str | None
            Existing page title used to resolve page ID if `page_id` is not given.
        new_title: str | None
            New title for the page. If omitted, current title is kept.
        content: str | None
            New page body. If omitted, current body is kept.
        content_format: str
            One of: "markdown" (default), "html", or "storage". Only used if `content` is provided.
        parent_id: str | None
            Optionally re-parent the page.
        minor_edit: bool
            Mark edit as minor (default True).
        version_comment: str | None
            Optional version comment.
        """
        state = get_state()
        if state is None or getattr(state, "confluence_source", None) is None:
            raise RuntimeError(
                "Confluence source is not configured. Provide confluence settings in config/.env."
            )

        # Resolve page_id if not provided
        # Normalize empty strings from clients to None
        page_id = page_id or None
        space = space or None
        match_title = match_title or None
        new_title = new_title or None
        content = content if (content is not None and content != "") else None
        parent_id = parent_id or None
        version_comment = version_comment or None

        allowed = _get_allowed_spaces(state)
        resolved_page_id = page_id
        if not resolved_page_id:
            # Resolve space if not provided
            chosen_space = space
            if not chosen_space:
                cfg = getattr(state, "settings", None)
                cfg = getattr(cfg, "confluence", None)
                chosen_space = getattr(cfg, "space", None)
                if not chosen_space:
                    cfg_spaces_val = getattr(cfg, "spaces", None)
                    if isinstance(cfg_spaces_val, str):
                        parts = [p.strip() for p in cfg_spaces_val.split(",") if p and p.strip()]
                        chosen_space = parts[0] if parts else None
            if not chosen_space or not match_title:
                raise ValueError(
                    "Must provide either `page_id` or both `space` and `match_title` to locate the page."
                )
            # Enforce allowed space when resolving by title
            _ensure_space_allowed(chosen_space, allowed)
            resolved_page_id = await state.confluence_source.get_page_id(chosen_space, match_title)
            if not resolved_page_id:
                raise ValueError(f"Page not found in space '{chosen_space}' with title '{match_title}'.")
        else:
            # We have page_id; fetch page to determine its space and enforce
            try:
                page_info = await state.confluence_source.get_page_by_id(resolved_page_id, expand="space")
                page_space = None
                if isinstance(page_info, dict):
                    sp = page_info.get("space")
                    if isinstance(sp, dict):
                        page_space = sp.get("key")
                if page_space:
                    _ensure_space_allowed(page_space, allowed)
            except Exception:
                # If we can't fetch, be conservative and block
                raise PermissionError("Unable to verify page space for update; refusing edit.")

        # Prepare content if provided
        representation = "storage"
        body: Optional[str] = None
        if content is not None:
            fmt = (content_format or "markdown").lower()
            if fmt == "markdown":
                body = md.markdown(content or "")
            elif fmt in ("html", "storage"):
                body = content or ""
            else:
                raise ValueError("Unsupported content_format. Use 'markdown', 'html', or 'storage'.")

        updated = await state.confluence_source.update_page(
            page_id=resolved_page_id,
            title=new_title,
            content=body,
            parent_id=parent_id,
            representation=representation,
            minor_edit=minor_edit,
            version_comment=version_comment,
        )

        if isinstance(updated, dict):
            out: Dict[str, Any] = {
                "id": updated.get("id") or resolved_page_id,
                "type": updated.get("type"),
                "status": updated.get("status"),
                "title": updated.get("title") or new_title,
            }
            links = updated.get("_links", {}) if isinstance(updated.get("_links"), dict) else {}
            base = links.get("base", "")
            webui = links.get("webui", "")
            if base or webui:
                out["url"] = f"{base}{webui}"
            return out
        return {"ok": True, "id": resolved_page_id}
