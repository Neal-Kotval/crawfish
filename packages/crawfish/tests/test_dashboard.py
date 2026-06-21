"""CRA-181 — the emission auto-dashboard.

The dashboard renders *any* emitted property without bespoke per-metric code: its
state is a pure projection of the typed :class:`Emission` stream. These tests build
state from a synthetic stream (multiple kinds + a tainted emission), assert that an
arbitrary new attribute renders generically as a metric series with zero new code,
and assert taint is surfaced. No socket is bound and no clock is read in the pure
state builder — determinism by construction.
"""

from __future__ import annotations

from crawfish.emission import Emission, EmissionKind
from crawfish.visualize import (
    EMISSION_DASHBOARD_HTML,
    collect_emissions,
    emission_dashboard_state,
    make_emission_handler,
    serve_emission_dashboard,
)


def _stream() -> list[Emission]:
    return [
        Emission(kind=EmissionKind.RUN_START, run_id="r1", ts=1.0, attrs={"runtime": "mock"}),
        Emission(
            kind=EmissionKind.MODEL,
            run_id="r1",
            node_id="agent",
            ts=2.0,
            attrs={"model": "sonnet", "cost_usd": 0.01, "tokens": 1200},
        ),
        Emission(
            kind=EmissionKind.MODEL,
            run_id="r1",
            node_id="agent",
            ts=3.0,
            attrs={"model": "sonnet", "cost_usd": 0.02, "tokens": 800},
        ),
        # An arbitrary, never-before-seen numeric attr ("sharpness") on a METRIC.
        # The dashboard must render it as a series with NO new dashboard code.
        Emission(
            kind=EmissionKind.METRIC,
            run_id="r1",
            ts=4.0,
            attrs={"metric": "quality", "value": 0.9, "sharpness": 42},
        ),
        # A tainted TOOL emission carrying a numeric attr derived from fluid input.
        Emission(
            kind=EmissionKind.TOOL,
            run_id="r2",
            ts=5.0,
            tainted=True,
            attrs={"tool": "web_fetch", "untrusted_score": 7},
        ),
    ]


def test_total_cost_rolls_up_from_model_emissions() -> None:
    state = emission_dashboard_state(_stream())
    # cost is just the model.cost_usd series sum — no bespoke cost branch.
    assert state["total_cost_usd"] == 0.03
    assert state["emission_count"] == 5


def test_arbitrary_new_attr_renders_generically_as_a_metric() -> None:
    state = emission_dashboard_state(_stream())
    metrics = {m["key"]: m for m in state["metrics"]}  # type: ignore[index,union-attr]
    # The novel "sharpness" attr appears as its own series with zero dashboard code.
    assert "metric.sharpness" in metrics
    assert metrics["metric.sharpness"]["sum"] == 42.0
    assert metrics["metric.sharpness"]["last"] == 42.0
    # And the standard numeric attrs aggregate too.
    assert metrics["model.cost_usd"]["sum"] == 0.03
    assert metrics["model.tokens"]["sum"] == 2000.0
    assert metrics["model.cost_usd"]["count"] == 2


def test_kind_buckets_list_union_of_attr_keys() -> None:
    state = emission_dashboard_state(_stream())
    kinds = {k["kind"]: k for k in state["kinds"]}  # type: ignore[index,union-attr]
    assert kinds["model"]["count"] == 2
    # a fresh attr key surfaces in the kind's attr_keys with no new code
    assert "tokens" in kinds["metric"]["attr_keys"] or "sharpness" in kinds["metric"]["attr_keys"]
    assert set(kinds["metric"]["attr_keys"]) == {"metric", "value", "sharpness"}


