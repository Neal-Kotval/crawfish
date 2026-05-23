# Crawfish — Features

Snapshot at `v0.3` (NOW slice complete, ROADMAP Weeks 1–5).

Source-of-truth scan: code in `cli/projectctl/`, `cli/orgctl/`, `desktop/dash/`, `desktop/lens/`, `desktop/opt/`, `desktop/opt-codebase/`. Roadmap horizon: [`ROADMAP.md`](./ROADMAP.md). Vision: [`docs/roadmap/GRAND_PLAN.md`](./docs/roadmap/GRAND_PLAN.md).

---

## 1 · Observability — what existed before this session

Surface across 5 submodules: `crawfish-lens` (transcript reader + REST + SSE), `crawfish-dash` (Tauri-shelled React UI), `crawfish-orgctl` (MCP server), `crawfish-opt` (browser optimizer), `crawfish-opt-codebase` (codebase optimizer, 3.25× token reduction on bench).

### Diagnoses engine (8 rules live)
- `oversized-tool-result`
- `re-read-loops`
- `low-cache-hit-rate`
- `dom-dump-detected`
- `log-truncation-pattern`
- `thinking-overhead`
- `grep-then-read-storms`
- `agent-fanout-cost`

### Runtime adapters (4 providers)
- `claude-code` · `claude-api` · `openai-api` · `codex` · OpenClaw (only non-Claude adapter shipped)

### Org templates (6 scaffolded)
- `startup` · `dev-shop` · `support` · `research` · `solo-builder` · `blank`

### Wizards (3 partial)
- `first-run` · `policy` · `prep`

---

## 2 · Task board — the NOW slice (shipped this session, v0.3)

### Cycles, epics, activity feed (W1)
- Per-project cycles in `.crawfish/cycles/*.md` with token-budget rollup `{planned, spent, remaining, slipped}`.
- Epics as open-ended task groupings (`.crawfish/epics/*.md`) with rollup computed dynamically from member tasks.
- Activity feed: every mutation appends to `.crawfish/board.jsonl` with actor + timestamp; events include `task_*`, `cycle_*`, `epic_*`, `criterion_*`, `task_assigned`, `task_linked`, `budget_breach`.
- Dashboard routes: **Board · Cycles · Epics · Activity · Plan · Roadmap**.

### Acceptance criteria + token budget (W2)
- `criteria[]` on every task. 5 kinds: `behavioral | test | metric | preflight | manual`.
- Each criterion carries optional `evidence: { kind, ...kind-specific fields }`.
- **Done-transition guard**: tasks cannot move to `done` while any criterion lacks evidence — rejects with `criteria_unmet: [criterion_ids]`.
- Per-task live token-budget bar. Color tiers: gray <50%, amber 50–80%, orange 80–100%, red 100%+ (visual cap 110% with "OVER" label).
- Auto-escalate at ≥100%: emits `budget_breach` event, flips task status to `escalated`.
- Agent preflight self-attestation via `preflight_attest` MCP tool — agent records that prep work happened before consequential calls.

### Capability-matched routing + AI triage + auto-decomposition (W3)
- Rolling 30-day stats per `(agent, label)`: `success_rate` + `avg_tokens_per_task` reconstructed from board events.
- Router cron picks cheapest agent with `success_rate > 0.7`; tie-breaks by least-loaded then deterministic agent id.
- Triage column (leftmost on Board) with raw/proposed visual variants + low-confidence "Needs review" badge (<0.6).
- Triage + planner agent templates preinstalled (`_agents/triage/`, `_agents/planner/`).
- Auto-decomposition: epic-tagged tasks get a planner proposal of subtask DAG; UI renders accept/reject diff + one-click "Approve all".
- Inbound channel adapters: **GitHub** wired (uses `gh` CLI with injectable wrapper); email, Notion-form, Slack-handoff are `not_configured` stubs awaiting credentials.

