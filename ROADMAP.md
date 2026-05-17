# Crawfish — Development Roadmap

> **Concrete, week-shaped plan to ship the Grand Plan.** Every item is a single named deliverable with files, definition-of-done, and dependency. No prose. If a feature is not on this list with a phase and a DoD, it is not being built.
>
> Source of vision: [`GRAND_PLAN.md`](./GRAND_PLAN.md). This file is the build schedule.
>
> Companion docs: [`PRODUCT.md`](./PRODUCT.md) · [`DESIGN.md`](./DESIGN.md) · [`INTEGRATIONS.md`](./INTEGRATIONS.md) · [`BRAINSTORM.md`](./BRAINSTORM.md) · [`AGENT-TEAMS.md`](./AGENT-TEAMS.md).

Last updated: 2026-05-16.

---

## 0 · Status snapshot (2026-05-16)

### Shipped
- `crawfish-lens` — JSONL reader, REST + SSE, 8 diagnoses rules, OpenClaw adapter.
- `crawfish-dash` — Tauri shell, Sessions / Agents / Plan / Board / Compare / Settings / HomeDashboard / Analytics tabs.
- `crawfish-org` v1 — on-disk org at `~/.crawfish/orgs/<id>/`, board JSONL, files REST, crons daemon, dual analytics.
- `crawfish-orgctl` — MCP server, `board_*` and `org_fs_*` tools, contract-compliant.
- `crawfish-opt` v0.2 — browser optimizer, Haiku summarizer, zone-based DOM index.
- `crawfish-opt-codebase` v0.1 — 3.25× token reduction on benchmark.
- **P4.1 — Multi-LLM runtimes (`claude-code` / `claude-api` / `openai-api` / `codex`)** wired into cron dispatch.
- **P4.3 — GitHub bridge (read-only via `gh` CLI)** — issues + PRs surfaced per org.
- **P4.2 partial** — knowledge-sources registry (CRUD on `org.json.knowledge_sources`); RAG indexing deferred.
- Theme system, Settings → Appearance / Runtimes / Integrations, font/sidebar refinement.

### Open from prior phases (carry-overs)
| Carry-over | Owner | Phase folded into |
|---|---|---|
| RAG indexing (`sqlite-vec` + `transformers.js`) | lens | P4.2-finish (week 1 of "Now") |
| Cycles + epics on the board | lens + dash | P3-finish |
| Member ACL on board events | lens | P3-finish |
| Activity feed per task | lens + dash | P3-finish |
| `dev-shop` / `support` / `research` template bodies | dash | P3-finish |
| Stats endpoint server-side | lens | P3-finish |
| Multi-org switcher in shell | dash | P3-finish |

---

## 1 · Build schedule at a glance

```
Now    (weeks  1–5) → Linear-grade agent board (P3 fully) — better than Linear for agent-native orgs
Next   (weeks 6–10) → P4.2-finish (RAG) + token-discipline pack + founder-dash polish ──► Stage-1 demo
Later  (weeks 11–16)→ P5: Skills, IDE v0, Codespaces local, LLM Wiki        ──► Engineer-IC daily driver
Later² (weeks 17–28)→ P6: Review, CI, CRDT, web-proxy, hosted opt-in        ──► Team-mode foundations

⟂ Parallel (weeks 6–16) → crawfish.dev — marketing/download portal → web dashboard → collaboration → team mode/billing

Stage 2 (m9–m24)   → §4 of GRAND_PLAN — hosted, RL fine-tunes, RBAC
Stage 3 (m18+)     → §5 of GRAND_PLAN — enterprise, SOC2, on-prem
```

**Reprioritized 2026-05-17:** the "Now" slice now ships the Linear-comparable feature set (cycles, AI triage, auto-decomposition, capability-matched routing, linked-task graph, FTS5 search, acceptance-criteria evidence, external-ref ingestion) ahead of RAG and optimizers. Rationale: the issue-tracker is the front door — every other Stage-1 feature (founder dash, crons, analytics) reads off this board, so making it best-in-class first compounds. RAG (week 1 previously) becomes a NEXT-week deliverable; optimizers + founder-dash polish move to NEXT alongside it.

Each week below is **one named sprint** with a single completion gate. Weeks slip if their gate slips; nothing downstream starts until the gate is green.

---

## NOW · Weeks 1–5 — Linear-grade agent board

**Outcome:** Crawfish's native task board ships the full Linear-for-Agents feature set and goes beyond it: agents are first-class members with capability-matched routing, every inbound channel triages into the board automatically, epics auto-decompose, acceptance criteria carry structural evidence, the linked-task graph is rendered in the drawer, and FTS5 structured search matches Linear's idiom. From this week's slice onward, the board is the front door — founder dash, crons, analytics, and RAG all read off it.

**Why this order:** GRAND_PLAN §3.2 calls out Linear as "the canonical example of agents as first-class workspace members and the bar we have to beat." Every Stage-1 persona (founder, small CEO, engineer IC, manager) lists §3.2 as a T1 feature. Shipping it first means every later week compounds on a board that's already correct.

### Week 1 — Cycles, epics, activity feed, member ACL

**Gate:** From the Plan tab, drag tasks into a named cycle, see token-budget rollup; on the Board, every transition appears in the per-task activity feed with actor + timestamp. Board rejects events from unknown members with `invalid_member`.

