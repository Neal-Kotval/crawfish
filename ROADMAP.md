# Crawfish — Platform Roadmap

> The full scope of the crawfish platform: lens (observability) + opt (optimizers), the contract that ties them, and a wave-by-wave build plan that's honest about what's one-shot-able vs. what isn't.

This is the **umbrella roadmap**. Each submodule has its own milestone-level roadmap; this doc is the cross-cutting plan and the source of truth when the two diverge.

- **crawfish-lens roadmap:** [`crawfish-lens/ROADMAP.md`](./crawfish-lens/ROADMAP.md)
- **crawfish-opt roadmap:** lives in the optimizer repo's docs (TBD — currently implicit in milestones M1.x referenced in the v0.2 ship notes)
- **crawfish-dash roadmap:** TBD; created at start of P2.
- **Product overview:** [`crawfish-lens/PRODUCT.md`](./crawfish-lens/PRODUCT.md)

## Three pillars

1. **`crawfish-opt`** — MCP servers that minimize tokens for specific workloads (browser, codebase, logs, search). Each is its own repo, its own release. Composable via the [optimizer contract](#2-the-optimizer-contract-shared-spec).
2. **`crawfish-lens`** — local observability. Reads `~/.claude/projects` JSONL, reports per-session/tool/model token usage, surfaces diagnoses with optimizer recommendations.
3. **`crawfish-dash`** — Apple-like dashboard that wraps both. Manages agents (Claude Code subagents → MCP bundles → [OpenClaw](https://openclaw.ai/) skills over time), embeds lens as a tab, installs optimizers from a marketplace tab. **The user-facing surface; lens and opt are the engines underneath.**

---

## 0. North star

**One sentence:** *Make multi-agent token waste visible at the team level, then enforce the optimizers that fix it — locally, with no transcripts leaving customer machines.*

**Done looks like:** A platform engineer at a 50-person AI-forward team runs `npx crawfish` once on their machine, sees the team's compounding factor (4.2× across 80 sessions last week), defines a policy bundle, distributes it via a signed git-pulled URL, and the next week's bill drops measurably. Engineers' Claude Code sessions hit the policy hook → wasteful patterns auto-route to the relevant `crawfish-opt-*`, savings show up in the per-session view, the platform engineer sees the aggregate trend in a self-hosted team-mode aggregator.

**Done does NOT look like:** A vendor-hosted SaaS that ingests transcripts. A generic LLM observability tool. A framework. A prompt-rewriter. See [`PRODUCT.md` § Anti-goals](./crawfish-lens/PRODUCT.md#anti-goals).

## 0a. Distribution strategy: Tier 1 + Tier 2

The product is local-first, but distribution has two tiers. Tier 1 is the OSS funnel; Tier 2 is the commercial wedge. Same engineering foundation; different go-to-market.

| Tier | Audience | Install | Pitch | Commercial |
|---|---|---|---|---|
| **Tier 1 — `npx crawfish`** | Individual ICs running Claude Code (the early adopters) | One command. Boots lens + dash + the codebase optimizer. Hook install with prompt. | "See where your tokens go. Cap the obvious waste." | Free, OSS forever. Drives Tier 2 inbound. |
| **Tier 2 — `crawfish team install <url>`** | Platform engineers rolling out to teams | Same binary; consumes a signed bundle URL declaring policies + optimizer set + opt-in aggregator endpoint. | "Cap your team's Claude Code spend without slowing them down." | Paid: site licenses + a self-hosted team aggregator (`crawfish-team`) for cross-engineer rollups. |
| **Tier 3 — `crawfish ci`** *(later)* | Eng managers who want PR-time enforcement | GitHub Action that flags wasteful patterns on PRs that touch agent configs. | "Catch the regression before merge." | Paid: per-seat. |

**Why this shape:** Generic LLM observability is commoditized (Langfuse, Helicone, Braintrust). Our defensible position is *Claude-Code-native fan-out detection plus enforceable policy* — neither incumbent can ship that without rewriting their stack. The OSS funnel earns the team's trust; the team install converts.

**Privacy is the wedge, not the constraint.** "Transcripts never leave the customer machine" isn't a temporary anti-goal; it's the only thing that makes legal say yes at most companies. Self-hosted aggregator preserves this — customers run their own collector pod, ICs opt in to send anonymized stats to it.

---

## 1. Phase summary

| Phase | What lands | What unlocks | Honest weeks |
|---|---|---|---|
| **P0** | Lens M0 CLI + crawfish-opt browser v0.2 | Local data is readable; one optimizer exists | ✅ done |
| **P1** | Lens M1 dashboard (Vite/React) + diagnoses skeleton + crawfish-opt-codebase v0.1 | The "see → fix" loop runs end-to-end for the first time | ✅ done |
| **P1.5** | crawfish-dash v0.1 webapp (Policies / Agents / Optimizers / Sessions / Benchmarks tabs) + topology graph + per-session savings + shared @crawfish/ui | Tier 1 in dogfood form: end-to-end usable platform on one machine | ✅ done |
| **P2 — Tier 1 ship** | `npx crawfish` one-liner: umbrella publishes to npm, single command boots lens + dash + opens browser, auto-installs hook with confirmation. Public on GitHub. | Real distribution. Anyone can try crawfish in 60 seconds. | 1-2 |
| **P3 — Tier 2 wedge** | `crawfish-team` self-hosted aggregator (5th submodule). Bundle distribution (signed git URLs). `crawfish team install <url>` consumes policy + optimizer set. Opt-in stat sharing from ICs to org aggregator. | Commercial wedge: platform engineers can roll out and measure across their team. | 4-6 |
| **P4 — depth** | crawfish-opt-logs v0.1, lens M2 diagnoses catalog, dash Tauri shell, OpenClaw integration, marketplace public submission flow. | Optimizer breadth + native macOS feel. | 4-6 |
| **P5 — Tier 3** | `crawfish ci` GitHub Action — PR-time token regression checks. Cursor/Aider adapters for non-Claude-Code shops. | Enterprise depth + non-CC reach. | open-ended |

**Total to public release (P0→P4):** 12-16 focused weeks (revised after dash addition). Solo, evening/weekend pace, no surprises.

The "one-shot this session" wave is **P1 only**, scoped tightly below. Architectural decisions in P1 (Vite + React + design tokens, no framework lock-in) are chosen so dash (P2) can fold lens components in without rewriting.

---

## 2. The optimizer contract (shared spec)

Lives at this layer because both repos depend on it. Should eventually move to `docs/optimizer-contract.md` in this umbrella.

Every crawfish-line MCP server MUST:

1. **Self-report `tokens_used`** on every tool response. JSON shape:
   ```jsonc
   { "tokens_used": { "input_estimate": 312, "output_estimate": 28, "method": "haiku|tiktoken|bytes/4" } }
   ```
2. **Be idempotent on retry.** An agent re-calling after a stall must not multiply API cost.
3. **Degrade gracefully without an API key.** Fall back to deterministic logic; surface a `degraded: true` flag.
4. **Address one token sink.** Browser, codebase, logs, search — not "everything."
5. **Ship a benchmark.** Each optimizer's repo includes `bench/baseline-vs-optimizer.ts` showing tokens-saved on a fixed task set. Lens's M4 marketplace reads these numbers; without them, the optimizer doesn't list.
6. **Version compatibility:** declare `crawfish-contract: "1.0"` in `package.json`. Lens checks this before recommending.

Lens MUST:

1. **Read** `tokens_used` from tool results when present, treat as authoritative.
2. **Detect contract violations** by diffing self-report against the next assistant turn's `cache_creation_input_tokens` delta. Flag as "optimizer misreports cost" if drift > 20%.
3. **Never depend on an optimizer being installed.** The base experience works against any Claude Code session.

---

## 3. Phase 1 — the one-shot wave

**Goal:** end-to-end "see → fix" loop. User opens lens, sees one diagnosis, installs one optimizer, sees the diagnosis go away.

This is the wave to commit to in a single focused build session. Everything below is acceptance-criteria sized — when a checkbox is satisfied, that piece is done.

### 3.1 Lens M1 — local dashboard

**Stack:** Node 20+, ESM, single-process. **No frontend framework.** Server-rendered HTML + a 40-line vanilla JS file for live updates. Zero build step on the frontend.

- [ ] **Server foundation** (`src/server/index.ts`)
  - Express? No — `node:http` + `node:url` only. Save the 30 deps.
  - Bind to `127.0.0.1:7878` only. `--bind` flag prints a security warning if non-localhost.
  - Single-page mode: `/` lists sessions, `/session/<id>` shows detail, `/events` is the SSE stream.
- [ ] **Tail layer** (`src/server/tail.ts`)
  - `chokidar` watching `~/.claude/projects/**/*.jsonl`.
  - Per-file cursor (`{ inode, byteOffset }`) — detects truncation/rotation, re-reads from offset on `change`.
  - Emits `Entry` objects to subscribers; backpressure-safe (drop oldest on slow consumer).
- [ ] **Session-list view** (`src/server/views/sessions.ts`)
  - Renders the same data as the CLI's `sessions` command but as HTML cards.
  - Live: cards re-render on tail events (server-pushed HTML fragments via SSE; replace by `id`).
  - Active indicator: mtime within last 5 min OR an SSE update arrived in the last 30 s.
- [ ] **Session-detail view** (`src/server/views/session.ts`)
  - Header: model, span, totals, hit rate.
  - Turn timeline: each assistant turn as a row, with stacked token bar (in / out / cache_read / cache_write).
  - Tool calls inline with each turn, showing call name + result-bytes badge.
  - Live: appends rows as new turns arrive.
- [ ] **JSON API** (`src/server/api.ts`) — same data, machine-readable; M3+ depends on this.
  - `GET /api/sessions` → `SessionSummary[]`
  - `GET /api/sessions/:id` → full `SessionDetail`
  - `GET /api/sessions/:id/events` → SSE turn-by-turn stream
- [ ] **Smoke tests** (`tests/smoke.test.ts`)
  - Start server against a fixture transcript dir, assert `/` returns HTML, `/api/sessions` returns expected JSON.
  - One Playwright test asserting live update propagates within 1s of a JSONL append.
- [ ] **Install UX**
  - `npx crawfish-lens serve` opens the browser automatically.
  - First-run banner explains what's being read, links to `docs/privacy.md`.

**Acceptance:** Open `http://localhost:7878`, see your real sessions, watch a card update live as you run Claude Code in another terminal.

### 3.2 Lens M2 — diagnoses *skeleton*

Full M2 is P2. The skeleton in P1 is the rule engine + ONE rule, so the architecture is real and there's at least one finding to surface.

- [ ] **Rule engine** (`src/diagnoses/engine.ts`)
  - `Rule = { id: string; severity: "info"|"warn"|"crit"; detect(s: SessionStats): Finding[]; fix: Fix }`
  - `Fix = { kind: "doc"|"config"|"install"; ... }`
  - `runDiagnoses(s) → Finding[]`, pure function.
- [ ] **Rule: oversized-tool-result** (`src/diagnoses/rules/oversized-result.ts`)
  - Threshold: 5000 tokens (configurable). Estimate via `bytes / 4` proxy at first.
  - Finding: `"<tool> returned <N>KB on <M> calls — try crawfish-opt-<X>"`
  - Maps tool name → recommended optimizer via static `tool-optimizer-map.ts`. Empty for now except `Bash → crawfish-logs`, `Read → crawfish-codebase`, `WebFetch → crawfish-search` — all "coming soon" until each ships.
- [ ] **Findings UI in dashboard** — banner on session-detail view, expandable.
- [ ] **`crawfish-lens diagnose <id>`** CLI command — same engine, terminal output.

**Acceptance:** A session with a 50KB Read result shows an "oversized tool result" finding in both CLI and web UI.

### 3.3 crawfish-opt-codebase v0.1

The reference second optimizer. Validates the contract works for something other than browser, and gives lens M2 a real "install this" recommendation.

- [ ] **Repo scaffold:** `Neal-Kotval/crawfish-opt-codebase`, sibling to crawfish-opt.
- [ ] **MCP tools:**
  - `codebase_overview()` → returns top-level structure (dirs, key files), <500 tokens.
  - `codebase_search(intent)` → semantic search over symbols + filenames; returns `{path, line, snippet}[]`, <300 tokens.
  - `codebase_read(path, intent?)` → returns just the relevant region (function/class) for the intent, summarized if huge. Replaces "Read this 800-line file."
  - `codebase_outline(path)` → file structure (top-level decls), <200 tokens.
- [ ] **Index built lazily** on first call per repo; cached in `~/.crawfish/codebase-cache/<repo-hash>/`.
- [ ] **Benchmark** (`bench/codebase-vs-naive.ts`):
  - Task set: 10 questions like "where is X defined", "what's the API surface of Y".
  - Naive baseline: `grep -rn` + `Read` calls.
  - Crawfish baseline: `codebase_search` + `codebase_read`.
  - Metric: tokens consumed by tool results.
- [ ] **Contract compliance:** `tokens_used` on every response, idempotent, `crawfish-contract: "1.0"` in package.json.

**Acceptance:** On the benchmark task set, codebase optimizer uses ≥3× fewer tokens than the naive baseline.

### 3.4 P1 ship checklist

- [ ] Lens M1 dashboard usable on real sessions
- [ ] At least one diagnosis fires
- [ ] crawfish-opt-codebase passes its benchmark
- [ ] Umbrella README updated to point at the dashboard install command
- [ ] [`PRODUCT.md`](./crawfish-lens/PRODUCT.md) "Status" line bumped to P1

**No P1 task touches:** subagents, hook integration, marketplace UI, or non-Claude-Code adapters. Those are P3+.

---

## 4. Phase 2 — dash MVP + diagnoses breadth + logs optimizer

After P1, you have one rule, one optimizer, and a working web dashboard. P2 wraps that in a polished native shell (dash), fills out the diagnoses catalog, and ships the second optimizer. **This is the phase where "platform" stops being aspirational.**

### 4.0 crawfish-dash MVP (NEW pillar)

The umbrella surface. Wraps lens's frontend in a Tauri 2 shell and adds two new tabs.

- [ ] **Repo:** `Neal-Kotval/crawfish-dash`, sibling submodule.
- [ ] **Stack:** Tauri 2 + React (same components as lens M1), `src-tauri/` Rust shell, `src/` shared frontend code.
- [ ] **Window:** native macOS feel — vibrancy, traffic-light controls, sidebar nav, ⌘-tab navigation. Web fallback via `vite preview` for non-Mac.
- [ ] **Tabs:**
  - **Sessions** — embeds lens M1's UI verbatim (imports `crawfish-lens/web/src/components/*`).
  - **Agents** — lists `~/.claude/agents/*.md`, shows frontmatter (name, description, tools, model). Create/edit/delete via filesystem; markdown editor inline.
  - **Optimizers** — reads `marketplace/optimizers.json` from umbrella; shows install commands per optimizer with copy-to-clipboard. **No auto-install** (security boundary).
- [ ] **Backend:** Tauri commands wrap the same data layer lens uses; no second server process.
- [ ] **Onboarding:** first-run flow detects whether ANTHROPIC_API_KEY is set, whether OpenClaw is installed (P3), whether any optimizers are installed; offers to fix each.

**Acceptance:** Open dash, see your real Claude Code sessions in the Sessions tab, see your subagent definitions in the Agents tab, see crawfish-opt + crawfish-opt-codebase in the Optimizers tab.

### 4.1 Diagnoses (lens M2 full)

Each rule is `src/diagnoses/rules/<id>.ts`, registered in `src/diagnoses/registry.ts`.

- [ ] **`oversized-tool-result`** — already shipped in P1, upgrade with `--tokenize` mode using a real tokenizer (`@anthropic-ai/tokenizer` if available, else fallback).
- [ ] **`repeated-identical-read`** — same path/range read ≥3 times with no intervening Edit. Suggests a session-local memo.
- [ ] **`low-cache-hit-rate`** — long session (>20 turns) with hit rate <50%. Surface the *delta* in `cache_creation_input_tokens` between adjacent turns to point at what's churning.
- [ ] **`dom-dump-detected`** — large `tool_result` content matching a heuristic (`<html`/`<!doctype` near the head, or huge JSON tree depth). Recommends crawfish-opt browser.
- [ ] **`log-truncation-pattern`** — Bash result content ending in `...` or matching `[truncated at N lines]`. Suggests crawfish-opt-logs.
- [ ] **`agent-fanout-cost`** — Agent tool calls whose subagent transcripts (cross-referenced via M3 logic) consumed >10× the parent's tokens.
- [ ] **`thinking-overhead`** — turns where extended thinking is on but output is trivial (<100 tok). Wasted reasoning budget.

**Each rule ships with:**
- A unit test against a fixture transcript that contains the pattern.
- A "false-positive" fixture that does not.
- A doc fragment (one paragraph) with the why and the fix.

### 4.2 crawfish-opt-logs v0.1

- [ ] **MCP tools:**
  - `logs_summarize(text, intent?)` — Haiku-summarized log block, returns key events + counts.
  - `logs_grep(text, pattern, n=20)` — matches with N lines of context around each.
  - `logs_tail_smart(text, n=50)` — tail, but skips repetitive lines (collapses runs).
- [ ] **Benchmark:** 10 representative log dumps (npm install, build output, stack traces, K8s events). Naive = full text. Crawfish = summarized.
- [ ] Contract compliance, same as codebase.

### 4.3 Diagnoses → install UX

- [ ] Each finding renders an "Install fix" button in the dashboard.
- [ ] Button copies the right `claude mcp add` command to clipboard. **Does NOT auto-execute** — security-relevant action requires user confirmation.

---

## 5. Phase 3 — subagents + live mode + OpenClaw

The "visualizer of open Claude agents" half of the original pitch, plus OpenClaw integration in dash.

### 5.0 Dash OpenClaw integration

[OpenClaw](https://openclaw.ai/) is an existing local agent runtime by Peter Steinberger — handles persistent agents, skills, 50+ integrations. Dash wraps it (we don't replace it).

- [ ] **Detection:** check for `~/.openclaw/workspace/` and the launchd service on port 18789.
- [ ] **Agents tab v2:** OpenClaw agents appear as a category beside Claude Code subagents.
- [ ] **Skills view:** list installed skills, link to source repos, show last-run timestamps.
- [ ] **Health:** show OpenClaw service status (running, stopped, errored); start/stop button.
- [ ] **No replication:** dash never duplicates OpenClaw's runtime functionality. If OpenClaw isn't installed, the OpenClaw section of the Agents tab shows an install prompt linking to openclaw.ai.

### 5.1 Subagent correlation

- [ ] Detect `Agent` tool calls in parent transcripts; capture `description`, `subagent_type`, timestamp window.
- [ ] Heuristic match: a child JSONL appearing in `~/.claude/projects/<encoded-cwd>/` within ±60s of the parent's Agent call, whose first user turn matches the parent's prompt content. Record the link in a sidecar `<id>.subagents.json`.
- [ ] M3 schema: `Session.children: SessionRef[]`, `Session.parentId?: string`.

### 5.2 Tree visualizer

- [ ] Tree view in dashboard: parent at root, children indented, each node showing rolled-up token totals.
- [ ] Highlight expensive branches (>50% of parent's total).
- [ ] Drill-in: click a child node → opens that session's detail view.

### 5.3 Hook-based live mode

JSONL flush is bursty (Claude Code may batch multiple turns before fsync). Hooks give us turn-level granularity.

- [ ] Ship a `crawfish-lens-hook` shell script that writes `{sessionId, turnUuid, ts}` to a Unix socket.
- [ ] Lens server listens on the socket; merges hook events with JSONL tail.
- [ ] One-line install: `crawfish-lens install-hooks` writes to `~/.claude/settings.json` (uses the `update-config` skill pattern). Always asks before modifying.

### 5.4 Real-time subagent streaming

- [ ] When a hook event indicates an Agent tool call, the dashboard shows a "spawning subagent" state on the parent card.
- [ ] When the child JSONL appears, link it live; show its tokens accumulating.

---

## 6. Phase 4 — marketplace + public release

### 6.1 Optimizer marketplace

- [ ] Static registry: `marketplace/optimizers.json` in this umbrella repo. Schema:
  ```jsonc
  {
    "id": "crawfish-opt-codebase",
    "tokenSink": "codebase-nav",
    "install": "claude mcp add crawfish-codebase ...",
    "benchmark": { "naiveTokens": 12400, "optimizedTokens": 3100, "tasks": 10 }
  }
  ```
- [ ] Dashboard reads this and surfaces in diagnoses.
- [ ] Submission flow: PR to umbrella, CI runs the submitted optimizer's benchmark, requires it to pass contract checks.

### 6.2 Benchmark harness (shared)

- [ ] `crawfish/bench/` in umbrella: harness that runs any optimizer's bench script and produces a normalized result.
- [ ] CI runs nightly across all known optimizers; lens dashboard shows historical token-saved trends.

### 6.3 Public release

- [ ] All three repos public.
- [ ] Landing page (markdown-only, no separate site): `README.md` of umbrella is the landing page. GitHub Pages renders it.
- [ ] `npm publish` for `crawfish-lens` and each optimizer.
- [ ] Announce: HN, Anthropic Discord, Claude Code subreddit, agents-themed Twitter.

---

## 7. Phase 5+ — beyond v1

Not committed; here so we don't accidentally cut off these futures.

- **CI integration.** GitHub Action that diffs token usage on PRs that touched MCP server configs or system prompts. Alerts on regressions.
- **Adapters.** Cursor (`.cursor/logs/`), Aider (its own log format), custom Anthropic SDK apps via an opt-in proxy. Each is a new `src/adapters/<name>.ts`; lens core stays unchanged.
- **Pricing overlay.** Optional `pricing.json`; dashboard shows $$ alongside tokens. Off by default.
- **`crawfish-opt-search`** — web search result optimizer (top-3 + summary, not full SERP).
- **`crawfish-opt-images`** — vision call optimizer (downscale, crop-to-region).
- **Team mode.** A way for multiple users on the same team to opt into sharing aggregate (not raw) stats. Anonymous-by-default. Possibly a thin self-hosted server. The exact opposite of "no telemetry" — must be explicit and reversible.

---

## 8. Risks, ranked

1. **Transcript schema drift.** Claude Code releases change the JSONL shape. *Mitigation:* version-pin in `docs/transcript-format.md`, golden-file tests, tolerant parser.
2. **Optimizer benchmarks are gameable.** Authors tune to the bench, real-world wins don't materialize. *Mitigation:* benchmarks are public and reproducible; lens detects contract violations from real session data, not just bench output.
3. **Dashboard becomes a generic LLM observability tool.** Scope creep is the failure mode. *Mitigation:* every feature must answer *"does this help a Claude Code user spend fewer tokens?"* If "well, it's nice telemetry" — cut.
4. **Solo bandwidth.** P0→P4 is 10-14 weeks. Realistic at evenings/weekends, brutal at full-time-job pace. *Mitigation:* P1 is the "one-shot wave" — earn the right to keep going by shipping it.
5. **Privacy panic.** Someone screenshots a transcript with a secret in it. *Mitigation:* localhost-only, redact mode for `--json` exports, prominent privacy doc.
6. **Anthropic ships first-party observability.** Possible but unlikely at this granularity, and even then, the optimizer line is independently valuable.

---

## 9. Build order if you actually try to one-shot P1

If you sit down for a day and want to land the entire P1 wave, the order that minimizes blocking:

1. Lens M1 server skeleton (`http`, routes, single fixture page) — 1h
2. Lens M1 tail layer + SSE — 1h
3. Lens M1 session-list view (HTML + live) — 1h
4. Lens M1 session-detail view + token bars — 1.5h
5. Diagnoses engine (just the types and runner) — 30m
6. The `oversized-tool-result` rule + UI banner — 45m
7. Pivot to crawfish-opt-codebase — separate repo, separate session.

The codebase optimizer is its own day. **Do not** try to one-shot M1 *and* the codebase optimizer in the same uninterrupted session — the context-switching cost is real, and the codebase optimizer benefits from being able to dogfood lens against itself while you build it.

Realistic P1 timing: **2 focused days, or ~1 week at evening pace.**

---

## 10. What we're NOT building (yet)

Listed here so we don't drift:

- A frontend framework integration (React, Next, Vue). M1's stack is HTML + 40 lines of JS. Holds until M3.
- Authentication of any kind. Localhost-only.
- A persistent database. The filesystem IS the database.
- Cost-in-dollars. Tokens are the unit.
- Auto-installation of optimizers. User confirms every install.
- Cross-machine session aggregation.
- A CLI for managing optimizers. `claude mcp add` already exists.

---

## 11. Source of truth

- **What's shipped:** the `main` branch of each repo.
- **What's planned:** this file.
- **What's been asked for:** GitHub issues on the umbrella repo.
- **What we've decided NOT to do:** § 10 above, and `PRODUCT.md` § Anti-goals.

Last updated: 2026-05-07.
