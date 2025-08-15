"""Custom exception hierarchy for Doxie.

These exceptions allow callers to discriminate error categories
and handle them appropriately while preserving the original context.
"""

from __future__ import annotations


class DoxieError(Exception):
    """Base class for all Doxie exceptions."""


class ConfigError(DoxieError):
    """Raised when configuration loading or validation fails."""


class ParsingError(DoxieError):
    """Raised when a document fails to parse."""


class StorageError(DoxieError):
    """Raised when the storage layer encounters an error (DB, filesystem, etc.)."""


class SearchError(DoxieError):
    """Raised for search indexing/query issues."""