| # | Deliverable | Files | DoD |
|---|---|---|---|
| 1.1 | Cycle + epic schema | `crawfish-lens/src/server/types.ts`, `docs/specs/org-contract.md` | `cycles.json` per org; tasks gain `cycle_id`, `epic_id`. Schema documented. |
| 1.2 | Cycles REST | `crawfish-lens/src/server/cycles.ts` | `GET/POST /api/orgs/:id/cycles`, `PUT/DELETE /:cycle_id`. Returns budget rollup `{planned, spent, remaining, slipped}`. |
| 1.3 | Activity feed | `crawfish-lens/src/server/activity.ts` | New event kinds: `status_changed`, `assigned`, `linked`, `labeled`, `budget_breach`. Stored inline in `board.jsonl`. |
| 1.4 | Plan tab — cycle picker | `crawfish-dash/web/src/routes/Plan.tsx` | Drag-rank within column; cycle drop-zone; budget bar at the top; over-capacity warning per agent. |
| 1.5 | Board — activity drawer | `crawfish-dash/web/src/components/TaskDrawer.tsx` | Activity feed panel under acceptance criteria; collapsible. |
| 1.6 | Member ACL | `crawfish-lens/src/server/board.ts:validateActor` | `appendEvent` rejects `by` / `assignee` not in `org.json.members`. 400 `invalid_member` w/ list of valid ids. Primary-assignee + contributor model: when an agent is added to a human's task, the agent lands as `contributor`, the human stays `assignee`. |
| 1.7 | Tests | `crawfish-lens/test/{cycles,activity,board-acl}.test.ts` | Cycle CRUD + budget math; activity reflects every state change; ACL rejects unknown actor; happy-path passes. |

### Week 2 — Acceptance criteria evidence + token-budget live bar + agent preflight

**Gate:** A task cannot transition to `done` unless every acceptance criterion carries evidence; the task drawer renders a live token-burn bar; at 100% the task auto-escalates, and any agent acting on the task runs a preflight self-attestation ("I have $X budget left, am I confident?").

| # | Deliverable | Files | DoD |
|---|---|---|---|
| 2.1 | Acceptance-criteria schema | `crawfish-lens/src/server/types.ts`, `docs/specs/org-contract.md` | `criteria: [{id, statement, kind: "test"|"manual"|"spec_match", evidence?: string}]`. Schema documented. |
| 2.2 | `done` transition guard | `crawfish-lens/src/server/board.ts:validateDoneTransition` | Rejects with `criteria_missing_evidence: [criterion_ids]` if any criterion lacks evidence. |
| 2.3 | Drawer — criteria editor + evidence chip | `crawfish-dash/web/src/components/TaskDrawer.tsx` | Add/remove criteria; per-criterion evidence input; kind selector; visual "needs evidence" badge. |
| 2.4 | Token-budget live bar | `crawfish-dash/web/src/components/TaskBudgetBar.tsx` + drawer | Reads SSE token stream; renders 0–100%+; color shifts at 80/100. |
| 2.5 | Auto-escalate at 100% | `crawfish-lens/src/server/board.ts:onBudgetBreach` | At ≥100%, emits `budget_breach` event, flips task to `escalated`, notifies primary assignee. |
| 2.6 | Agent preflight self-attestation | `crawfish-orgctl/src/preflight.ts` + tool wrapper | Before any tool call on a budgeted task, agent receives `{budget_remaining_cents, confidence_required: true}` injected into context; logs a `preflight_attested` event. |
| 2.7 | Tests | `crawfish-lens/test/{criteria,budget,preflight}.test.ts` | Done blocked without evidence; budget bar math; preflight event logged. |

### Week 3 — Capability-matched routing + AI triage column + auto-decomposition

**Gate:** Tasks created without an assignee are auto-routed within 30s to the cheapest agent with success_rate > threshold for the matching label; inbound issues from GitHub/email/Notion land in a `Triage` column and get rewritten into the structured schema; tasks tagged `epic` spawn a planning agent that proposes a subtask DAG the human approves in one click.

| # | Deliverable | Files | DoD |
|---|---|---|---|
| 3.1 | Capability stats per agent | `crawfish-lens/src/server/agent-stats.ts` | Rolling 30-day `success_rate` and `avg_tokens_per_task` keyed by `label`. Exposed via `GET /api/orgs/:id/agents/:id/stats`. |
| 3.2 | Router cron | `crawfish-lens/src/server/router.ts` + crons | Picks lowest-`avg_tokens_per_task` agent with `success_rate > 0.7`; ties broken by least-loaded. Writes `assigned` event w/ `by: "router"`. |
| 3.3 | Triage column + agent | `crawfish-dash/web/src/routes/Board.tsx`, `crawfish-dash/src/templates/_agents/triage/{member.md,policy.json}` | New leftmost column "Triage". Triage agent (preinstalled in every template) rewrites raw inbound into `{title, labels, priority, criteria}`; pings human watcher only on low-confidence (<0.6). |
| 3.4 | Inbound channel adapters | `crawfish-lens/src/server/inbound/{github-issues,email,notion-form,slack-handoff}.ts` | Each adapter normalizes inbound into a `task_created` event with `external_ref` set. GitHub via existing `gh` bridge. |
| 3.5 | Auto-decomposition planner | `crawfish-lens/src/server/planner.ts`, `crawfish-dash/src/templates/_agents/planner/` | Task tagged `epic` fires the planner agent; output is a proposed subtask list w/ `depends_on` edges; rendered in drawer as accept/reject diff. |
| 3.6 | Decomp approval UI | `crawfish-dash/web/src/components/DecompositionDrawer.tsx` | Side-by-side: proposed subtasks, dependency graph preview, per-subtask edit, one-click "approve all". |
| 3.7 | Tests | `crawfish-lens/test/{router,triage,planner}.test.ts` + fixture inboxes | Router picks expected agent on 6 fixtures; triage normalizes 4 inbound shapes; planner decomposes 3 fixture epics. |

### Week 4 — Linked-task graph + FTS5 structured search + external-ref ingestion

**Gate:** Task drawer renders a force-directed graph of `blocks` / `depends_on` / `duplicates` / `relates_to` / `subtask_of`; clicking a node navigates the drawer. A structured-query bar at the top of the Board parses Linear-shaped queries (`assignee:engineer-1 label:bug priority>=high cycle:current`) and filters live. GitHub issues and Notion pages round-trip with `external_ref`.

