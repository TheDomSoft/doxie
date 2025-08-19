"""Tool registration modules for the Doxie MCP server."""

from .confluence import register_confluence_tools
from .github import register_github_tools
from .jira import register_jira_tools
from .web_docs import register_web_docs_tools

__all__ = [
    "register_confluence_tools",
    "register_web_docs_tools",
    "register_github_tools",
    "register_jira_tools",
]
