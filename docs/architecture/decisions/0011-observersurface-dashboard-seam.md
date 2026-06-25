# ADR 0011 — The dashboard reads through the ObserverSurface / Store seam

* **Status:** Accepted
* **Date:** 2026-06-25
* **Milestone:** M4 (`craw code` dashboard / operate plane)
* **Issues:** CRA-252, CRA-253, CRA-254, UNFILED-SEAM, UNFILED-XSS, UNFILED-COST
* **Supersedes the placeholder ADR number in the spec** — the M4 spec
  (`docs/specs/craw-code/03-dashboard-operate-hitl.md`) refers to "ADR 0008 (verify
  number)". The `decisions/` directory had already advanced past 0008 when this was
  written (0010, 0012 exist), so the seam is recorded here as **0011**.

## Context

`craw code dashboard` renders a loopback fleet view over the `.crawfish/` ledger: runs in
flight, fan-out progress, cost burn, and an org-scoped cost-vs-ceiling gauge. The ledger
and deploy registry under `.crawfish/` are the source of truth.

RFC 0001 §12.3 flags this surface as the single most likely place to violate the
load-bearing architecture rule of `CLAUDE.md` / `ARCHITECTURE.md`:

> The product model imports the `Store` / `ObserverSurface` / `ArtifactStore` **protocols**,
> never a concrete backend.

One stray `from crawfish.store.sqlite import SqliteStore` in the dashboard, or one raw
`SELECT` against `.crawfish/crawfish.db`, and the SQLite→Postgres (cloud / scale) swap
stops being a driver swap and becomes a rewrite. Two further spine guarantees ride on the
same seam:

1. **Scrubbing.** Secrets/PII are redacted *before* the Store write by wrapping the store
   in `ScrubbingStore` (`crawfish/secrets.py`). If the dashboard could read past the
   surface (a direct table read, a second un-wrapped store), it would bypass that
   redaction and could render a secret ref / egress host / sink target.
2. **Tenancy.** Every read is scoped to one `org_id`; an org-A dashboard must never surface
   an org-B row. The surface is the chokepoint where `org_id` is applied.

## Decision

1. **The dashboard package imports protocols and surfaces only.** `code/dashboard/`
   depends on `crawfish.observe` (`ObserverSurface`, `RunInfo`, `ObserverEvent`),
   `crawfish.store.base` (the `Store` protocol), `crawfish.deploy` (`DeployRegistry`),
   `crawfish.manage` (`manage_list`, `store_for_dir`, `PipelineStatus`), `crawfish.cost`
   (`CostEstimate`), `crawfish.config` (`load_budget`), and `crawfish.secrets`
   (`ScrubbingStore`, `SecretManager` — a protocol-level decorator, **not** a backend).
   It **never** names `SqliteStore`, `crawfish.store.sqlite`, `sqlite3`, or any SQL string.

2. **Construction seam.** `craw code dashboard` resolves the project's configured `Store`
   via `crawfish.manage.store_for_dir` (the same factory `craw visualize` / `craw manage`
   use — the one place that knows the concrete backend), wraps it in `ScrubbingStore`, and
   hands the *interface* to `ObserverSurface` / `DeployRegistry`. The dashboard code
   receives only the surface; it cannot reconstruct an un-scrubbed one.

3. **Aggregation is pure Python over typed, scrubbed rows.** Cost rollups, fan-out
   progress (`done/total`), status counts, the cost-vs-ceiling gauge — all are computed in
   Python over `ObserverSurface.run_info(...)` / `.events(...)` / `manage_list(...)` rows.
   No SQL `COUNT`/`SUM`/`SELECT` is constructed in the dashboard; the only SQL in the
   process lives inside the `SqliteStore` impl behind the protocol.

4. **Loopback only.** The HTTP server binds `127.0.0.1` exclusively (extending
   `craw visualize`), rejects non-loopback `Host` headers (DNS-rebinding defense), and adds
   no auth layer because there is no network surface.

5. **Tainted ledger text is output-encoded + CSP'd (see UNFILED-XSS).** Scrubbing removes
   *secrets*, not *markup*. `ObserverEvent.detail`, `RunInfo.version`, item ids, and any
   model-derived field are `Flow.FLUID` and reach the HTTP layer **unmodified** so the
   render layer's `encode_field` is the single chokepoint, backed by a strict
   `default-src 'none'` CSP. `pipeline` / `kind` / `status` / `severity` are stable static
   identifiers and the only fields rendered unencoded.

## Consequences

* The cloud/scale swap stays a driver swap: pointing `store_for_dir` at a Postgres-backed
  `Store` changes nothing in `code/dashboard/`. An import/source-lint test
  (`test_code_dashboard_seam.py`) fails the build if any dashboard module names a concrete
  backend or SQL, and a `MemoryStore` (a non-`SqliteStore` `Store` impl) produces the same
  `--json` snapshot — proving the swap.
* Scrubbing can never be bypassed: every read is forced through the `ScrubbingStore`-wrapped
  surface, so the redaction guarantee holds structurally, not by convention.
* Tenancy holds: the surface is constructed `ObserverSurface(store, org_id=args.org)`, and
  the two-org isolation test proves org-B rows never appear in an org-A dashboard.
* Python aggregation costs a full-row scan per render. Acceptable: the dashboard is a
  loopback, human-paced, poll-every-N-seconds surface, not a hot path; and it keeps the SQL
  surface area zero outside the `Store` impl. If a project's ledger grows large enough that
  this matters, the answer is a `Store`-level aggregation method on the protocol (available
  to every backend), never a raw query in the dashboard.

## Rejected alternatives

* **Direct SQLite read for speed.** A `sqlite3.connect(".crawfish/crawfish.db")` with
  `SELECT … GROUP BY` would be faster and simpler. Rejected: it hard-codes the backend
  (breaks the swap), bypasses `ScrubbingStore` (a secret/egress/sink-target leak straight
  into a rendered, fluid surface), and bypasses `org_id` scoping (cross-tenant leakage).
  The three spine guarantees this ADR exists to protect are *exactly* the ones a direct
  read discards.
* **A bespoke dashboard `Store` subclass.** Rejected: re-implements persistence the seam
  already owns and tempts a second, un-scrubbed read path.
* **Server-push / websockets for live updates.** Rejected in favor of polling the `--json`
  snapshot endpoint — keeps the network surface closed (one loopback GET), no long-lived
  socket, no server-initiated connection.
