"""SQLite reference implementation of the ``Store`` seam.

WAL mode + a process lock let thousands of fan-out runs write telemetry, outputs,
and idempotency claims concurrently without lock contention. Idempotency uses a
single ``INSERT OR IGNORE`` so check-then-write is atomic (no race). All SQL lives
here; call sites use the protocol.

Schema evolution is handled by :mod:`crawfish.store.migrations`: the version lives in
``PRAGMA user_version`` and forward migrations run on open. See that module for the
migration-authoring contract.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path

from crawfish.core.types import JSONValue
from crawfish.store.migrations import (
    CURRENT_SCHEMA_VERSION,
    StoreMigrationError,
    apply_migrations,
    upconvert_record,
)

__all__ = ["CURRENT_SCHEMA_VERSION", "SqliteStore", "StoreMigrationError"]


class SqliteStore:
    """A ``Store`` backed by SQLite. Use ``:memory:`` for tests, a path for dev."""

    def __init__(self, path: str | Path = ":memory:") -> None:
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        if str(path) != ":memory:":
            self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        # Migrate-on-open under the lock: a concurrent opener sees the bumped
        # user_version and applies nothing. Raises StoreMigrationError on a downgrade.
        with self._lock:
            apply_migrations(self._conn)
            self._conn.commit()

    # -- records ------------------------------------------------------------
    def put_record(
        self, kind: str, id: str, data: dict[str, JSONValue], *, org_id: str = "local"
    ) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO records(org_id, kind, id, json, updated_at) "
                "VALUES(?,?,?,?, julianday('now')) "
                "ON CONFLICT(org_id, kind, id) DO UPDATE SET "
                "json=excluded.json, updated_at=excluded.updated_at",
                (org_id, kind, id, json.dumps(data)),
            )
            self._conn.commit()

    def get_record(
        self, kind: str, id: str, *, org_id: str = "local"
    ) -> dict[str, JSONValue] | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT json FROM records WHERE org_id=? AND kind=? AND id=?",
                (org_id, kind, id),
            ).fetchone()
        if row is None:
            return None
        return upconvert_record(kind, json.loads(row["json"]))

    def list_records(self, kind: str, *, org_id: str = "local") -> list[dict[str, JSONValue]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT json FROM records WHERE org_id=? AND kind=? ORDER BY updated_at",
                (org_id, kind),
            ).fetchall()
        return [upconvert_record(kind, json.loads(r["json"])) for r in rows]

    def delete_record(self, kind: str, id: str, *, org_id: str = "local") -> None:
        with self._lock:
            self._conn.execute(
                "DELETE FROM records WHERE org_id=? AND kind=? AND id=?", (org_id, kind, id)
            )
            self._conn.commit()

    # -- KV -----------------------------------------------------------------
    def kv_get(self, namespace: str, key: str, *, org_id: str = "local") -> JSONValue | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT json FROM kv WHERE org_id=? AND namespace=? AND key=?",
                (org_id, namespace, key),
            ).fetchone()
        return json.loads(row["json"]) if row else None

    def kv_set(self, namespace: str, key: str, value: JSONValue, *, org_id: str = "local") -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO kv(org_id, namespace, key, json) VALUES(?,?,?,?) "
                "ON CONFLICT(org_id, namespace, key) DO UPDATE SET json=excluded.json",
                (org_id, namespace, key, json.dumps(value)),
            )
            self._conn.commit()

    # -- idempotency --------------------------------------------------------
    def claim_idempotency(self, key: str, *, org_id: str = "local") -> bool:
        with self._lock:
            cur = self._conn.execute(
                "INSERT OR IGNORE INTO idempotency(org_id, key) VALUES(?,?)", (org_id, key)
            )
            self._conn.commit()
            return cur.rowcount == 1

    # -- events -------------------------------------------------------------
    def append_event(
        self, run_id: str, event: dict[str, JSONValue], *, org_id: str = "local"
    ) -> None:
        with self._lock:
            row = self._conn.execute(
                "SELECT COALESCE(MAX(seq), -1) + 1 AS next FROM events WHERE org_id=? AND run_id=?",
                (org_id, run_id),
            ).fetchone()
            self._conn.execute(
                "INSERT INTO events(org_id, run_id, seq, json) VALUES(?,?,?,?)",
                (org_id, run_id, int(row["next"]), json.dumps(event)),
            )
            self._conn.commit()

    def events(self, run_id: str, *, org_id: str = "local") -> list[dict[str, JSONValue]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT json FROM events WHERE org_id=? AND run_id=? ORDER BY seq",
                (org_id, run_id),
            ).fetchall()
        return [json.loads(r["json"]) for r in rows]

    def close(self) -> None:
        with self._lock:
            self._conn.close()
