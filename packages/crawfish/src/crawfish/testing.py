"""Testing harness — fixtures, snapshots, replay, eval-as-test.

Make Definitions and pipelines *testable* so people trust and ship them. The
pieces here are the library a ``craw test`` command drives:

* **Snapshot testing** — :func:`snapshot_match` / :func:`assert_snapshot` pin a
  JSON-serializable value to a file; an output regression fails the diff.
* **Fixture runner** — :func:`run_fixtures` loads ``{inputs, [expected]}`` JSON
  files and executes the Definition once per fixture, reporting pass/fail.
* **Deterministic record/replay** — :func:`replaying` wraps a runtime in a
  :class:`~crawfish.runtime.replay.RecordReplayRuntime` so CI never makes a live
  model call (replay a cassette, or record once with ``record=True``).
* **Eval-as-test** — :func:`assert_rubric` turns a :class:`~crawfish.metrics.Rubric`
  threshold into a CI assertion (score below threshold -> ``AssertionError``).

Everything stays deterministic: pair with
:class:`~crawfish.runtime.mock.MockRuntime` or a recorded cassette and no model
call is ever made.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from crawfish.core.context import RunContext
from crawfish.core.types import JSONValue
from crawfish.definition.types import Definition
from crawfish.metrics import Rubric
from crawfish.output import Output
from crawfish.run import Run
from crawfish.runtime.base import AgentRuntime
from crawfish.runtime.replay import RecordReplayRuntime
from crawfish.store.sqlite import SqliteStore

__all__ = [
    "snapshot_match",
    "assert_snapshot",
    "SnapshotMismatch",
    "FixtureResult",
    "run_fixtures",
    "replaying",
    "assert_rubric",
    "RubricThresholdError",
]


# -- snapshot testing -------------------------------------------------------
class SnapshotMismatch(AssertionError):
    """Raised by :func:`assert_snapshot` when a value diverges from its snapshot."""


def _canonical(value: JSONValue) -> str:
    """Stable JSON text for snapshot comparison (sorted keys, indented)."""
    return json.dumps(value, sort_keys=True, indent=2, default=str)


def snapshot_match(path: str | Path, value: JSONValue, *, update: bool = False) -> bool:
    """Compare ``value`` against the snapshot at ``path``.

    Writes the snapshot and returns ``True`` when it is missing or ``update`` is
    set (the accept-new-baseline path). Otherwise returns ``True`` on a match and
    ``False`` on a diff — the caller decides how to surface a regression.
    """
    snapshot_path = Path(path)
    serialized = _canonical(value)
    if update or not snapshot_path.exists():
        snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        snapshot_path.write_text(serialized + "\n")
        return True
    return snapshot_path.read_text().rstrip("\n") == serialized


def assert_snapshot(path: str | Path, value: JSONValue, *, update: bool = False) -> None:
    """Like :func:`snapshot_match` but raise :class:`SnapshotMismatch` on a diff.

    The error carries a readable line-by-line diff (expected snapshot vs actual).
    """
    if snapshot_match(path, value, update=update):
        return
    import difflib

    expected = Path(path).read_text().rstrip("\n").splitlines()
    actual = _canonical(value).splitlines()
    diff = "\n".join(
        difflib.unified_diff(expected, actual, fromfile="snapshot", tofile="actual", lineterm="")
    )
    raise SnapshotMismatch(f"snapshot mismatch for {path}:\n{diff}")


# -- fixture runner ---------------------------------------------------------
@dataclass
class FixtureResult:
    """The outcome of running one fixture through a Definition."""

    name: str
    passed: bool
    inputs: dict[str, JSONValue] = field(default_factory=dict)
    expected: JSONValue | None = None
    actual: JSONValue | None = None
    error: str | None = None


def _new_ctx() -> RunContext:
    """A throwaway, in-memory RunContext for a single fixture run."""
    return RunContext(store=SqliteStore())


async def run_fixtures(
    fixtures_dir: str | Path,
    definition: Definition,
    runtime: AgentRuntime,
    *,
    ctx_factory: Callable[[], RunContext] | None = None,
) -> list[FixtureResult]:
    """Run every ``*.json`` fixture in ``fixtures_dir`` against ``definition``.

    Each fixture is ``{"inputs": {...}, "expected": <optional>}``. The Definition
    runs once per fixture (via :class:`~crawfish.run.Run`); a fixture passes when
    it executes cleanly and — if ``expected`` is given — the Output value matches.
    Fixtures are processed in sorted filename order for stable reporting.

    ``ctx_factory`` is an optional zero-arg callable returning a fresh
    :class:`~crawfish.core.context.RunContext` per fixture (defaults to an
    in-memory SQLite-backed context).
    """
    make_ctx = ctx_factory if ctx_factory is not None else _new_ctx
    results: list[FixtureResult] = []
    for fixture_path in sorted(Path(fixtures_dir).glob("*.json")):  # noqa: ASYNC240
        name = fixture_path.stem
        try:
            spec = json.loads(fixture_path.read_text())
        except (ValueError, OSError) as exc:
            results.append(FixtureResult(name=name, passed=False, error=f"load failed: {exc}"))
            continue

        inputs: dict[str, JSONValue] = dict(spec.get("inputs", {}))
        has_expected = "expected" in spec
        expected: JSONValue | None = spec.get("expected")

        try:
            ctx = make_ctx()
            run = Run(definition, inputs, runtime=runtime)
            output = await run.execute(ctx, runtime)
        except Exception as exc:  # noqa: BLE001 — report any failure as a fixture failure
            results.append(
                FixtureResult(
                    name=name,
                    passed=False,
                    inputs=inputs,
                    expected=expected if has_expected else None,
                    error=str(exc),
                )
            )
            continue

        actual: JSONValue = output.value
        passed = (not has_expected) or actual == expected
        results.append(
            FixtureResult(
                name=name,
                passed=passed,
                inputs=inputs,
                expected=expected if has_expected else None,
                actual=actual,
            )
        )
    return results


# -- deterministic record/replay -------------------------------------------
def replaying(
    inner_runtime: AgentRuntime,
    cassette_dir: str | Path,
    *,
    record: bool = False,
) -> RecordReplayRuntime:
    """Wrap ``inner_runtime`` so tests replay cassettes instead of calling live.

    With ``record=False`` (the CI default) a cache miss raises
    :class:`~crawfish.runtime.replay.CassetteMiss`, guaranteeing no live model
    call. Set ``record=True`` once to capture cassettes from ``inner_runtime``.
    """
    return RecordReplayRuntime(inner_runtime, cassette_dir, record=record)


# -- eval-as-test -----------------------------------------------------------
class RubricThresholdError(AssertionError):
    """Raised when a rubric metric scores below its CI threshold."""


def assert_rubric(
    output: Output[JSONValue],
    rubric: Rubric,
    thresholds: dict[str, float],
) -> None:
    """Score ``output`` and assert each thresholded metric clears its floor.

    A :class:`~crawfish.metrics.Rubric` threshold becomes a CI assertion: keys in
    ``thresholds`` name metrics (by ``Metric.name``) that must score ``>=`` their
    value. Raise :class:`RubricThresholdError` listing every metric that fell
    short (or a threshold naming a metric absent from the rubric).
    """
    scores = rubric.score(output)
    failures: list[str] = []
    for name, floor in thresholds.items():
        if name not in scores:
            failures.append(f"{name}: not in rubric (have {sorted(scores)})")
            continue
        actual = scores[name]
        if actual < floor:
            failures.append(f"{name}: {actual:.4f} < {floor:.4f}")
    if failures:
        raise RubricThresholdError("rubric thresholds not met:\n  " + "\n  ".join(failures))
