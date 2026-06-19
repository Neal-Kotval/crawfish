"""CRA-150 dogfood integration: deploy → observe → visualize → manage on the demo.

Exercises the whole operate/observe/integrate layer end to end against the real
`demo/triage-bot` Definition and `demo/observers/quality` judge — deterministically
(MockRuntime, injected clock, fake spawner; no live model call, no real daemon).
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path

import pytest

from crawfish.core.context import RunContext
from crawfish.definition import Definition
from crawfish.deploy import DeployRegistry, RunFn, Supervisor, deploy, stop
from crawfish.manage import manage_list
from crawfish.observer import FailureRateAbove, Observer
from crawfish.runtime import MockRuntime, run_team
from crawfish.store import SqliteStore
from crawfish.visualize import dashboard_state

REPO_ROOT = Path(__file__).resolve().parents[3]
DEMO = REPO_ROOT / "demo"
NOW = datetime(2026, 6, 19, 8, 0, tzinfo=UTC)


@pytest.fixture
def triage() -> Definition:
    return Definition.from_package(str(DEMO / "triage-bot"))


def _good_cycle(triage: Definition) -> RunFn:
    """A healthy cycle: run the real triage-bot on the mock runtime + a small charge."""

    def _run(ctx: RunContext) -> None:
        inputs = {"project": "acme", "ticket_body": "login button does nothing"}
        asyncio.run(run_team(triage, inputs, ctx, MockRuntime()))
        ctx.cost_budget.charge(0.04)

    return _run


def _bad_cycle(ctx: RunContext) -> None:
    raise RuntimeError("classifier timed out")


def test_deploy_observe_visualize_manage_end_to_end(triage: Definition) -> None:
    store = SqliteStore()

    # 1. DEPLOY the triage-bot (detached; fake spawn so no real daemon launches).
    entry = deploy(
        DEMO / "triage-bot",
        name="triage-bot",
        store=store,
        schedule="0 8 * * *",
        spawn=lambda _argv, _cwd, _log: 4242,
    )
    assert DeployRegistry(store).get("triage-bot") is not None
    assert "hunter2" not in str(entry.session)  # session name carries no secret

    # 2. The supervisor fires healthy cycles + one induced bad run (auto-restart).
    good = Supervisor("triage-bot", store, _good_cycle(triage), schedule="0 8 * * *")
    for _ in range(3):
        good.run_cycle(now=NOW)
    Supervisor("triage-bot", store, _bad_cycle).run_cycle(now=NOW)  # induced failure

    # 3. OBSERVE: a rule-based observer flags the failure rate...
    rule_obs = Observer("triage-bot", rules=[FailureRateAbove(0.2)])
    rule_events = rule_obs.evaluate(store, now=NOW)
    assert any(e.kind == "failure.rate" for e in rule_events)

    # ...and the LLM/Definition-backed judge flags low quality in plain language.
    judge = Definition.from_package(str(DEMO / "observers" / "quality"))
    judged_runtime = MockRuntime(responder=lambda _r: "1/4 runs failed — classifier timing out")
    llm_obs = Observer("triage-bot", judge=judge, judge_runtime=judged_runtime)
    llm_events = llm_obs.evaluate(store, now=NOW)
    assert any(e.kind == "quality.low" and "classifier" in e.detail for e in llm_events)

    # 4. VISUALIZE: the dashboard feed shows pipelines, runs, cost, observer events.
    state = dashboard_state(store, now=NOW)
    names = [p["name"] for p in state["pipelines"]]  # type: ignore[index]
    assert "triage-bot" in names
    assert len(state["recent_runs"]) == 4  # type: ignore[arg-type]
    statuses = {r["status"] for r in state["recent_runs"]}  # type: ignore[index,union-attr]
    assert statuses == {"done", "failed"}
    assert state["cost_today_usd"] >= 0.12  # 3 × $0.04  # type: ignore[operator]
    kinds = {e["kind"] for e in state["observer_events"]}  # type: ignore[index,union-attr]
    assert {"failure.rate", "quality.low"} <= kinds

    # 5. MANAGE: the deployed pipeline is listed and controllable.
    rows = manage_list(store, now=NOW)
    assert rows[0].name == "triage-bot"
    assert rows[0].last_run_status in {"done", "failed"}
    assert stop("triage-bot", store=store, kill=lambda _pid: None) is True
    assert manage_list(store, now=NOW)[0].status == "stopped"


def test_demo_definition_exports_to_claude_code(triage: Definition, tmp_path: Path) -> None:
    """The Claude Code export of the demo Definition carries instructions, not secrets."""
    from crawfish.ccexport import export_claude_code

    paths = export_claude_code(triage, tmp_path)
    text = paths[0].read_text()
    assert paths[0].name == "triage-bot.md"
    assert "triage" in text.lower()
    assert "GITHUB_TOKEN" not in text and "***REDACTED***" not in text
