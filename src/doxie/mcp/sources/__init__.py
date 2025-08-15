"""Sources abstraction for MCP tools.

A Source wraps one or more connectors and exposes a stable interface
for tools to interact with content without depending on connector details.
"""

from .base import ContentSource
from .confluence_source import ConfluenceSource

__all__ = ["ContentSource", "ConfluenceSource"]
