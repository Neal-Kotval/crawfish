"""Persistence seam: the ``Store`` protocol + SQLite reference impl."""

from __future__ import annotations

from crawfish.store.base import Store
from crawfish.store.migrations import (
    CURRENT_SCHEMA_VERSION,
    Migration,
    StoreMigrationError,
)
from crawfish.store.sqlite import SqliteStore

__all__ = [
    "CURRENT_SCHEMA_VERSION",
    "Migration",
    "SqliteStore",
    "Store",
    "StoreMigrationError",
]
