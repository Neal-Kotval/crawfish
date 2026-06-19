"""CRA-153 acceptance: the Observer primitive — rule-based + LLM judge.

Deterministic: rules run over seeded RunInfo; the LLM judge uses MockRuntime with a
fixed responder (no live model call). Verifies an event fires on an induced
failure/cost spike and the judge flags a low-quality run with a plain-language reason.
"""

from __future__ import annotations

from datetime import UTC, datetime

from crawfish.definition import AgentSpec, Definition, TeamSpec
from crawfish.observe import ObserverSurface, RunInfo
from crawfish.observer import CostSpike, FailureRateAbove, Observer, StuckRun
from crawfish.runtime import MockRuntime
from crawfish.store import SqliteStore

NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


def _seed(store: SqliteStore, runs: list[RunInfo]) -> None:
    surface = ObserverSurface(store)
    for r in runs:
        surface.put_run_info(r)


def test_failure_rate_rule_fires_on_induced_failures() -> None:
    store = SqliteStore()
    t = NOW.timestamp()
    _seed(
        store,
        [
            RunInfo(
                pipeline="p", run_id="a", status="failed", started_at=t - 10, finished_at=t - 9
            ),
            RunInfo(pipeline="p", run_id="b", status="failed", started_at=t - 8, finished_at=t - 7),
            RunInfo(pipeline="p", run_id="c", status="done", started_at=t - 6, finished_at=t - 5),
        ],
    )
    obs = Observer("p", rules=[FailureRateAbove(0.2)])
    events = obs.evaluate(store, now=NOW)
    assert [e.kind for e in events] == ["failure.rate"]
    assert "failed" in events[0].detail
    # the finding landed on the surface, queryable
    assert ObserverSurface(store).events("p", kind="failure.rate")


def test_cost_spike_rule_fires() -> None:
    store = SqliteStore()
    t = NOW.timestamp()
    _seed(
        store,
        [
            RunInfo(pipeline="p", run_id="a", cost_usd=1.5, started_at=t - 60, finished_at=t - 59),
            RunInfo(pipeline="p", run_id="b", cost_usd=0.8, started_at=t - 30, finished_at=t - 29),
        ],
    )
    obs = Observer("p", rules=[CostSpike(2.0, window="-5m")])
    events = obs.evaluate(store, now=NOW)
    assert events and events[0].kind == "cost.spike"


def test_rules_quiet_when_healthy() -> None:
    store = SqliteStore()
    t = NOW.timestamp()
    _seed(
        store,
        [
            RunInfo(
                pipeline="p",
                run_id="a",
                status="done",
                cost_usd=0.01,
                started_at=t - 5,
                finished_at=t - 4,
            )
        ],
    )
    obs = Observer("p", rules=[FailureRateAbove(0.2), CostSpike(2.0)])
    assert obs.evaluate(store, now=NOW) == []


def test_stuck_run_rule() -> None:
    store = SqliteStore()
    t = NOW.timestamp()
    _seed(store, [RunInfo(pipeline="p", run_id="a", status="running", started_at=t - 600)])
    obs = Observer("p", rules=[StuckRun(seconds=300)])
    events = obs.evaluate(store, now=NOW)
    assert events and events[0].kind == "run.stuck"


def test_llm_judge_flags_low_quality_run() -> None:
    store = SqliteStore()
    t = NOW.timestamp()
    _seed(store, [RunInfo(pipeline="triage-bot", run_id="a", status="done", started_at=t - 5)])
    judge = Definition(
        name="quality", team=TeamSpec(agents=[AgentSpec(role="judge", prompt="Judge")])
    )
    runtime = MockRuntime(responder=lambda _req: "3/10 PRs missed the root cause")
    obs = Observer("triage-bot", judge=judge, judge_runtime=runtime)
    events = obs.evaluate(store, now=NOW)
    assert events and events[0].kind == "quality.low"
    assert "root cause" in events[0].detail
    assert events[0].observer == "judge"


