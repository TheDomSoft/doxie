"""Markdown parser that converts Markdown/MDX into a ParsedDocument.

Implementation note: we convert Markdown to HTML using the `markdown` library
(extensions enabled for tables and fenced code), then reuse `HTMLParser`
logic to extract text and heading sections for consistency with other sources.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

import markdown as md  # type: ignore[import-untyped]

from .base_parser import BaseParser, ParsedDocument
from .html_parser import HTMLParser


class MarkdownParser(BaseParser):
    """Parser for `.md` and `.mdx` files or content strings."""

    def __init__(self) -> None:
        # Reuse HTML parsing logic for headings/text
        self._html = HTMLParser()
        # Reasonable default extensions; avoid heavy/unsafe ones
        self._extensions = [
            "tables",
            "fenced_code",
            "codehilite",
            "toc",
            "sane_lists",
            "smarty",
        ]

    def can_parse(self, path: Path) -> bool:
        return path.suffix.lower() in {".md", ".mdx"}

    def parse(self, path: Path) -> ParsedDocument:
        text = path.read_text(encoding="utf-8")
        return self.parse_markdown_content(text, metadata={"source_path": str(path)})

    def parse_markdown_content(
        self, markdown_text: str, *, metadata: Optional[Dict[str, Any]] = None
    ) -> ParsedDocument:
        html = md.markdown(markdown_text, extensions=self._extensions)
        return self._html.parse_html_content(html, metadata=metadata or {})
