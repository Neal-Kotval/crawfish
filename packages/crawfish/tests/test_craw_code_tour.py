"""The Wave-6 ``craw code`` tour, pinned end to end (deterministic, mock-only, fast).

This drives the *real* verbs through :func:`crawfish.code.cli.run_code` — via the shared
:func:`demo.craw-code-tour.tour.run_tour` walkthrough — against a freshly ``craw code init``'d
project in ``tmp_path``, and asserts every step's exit code + the load-bearing envelope fields.
No live model call, no network: the two model-shaped steps are stood in for ($0 ``refine``
optimize; a failed run seeded straight into the ledger through the ObserverSurface). See
``demo/craw-code-tour/README.md`` for the narrated walkthrough.

The two fail-closed contracts are the heart of the suite:

* ``apply`` with **no** recorded approval → ``no_approval``, exit ``4`` (security, non-retryable),
  the spec's granular ``detail.exit=7``.
* ``apply`` after the component's **on-disk sha drifts** from the approved sha → ``no_approval``,
  exit ``4``, with ``detail.approved_sha != detail.current_sha`` — re-propose required.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

#: The tour lives under ``demo/craw-code-tour/`` (not an installed package), so we load it by
#: path — the same module the runnable ``tour.py`` script uses, so the test and the demo can
#: never drift apart.
_TOUR_PATH = Path(__file__).resolve().parents[3] / "demo" / "craw-code-tour" / "tour.py"


def _load_tour() -> ModuleType:
    """Import ``demo/craw-code-tour/tour.py`` by file path (it is not on ``sys.path``)."""
    spec = importlib.util.spec_from_file_location("craw_code_tour", _TOUR_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def tour_result(tmp_path_factory: pytest.TempPathFactory) -> object:
    """Run the whole tour once against a fresh tmp project; share the captured steps.

    Module-scoped so the (already fast) tour runs once for all assertions. The tour ``chdir``s
    into the project and restores cwd on exit, so it is self-contained.
    """
    if not _TOUR_PATH.exists():  # pragma: no cover - guards a moved demo
        pytest.skip(f"tour script not found at {_TOUR_PATH}")
    tour = _load_tour()
    project = tmp_path_factory.mktemp("craw-code-tour") / "app"
    return tour.run_tour(project, echo=False)


def test_every_step_meets_its_expected_exit(tour_result: object) -> None:
    """The whole tour is green: every step's exit code matches what that step expects.

    A fail-closed rejection is a *passing* step — it expects exit ``4`` — so this asserts the
    tour's own per-step verdict, not "exit == 0".
    """
    failures = [s.name for s in tour_result.steps if not s.ok]  # type: ignore[attr-defined]
    assert not failures, f"unexpected exit codes for steps: {failures}"
    assert tour_result.all_ok  # type: ignore[attr-defined]


def test_init_scaffolds_the_component(tour_result: object) -> None:
    step = tour_result.by_name("init")  # type: ignore[attr-defined]
    assert step.exit_code == 0
    assert step.envelope["schema"] == "craw.code.init.v1"
    assert "definitions/triage-bot/definition.py" in step.envelope["scaffolded"]


def test_describe_reflects_typed_io(tour_result: object) -> None:
    step = tour_result.by_name("describe")  # type: ignore[attr-defined]
    assert step.exit_code == 0
    assert step.envelope["schema"] == "craw.code.describe.v1"
    # The STATIC consequential triage output is part of the reflected boundary.
    out_names = {o["name"] for o in step.envelope["outputs"]}  # type: ignore[index]
    assert "triage" in out_names


def test_estimate_emits_honest_cost_band(tour_result: object) -> None:
    step = tour_result.by_name("estimate")  # type: ignore[attr-defined]
    assert step.exit_code == 0
    env = step.envelope
    assert env["schema"] == "craw.code.estimate.v1"
    # total ≤ expected ≤ worst_case is the honesty invariant (CRA cost band).
    assert env["total_usd"] <= env["expected_usd"] <= env["worst_case_usd"]


def test_sync_is_clean_for_a_fresh_project(tour_result: object) -> None:
    step = tour_result.by_name("sync")  # type: ignore[attr-defined]
    assert step.exit_code == 0
    assert step.envelope["schema"] == "craw.code.sync.v1"
    assert step.envelope["drift"] == []
    assert step.envelope["load_errors"] == []


def test_validate_authoring_eval_passes(tour_result: object) -> None:
    step = tour_result.by_name("validate-authoring")  # type: ignore[attr-defined]
    assert step.exit_code == 0
    assert step.envelope["schema"] == "craw.code.validate.v1"
    # The negative corpus is rejected by the right gate, the positive fixture is gate-clean.
    assert all(n["rejected"] for n in step.envelope["negatives"])  # type: ignore[index]
    assert all(p["ok"] for p in step.envelope["positives"])  # type: ignore[index]


def test_optimize_runs_zero_cost_refine(tour_result: object) -> None:
    step = tour_result.by_name("optimize")  # type: ignore[attr-defined]
    assert step.exit_code == 0
    assert step.envelope["schema"] == "craw.code.optimize.v1"
    assert step.envelope["mode"] == "refine"


# ---------------------------------------------------------------------------
# The human-approval gate — the heart of the tour.
# ---------------------------------------------------------------------------
def test_propose_stages_a_pending_typed_diff(tour_result: object) -> None:
    step = tour_result.by_name("propose")  # type: ignore[attr-defined]
    assert step.exit_code == 0
    env = step.envelope
    assert env["schema"] == "craw.code.propose.v1"
    assert env["approval"] == "pending"  # no human decision yet → pending (fail closed)
    assert env["candidate_sha"]  # a content-addressed sha
    assert set(env["cost_estimate"]) == {"total_usd", "expected_usd", "worst_case_usd"}  # type: ignore[arg-type]


def test_apply_without_approval_fails_closed(tour_result: object) -> None:
    """The load-bearing gate: an unapproved promotion is rejected, non-retryably."""
    step = tour_result.by_name("apply_no_approval")  # type: ignore[attr-defined]
    assert step.exit_code == 4  # EXIT_SECURITY
    env = step.envelope
    assert env["schema"] == "craw.error.v1"
    assert env["code"] == "no_approval"
    assert env["retryable"] is False  # an injected agent cannot retry past it
    assert env["detail"]["exit"] == 7  # the spec's granular code rides in the envelope


def test_reject_records_the_decision(tour_result: object) -> None:
    step = tour_result.by_name("reject")  # type: ignore[attr-defined]
    assert step.exit_code == 0
    assert step.envelope["schema"] == "craw.code.reject.v1"
    assert step.envelope["result"] == "rejected"


def test_apply_with_recorded_approval_promotes(tour_result: object) -> None:
    step = tour_result.by_name("apply_approved")  # type: ignore[attr-defined]
    assert step.exit_code == 0
    assert step.envelope["schema"] == "craw.code.apply.v1"
    assert step.envelope["result"] == "applied"


def test_apply_after_sha_drift_fails_closed(tour_result: object) -> None:
    """A recorded approval for sha A cannot promote an on-disk component that drifted to sha B."""
    step = tour_result.by_name("apply_sha_drift")  # type: ignore[attr-defined]
    assert step.exit_code == 4  # EXIT_SECURITY
    env = step.envelope
    assert env["code"] == "no_approval"
    assert env["retryable"] is False
    detail = env["detail"]
    # The drift is visible in the envelope: approved sha ≠ current on-disk sha.
    assert detail["approved_sha"] != detail["current_sha"]  # type: ignore[index]


# ---------------------------------------------------------------------------
# Operate / observe — deploy, then read a real (seeded) ledger.
# ---------------------------------------------------------------------------
def test_deploy_registers_pipeline_and_observers(tour_result: object) -> None:
    step = tour_result.by_name("deploy")  # type: ignore[attr-defined]
    assert step.exit_code == 0
    assert step.envelope["schema"] == "craw.code.deploy.v1"
    assert step.envelope["pipeline"] == "triage-bot"
    assert step.envelope["observers_scaffolded"]  # default observers were scaffolded


def test_dashboard_snapshot_carries_the_seeded_run(tour_result: object) -> None:
    step = tour_result.by_name("dashboard")  # type: ignore[attr-defined]
    assert step.exit_code == 0
    env = step.envelope
    assert env["schema"] == "craw.code.dashboard.v1"
    run_ids = {e["run_id"] for e in env["events"]}  # type: ignore[index]
    assert "run-tour-1" in run_ids


def test_dashboard_json_carries_tainted_detail_verbatim_for_html_encoding(
    tour_result: object,
) -> None:
    """The --json snapshot carries the tainted ``detail`` as a string (a parser never executes
    it); the HTML renderer is the layer that output-encodes it. Here we prove the raw payload
    rode through --json, and that the dashboard's own encoder neutralizes it for HTML."""
    from crawfish.code.dashboard import Encoding, encode_field

    step = tour_result.by_name("dashboard")  # type: ignore[attr-defined]
    details = [e["detail"] for e in step.envelope["events"]]  # type: ignore[index]
    tainted = next(d for d in details if "<script>" in d)
    # In HTML context the chokepoint renders the <script> inert (entity-encoded).
    encoded = encode_field(tainted, Encoding.HTML_BODY)
    assert "<script>" not in encoded
    assert "&lt;script&gt;" in encoded


def test_review_output_encodes_the_tainted_detail(tour_result: object) -> None:
    """``review`` is a digest surface; its tainted detail is already output-encoded in the body."""
    step = tour_result.by_name("review")  # type: ignore[attr-defined]
    assert step.exit_code == 0
    assert step.envelope["schema"] == "craw.code.review.v1"
    blob = str(step.envelope.get("findings"))
    assert "<script>" not in blob  # the digest neutralized the markup
    assert "&lt;script&gt;" in blob


def test_diagnose_correlates_the_first_failure(tour_result: object) -> None:
    step = tour_result.by_name("diagnose")  # type: ignore[attr-defined]
    assert step.exit_code == 0
    env = step.envelope
    assert env["schema"] == "craw.code.diagnose.v1"
    assert env["first_failure"]["node"] == "summarize"  # type: ignore[index]
    # A $0 replay remediation, not a re-run.
    assert env["remediation"]["action"] == "replay_swap"  # type: ignore[index]
