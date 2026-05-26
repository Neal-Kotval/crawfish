# Crawfish — Development Roadmap

> **Concrete, week-shaped plan to ship the Grand Plan.** Every item is a single named deliverable with files, definition-of-done, and dependency. No prose. If a feature is not on this list with a phase and a DoD, it is not being built.
>
> Source of vision: [`GRAND_PLAN.md`](./docs/roadmap/GRAND_PLAN.md). This file is the build schedule.
>
> Companion docs: [`PRODUCT.md`](./PRODUCT.md) · [`DESIGN.md`](./docs/product/DESIGN.md) · [`INTEGRATIONS.md`](./docs/product/INTEGRATIONS.md) · [`BRAINSTORM.md`](./docs/product/BRAINSTORM.md) · [`AGENT-TEAMS.md`](./docs/ops/AGENT-TEAMS.md).

Last updated: 2026-05-22.

**Changelog (2026-05-22):** Added the **Orchestrator track (O0–O7)** as a new top-level workstream — a 44-week hosted-orchestrator build for mid-market eng teams. Sequenced parallel to the existing NOW/NEXT/LATER slices; pulls forward several items from PARALLEL TRACK D, LATER² weeks 19–24, and GRAND_PLAN Stage 2 §4.1/§4.4/§4.6/§4.10. Slip annotations added inline to affected LATER and LATER² weeks. Full detail in [`docs/roadmap/ORCHESTRATOR-STAGES.md`](./docs/roadmap/ORCHESTRATOR-STAGES.md); product spec in [`docs/roadmap/ORCHESTRATOR-ONEPAGER.md`](./docs/roadmap/ORCHESTRATOR-ONEPAGER.md); MVP user stories in [`docs/roadmap/ORCHESTRATOR-USER-STORIES.md`](./docs/roadmap/ORCHESTRATOR-USER-STORIES.md).

---

## 0 · Status snapshot (2026-05-22)

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

⟂ Parallel    (weeks 6–16) → crawfish.dev — marketing/download portal → web dashboard → collaboration → team mode/billing
⟂ Orchestrator (weeks 6–49) → Hosted orchestrator for mid-market eng teams (O0–O7) — see §Orchestrator track below

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

> **Slip note (2026-05-22):** This week slips ~3 weeks because the orchestrator track's O0.5 worktree-isolation work covers part of the surface but not the full Codespaces experience. Full Code-OSS Codespaces resumes after orchestrator stage O3.

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

> **Slip note (2026-05-22):** Slips ~4 weeks because dashboard components the IDE consumes are under heavy edit by the orchestrator team through O3. Resumes after O3 dashboard work stabilizes.

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

> **Slip note (2026-05-22):** Track D (weeks 14–16, team mode + Stripe billing) is **consumed by Orchestrator stage O5** below — same Stripe + seat + audit work, sequenced as part of the orchestrator's multi-user readiness. Tracks A–C ship on the original schedule.

---

## ORCHESTRATOR TRACK · Weeks 6–49 — Hosted orchestrator for mid-market eng teams (runs alongside NEXT / LATER / LATER²)

**Outcome:** A cloud-hosted service that connects to a customer's Linear or GitHub Issues, classifies which inbound tickets are eligible for autonomous handling, dispatches each one to a curated team of "craws" (specialist agent containers) running in isolated worktrees, verifies the result against CI, and produces a checkpoint-gated pull request. Reviewers approve the plan and the final merge; the system handles everything in between, including a budget-capped loop that addresses PR comments without infinite back-and-forth. Hybrid seat+usage pricing. Mid-market eng startups (10–50 engineers) as the v1 ICP.

**Why this lives in its own track:** the orchestrator is a paid SaaS surface; the existing NOW/NEXT/LATER slices are local-first MIT. Putting it in a parallel track keeps the local-first commitments honest while making the SaaS investment visible and dated. Roughly 70% of the substrate already exists in v0.3 (board, triage, capability routing, criteria, budgets, GitHub mirror, runtime adapters, dash, partial cloud auth); the orchestrator is the SaaS framing on top.

**Companion docs:** [`docs/roadmap/ORCHESTRATOR-ONEPAGER.md`](./docs/roadmap/ORCHESTRATOR-ONEPAGER.md) (1-page spec — ICP, wedge, architecture, scope, risks); [`docs/roadmap/ORCHESTRATOR-USER-STORIES.md`](./docs/roadmap/ORCHESTRATOR-USER-STORIES.md) (~95 stories across 17 surfaces); [`docs/roadmap/ORCHESTRATOR-STAGES.md`](./docs/roadmap/ORCHESTRATOR-STAGES.md) (full stage deliverables + file paths + slip-impact accounting).

**Reuse vs. build summary:** see the per-stage tables in `ORCHESTRATOR-STAGES.md`. At a glance: orchestrator reuses the v0.3 board substrate (`cli/orgctl/src/board.ts`), capability router (`cli/projectctl/src/router.ts`), budget primitives (`cli/orgctl/src/budget.ts`), inbound adapter pattern (`cli/orgctl/src/inbound/`), runtime adapter contract (`desktop/lens/src/adapters/`), Prisma org/project models (`cloud/server/prisma/`), Clerk auth, GitHub OAuth, and lens SSE infrastructure. It builds: the durable workflow engine, the checkpoint workflows, the auto-classifier, the live team-execution dashboard, the PR-comment bot, the curated craw library, the worktree-isolation utility (pulled forward from LATER² weeks 23–24), Stripe billing (pulled forward from PARALLEL TRACK D), and basic RBAC + audit log.

### Pre-stage — substrate readiness (covered by NOW weeks 1–5)

