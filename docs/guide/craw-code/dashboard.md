# The dashboard

The dashboard is a human-readable view of what your fleet is doing — runs, cost, optimization
history — served on loopback over the `.crawfish/` ledger. It is a *read-model*: it reads the
event stream through the same observer and store seams the rest of Crawfish uses, scrubs every
row, and shows it. It never acts on the fleet and never touches the database directly.

!!! note "You will learn:"
    - How to start the dashboard and what it shows
    - Why it reads through the `ObserverSurface`/`Store` seam instead of SQLite
    - The XSS and scrubbing guarantees that make it safe to render tainted ledger text
    - How org-scoping isolates one tenant's view from another's

## Starting it

```bash
craw code dashboard --open
# binds 127.0.0.1 only, reads .crawfish/ in the current project, opens a browser tab
```

| Flag | What it does |
| --- | --- |
| `--port PORT` | The loopback port (binds `127.0.0.1` only — never a routable interface). |
| `--project DIR` | The project directory holding `.crawfish/` (default: cwd). |
| `--open` | Launch a browser tab at the loopback URL. |
| `--org ORG` | The tenancy `org_id`; the dashboard shows only that org's rows. |

The dashboard surfaces three views, each backed by its own versioned envelope so the same data
is available as JSON: the **runs** view (`craw.code.dashboard.runs.v1`) lists recent runs with
their status and item counts; the **cost** view rolls up spend per run and per org against the
budget ceiling; and the **optimize** view (`craw.code.dashboard.optimize.v1`) shows the
tune/refine/learn history for a component.

## Reading through the seam, not the database

The dashboard package imports only protocols and surfaces — `crawfish.observe`,
`crawfish.store.base`, `crawfish.deploy`, `crawfish.cost`, `crawfish.config`,
`crawfish.secrets`. It never imports `SqliteStore`, `sqlite3`, or raw SQL. It gets its store
through the construction seam `crawfish.manage.store_for_dir`, wrapped in a `ScrubbingStore`,
and aggregates in pure Python over the scrubbed rows. This is [ADR 0011](../../architecture/decisions/0011-observersurface-dashboard-seam.md).

The reason is not tidiness. Reading SQLite directly would hard-code the backend (breaking the
"cloud and scale are a driver swap" seam), and — worse — it would **bypass the scrubbing and
org-scoping** that the store wrapper enforces. By going through the seam, the dashboard cannot
see an unscrubbed secret or another org's rows even by accident.

## XSS and scrubbing guarantees

The ledger contains tainted text — a ticket body, an error message, anything a fluid input
carried. Rendering that in a browser is exactly the shape of a stored-XSS bug, so the
dashboard treats every value as hostile:

!!! warning "Tainted ledger text is data, never markup"
    All ledger-derived text is output-encoded before it reaches the page, and the dashboard
    serves a strict Content-Security-Policy. A poisoned ticket that embedded a `<script>` tag
    renders as inert text; it cannot execute in the dashboard. Secrets are scrubbed at the
    store seam before aggregation, so a credential cannot reach the page to be rendered at all.

The server is loopback-only and rejects requests whose `Host` header is not a loopback
address, so the page cannot be reached from another machine even if the port were forwarded.
There are no websockets — the view refreshes by polling — which keeps the surface closed.

## Org-scoping

Every `Store` row carries an `org_id` (defaulted `"local"`), and the dashboard threads
`--org` through every read. The runs, cost, and optimize views you see are exactly the rows
for that org and no other. Running two dashboards with different `--org` values shows two
isolated fleets from the same ledger file.

```bash
craw code dashboard --org acme --port 8788
# a view scoped to org "acme", on a separate loopback port
```

## A deterministic walk-through

The dashboard reads whatever is in `.crawfish/`, so you can populate it deterministically from
the demo before opening it — every command below runs on the mock runtime:

```bash
craw code sync --dir demo/craw-code-golden   # reconcile + assembly gate, writes ledger events
craw code dashboard --project demo/craw-code-golden --open
```

What you see is the scrubbed read-model of those events: the runs that fired, their cost band,
and (once you have optimized a component) its tuning history — all rendered from the ledger,
none of it live.

## See also

- [Operate & optimize](operate.md) — the verbs that produce the events the dashboard renders
- [ADR 0011](../../architecture/decisions/0011-observersurface-dashboard-seam.md) — the ObserverSurface/Store dashboard seam
- [Security model](security.md) — scrubbing, CSP, and the loopback boundary in depth
- [Observe](../observers.md) — the observer surface the dashboard reads through
