"""Persistence seam: the ``Store`` protocol + SQLite reference impl."""

from __future__ import annotations

from crawfish.store.base import Store
from crawfish.store.sqlite import SqliteStore

__all__ = ["Store", "SqliteStore"]