### Linked-task graph + structured search (W4)
- 5-kind task links: `blocks` / `depends_on` / `duplicates` / `relates_to` / `subtask_of`.
- Reciprocal-edge auto-management: `blocks ↔ depends_on`; `duplicates` + `relates_to` reflexive; `subtask_of` one-way.
- **LinkGraph** in task drawer — pure SVG concentric rings rendering depth-≤2 neighborhood, edges colored by kind, click-to-navigate.
- **FTS5 search** over board events at `~/.crawfish/<sha1>/search.db` (porter unicode61 tokenizer); in-memory fallback when `node:sqlite` is absent.
- **Structured query parser**: `assignee:engineer-1 label:bug priority>=high cycle:current free text` — recognized keys, `:` / `>=` / `<=` / `>` / `<`, priority ordering `low<med<high<critical`, `cycle:current` resolves to active cycle.
- ⌘K SearchBar with typeahead, debounced (150ms) live count, top-10 hit list, Enter applies as Board filter, composes with existing assignee/label/text filters.
- **External-ref round-trip**: GitHub issues mirror task status back via `gh` — `to: doing` comments, `to: done` closes, `from: done → other` reopens. Notion pages ingestion is a `not_configured` stub. Crawfish remains authoritative.

### Templates breadth + multi-org + stats + capacity (W5)
- `dev-shop` preinstalls triage + planner members and a daily-standup cron.
- `support` template wires `inbound_email_ingest` to `tier-1`.
- `research` template ships 4 members + paper-digest cron.
- **DescribeOrgWizard** — 4-question deterministic onboarding (org work / team size / work kind / stage) → synthesizes `org.json` with diff preview against nearest template.
- **OrgSwitcher** top-bar dropdown with `⌘O` toggle, checkmark on active, `crawfish:lastOrgId` localStorage persistence with legacy-key migration.
- **Stats endpoint** (`stats_get`): `view=dev` returns `{tokens_by_agent, tokens_by_tool, success_rate}`; `view=product` returns `{completion_rate, escalation_rate, tasks_by_status}`. 30-day rolling window; NaN-guarded.
- **Cycle planner** per-agent capacity row under each active cycle (color signal currently informational — see Known Defects).
- **7 industry overlays** under `desktop/dash/src/templates/_overlays/`: `b2b-saas`, `consumer-mobile`, `agency`, `e-commerce`, `content-studio`, `dev-tools`, `vertical-ai`. Merge engine `applyOverlay` is pure, append-only, throws on member-id collision.

---

## 3 · MCP tool surface (agent-callable)

Registered in `cli/orgctl/src/index.ts`:

**Board core:**
- `board_list_tasks` · `board_create_task` · `board_update_task` · `board_comment`
- `org_fs_list` · `org_fs_read` · `org_fs_write`

**Activity (W3 of prior phase):**
- `activity_*` (record / list / mentions)

**NOW-W2 — acceptance criteria + budget + preflight:**
- `preflight_attest` — agent self-attestation before consequential actions
- `criteria_set` — replace task's criteria array
- `criteria_attest` — set evidence on a single criterion
- `task_budget_report` — agent reports observed spend, server decides escalate

**NOW-W3 — triage + planner + inbound:**
- `triage_normalize` — heuristic shaping of raw inbound into `{title, labels, priority, criteria, triage_confidence}`
- `planner_decompose` — produces subtask DAG with `depends_on` edges
- `inbound_github_ingest` — `gh issue view --json` → task with `external_ref`

**NOW-W4 — external-ref + search:**
- `inbound_github_mirror` — mirror task status back to GitHub (close / comment / reopen)
- `inbound_notion_ingest` — stub (not_configured)
- `task_link_add` · `task_link_remove` — reciprocal-edge link management
- `tasks_search` — FTS5 + structured query

**NOW-W5:**
- `stats_get` — dev or product analytics
- `agent_stats_get` — per-agent rolling 30-day stats
- `router_run` — manual one-shot router pass