| # | Deliverable | Files | DoD |
|---|---|---|---|
| 4.1 | Link types in schema + REST | `crawfish-lens/src/server/types.ts`, `crawfish-lens/src/server/board.ts` | `links: [{kind, target_task_id}]` with the 5 kinds. `POST /api/orgs/:id/tasks/:id/links`, `DELETE …/links/:link_id`. Reciprocal edges auto-managed. |
| 4.2 | Force-directed graph in drawer | `crawfish-dash/web/src/components/LinkGraph.tsx` (D3 or vis-network) | Renders neighborhood of current task (depth ≤2); click navigates; edge color per link kind. |
| 4.3 | FTS5 search index | `crawfish-lens/src/server/search.ts` | SQLite FTS5 over `board.jsonl` events: task title, description, criteria, comments, labels. Rebuild-on-load + incremental insert on append. |
| 4.4 | Structured-query parser | `crawfish-lens/src/server/search.ts:parseQuery` | Parses `key:value` and `key>=value` for {assignee, label, priority, status, cycle, epic}; falls through to FTS5 for free text. |
| 4.5 | Board search bar | `crawfish-dash/web/src/components/SearchBar.tsx`, mount in `Board.tsx` | ⌘K opens; typeahead for keys + values; filter result count in real time. |
| 4.6 | External-ref ingestion | `crawfish-lens/src/server/inbound/github-issues.ts` (extend), `…/notion-pages.ts` | GitHub issue or Notion page → task with `external_ref: {kind, id, url}`. Mirror updates back to the source on `status_changed` and `done`. Crawfish is authoritative. |
| 4.7 | Tests | `crawfish-lens/test/{links,search,external-ref}.test.ts` | Link reciprocity; 8 search-query fixtures parse correctly; GitHub issue round-trip on a real test repo. |

### Week 5 — Templates breadth + multi-org switcher + stats + cycle planner polish

**Gate:** From Home, create an org from each of 6 templates; multi-org switcher in shell; Analytics page loads via single `GET /api/orgs/:id/stats?view=dev|product`; cycle planner view shows over-capacity agents per cycle.

| # | Deliverable | Files | DoD |
|---|---|---|---|
| 5.1 | `dev-shop` template body | `crawfish-dash/src/templates/dev-shop/{org.json,members/*.md,crons.json,files/*}` | 5 members (PM, FE eng, BE eng, code-review, QA); 3 seed tasks; 1 cron. Triage + planner agents preinstalled. |
| 5.2 | `support` template body | `crawfish-dash/src/templates/support/*` | 3 members (tier-1, escalation, handoff-human); ticket-triage cron; email inbound wired. |
| 5.3 | `research` template body | `crawfish-dash/src/templates/research/*` | 4 members (lead + 3 specialists); paper-digest cron. |
| 5.4 | Industry overlay scaffold | `crawfish-dash/src/templates/_overlays/{b2b-saas,consumer-mobile,agency,e-commerce,content-studio,dev-tools,vertical-ai}.json` | Merge logic in `crawfish-orgctl/src/templates/apply.ts`. Overlays add members + skills, never rename existing roles. |
| 5.5 | "Describe my org" wizard | `crawfish-dash/web/src/wizards/describe/index.tsx` | 4 questions → runtime call → synthesized `org.json` + members preview → diff vs nearest template → user accepts. |
| 5.6 | Multi-org switcher | `crawfish-dash/web/src/components/OrgSwitcher.tsx`, mount in `cf-toolbar` | Top-bar dropdown, keyboard `⌘O`, lists orgs from `GET /api/orgs`, persists last-selected. |
| 5.7 | Stats endpoint | `crawfish-lens/src/server/stats.ts` + route | `GET /api/orgs/:id/stats?view=dev` returns `{tokens_by_agent, tokens_by_tool, success_rate}`; `view=product` returns `{completion_rate, escalation_rate, tasks_by_status}`. |
| 5.8 | Cycle planner over-capacity view | `crawfish-dash/web/src/routes/Plan.tsx` | Per-agent capacity row; red when planned tokens > 30-day avg × 1.5. |
| 5.9 | Tests | `crawfish-lens/test/{templates,stats}.test.ts` | Each template loads cleanly; stats response shape stable. |

**End-of-Now milestone:** Cut a `v0.3` tag across umbrella + each submodule. Push to remote. The board is now demonstrably better than Linear for an agent-native org — every persona's T1 from GRAND_PLAN §3.2 is live.

---

## NEXT · Weeks 6–10 — RAG, optimizers, founder-dash polish (Stage-1 demo gate)

**Outcome:** Now that the board is Linear-grade, layer on the knowledge layer, the token-discipline optimizer pack, and the founder dashboard — and ship the Stage-1 demo. A founder hits "5 working agents + 1 cron firing + RAG citations on a real repo" in ≤15 minutes from `git clone`.

### Week 6 — RAG indexing + Knowledge tab

**Gate:** `knowledge_query` returns top-5 chunks with citations from a 500-file repo, ≤200ms. Knowledge tab renders sources, query box, top-5 hits.

| # | Deliverable | Files | DoD |
|---|---|---|---|
| 6.0a | Install `better-sqlite3` + `sqlite-vec` + `@xenova/transformers` in lens | `crawfish-lens/package.json` | `npm i` clean, vec extension loadable on macOS arm64. |
| 6.0b | `RagIndex` module | `crawfish-lens/src/knowledge/{index,chunker,embed}.ts` | Chunks markdown 800-char windows w/ 200 overlap; embeds via `Xenova/all-MiniLM-L6-v2`; persists to `~/.crawfish/orgs/<id>/knowledge.sqlite`. |
| 6.0c | Wire `GET /api/orgs/:id/knowledge/query` to real chunks | `crawfish-lens/src/server/knowledge.ts` | Returns `{chunks: [{source_id, path_or_url, chunk_text, score}], note?}`. |
| 6.0d | Ingest pipeline | `crawfish-lens/src/server/knowledge.ts:handleIngest`, `POST /api/orgs/:id/knowledge/sources/:source_id/ingest` | Crawls `files` and `repo` sources; skips binary; tracks last-mtime per file. |
| 6.0e | Knowledge tab in dash | `crawfish-dash/web/src/routes/Knowledge.tsx`, route `/orgs/:id/knowledge` | Lists sources w/ last-ingest timestamp, query box, top-5 results with file/line. |
| 6.0f | Tests | `crawfish-lens/test/knowledge.test.ts` | Ingest 50 md files, query returns expected file in top-3 on 10 fixture queries. |

