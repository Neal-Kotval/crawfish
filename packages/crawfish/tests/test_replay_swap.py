"""CRA-230 / R3 acceptance: ``craw replay --swap`` counterfactual time-travel.

Re-run a recorded run with one model swapped: unaffected leaves replay bit-for-bit at
$0, only the dirtied leaves differ, the cascade is cost-bounded, and the counterfactual
is shown vs. the original. All deterministic — NO live model calls (the counterfactual
is sourced from an alternate cassette dir or a deterministic re-stamp).
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from crawfish.core.context import RunContext
from crawfish.definition import Definition
from crawfish.replay_swap import SwapSpec, parse_swap, plan_swap, run_swap
from crawfish.runtime import MockRuntime, RecordReplayRuntime, RunRequest
from crawfish.runtime.base import EventKind, RunResult, RuntimeEvent
from crawfish.store import SqliteStore

FIXTURES = Path(__file__).parent / "fixtures"


def _definition(tmp_path: Path) -> Definition:
    dest = tmp_path / "full"
    shutil.copytree(FIXTURES / "full", dest)
    return Definition.from_package(str(dest))


def _write_cassette(cdir: Path, key: str, *, model: str, text: str) -> None:
    """Write a minimal recorded RunResult cassette keyed by ``key``."""
    cdir.mkdir(parents=True, exist_ok=True)
    res = RunResult(
        text=text,
        model=model,
        events=[RuntimeEvent(kind=EventKind.RESULT, text=text)],
    )
    (cdir / f"{key}.json").write_text(res.model_dump_json(indent=2))


# --- parse ---------------------------------------------------------------------------


def test_parse_swap_roundtrip() -> None:
    assert parse_swap("a=b") == SwapSpec(frm="a", to="b")
    assert parse_swap(" claude-haiku-4-5 = claude-opus-4-8 ") == SwapSpec(
        frm="claude-haiku-4-5", to="claude-opus-4-8"
    )


def test_parse_swap_rejects_malformed() -> None:
    for bad in ("", "a=", "=b", "noequals"):
        try:
            parse_swap(bad)
        except ValueError:
            continue
        raise AssertionError(f"expected ValueError for {bad!r}")


# --- change detection ----------------------------------------------------------------


def test_plan_swap_dirties_only_matching_model(tmp_path: Path) -> None:
    cdir = tmp_path / "run"
    _write_cassette(cdir, "leaf0", model="haiku", text="a")
    _write_cassette(cdir, "leaf1", model="haiku", text="b")
    _write_cassette(cdir, "leaf2", model="sonnet", text="c")

    cassettes, dirtied = plan_swap(cdir, SwapSpec("haiku", "opus"))
    assert len(cassettes) == 3
    assert sorted(dirtied) == ["leaf0", "leaf1"]


# --- determinism: clean leaves replay bit-for-bit; only dirtied differ ----------------


def test_clean_leaves_replay_bit_for_bit(tmp_path: Path) -> None:
    cdir = tmp_path / "run"
    _write_cassette(cdir, "leaf0", model="haiku", text="dirty-orig")
    _write_cassette(cdir, "leaf1", model="sonnet", text="clean")

    altdir = tmp_path / "alt"
    _write_cassette(altdir, "leaf0", model="opus", text="dirty-counterfactual")

    report = run_swap(cdir, SwapSpec("haiku", "opus"), alt_cassette_dir=altdir)
    assert report.total_leaves == 2
    assert report.dirtied_leaves == 1

    by_key = {d.key: d for d in report.deltas}
    # Clean leaf: counterfactual == original, byte-for-byte.
    clean = by_key["leaf1"]
    assert not clean.dirtied
    assert clean.counterfactual_text == clean.original_text == "clean"
    assert clean.counterfactual_model == clean.original_model == "sonnet"
    # Dirtied leaf: swapped to the alternate cassette's result.
    dirty = by_key["leaf0"]
    assert dirty.dirtied
    assert dirty.original_text == "dirty-orig"
    assert dirty.counterfactual_text == "dirty-counterfactual"
    assert dirty.counterfactual_model == "opus"
    assert report.changed


def test_swap_is_deterministic(tmp_path: Path) -> None:
    cdir = tmp_path / "run"
    _write_cassette(cdir, "leaf0", model="haiku", text="x")
    altdir = tmp_path / "alt"
    _write_cassette(altdir, "leaf0", model="opus", text="y")
    a = run_swap(cdir, SwapSpec("haiku", "opus"), alt_cassette_dir=altdir)
    b = run_swap(cdir, SwapSpec("haiku", "opus"), alt_cassette_dir=altdir)
    assert a.summary() == b.summary()


# --- no alternate cassette ⇒ deterministic re-stamp placeholder, charged --------------


def test_missing_alt_restamps_and_charges(tmp_path: Path) -> None:
    cdir = tmp_path / "run"
    _write_cassette(cdir, "leaf0", model="haiku", text="orig")
    report = run_swap(cdir, SwapSpec("haiku", "opus"), live_cost_usd=0.01)
    d = report.deltas[0]
    assert d.dirtied
    assert d.counterfactual_model == "opus"
    assert d.cost_usd == 0.01
    assert report.spent_usd == 0.01


# --- cost bound: an over-budget cascade is refused before spending --------------------


def test_over_budget_cascade_is_refused(tmp_path: Path) -> None:
    cdir = tmp_path / "run"
    for i in range(5):
        _write_cassette(cdir, f"leaf{i}", model="haiku", text=str(i))
    # 5 dirtied leaves * $0.10 = $0.50 projected > $0.20 budget ⇒ refused, no spend.
    report = run_swap(cdir, SwapSpec("haiku", "opus"), budget_usd=0.20, live_cost_usd=0.10)
    assert report.over_budget
    assert report.spent_usd == 0.0
    assert report.deltas == ()
    assert "REFUSED" in report.summary()


# --- integration: a real recorded run via RecordReplayRuntime, then swap --------------


async def test_recorded_run_then_swap(tmp_path: Path) -> None:
    """Record real leaves via RecordReplayRuntime, then swap the recorded model.

    The swap keys off the *recorded* ``RunResult.model`` (what the backend actually
    served), which is the F-1 cassette's source of truth — here ``MockRuntime`` records
    ``model="mock"`` for every leaf, so swapping ``mock=>opus`` dirties them all, and the
    counterfactual re-stamps each to ``opus`` deterministically with NO live call."""
    d = _definition(tmp_path)
    ctx = RunContext(store=SqliteStore())
    cdir = tmp_path / "cassettes"

    rec = RecordReplayRuntime(MockRuntime(lambda r: f"out:{r.inputs}"), cdir, record=True)
    await rec.run(RunRequest(definition=d, role="lead", inputs={"pr_body": "x"}), ctx)
    await rec.run(RunRequest(definition=d, role="lead", inputs={"pr_body": "y"}), ctx)

    cassettes, dirtied = plan_swap(cdir, SwapSpec("mock", "opus"))
    assert len(cassettes) == 2
    assert len(dirtied) == 2  # both leaves were served by the `mock` backend

    report = run_swap(cdir, SwapSpec("mock", "opus"), live_cost_usd=0.0)
    assert report.dirtied_leaves == 2
    # Every dirtied leaf is re-stamped to the `to` model; original text is preserved.
    assert all(x.counterfactual_model == "opus" for x in report.deltas)
    # A model the run never used dirties nothing (cost-bound stays at zero).
    _, none_dirty = plan_swap(cdir, SwapSpec("nonexistent", "opus"))
    assert none_dirty == []


# --- CLI integration -----------------------------------------------------------------


def test_cli_replay_swap_json(tmp_path: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    from crawfish.cli import main

    cdir = tmp_path / "run"
    _write_cassette(cdir, "leaf0", model="haiku", text="orig")
    _write_cassette(cdir, "leaf1", model="sonnet", text="keep")
    altdir = tmp_path / "alt"
    _write_cassette(altdir, "leaf0", model="opus", text="cf")

    code = main(
        [
            "replay",
            "--cassettes",
            str(cdir),
            "--swap",
            "haiku=opus",
            "--alt-cassettes",
            str(altdir),
            "--json",
        ]
    )
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["schema"].startswith("craw.replay.v")
    assert payload["dirtied_leaves"] == 1
    assert payload["total_leaves"] == 2
    assert payload["changed"] is True


def test_cli_replay_over_budget_exits_nonzero(tmp_path: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    from crawfish.cli import main

    cdir = tmp_path / "run"
    for i in range(3):
        _write_cassette(cdir, f"leaf{i}", model="haiku", text=str(i))
    code = main(
        [
            "replay",
            "--cassettes",
            str(cdir),
            "--swap",
            "haiku=opus",
            "--budget",
            "0.01",
            "--cost-per-leaf",
            "0.10",
        ]
    )
    assert code == 1
    assert "REFUSED" in capsys.readouterr().out
