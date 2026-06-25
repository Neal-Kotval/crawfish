"""Loopback HTTP server for the dashboard (CRA-253) — strict CSP, no external surface.

Binds ``127.0.0.1`` exclusively (extends ``craw visualize``), rejects non-loopback ``Host``
headers (DNS-rebinding defense), and stamps the strict CSP + ``nosniff`` / ``no-referrer``
(:data:`~crawfish.code.dashboard.encoding.SECURITY_HEADERS`) on every HTML response. The
``--json`` snapshot endpoints serve ``application/json`` and are never rendered as HTML.

The page's JS/CSS are same-origin static files (so the CSP can forbid ``'unsafe-inline'``).
The rendered HTML is built by :mod:`~crawfish.code.dashboard.views`, whose ``encode_field``
chokepoint has already neutralized every tainted field before it reaches the socket.
"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from crawfish.code.dashboard.data import DashboardData

__all__ = ["LOOPBACK", "DEFAULT_PORT", "make_handler", "serve_dashboard", "render_snapshot"]

LOOPBACK = "127.0.0.1"  # never bind a public interface
DEFAULT_PORT = 7878


def render_snapshot(data: DashboardData, *, now: float | None = None) -> dict[str, object]:
    """The full ``--json`` snapshot (``craw.code.dashboard.v1``) — fleet + runs + events + cost.

    A typed, deterministic projection. Tainted fields (``detail`` / ``version``) are carried
    as-is in the JSON (a parser consumes them as strings, never executes them); a downstream
    *HTML* renderer is the one that must encode — which the dashboard's own views do.
    """
    from crawfish.code.dashboard.data import (
        COST_SCHEMA,
        DASHBOARD_SCHEMA,
        RUNS_SCHEMA,
    )

    fleet = data.fleet(now=now)
    runs = data.runs()
    gauge = data.cost_gauge(now=now)
    events = data.events()
    return {
        "schema": DASHBOARD_SCHEMA,
        "runs_schema": RUNS_SCHEMA,
        "cost_schema": COST_SCHEMA,
        "org_id": fleet.org_id,
        "generated_at": fleet.generated_at,
        "fleet": [r.model_dump() for r in fleet.rows],
        "cost_today_usd": fleet.cost_today_usd,
        "runs": [c.model_dump() for c in runs],
        "cost": gauge.model_dump(),
        "events": [
            {
                "pipeline": e.pipeline,
                "kind": e.kind,
                "severity": e.severity.value,
                "detail": e.detail,
                "run_id": e.run_id,
            }
            for e in events
        ],
    }


def _render_html(data: DashboardData, *, now: float | None = None) -> str:
    from crawfish.code.dashboard.views import render_page

    return render_page(
        fleet=data.fleet(now=now),
        runs=data.running(),
        gauge=data.cost_gauge(now=now),
        events=data.events(),
    )


def make_handler(data: DashboardData) -> type[BaseHTTPRequestHandler]:
    """Build a request handler over a :class:`DashboardData` facade (no store class here)."""
    from crawfish.code.dashboard.encoding import SECURITY_HEADERS
    from crawfish.code.dashboard.views import STATIC_CSS

    class _Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args: object) -> None:  # silence default stderr logging
            return

        def _host_is_loopback(self) -> bool:
            """Reject non-loopback Host headers (DNS-rebinding defense)."""
            host = (self.headers.get("Host") or "").split(":")[0].strip().lower()
            return host in ("127.0.0.1", "localhost", "")

        def _send(self, body: bytes, ctype: str, *, html: bool) -> None:
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            if html:
                for name, value in SECURITY_HEADERS:
                    self.send_header(name, value)
            else:
                # JSON / CSS still get nosniff + no-store (never sniffed into HTML).
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802 — http.server API
            if not self._host_is_loopback():
                self.send_error(403, "loopback only")
                return
            path = self.path.split("?", 1)[0]
            if path in ("/", "/index.html"):
                html = _render_html(data).encode("utf-8")
                self._send(html, "text/html; charset=utf-8", html=True)
            elif path == "/app.css":
                self._send(STATIC_CSS.encode("utf-8"), "text/css; charset=utf-8", html=False)
            elif path == "/snapshot.json":
                body = json.dumps(render_snapshot(data), sort_keys=True).encode("utf-8")
                self._send(body, "application/json", html=False)
            else:
                self.send_error(404)

    return _Handler


def serve_dashboard(data: DashboardData, *, port: int = DEFAULT_PORT) -> ThreadingHTTPServer:
    """Create a loopback-bound dashboard server (caller runs ``serve_forever``).

    Always binds :data:`LOOPBACK` — the dashboard is never reachable off-host (ADR 0011).
    """
    return ThreadingHTTPServer((LOOPBACK, port), make_handler(data))