**Risk:** `sqlite-vec` prebuilds may not exist for every Node ABI. Mitigation: pin Node 20, ship a fallback `IndexedDB`-equivalent that's only the cosine path — slower but works.

### Week 7 — Token-discipline optimizer pack

**Gate:** Two new optimizers shipped with benchmarks; the diagnoses engine recommends them automatically when their pattern fires.

| # | Deliverable | Files | DoD |
|---|---|---|---|
| 7.1 | `crawfish-opt-logs` v0.1 | `crawfish-opt-logs/` (new submodule) | Tools: `logs_summarize`, `logs_grep`, `logs_tail_smart`. Benchmark: 10 log dumps. Target ≥4× reduction on truncation cases. |
| 7.2 | `crawfish-opt-artifact` v0.1 | `crawfish-opt-artifact/` (new submodule) | Wraps big-payload returns into `{artifact_id, summary, next_action}`; payload to `~/.crawfish/artifacts/<id>`. |
| 7.3 | Diagnoses engine — recommend by tool match | `crawfish-lens/src/diagnoses/tool-optimizer-map.ts` | `Bash:log-truncation` → `opt-logs`; `WebFetch:large-payload` → `opt-artifact`. |
| 7.4 | Optimizers tab — install state | `crawfish-dash/web/src/routes/optimizers.tsx` | Per-optimizer card shows install state via `which` check; copy-install command. |
| 7.5 | Benchmark runner | `scripts/bench-optimizer.ts` | `node scripts/bench-optimizer.ts opt-logs` prints baseline vs optimized tokens. |

### Week 8 — Founder dashboard polish + acceptance demo

**Gate:** Home dashboard shows yesterday's cost, top sinks, compounding factor, diagnoses inbox, and live session strip. `scripts/smoke-15min.ts` is green in CI.

| # | Deliverable | Files | DoD |
|---|---|---|---|
| 8.1 | "What it cost me yesterday" widget | `crawfish-dash/web/src/routes/HomeDashboard.tsx`, `…/lib/spend.ts` | Reads `GET /api/orgs/:id/stats?view=dev&since=24h`; top-3 sinks by agent. |
| 8.2 | Live session strip | `crawfish-dash/web/src/components/LiveSessionStrip.tsx` | SSE row per in-flight session; emergency-stop button POSTs `/api/sessions/:id/stop`. |
| 8.3 | Compounding-factor KPI | `crawfish-lens/src/stats.ts:computeCompoundingFactor` + HomeDashboard | Per-session ratio + 7-day trend line. |
| 8.4 | Diagnoses inbox | `crawfish-dash/web/src/routes/HomeDashboard.tsx` (new section) | Lists every fired rule; click-to-fix invokes recommended action. |
| 8.5 | "15-minute install" smoke test | `scripts/smoke-15min.ts` | Headless: install, pick template, fire cron, assert board event. CI green required. |
| 8.6 | Demo video | `docs/demo-stage1.mp4` | 5-minute walkthrough. Ship-blocker until recorded. |

### Weeks 9–10 — Buffer + alpha-readiness

Reserved for slip from weeks 1–8, alpha invitee onboarding, telemetry opt-in plumbing, and any P3-finish carry-overs.

**End-of-Now-extended milestone:** Cut a `v0.4` tag. Open external alpha (≤20 invitees).

---

## LATER · Weeks 11–16 — Stage 1 IDE & filesystem layer

**Outcome:** Engineer-IC persona has a daily-driver IDE, agents run in isolated Codespaces, and the org filesystem is a real knowledge wiki with concurrent-write safety.

### Week 11 — Skill backbone (first half)

**Gate:** 6 skills callable from any runtime via the orgctl MCP server; each is documented and benchmarked.

| # | Deliverable | Files |
|---|---|---|
| 6.1 | `~/.crawfish/skills/` layout + loader | `crawfish-orgctl/src/skills/loader.ts` |
| 6.2 | `skill.docx`, `skill.xlsx`, `skill.pptx` (Cowork-wrapped) | `crawfish-orgctl/src/skills/{document,spreadsheet,presentation}/SKILL.md + impl.ts` |
| 6.3 | `skill.pdf.fillform` | `crawfish-orgctl/src/skills/pdf-fillform/` |
| 6.4 | `skill.email.draft` (uses `org-fs/knowledge/voice/`) | `crawfish-orgctl/src/skills/email-draft/` |
| 6.5 | `skill.calendar.schedule` | `crawfish-orgctl/src/skills/calendar/` |
| 6.6 | Skills tab in dash (browse + install per-org) | `crawfish-dash/web/src/routes/Skills.tsx` |

**DoD:** Each skill ships with `SKILL.md` + a unit-fixture test that calls it through orgctl and asserts the output shape.

### Week 12 — Skill backbone (second half) + Agentic-OS surfaces

**Gate:** `crawfish journal -u <agent-id> --since 1h` prints the agent's journal; `crawfish crontab -e` opens an editor.

