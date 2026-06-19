"""CRA-119 acceptance: snapshots, fixture runner, replay, eval-as-test."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from crawfish.definition import Definition
from crawfish.metrics import Rubric, field_present, is_nonempty
from crawfish.output import Output
from crawfish.runtime import MockRuntime
from crawfish.runtime.base import RunRequest
from crawfish.testing import (
    FixtureResult,
    RubricThresholdError,
    SnapshotMismatch,
    assert_rubric,
    assert_snapshot,
    run_fixtures,
    snapshot_match,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _minimal(tmp_path: Path) -> Definition:
    dest = tmp_path / "minimal"
    shutil.copytree(FIXTURES / "minimal", dest, dirs_exist_ok=True)
    return Definition.from_package(str(dest))


def _json_runtime(payload: dict[str, object]) -> MockRuntime:
    def responder(_request: RunRequest) -> str:
        return json.dumps(payload)

    return MockRuntime(responder)


def _out(value: object) -> Output[object]:
    return Output(output_schema=[], value=value, produced_by="r")


# -- snapshot testing -------------------------------------------------------
def test_snapshot_writes_then_matches(tmp_path: Path) -> None:
    snap = tmp_path / "snap.json"
    value = {"summary": "ok", "score": 0.9}
    # first call: missing -> writes and reports True
    assert snapshot_match(snap, value) is True
    assert snap.exists()
    # second call: identical value -> matches
    assert snapshot_match(snap, value) is True


def test_snapshot_changed_value_fails(tmp_path: Path) -> None:
    snap = tmp_path / "snap.json"
    snapshot_match(snap, {"summary": "ok"})
    assert snapshot_match(snap, {"summary": "changed"}) is False


def test_snapshot_update_rewrites(tmp_path: Path) -> None:
    snap = tmp_path / "snap.json"
    snapshot_match(snap, {"summary": "ok"})
    # update=True accepts the new baseline and returns True
    assert snapshot_match(snap, {"summary": "new"}, update=True) is True
    # subsequent match against the rewritten baseline succeeds
    assert snapshot_match(snap, {"summary": "new"}) is True


def test_assert_snapshot_raises_readable_diff(tmp_path: Path) -> None:
    snap = tmp_path / "snap.json"
    assert_snapshot(snap, {"summary": "ok"})  # writes baseline
    assert_snapshot(snap, {"summary": "ok"})  # matches, no raise
    with pytest.raises(SnapshotMismatch) as excinfo:
        assert_snapshot(snap, {"summary": "regressed"})
    message = str(excinfo.value)
    assert "regressed" in message and "ok" in message


# -- fixture runner ---------------------------------------------------------
def _write_fixture(directory: Path, name: str, spec: dict[str, object]) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{name}.json").write_text(json.dumps(spec))


async def test_run_fixtures_reports_per_fixture(tmp_path: Path) -> None:
    definition = _minimal(tmp_path)
    fixtures_dir = tmp_path / "fixtures"
    payload = {"summary": "done"}
    # one fixture with no expectation (passes if it runs)
    _write_fixture(fixtures_dir, "a_smoke", {"inputs": {"ticket": "hi"}})
    # one fixture whose expectation matches the deterministic mock output
    _write_fixture(
        fixtures_dir, "b_expected", {"inputs": {"ticket": "hi"}, "expected": json.dumps(payload)}
    )
    # one fixture whose expectation does NOT match
    _write_fixture(fixtures_dir, "c_mismatch", {"inputs": {"ticket": "hi"}, "expected": "nope"})

    results = await run_fixtures(fixtures_dir, definition, _json_runtime(payload))

    assert [r.name for r in results] == ["a_smoke", "b_expected", "c_mismatch"]
    assert all(isinstance(r, FixtureResult) for r in results)
    by_name = {r.name: r for r in results}
    assert by_name["a_smoke"].passed is True
    assert by_name["b_expected"].passed is True
    assert by_name["c_mismatch"].passed is False
    assert by_name["c_mismatch"].actual == json.dumps(payload)


async def test_run_fixtures_empty_dir_returns_empty(tmp_path: Path) -> None:
    definition = _minimal(tmp_path)
    fixtures_dir = tmp_path / "empty"
    fixtures_dir.mkdir()
    assert await run_fixtures(fixtures_dir, definition, MockRuntime()) == []


# -- eval-as-test -----------------------------------------------------------
def test_assert_rubric_passes_above_threshold() -> None:
    output = _out({"text": "a real summary"})
    rubric = Rubric([field_present("text"), is_nonempty(field="text")])
    # both metrics score 1.0 here; thresholds are cleared -> no raise
    assert_rubric(
        output,
        rubric,
        {field_present("text").name: 1.0, is_nonempty(field="text").name: 1.0},
    )


def test_assert_rubric_raises_below_threshold() -> None:
    output = _out({"other": "value"})  # `text` absent -> field_present == 0.0
    rubric = Rubric([field_present("text")])
    with pytest.raises(RubricThresholdError) as excinfo:
        assert_rubric(output, rubric, {field_present("text").name: 1.0})
    assert field_present("text").name in str(excinfo.value)


def test_assert_rubric_flags_unknown_metric() -> None:
    output = _out({"text": "ok"})
    rubric = Rubric([field_present("text")])
    with pytest.raises(RubricThresholdError):
        assert_rubric(output, rubric, {"nonexistent_metric": 0.5})
