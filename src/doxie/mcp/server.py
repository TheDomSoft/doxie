"""Doxie MCP server entrypoint using FastMCP.

Exposes tools built atop Doxie connectors and data sources (e.g., Confluence).
Run with:
  - poetry run doxie-mcp
  - or: python -m doxie.mcp.server (ensure PYTHONPATH includes ./src)
"""
from __future__ import annotations

from typing import Optional

from fastmcp import FastMCP

from doxie.config import Settings, load_settings
from doxie.connectors.confluence import ConfluenceConnector
from doxie.mcp.sources import ConfluenceSource
from doxie.mcp.tools import register_confluence_tools


class AppState:
    """Application state shared by MCP tools."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.confluence: Optional[ConfluenceConnector] = None
        self.confluence_source: Optional[ConfluenceSource] = None

    def init_connectors(self) -> None:
        """Initialize connectors from configuration."""
        cfg = self.settings.confluence
        if cfg.base_url and cfg.token:
            self.confluence = ConfluenceConnector(
                base_url=cfg.base_url,
                username=cfg.username,
                token=cfg.token,
                space=cfg.space,
                cloud=cfg.cloud,
                verify_ssl=cfg.verify_ssl,
            )
            self.confluence_source = ConfluenceSource(self.confluence)
        else:
            self.confluence = None
            self.confluence_source = None


# Global state and server instance
_state: Optional[AppState] = None
mcp = FastMCP("Doxie MCP Server")


# ----- Tools -----

@mcp.tool
def health() -> str:
    """Simple health check tool."""
    return "ok"




# ----- Entrypoint -----

def main() -> None:
    """Initialize state and run the MCP server."""
    global _state
    settings = load_settings()
    _state = AppState(settings)
    _state.init_connectors()
    # Register tools
    register_confluence_tools(mcp, get_state=lambda: _state)
    # Choose transport based on configuration: stdio (default), http, or sse
    transport = settings.app.transport
    if transport in ("http", "sse"):
        mcp.run(transport=transport, host=settings.app.host, port=settings.app.port)
    else:
        mcp.run()


if __name__ == "__main__":  # pragma: no cover
    main()