**Gate:** v0.3 tag cut; board substrate (cycles, criteria, capability routing, activity feed, FTS5 search) is feature-complete. The orchestrator depends on this; O0 cannot start until this gate is green.

### O0 — foundation choices + end-to-end spike (weeks 6–8)

**Gate:** ADR-002 (workflow engine: Temporal vs. Inngest vs. Restate) merged. End-to-end spike script in CI produces a draft PR on a sandbox repo without manual intervention, using the existing `claude-code` adapter and one new dep-bumper craw.

| # | Deliverable | Files |
|---|---|---|
| O0.1 | ADR-002 — durable workflow engine | `.planning/decisions/ADR-002-orchestrator-workflow-engine.md` |
| O0.2 | Cloud-server orchestrator skeleton | `cloud/server/src/orchestrator/{queue,worker,workflow,types}.ts` |
| O0.3 | Worker runtime adapter shim | `cloud/server/src/orchestrator/adapters/claude-code.ts` |
| O0.4 | First curated craw (dep-bumper) | `cli/orgctl/src/craws/dep-bumper/{craw.yaml,SKILL.md,impl.ts}` |
| O0.5 | Worktree isolation utility (pulled forward from LATER² wk 23–24 worktree half) | `cli/orgctl/src/worktree/{spawn,merge,cleanup}.ts` |
| O0.6 | End-to-end spike script | `scripts/spike-orchestrator-e2e.ts` |

### O1 — single-craw PR loop, first design partners (weeks 9–14)

**Gate:** Five design partners actively using the orchestrator against their own repos with the dep-bumper craw. ≥20 PRs merged across partners. P50 ticket-to-draft-PR latency <15 minutes. Zero P0 incidents in last 7 days.

| # | Deliverable | Files |
|---|---|---|
| O1.1 | Linear webhook receiver | `cloud/server/src/inbound/linear.ts` |
| O1.2 | GitHub Issues poller | `cloud/server/src/inbound/github-issues-poller.ts` |
| O1.3 | Plan checkpoint workflow (gate 1) | `cloud/server/src/orchestrator/checkpoints/plan.ts` |
| O1.4 | Pre-merge checkpoint workflow (gate 2) | `cloud/server/src/orchestrator/checkpoints/merge.ts` |
| O1.5 | Basic execution dashboard widget | `cloud/platform/src/pages/Orchestrator.tsx` + `desktop/dash/web/src/routes/Orchestrator.tsx` |
| O1.6 | Per-task budget cap enforcement | `cloud/server/src/orchestrator/budget.ts` (wraps existing `cli/orgctl/src/budget.ts`) |
| O1.7 | CI gate (GitHub Actions) | `cloud/server/src/orchestrator/ci.ts` |
| O1.8 | Cancel + retry primitives | dashboard + workflow |
| O1.9 | Design-partner onboarding runbook | `docs/orchestrator/design-partner-onboarding.md` |
| O1.10 | Integration test suite | `cloud/server/test/orchestrator/*.test.ts` |

### O2 — curated craw library + auto-classifier v1 (weeks 15–18)

**Gate:** Four craws live (dep-bumper + test-backfill + lint-cleaner + type-annotator) with published bench scores. Auto-classifier shipped with eval harness. Ten design partners. Classifier precision ≥80% on aggregated eval set. ≥100 PRs merged across partners.

| # | Deliverable | Files |
|---|---|---|
| O2.1 | test-backfill craw | `cli/orgctl/src/craws/test-backfill/` |
| O2.2 | lint-cleaner craw | `cli/orgctl/src/craws/lint-cleaner/` |
| O2.3 | type-annotator craw | `cli/orgctl/src/craws/type-annotator/` |
| O2.4 | Auto-classifier service (Haiku-class) | `cloud/server/src/classifier/{index,prompts,eval}.ts` |
| O2.5 | Per-workspace eval harness | `cloud/server/src/classifier/eval-harness.ts` + dashboard |
| O2.6 | Label-only fallback toggle | dashboard + workflow |
| O2.7 | Per-craw routing rules UI | `cloud/platform/src/pages/RoutingRules.tsx` |
| O2.8 | Per-craw file-path allow/deny lists | dashboard + worker (defence-toolcall pattern from GRAND_PLAN §3.16) |
| O2.9 | Craw version pinning + rollback | dashboard |
| O2.10 | Bench fixtures per craw | `bench/craws/{dep-bumper,test-backfill,lint-cleaner,type-annotator}/` |

### O3 — live team-execution dashboard + multi-craw collab (weeks 19–22)

**Gate:** Dashboard shows live multi-craw view (mostly 1-of-1 in v1 but infra in place). Replay mode works for all v0.3+ tasks. Failure taxonomy applied to all failed tasks for last 7 days. Auto-disable verified on synthetic failure-rate spike.

| # | Deliverable | Files |
|---|---|---|
| O3.1 | Multi-craw collab primitive (impl + tester + reviewer in one worktree) | `cloud/server/src/orchestrator/team.ts` |
| O3.2 | Per-craw SSE stream + aggregation | `cloud/server/src/orchestrator/stream.ts` |
| O3.3 | Team execution view (vertical lane per craw) | `cloud/platform/src/pages/TaskRun.tsx` + `desktop/dash/web/src/routes/TaskRun.tsx` |
| O3.4 | Replay mode (reuse lens replay primitives) | shared with O3.3 |
| O3.5 | Failure categorization taxonomy | `cloud/server/src/orchestrator/failure-taxonomy.ts` |
| O3.6 | Failure dashboard widget | dashboard |
| O3.7 | Auto-disable craw on failure-rate spike | `cloud/server/src/orchestrator/craw-health.ts` |
| O3.8 | Manual-takeover detection | `cloud/server/src/orchestrator/takeover-detector.ts` |

