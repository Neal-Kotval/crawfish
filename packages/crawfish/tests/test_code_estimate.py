"""CRA-273 — ``craw code estimate`` cost preview + project budget threading.

Pins: ``estimate`` previews ``total``/``expected``/``worst_case`` with **no** model call; a
``[budget] ceiling_usd`` in ``crawfish.toml`` is read + threaded; a ``--live`` run whose
``worst_case_usd`` exceeds the remaining ceiling halts before the call with
``code='budget_exceeded'`` (exit 3); and the band honors ``total ≤ expected ≤ worst_case``.
No model calls (FakeJail compile + the pure cost estimator).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from crawfish.code import EXIT_BUDGET, ErrorCode
from crawfish.code.estimate import (
    EXIT_OK,
    BudgetCeilingExceeded,
    assert_within_budget,
    estimate_component,
    estimate_payload,
)
from crawfish.config import load_budget


def _project(
    tmp_path: Path, *, model: str = "claude-haiku-4-5", ceiling: float | None = None
) -> Path:
    root = tmp_path / "triage"
    (root / "agents").mkdir(parents=True)
    (root / "instructions.md").write_text("triage\n")
    (root / "definition.py").write_text(
        "from crawfish.core import Flow, Parameter\n"
        "inputs = [Parameter(name='ticket', type='str', flow=Flow.FLUID)]\n"
        "outputs = [Parameter(name='label', type='str', flow=Flow.STATIC)]\n"
        "lead = 'lead'\n"
    )
    (root / "agents" / "lead.md").write_text(f"---\nrole: lead\nmodel: {model}\n---\nTriage it.\n")
    toml = "[project]\nname = 'triage'\n"
    if ceiling is not None:
        toml += f"\n[budget]\nceiling_usd = {ceiling}\n"
    (root / "crawfish.toml").write_text(toml)
    return root


def test_estimate_previews_band_no_model_call(tmp_path: Path) -> None:
    """The estimate previews the band with no model call (pure estimator, positive spend)."""
    root = _project(tmp_path, model="claude-haiku-4-5")
    estimate, ceiling = estimate_component(str(root), items=100)
    assert estimate.total_usd > 0.0  # a priced team over 100 items has non-zero spend
    assert ceiling is None
    # Band invariant: total ≤ expected ≤ worst_case.
    assert estimate.total_usd <= estimate.expected_usd <= estimate.worst_case_usd


def test_budget_section_is_read_and_threaded(tmp_path: Path) -> None:
    """A ``[budget] ceiling_usd`` is read from crawfish.toml and threaded into the estimate."""
    root = _project(tmp_path, model="claude-haiku-4-5", ceiling=1000.00)
    assert load_budget(root).ceiling_usd == pytest.approx(1000.00)
    estimate, ceiling = estimate_component(str(root), items=100)
    assert ceiling == pytest.approx(1000.00)
    body = estimate_payload(
        estimate, component=str(root), ceiling_usd=ceiling, remaining_usd=ceiling
    )
    assert body["project_ceiling_usd"] == pytest.approx(1000.00)
    assert body["within_budget"] is True  # worst case well under a $1000 ceiling


def test_ceiling_below_worst_case_halts(tmp_path: Path) -> None:
    """A ``--live`` worst case above the remaining ceiling halts (BudgetCeilingExceeded)."""
    root = _project(tmp_path, model="claude-haiku-4-5", ceiling=0.001)
    estimate, ceiling = estimate_component(str(root), items=100)  # worst case >> $0.001
    with pytest.raises(BudgetCeilingExceeded):
        assert_within_budget(estimate, ceiling_usd=ceiling)


def test_within_budget_when_under_ceiling(tmp_path: Path) -> None:
    """A worst case under the remaining ceiling does not halt."""
    root = _project(tmp_path, model="claude-haiku-4-5", ceiling=1000.0)
    estimate, ceiling = estimate_component(str(root), items=100)
    assert_within_budget(estimate, ceiling_usd=ceiling)  # no raise


def test_estimate_verb_emits_payload(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """The verb emits ``craw.code.estimate.v1`` under ``--json`` (exit 0)."""
    import json

    from crawfish.code.cli import run_code

    root = _project(tmp_path, model="claude-haiku-4-5", ceiling=1000.00)
    rc = run_code(["estimate", str(root), "--items", "100", "--json"])
    assert rc == EXIT_OK
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert payload["schema"] == "craw.code.estimate.v1"
    assert payload["worst_case_usd"] > 0.0
    assert payload["project_ceiling_usd"] == pytest.approx(1000.00)
    assert payload["within_budget"] is True


def test_budget_exceeded_maps_to_exit_3() -> None:
    """The budget code maps to exit 3 and is non-retryable (the responsibility gate)."""
    from crawfish.code import CODE_EXIT, SECURITY_CODES

    assert CODE_EXIT[ErrorCode.BUDGET_EXCEEDED] == EXIT_BUDGET
    # budget_exceeded is not a *security* code, but the halt itself is non-retryable by the
    # caller's contract (an injected agent must not loop past it) — verified at the call site.
    assert ErrorCode.BUDGET_EXCEEDED not in SECURITY_CODES