---

## 4 · Token discipline — optimizer subprojects

- `crawfish-opt` — browser optimizer (MCP server reducing DOM dump tokens)
- `crawfish-opt-codebase` — codebase optimizer, **3.25× token reduction** on bench
- `opt-logs` — Week 7 (not yet built)
- `opt-artifact` — Week 7 (not yet built)

---

## 5 · CLI surface (`crawfish-projectctl`)

Verbs in `cli/projectctl/src/verbs/`:
- Project init/refresh/status/doctor
- Task CRUD (via single-writer `tasks.ts`)
- Cycle CRUD + rollup
- Epic CRUD + rollup
- `board:rebuild` (recover from journal)
- `agent:stats <id>` (W3)
- `router:run` (W3)
- `link:add` / `link:remove` (W4)
- `search <query>` (W4)
- `stats` (W5)
- `decision:add` / `memory:append` / `activity:record`
- `install-hooks` / `uninstall-hooks`

---

## 6 · Architectural invariants

- **ADR-001 single-writer**: every `.crawfish/tasks/*.md` mutation goes through `cli/projectctl/src/tasks.ts`. Direct FS writes are forbidden.
- **Append-only event log**: `.crawfish/board.jsonl` is the rebuildable audit trail; `.md` files are canonical, jsonl is the derived journal.
- **Type-safe ULIDs**: `cyc_*` cycles, `epc_*` epics, `task_*` tasks.
- **Optimizer contract v1.0**: every MCP tool response stamps `tokens_used` (byte-estimator); errors return `{tokens_used: 0, error: {code, message}}`.
- **All network binds to `127.0.0.1`**.

---

## 7 · Known defects (flagged in `v0.3` tag annotation)

1. **Plan capacity row math is self-referential.** The 30-day rolling avg falls back to a per-cycle computation (`planned / 30`), so the "over capacity" color always lights up when any plan exists. Needs a real lens-side rolling-sum endpoint surfaced through the dash HTTP client before the signal is trustworthy.
2. **Lens-side criteria REST routes not implemented.** Orgctl's `criteria_set` / `criteria_attest` tools hit `PATCH /api/orgs/:id/board/tasks/:tid/criteria` (inferred shape); the lens server hasn't landed these yet, so live calls 404 until that route ships.
3. **`escalated` status is a forward-compat sentinel** in `stats.ts`. Rates parse the string off `task_status_changed` payloads but `TaskStatus` doesn't include it in the static union — math degrades to 0 today and lights up once the budget-breach event ships in production usage.
4. **UI not browser-verified.** All dash work this session tsc-clean only. Manual walk via `npm --prefix desktop/dash run dev` is the gate before alpha.

---

## 8 · What's NOT shipped yet

Per ROADMAP horizon — these are not in the codebase:

**NEXT (Weeks 6–10):** RAG indexing (`sqlite-vec` + `transformers.js`) + Knowledge tab · `opt-logs` + `opt-artifact` submodules · founder-dash polish · v0.4 alpha cut.

**LATER (Weeks 11–16):** preinstalled skill backbone · agentic-OS surfaces (`bin/`, `crontab`) · local Codespaces (Docker + devcontainer) · Crawfish IDE v0.1 · LLM Wiki + Obsidian sync · cron recipes + cost-manager agent.

**Parallel track:** marketing site + authed web dashboard + collaboration (CRDT) + team mode.

**LATER² (Weeks 17–28):** native code review (P6) · CI integration · visual-auditor · runtime adapters (Cursor, SDK) · CRDT + git-worktree filesystem.

**Stage 2 (months 9–24):** hosted servers · Pilot Protocol on Crawfish · RL training of agent-first models · multi-user identities · manager-grade employee analytics · 24/7 issue tracking · org knowledge layer at scale · advanced agent generation · AI automations marketplace · pricing posture.

**Stage 3 (months 18+):** enterprise compliance · audit trail · regulated industries.
