"""``craw visualize`` — a minimal localhost dashboard.

A hardcoded, zero-config dashboard over the run-info surface: deployed pipelines
(from the deploy registry), recent runs + status, today's spend, and the observer
event feed. One static HTML page plus a small JSON endpoint — no build step, no
framework. Auto-refreshes by polling the JSON.

Security spine: binds **loopback only** (``127.0.0.1``), never ``0.0.0.0``; it reads
the already-scrubbed run-info surface, so no secret value is ever rendered; there is
no auth to bypass because there is nothing reachable off-host. ``dashboard_state``
(the JSON the page shows) is built purely from the scrubbed Store records.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import TYPE_CHECKING

from crawfish.core.types import JSONValue
from crawfish.emission import Emission, read_emissions
from crawfish.manage import manage_list
from crawfish.observe import ObserverSurface, parse_since

if TYPE_CHECKING:
    from crawfish.store.base import Store

__all__ = [
    "dashboard_state",
    "DASHBOARD_HTML",
    "serve_dashboard",
    "make_handler",
    "emission_dashboard_state",
    "collect_emissions",
    "EMISSION_DASHBOARD_HTML",
    "serve_emission_dashboard",
    "make_emission_handler",
    "EMISSION_DASHBOARD_PORT",
]

LOOPBACK = "127.0.0.1"  # never bind a public interface
DEFAULT_PORT = 7878
EMISSION_DASHBOARD_PORT = 7879  # distinct from the topology dashboard's 7878


def dashboard_state(
    store: Store, *, org_id: str = "local", now: datetime | None = None, event_window: str = "-24h"
) -> dict[str, JSONValue]:
    """Build the JSON the dashboard renders — pipelines, runs, cost, observer feed.

    Every value comes from the scrubbed Store surface; nothing here reaches outside
    the persisted, redacted records.
    """
    now = now or datetime.now(UTC)
    surface = ObserverSurface(store, org_id=org_id)
    rows = manage_list(store, org_id=org_id, now=now)

    pipelines: list[JSONValue] = []
    recent_runs: list[JSONValue] = []
    observer_events: list[JSONValue] = []
    total_today = 0.0
    for r in rows:
        total_today += r.cost_today_usd
        pipelines.append(
            {
                "name": r.name,
                "status": r.status,
                "schedule": r.schedule,
                "next_fire": r.next_fire,
                "cost_today_usd": round(r.cost_today_usd, 4),
                "last_run_status": r.last_run_status,
            }
        )
        for ri in r.runs[:10]:
            recent_runs.append(
                {
                    "pipeline": ri.pipeline,
                    "run_id": ri.run_id,
                    "status": ri.status,
                    "cost_usd": round(ri.cost_usd, 4),
                    "started_at": ri.started_at,
                }
            )
        for ev in surface.events(r.name, since=event_window, now=now.timestamp()):
            observer_events.append(
                {
                    "pipeline": ev.pipeline,
                    "kind": ev.kind,
                    "severity": ev.severity.value,
                    "detail": ev.detail,
                    "ts": ev.ts,
                }
            )

    recent_runs.sort(key=lambda r: r["started_at"], reverse=True)
    observer_events.sort(key=lambda e: e["ts"], reverse=True)
    return {
        "generated_at": now.timestamp(),
        "cost_today_usd": round(total_today, 4),
        "pipelines": pipelines,
        "recent_runs": recent_runs[:50],
        "observer_events": observer_events[:50],
    }


# Single static page; fetches /state.json and re-renders every few seconds. No
# framework, no build, no external assets — and nothing here interpolates a secret.
DASHBOARD_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Crawfish · visualize</title>
<style>
  :root { color-scheme: dark; }
  body { font: 14px/1.5 ui-monospace, SFMono-Regular, Menlo, monospace;
         background:#0d1117; color:#e6edf3; margin:0; padding:24px; }
  h1 { font-size:18px; margin:0 0 4px; }
  .sub { color:#7d8590; margin:0 0 20px; }
  .grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(320px,1fr)); gap:16px; }
  .card { background:#161b22; border:1px solid #30363d; border-radius:8px; padding:16px; }
  .card h2 { font-size:13px; text-transform:uppercase; letter-spacing:.05em;
             color:#7d8590; margin:0 0 12px; }
  table { width:100%; border-collapse:collapse; }
  td, th { text-align:left; padding:4px 8px; border-bottom:1px solid #21262d; }
  th { color:#7d8590; font-weight:600; }
  .running { color:#3fb950; } .done { color:#3fb950; }
  .failed, .critical, .dead { color:#f85149; } .stopped, .warn { color:#d29922; }
  .big { font-size:28px; font-weight:700; }
  .feed div { padding:4px 0; border-bottom:1px solid #21262d; }
  .muted { color:#7d8590; }
</style>
</head>
<body>
  <h1>🦞 Crawfish</h1>
  <p class="sub">local dashboard · 127.0.0.1 · auto-refreshing</p>
  <div class="grid">
    <div class="card"><h2>Spend today</h2><div class="big" id="cost">$0.00</div></div>
    <div class="card"><h2>Pipelines</h2><table id="pipelines"></table></div>
    <div class="card"><h2>Recent runs</h2><table id="runs"></table></div>
    <div class="card"><h2>Observer feed</h2><div class="feed" id="events"></div></div>
  </div>
<script>
function ago(ts){ const s=Math.max(0,Date.now()/1000-ts);
  if(s<60)return Math.floor(s)+"s"; if(s<3600)return Math.floor(s/60)+"m";
  if(s<86400)return Math.floor(s/3600)+"h"; return Math.floor(s/86400)+"d"; }
function esc(x){ return String(x==null?"":x).replace(/[&<>]/g,
  c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c])); }
async function tick(){
  let d; try { d = await (await fetch('/state.json')).json(); } catch(e){ return; }
  document.getElementById('cost').textContent = '$'+(d.cost_today_usd||0).toFixed(2);
  document.getElementById('pipelines').innerHTML =
    '<tr><th>name</th><th>status</th><th>next</th><th>$today</th></tr>' +
    (d.pipelines||[]).map(p=>`<tr><td>${esc(p.name)}</td>`+
      `<td class="${esc(p.status)}">${esc(p.status)}</td>`+
      `<td>${esc(p.next_fire||'—')}</td><td>$${(p.cost_today_usd||0).toFixed(2)}</td></tr>`).join('')
      || '<tr><td class="muted">no deployed pipelines</td></tr>';
  document.getElementById('runs').innerHTML =
    '<tr><th>pipeline</th><th>status</th><th>$</th><th>when</th></tr>' +
    (d.recent_runs||[]).map(r=>`<tr><td>${esc(r.pipeline)}</td>`+
      `<td class="${esc(r.status)}">${esc(r.status)}</td>`+
      `<td>$${(r.cost_usd||0).toFixed(2)}</td><td>${ago(r.started_at)} ago</td></tr>`).join('')
      || '<tr><td class="muted">no runs yet</td></tr>';
  document.getElementById('events').innerHTML =
    (d.observer_events||[]).map(e=>`<div><span class="${esc(e.severity)}">`+
      `[${esc(e.kind)}]</span> ${esc(e.detail)} `+
      `<span class="muted">${ago(e.ts)} ago</span></div>`).join('')
      || '<div class="muted">no observer events</div>';
}
tick(); setInterval(tick, 3000);
</script>
</body>
</html>
"""


