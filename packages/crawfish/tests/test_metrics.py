"""CRA-110 acceptance: metrics, rubrics, benchmarks, regression detection."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from crawfish.batch import Task
from crawfish.core.context import RunContext
from crawfish.definition import Definition
from crawfish.metrics import (
    Benchmark,
    Rubric,
    compare,
    confidence_threshold,
    field_present,
    is_nonempty,
    is_regression,
    output_number,
)
from crawfish.output import Output
from crawfish.runtime import MockRuntime
from crawfish.runtime.base import RunRequest
from crawfish.store import SqliteStore

FIXTURES = Path(__file__).parent / "fixtures"


def _out(value: object) -> Output[object]:
    return Output(output_schema=[], value=value, produced_by="r")


# -- starter metrics --------------------------------------------------------
def test_output_number_from_field_and_string() -> None:
    assert output_number(field="score").evaluate(_out({"score": 0.9, "text": "ok"})) == 0.9
    assert output_number().evaluate(_out("rated 7 of 10")) == 7.0
    assert output_number(default=-1.0).evaluate(_out("no digits here")) == -1.0


def test_field_present() -> None:
    metric = field_present("text")
    assert metric.evaluate(_out({"score": 0.9, "text": "ok"})) == 1.0
    assert metric.evaluate(_out({"score": 0.9})) == 0.0
    assert metric.evaluate(_out({"text": None})) == 0.0


def test_is_nonempty() -> None:
    assert is_nonempty().evaluate(_out("ok")) == 1.0
    assert is_nonempty().evaluate(_out("   ")) == 0.0
    assert is_nonempty().evaluate(_out([])) == 0.0
    assert is_nonempty(field="text").evaluate(_out({"text": "hi"})) == 1.0
    assert is_nonempty(field="text").evaluate(_out({"text": ""})) == 0.0


def test_confidence_threshold() -> None:
    metric = confidence_threshold("score", 0.8)
    assert metric.evaluate(_out({"score": 0.9})) == 1.0
    assert metric.evaluate(_out({"score": 0.5})) == 0.0
    assert metric.evaluate(_out({})) == 0.0


def test_rubric_scores_one_float_per_metric() -> None:
    rubric = Rubric(
        [
            output_number(field="score"),
            field_present("text"),
            is_nonempty(field="text"),
            confidence_threshold("score", 0.8),
        ]
    )
    scores = rubric.score(_out({"score": 0.9, "text": "ok"}))
    assert set(scores) == {m.name for m in rubric.metrics}
    assert len(scores) == 4
    assert all(isinstance(v, float) for v in scores.values())
    assert scores[output_number(field="score").name] == 0.9


# -- benchmark over a fixed task set ----------------------------------------
def _minimal(tmp_path: Path) -> Definition:
    dest = tmp_path / "minimal"
    shutil.copytree(FIXTURES / "minimal", dest, dirs_exist_ok=True)
    return Definition.from_package(str(dest))


def _json_runtime(payload: dict[str, object]) -> MockRuntime:
    def responder(_request: RunRequest) -> str:
        return json.dumps(payload)

    return MockRuntime(responder)


def _rubric() -> Rubric:
    return Rubric(
        [
            output_number(field="score"),
            is_nonempty(field="text"),
            confidence_threshold("score", 0.8),
        ]
    )


async def test_benchmark_aggregates_per_metric(tmp_path: Path) -> None:
    definition = _minimal(tmp_path)
    tasks = [Task(description="a"), Task(description="b"), Task(description="c")]
    benchmark = Benchmark(_rubric(), tasks)
    ctx = RunContext(store=SqliteStore())

    scores = await benchmark.run(definition, ctx, _json_runtime({"score": 0.9, "text": "ok"}))

    assert set(scores) == {m.name for m in _rubric().metrics}
    assert scores[output_number(field="score").name] == 0.9  # mean across 3 tasks
    assert scores[is_nonempty(field="text").name] == 1.0
    assert scores[confidence_threshold("score", 0.8).name] == 1.0


# -- the improvement loop ---------------------------------------------------
async def test_two_versions_produce_comparable_ordered_scores(tmp_path: Path) -> None:
    definition = _minimal(tmp_path)
    tasks = [Task(description="a"), Task(description="b")]
    rubric = _rubric()

    baseline = await Benchmark(rubric, tasks).run(
        definition, RunContext(store=SqliteStore()), _json_runtime({"score": 0.9, "text": "ok"})
    )
    candidate = await Benchmark(rubric, tasks).run(
        definition, RunContext(store=SqliteStore()), _json_runtime({"score": 0.4, "text": ""})
    )

    deltas = compare(baseline, candidate)
    assert deltas[output_number(field="score").name] < 0  # candidate scored lower
    assert is_regression(baseline, candidate)


def test_no_regression_when_candidate_improves_or_holds() -> None:
    baseline = {"score": 0.5, "present": 1.0}
    better = {"score": 0.9, "present": 1.0}
    assert not is_regression(baseline, better)
    assert is_regression(baseline, {"score": 0.49, "present": 1.0})
    # tolerance absorbs small noise
    assert not is_regression(baseline, {"score": 0.49, "present": 1.0}, tolerance=0.05)


def test_compare_handles_unaligned_vectors() -> None:
    deltas = compare({"a": 1.0}, {"b": 2.0})
    assert deltas == {"a": -1.0, "b": 2.0}


# -- CRA-175: typed structured-output & semantic-diff scoring ----------------
from crawfish.core.types import Parameter  # noqa: E402
from crawfish.metrics import (  # noqa: E402
    field_exact_match,
    numeric_tolerance,
    schema_conformance,
    set_overlap,
    structural_match,
)


def test_field_exact_match_reads_typed_value_canonically() -> None:
    m = field_exact_match({"a": 1, "b": 2}, field="obj")
    assert m.evaluate(_out({"obj": {"b": 2, "a": 1}})) == 1.0  # key order ignored
    assert m.evaluate(_out({"obj": {"a": 1, "b": 3}})) == 0.0
    assert field_exact_match("bug", field="cls").evaluate(_out({"cls": "bug"})) == 1.0
    assert field_exact_match([1, 2, 3]).evaluate(_out([1, 2, 3])) == 1.0


def test_set_overlap_f1_and_jaccard_order_free() -> None:
    f1 = set_overlap(["a", "b", "c"], field="labels")
    assert f1.evaluate(_out({"labels": ["c", "b", "a"]})) == 1.0  # order ignored
    assert abs(f1.evaluate(_out({"labels": ["a", "b", "x"]})) - 2 / 3) < 1e-9
    jac = set_overlap(["a", "b"], field="labels", mode="jaccard")
    assert jac.evaluate(_out({"labels": ["a", "c"]})) == 1 / 3  # |∩|=1 |∪|=3
    assert set_overlap([], field="labels").evaluate(_out({"labels": []})) == 1.0


def test_numeric_tolerance_absolute_and_relative() -> None:
    assert numeric_tolerance(10.0, field="n", tol=0.5).evaluate(_out({"n": 10.4})) == 1.0
    assert numeric_tolerance(10.0, field="n", tol=0.5).evaluate(_out({"n": 11.0})) == 0.0
    rel = numeric_tolerance(100.0, field="n", tol=0.05, relative=True)
    assert rel.evaluate(_out({"n": 104.0})) == 1.0  # within 5%
    assert rel.evaluate(_out({"n": 120.0})) == 0.0
    assert numeric_tolerance(1.0, field="n").evaluate(_out({"n": "x"})) == 0.0


def test_schema_conformance_scores_partial_records() -> None:
    # SchemaConformance validates against the default registry; register the record there.
    from crawfish.typesystem import default_registry

    default_registry.register_record("Triage", {"cls": "str", "score": "float"})
    schema = [Parameter(name="out", type="Triage")]
    full = Output(output_schema=[], value='{"cls": "bug", "score": 0.9}', produced_by="r")
    assert schema_conformance(schema).evaluate(full) == 1.0
    half = Output(output_schema=[], value='{"cls": "bug"}', produced_by="r")
    assert schema_conformance(schema).evaluate(half) == 0.5  # 1 of 2 fields missing
    junk = Output(output_schema=[], value="not json at all", produced_by="r")
    assert schema_conformance(schema).evaluate(junk) == 0.0


def test_structural_match_partial_credit() -> None:
    m = structural_match({"a": 1, "b": 2, "c": 3})
    assert m.evaluate(_out({"a": 1, "b": 2, "c": 3})) == 1.0
    assert abs(m.evaluate(_out({"a": 1, "b": 2, "c": 9})) - 2 / 3) < 1e-9  # 1 of 3 leaves


def test_structured_scoring_guards_multiple_json_objects() -> None:
    # CRA-172 follow-up: a string emitting TWO objects must NOT silently score the first.
    two = Output(output_schema=[], value='{"cls": "bug"}\n{"cls": "feature"}', produced_by="r")
    assert field_exact_match("bug", field="cls").evaluate(two) == 0.0  # opaque, no false match
    one = Output(output_schema=[], value='{"cls": "bug"}', produced_by="r")
    assert field_exact_match("bug", field="cls").evaluate(one) == 1.0