### O4 — PR-comment loop with budget + halt heuristics (weeks 23–26)

**Gate:** PR-bot ships behind a per-workspace flag; turn-on rate among 10 design partners ≥60% within 2 weeks; zero PRs require emergency manual disable in 7-day window after enablement.

| # | Deliverable | Files |
|---|---|---|
| O4.1 | Bot identity + mention listener | `cloud/server/src/orchestrator/pr-bot/listener.ts` |
| O4.2 | Comment-resolution state machine | `cloud/server/src/orchestrator/pr-bot/state-machine.ts` |
| O4.3 | Per-PR revision + token cap (defaults: 5 revisions, $10) | shared with O4.2 |
| O4.4 | Conflict-with-reviewer detector | `cloud/server/src/orchestrator/pr-bot/conflict-detector.ts` |
| O4.5 | Out-of-scope detector | `cloud/server/src/orchestrator/pr-bot/scope-detector.ts` |
| O4.6 | Auto-respond mode toggle (mention-only / respond-to-all / off) | dashboard |
| O4.7 | Bot reply templates (standardized) | `cloud/server/src/orchestrator/pr-bot/templates.ts` |
| O4.8 | Audit trail per revision | reuses existing JSONL audit substrate |

### O5 — multi-user, RBAC, billing, audit (weeks 27–30)

**Gate:** Stripe webhook live; first paying team signed (one of the existing design partners); RBAC matrix doc + UI shipped; audit log queryable in dashboard. SOC2 readiness checklist drafted (Stage 3 work begins).

**Consumes PARALLEL TRACK D weeks 14–16** — Stripe + seat + audit work is the same deliverable, sequenced here instead.

