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
Now (weeks  1–5)   → P3-finish + P4.2-finish + Token-discipline pack  ──► Stage-1 founder demo
Next (weeks 6–11)  → P5: Skills, IDE v0, Codespaces local, LLM Wiki   ──► Engineer-IC daily driver
Later (weeks 12–24)→ P6: Review, CI, CRDT, web-proxy, hosted opt-in   ──► Team mode + paid tier
Stage 2 (m9–m24)   → §4 of GRAND_PLAN — hosted, RL fine-tunes, RBAC
Stage 3 (m18+)     → §5 of GRAND_PLAN — enterprise, SOC2, on-prem
```

Each week below is **one named sprint** with a single completion gate. Weeks slip if their gate slips; nothing downstream starts until the gate is green.

---

## NOW · Weeks 1–5 — Finish Stage 1 founder slice

**Outcome:** A solo founder installs Crawfish, picks a template, gets 5 working agents on a kanban board, runs a real cron-driven daily standup that costs <$1, and watches the compounding factor drop on Analytics. No external tool needed. This is the shipping bar for the "founder dashboard" pitch.

### Week 1 — RAG indexing + member ACL

**Gate:** `knowledge_query` returns top-5 chunks with citations from a 500-file repo, ≤200ms. Board rejects events from unknown members with `invalid_member`.

| # | Deliverable | Files | DoD |
|---|---|---|---|
| 1.1 | Install `better-sqlite3` + `sqlite-vec` + `@xenova/transformers` in lens | `crawfish-lens/package.json` | `npm i` clean, vec extension loadable on macOS arm64. |
| 1.2 | `RagIndex` module | `crawfish-lens/src/knowledge/index.ts`, `crawfish-lens/src/knowledge/chunker.ts`, `crawfish-lens/src/knowledge/embed.ts` | Chunks markdown by 800-char windows w/ 200 overlap; embeds via `Xenova/all-MiniLM-L6-v2`; persists to `~/.crawfish/orgs/<id>/knowledge.sqlite`. |
| 1.3 | Wire `GET /api/orgs/:id/knowledge/query` to return real chunks | `crawfish-lens/src/server/knowledge.ts` | Replaces existing stub. Returns `{chunks: [{source_id, path_or_url, chunk_text, score}], note?}`. |
| 1.4 | Ingest pipeline | `crawfish-lens/src/server/knowledge.ts:handleIngest`, `POST /api/orgs/:id/knowledge/sources/:source_id/ingest` | Crawls source kind=`files` and `repo` (local clone path); skips binary; tracks last-mtime per file. |
| 1.5 | Knowledge tab in dash | `crawfish-dash/web/src/routes/Knowledge.tsx`, route `/orgs/:id/knowledge` | Lists sources w/ last-ingest timestamp, query box, top-5 results with file/line. |
| 1.6 | Member ACL | `crawfish-lens/src/server/board.ts:validateActor` | `appendEvent` rejects `by` / `assignee` not in `org.json.members`. 400 `invalid_member` w/ list of valid ids. |
| 1.7 | Test suite | `crawfish-lens/test/knowledge.test.ts`, `crawfish-lens/test/board-acl.test.ts` | RAG: ingest 50 md files, query returns expected file in top-3 on 10 fixture queries. ACL: rejects unknown actor; happy-path still passes. |

**Risk:** `sqlite-vec` prebuilds may not exist for every Node ABI. Mitigation: pin Node 20, ship a fallback `IndexedDB`-equivalent that's only the cosine path (no `vec0` virtual table) — slower but works.

### Week 2 — Cycles, epics, activity feed

**Gate:** From the Plan tab, drag tasks into a named cycle, see budget rollup; on the Board, every transition appears in the per-task activity feed with actor + timestamp.

| # | Deliverable | Files | DoD |
|---|---|---|---|
| 2.1 | Cycle + epic schema | `crawfish-lens/src/server/types.ts`, `docs/specs/org-contract.md` | `cycles.json` per org; tasks gain `cycle_id`, `epic_id`. Schema documented. |
| 2.2 | Cycles REST | `crawfish-lens/src/server/cycles.ts` (already scaffolded) | `GET/POST /api/orgs/:id/cycles`, `PUT/DELETE /:cycle_id`. Returns budget rollup `{planned, spent, remaining, slipped}`. |
| 2.3 | Activity feed | `crawfish-lens/src/server/activity.ts` (already scaffolded) | New event kinds: `status_changed`, `assigned`, `linked`, `labeled`, `budget_breach`. Stored inline in `board.jsonl`. |
| 2.4 | Plan tab — cycle picker | `crawfish-dash/web/src/routes/Plan.tsx` | Drag-rank within column; cycle drop-zone; budget bar at the top. |
| 2.5 | Board — activity drawer | `crawfish-dash/web/src/components/TaskDrawer.tsx` | Activity feed panel under acceptance criteria; collapsible. |
| 2.6 | Tests | `crawfish-lens/test/cycles.test.ts`, `crawfish-lens/test/activity.test.ts` | Cycle CRUD + budget math; activity reflects every state change. |

### Week 3 — Templates breadth + multi-org switcher + stats

**Gate:** From Home, create an org from each of 6 templates; see them in the multi-org switcher in the shell; Analytics page loads via single `GET /api/orgs/:id/stats?view=dev|product`.

| # | Deliverable | Files | DoD |
|---|---|---|---|
| 3.1 | `dev-shop` template body | `crawfish-dash/src/templates/dev-shop/{org.json,members/*.md,crons.json,files/*}` | 5 members (PM, FE eng, BE eng, code-review, QA); 3 seed tasks; 1 cron. |
| 3.2 | `support` template body | `crawfish-dash/src/templates/support/*` | 3 members (tier-1, escalation, handoff-human); ticket-triage cron. |
| 3.3 | `research` template body | `crawfish-dash/src/templates/research/*` | 4 members (lead + 3 specialists); paper-digest cron. |
| 3.4 | Industry overlay scaffold | `crawfish-dash/src/templates/_overlays/{b2b-saas,consumer-mobile,agency,e-commerce,content-studio,dev-tools,vertical-ai}.json` | One JSON each; merge logic in `crawfish-orgctl/src/templates/apply.ts`. Overlays add members + skills but never rename existing roles. |
| 3.5 | "Describe my org" wizard | `crawfish-dash/web/src/wizards/describe/index.tsx` | 4 questions → runtime call (active runtime, fallback Haiku) → synthesized `org.json` + members preview → diff vs nearest template → user accepts. Reuses §4.1 runtime layer. |
| 3.6 | Multi-org switcher | `crawfish-dash/web/src/components/OrgSwitcher.tsx`, mount in `cf-toolbar` | Top-bar dropdown, keyboard `⌘O`, lists orgs from `GET /api/orgs`, persists last-selected to localStorage. |
| 3.7 | Stats endpoint | `crawfish-lens/src/server/stats.ts` + route | `GET /api/orgs/:id/stats?view=dev` returns `{tokens_by_agent, tokens_by_tool, success_rate}`; `view=product` returns `{completion_rate, escalation_rate, tasks_by_status}`. |
| 3.8 | Tests | `crawfish-lens/test/templates.test.ts`, `crawfish-lens/test/stats.test.ts` | Each template loads cleanly; stats response shape stable. |

### Week 4 — Token-discipline optimizer pack (start)

**Gate:** Two new optimizers shipped with benchmarks; the diagnoses engine recommends them automatically when their pattern fires.

| # | Deliverable | Files | DoD |
|---|---|---|---|
| 4.1 | `crawfish-opt-logs` v0.1 (already scaffolded in INTEGRATIONS) | `crawfish-opt-logs/` (new submodule) | Tools: `logs_summarize`, `logs_grep`, `logs_tail_smart`. Benchmark: 10 log dumps (npm/cargo/k8s/stack-trace). Target: ≥4× reduction on truncation cases. |
| 4.2 | `crawfish-opt-artifact` v0.1 | `crawfish-opt-artifact/` (new submodule) | Tools wrap big-payload returns into `{artifact_id, summary, next_action}`; payload to `~/.crawfish/artifacts/<id>`. Pairs with §4.3. |
| 4.3 | Diagnoses engine — recommend by tool match | `crawfish-lens/src/diagnoses/tool-optimizer-map.ts` | New entries map `Bash:log-truncation` → `opt-logs`, `WebFetch:large-payload` → `opt-artifact`. |
| 4.4 | Optimizers tab — install state | `crawfish-dash/web/src/routes/optimizers.tsx` | Per-optimizer card shows "installed / not installed" via `which` check; copy-install command (no auto-install). |
| 4.5 | Benchmark runner | `scripts/bench-optimizer.ts` | `node scripts/bench-optimizer.ts opt-logs` runs the 10-fixture suite, prints baseline vs optimized tokens. |

### Week 5 — Founder dashboard polish + acceptance demo

**Gate:** A first-time user reaches "5 working agents + 1 cron firing real LLM output" in ≤15 minutes from `git clone`, and the Home dashboard shows yesterday's cost, top sinks, and compounding factor.

| # | Deliverable | Files | DoD |
|---|---|---|---|
| 5.1 | "What it cost me yesterday" widget | `crawfish-dash/web/src/routes/HomeDashboard.tsx`, `crawfish-dash/web/src/lib/spend.ts` | Reads `GET /api/orgs/:id/stats?view=dev&since=24h`; renders top-3 sinks by agent. |
| 5.2 | Live session strip | `crawfish-dash/web/src/components/LiveSessionStrip.tsx` | Subscribes to lens SSE; one row per in-flight session; emergency-stop button POSTs `POST /api/sessions/:id/stop`. |
| 5.3 | Compounding-factor KPI | `crawfish-lens/src/stats.ts:computeCompoundingFactor` + HomeDashboard render | Per-session ratio surfaced; 7-day trend line. |
| 5.4 | Diagnoses inbox | `crawfish-dash/web/src/routes/HomeDashboard.tsx` (new section) | Lists every fired rule; click-to-fix invokes recommended action (install optimizer, open policy editor). |
| 5.5 | "15-minute install" smoke test | `scripts/smoke-15min.ts` | Headless: install, pick template, fire cron, assert board event. CI green required to ship the slice. |
| 5.6 | Demo video | `docs/demo-stage1.mp4` | 5-minute walkthrough. Ship-blocker until recorded. |

**End-of-Now milestone:** Cut a `v0.3` tag across umbrella + each submodule. Push to remote. Open external alpha (≤20 invitees).

---

## NEXT · Weeks 6–11 — Stage 1 IDE & filesystem layer

**Outcome:** Engineer-IC persona has a daily-driver IDE, agents run in isolated Codespaces, and the org filesystem is a real knowledge wiki with concurrent-write safety.

### Week 6 — Skill backbone (first half)

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

### Week 7 — Skill backbone (second half) + Agentic-OS surfaces

**Gate:** `crawfish journal -u <agent-id> --since 1h` prints the agent's journal; `crawfish crontab -e` opens an editor.

| # | Deliverable | Files |
|---|---|---|
| 7.1 | `skill.web.research` | `crawfish-orgctl/src/skills/web-research/` |
| 7.2 | `skill.code.review` + `skill.code.test` + `skill.code.visualAudit` | `crawfish-orgctl/src/skills/code-{review,test,visualAudit}/` |
| 7.3 | `skill.brand.image` + `skill.crm.touch` + `skill.org.standup` + `skill.bench.regress` | `crawfish-orgctl/src/skills/{brand-image,crm-touch,org-standup,bench-regress}/` |
| 7.4 | `~/.crawfish/bin/` shim — agents-as-executables | `crawfish-orgctl/src/bin/install.ts`, `crawfish-orgctl/src/bin/run.ts` |
| 7.5 | `crawfish journal` + `crawfish crontab` CLI | `crawfish-orgctl/src/cli/{journal,crontab}.ts` |
| 7.6 | `~/.crawfish/proc/<agent-id>/status` virtual file | `crawfish-orgctl/src/proc.ts` |

### Week 8 — Local Codespaces (Docker + Devcontainer)

**Gate:** `crawfish space create eng-agent-1 && crawfish space exec eng-agent-1 -- npm test` works; container has `org-fs/` mounted, agent's policy bundle loaded, MCP tools wired.

| # | Deliverable | Files |
|---|---|---|
| 8.1 | `crawfish space` CLI | `crawfish-orgctl/src/cli/space.ts` |
| 8.2 | Devcontainer template per template | `crawfish-dash/src/templates/<t>/devcontainer/devcontainer.json` |
| 8.3 | Resource caps (cgroups Linux, launchd profile macOS) | `crawfish-orgctl/src/space/limits.ts` |
| 8.4 | Snapshot + branch (git worktree of the space) | `crawfish-orgctl/src/space/snapshot.ts` |
| 8.5 | Dash Spaces panel — list + open shell | `crawfish-dash/web/src/routes/Spaces.tsx` |
| 8.6 | E2E test | `crawfish-orgctl/test/space.e2e.ts` — full lifecycle |

### Week 9 — Crawfish IDE v0.1

**Gate:** VS Code extension installs from `.vsix`; sidebar shows Sessions + Agents + Board; PreToolUse hook fires in-editor; status bar shows live token meter.

| # | Deliverable | Files |
|---|---|---|
| 9.1 | Extension skeleton | `crawfish-ide/` (new repo) — TypeScript, package.json with VS Code engines |
| 9.2 | Crawfish sidebar (web view, reuses dash components) | `crawfish-ide/src/sidebar.ts`, `crawfish-ide/webview/` |
| 9.3 | PreToolUse hook integration | `crawfish-ide/src/hooks/preToolUse.ts` — registers as Claude Code hook |
| 9.4 | Status-bar token meter | `crawfish-ide/src/statusBar.ts` |
| 9.5 | Inline-comment agent dispatch (`// @agent code-review: …`) | `crawfish-ide/src/commands/dispatch.ts` |
| 9.6 | Publish to internal `vsix` registry | `scripts/publish-ide.sh` |

### Week 10 — LLM Wiki + Obsidian sync

**Gate:** `org-fs/knowledge/` renders as a wiki with backlinks, graph view, and "what would an agent retrieve for this query"; opening a vault in Obsidian shows the same files unchanged.

| # | Deliverable | Files |
|---|---|---|
| 10.1 | Markdown parser + backlink graph builder | `crawfish-lens/src/knowledge/wiki.ts` |
| 10.2 | Wiki tab — wikilink renderer + sidebar of backlinks | `crawfish-dash/web/src/routes/Wiki.tsx` |
| 10.3 | Force-directed graph view | `crawfish-dash/web/src/components/wiki/Graph.tsx` (D3) |
| 10.4 | "Retrieval preview" — paste query, see what RAG would return | `crawfish-dash/web/src/routes/Wiki.tsx` (retrieval panel) |
| 10.5 | Obsidian path setting | Settings → Integrations → "Use Obsidian vault at path …" |
| 10.6 | Chokidar watcher → re-index on edit | `crawfish-lens/src/knowledge/watcher.ts` |

### Week 11 — Cron recipes + dynamic model switching + cost-manager agent

**Gate:** Every template has the 7 cron recipes preinstalled; the cost-manager agent auto-pauses an agent that crosses 2σ of its 7-day baseline.

| # | Deliverable | Files |
|---|---|---|
| 11.1 | 7 cron recipes as JSON entries | `crawfish-dash/src/templates/_crons/{standup,token-review,backlog-groom,stale-sweep,friday-roundup,security-sweep,knowledge-digest}.json` |
| 11.2 | Cron run-now button | `crawfish-dash/web/src/routes/Crons.tsx` |
| 11.3 | Per-task model picker | `crawfish-lens/src/runtimes/router.ts` — chooses runtime + model from `task.label` and historical success rates |
| 11.4 | Trajectory cache | `crawfish-lens/src/runtimes/trajectories.ts` — writes successful trajectories to `org-fs/agent-memory/trajectories/<hash>.jsonl`; injects as hint on similar tasks |
| 11.5 | `cost-manager` agent template | `crawfish-dash/src/templates/_skills/cost-manager/SKILL.md + impl.ts` — preinstalled in every template; pause action via `crawfish-orgctl` |
| 11.6 | Tests | `crawfish-lens/test/router.test.ts`, `crawfish-lens/test/trajectories.test.ts` |

**End-of-Next milestone:** `v0.5` tag. Open Stage-1 public alpha. Begin telemetry collection (opt-in).

---

## LATER · Weeks 12–24 — Stage 1 finish + Stage 2 prep

### Weeks 12–13 — Native code review (P6 start)

| # | Deliverable | Files |
|---|---|---|
| 12.1 | Repo connection (local git only) | `crawfish-lens/src/server/repo.ts` — watches `.git/refs/heads/` |
| 12.2 | Side-by-side diff viewer | `crawfish-dash/web/src/routes/Review.tsx` |
| 12.3 | Inline review comments + suggested edits | `crawfish-dash/web/src/components/review/Comment.tsx`, `…/Suggestion.tsx` |
| 12.4 | Agent reviewer hooks | `crawfish-orgctl/src/tools/review.ts` — `review_open_pr`, `review_read_diff`, `review_comment`, `review_approve`, `review_request_changes` |
| 12.5 | PR ↔ CrawfishTask link | `crawfish-lens/src/server/board.ts` — `linked_task_id` resolves both ways |
| 12.6 | Review on push (cron) | `crawfish-lens/src/server/crons.ts` — new built-in cron `review-on-push` |

### Weeks 14–15 — Test-generator + Visual-auditor agents (CI/CD)

| # | Deliverable | Files |
|---|---|---|
| 14.1 | Test-gen agent preinstall | `crawfish-dash/src/templates/_agents/test-generator/{member.md,policy.json}` |
| 14.2 | Visual-auditor agent preinstall | `crawfish-dash/src/templates/_agents/visual-auditor/…` |
| 14.3 | Native CI runner | `crawfish-lens/src/server/ci.ts` — watches PR branches, executes bench suite, posts a review comment |
| 14.4 | Token-regression gate | `crawfish-lens/src/server/ci.ts:assertNoRegression` — fails PR if bench tokens climb >20% |

### Weeks 16–17 — Agent-web proxy MVP (track B of §3.7)

| # | Deliverable | Files |
|---|---|---|
| 16.1 | Proxy daemon skeleton | `crawfish-proxy/` (new repo) — Node HTTP, bound 127.0.0.1, per-adapter routes |
| 16.2 | Stripe adapter | `crawfish-proxy/adapters/stripe/` — list customers / invoices / charges in token-thin JSON |
| 16.3 | GitHub adapter (UI flows beyond `gh` CLI scope) | `crawfish-proxy/adapters/github/` |
| 16.4 | Benchmark vs naive Playwright | `crawfish-proxy/bench/{stripe,github}.bench.ts` |
| 16.5 | Adapter contract doc | `crawfish-proxy/CONTRACT.md` |

### Weeks 18–19 — CRDT + git-worktree isolation

| # | Deliverable | Files |
|---|---|---|
| 18.1 | Yjs-based CRDT for markdown in `org-fs/knowledge/` | `crawfish-orgctl/src/crdt/yjs.ts` |
| 18.2 | Per-agent worktree provisioning | `crawfish-orgctl/src/worktree/spawn.ts` — `git worktree add` under `~/.crawfish/worktrees/<agent-id>/` |
| 18.3 | Lead-merges-back workflow | `crawfish-orgctl/src/worktree/merge.ts` — wraps `git merge --no-ff` and writes a `merge.jsonl` audit |
| 18.4 | Settings → Worktrees panel | `crawfish-dash/web/src/routes/Settings.tsx` (new sub-tab) |

### Weeks 20–22 — Communication-graph features (P3 finish + P5 extensions)

| # | Deliverable | Files |
|---|---|---|
| 20.1 | Org-level flow graph (cross-session) | `crawfish-dash/web/src/components/FlowGraph.tsx` — extend existing single-session view |
| 20.2 | Time scrubber | same file — `<input type=range>` over board.jsonl time index |
| 20.3 | Pattern detection — "Agent A only sends to B" + "siblings reading same file" | `crawfish-lens/src/diagnoses/rules/{pipeline-shape,shared-read-redundancy}.ts` |
| 20.4 | Drill-in to journey timeline | `crawfish-dash/web/src/components/JourneyTimeline.tsx` (already partial) |

### Weeks 23–24 — Stage 2 prep: hosted-mode dry-run + RL data export

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
| 3.1 Templates | 3, 6 (overlays via skills) | active |
| 3.2 AI issue tracking | 2 + Stage 2 §4.6 | partial — cycles/epics now, AI triage in Stage 2 |
| 3.3 Local agent FS | 1, 10, 18 | active |
| 3.4 Skill backbone | 6, 7 | scheduled |
| 3.5 Crawfish IDE | 9 | scheduled |
| 3.6 Founder dash | 5 | active |
| 3.7 Web for agents (track A) | 4 (logs optimizer); track B at 16 | mixed |
| 3.8 Local Codespaces | 8 | scheduled |
| 3.9 Agent CI/CD | 14 | scheduled |
| 3.10 Cron recipes | 11 | scheduled |
| 3.11 Token discipline | 4, 11 | active |
| 3.12 Comms graph | 2 (per-task), 20 (org-level) | mixed |
| 3.13 Dual analytics | 3, 5 | active |

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