def make_handler(store: Store, *, org_id: str = "local") -> type[BaseHTTPRequestHandler]:
    """Build a request handler bound to ``store`` — serves the page + ``/state.json``."""

    class _Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args: object) -> None:  # silence default stderr logging
            return

        def _host_is_loopback(self) -> bool:
            """Reject non-loopback Host headers (DNS-rebinding defense)."""
            host = (self.headers.get("Host") or "").split(":")[0].strip().lower()
            return host in ("127.0.0.1", "localhost", "")

        def do_GET(self) -> None:  # noqa: N802 — http.server API
            if not self._host_is_loopback():
                # a rebinding page can hit the socket but not forge a loopback Host
                self.send_error(403, "loopback only")
                return
            if self.path in ("/", "/index.html"):
                body = DASHBOARD_HTML.encode("utf-8")
                ctype = "text/html; charset=utf-8"
            elif self.path.startswith("/state.json"):
                body = json.dumps(dashboard_state(store, org_id=org_id)).encode("utf-8")
                ctype = "application/json"
            else:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

    return _Handler


def serve_dashboard(
    store: Store, *, org_id: str = "local", port: int = DEFAULT_PORT
) -> ThreadingHTTPServer:
    """Create a loopback-bound dashboard server (caller runs ``serve_forever``).

    Always binds :data:`LOOPBACK` — the dashboard is never reachable off-host.
    """
    return ThreadingHTTPServer((LOOPBACK, port), make_handler(store, org_id=org_id))


