"""CRA-99 acceptance: Store round-trips records, KV, idempotency, events."""

from __future__ import annotations

import threading

from crawfish.store import SqliteStore, Store


def test_store_satisfies_protocol() -> None:
    assert isinstance(SqliteStore(), Store)


def test_record_roundtrip_definition_and_run() -> None:
    s = SqliteStore()
    s.put_record("definition", "d1", {"name": "clarity", "version": "0.1"})
    s.put_record("run", "r1", {"definition": "d1", "status": "done"})
    assert s.get_record("definition", "d1") == {"name": "clarity", "version": "0.1"}
    assert s.get_record("run", "r1") == {"definition": "d1", "status": "done"}
    assert len(s.list_records("run")) == 1


def test_tenancy_isolation() -> None:
    s = SqliteStore()
    s.put_record("run", "r1", {"a": 1}, org_id="acme")
    assert s.get_record("run", "r1") is None  # default org cannot see acme's row
    assert s.get_record("run", "r1", org_id="acme") == {"a": 1}


def test_kv_roundtrip() -> None:
    s = SqliteStore()
    s.kv_set("memory", "seen:ticket-1", True)
    assert s.kv_get("memory", "seen:ticket-1") is True
    assert s.kv_get("memory", "missing") is None


def test_idempotency_claim_is_once() -> None:
    s = SqliteStore()
    assert s.claim_idempotency("k") is True
    assert s.claim_idempotency("k") is False  # second claim loses


def test_idempotency_atomic_under_threads() -> None:
    s = SqliteStore()
    wins: list[bool] = []
    lock = threading.Lock()

    def claim() -> None:
        got = s.claim_idempotency("shared")
        with lock:
            wins.append(got)

    threads = [threading.Thread(target=claim) for _ in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sum(wins) == 1  # exactly one winner, no races


def test_events_append_and_read() -> None:
    s = SqliteStore()
    s.append_event("r1", {"event": "start"})
    s.append_event("r1", {"event": "done"})
    assert [e["event"] for e in s.events("r1")] == ["start", "done"]
