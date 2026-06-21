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


# -- CRA-175: golden-set string→typed migration & deterministic LLM-judge ----
from crawfish.eval import EvalCase, migrate_golden_set, upconvert_case  # noqa: E402
from crawfish.metrics import field_exact_match  # noqa: E402


def test_upconvert_case_lifts_string_output_and_label() -> None:
    # a string-era row: output/label are JSON-encoded strings
    rec = {"id": "c1", "inputs": {}, "output": '{"cls": "bug"}', "label": '{"expected": "bug"}'}
    lifted = upconvert_case(rec)
    assert lifted["output"] == {"cls": "bug"}  # now a typed dict
    assert lifted["label"] == {"expected": "bug"}
    # free text and ambiguous multi-object strings are left untouched
    assert upconvert_case({"output": "plain text"})["output"] == "plain text"
    assert upconvert_case({"output": '{"a":1}{"b":2}'})["output"] == '{"a":1}{"b":2}'
    # already-typed rows are idempotent
    typed = {"output": {"cls": "bug"}}
    assert upconvert_case(typed)["output"] == {"cls": "bug"}


def test_golden_set_migration_upconverts_on_read_and_in_place() -> None:
    store = SqliteStore()
    gs = GoldenSet(store, "triage")
    # simulate a string-era persisted case by writing the raw string-output record
    raw = EvalCase(inputs={"pr": "x"}, output='{"cls": "bug"}', label='{"expected": "bug"}')
    store.put_record(gs._kind, raw.id, raw.model_dump(mode="json"))  # noqa: SLF001

    # lazy read path: get()/cases() return TYPED values without a migration run
    loaded = gs.get(raw.id)
    assert loaded is not None
    assert loaded.output == {"cls": "bug"}
    assert loaded.label == {"expected": "bug"}

    # a typed metric scores the migrated value directly
    out = Output(output_schema=[], value=loaded.output, produced_by="r")
    assert field_exact_match("bug", field="cls").evaluate(out) == 1.0

    # bulk migrate rewrites in place; second run is a no-op (idempotent)
    assert migrate_golden_set(store, "triage") == 1
    assert migrate_golden_set(store, "triage") == 0


async def test_llm_judge_deterministic_on_recorded_output(tmp_path: Path) -> None:
    # Deterministic: the judge runs on a RECORDED output via MockRuntime — no live call,
    # same verdict every run.
    judge = LLMJudge(_judge_def(tmp_path), MockRuntime(responder=lambda r: "verdict score: 0.8"))
    recorded = Output(output_schema=[], value={"cls": "bug"}, produced_by="agent")
    first = await judge.grade(recorded, _ctx(), criteria="accuracy")
    second = await judge.grade(recorded, _ctx(), criteria="accuracy")
    assert first == second == 0.8