| # | Deliverable | Files |
|---|---|---|
| 7.1 | `skill.web.research` | `crawfish-orgctl/src/skills/web-research/` |
| 7.2 | `skill.code.review` + `skill.code.test` + `skill.code.visualAudit` | `crawfish-orgctl/src/skills/code-{review,test,visualAudit}/` |
| 7.3 | `skill.brand.image` + `skill.crm.touch` + `skill.org.standup` + `skill.bench.regress` | `crawfish-orgctl/src/skills/{brand-image,crm-touch,org-standup,bench-regress}/` |
| 7.4 | `~/.crawfish/bin/` shim — agents-as-executables | `crawfish-orgctl/src/bin/install.ts`, `crawfish-orgctl/src/bin/run.ts` |
| 7.5 | `crawfish journal` + `crawfish crontab` CLI | `crawfish-orgctl/src/cli/{journal,crontab}.ts` |
| 7.6 | `~/.crawfish/proc/<agent-id>/status` virtual file | `crawfish-orgctl/src/proc.ts` |

### Week 13 — Local Codespaces (Docker + Devcontainer)

**Gate:** `crawfish space create eng-agent-1 && crawfish space exec eng-agent-1 -- npm test` works; container has `org-fs/` mounted, agent's policy bundle loaded, MCP tools wired.

| # | Deliverable | Files |
|---|---|---|
| 8.1 | `crawfish space` CLI | `crawfish-orgctl/src/cli/space.ts` |
| 8.2 | Devcontainer template per template | `crawfish-dash/src/templates/<t>/devcontainer/devcontainer.json` |
| 8.3 | Resource caps (cgroups Linux, launchd profile macOS) | `crawfish-orgctl/src/space/limits.ts` |
| 8.4 | Snapshot + branch (git worktree of the space) | `crawfish-orgctl/src/space/snapshot.ts` |
| 8.5 | Dash Spaces panel — list + open shell | `crawfish-dash/web/src/routes/Spaces.tsx` |
| 8.6 | E2E test | `crawfish-orgctl/test/space.e2e.ts` — full lifecycle |

### Week 14 — Crawfish IDE v0.1

**Gate:** VS Code extension installs from `.vsix`; sidebar shows Sessions + Agents + Board; PreToolUse hook fires in-editor; status bar shows live token meter.

| # | Deliverable | Files |
|---|---|---|
| 9.1 | Extension skeleton | `crawfish-ide/` (new repo) — TypeScript, package.json with VS Code engines |
| 9.2 | Crawfish sidebar (web view, reuses dash components) | `crawfish-ide/src/sidebar.ts`, `crawfish-ide/webview/` |
| 9.3 | PreToolUse hook integration | `crawfish-ide/src/hooks/preToolUse.ts` — registers as Claude Code hook |
| 9.4 | Status-bar token meter | `crawfish-ide/src/statusBar.ts` |
| 9.5 | Inline-comment agent dispatch (`// @agent code-review: …`) | `crawfish-ide/src/commands/dispatch.ts` |
| 9.6 | Publish to internal `vsix` registry | `scripts/publish-ide.sh` |

### Week 15 — LLM Wiki + Obsidian sync

**Gate:** `org-fs/knowledge/` renders as a wiki with backlinks, graph view, and "what would an agent retrieve for this query"; opening a vault in Obsidian shows the same files unchanged.

| # | Deliverable | Files |
|---|---|---|
| 10.1 | Markdown parser + backlink graph builder | `crawfish-lens/src/knowledge/wiki.ts` |
| 10.2 | Wiki tab — wikilink renderer + sidebar of backlinks | `crawfish-dash/web/src/routes/Wiki.tsx` |
| 10.3 | Force-directed graph view | `crawfish-dash/web/src/components/wiki/Graph.tsx` (D3) |
| 10.4 | "Retrieval preview" — paste query, see what RAG would return | `crawfish-dash/web/src/routes/Wiki.tsx` (retrieval panel) |
| 10.5 | Obsidian path setting | Settings → Integrations → "Use Obsidian vault at path …" |
| 10.6 | Chokidar watcher → re-index on edit | `crawfish-lens/src/knowledge/watcher.ts` |

### Week 16 — Cron recipes + dynamic model switching + cost-manager agent

**Gate:** Every template has the 7 cron recipes preinstalled; the cost-manager agent auto-pauses an agent that crosses 2σ of its 7-day baseline.

| # | Deliverable | Files |
|---|---|---|
| 11.1 | 7 cron recipes as JSON entries | `crawfish-dash/src/templates/_crons/{standup,token-review,backlog-groom,stale-sweep,friday-roundup,security-sweep,knowledge-digest}.json` |
| 11.2 | Cron run-now button | `crawfish-dash/web/src/routes/Crons.tsx` |
| 11.3 | Per-task model picker | `crawfish-lens/src/runtimes/router.ts` — chooses runtime + model from `task.label` and historical success rates |
| 11.4 | Trajectory cache | `crawfish-lens/src/runtimes/trajectories.ts` — writes successful trajectories to `org-fs/agent-memory/trajectories/<hash>.jsonl`; injects as hint on similar tasks |
| 11.5 | `cost-manager` agent template | `crawfish-dash/src/templates/_skills/cost-manager/SKILL.md + impl.ts` — preinstalled in every template; pause action via `crawfish-orgctl` |
| 11.6 | Tests | `crawfish-lens/test/router.test.ts`, `crawfish-lens/test/trajectories.test.ts` |

**End-of-Later milestone:** `v0.5` tag. Open Stage-1 public alpha. Begin telemetry collection (opt-in).

---

## PARALLEL TRACK · crawfish.dev — Web dashboard + collaboration (weeks 6–16, runs alongside NEXT/LATER)

**Outcome:** A hosted-static (free, no-account) marketing + download portal at `crawfish.dev` evolves into a logged-in **web dashboard** that mirrors the Tauri app's Board / Plan / Wiki / Analytics views for team collaboration — so a small CEO can invite teammates without forcing them to install the desktop app or the IDE. The desktop app and the IDE remain the power-user surfaces; the web dashboard is the social surface and the front door.

**Why it lives in its own track:** the desktop app, IDE, and web dashboard share lens APIs but ship from different repos and have different release cadences. Putting this in a parallel track keeps the NOW/NEXT slices honest about what blocks a Stage-1 demo (nothing here does — this is for collaboration, distribution, and team mode).