# ===========================================================================
# Emission auto-dashboard (CRA-181)
# ---------------------------------------------------------------------------
# A *generic* projection over the typed :class:`Emission` stream. The renderable
# view is derived from ``Emission.attrs`` keys per :class:`EmissionKind`, so a new
# attribute on any emission shows up with **zero** dashboard-specific code. Numeric
# attr values become aggregated series; everything else becomes table rows.
#
# Security: this reads only the already-scrubbed ledger (no raw-secret path), binds
# loopback only, and propagates ``Emission.tainted`` into the rendered state so
# untrusted content is never laundered as trusted.
# ===========================================================================

# attrs we never want to treat as a numeric metric series even if numeric-looking.
_NON_METRIC_ATTRS = frozenset({"node_id", "session_id", "output_id", "batch_id", "cap"})


def _is_number(value: JSONValue) -> bool:
    # bool is an int subclass; a boolean is a flag, not a measured number.
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def emission_dashboard_state(
    emissions: Iterable[Emission], *, generated_at: float = 0.0
) -> dict[str, JSONValue]:
    """Build the dashboard JSON purely from a typed :class:`Emission` stream.

    This is the single source of truth for the live dashboard and is **pure** (no
    clock, no socket, no Store): pass the emissions and an optional ``generated_at``
    timestamp. It is the deterministically-testable core; the serve/handler layer is a
    thin wrapper that collects emissions and calls this.

    Generic rendering — *no per-metric code*:

    * **kinds** — one bucket per :class:`EmissionKind` seen, with a count and the
      union of every ``attrs`` key observed for that kind (so a brand-new attr is
      listed automatically).
    * **metrics** — every *numeric* ``attrs`` value, aggregated into a series keyed by
      ``"<kind>.<attr>"`` (sum / count / last / latest-ts). ``model.cost_usd`` rolls up
      total spend with no bespoke branch; an arbitrary new numeric attr does too.
    * **events** — every emission as a table row (kind, run, node, ts, non-numeric
      attrs rendered generically), newest first.
    * **runs** — per-``run_id`` rollup (kinds seen, emission count, latest ts).

    Taint: each event row carries ``tainted``; a tainted emission's numeric
    contributions are also counted under each metric's ``tainted`` tally, and any
    metric/kind/run touched by a tainted emission is flagged ``tainted: true`` — so
    untrusted content is visibly distinguished and never laundered as trusted.
    """
    items = list(emissions)

    kinds: dict[str, dict[str, JSONValue]] = {}
    metrics: dict[str, dict[str, JSONValue]] = {}
    runs: dict[str, dict[str, JSONValue]] = {}
    events: list[dict[str, JSONValue]] = []
    tainted_count = 0

    for e in items:
        kind = e.kind.value
        if e.tainted:
            tainted_count += 1

        # -- per-kind bucket: count + union of every attr key ever seen ----------
        kb = kinds.setdefault(kind, {"kind": kind, "count": 0, "attr_keys": [], "tainted": False})
        kb["count"] = int(kb["count"]) + 1
        seen_keys = kb["attr_keys"]
        assert isinstance(seen_keys, list)
        for k in e.attrs:
            if k not in seen_keys:
                seen_keys.append(k)
        if e.tainted:
            kb["tainted"] = True

        # -- per-run rollup -----------------------------------------------------
        rb = runs.setdefault(
            e.run_id,
            {"run_id": e.run_id, "pipeline": e.pipeline, "count": 0, "kinds": [], "latest_ts": 0.0},
        )
        rb["count"] = int(rb["count"]) + 1
        rkinds = rb["kinds"]
        assert isinstance(rkinds, list)
        if kind not in rkinds:
            rkinds.append(kind)
        if e.ts > float(rb["latest_ts"]):
            rb["latest_ts"] = e.ts
        if e.tainted:
            rb["tainted"] = True

        # -- generic metric series over numeric attrs ---------------------------
        non_numeric: dict[str, JSONValue] = {}
        for key, val in e.attrs.items():
            if key in _NON_METRIC_ATTRS or not _is_number(val):
                non_numeric[key] = val
                continue
            series_key = f"{kind}.{key}"
            m = metrics.setdefault(
                series_key,
                {
                    "key": series_key,
                    "kind": kind,
                    "attr": key,
                    "count": 0,
                    "sum": 0.0,
                    "last": 0.0,
                    "latest_ts": 0.0,
                    "tainted_count": 0,
                    "tainted": False,
                },
            )
            num = float(val)
            m["count"] = int(m["count"]) + 1
            m["sum"] = round(float(m["sum"]) + num, 6)
            if e.ts >= float(m["latest_ts"]):
                m["latest_ts"] = e.ts
                m["last"] = num
            if e.tainted:
                m["tainted_count"] = int(m["tainted_count"]) + 1
                m["tainted"] = True

        events.append(
            {
                "id": e.id,
                "kind": kind,
                "run_id": e.run_id,
                "pipeline": e.pipeline,
                "node_id": e.node_id,
                "ts": e.ts,
                "tainted": e.tainted,
                "attrs": non_numeric,  # numeric attrs live in the metric series
            }
        )

    events.sort(key=lambda ev: float(ev["ts"]), reverse=True)

    # total spend is just the model.cost_usd series sum — no bespoke cost code.
    cost_series = metrics.get("model.cost_usd")
    total_cost = round(float(cost_series["sum"]), 4) if cost_series else 0.0

    return {
        "generated_at": generated_at,
        "emission_count": len(items),
        "tainted_count": tainted_count,
        "total_cost_usd": total_cost,
        "kinds": sorted(kinds.values(), key=lambda k: str(k["kind"])),
        "metrics": sorted(metrics.values(), key=lambda m: str(m["key"])),
        "runs": sorted(runs.values(), key=lambda r: float(r["latest_ts"]), reverse=True),
        "events": events[:200],
    }


