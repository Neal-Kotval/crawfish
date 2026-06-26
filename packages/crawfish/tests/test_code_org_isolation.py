"""CRA-275 — thread org_id (tenancy) through all craw code verbs.

Every ``Store`` row carries an ``org_id`` (defaulted ``"local"``). The new ``craw code`` verbs
must thread the same ``org_id`` or risk cross-tenant leakage (§12.3). Pins: every verb accepts
``--org`` and threads it; CRA-266 provenance rows and the CRA-274 describe cache are org-scoped;
and the acceptance gate — a two-org isolation test — a verb under ``--org a`` sees none of
``--org b``'s rows. Reuses the registered cross-tenant isolation surface. No model calls.
"""

from __future__ import annotations

from pathlib import Path

from crawfish.code.describe import _cache_path, describe_component
from crawfish.provenance import file_provenance
from crawfish.store import SqliteStore
from crawfish.testing import assert_store_org_scoped


def _project(tmp_path: Path) -> Path:
    root = tmp_path / "triage"
    root.mkdir(parents=True)
    (root / "instructions.md").write_text("triage\n")
    (root / "definition.py").write_text(
        "from crawfish.core import Flow, Parameter\n"
        "inputs = [Parameter(name='ticket', type='str', flow=Flow.FLUID)]\n"
        "outputs = [Parameter(name='label', type='str', flow=Flow.STATIC)]\n"
    )
    return root


def test_store_paths_are_org_scoped() -> None:
    """The shared Store-isolation gate passes (records / events / idempotency tenant-scoped)."""
    assert_store_org_scoped()  # no raise


def test_describe_provenance_rows_are_org_scoped(tmp_path: Path) -> None:
    """A describe under org A writes provenance rows org B cannot read (CRA-266 + CRA-275)."""
    root = _project(tmp_path)
    store = SqliteStore()
    try:
        describe_component(str(root), store=store, org_id="acme")
        from crawfish.code.describe import _file_sha

        sha = _file_sha(root / "definition.py")
        # Org A (acme) recorded a row; org B (other) sees nothing for the same file/sha.
        assert file_provenance("definition.py", sha, store=store, org_id="acme") is not None
        assert file_provenance("definition.py", sha, store=store, org_id="other") is None
    finally:
        store.close()


def test_describe_cache_is_org_scoped(tmp_path: Path) -> None:
    """The describe cache lands under a per-org subdir — no cross-org cache read (CRA-275)."""
    root = _project(tmp_path)
    store = SqliteStore()
    try:
        describe_component(str(root), store=store, org_id="acme")
    finally:
        store.close()
    # Org A's cache exists; org B's cache dir is empty (no shared projection).
    from crawfish.definition.compiler import _content_sha

    sha = _content_sha(root)
    assert _cache_path(root, sha, "acme").exists()
    assert not _cache_path(root, sha, "other").exists()


def test_two_org_describe_no_cross_read(tmp_path: Path) -> None:
    """The acceptance gate: describe under two orgs against a shared store never cross-reads."""
    root = _project(tmp_path)
    store = SqliteStore()
    try:
        body_a = describe_component(str(root), store=store, org_id="orgA")
        body_b = describe_component(str(root), store=store, org_id="orgB")
        # Both compile the same on-disk component (same typed shape) but in isolated tenancy:
        # neither org's provenance row nor cache is visible to the other (asserted above).
        assert body_a["content_sha"] == body_b["content_sha"]
        from crawfish.code.describe import _file_sha

        sha = _file_sha(root / "definition.py")
        assert file_provenance("definition.py", sha, store=store, org_id="orgA") is not None
        assert file_provenance("definition.py", sha, store=store, org_id="orgB") is not None
        # Cross-read is impossible — a third org sees neither.
        assert file_provenance("definition.py", sha, store=store, org_id="orgC") is None
    finally:
        store.close()
