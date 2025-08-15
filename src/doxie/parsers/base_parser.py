"""Abstract base classes and data structures for document parsers.

Parsers are responsible for extracting raw text, structural information, and
metadata from supported document types (PDF, DOCX, Markdown, etc.).

Concrete implementations should subclass `BaseParser` and implement
`can_parse()` and `parse()`.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


@dataclass(slots=True)
class SectionInfo:
    """Represents a logical section within a document (e.g., heading/section).

    Attributes
    ----------
    title: str
        The human-readable section title.
    level: int
        A hierarchical level where 1 is top-level (e.g., H1), 2 is H2, etc.
    start_offset: int | None
        Optional character offset in the plain text where this section begins.
    end_offset: int | None
        Optional character offset in the plain text where this section ends.
    """

    title: str
    level: int
    start_offset: Optional[int] = None
    end_offset: Optional[int] = None


@dataclass(slots=True)
class ParsedDocument:
    """Container for parsed document outputs."""

    text: str = ""
    sections: List[SectionInfo] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class BaseParser(ABC):
    """Abstract parser interface."""

    @abstractmethod
    def can_parse(self, path: Path) -> bool:
        """Return True if this parser can handle the given file/path."""

    @abstractmethod
    def parse(self, path: Path) -> ParsedDocument:
        """Parse the file and return a `ParsedDocument`.

        Implementations should raise `doxie.exceptions.ParsingError` on failure.
        """
        raise NotImplementedError