| # | Deliverable | Files |
|---|---|---|
| O5.1 | Stripe Connect integration (humans bill, agents don't) | `cloud/server/src/billing/{stripe,seats,usage}.ts` |
| O5.2 | RBAC roles + permission matrix | `cloud/server/src/auth/rbac.ts` + `docs/orchestrator/rbac-matrix.md` |
| O5.3 | Audit log projection + UI (90-day default retention) | `cloud/server/src/audit/{index,query}.ts` + `cloud/platform/src/pages/AuditLog.tsx` |
| O5.4 | Seat enforcement | shared with O5.1 |
| O5.5 | Usage metering above per-seat allowance | shared with O5.1 |
| O5.6 | Monthly budget cap + pause | `cloud/server/src/billing/budget-cap.ts` |
| O5.7 | Invite flow polish | existing `cloud/server` Invite model + new UI |
| O5.8 | Per-craw + per-org network egress policy | `cloud/server/src/policy/egress.ts` |
| O5.9 | Workspace-wide kill switch | dashboard + workflow |

### O6 — closed beta with 10–20 paying teams (weeks 31–36)

**Gate:** 10–20 paying teams. Mean ticket-to-merged-PR <2h for boring & bounded tasks. P95 <8h. NPS ≥30 from design partners. MRR ≥$10k.

| # | Deliverable | Files |
|---|---|---|
| O6.1 | Onboarding walkthrough (ends with real PR in <10min) | `cloud/platform/src/onboarding/orchestrator/` |
| O6.2 | Escalation policy + UI (fallback reviewer chain) | dashboard |
| O6.3 | Manual-takeover UX (hand off worktree gracefully) | dashboard + Linear/GitHub comments |
| O6.4 | Notifications (in-app + email + one-way Slack webhook) | `cloud/server/src/notifications/` |
| O6.5 | Support runbooks | `docs/orchestrator/support/{onboarding,common-failures,billing-questions}.md` |
| O6.6 | Status page | hosted (statuspage.io or equivalent) |
| O6.7 | First-line on-call rotation | internal — 1 engineer/week for 10–20 customer fleet |
| O6.8 | Customer feedback channel | shared Linear/Slack per design partner |
| O6.9 | Per-craw release notes + changelog | `docs/orchestrator/craws/<id>/CHANGELOG.md` |
| O6.10 | Regression alert pipeline (2σ drop in success rate) | `cloud/server/src/quality/regression.ts` (uses cost-manager pattern) |

### O7 — public beta + customer-authored craws v1 (weeks 37–44)

**Gate:** Public signup live; ≥3 customers have authored their own craws; ≥30 paying teams; ARR ≥$50k. Begin GRAND_PLAN Stage 2 work in earnest (hosted RAG spike, RL data-export pipeline).

| # | Deliverable | Files |
|---|---|---|
| O7.1 | Public signup + onboarding | `cloud/platform/` |
| O7.2 | Customer-authored craw forking | `cloud/platform/src/pages/CrawEditor.tsx` + `cli/orgctl/src/craws/templates/` |
| O7.3 | Craw authoring docs (5-page set + `craw test` CLI) | `docs/orchestrator/authoring-craws/` |
| O7.4 | Per-workspace craw registry (private + curated together) | extends O5.7 |
| O7.5 | Marketing site update (pricing, logos, positioning) | `web/` |
| O7.6 | GRAND_PLAN Stage 2 prep begins (was LATER² week 28) | per [`GRAND_PLAN.md`](./docs/roadmap/GRAND_PLAN.md) §4 |
| O7.7 | Closed-beta post-mortem | `docs/orchestrator/post-mortems/closed-beta-v1.md` |

**End-of-orchestrator-track milestone:** v1.0 of the hosted orchestrator. Public signup open. 30+ paying teams. Stage 2 of GRAND_PLAN begins from a position of revenue rather than from scratch.

### Resourcing assumption

Two full-time engineers on the orchestrator (one backend + workflow, one frontend + dashboard + cloud-platform), separate from the existing lens + dash + ui team. With one engineer multiply timeline by ~1.8 (~78 weeks). With three engineers, compresses to ~33 weeks but requires tight coordination per [`CLAUDE.md`](./CLAUDE.md) ownership rules. Product designer needed part-time from O3 onward.

### Open questions that gate O0

Resolve before O0 closes; tracked in `ORCHESTRATOR-STAGES.md` §"Open questions":

1. Hosting target (AWS / GCP / Fly.io) — constrains worker isolation model.
2. Per-task token-cost ceiling — anchors O5 pricing; spike O0.6 should produce the measured input.
3. Domain: same `crawfish.dev` or `orchestrator.crawfish.dev` — marketing decision.
4. Single shared GitHub App vs. per-customer apps — ops vs. scale tradeoff.
5. External craw contributor invitations before O7 customer-authored ships.
6. Merge-approval policy: GitHub branch protection only, or orchestrator-layer override.

---

## GRAND_PLAN expansions · Weeks 10–36 — workstreams previously unscheduled

**Why this section exists:** prior to 2026-05-22, several Stage-1 workstreams in [`docs/roadmap/GRAND_PLAN.md`](./docs/roadmap/GRAND_PLAN.md) §3 had narrative commitments and phase assignments in GRAND_PLAN §8 but no concrete weeks in `ROADMAP.md`. This block fills that gap. Each subsection sequences a single GRAND_PLAN workstream across P4 → P5 → P6, with each entry pointing at the week it lands. Slip-sensitive (these are added on top of the orchestrator track; if the orchestrator team isn't resourced per `ORCHESTRATOR-STAGES.md` §"Resourcing assumptions," several of these slip by 4–8 weeks).

### §3.3.1 — The agentic brain (librarian)

The single most-contested feature in the GRAND_PLAN per §6.12. Three versioned shippings; v1 is the minimum that makes the moat narrative concrete.

| When | Deliverable | Files |
|---|---|---|
| Week 10 (P4) | **Brain v1** — query clustering (k-means + transformers.js CPU); LinUCB contextual bandit per cluster; cold-start priors (one Haiku call seeds arm probabilities); reward signal (citation, no re-prompt, task success); six MCP tools (`knowledge_route`, `knowledge_feedback`, `knowledge_explain`, `bundle_get`, `bundle_diff`, `bundle_pin`); spawn-time bundle composer + role-graph + per-role bundle UI in dash | `crawfish-lens/src/brain/{clusters,bandit,reward,bundle-composer,role-graph}.ts`; `~/.crawfish/orgs/<id>/brain/{clusters.json,bandits.sqlite,feedback.jsonl,bundles/<role>.json,role-graph.json}`; `crawfish-orgctl/src/tools/brain.ts`; `crawfish-dash/web/src/routes/Brain.tsx` |
| Week 22 (P5) | **Brain v2** — LightGBM gradient-boosted ranker (within-source ordering, retrained nightly); PageRank over citation graph; LLM Wiki visualization (cluster name, arm distribution, arm-evolution graph, alternatives considered); bundle delta-propagation to running agents; bundle-pin human overrides | `crawfish-lens/src/brain/{ranker,pagerank,delta-propagation}.ts`; `ranker.lightgbm`, `pagerank.json` artifacts; `crawfish-dash/web/src/routes/Brain.tsx` (extend) |
| Week 32 (P6) | **Brain v3** — two-tower neural retrieval (ONNX, CPU-trainable in 1h on a year of feedback); cluster auto-naming + drift detection (nightly Haiku reads sample queries per cluster); arm-evolution-over-time view; per-agent personalization layered on role bundles | `crawfish-lens/src/brain/{two-tower-train,drift,personalize}.ts`; `tower.onnx` artifact |

**Persona priority (per GRAND_PLAN §3.3.1):** solo founder + engineer IC + manager + research lead + compliance.

**Hard prerequisite:** §3.3 RAG (NEXT week 6) and three-zone org-fs layout. Brain v1 cannot start before RAG indexing is shipped and stable.

### §3.14 — Native orchestration runtime

The runtime Crawfish owns. Pluggable third-party runtimes (Claude Code, CMA, OpenClaw, Codex, Ruflo) remain available; from week 14 onward, native is the default for new orgs. ADR-001 (already in `.planning/decisions/`) pins the task data model the runtime shares.

| When | Deliverable | Files |
|---|---|---|
| Week 11 (P5) | **Cap 1 — Swarm primitives.** Three topologies: hierarchical, mesh, adaptive. Per-task topology choice in task frontmatter or chosen by planner. | `crawfish-lens/src/runtime/swarm/{hierarchical,mesh,adaptive}.ts` |
| Week 12 (P5) | **Cap 2 — GOAP planner.** Plain-English goal → state-space A* through actions with preconditions/effects → executable plan tree. Renders in Plan tab as collapsible tree with blocked branches + rollbacks highlighted. Replans on state change. | `crawfish-lens/src/runtime/planner/{goap,plan-tree,replan}.ts`; `crawfish-dash/web/src/routes/Plan.tsx` (extend) |
| Week 13 (P5) | **Cap 3 — Agent scheduler.** Token-budget-aware dispatch. Capability-matched routing (reuses `cli/projectctl/src/router.ts` 70%-success-rate primitive). Per-agent concurrency limits. Backpressure when org-wide budget depleted. | `crawfish-lens/src/runtime/scheduler/{dispatch,backpressure}.ts` |
| Week 14 (P5) | **Cap 7 — MCP-tool catalog.** `swarm_init`, `agent_spawn`, `task_orchestrate`, `goal_decompose`, `memory_store`, `memory_search`, `federation_send`, `trajectory_replay` registered in `cli/orgctl`. Schemas match converging Ruflo/CrewAI/MAF shapes where overlap exists. | `cli/orgctl/src/tools/runtime.ts` |
| Week 25 (P6) | **Cap 4 — Agent memory.** Per-agent working memory + shared `org-fs/memory/<agent-id>/`. RVF-style snapshot/restore so a long-running agent can be paused, exported, resumed on another machine. | `crawfish-lens/src/runtime/memory/{working,snapshot,restore}.ts` |
| Week 26 (P6) | **Cap 5 — Federation v0.** Two-node only. mDNS LAN discovery; signed-invite WAN; ed25519 challenge-response auth; typed message bus; PII pipeline in front of every outbound message. | `crawfish-lens/src/runtime/federation/{discover,auth,bus}.ts` |
| Week 27 (P6) | **Cap 6 — Self-learning loop.** Every completed task writes a trajectory record (goal, plan, outcome, tokens, success/failure, fix-if-failed). Planner queries trajectories via the brain before A* search — past solutions become learned priors. | `crawfish-lens/src/runtime/trajectory/{record,query,replay}.ts`; `org-fs/agent-memory/trajectories/` |
| Week 28 (P6) | **Cap 8 — Runtime adapter parity.** Native runtime implements same adapter contract (`crawfish-lens/src/adapters/`) as Claude Code / Codex / OpenClaw. Lens reads native transcripts the same way. Diagnoses rules fire unmodified. | `crawfish-lens/src/adapters/crawfish-native.ts` |

**Risk per GRAND_PLAN §3.14 risk register:** Ruflo v3 ships better swarm intelligence before week 14; mitigation — keep Ruflo as first-class adapter. Federation v0 introduces security surface; mitigation — single-machine first, multi-machine gated on security audit.

### §3.15 — Methodology packs

Methodology lives one layer above the runtime (per §3.14 anti-feature list). Each pack is an org-template + skill-pack + role-graph + brain-bundle template.

| When | Deliverable | Files |
|---|---|---|
| Week 15 (P5) | **SPARC + ADR** org templates. SPARC: 5-phase methodology (Specification → Pseudocode → Architecture → Refinement → Completion) with quality gates; 5 specialist agents + coordinator. ADR: every architectural choice → `org-fs/knowledge/adr/####-title.md`; supersedes relationships in entity graph. | `crawfish-dash/src/templates/{sparc,adr}/{org.json,members/,_skills/}`; `crawfish-orgctl/src/skills/{sparc.spec.write,sparc.architecture.diagram,sparc.refinement.review,adr.write,adr.supersede}/SKILL.md` |
| Week 24 (P6) | **DDD + GTD-for-orgs + OKRs.** DDD: bounded contexts, aggregates, events, ACLs; domain modeler + integration architect agents. GTD: capture/clarify/organize/reflect/engage mapped onto board states. OKRs: hierarchy of objectives + key results decomposed into tasks; quarterly review cron. | `crawfish-dash/src/templates/{ddd,gtd,okrs}/`; `crawfish-orgctl/src/skills/{ddd.aggregate.scaffold,gtd.capture,okrs.rollup}/SKILL.md` |

### §3.16 — AI Defence

The five-module pipeline that gates every other workstream against prompt injection, PII leakage, secrets exposure, tool-call escalation, vulnerability bleed-through. Per §7 wiring policy: reimplemented natively (not forked from `ruflo-aidefence`) because every defence module hooks the diagnoses engine.

| When | Deliverable | Files |
|---|---|---|
| Week 10 (P4) | **`defence-promptinject`** — pre-tool-call hook scans incoming text for instruction-override tokens, known jailbreak phrasings, suspicious embedded tool-call requests. Quarantine (`<untrusted>` wrap) or block. Default quarantine. | `crawfish-lens/src/defence/promptinject.ts` + `cli/orgctl/src/hooks/pre-tool-use.ts` |
| Week 10 (P4) | **`defence-secrets`** — runs on transcript ingestion + Codespace shell history. Detects API keys, tokens, credentials, private keys via entropy + format match (GitHub secret-scanning patterns + org-customizable). Hits → `secrets-incidents.jsonl` + board task. Token hashed in transcript so trail is auditable but not replayable. | `crawfish-lens/src/defence/secrets.ts`; `~/.crawfish/orgs/<id>/secrets-incidents.jsonl` |
| Week 16 (P5) | **`defence-pii`** — per-source-class PII detector on ingest + every retrieval. Tags chunks with `pii_class` metadata. Brain bundle composer + librarian router respect `pii_class` against agent's `allowed_pii_classes` policy. PII redacted at retrieval time (not ingest) so user can still audit what's there. | `crawfish-lens/src/defence/pii.ts`; extend `crawfish-lens/src/brain/bundle-composer.ts` |
| Week 16 (P5) | **`defence-toolcall`** — PreToolUse hook (Claude Code's contract, adapted). Per-agent allowlist of MCP tools + per-tool argument patterns. Denied calls → diagnoses feed + click-to-approve. Egress denied by default; per-domain explicit allowlists. | `crawfish-lens/src/defence/toolcall.ts`; extend `cli/orgctl/src/hooks/pre-tool-use.ts` |
| Week 27 (P6) | **`defence-cve` + unified Defence dashboard.** Nightly CVE scan across connected codebases; hits → `priority: high` board tasks; code-review agents pre-loaded with current CVE state via bundle composer. Dashboard surface in dash. | `crawfish-lens/src/defence/cve.ts`; `crawfish-dash/web/src/routes/Defence.tsx` |

**Note:** §3.16 is the canonical example of the §7 "reimplement natively, steal the design" pattern. We do not depend on `ruflo-aidefence` as a library.

### §3.17 — Craws as the packaging unit

The unit of installation, distribution, and marketplace listing. Nine kinds (agent / skill / template / connector / optimizer / cron / methodology / defence / benchmark) ship under one manifest format.

| When | Deliverable | Files |
|---|---|---|
| Week 17 (P5) | **`craw.yaml` manifest** + `craw add <id>` CLI + four kind handlers (agent, skill, template, optimizer — the kinds that already exist). ed25519 signing; signature verification at install; bundled benchmark required at submission. | `cli/orgctl/src/craws/{manifest,verify,install}.ts`; `bin/craw.js` (extend); `cli/orgctl/src/craws/handlers/{agent,skill,template,optimizer}.ts` |
| Week 29 (P6) | **Five more kind handlers** — connector, cron, methodology, defence, benchmark. Each kind handler routes the install to the correct subsystem (connector → ingest pipeline; cron → crons.json; methodology → templates + skills + role-graph + brain bundle; defence → defence module registry; benchmark → bench fixtures). | `cli/orgctl/src/craws/handlers/{connector,cron,methodology,defence,benchmark}.ts` |
| Week 30+ (Stage 2) | **Signed-distribution marketplace** — see GRAND_PLAN §4.9. PR-based submission, CI benchmark gating, install counts, reviews, compatibility matrix, paid distribution via Stripe Connect. | new repo `crawfish-marketplace/`; submission CI in umbrella `.github/workflows/marketplace-submit.yml` |

### §3.18 — `craw init` first-run discovery

The founder's first-60-seconds gesture. Multi-phase rollout per GRAND_PLAN sequencing.

| When | Deliverable | Files |
|---|---|---|
| Week 5 (P3 finish) | **Local agent surface scan.** Walks `~/.claude/projects/`, `~/.claude/teams/`, `~/.openclaw/workspace/`, Cursor application support, `~/.codex/`. Each becomes a "discovered project" card with token spend, last activity, agent count, top files touched. Import-as-org flow. | `cli/projectctl/src/verbs/init.ts` (extend); `crawfish-dash/web/src/routes/Discover.tsx` |
| Week 11 (P4) | **Code-repo scan + Obsidian-vault detection + Tier-1 connector one-clicks.** Walks `~/code/`, `~/projects/`, `~/Documents/`, git global config. Per repo, proposes a Crawfish org seeded from a relevant template. Detects Obsidian vaults non-destructively (symlink, not copy). One-click OAuth for Gmail/Slack/GitHub/Linear/Notion. | `cli/projectctl/src/discover/{repo-scan,obsidian-detect,connector-installer}.ts` |
| Week 18 (P5) | **"Before Crawfish" cost baseline + recommended craws.** Reads last 30 days of Claude Code / OpenClaw / Codex transcripts. Computes compounding factor, top sinks, top recommendations. Surfaces as the §3.6 founder dashboard at first-run. Recommended craws list with estimated token savings per craw. | `cli/projectctl/src/discover/{cost-baseline,recommend}.ts`; integrates with §3.6 HomeDashboard |
| Week 30 (P6) | **defence-secrets pre-scan + org-shape recommender.** Runs `defence-secrets` over discovered transcripts; surfaces leaked tokens/keys *before* the founder has even created an org. Haiku-class summarization of discovered surfaces → template recommendation ("`startup × b2b-saas` with the support-agent + engineering-agent + ops-agent triad"). | `cli/projectctl/src/discover/{secret-prescan,org-shape-recommender}.ts` |

### §3.19 — Brain across all routing dimensions

The brain (§3.3.1) generalizes from knowledge-routing to all five routing dimensions. v1–v2 land via §3.3.1. The remaining dimensions extend the substrate.

| When | Deliverable | Files |
|---|---|---|
| Week 26 (P6) | **Task → agent routing promotion.** Promote `cli/projectctl/src/router.ts` (static capability matcher) to a bandit-backed dimension of the brain. Same `bandits.sqlite` substrate, new table per `<task-cluster, agent>` pair. Reward = agent completed within budget. Adds `route_task`, `route_feedback`, `route_explain`, `route_alternatives` MCP tools. | `crawfish-lens/src/brain/route-task.ts`; `cli/orgctl/src/tools/route.ts`; deprecate-but-keep `cli/projectctl/src/router.ts` as fallback |
| Stage 2 | **Task → model and task → runtime routing** + the unified Brain dashboard (five dimensions side-by-side). See GRAND_PLAN §3.19 sequencing. | TBD — Stage 2 scope |

---

## LATER² · Weeks 17–28 — Stage 1 finish + Stage 2 prep

### Weeks 17–18 — Native code review (P6 start)

> **Slip note (2026-05-22):** Slips ~4 weeks due to orchestrator parallel-track bandwidth on O3/O4 dashboard + PR-bot. The orchestrator's own PR loop covers the basic review case for craw-authored PRs from O1; this is the native review surface for human-authored code.

| # | Deliverable | Files |
|---|---|---|
| 12.1 | Repo connection (local git only) | `crawfish-lens/src/server/repo.ts` — watches `.git/refs/heads/` |
| 12.2 | Side-by-side diff viewer | `crawfish-dash/web/src/routes/Review.tsx` |
| 12.3 | Inline review comments + suggested edits | `crawfish-dash/web/src/components/review/Comment.tsx`, `…/Suggestion.tsx` |
| 12.4 | Agent reviewer hooks | `crawfish-orgctl/src/tools/review.ts` — `review_open_pr`, `review_read_diff`, `review_comment`, `review_approve`, `review_request_changes` |
| 12.5 | PR ↔ CrawfishTask link | `crawfish-lens/src/server/board.ts` — `linked_task_id` resolves both ways |
| 12.6 | Review on push (cron) | `crawfish-lens/src/server/crons.ts` — new built-in cron `review-on-push` |

### Weeks 19–20 — Test-generator + Visual-auditor agents (CI/CD)

> **Accelerates (2026-05-22):** Test-gen + visual-auditor ship as additional orchestrator craws in **stage O3** (weeks 19–22 of orchestrator track) rather than as separate work. The deliverables below remain as the on-paper plan but are subsumed by the orchestrator craw work.

| # | Deliverable | Files |
|---|---|---|
| 14.1 | Test-gen agent preinstall | `crawfish-dash/src/templates/_agents/test-generator/{member.md,policy.json}` |
| 14.2 | Visual-auditor agent preinstall | `crawfish-dash/src/templates/_agents/visual-auditor/…` |
| 14.3 | Native CI runner | `crawfish-lens/src/server/ci.ts` — watches PR branches, executes bench suite, posts a review comment |
| 14.4 | Token-regression gate | `crawfish-lens/src/server/ci.ts:assertNoRegression` — fails PR if bench tokens climb >20% |

### Weeks 21–22 — Agent-web proxy MVP (track B of §3.7)

> **Slip note (2026-05-22):** Slips ~4 weeks because the parallel-track engineer's bandwidth is consumed by orchestrator O3/O4.

| # | Deliverable | Files |
|---|---|---|
| 16.1 | Proxy daemon skeleton | `crawfish-proxy/` (new repo) — Node HTTP, bound 127.0.0.1, per-adapter routes |
| 16.2 | Stripe adapter | `crawfish-proxy/adapters/stripe/` — list customers / invoices / charges in token-thin JSON |
| 16.3 | GitHub adapter (UI flows beyond `gh` CLI scope) | `crawfish-proxy/adapters/github/` |
| 16.4 | Benchmark vs naive Playwright | `crawfish-proxy/bench/{stripe,github}.bench.ts` |
| 16.5 | Adapter contract doc | `crawfish-proxy/CONTRACT.md` |

### Weeks 23–24 — CRDT + git-worktree isolation (agent-side)

> **Split (2026-05-22):** Git-worktree isolation pulled forward to orchestrator stage **O0.5** (weeks 6–8). The Yjs CRDT layer for `org-fs/knowledge/` holds at the original timing — that work is local-first and not on the orchestrator path.

| # | Deliverable | Files |
|---|---|---|
| 18.1 | Yjs-based CRDT for markdown in `org-fs/knowledge/` | `crawfish-orgctl/src/crdt/yjs.ts` |
| 18.2 | Per-agent worktree provisioning | `crawfish-orgctl/src/worktree/spawn.ts` — `git worktree add` under `~/.crawfish/worktrees/<agent-id>/` |
| 18.3 | Lead-merges-back workflow | `crawfish-orgctl/src/worktree/merge.ts` — wraps `git merge --no-ff` and writes a `merge.jsonl` audit |
| 18.4 | Settings → Worktrees panel | `crawfish-dash/web/src/routes/Settings.tsx` (new sub-tab) |

### Weeks 25–27 — Communication-graph features (P3 finish + P5 extensions)

> **Slip note (2026-05-22):** Slips ~6 weeks because of orchestrator parallel-track bandwidth.

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
| 3.2 AI issue tracking — **Linear-grade board** | 1–5 (full); Stage 2 §4.6 for 24/7 triage covered by orchestrator track | **active — front-loaded** |
| 3.3 Local agent FS | 6 (RAG), 15 (Wiki), 23 (CRDT agent-side; worktree-half pulled to O0.5) | active |
| **3.3.1 Brain (librarian)** | **10 (v1), 22 (v2), 32 (v3)** | **scheduled — newly ratified 2026-05-22** |
| 3.4 Skill backbone | 11, 12 | scheduled |
| 3.5 Crawfish IDE | 14 → slipped ~4w to ~18 | scheduled (slipped) |
| 3.6 Founder dash | 8 | scheduled |
| 3.7 Web for agents (track A) | 7 (logs optimizer); track B at 21 → slipped ~4w to ~25 | mixed |
| 3.8 Local Codespaces | 13 → slipped ~3w to ~16; worktree-half pulled forward to O0.5 | scheduled (slipped) |
| 3.9 Agent CI/CD | 19–20 → **accelerated, ships as orchestrator craws in O3** | scheduled (accelerated) |
| 3.10 Cron recipes | 16 | scheduled |
| 3.11 Token discipline | 7, 16 | active |
| 3.12 Comms graph | 1 (per-task activity), 25 (org-level) → slipped ~6w to ~31 | mixed |
| 3.13 Dual analytics | 5, 8 | active |
| **3.14 Native orchestration runtime** | **11–14 (caps 1+2+3+7), 25–28 (caps 4+5+6+8)** | **scheduled — newly ratified 2026-05-22** |
| **3.15 Methodology packs** | **15 (SPARC + ADR), 24 (DDD + GTD + OKRs)** | **scheduled — newly ratified 2026-05-22** |
| **3.16 AI Defence** | **10 (promptinject + secrets), 16 (pii + toolcall), 27 (cve + dashboard)** | **scheduled — newly ratified 2026-05-22** |
| **3.17 Craws packaging** | **17 (manifest + 4 kinds), 29 (5 more kinds), 30+ marketplace (Stage 2)** | **scheduled — newly ratified 2026-05-22** |
| **3.18 `craw init` discovery** | **5 (local scans), 11 (cloud connectors), 18 (cost baseline), 30 (secrets + recommender)** | **scheduled — newly ratified 2026-05-22** |
| **3.19 Brain across all dimensions** | **26 (task → agent); model + runtime dimensions Stage 2** | **scheduled — newly ratified 2026-05-22** |
| **NEW — Web dashboard + collab** (`crawfish.dev`) | Parallel Track 6–16 | **active** |
| ↳ marketing + download portal (links to app + IDE) | 6–7 | scheduled |
| ↳ authed web dashboard (tunneled lens) | 8–10 | scheduled |
| ↳ collaboration (presence, comments, CRDT drawer, @mentions) | 11–13 | scheduled |
| ↳ team mode + Stripe billing (humans = seats; agents free) | 14–16 → **consumed by orchestrator O5 (weeks 27–30)** | scheduled (consumed) |
| **NEW — Hosted orchestrator track** | **6–44 (O0–O7)** | **active — newly ratified 2026-05-22** |
| ↳ O0 foundation + spike | 6–8 | scheduled |
| ↳ O1 single-craw PR loop + first design partners | 9–14 | scheduled |
| ↳ O2 curated craw library + auto-classifier v1 | 15–18 | scheduled |
| ↳ O3 live team-execution dashboard + multi-craw collab | 19–22 | scheduled |
| ↳ O4 PR-comment loop with budget + halt heuristics | 23–26 | scheduled |
| ↳ O5 multi-user + RBAC + billing + audit (consumes PARALLEL TRACK D) | 27–30 | scheduled |
| ↳ O6 closed beta with 10–20 paying teams | 31–36 | scheduled |
| ↳ O7 public beta + customer-authored craws v1 | 37–44 | scheduled |

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
- Per-org RL fine-tunes (GRAND_PLAN §4.3) — Stage 2, gated on revenue.
- Hosted RAG + S3 backing (GRAND_PLAN §4.1) — Stage 2 (note: the hosted *orchestrator* lands in O0–O5, but org-fs hosting stays Stage 2).
- SSO / SAML / OIDC — Stage 3 only. (Basic RBAC + audit log pulled forward to orchestrator O5.)
- ~~Notification routing via SMTP — Stage 2 week 1 (hosted prereq).~~ **Pulled forward to orchestrator O6.4 (email + in-app + one-way Slack webhook). PagerDuty/Discord/Teams remain deferred.**
- AutoGen / CrewAI / Mastra SDK adapters — Stage 2 after `@crawfish/sdk` ships.
- A separate desktop `crawfish-orchestrator` bundle (OpenClaw + lens + policy) — re-evaluate after week 8.
- §3.19 task → model and task → runtime routing dimensions — Stage 2 (only task → agent dimension is in P6 at week 26).
- Stage 2 §4.2 hosted Pilot Protocol — Stage 2 onward, gated on §3.7 Track B proxy maturity.
- Stage 2 §4.5 manager-grade employee analytics — Stage 2.
- Stage 2 §4.7 org knowledge layer at scale (Confluence / Notion / Drive / Slack-archive cross-source ingestion) — Stage 2; the orchestrator doesn't need it for v1.
- Stage 2 §4.8 advanced agent generation (generate-an-agent / iterate-on-an-agent / A/B between versions) — Stage 2; orchestrator O7 ships *forking* curated craws but not full synthesis.
- Stage 2 §4.9 paid marketplace + revenue share + verified-publisher tier — Stage 2. Free MIT marketplace ships earlier per §3.17 sequencing.
- Stage 3 §5 compliance tier, on-prem deployment, vendor procurement kit, co-sell — Stage 3, gated on Stage 2 paying.
- GRAND_PLAN §6.10 Linux Foundation AAIF membership — strategic decision, not a build item. Track separately.

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
- **What's planned:** §1 above (weekly schedule) + the §"GRAND_PLAN expansions" subsections + the §"Orchestrator track" subsections. Edits go through PR review.
- **What we will not build:** §6, plus [`GRAND_PLAN.md`](./docs/roadmap/GRAND_PLAN.md) §10 anti-goals.
- **Product spec for the hosted orchestrator:** [`docs/roadmap/ORCHESTRATOR-ONEPAGER.md`](./docs/roadmap/ORCHESTRATOR-ONEPAGER.md).
- **MVP user stories for the hosted orchestrator (~95 stories across 17 surfaces):** [`docs/roadmap/ORCHESTRATOR-USER-STORIES.md`](./docs/roadmap/ORCHESTRATOR-USER-STORIES.md).
- **Orchestrator development stages (O0–O7) with file paths + slip accounting:** [`docs/roadmap/ORCHESTRATOR-STAGES.md`](./docs/roadmap/ORCHESTRATOR-STAGES.md).
- **Long-range vision (24 months):** [`docs/roadmap/GRAND_PLAN.md`](./docs/roadmap/GRAND_PLAN.md).
- **Local-first MVP (pre-orchestrator wave):** [`docs/roadmap/ROADMAP-MVP.md`](./docs/roadmap/ROADMAP-MVP.md).
- **North star (one sentence):** Make it as easy to run a company with AI agents as it is to run one with people — and make the agent company faster, cheaper, and more observable than the human one.