**Repo layout:**
```
crawfish-web/                # new repo — Next.js app router, deployed to Vercel
  app/(marketing)/           # public landing + download portal
  app/(dash)/                # authed web dashboard (mirrors Tauri tabs)
  app/api/auth/              # NextAuth (GitHub + Google + magic link)
  lib/lens-client.ts         # shared with crawfish-dash/web (extract into ui/)
```

### Track A — Marketing + download portal (weeks 6–7)

**Gate:** `crawfish.dev` is live with download buttons for the desktop app (macOS arm64/intel, Windows, Linux) and the VS Code extension (`.vsix` + Marketplace link), plus a "What is Crawfish?" tour pulling screenshots from the Tauri app.

| # | Deliverable | Files | DoD |
|---|---|---|---|
| W6-A.1 | Next.js scaffold + Vercel deploy | `crawfish-web/` (new repo) | `pnpm dev` and Vercel preview green; alias `crawfish.dev`. |
| W6-A.2 | Landing page — hero, three-pillar pitch (Board / FS / IDE), pricing teaser | `app/(marketing)/page.tsx` | Reuses `ui/` tokens; ≤80kB above-the-fold JS. |
| W6-A.3 | Download portal | `app/(marketing)/download/page.tsx`, `app/api/releases/latest/route.ts` | Reads latest release from `crawfish-app` GitHub Releases via `gh api`; auto-detects platform; presents `.dmg` / `.exe` / `.AppImage` direct links + checksums. |
| W6-A.4 | IDE download card | `app/(marketing)/download/ide/page.tsx` | Links to (a) VS Code Marketplace listing once published, (b) raw `.vsix` from `crawfish-ide` releases, (c) `code --install-extension` one-liner. |
| W7-A.5 | Tour / demo embed | `app/(marketing)/tour/page.tsx` | Embeds `docs/demo-stage1.mp4` + a clickable "open in web dashboard" CTA (gated until Track B ships). |
| W7-A.6 | OG cards, sitemap, robots | `app/(marketing)/{opengraph-image,sitemap,robots}.ts` | Lighthouse ≥95 across the board. |

### Track B — Authed web dashboard MVP (weeks 8–10)

**Gate:** Logged-in user can view their own org's Board, Plan, Wiki, and Analytics from the browser, pointed at their local lens via a secure tunnel; teammates with an invite token see the same view in real time.

| # | Deliverable | Files | DoD |
|---|---|---|---|
| W8-B.1 | Auth | `app/api/auth/[...nextauth]/route.ts` | NextAuth: GitHub + Google + email-magic-link. Session in JWT. |
| W8-B.2 | Lens-tunnel | `crawfish-lens/src/server/tunnel.ts`, `crawfish-web/lib/tunnel-client.ts` | User clicks "connect web" in desktop app → opens an outbound WebSocket to `wss://tunnel.crawfish.dev`; web dashboard talks REST/SSE through the tunnel. Auth via per-org-token signed by lens; no inbound port on user's machine. |
| W8-B.3 | Shared component extraction | `ui/components/{Board,Plan,TaskDrawer,Wiki,Analytics}/*` (move from `crawfish-dash/web/src/`) | One source of truth consumed by both Tauri shell and Next.js web. Type-checks in both. |
| W9-B.4 | Web Board + Plan + Drawer | `app/(dash)/orgs/[id]/{board,plan}/page.tsx` | Renders shared components against tunneled lens; live SSE updates. |
| W9-B.5 | Web Wiki | `app/(dash)/orgs/[id]/wiki/[[...path]]/page.tsx` | Reads `org-fs/knowledge/` via tunneled lens; backlinks + graph. |
| W10-B.6 | Web Analytics | `app/(dash)/orgs/[id]/analytics/page.tsx` | Dev + product views; same API as Tauri. |
| W10-B.7 | "Open in desktop" deep link | `app/(dash)/components/OpenInDesktop.tsx` | `crawfish://orgs/<id>/tasks/<id>` URI scheme registered by Tauri shell. |

### Track C — Collaboration features (weeks 11–13)

**Gate:** Multiple humans can edit the same task drawer concurrently without clobbering; @mentions notify by email; comments thread by task; presence avatars show who's looking.

| # | Deliverable | Files | DoD |
|---|---|---|---|
| W11-C.1 | Invite + member management | `app/(dash)/orgs/[id]/members/page.tsx`, `crawfish-lens/src/server/invites.ts` | Owner generates `invite_token` with role; invitee accepts via magic link; member appended to `org.json.members` with `humanity: "human"`. |
| W11-C.2 | Presence | `crawfish-lens/src/server/presence.ts` (SSE channel), `ui/components/PresenceAvatars.tsx` | Avatars on Board columns + drawer; idle ≥60s drops user. |
| W12-C.3 | Comments on tasks | `crawfish-lens/src/server/comments.ts`, `ui/components/CommentThread.tsx` | Markdown comments; @mentions parse to member ids; emitted as `task_commented` events. |
| W12-C.4 | Notifications | `crawfish-lens/src/server/notify.ts` (email via Resend), `app/(dash)/notifications/page.tsx` | @mention → email + in-app inbox; mute per-task; digest mode. |
| W13-C.5 | Concurrent-edit safety on drawer | Yjs-based CRDT on description + criteria fields (`ui/components/TaskDrawer.tsx`) | Two browsers editing same field merge without loss; offline → resync. Reuses the Yjs work from Week 25 (CRDT block) — pulled forward here for human collaboration; agent file CRDT still happens in §LATER². |
| W13-C.6 | Per-task watchers + subscriptions | `crawfish-lens/src/server/subscriptions.ts` | Watch a task → notifications on every event; subscribe to label / cycle / agent. |

### Track D — Team mode + paid tier hook (weeks 14–16)

