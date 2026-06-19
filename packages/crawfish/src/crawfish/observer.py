"""The Observer primitive — watch a running pipeline (CRA-153).

An :class:`Observer` polls a pipeline's run-info/event stream on a cron interval and
emits structured :class:`~crawfish.observe.ObserverEvent`s. It is either:

* **rule-based** — cheap, deterministic checks over recent runs (failure rate, cost
  spike, stuck run); or
* **LLM-driven** — a Definition-backed *judge* that reads recent runs as **data** and
  reports run quality in natural language.

The judge runs under the same guardrails as any Definition: the run data it inspects
is passed as **fluid inputs** (data, never instructions — the prompt-injection
boundary), and its spend is bounded by a per-evaluation :class:`CostBudget` so an
observer can never run away with cost. Findings emit through the run-info surface, so
``craw visualize`` / ``craw manage`` / alerting all see them.

Example::

    Observer(
        watch="triage-bot",
        poll=Cron("*/5 * * * *"),
        rules=[FailureRateAbove(0.2), CostSpike(2.0)],
        judge=Definition.from_package("observers/quality"),  # optional LLM observer
    )
"""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from crawfish.core.context import CostBudget, RunContext
from crawfish.observe import ObserverEvent, ObserverSurface, RunInfo, Severity, parse_since
from crawfish.triggers import CronSchedule

if TYPE_CHECKING:
    from crawfish.definition.types import Definition
    from crawfish.runtime import AgentRuntime
    from crawfish.store.base import Store

__all__ = [
    "ObserverContext",
    "Rule",
    "FailureRateAbove",
    "CostSpike",
    "StuckRun",
    "Observer",
]

_DEFAULT_LOOKBACK = "-24h"
_JUDGE_OK = {"", "ok", "pass", "none", "fine", "good"}


@dataclass
class ObserverContext:
    """The window a rule judges: recent runs + events for one pipeline at ``now``."""

    pipeline: str
    runs: list[RunInfo]
    events: list[ObserverEvent]
    now: datetime

    def runs_since(self, window: str) -> list[RunInfo]:
        threshold = parse_since(window, now=self.now.timestamp())
        return [r for r in self.runs if r.started_at >= threshold]


class Rule(ABC):
    """A cheap, deterministic check over recent runs. Returns an event or ``None``."""

    kind: str

    @abstractmethod
    def evaluate(self, octx: ObserverContext) -> ObserverEvent | None: ...


class FailureRateAbove(Rule):
    """Fire when the fraction of failed runs in ``window`` exceeds ``threshold``."""

    kind = "failure.rate"

    def __init__(self, threshold: float, *, window: str = "-1h") -> None:
        self.threshold = threshold
        self.window = window

    def evaluate(self, octx: ObserverContext) -> ObserverEvent | None:
        runs = [r for r in octx.runs_since(self.window) if r.finished_at is not None]
        if not runs:
            return None
        failed = sum(1 for r in runs if r.status == "failed")
        rate = failed / len(runs)
        if rate <= self.threshold:
            return None
        return ObserverEvent(
            pipeline=octx.pipeline,
            kind=self.kind,
            severity=Severity.CRITICAL,
            detail=f"{failed}/{len(runs)} runs failed ({rate:.0%} > {self.threshold:.0%})",
            observer="rule:failure_rate",
            data={"rate": rate, "failed": failed, "total": len(runs)},
            ts=octx.now.timestamp(),
        )


class CostSpike(Rule):
    """Fire when total spend across runs in ``window`` reaches ``usd``."""

    kind = "cost.spike"

    def __init__(self, usd: float, *, window: str = "-5m") -> None:
        self.usd = usd
        self.window = window

    def evaluate(self, octx: ObserverContext) -> ObserverEvent | None:
        runs = octx.runs_since(self.window)
        spent = sum(r.cost_usd for r in runs)
        if spent < self.usd:
            return None
        return ObserverEvent(
            pipeline=octx.pipeline,
            kind=self.kind,
            severity=Severity.WARN,
            detail=f"${spent:.2f} spent in {self.window.lstrip('-')} (≥ ${self.usd:.2f})",
            observer="rule:cost_spike",
            data={"spent_usd": spent, "threshold_usd": self.usd},
            ts=octx.now.timestamp(),
        )


class StuckRun(Rule):
    """Fire when a run has been ``running`` for longer than ``seconds``."""

    kind = "run.stuck"

    def __init__(self, seconds: float) -> None:
        self.seconds = seconds

    def evaluate(self, octx: ObserverContext) -> ObserverEvent | None:
        now = octx.now.timestamp()
        stuck = [
            r
            for r in octx.runs
            if r.status == "running"
            and r.finished_at is None
            and (now - r.started_at) > self.seconds
        ]
        if not stuck:
            return None
        worst = max(stuck, key=lambda r: now - r.started_at)
        age = now - worst.started_at
        return ObserverEvent(
            pipeline=octx.pipeline,
            kind=self.kind,
            severity=Severity.CRITICAL,
            detail=f"run {worst.run_id} stuck {age:.0f}s (> {self.seconds:.0f}s)",
            observer="rule:stuck_run",
            data={"run_id": worst.run_id, "age_s": age},
            ts=octx.now.timestamp(),
        )


