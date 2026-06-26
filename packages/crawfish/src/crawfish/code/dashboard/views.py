"""Server-rendered dashboard views — runs in flight, cost band, lineage, gauge.

Every view here renders to a **string** (deterministic, testable without a browser) and
routes every tainted field through ``encode_field`` (``encoding.py``) — the single
output-encoding chokepoint (UNFILED-XSS). ``pipeline`` / ``kind`` / ``status`` / ``severity``
are stable static identifiers and rendered unencoded; ``detail`` / ``version`` / item ids /
metric labels / URLs are tainted and encoded for their context.

No inline ``<script>``/``<style>`` (the CSP forbids ``'unsafe-inline'``): the page's JS/CSS
are served as same-origin static files (``app.js`` / ``app.css``), so the rendered HTML is
pure markup the encoder fully controls.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from crawfish.code.dashboard.encoding import Encoding, encode_field

if TYPE_CHECKING:
    from crawfish.code.dashboard.data import CostGauge, FleetSnapshot, RunCard
    from crawfish.observe import ObserverEvent

__all__ = ["render_page", "render_runs", "render_cost_gauge", "render_events", "STATIC_CSS"]

#: Same-origin stylesheet (served as a static file — never inlined, so the CSP can forbid
#: ``'unsafe-inline'``). No untrusted value is ever interpolated into it.
STATIC_CSS = """:root { color-scheme: dark; }
body { font: 14px/1.5 ui-monospace, SFMono-Regular, Menlo, monospace;
       background:#0d1117; color:#e6edf3; margin:0; padding:24px; }
h1 { font-size:18px; margin:0 0 4px; }
h2 { font-size:14px; margin:24px 0 8px; color:#8b949e; text-transform:uppercase;
     letter-spacing:.05em; }
table { border-collapse:collapse; width:100%; margin-bottom:16px; }
th, td { text-align:left; padding:4px 10px; border-bottom:1px solid #21262d; }
th { color:#8b949e; font-weight:600; }
.band { position:relative; height:14px; background:#161b22; border-radius:3px; min-width:120px; }
.band > .fill { position:absolute; left:0; top:0; bottom:0; background:#2f81f7; border-radius:3px; }
.band.amber > .fill { background:#d29922; }
.gauge { height:18px; background:#161b22; border-radius:3px; position:relative; }
.gauge > .fill { position:absolute; left:0; top:0; bottom:0; background:#3fb950; }
.gauge.warn > .fill { background:#d29922; }
.gauge.ceiling_reached > .fill { background:#f85149; }
.sev-critical { color:#f85149; }
.sev-warn { color:#d29922; }
"""


def _pct(num: float, den: float) -> float:
    """A clamped 0..100 percentage; a zero/negative denominator is 0%."""
    if den <= 0:
        return 0.0
    return max(0.0, min(100.0, 100.0 * num / den))


def render_runs(cards: list[RunCard]) -> str:
    """Runs-in-flight table: fan-out progress (done/total) + the cost band vs budget.

    The band fills toward ``worst_case_usd``; when actual exceeds ``expected_usd`` the band
    flips amber (the spec's threshold). ``run_id`` / ``version`` are tainted → encoded.
    """
    rows: list[str] = []
    for c in cards:
        amber = c.cost_usd > c.budget.expected_usd and c.budget.expected_usd >= 0
        fill = _pct(c.cost_usd, c.budget.worst_case_usd or c.cost_usd or 1.0)
        # pipeline/status are static identifiers; run_id/version are tainted (encoded).
        rows.append(
            "<tr>"
            f"<td>{encode_field(c.run_id, Encoding.HTML_BODY)}</td>"
            f"<td>{c.pipeline}</td>"  # static identifier
            f"<td>{c.status}</td>"  # static identifier
            f"<td>{encode_field(c.version, Encoding.HTML_BODY)}</td>"
            f"<td>{c.done_items}/{c.items}</td>"
            f"<td>${c.cost_usd:.4f}</td>"
            f'<td><div class="band{" amber" if amber else ""}">'
            f'<div class="fill" style="width:{fill:.1f}%"></div></div></td>'
            "</tr>"
        )
    body = "".join(rows) or '<tr><td colspan="7">no runs</td></tr>'
    return (
        "<table><thead><tr><th>run</th><th>pipeline</th><th>status</th>"
        "<th>version</th><th>fan-out</th><th>cost</th><th>budget</th></tr></thead>"
        f"<tbody>{body}</tbody></table>"
    )


def render_cost_gauge(gauge: CostGauge) -> str:
    """The org-scoped aggregate cost-vs-ceiling gauge (UNFILED-COST).

    ``state`` (ok / warn / ceiling_reached) drives the fill color. ``org_id`` is a static
    tenancy identifier but still encoded as an attribute for belt-and-braces.
    """
    if gauge.ceiling_usd is None:
        return (
            f"<p>spent today ${gauge.spent_today_usd:.4f} — "
            f"no ceiling configured (<code>[budget] ceiling_usd</code>)</p>"
        )
    fill = _pct(gauge.spent_today_usd, gauge.ceiling_usd)
    return (
        f'<div class="gauge {gauge.state}" '
        f'title="{encode_field(gauge.org_id, Encoding.ATTR)}">'
        f'<div class="fill" style="width:{fill:.1f}%"></div></div>'
        f"<p>${gauge.spent_today_usd:.4f} / ${gauge.ceiling_usd:.4f} "
        f"(projected ${gauge.projected_today_usd:.4f}) — <strong>{gauge.state}</strong></p>"
    )


def render_events(events: list[ObserverEvent]) -> str:
    """Observer-event feed. ``detail`` is fully tainted and entity-encoded (the XSS surface).

    A ``data`` value that is a URL is run through the URL encoder (rejecting ``javascript:`` /
    off-host schemes); ``kind`` / ``severity`` are static identifiers.
    """
    rows: list[str] = []
    for ev in events:
        link = ev.data.get("link") if isinstance(ev.data, dict) else None
        link_cell = ""
        if isinstance(link, str):
            href = encode_field(link, Encoding.URL)
            link_cell = f'<a href="{href}" rel="noopener noreferrer">link</a>'
        rows.append(
            "<tr>"
            f"<td>{ev.pipeline}</td>"  # static
            f"<td>{ev.kind}</td>"  # static
            f'<td class="sev-{ev.severity.value}">{ev.severity.value}</td>'  # static enum
            f"<td>{encode_field(ev.detail, Encoding.HTML_BODY)}</td>"
            f"<td>{link_cell}</td>"
            "</tr>"
        )
    body = "".join(rows) or '<tr><td colspan="5">no events</td></tr>'
    return (
        "<table><thead><tr><th>pipeline</th><th>kind</th><th>severity</th>"
        "<th>detail</th><th>link</th></tr></thead>"
        f"<tbody>{body}</tbody></table>"
    )


def render_page(
    *,
    fleet: FleetSnapshot,
    runs: list[RunCard],
    gauge: CostGauge,
    events: list[ObserverEvent],
) -> str:
    """Assemble the full dashboard HTML page (no inline script/style; CSP-safe).

    The page links ``/app.css`` (same-origin); there is no inline ``<script>`` (the polling
    JS, when present, ships as ``/app.js``). Every tainted value is already encoded by the
    section renderers, so the assembled string contains no live injected markup.
    """
    org = encode_field(fleet.org_id, Encoding.HTML_BODY)
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        "<title>craw code · dashboard</title>"
        '<link rel="stylesheet" href="/app.css"></head><body>'
        f"<h1>craw code · dashboard</h1><p>org <code>{org}</code> · "
        f"${fleet.cost_today_usd:.4f} today</p>"
        "<h2>cost vs ceiling</h2>"
        + render_cost_gauge(gauge)
        + "<h2>runs in flight</h2>"
        + render_runs(runs)
        + "<h2>observer events</h2>"
        + render_events(events)
        + "</body></html>"
    )