**Gate:** Org owner can convert a personal org into a team org; billing collected via Stripe; humans count as seats, agents don't (mirroring Linear's policy from GRAND_PLAN §3.2).

| # | Deliverable | Files | DoD |
|---|---|---|---|
| W14-D.1 | Stripe customer + subscription | `crawfish-lens/src/server/billing.ts`, `app/api/billing/webhook/route.ts` | Free tier (1 owner, 5 agents), Team tier ($X/human/mo, unlimited agents). |
| W14-D.2 | Seat enforcement | `crawfish-lens/src/server/board.ts:enforceSeatLimit` | Adding a `humanity: "human"` member when over plan → 402 `seat_limit`; agents always allowed. |
| W15-D.3 | Settings → Billing tab (Tauri + web) | `ui/routes/Billing.tsx` | Stripe customer-portal redirect; current usage; upgrade CTA. |
| W15-D.4 | Audit log (web-only view) | `app/(dash)/orgs/[id]/audit/page.tsx` | Read-only feed of every governance-sensitive event (member added, policy changed, billing changed). |
| W16-D.5 | Public org pages (opt-in) | `app/(public)/o/[slug]/page.tsx` | Owner can mark an org public; the board renders read-only at `crawfish.dev/o/<slug>`. Used for OSS projects + demos. |

**End-of-parallel-track milestone:** `crawfish.dev/v1` — the marketing surface, the auth'd web dashboard, the collaboration features, and a working paid tier. This is what unlocks "small CEO with 5 humans + 30 agents" as a customer.

---

## LATER² · Weeks 17–28 — Stage 1 finish + Stage 2 prep

### Weeks 17–18 — Native code review (P6 start)

| # | Deliverable | Files |
|---|---|---|
| 12.1 | Repo connection (local git only) | `crawfish-lens/src/server/repo.ts` — watches `.git/refs/heads/` |
| 12.2 | Side-by-side diff viewer | `crawfish-dash/web/src/routes/Review.tsx` |
| 12.3 | Inline review comments + suggested edits | `crawfish-dash/web/src/components/review/Comment.tsx`, `…/Suggestion.tsx` |
| 12.4 | Agent reviewer hooks | `crawfish-orgctl/src/tools/review.ts` — `review_open_pr`, `review_read_diff`, `review_comment`, `review_approve`, `review_request_changes` |
| 12.5 | PR ↔ CrawfishTask link | `crawfish-lens/src/server/board.ts` — `linked_task_id` resolves both ways |
| 12.6 | Review on push (cron) | `crawfish-lens/src/server/crons.ts` — new built-in cron `review-on-push` |

### Weeks 19–20 — Test-generator + Visual-auditor agents (CI/CD)

| # | Deliverable | Files |
|---|---|---|
| 14.1 | Test-gen agent preinstall | `crawfish-dash/src/templates/_agents/test-generator/{member.md,policy.json}` |
| 14.2 | Visual-auditor agent preinstall | `crawfish-dash/src/templates/_agents/visual-auditor/…` |
| 14.3 | Native CI runner | `crawfish-lens/src/server/ci.ts` — watches PR branches, executes bench suite, posts a review comment |
| 14.4 | Token-regression gate | `crawfish-lens/src/server/ci.ts:assertNoRegression` — fails PR if bench tokens climb >20% |

### Weeks 21–22 — Agent-web proxy MVP (track B of §3.7)

| # | Deliverable | Files |
|---|---|---|
| 16.1 | Proxy daemon skeleton | `crawfish-proxy/` (new repo) — Node HTTP, bound 127.0.0.1, per-adapter routes |
| 16.2 | Stripe adapter | `crawfish-proxy/adapters/stripe/` — list customers / invoices / charges in token-thin JSON |
| 16.3 | GitHub adapter (UI flows beyond `gh` CLI scope) | `crawfish-proxy/adapters/github/` |
| 16.4 | Benchmark vs naive Playwright | `crawfish-proxy/bench/{stripe,github}.bench.ts` |
| 16.5 | Adapter contract doc | `crawfish-proxy/CONTRACT.md` |

### Weeks 23–24 — CRDT + git-worktree isolation (agent-side)

| # | Deliverable | Files |
|---|---|---|
| 18.1 | Yjs-based CRDT for markdown in `org-fs/knowledge/` | `crawfish-orgctl/src/crdt/yjs.ts` |
| 18.2 | Per-agent worktree provisioning | `crawfish-orgctl/src/worktree/spawn.ts` — `git worktree add` under `~/.crawfish/worktrees/<agent-id>/` |
| 18.3 | Lead-merges-back workflow | `crawfish-orgctl/src/worktree/merge.ts` — wraps `git merge --no-ff` and writes a `merge.jsonl` audit |
| 18.4 | Settings → Worktrees panel | `crawfish-dash/web/src/routes/Settings.tsx` (new sub-tab) |

### Weeks 25–27 — Communication-graph features (P3 finish + P5 extensions)

| # | Deliverable | Files |
|---|---|---|
| 20.1 | Org-level flow graph (cross-session) | `crawfish-dash/web/src/components/FlowGraph.tsx` — extend existing single-session view |
| 20.2 | Time scrubber | same file — `<input type=range>` over board.jsonl time index |
| 20.3 | Pattern detection — "Agent A only sends to B" + "siblings reading same file" | `crawfish-lens/src/diagnoses/rules/{pipeline-shape,shared-read-redundancy}.ts` |
| 20.4 | Drill-in to journey timeline | `crawfish-dash/web/src/components/JourneyTimeline.tsx` (already partial) |

### Week 28 — Stage 2 prep: hosted-mode dry-run + RL data export