def collect_emissions(
    store: Store,
    *,
    org_id: str = "local",
    since: str | float | int | None = None,
    now: float | None = None,
) -> list[Emission]:
    """Gather typed emissions across all known runs from the scrubbed Store.

    Enumerates runs via the run-info surface, then lifts each run's ledger through
    :func:`read_emissions`. Filters to emissions at/after the ``since`` threshold.
    Pure read — the only clock use is resolving a relative ``since`` window.
    """
    threshold = parse_since(since, now=now)
    surface = ObserverSurface(store, org_id=org_id)
    out: list[Emission] = []
    for ri in surface.run_info():
        out.extend(read_emissions(store, ri.run_id, org_id=org_id))
    return [e for e in out if e.ts >= threshold]


# Single static page; fetches /state.json and re-renders generically from whatever
# kinds/metrics/events the projection carries. No framework, no build, no secret.
EMISSION_DASHBOARD_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Crawfish · emissions</title>
<style>
  :root { color-scheme: dark; }
  body { font: 14px/1.5 ui-monospace, SFMono-Regular, Menlo, monospace;
         background:#0d1117; color:#e6edf3; margin:0; padding:24px; }
  h1 { font-size:18px; margin:0 0 4px; }
  .sub { color:#7d8590; margin:0 0 20px; }
  .grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(320px,1fr)); gap:16px; }
  .card { background:#161b22; border:1px solid #30363d; border-radius:8px; padding:16px; }
  .card h2 { font-size:13px; text-transform:uppercase; letter-spacing:.05em;
             color:#7d8590; margin:0 0 12px; }
  table { width:100%; border-collapse:collapse; }
  td, th { text-align:left; padding:4px 8px; border-bottom:1px solid #21262d;
           vertical-align:top; }
  th { color:#7d8590; font-weight:600; }
  .big { font-size:28px; font-weight:700; }
  .muted { color:#7d8590; }
  .tainted { color:#d29922; }
  .tag { display:inline-block; font-size:11px; padding:0 6px; border-radius:6px;
         background:#3a2d00; color:#d29922; margin-left:6px; }
</style>
</head>
<body>
  <h1>🦞 Crawfish · emission dashboard</h1>
  <p class="sub">local · 127.0.0.1 · auto-rendered from the typed emission stream</p>
  <div class="grid">
    <div class="card"><h2>Spend (model emissions)</h2><div class="big" id="cost">$0.00</div>
      <div class="muted" id="counts"></div></div>
    <div class="card"><h2>Kinds</h2><table id="kinds"></table></div>
    <div class="card"><h2>Metrics (auto)</h2><table id="metrics"></table></div>
    <div class="card"><h2>Runs</h2><table id="runs"></table></div>
  </div>
  <div class="card" style="margin-top:16px"><h2>Emission feed</h2>
    <table id="events"></table></div>
<script>
function esc(x){ return String(x==null?"":x).replace(/[&<>]/g,
  c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c])); }
function taint(t){ return t ? '<span class="tag">tainted</span>' : ''; }
function kvs(o){ return Object.keys(o||{}).map(k=>esc(k)+'='+esc(o[k])).join(' '); }
async function tick(){
  let d; try { d = await (await fetch('/state.json')).json(); } catch(e){ return; }
  document.getElementById('cost').textContent = '$'+(d.total_cost_usd||0).toFixed(2);
  document.getElementById('counts').textContent =
    (d.emission_count||0)+' emissions · '+(d.tainted_count||0)+' tainted';
  document.getElementById('kinds').innerHTML =
    '<tr><th>kind</th><th>n</th><th>attrs</th></tr>' +
    (d.kinds||[]).map(k=>`<tr><td>${esc(k.kind)}${taint(k.tainted)}</td>`+
      `<td>${esc(k.count)}</td>`+
      `<td class="muted">${(k.attr_keys||[]).map(esc).join(', ')}</td></tr>`)
      .join('') || '<tr><td class="muted">none</td></tr>';
  document.getElementById('metrics').innerHTML =
    '<tr><th>metric</th><th>sum</th><th>last</th><th>n</th></tr>' +
    (d.metrics||[]).map(m=>`<tr><td>${esc(m.key)}${taint(m.tainted)}</td>`+
      `<td>${esc(m.sum)}</td><td>${esc(m.last)}</td><td>${esc(m.count)}</td></tr>`)
      .join('') || '<tr><td class="muted">none</td></tr>';
  document.getElementById('runs').innerHTML =
    '<tr><th>run</th><th>kinds</th><th>n</th></tr>' +
    (d.runs||[]).map(r=>`<tr><td>${esc(String(r.run_id).slice(0,8))}${taint(r.tainted)}</td>`+
      `<td class="muted">${(r.kinds||[]).map(esc).join(', ')}</td><td>${esc(r.count)}</td></tr>`)
      .join('') || '<tr><td class="muted">none</td></tr>';
  document.getElementById('events').innerHTML =
    '<tr><th>kind</th><th>run</th><th>node</th><th>attrs</th></tr>' +
    (d.events||[]).map(e=>`<tr class="${e.tainted?'tainted':''}">`+
      `<td>${esc(e.kind)}${taint(e.tainted)}</td>`+
      `<td>${esc(String(e.run_id).slice(0,8))}</td><td>${esc(e.node_id||'—')}</td>`+
      `<td class="muted">${esc(kvs(e.attrs))}</td></tr>`)
      .join('') || '<tr><td class="muted">no emissions</td></tr>';
}
tick(); setInterval(tick, 3000);
</script>
</body>
</html>
"""


def make_emission_handler(
    store: Store,
    *,
    org_id: str = "local",
    since: str | float | int | None = None,
) -> type[BaseHTTPRequestHandler]:
    """Build a request handler that serves the emission dashboard + ``/state.json``.

    ``/state.json`` collects emissions from the scrubbed Store and projects them via the
    pure :func:`emission_dashboard_state`. ``generated_at`` is stamped here (the only
    clock use), keeping the projection itself deterministic.
    """

    class _Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args: object) -> None:  # silence default stderr logging
            return

        def _host_is_loopback(self) -> bool:
            host = (self.headers.get("Host") or "").split(":")[0].strip().lower()
            return host in ("127.0.0.1", "localhost", "")

        def do_GET(self) -> None:  # noqa: N802 — http.server API
            if not self._host_is_loopback():
                self.send_error(403, "loopback only")
                return
            if self.path in ("/", "/index.html"):
                body = EMISSION_DASHBOARD_HTML.encode("utf-8")
                ctype = "text/html; charset=utf-8"
            elif self.path.startswith("/state.json"):
                emissions = collect_emissions(store, org_id=org_id, since=since)
                state = emission_dashboard_state(
                    emissions, generated_at=datetime.now(UTC).timestamp()
                )
                body = json.dumps(state).encode("utf-8")
                ctype = "application/json"
            else:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

    return _Handler


def serve_emission_dashboard(
    store: Store,
    *,
    org_id: str = "local",
    port: int = EMISSION_DASHBOARD_PORT,
    since: str | float | int | None = None,
) -> ThreadingHTTPServer:
    """Create a loopback-bound emission dashboard server (caller runs ``serve_forever``).

    Always binds :data:`LOOPBACK`; never reachable off-host. No write path, no egress.
    """
    return ThreadingHTTPServer(
        (LOOPBACK, port), make_emission_handler(store, org_id=org_id, since=since)
    )