def test_taint_is_surfaced_in_state() -> None:
    state = emission_dashboard_state(_stream())
    assert state["tainted_count"] == 1

    # the tainted emission's metric contribution is flagged, not laundered as trusted
    metrics = {m["key"]: m for m in state["metrics"]}  # type: ignore[index,union-attr]
    assert metrics["tool.untrusted_score"]["tainted"] is True
    assert metrics["tool.untrusted_score"]["tainted_count"] == 1
    # trusted series are NOT flagged
    assert metrics["model.cost_usd"]["tainted"] is False

    # the tainted kind bucket + run rollup are flagged
    kinds = {k["kind"]: k for k in state["kinds"]}  # type: ignore[index,union-attr]
    assert kinds["tool"]["tainted"] is True
    runs = {r["run_id"]: r for r in state["runs"]}  # type: ignore[index,union-attr]
    assert runs["r2"].get("tainted") is True

    # the event row itself carries the taint flag
    tool_events = [e for e in state["events"] if e["kind"] == "tool"]  # type: ignore[index]
    assert tool_events and tool_events[0]["tainted"] is True


def test_events_are_newest_first_and_numeric_attrs_excluded_from_row_attrs() -> None:
    state = emission_dashboard_state(_stream())
    events = state["events"]
    assert isinstance(events, list)
    ts_seq = [e["ts"] for e in events]  # type: ignore[index]
    assert ts_seq == sorted(ts_seq, reverse=True)
    # numeric attrs are projected into series, not duplicated as row attrs
    model_event = next(e for e in events if e["kind"] == "model")  # type: ignore[index]
    assert "cost_usd" not in model_event["attrs"]  # type: ignore[operator]
    assert model_event["attrs"]["model"] == "sonnet"  # type: ignore[index]


def test_generated_at_is_passed_in_not_read_from_clock() -> None:
    assert emission_dashboard_state([], generated_at=123.0)["generated_at"] == 123.0
    assert emission_dashboard_state([])["generated_at"] == 0.0


def test_collect_emissions_reads_runs_from_store() -> None:
    from crawfish.emission import emit
    from crawfish.observe import ObserverSurface, RunInfo
    from crawfish.store.sqlite import SqliteStore

    store = SqliteStore(":memory:")
    surface = ObserverSurface(store)
    surface.put_run_info(RunInfo(pipeline="p", run_id="r1", started_at=1.0))
    emit(
        store,
        Emission(
            kind=EmissionKind.MODEL, run_id="r1", ts=2.0, attrs={"model": "m", "cost_usd": 0.5}
        ),
    )

    got = collect_emissions(store)
    state = emission_dashboard_state(got)
    assert state["total_cost_usd"] == 0.5


def test_since_window_filters_collected_emissions() -> None:
    from crawfish.emission import emit
    from crawfish.observe import ObserverSurface, RunInfo
    from crawfish.store.sqlite import SqliteStore

    store = SqliteStore(":memory:")
    surface = ObserverSurface(store)
    surface.put_run_info(RunInfo(pipeline="p", run_id="r1", started_at=1.0))
    emit(
        store,
        Emission(
            kind=EmissionKind.MODEL, run_id="r1", ts=10.0, attrs={"model": "m", "cost_usd": 1.0}
        ),
    )
    emit(
        store,
        Emission(
            kind=EmissionKind.MODEL, run_id="r1", ts=100.0, attrs={"model": "m", "cost_usd": 2.0}
        ),
    )

    # absolute epoch threshold keeps only the later emission (no clock dependence)
    got = collect_emissions(store, since=50.0)
    assert emission_dashboard_state(got)["total_cost_usd"] == 2.0


def test_serve_binds_loopback_only_and_serves_html() -> None:
    from crawfish.store.sqlite import SqliteStore
    from crawfish.visualize import LOOPBACK

    store = SqliteStore(":memory:")
    # port 0 -> OS picks a free port; we never bind a fixed public port in tests
    server = serve_emission_dashboard(store, port=0)
    try:
        assert server.server_address[0] == LOOPBACK
    finally:
        server.server_close()


def test_handler_factory_and_html_are_wired() -> None:
    from crawfish.store.sqlite import SqliteStore

    store = SqliteStore(":memory:")
    handler = make_emission_handler(store)
    assert handler is not None
    assert "emission" in EMISSION_DASHBOARD_HTML