JudgeFlagFn = Callable[[str], bool]


def _default_judge_flag(text: str) -> bool:
    """A finding is flagged unless the judge clearly signalled 'all good'."""
    return text.strip().lower() not in _JUDGE_OK


class Observer:
    """Watch one pipeline: run rules (and an optional LLM judge) on a poll interval."""

    def __init__(
        self,
        watch: str,
        *,
        poll: str | CronSchedule | None = None,
        rules: Sequence[Rule] = (),
        judge: Definition | None = None,
        judge_runtime: AgentRuntime | None = None,
        judge_cost_cap_usd: float = 0.50,
        judge_flag: JudgeFlagFn = _default_judge_flag,
        org_id: str = "local",
        lookback: str = _DEFAULT_LOOKBACK,
    ) -> None:
        self.watch = watch
        self.poll = CronSchedule(poll) if isinstance(poll, str) else poll
        self.rules = list(rules)
        self.judge = judge
        self.judge_runtime = judge_runtime
        self.judge_cost_cap_usd = judge_cost_cap_usd
        self.judge_flag = judge_flag
        self.org_id = org_id
        self.lookback = lookback

    def poll_due(self, now: datetime) -> bool:
        """Whether the poll schedule fires at ``now`` (always, if no schedule)."""
        return True if self.poll is None else self.poll.matches(now)

    def _context(self, store: Store, now: datetime) -> ObserverContext:
        surface = ObserverSurface(store, org_id=self.org_id)
        return ObserverContext(
            pipeline=self.watch,
            runs=surface.run_info(self.watch, since=self.lookback, now=now.timestamp()),
            events=surface.events(self.watch, since=self.lookback, now=now.timestamp()),
            now=now,
        )

    def evaluate(
        self, store: Store, *, now: datetime | None = None, run_judge: bool = True
    ) -> list[ObserverEvent]:
        """Run every rule (and the judge, if configured) once; emit + return findings."""
        now = now or datetime.now(UTC)
        surface = ObserverSurface(store, org_id=self.org_id)
        octx = self._context(store, now)
        emitted: list[ObserverEvent] = []
        for rule in self.rules:
            event = rule.evaluate(octx)
            if event is not None:
                surface.emit(event)
                emitted.append(event)
        if run_judge and self.judge is not None:
            judged = self._judge(store, octx)
            if judged is not None:
                surface.emit(judged)
                emitted.append(judged)
        return emitted

    def _judge(self, store: Store, octx: ObserverContext) -> ObserverEvent | None:
        """Run the LLM judge over recent runs under a hard cost cap (the data is data)."""
        judge, runtime = self.judge, self.judge_runtime
        if judge is None or runtime is None:
            return None
        from crawfish.runtime import run_team

        summary = self._summarize(octx.runs)
        # recent-run summary is passed as *fluid inputs* (data, never instructions)
        inputs: dict[str, object] = {p.name: summary for p in judge.inputs} or {"runs": summary}
        ctx = RunContext(
            store=store,
            org_id=self.org_id,
            cost_budget=CostBudget(limit_usd=self.judge_cost_cap_usd),
        )

        async def _go() -> str:
            result = await run_team(judge, inputs, ctx, runtime)
            return result.text

        text = asyncio.run(_go())
        flagged = self.judge_flag(text)
        return ObserverEvent(
            pipeline=octx.pipeline,
            kind="quality.low" if flagged else "quality.ok",
            severity=Severity.WARN if flagged else Severity.INFO,
            detail=text.strip()[:300],
            observer="judge",
            data={"cost_usd": ctx.cost_budget.spent_usd},
            ts=octx.now.timestamp(),
        )

    @staticmethod
    def _summarize(runs: list[RunInfo]) -> str:
        if not runs:
            return "no recent runs"
        done = sum(1 for r in runs if r.status == "done")
        failed = sum(1 for r in runs if r.status == "failed")
        cost = sum(r.cost_usd for r in runs)
        lines = [f"{len(runs)} recent runs: {done} done, {failed} failed, ${cost:.2f} total"]
        for r in runs[:10]:
            lines.append(f"- {r.run_id}: {r.status} (${r.cost_usd:.2f})")
        return "\n".join(lines)

    def watch_loop(
        self,
        store: Store,
        *,
        max_polls: int | None = None,
        now_fn: Callable[[], datetime] | None = None,
        sleep_fn: Callable[[float], None] | None = None,
        stop_flag: Callable[[], bool] | None = None,
    ) -> int:
        """Block, evaluating on each poll tick. Returns the number of evaluations."""
        import time as _time

        now_fn = now_fn or (lambda: datetime.now(UTC))
        sleep_fn = sleep_fn or _time.sleep
        stop_flag = stop_flag or (lambda: False)
        polls = 0
        while not stop_flag():
            if max_polls is not None and polls >= max_polls:
                break
            now = now_fn()
            if self.poll_due(now):
                self.evaluate(store, now=now)
                polls += 1
            if self.poll is None:
                sleep_fn(60.0)
            else:
                sleep_fn(max(1.0, (self.poll.next_after(now) - now).total_seconds()))
        return polls