| # | Deliverable | Files |
|---|---|---|
| 23.1 | Event-export pipeline (opt-in) | `crawfish-lens/src/server/export.ts` — JSONL of all org events to a user-supplied S3 bucket |
| 23.2 | Trajectory-dataset packer | `scripts/pack-trajectories.ts` — produces the substrate for §4.3 RL fine-tunes |
| 23.3 | Tenant-ID plumbing | `crawfish-lens/src/server/types.ts`, every appended event gains `tenant_id` |
| 23.4 | Hosted-mode spike doc | `docs/specs/hosted-mode.md` — concrete plan for Stage 2 week 1 |

**End-of-Later milestone:** `v0.9` tag. Public beta. Stage-2 build starts month 6.

---

## 2 · Workstream ↔ phase matrix

For navigation. Each GRAND_PLAN workstream maps to specific weeks above.

| GRAND_PLAN §  | Weeks | Status |
|---|---|---|
| 3.1 Templates | 5, 11 (overlays via skills) | active |
| 3.2 AI issue tracking — **Linear-grade board** | 1–5 (full); Stage 2 §4.6 for 24/7 triage | **active — front-loaded** |
| 3.3 Local agent FS | 6 (RAG), 15 (Wiki), 23 (CRDT agent-side) | active |
| 3.4 Skill backbone | 11, 12 | scheduled |
| 3.5 Crawfish IDE | 14 | scheduled |
| 3.6 Founder dash | 8 | scheduled |
| 3.7 Web for agents (track A) | 7 (logs optimizer); track B at 21 | mixed |
| 3.8 Local Codespaces | 13 | scheduled |
| 3.9 Agent CI/CD | 19 | scheduled |
| 3.10 Cron recipes | 16 | scheduled |
| 3.11 Token discipline | 7, 16 | active |
| 3.12 Comms graph | 1 (per-task activity), 25 (org-level) | mixed |
| 3.13 Dual analytics | 5, 8 | active |
| **NEW — Web dashboard + collab** (`crawfish.dev`) | Parallel Track 6–16 | **active** |
| ↳ marketing + download portal (links to app + IDE) | 6–7 | scheduled |
| ↳ authed web dashboard (tunneled lens) | 8–10 | scheduled |
| ↳ collaboration (presence, comments, CRDT drawer, @mentions) | 11–13 | scheduled |
| ↳ team mode + Stripe billing (humans = seats; agents free) | 14–16 | scheduled |

---

## 3 · Ownership & teamwork rules

Two-track work via the AGENT-TEAMS pattern. Lead agent owns the umbrella; teammates own one submodule each.

**Single-owner files (lead-only) — see [`CLAUDE.md`](./CLAUDE.md) for the full list.**

When fan-out exceeds one teammate per submodule, use `Agent({isolation: "worktree", …})` so each spawn lives in a worktree (lines up with the §18 CRDT/worktree work).

---

## 4 · Definition of done (project-wide)

Every PR must:
1. Type-check clean in every submodule it touches (`npx tsc --noEmit -p tsconfig.json`).
2. Run its submodule's vitest suite (`npm test` per submodule); CI gates the merge.
3. Add a fixture / test for new logic; never "see, it works" without a test.
4. Use existing design tokens — no new hex in components.
5. Update [`docs/specs/`](./docs/specs/) if it changes a schema.
6. Carry a one-line entry in this file's "Shipped" section when it merges.

---

## 5 · Risks & mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| `sqlite-vec` prebuilds drift on Node minor bumps | M | H (P4.2-finish gate) | Pin Node 20.18; vendor the binary in `vendor/sqlite-vec/` as escape hatch. |
| `transformers.js` cold-load is slow on first ingest | M | M | Spinner + progress in UI; cache the model under `~/.crawfish/cache/transformers/`. |
| Skill explosion → maintenance debt | M | M | Skill submission gate: must ship a bench fixture + a passing test. |
| Codespaces work blocked on Docker availability on user machines | L | M | Detect Docker on launch; fall back to plain process isolation with a warning banner. |
| Crawfish IDE adds VS Code-API surface we have to track | M | L | Pin a single VS Code engine version per `v` release; bump only on schedule. |
| Cron-driven runtime spend balloons during alpha | H | M | Cost-manager agent (week 11) ships before public alpha (end of week 11). |
| Two teammates clobber `crawfish-lens/src/server/index.ts` route table | H | M | Lead owns the file; teammates `SendMessage` for route additions. |

---

## 6 · Parking lot — not on the schedule

Items called out in BRAINSTORM / GRAND_PLAN that are deliberately deferred and need re-pricing before they get a phase:

- LangGraph adapter (INTEGRATIONS §LangGraph) — Stage 2.
- Aider / Cline / Continue / Roo adapters — Stage 2 once SDK surface stabilizes.
- Per-org RL fine-tunes (§4.3) — Stage 2, gated on revenue.
- Hosted RAG + S3 backing — Stage 2.
- SSO / SAML / OIDC — Stage 3 only.
- Notification routing via SMTP — Stage 2 week 1 (hosted prereq).
- AutoGen / CrewAI / Mastra SDK adapters — Stage 2 after `@crawfish/sdk` ships.
- A separate desktop `crawfish-orchestrator` bundle (OpenClaw + lens + policy) — re-evaluate after week 8.

---

## 7 · How to read this document

- **Scheduled** = a row exists in §1 with a week.
- **Active** = work has started; commits are landing this week.
- **Shipped** = listed in §0 with no caveat.
- **Carry-over** = in §0's open-from-prior table; folds into the named upcoming phase.
- **Parking lot** = §6; not built until re-priced.

Anything not in one of those buckets is, by convention, not being built. Add it via a PR to this file with a phase assignment, an estimate, and a DoD — not in code first.

---

## 8 · Source of truth

- **What's shipped:** `main` of each repo + §0 above.
- **What's planned:** §1 above. Edits go through PR review.
- **What we will not build:** §6, plus [`GRAND_PLAN.md`](./GRAND_PLAN.md) §9 anti-goals.
- **North star (one sentence):** Make it as easy to run a company with AI agents as it is to run one with people — and make the agent company faster, cheaper, and more observable than the human one.
