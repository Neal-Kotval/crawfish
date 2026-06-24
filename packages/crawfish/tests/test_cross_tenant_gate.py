"""SEC-5 (CRA-242) acceptance: cross-tenant isolation conformance gate.

Two orgs issuing an identical ``(definition, inputs)`` call must produce two distinct
cassette keys (never coalesce / share a cassette), and every Store/ledger/idempotency path
must be org-scoped. The conformance asserter is the single shared gate every new keyed
store registers against. All deterministic — recorded keys, no model call.
"""

from __future__ import annotations

import pytest

from crawfish.testing import (
    CrossTenantLeak,
    assert_cassette_key_org_scoped,
    assert_cross_tenant_isolation,
    assert_keyfn_org_scoped,
    assert_store_org_scoped,
)


def test_cassette_key_folds_org_id() -> None:
    """Identical (definition, inputs) under two orgs ⇒ two distinct cassette keys."""
    assert_cassette_key_org_scoped()  # no raise


def test_store_paths_org_scoped() -> None:
    """Record / event / idempotency Store paths are tenant-isolated."""
    assert_store_org_scoped()  # no raise


def test_full_isolation_gate_passes() -> None:
    """The shared CI gate passes on the shipped surfaces (F-1 key + Store)."""
    assert_cross_tenant_isolation()  # no raise


def test_keyfn_gate_catches_a_leaking_key() -> None:
    """A key function that IGNORES org_id is caught by the gate (the regression net)."""

    def leaky_key(*, org_id: str, x: int) -> str:
        return f"key-{x}"  # BUG: omits org_id — two orgs coalesce

    with pytest.raises(CrossTenantLeak):
        assert_keyfn_org_scoped(leaky_key, name="leaky", x=1)


def test_keyfn_gate_passes_an_org_scoped_key() -> None:
    """An org-folding key function passes the gate."""

    def good_key(*, org_id: str, x: int) -> str:
        return f"key-{org_id}-{x}"

    assert_keyfn_org_scoped(good_key, name="good", x=1)  # no raise


def test_keyfn_gate_catches_nondeterminism() -> None:
    """A non-deterministic key function fails the gate (same org ⇒ same key required)."""
    import itertools

    counter = itertools.count()

    def flaky_key(*, org_id: str) -> str:
        return f"{org_id}-{next(counter)}"

    with pytest.raises(CrossTenantLeak):
        assert_keyfn_org_scoped(flaky_key, name="flaky")


def test_extra_key_fns_fold_into_the_gate() -> None:
    """A new keyed store registers its key fn into the single shared gate."""

    def store_key(*, org_id: str, kind: str, id: str) -> str:
        return f"{org_id}:{kind}:{id}"  # correctly org-scoped

    assert_cross_tenant_isolation(
        extra_key_fns=[("new_store", store_key, {"kind": "k", "id": "i"})]
    )  # no raise
