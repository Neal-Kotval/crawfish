"""``craw visualize`` — a minimal localhost dashboard (CRA-155).

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
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import TYPE_CHECKING

from crawfish.core.types import JSONValue
from crawfish.manage import manage_list
from crawfish.observe import ObserverSurface

if TYPE_CHECKING:
    from crawfish.store.base import Store

__all__ = ["dashboard_state", "DASHBOARD_HTML", "serve_dashboard", "make_handler"]

LOOPBACK = "127.0.0.1"  # never bind a public interface
DEFAULT_PORT = 7878


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

        def do_GET(self) -> None:  # noqa: N802 — http.server API
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
