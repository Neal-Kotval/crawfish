"""CRA-219 (OPT-1) + CRA-222 (OPT-4) acceptance — the optimization-plane CLI.

Each of ``craw eval / tune / refine / learn / guard`` registers, parses, dispatches, and
honours ``--budget --seed --org --json`` (the versioned machine-readable surface ``craw
code`` parses). ``craw lock`` writes a pinned transitive-closure lockfile and ``--check``
detects drift. Everything here is deterministic on the MockRuntime — NO live model call.

The acceptance criteria exercised (issue §):
* all five register + accept the shared flags;
* ``craw tune --seed S`` twice ⇒ byte-identical ``winner`` sha + trial log;
* ``craw eval`` exits non-zero iff a regression; ``--json`` emits per-case deltas + cost band;
* ``craw tune --budget B`` with a per-trial cost stops with ``stopped_reason="budget"``;
* ``craw learn --rollback <sha>`` re-activates a prior version (no model call);
* ``craw guard`` distils a closed-grammar predicate into a stage;
* every ``--json`` schema is shape-snapshot-tested;
* ``craw lock`` writes the closure and ``--check`` exits non-zero on drift.
"""

from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from pathlib import Path

import pytest

from crawfish.cli import LOCKFILE_NAME, main
from crawfish.scaffold import scaffold_project


# --------------------------------------------------------------------------- helpers
def _project(tmp_path: Path) -> str:
    """A scaffolded project (the shipped triage-bot Definition) under tmp."""
    root = scaffold_project(str(tmp_path / "app"))
    return str(root / "definitions" / "triage-bot")


def _run_json(argv: list[str]) -> tuple[int, dict[str, object]]:
    """Run a CLI command with ``--json`` and return ``(exit_code, parsed_last_line)``."""
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = main(argv)
    last = buf.getvalue().strip().splitlines()[-1]
    return rc, json.loads(last)


# --------------------------------------------------------------------------- registration
def test_all_subcommands_register_and_accept_shared_flags(tmp_path: Path) -> None:
    path = _project(tmp_path)
    common = ["--budget", "5.0", "--seed", "3", "--org", "acme", "--json"]
    # Each parses + dispatches with the shared flags and reports its schema + threaded org.
    for cmd, extra in [
        ("eval", []),
        ("tune", ["--models", "claude-haiku-4-5", "claude-opus-4-8"]),
        ("refine", ["--until", "score>=0.5", "--max-iters", "2"]),
        ("learn", ["--models", "claude-haiku-4-5", "claude-opus-4-8"]),
        ("guard", ["--predicate", '{"kind":"always","value":true}']),
    ]:
        _rc, payload = _run_json([cmd, path, *common, *extra])
        assert payload["schema"] == f"craw.{cmd}.v1"
        assert payload["org"] == "acme"
        assert payload["seed"] == 3


# --------------------------------------------------------------------------- eval
def test_eval_emits_scores_and_cost_band(tmp_path: Path) -> None:
    rc, payload = _run_json(["eval", _project(tmp_path), "--json"])
    assert rc == 0  # no baseline ⇒ nothing to regress against
    assert payload["scores"]["score"] == 5.0
    cost = payload["cost"]
    # The honest OPT-2 band: lower <= expected <= worst_case.
    assert cost["lower_usd"] <= cost["expected_usd"] <= cost["worst_case_usd"]


def test_eval_gates_on_baseline_and_emits_deltas(tmp_path: Path) -> None:
    path = _project(tmp_path)
    # Seed a baseline of the current scores (score=5), then a real run must NOT regress.
    rc0, _ = _run_json(["eval", path, "--baseline", "bench", "--set-baseline", "--json"])
    assert rc0 == 0
    rc1, payload = _run_json(["eval", path, "--baseline", "bench", "--json"])
    assert rc1 == 0
    assert payload["regressed"] is False
    assert payload["passed"] is True
    # Per-metric deltas are emitted against the stored baseline.
    assert payload["deltas"] == {"score": 0.0}


def test_eval_exits_nonzero_on_regression(tmp_path: Path) -> None:
    path = _project(tmp_path)
    # Plant a baseline ABOVE the achievable score so the next run reads as a regression.
    from crawfish.cli import _open_store
    from crawfish.eval import save_baseline

    store = _open_store(path)
    save_baseline(store, "high", {"score": 99.0}, org_id="local")
    store.close()
    rc, payload = _run_json(["eval", path, "--baseline", "high", "--json"])
    assert rc == 1
    assert payload["regressed"] is True
    assert payload["passed"] is False


# --------------------------------------------------------------------------- tune
def test_tune_is_byte_identical_across_runs(tmp_path: Path) -> None:
    path = _project(tmp_path)
    args = [
        "tune",
        path,
        "--models",
        "claude-haiku-4-5",
        "claude-opus-4-8",
        "--seed",
        "7",
        "--json",
    ]
    buf_a, buf_b = io.StringIO(), io.StringIO()
    with redirect_stdout(buf_a):
        main(args)
    with redirect_stdout(buf_b):
        main(args)
    # Same seed ⇒ byte-identical winner sha + trial log (the whole JSON line).
    assert buf_a.getvalue() == buf_b.getvalue()
    payload = json.loads(buf_a.getvalue().strip())
    assert payload["winner"]  # a real winning sha
    assert payload["best_scores"]["score"] == 9.0  # the strong model wins


def test_tune_budget_stops_with_budget_reason(tmp_path: Path) -> None:
    path = _project(tmp_path)
    # Per-trial cost 0.30 against a 0.50 ceiling ⇒ only the first trial fits, then budget.
    _rc, payload = _run_json(
        [
            "tune",
            path,
            "--models",
            "claude-haiku-4-5",
            "claude-opus-4-8",
            "--budget",
            "0.50",
            "--cost-per-trial",
            "0.30",
            "--json",
        ]
    )
    assert payload["stopped_reason"] == "budget"


