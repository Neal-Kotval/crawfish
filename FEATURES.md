# Crawfish — Features Shipped

Last updated: 2026-05-17 (post NOW-W1).

## crawfish-lens (server)
- JSONL session reader, REST + SSE tail
- 8 diagnoses rules + diagnoses engine
- OpenClaw runtime adapter
- Multi-LLM runtimes: `claude-code` / `claude-api` / `openai-api` / `codex` (cron dispatch)
- GitHub bridge (read-only via `gh` CLI) — issues + PRs per org
- Knowledge-sources registry (CRUD on `org.json.knowledge_sources`)
- RAG indexing (`sqlite-vec` + `transformers.js`)
- Per-org files REST under `~/.crawfish/orgs/<id>/files/`
- Crons daemon (`node-cron`, `crons.json`)
- Dual analytics endpoint (dev sessions + product board)
- Flat activity feed `GET /activity` + SSE snapshot (NOW-W1)
- Cycles + epics `GET/PUT /cycles` with `If-Match` mtime guard (NOW-W1)
- Four-tier ACL (`owner/admin/member/viewer`) via `validateActor` (NOW-W1)
- Primary-assignee + contributor rewrite rule (sticky human; `assignee_locked`) (NOW-W1)
- Linked tasks + reciprocal edges
- FTS5 structured search (Linear-shaped grammar)
- Topology + flow graphs

## crawfish-dash (UI, Tauri shell)
- Tabs: Sessions / Agents / Plan / Board / Compare / Files / Crons / Knowledge / Optimizers / Policies / Runtimes / Integrations / Settings / Analytics / Home / HomeDashboard / Org
- TaskCard with status dot + tabular numerics
- Kanban column count badges
- Cycle picker + `CycleBudgetBar` on Plan tab (NOW-W1)
- TaskDrawer with activity panel (NOW-W1), comments, links, criteria editor
- Founder dashboard (cost widget, diagnoses inbox, live-session strip)
- OrgSwitcher
- Theme system + design-token CSS (`ui/tokens/globals.css`)
- ActivityFeed component with @mentions

## crawfish-org (on-disk format)
- `~/.crawfish/orgs/<id>/{org.json, board.jsonl, cycles.json, crons.json, members/, files/}`
- Append-only `board.jsonl` event log → folded `Task[]`
- Member fields: `kind`, `humanity`, `acl`, `prompt_file`, `tools`, `model` (NOW-W1)
- Templates: dev-shop / support / research scaffolds

## crawfish-orgctl (MCP server)
- `board_list_tasks` / `board_create_task` / `board_update_task` / `board_comment`
- `org_fs_list` / `org_fs_read` / `org_fs_write`
- `cycles_list` / `cycles_upsert` (NOW-W1)
- `activity_list` (NOW-W1)
- Per-tool `tokens_used` reporting

## crawfish-opt (browser optimizer)
- v0.2 zone-based DOM index, Haiku summarizer
- MCP tool exposed to agents
- Benchmark suite (`BENCHMARK.md`)

## crawfish-opt-codebase
- v0.1 codebase optimizer — 3.25× token reduction on benchmark

## crawfish-app (Tauri shell)
- Native desktop app (Mac/Windows) bundling lens + dash as child processes
- DMG packaging via `scripts/build-dmg.sh`
- Custom app icon

## Tooling & infra
- Diagnoses rules: dom-dump, log-truncation, thinking-overhead, re-read loops, grep-then-read storms, context-window panic, sibling redundancy, agent-fanout cost, low-cache-hit rate
- Vitest in lens + dash; node:test in orgctl
- Type-check gates (`tsc --noEmit`) per submodule
- Submodule layout: `ui/`, `crawfish-lens/`, `crawfish-dash/`, `crawfish-opt/`, `crawfish-opt-codebase/`, `crawfish-app/`, `crawfish-orgctl/`

## Latest milestone
- **v0.3** — Stage 1 Now slice (RAG, ACL, founder dashboard, optimizers)
- **NOW-W1 (post-v0.3)** — Cycles + epics + activity feed + member ACL contract-aligned

## In progress
- NOW-W2 — Acceptance criteria evidence + token-budget bar + agent preflight