def test_llm_judge_quiet_when_ok() -> None:
    store = SqliteStore()
    t = NOW.timestamp()
    _seed(store, [RunInfo(pipeline="p", run_id="a", status="done", started_at=t - 5)])
    judge = Definition(
        name="quality", team=TeamSpec(agents=[AgentSpec(role="judge", prompt="Judge")])
    )
    runtime = MockRuntime(responder=lambda _req: "ok")
    obs = Observer("p", judge=judge, judge_runtime=runtime)
    events = obs.evaluate(store, now=NOW)
    assert events and events[0].kind == "quality.ok"


def test_judge_runs_under_cost_cap() -> None:
    # the judge's RunContext carries a bounded CostBudget — spend is capped + recorded
    store = SqliteStore()
    _seed(store, [RunInfo(pipeline="p", run_id="a", status="done", started_at=NOW.timestamp())])
    judge = Definition(name="q", team=TeamSpec(agents=[AgentSpec(role="j", prompt="J")]))
    obs = Observer("p", judge=judge, judge_runtime=MockRuntime(), judge_cost_cap_usd=0.25)
    events = obs.evaluate(store, now=NOW)
    assert events and "cost_usd" in events[0].data


def test_rule_boundaries_are_pinned() -> None:
    # FailureRateAbove is strictly-greater: rate == threshold does NOT fire.
    store = SqliteStore()
    t = NOW.timestamp()
    _seed(
        store,
        [
            RunInfo(pipeline="p", run_id="a", status="failed", started_at=t - 4, finished_at=t - 3),
            RunInfo(pipeline="p", run_id="b", status="done", started_at=t - 2, finished_at=t - 1),
        ],
    )  # rate exactly 0.5
    assert Observer("p", rules=[FailureRateAbove(0.5)]).evaluate(store, now=NOW) == []
    assert Observer("p", rules=[FailureRateAbove(0.49)]).evaluate(store, now=NOW)

    # CostSpike is inclusive: spent == threshold DOES fire.
    store2 = SqliteStore()
    ObserverSurface(store2).put_run_info(
        RunInfo(pipeline="p", run_id="a", cost_usd=2.0, started_at=NOW.timestamp() - 1)
    )
    assert Observer("p", rules=[CostSpike(2.0, window="-5m")]).evaluate(store2, now=NOW)


def test_failure_rate_handles_zero_runs() -> None:
    store = SqliteStore()  # no runs at all
    assert Observer("p", rules=[FailureRateAbove(0.2)]).evaluate(store, now=NOW) == []


def test_judge_binds_declared_inputs() -> None:
    # a judge Definition that DECLARES inputs gets the run summary bound to them
    from crawfish.core import Flow, Parameter

    store = SqliteStore()
    _seed(store, [RunInfo(pipeline="p", run_id="a", status="failed", started_at=NOW.timestamp())])
    judge = Definition(
        name="q",
        inputs=[Parameter(name="recent", type="str", flow=Flow.STATIC)],
        team=TeamSpec(agents=[AgentSpec(role="j", prompt="J")]),
    )
    # the declared-inputs branch must bind the run summary without InputBindingError
    obs = Observer("p", judge=judge, judge_runtime=MockRuntime(responder=lambda _r: "looks wrong"))
    events = obs.evaluate(store, now=NOW)
    assert events and events[0].kind == "quality.low"


def test_poll_due_respects_schedule() -> None:
    obs = Observer("p", poll="*/5 * * * *")
    assert obs.poll_due(datetime(2026, 1, 1, 0, 5, tzinfo=UTC)) is True
    assert obs.poll_due(datetime(2026, 1, 1, 0, 6, tzinfo=UTC)) is False


def test_watch_loop_evaluates_each_poll() -> None:
    store = SqliteStore()
    _seed(
        store,
        [
            RunInfo(
                pipeline="p",
                run_id="a",
                status="failed",
                started_at=NOW.timestamp(),
                finished_at=NOW.timestamp(),
            )
        ],
    )
    obs = Observer("p", rules=[FailureRateAbove(0.2)])
    polls = obs.watch_loop(store, max_polls=2, now_fn=lambda: NOW, sleep_fn=lambda _s: None)
    assert polls == 2
