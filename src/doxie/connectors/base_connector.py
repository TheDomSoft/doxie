"""Base interfaces for external content connectors.

All connectors should implement asynchronous methods to fetch content and
optionally perform synchronization workflows.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

from doxie.parsers.base_parser import ParsedDocument


class BaseConnector(ABC):
    """Abstract connector interface.

    Implementations should be safe to construct without side effects and should
    not perform network calls until methods are invoked.
    """

    @abstractmethod
    async def fetch_content(self) -> List[ParsedDocument]:
        """Fetch and return a list of parsed documents from the source."""
        raise NotImplementedError

    @abstractmethod
    async def sync(self) -> None:
        """Perform a synchronization run (fetch + store + index)."""
        raise NotImplementedError
