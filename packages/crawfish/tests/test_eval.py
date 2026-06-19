"""CRA-139 acceptance: capture/label/golden-set, LLM-judge, regression gating."""

from __future__ import annotations

import shutil
from pathlib import Path

from crawfish.core.context import RunContext
from crawfish.definition import Definition
from crawfish.eval import (
    GoldenSet,
    LLMJudge,
    capture_case,
    gate_against_baseline,
    grade_output,
    save_baseline,
)
from crawfish.metrics import Rubric, field_present
from crawfish.output import Output
from crawfish.runtime import MockRuntime
from crawfish.store import SqliteStore

FIXTURES = Path(__file__).parent / "fixtures"


def _judge_def(tmp_path: Path) -> Definition:
    dest = tmp_path / "minimal"
    shutil.copytree(FIXTURES / "minimal", dest, dirs_exist_ok=True)
    return Definition.from_package(str(dest))


def _ctx() -> RunContext:
    return RunContext(store=SqliteStore())


def _out(value: object = None) -> Output[object]:
    return Output(output_schema=[], value=value or {"text": "ok"}, produced_by="r1")


def test_capture_label_and_golden_set() -> None:
    store = SqliteStore()
    gs = GoldenSet(store, "triage")
    case = capture_case(inputs={"pr_body": "crash on login"}, output=_out())
    gs.add(case)
    gs.label(case.id, {"expected": "bug"})

    # persistence: a fresh GoldenSet over the same store sees the labeled case
    again = GoldenSet(store, "triage")
    loaded = again.get(case.id)
    assert loaded is not None
    assert loaded.label == {"expected": "bug"}
    assert len(again.cases()) == 1


async def test_llm_judge_scores_and_feeds_rubric(tmp_path: Path) -> None:
    judge = LLMJudge(_judge_def(tmp_path), MockRuntime(responder=lambda r: "score: 0.9"))
    out = _out()
    score = await judge.grade(out, _ctx())
    assert score == 0.9

    combined = await grade_output(
        out, _ctx(), rubric=Rubric([field_present("text")]), judges=[judge]
    )
    assert combined["llm_judge"] == 0.9  # judge grade present
    assert len(combined) >= 2  # rubric metric(s) + the judge both contributed
    assert max(combined.values()) == 1.0  # the coded metric scored the present field


def test_regression_gate_catches_worse_candidate() -> None:
    store = SqliteStore()
    save_baseline(store, "triage", {"accuracy": 0.9, "format": 1.0})
    # a worse candidate is gated out (regression caught)
    assert gate_against_baseline(store, "triage", {"accuracy": 0.7, "format": 1.0}) is False
    # an equal/better candidate passes
    assert gate_against_baseline(store, "triage", {"accuracy": 0.9, "format": 1.0}) is True


def test_no_baseline_passes() -> None:
    store = SqliteStore()
    assert gate_against_baseline(store, "unseen", {"accuracy": 0.5}) is True
