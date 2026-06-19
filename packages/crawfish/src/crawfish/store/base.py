"""The ``Store`` seam — all persistence goes through this protocol (CRA-99).

The product model imports the *protocol*, never a concrete backend, so SQLite →
Postgres is a driver swap. No raw SQL appears at any call site. Every row carries
an ``org_id`` tenancy key (defaulted ``"local"``) so cloud multi-tenancy is a
driver swap, not a schema migration.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from crawfish.core.types import JSONValue

__all__ = ["Store"]


@runtime_checkable
class Store(Protocol):
    """Persistence contract: typed records, KV/memory, idempotency, telemetry."""

    # -- records (Definitions, Runs, Outputs, ...) --------------------------
    def put_record(
        self, kind: str, id: str, data: dict[str, JSONValue], *, org_id: str = "local"
    ) -> None: ...

    def get_record(
        self, kind: str, id: str, *, org_id: str = "local"
    ) -> dict[str, JSONValue] | None: ...

    def list_records(self, kind: str, *, org_id: str = "local") -> list[dict[str, JSONValue]]: ...

    def delete_record(self, kind: str, id: str, *, org_id: str = "local") -> None: ...

    # -- KV / working memory (CRA-123 builds on this) -----------------------
    def kv_get(self, namespace: str, key: str, *, org_id: str = "local") -> JSONValue | None: ...

    def kv_set(
        self, namespace: str, key: str, value: JSONValue, *, org_id: str = "local"
    ) -> None: ...

    # -- idempotency: transactional check-then-claim (CRA-104) --------------
    def claim_idempotency(self, key: str, *, org_id: str = "local") -> bool:
        """Atomically claim ``key``. Returns True iff this call won the claim
        (i.e. it had not been claimed before). Safe under concurrency."""
        ...

    # -- telemetry / execution ledger (CRA-106, CRA-134) --------------------
    def append_event(
        self, run_id: str, event: dict[str, JSONValue], *, org_id: str = "local"
    ) -> None: ...

    def events(self, run_id: str, *, org_id: str = "local") -> list[dict[str, JSONValue]]: ...

    def close(self) -> None: ...
