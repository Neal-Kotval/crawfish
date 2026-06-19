"""Eval data lifecycle — cases, labeling, golden sets, LLM-judge (CRA-139).

The other half of the quality loop: CRA-110 ships the scoring *types*
(Metric/Rubric/Benchmark); this ships the eval *data* lifecycle that lets the
"metrics correlate with quality" bet be validated. Capture real runs as reusable
eval cases, attach human labels, curate versioned golden sets, grade with an
LLM-as-judge (complementing coded Metrics), and gate a new Definition version
against a stored regression baseline.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, Field

from crawfish.core.context import RunContext
from crawfish.core.ids import new_id
from crawfish.core.types import JSONValue
from crawfish.definition.types import Definition
from crawfish.metrics import Rubric, is_regression
from crawfish.output import Output
from crawfish.runtime.base import AgentRuntime
from crawfish.runtime.team import run_team
from crawfish.store.base import Store

__all__ = [
    "EvalCase",
    "GoldenSet",
    "LLMJudge",
    "capture_case",
    "grade_output",
    "save_baseline",
    "load_baseline",
    "gate_against_baseline",
]


class EvalCase(BaseModel):
    """A captured run made reusable: its inputs, the produced output, and an
    optional human label (expected output / judgment)."""

    id: str = Field(default_factory=new_id)
    inputs: dict[str, JSONValue] = Field(default_factory=dict)
    output: JSONValue = None
    produced_by: str | None = None
    transcript: list[JSONValue] = Field(default_factory=list)
    label: JSONValue = None  # human judgment / expected output
    metadata: dict[str, JSONValue] = Field(default_factory=dict)


def capture_case(
    *,
    inputs: dict[str, JSONValue],
    output: Output[JSONValue],
    transcript: list[JSONValue] | None = None,
    label: JSONValue = None,
) -> EvalCase:
    """Capture a real run (inputs + output [+ transcript]) as an eval case."""
    return EvalCase(
        inputs=dict(inputs),
        output=output.value,
        produced_by=output.produced_by,
        transcript=list(transcript or []),
        label=label,
    )


class GoldenSet:
    """A named, versioned set of labeled cases, persisted through the ``Store``."""

    def __init__(
        self, store: Store, name: str, *, org_id: str = "local", version: str = "0.1"
    ) -> None:
        self._store = store
        self.name = name
        self.version = version
        self._org = org_id

    @property
    def _kind(self) -> str:
        return f"golden:{self.name}@{self.version}"

    def add(self, case: EvalCase) -> None:
        self._store.put_record(self._kind, case.id, case.model_dump(mode="json"), org_id=self._org)

    def label(self, case_id: str, label: JSONValue) -> None:
        rec = self._store.get_record(self._kind, case_id, org_id=self._org)
        if rec is None:
            raise KeyError(f"no case {case_id!r} in golden set {self.name!r}")
        rec["label"] = label
        self._store.put_record(self._kind, case_id, rec, org_id=self._org)

    def get(self, case_id: str) -> EvalCase | None:
        rec = self._store.get_record(self._kind, case_id, org_id=self._org)
        return None if rec is None else EvalCase.model_validate(rec)

    def cases(self) -> list[EvalCase]:
        return [
            EvalCase.model_validate(r)
            for r in self._store.list_records(self._kind, org_id=self._org)
        ]


_SCORE_RE = re.compile(r"-?\d+(?:\.\d+)?")


def _parse_score(text: str) -> float:
    """Extract a [0,1] score from a judge's free-text verdict (clamped)."""
    m = _SCORE_RE.search(text)
    if not m:
        return 0.0
    return max(0.0, min(1.0, float(m.group())))


class LLMJudge:
    """A Definition-backed grader: an agent scores an output against criteria.

    Complements coded ``Metric``s. Deterministic under a mock/replay runtime.
    """

    def __init__(
        self, definition: Definition, runtime: AgentRuntime, *, name: str = "llm_judge"
    ) -> None:
        self.definition = definition
        self.runtime = runtime
        self.name = name

    async def grade(
        self, output: Output[JSONValue], ctx: RunContext, *, criteria: str = "quality"
    ) -> float:
        # The output value is bound as fluid (untrusted) data for the judge.
        inputs: dict[str, JSONValue] = {"output": output.value, "criteria": criteria}
        result = await run_team(self.definition, inputs, ctx, self.runtime)
        return _parse_score(result.text)


async def grade_output(
    output: Output[JSONValue],
    ctx: RunContext,
    *,
    rubric: Rubric | None = None,
    judges: list[LLMJudge] | None = None,
) -> dict[str, float]:
    """Combine coded-metric scores and LLM-judge grades into one score dict."""
    scores: dict[str, float] = {}
    if rubric is not None:
        scores.update(rubric.score(output))
    for judge in judges or []:
        scores[judge.name] = await judge.grade(output, ctx)
    return scores


# -- regression baselines -----------------------------------------------------
def save_baseline(
    store: Store, name: str, scores: dict[str, float], *, org_id: str = "local"
) -> None:
    store.put_record("eval_baseline", name, dict(scores), org_id=org_id)


def load_baseline(store: Store, name: str, *, org_id: str = "local") -> dict[str, float] | None:
    rec = store.get_record("eval_baseline", name, org_id=org_id)
    return None if rec is None else {k: float(v) for k, v in rec.items()}


def gate_against_baseline(
    store: Store,
    name: str,
    candidate: dict[str, float],
    *,
    tolerance: float = 0.0,
    org_id: str = "local",
) -> bool:
    """True if ``candidate`` passes (no regression vs the stored baseline)."""
    baseline = load_baseline(store, name, org_id=org_id)
    if baseline is None:
        return True  # no baseline yet — nothing to regress against
    return not is_regression(baseline, candidate, tolerance=tolerance)