# --------------------------------------------------------------------------- refine
def test_refine_until_dsl_drives_the_loop(tmp_path: Path) -> None:
    rc, payload = _run_json(
        ["refine", _project(tmp_path), "--until", "score>=0.5", "--max-iters", "3", "--json"]
    )
    assert rc == 0  # the mock clears the (clamped) threshold immediately
    assert payload["refine_stopped"] == "satisfied"
    assert payload["metric"] == "score"


def test_refine_rejects_a_malformed_until() -> None:
    with pytest.raises(SystemExit):
        main(["refine", ".", "--until", "score~=bogus"])


# --------------------------------------------------------------------------- learn
def test_learn_improves_then_rollback_reactivates_prior_version(tmp_path: Path) -> None:
    path = _project(tmp_path)
    # One improve cycle promotes the strong-model winner over the base.
    rc, improved = _run_json(
        [
            "learn",
            path,
            "--name",
            "agent",
            "--models",
            "claude-haiku-4-5",
            "claude-opus-4-8",
            "--json",
        ]
    )
    assert rc == 0
    assert improved["promoted"] is True
    base_sha = str(improved["base_sha"])

    # Rollback to the base is a pointer move (no model call) — re-activates the prior version.
    rc2, rolled = _run_json(["learn", path, "--name", "agent", "--rollback", base_sha, "--json"])
    assert rc2 == 0
    assert rolled["rolled_back"] is True
    assert rolled["active"] == base_sha


def test_learn_rollback_unknown_sha_fails_closed(tmp_path: Path) -> None:
    rc, payload = _run_json(
        ["learn", _project(tmp_path), "--name", "x", "--rollback", "nope", "--json"]
    )
    assert rc == 1
    assert payload["rolled_back"] is False


# --------------------------------------------------------------------------- guard
def test_guard_distills_a_predicate_into_a_stage(tmp_path: Path) -> None:
    # No corrections corpus ⇒ the joint gate fails closed: the guard stays non-blocking.
    rc, payload = _run_json(
        [
            "guard",
            _project(tmp_path),
            "--predicate",
            '{"kind":"comparison","field":"verdict","op":"==","literal":"unsafe"}',
            "--json",
        ]
    )
    assert rc == 0
    assert payload["earned"] is False
    assert payload["stage"] in {"shadow", "warn", "block"}


def test_guard_rejects_a_malformed_predicate(tmp_path: Path) -> None:
    rc, payload = _run_json(["guard", _project(tmp_path), "--predicate", "not json", "--json"])
    assert rc == 1
    assert payload["earned"] is False
    assert "error" in payload


# --------------------------------------------------------------------------- lock (CRA-222)
def test_lock_writes_a_closure_then_check_passes(tmp_path: Path) -> None:
    root = scaffold_project(str(tmp_path / "app"))
    proj = str(root)
    assert main(["lock", "--dir", proj]) == 0
    lock_path = Path(proj) / LOCKFILE_NAME
    assert lock_path.exists()
    doc = json.loads(lock_path.read_text())
    assert doc["lockfile_version"] == 1
    assert doc["closure_sha"].startswith("sha256:")
    assert doc["pins"]  # at least the root pin
    # A fresh re-resolve matches the on-disk closure ⇒ --check is clean.
    assert main(["lock", "--dir", proj, "--check"]) == 0


def test_lock_check_detects_drift(tmp_path: Path) -> None:
    root = scaffold_project(str(tmp_path / "app"))
    proj = str(root)
    main(["lock", "--dir", proj])
    lock_path = Path(proj) / LOCKFILE_NAME
    # Tamper with a pinned version: the on-disk closure no longer matches a re-resolve.
    doc = json.loads(lock_path.read_text())
    doc["pins"][0]["version"] = "9.9.9"
    lock_path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n")
    # --check fails closed (the tampered lockfile drifts from / is invalid vs the resolve).
    assert main(["lock", "--dir", proj, "--check"]) == 1


def test_lock_check_without_a_lockfile_fails(tmp_path: Path) -> None:
    root = scaffold_project(str(tmp_path / "app"))
    assert main(["lock", "--dir", str(root), "--check"]) == 1


# --------------------------------------------------------------------------- JSON schema snapshots
def test_json_schemas_are_stable(tmp_path: Path) -> None:
    """Snapshot the versioned ``--json`` key sets — the contract ``craw code`` parses."""
    path = _project(tmp_path)
    _rc, ev = _run_json(["eval", path, "--json"])
    assert set(ev) == {
        "schema",
        "seed",
        "org",
        "scores",
        "baseline",
        "deltas",
        "regressed",
        "passed",
        "cost",
    }
    assert set(ev["cost"]) == {"lower_usd", "expected_usd", "worst_case_usd"}

    _rc, tu = _run_json(["tune", path, "--models", "claude-haiku-4-5", "--json"])
    assert set(tu) == {
        "schema",
        "seed",
        "org",
        "winner",
        "stopped_reason",
        "improved",
        "base_scores",
        "best_scores",
        "trials",
    }

    _rc, rf = _run_json(["refine", path, "--until", "score>=0.5", "--json"])
    assert set(rf) == {
        "schema",
        "seed",
        "org",
        "until",
        "metric",
        "at_least",
        "refine_iters",
        "spent_usd",
        "refine_stopped",
        "best_progress",
    }

    _rc, gd = _run_json(["guard", path, "--predicate", '{"kind":"always","value":false}', "--json"])
    assert set(gd) == {
        "schema",
        "seed",
        "org",
        "stage",
        "earned",
        "tainted",
        "content_sha",
        "reason",
    }
