"""HTML parser for converting rich HTML content (e.g., from Confluence)
into a `ParsedDocument` with extracted text and simple section structure.

This skeleton provides a basic interface and a minimal implementation for
string-based HTML parsing. File-based parsing is supported for `.html` files
via the base `parse()` method.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup  # type: ignore[import-untyped]

from .base_parser import BaseParser, ParsedDocument, SectionInfo


class HTMLParser(BaseParser):
    """Parser for HTML content."""

    def can_parse(self, path: Path) -> bool:
        return path.suffix.lower() in {".html", ".htm"}

    def parse(self, path: Path) -> ParsedDocument:
        """Parse an HTML file from disk."""
        html = path.read_text(encoding="utf-8")
        return self.parse_html_content(html, metadata={"source_path": str(path)})

    def parse_html_content(
        self, html: str, *, metadata: Optional[Dict[str, Any]] = None
    ) -> ParsedDocument:
        """Parse HTML string content into a `ParsedDocument`.

        This basic implementation extracts visible text and identifies headings
        (h1-h6) as sections with hierarchy levels 1-6. Offsets are not computed
        in the skeleton and remain None.
        """
        soup = BeautifulSoup(html, "html.parser")

        # Extract plain text (very naive for skeleton)
        text = soup.get_text(" ", strip=True)

        # Build sections from headings
        sections: List[SectionInfo] = []
        for level in range(1, 7):
            for tag in soup.find_all(f"h{level}"):
                title = tag.get_text(" ", strip=True)
                if title:
                    sections.append(SectionInfo(title=title, level=level))

        return ParsedDocument(text=text, sections=sections, metadata=metadata or {})
