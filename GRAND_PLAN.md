# Crawfish — Grand Plan

> **The operating system for companies that run on AI agents.**
>
> From the solo founder spinning up their first agent to the 500-person org running a thousand of them — one platform, one task schema, one accounting unit (tokens), one place to look.

This document is the long-horizon vision. It assumes the v1 agent-org layer is already in production (see `ROADMAP.md` for what shipped on 2026-05-15) and the Phase 2–6 schedule is the near-term plan. **Grand Plan** is what we want Crawfish to be in 18–24 months, organized around the people who will use it.

Companion docs:

- `PRODUCT.md` — one-page pitch
- `ROADMAP.md` — phased build schedule (P0–P6)
- `BRAINSTORM.md` — half-formed ideas, ranked
- `DESIGN.md` — design system + tokens
- `INTEGRATIONS.md` — runtime adapter matrix
- `AGENT-TEAMS.md` — multi-teammate working conventions

---

## 0 · Where we are today (May 2026)

A clean baseline so the rest of this doc has somewhere to push off from.

The umbrella holds six submodules: `crawfish-lens` (observability + REST + SSE), `crawfish-dash` (Tauri-shelled React UI), `crawfish-orgctl` (MCP server giving agents `board_*` and `org_fs_*` tools), `crawfish-opt` (browser optimizer), `crawfish-opt-codebase` (codebase optimizer, 3.25× token reduction on bench), and `crawfish-app` (the native shell). Eight diagnoses rules are live (`oversized-tool-result`, `re-read-loops`, `low-cache-hit-rate`, `dom-dump-detected`, `log-truncation-pattern`, `thinking-overhead`, `grep-then-read-storms`, `agent-fanout-cost`). Four runtime providers exist (`claude-code`, `claude-api`, `openai-api`, `codex`). Six org templates are scaffolded (`startup`, `dev-shop`, `support`, `research`, `solo-builder`, `blank`). Three wizards are partly in place (`first-run`, `policy`, `prep`). OpenClaw is the only non-Claude adapter so far. Everything binds to `127.0.0.1`.

This is enough surface to demo "agents as first-class employees." It is not yet enough to be the OS for a 200-person engineering org. The Grand Plan covers that gap.

---

## 1 · The north-star vision

Crawfish becomes the place where work gets defined, assigned, executed, observed, and paid for — whether the worker is a person, a Claude Code session, a hosted OpenClaw daemon, or a Codex CLI run on a Tuesday cron. The CrawfishTask is the universal unit. The org filesystem is the shared memory. The flow graph is the org chart. The token meter is the wage bill.

A founder gets a working five-agent company from a template in fifteen minutes and never thinks about Jira, Slack, GitHub Issues, CodeRabbit, Notion, Pendo, LangSmith, or six dashboards again — because Crawfish is all of those, native, and they all share one data model.

A platform engineer at a 200-person org sees every agent in the company on one flow graph, can clamp a runaway agent in two clicks, and exports the audit trail to SOC2 without writing a query.

A research team mints a new specialist agent by forking a marketplace container, points it at their `org-fs/knowledge/`, and that agent inherits the company's writing style, taxonomy, runbooks, and prior decisions — because the knowledge layer is a real RAG with citations, not a prompt-stuffing exercise.

That is the destination. The two stages below are how we get there.

---

## 2 · Personas — who we are building for

Designs collapse when they try to please everyone equally. The honest hierarchy:

**Tier 1 — bottoms-up, must-love (P1–P5):** *Solo startup founder*, *small company CEO*, *individual engineer at a small team*. These three are the only personas whose love is required to keep the company alive. Every feature in Stage 1 gets graded against them.

**Tier 2 — adoption multipliers (P4–P6):** *Platform / DevOps engineer*, *engineering manager at a 30–200 person org*. They are how a single seat becomes thirty seats.

**Tier 3 — enterprise gates (P6+):** *Director / VP of Engineering*, *Finance & Ops*, *Compliance / IT*, *Customer Support lead*, *Research lead*. These personas write the cheques but are not the ones we design *for*; we design *around* them so they can say yes.

The rest of this doc is annotated with which personas each feature lights up.

### 2.1 Solo startup founder

Wears every hat. Is the PM, the engineer, the designer, the QA, the support team, and the marketer at 11pm. Lives in Claude Code. Has burned $400 in a week because a subagent went into a re-read loop and no one was watching. Wants a company in a box — five working agents, sensible defaults, a board they can point at — without spending a week on YAML.

What they need from Crawfish: **org templates that work out of the gate, brutal token discipline, one place to see what their agents are doing, and a panic button.**

### 2.2 Small company CEO (5–30 people, often a non-engineer)

Has agents helping with customer support, sales outreach, content, and ops. Cannot read a transcript. Wants to know: are the agents doing what we hired them to do, where is the money going, and which of them needs human help today?

What they need: **product-side analytics, board-level rollups, cost-by-agent with names not IDs, and a Friday email that says "here is what your robot employees did this week."**

### 2.3 Software engineering employee (IC)

A real engineer at a team where agents are now coworkers. Uses Claude Code or Codex daily. Cares about: my agent helping me ship, not blocking my PR, not racking up a five-figure invoice, and not stepping on a teammate's changes. Will leave if Crawfish adds friction.

What they need: **the dashboard, the IDE plugin, dependable token caching, fast diffs and reviews, agent-team coordination that does not corrupt their working tree.**

### 2.4 Platform / DevOps engineer

The "agent platform engineer" role that emerged in late 2025. They own the policy bundle, the optimizer install, the runtime selection, the cost budget per team, and the escalation tree. They are the buyer for self-serve teams.

What they need: **policy authoring + dry-run, hook injection across every runtime, OTel + Prometheus exporters, fleet-wide rogue-spender detection, and a console that lets them turn the spigot off.**

### 2.5 Medium-company engineering manager (30–200 engineers)

Has a budget. Reports compounding factor up the chain. Wants per-team and per-engineer rollups, fair cross-team comparison, and a way to spot the "AI 10×er" vs. the "$8k-a-month log dumper." Cannot be the one clicking around at 2am.

What they need: **manager dashboards, weekly auto-reports, anomaly alerts, employee performance views that respect privacy, and an audit log that explains every blocked tool call.**

### 2.6 Finance / Ops leader

Doesn't care which model is which. Cares that the AI line item on the P&L is forecastable and that someone is accountable for it. Will be the one in the room when the AI budget gets cut by 30% next year.

What they need: **dollar-denominated rollups (opt-in), forecasted run-rate, "if we kept current trajectory, the bill in 90 days is X," exportable to FP&A.**

### 2.7 Customer support lead

Runs a triage + specialist + escalation agent team. Cares about: did the agent solve the customer's problem, did the customer have to repeat themselves, did we hand off to a human at the right moment.

What they need: **the product analytics surface — completion rate, re-prompt rate, escalation rate, satisfaction signal, failure clustering.**

### 2.8 Research lead

Runs swarms. Each researcher might fan out into 30 sub-agents that all hit the same five papers. They are the canonical compounding-factor disaster.

What they need: **the swarm architecture pattern, knowledge-layer dedup, the redundancy graph (siblings reading the same files), and a hard cap on tokens per question.**

### 2.9 Enterprise IT / Compliance officer

The yes/no vote on company-wide adoption. Cares about: SSO, RBAC, audit log, data residency, attestation, retention policies, and a piece of paper that says SOC2.

What they need: **the Phase 6 compliance tier, the audit export, the attestation primitive, the SSO/SAML/OIDC path.**

---

## 3 · Stage 1 — Founders & Small Companies (next 9 months)

This is the bottoms-up motion. Everything here ships local-first, MIT, runs on `127.0.0.1`, assumes a single-machine user, and is free. The objective is *one machine, five agents, no friction.* If we miss on this stage no amount of enterprise gloss saves us.

Stage 1 is organized into nine workstreams. Each lines up with one of the features the user has asked for; each is grounded in what is already in the repo.

### 3.1 Organization templates — the wedge

**Inspiration:** Gumloop's "pick a workflow, get a working bot." Vercel's "deploy template" gesture. Linear's "create from preset."

**What it becomes in Crawfish:**

The `crawfish-dash/src/templates/` directory currently scaffolds six shapes. Stage 1 fleshes them out and adds *industry-specific* variants on top of the *role-specific* ones already there.

Concrete feature set:

- **Role-shape templates (already present, to be polished):** `startup` (Founder + Eng + Design + Support + Ops), `dev-shop` (PM + 3 engineers + QA), `support` (tier-1 + escalation + handoff), `research` (lead + 3 specialists), `solo-builder` (you + one generalist), `blank` (just you, add agents from Settings).
- **Industry templates (new in Stage 1):** `b2b-saas`, `consumer-mobile`, `agency`, `e-commerce`, `content-studio`, `dev-tools`, `vertical-ai`. Each is a `role-shape × industry` overlay — e.g., `dev-shop × consumer-mobile` ships with iOS reviewer, Android reviewer, App Store metadata writer, and a Playwright visual-diff agent preinstalled.
- **Forkability.** A template is on-disk under `~/.crawfish/orgs/<id>/`. "Fork this org" is `cp -r` plus a UUID rewrite. Two-second operation.
- **Template revisions.** Templates ship versioned (`startup@v3`); a user is told when a template upgrade is available and can take it as a patch with diffs preview.
- **Community submissions.** PR to the umbrella drops a template JSON; CI validates the schema and runs a 10-task smoke test against the template's preinstalled agents.
- **The "describe my org" path.** A wizard that asks four questions ("What's your company doing?" "How big are you?" "What's your stack?" "What hurts most?") and synthesizes a custom template by combining preexisting role containers — written to disk so the founder can edit it. This is the founder-onboarding moment.

**Personas this lights up:** Solo founder (T1), Small company CEO (T1).

**Sequencing:** P3 polish for the existing six; P4 introduces industry overlays; P5 ships the "describe my org" synthesizer (uses the active runtime, falls back to Haiku).

### 3.2 AI-automated issue tracking — Linear, but for agents and humans together

**Inspiration:** Linear's velocity, structured-query filters, and unapologetic opinionatedness. The current ROADMAP already commits to the native task board; this Stage 1 work is what makes that board *better than Linear* for an agent-native company.

**Specific additions:**

- **Acceptance criteria are first-class.** Not "in description prose." Each criterion is `{ id, statement, kind: "test" | "manual" | "spec_match", evidence?: string }`. The board enforces that a `done` transition requires every criterion to carry evidence.
- **Token budget per task.** Already in the schema. Stage 1 adds the live-burn bar, the auto-escalate at 100%, the agent-side preflight ("this task has $0.43 of budget remaining, am I confident?"), and an end-of-task self-attestation entry.
- **Capability-matched routing.** A task is created without an assignee. The router (a cron in `crawfish-lens/src/server/`) reads each agent's `success_rate` and `avg_tokens_per_task` by task `label`, picks the cheapest agent with success > threshold, and auto-assigns. Override with one click.
- **AI triage.** Inbound issues from any source (GitHub, support email, a Notion form, a Slack hand-off) land in a Triage column. A triage agent rewrites them into the structured schema — label, priority, acceptance criteria — and pings the human watcher only when it is unsure.
- **Auto-decomposition.** A task tagged `epic` automatically spawns a planning agent that proposes subtasks with dependency links. The human approves the decomposition in one drawer; the subtasks are then routed by §3.2-bullet-3 above.
- **Cycle planning view.** Multi-agent cycle plan — drag tasks into the cycle column, see token budget rollup, see which agents are over capacity for the week. This is the medium-company manager's home screen but it earns its keep at the small-company stage too.
- **Linked-task graph.** `blocks` / `depends_on` / `duplicates` / `relates_to` / `subtask_of` rendered as a force-directed graph in the task drawer. Click a node, the drawer follows.
- **Search.** SQLite FTS5 over the JSONL event log; structured-query bar (`assignee:engineer-1 label:bug priority>=high cycle:current`) matching Linear's idiom.
- **External-ref ingestion.** GitHub issues, Notion pages, support tickets land as `task_created` events with `external_ref` set. Crawfish remains authoritative; the external system is mirrored.

**Personas:** Solo founder (T1), Small CEO (T1), Engineer IC (T1), Manager (T2).

**Sequencing:** P3 ships the kanban + structured criteria + token budget. P4 ships AI triage + auto-decomposition + capability routing. P5 ships the cycle planner and the linked-task graph.

### 3.3 Local agent filesystem — Obsidian for agents

**Inspiration:** Obsidian's local-first, markdown-native, graph-aware vault model. Combined with **LightRAG**, **CRDTs**, **Git Worktrees**, and **LLM Wiki** patterns we've referenced in BRAINSTORM and elsewhere.

The current `~/.crawfish/orgs/<id>/files/` ships REST CRUD with path-escape protection and a 1 MiB cap. That is the floor. The Stage 1 vision is dramatically larger.

**Three logical zones, evolved from Phase 4:**

1. **`org-fs/scratchpad/`, `org-fs/outputs/`, `org-fs/agent-memory/`** — internal working memory. Mutable, *not* indexed for RAG.
2. **`org-fs/knowledge/`** — human-curated markdown (runbooks, ADRs, specs, decisions). Indexed.
3. **`org-fs/external/`** — declared in `org.json.knowledge_sources`: `{ kind: "repo"|"url"|"files", path|url, include?, exclude? }`. Indexed by reference.

**New mechanisms layered on top:**

- **CRDT for concurrent writes.** Two agents on the same file in different worktrees should not race. Each markdown file is materialized through a Yjs-equivalent CRDT layer (text-only, no rich-text gymnastics). The on-disk form remains plain markdown; the CRDT lives in `.crawfish/state/crdt/`. Conflicts resolve to a single authoritative file plus a `merge.jsonl` audit trail.
- **Git worktrees per agent.** Long-running agents on overlapping code paths each operate inside `git worktree`-isolated checkouts under `~/.crawfish/worktrees/<agent-id>/`. The lead agent reviews PRs into the canonical worktree. This kills the "two teammates clobber each other's edits" failure mode that AGENT-TEAMS.md warns about today.
- **LightRAG over the knowledge zone.** Local-only RAG: SQLite + `sqlite-vec`, embeddings via `transformers.js` (`Xenova/all-MiniLM-L6-v2`, CPU). Adds **knowledge graph extraction** — entities + relationships per document, surfaced as a navigable LLM Wiki. Citations carry `source_id`, `path_or_url`, `chunk_text`, `score`, and (where the graph applies) `entity_path`.
- **LLM Wiki view.** A dash tab that renders `org-fs/knowledge/` as a wiki — backlinks, graph view, full-text search, "what links here," and "what would an agent retrieve if it asked this question right now." This is the founder's "what does my company actually know" surface, and it doubles as a quality-control surface for the RAG.
- **MCP tool surface.** `knowledge_query`, `knowledge_ingest`, `knowledge_list_sources`, plus new `knowledge_write` (with the CRDT layer enforcing safety) and `knowledge_graph_walk` for traversing entity relationships.
- **Sync to Obsidian.** Optional: if the user has an Obsidian vault, point `org-fs/knowledge/` at it. Obsidian is the editor; Crawfish is the agent-facing index. No fork, no plugin, no proprietary format.

**Personas:** Solo founder (T1), Engineer IC (T1), Manager (T2), Research lead (T3).

**Sequencing:** P4 ships the three zones + LightRAG. P5 ships the LLM Wiki view + Obsidian sync. P6 ships CRDT-coordinated writes + git-worktree isolation per agent.

### 3.4 Preinstalled skill backbone + Agentic OS features

**Inspiration:** the "Anthropic skills" pattern. A skill is a folder with a `SKILL.md` and any helper assets; the runtime loads it when a trigger matches. Crawfish should not just ship agents — it should ship *agents that know how to do real office work out of the box*.

**Stage 1 deliverable: the Crawfish Skill Pack.**

A vendor-neutral skill collection that any agent in any Crawfish org can invoke. Skills are MIT, live in `~/.crawfish/skills/`, can be installed per-org or per-agent, and the lens diagnoses engine knows which skill should have been invoked when an agent fails.

Starting set:

- **`document.docx`** — produce professional Word documents (covers letters, memos, reports). Already in the Cowork skill set; we wrap it for Crawfish.
- **`spreadsheet.xlsx`** — produce Excel with formulas, charts, formatting. Same pattern.
- **`presentation.pptx`** — slide decks with layouts and speaker notes.
- **`pdf.fillform`** — fill an interactive PDF (HR forms, invoices, contracts).
- **`email.draft`** — compose an email in the user's voice using `org-fs/knowledge/voice/`.
- **`calendar.schedule`** — propose meeting times that respect everyone's calendar.
- **`web.research`** — multi-source web research with citations and bias check.
- **`web.useReplace`** — see §3.7 (Pilot Protocol direction).
- **`code.review`** — diff-aware code review against the org's `crawfish.yaml`.
- **`code.test`** — generate tests from acceptance criteria. See §3.10.
- **`code.visualAudit`** — Playwright-driven visual diff. See §3.10.
- **`brand.image`** — image generation pinned to the org's brand guide.
- **`crm.touch`** — log a CRM touch against the org's chosen connector.
- **`org.standup`** — generate the daily standup (see §3.11).
- **`bench.regress`** — run the org's benchmark suite and flag regressions.

**Agentic OS features (the deeper layer):**

The skill pack is half of it. The other half is making Crawfish behave like an *operating system* — agents can read each other's outputs, pipe between each other, persist state, and be addressable.

- **A real `~/.crawfish/bin/`.** Each agent in an org is an executable: `~/.crawfish/bin/triage-agent < ticket.txt > suggestion.md`. The shell can pipe between them. This is the "agents as Unix processes" frame.
- **A real `~/.crawfish/proc/`.** Live processes are introspectable: `cat /proc/<agent-id>/status` shows running task, token burn, last activity.
- **A real `~/.crawfish/etc/`.** Configuration lives where it always has — flat files, version-controlled.
- **A `crontab` for agents.** Already in `crons.json`; Stage 1 promotes it to a first-class CLI: `crawfish crontab -e`.
- **Capabilities, not roles.** Per-agent ACL list — what the agent *can* do (file paths, MCP tools, runtime providers, network egress allow-list). Enforced at the orgctl layer.
- **A `journalctl`-equivalent.** `crawfish journal -u triage-agent --since 1h` shows what that agent did, with token cost.

**Personas:** all of T1; Manager (T2).

**Sequencing:** P3 ships the first six skills + the `bin/` and `crontab` surfaces. P4 ships the rest of the skill pack + `proc/` and `journal`. P5 ships capabilities/ACL.

### 3.5 The Crawfish IDE

**Inspiration:** Cursor and Zed's agent-native IDE pattern. Crawfish needs its own because the IDE is where the engineer-IC persona lives — and the IDE is where token-discipline policy can be enforced *before* a bad tool call hits the wire.

The Crawfish IDE is **not** a fork of VS Code from scratch — it is a thin extension over Code OSS that ships with:

- **The Crawfish sidebar.** Sessions, agents, board, optimizers. Same surface as the desktop dash, in the editor.
- **The PreToolUse hook, in-editor.** Policy violations are surfaced as inline diagnostics, not as a separate panel. Click-to-fix patches the tool call to use the recommended optimizer.
- **The org-fs in the file tree.** `org-fs/knowledge/` shows up as a virtual folder; edits go through the CRDT layer.
- **Agent dispatch from inline comments.** Type `// @agent code-reviewer: please look at this function` and the agent picks up a task on the board.
- **Live token meter in the status bar.** Per-session, per-agent.
- **Worktree switcher.** One click between your active worktree and any agent's active worktree.
- **Codespaces parity.** See §3.8.

**Personas:** Solo founder (T1), Engineer IC (T1), Platform engineer (T2).

**Sequencing:** P5 ships v0.1 (sidebar + hook + token meter). P6 ships worktree switcher + agent dispatch + Codespaces parity.

### 3.6 The Claude Code founder dashboard

**Inspiration:** the founder demographic. They are 80% on Claude Code already; they need a dashboard *for that*, not yet-another-thing-to-install.

Crawfish-dash already has Sessions and analytics. Stage 1 makes it the obvious dashboard a Claude Code founder opens every morning.

**Concrete additions:**

- **"What did my agents cost me yesterday" widget** on Home. Per-agent, per-task-type, per-runtime. Top-three sinks called out by name.
- **Live session strip.** One row per in-flight Claude Code session, with token burn rate, current tool, and an emergency-stop button (kills the underlying process and refunds the rest of the task's budget).
- **Compounding-factor headline KPI.** `total_subagent_tokens / parent_useful_tokens` per session, per agent, weekly trend.
- **Diagnoses inbox.** Every fired rule lives here until acknowledged; clicking the diagnosis applies the recommended fix (install an optimizer, edit the policy, swap to a cheaper runtime).
- **"Replay this session."** Journey-timeline view (see §3.13).

This is largely Phase 3 polish; it gets called out separately because *naming it the founder dashboard changes how we tell the story*.

**Personas:** Solo founder (T1), Engineer IC (T1).

### 3.7 Web for agents — use, then replace

**Inspiration:** Pilot Protocol. Today browser optimizers like `crawfish-opt` shave token cost on existing sites; Pilot's argument is that agents should not be visiting human-shaped sites at all — there should be an *agent-native* protocol layer.

Crawfish's pragmatic position is **dual-track**:

- **Track A — use today's web well.** The `crawfish-opt` browser optimizer (already shipped at v0.2) wraps Playwright + a Haiku semantic summarizer + a zone-based DOM index. This is the floor. Stage 1 adds (a) site-specific *recipes* for the highest-traffic agent destinations (Stripe, AWS, Linear, Notion, GitHub UI, Google Workspace admin), each cutting tokens 5–10× vs. blind DOM read; (b) a session-replay cache so the same `browser_navigate` to the same URL within a window hits a local store.
- **Track B — provide an agent-native edge.** A Crawfish-hosted (or self-hostable) **agent-web proxy** that re-exposes common consumer/SaaS endpoints in a token-thin, JSON-shaped, capability-scoped form. Each backend has an adapter; each adapter is benchmarked against the naive-Playwright baseline. Over time the proxy becomes the preferred path and the human-DOM optimizer is the fallback. When the destination *itself* publishes an agent-native protocol (PiP, Pilot Protocol, or similar), Crawfish adopts it natively and the proxy becomes a passthrough.

This is the only way to honestly resolve "use the web, replace the web" — give the user both, measure both, and let the proxy beat the optimizer over time.

**Personas:** Solo founder (T1), Engineer IC (T1), Support lead (T3).

**Sequencing:** P4 ships site-recipes + replay cache. P5 ships the proxy MVP with two backends. P6 onward grows the proxy.

### 3.8 Local Agent Codespaces

**Inspiration:** GitHub Codespaces. Each agent should get a clean, reproducible, isolated environment — but locally, without the Microsoft tax, and with the agent's worktree + skills + env pre-mounted.

**Specific feature set:**

- **`crawfish space create <agent-id>`** — spins up a Devcontainer-shaped sandbox: a Docker container, the agent's worktree mounted, `org-fs/` mounted, the agent's policy bundle wired in, the agent's MCP tool list mounted as `/etc/crawfish/mcp/`.
- **`crawfish space attach <agent-id>`** — drops into a shell *as that agent*. Useful for the engineer-IC who wants to inspect what an agent is seeing.
- **`crawfish space exec <agent-id> -- <cmd>`** — run a command inside that space. The agent can do this too via a sandboxed MCP tool.
- **Resource ceilings.** Per-agent CPU, RAM, network egress caps. Enforced via cgroups (Linux) and a launchd profile (macOS).
- **Snapshot + branch.** A space is a Git branch; freezing it captures the working tree, env vars, and a hash of the policy bundle. Useful for "re-run the same task under the same conditions next week."
- **Hosted variant.** In Stage 2, these spaces become hosted. See §4.

**Personas:** Solo founder (T1), Engineer IC (T1), Platform engineer (T2).

**Sequencing:** P5 ships local. Hosted is Stage 2.

### 3.9 Agent CI/CD — the test-and-visual-audit pair

**Inspiration:** the current CI gate culture. Stage 1 introduces two specialist agents that earn their keep by closing the test feedback loop without a human.

- **Test-generating agent.** Triggered on every PR that lacks coverage delta. Reads the diff, the linked CrawfishTask's acceptance criteria, the repo's existing test conventions, and produces a coherent test file. Tests run in the agent's Codespace; failures land as comments on the PR with a proposed fix.
- **Visual-auditor agent.** Playwright-driven. Per PR, runs the app, takes screenshots of every route (baseline from `main`, candidate from the PR branch), diffs them, and posts a visual changelog. Catches the "I changed one CSS variable and the whole sidebar moved" class of bug. Wraps the existing `crawfish-opt` browser primitives.

These are both shipped as preinstalled agents inside the `dev-shop` template and as standalone marketplace containers any org can install. Both follow the optimizer contract (`tokens_used` on every response).

**Personas:** Engineer IC (T1), Platform engineer (T2), Manager (T2).

**Sequencing:** P5 ships test-generation. P6 ships visual audit.

### 3.10 Developer-task crons

**Inspiration:** the existing `crons.json`/`node-cron` daemon. Stage 1 ships the *recipes* a founder actually wants to run on a schedule.

Preinstalled cron templates:

- **Daily standup.** A manager agent reviews every in-progress task on the board, writes a one-screen status summary, posts to a Crawfish channel and (optionally) emails it.
- **Weekly token review.** Per-agent, per-task-type. Flags drifters.
- **Backlog grooming.** A planning agent reviews unassigned tasks, suggests assignees, updates priorities.
- **Stale-task sweep.** Tasks idle >N days get a comment from the manager agent ("still relevant?") and auto-close after the configured timeout.
- **Friday roundup.** "What shipped this week," human-readable, exported to email or `org-fs/outputs/roundups/`.
- **Security sweep.** Reads each agent's `capabilities`, the policy bundle, the MCP tools list. Flags anything new since last week.
- **Knowledge digest.** Re-indexes the knowledge zone; if any new high-importance documents landed, summarizes them and pushes to the standup.

These ship as JSON entries in the template's `crons.json`; users edit them in the Crons tab. Each is invocable on-demand from the Crons UI with one click ("run now").

**Personas:** Solo founder (T1), Small CEO (T1), Engineer IC (T1).

### 3.11 Token minimization — the deepest moat

**Inspiration:** the Anthropic costs page; the brutal reality that an agent team uses ~7× the tokens of a single agent on the same task. This is *the* differentiator. Crawfish lives or dies on whether the agent company is cheaper than the human one.

The optimizer layer already exists. Stage 1 adds the *context-discipline* pair (§7 of BRAINSTORM.md) and the manager-agent governance layer.

**The token-discipline optimizers (BRAINSTORM §7 promoted to Stage 1):**

1. **`crawfish-opt-context`** — managed proxy in front of Anthropic's `clear_tool_uses_20250919` context-editing beta. Per-tool TTLs, exclude-from-clear lists, every clear logged to lens. Anthropic's own number: **84% reduction on a 100-turn web-search eval.**
2. **`crawfish-opt-artifact`** — durable-reference returns. Tools producing big payloads (test logs, web fetches, DB dumps, screenshots) write to `~/.crawfish/artifacts/<id>` and return `{artifact_id, summary, next_action}`. Pairs with `opt-context`.
3. **`crawfish-opt-mcp-shrinker`** — proxy that lazy-loads other MCP servers' tool schemas. Atlassian measured **70–97% bloat** in re-sent tool definitions. Highest cross-stack leverage.
4. **`crawfish-opt-fork`** — fork-aware subagent spawner. Collapses N parallel `cache_control` markers into a single trailing breakpoint; prefers forked subagents reusing parent prompt cache. **59% measured savings** (ProjectDiscovery).
5. **`crawfish-opt-logs`** — streaming tail+head+error-extraction filter for `npm test`, `cargo build`, stack traces, `kubectl logs`.
6. **`crawfish-opt-codebase` repomap mode** — Aider-style tree-sitter symbol map, PageRank-ranked, token-budgeted. **46.9% measured reduction** (Cursor A/B).
7. **`crawfish-opt-toon`** — TOON serialization for tabular tool returns. **30–60% input-token reduction.**

**Caching agentic behaviors:**

When an agent solves a task, the trajectory (sequence of tool calls + reasoning) is hashed against the task type and the input shape. The next agent facing a similar task — same `label`, same input hash class — gets the prior trajectory as a *hint* in the system prompt: "an agent previously solved a task like this with these tool calls; consider this path before deriving from scratch." Effectively prompt-cache for *plans*, not just tokens. Trajectories live in `org-fs/agent-memory/trajectories/`.

**Dynamic model switching:**

Inspired by Perplexity's router. Stage 1 ships a **per-task model picker**: a cron-time decision based on the task's `label`, its acceptance criteria, and historical success rates per model. The agent's `runtime` field becomes a *default*; the router can downgrade to Haiku/GPT-4.1-mini for routine work and upgrade to Sonnet/Opus only when the task warrants it. Surfaced in the Crons UI as a "model strategy" column per task type.

**Manager-agent layer — spot the rogue spenders:**

A built-in `cost-manager` agent (preinstalled in every org template) does the following:

- Scans the prior 24h of token burn per agent, per task.
- Flags agents whose `avg_tokens_per_task` jumped >2σ from their 7-day baseline.
- Pauses the offender if it crosses a configurable hard cap. Pauses are reversible by a human in two clicks.
- Posts a post-mortem with the diagnoses-engine's best guess at the root cause.

**Personas:** all of T1; Manager (T2); Finance (T3).

### 3.12 Communication-graph visualization

**Inspiration:** the topology already in `crawfish-lens/src/topology.ts`. Today it's a single-session view; Stage 1 makes it the *org*-level flow graph that the user has asked for.

- **Org-level flow.** Across every session and every agent in the org, nodes = agents + humans, edges = communication events. Click an edge → the actual log of messages between those two agents in the window.
- **Edge weight = token volume.** Edge color = cost intensity. Edge style = task-completion-rate (dashed under threshold).
- **Time scrubber.** Replay how work moved through the org over a day, a week, a quarter.
- **Drill-in to journey.** Click a task on the edge → opens the journey timeline view (BRAINSTORM §3).
- **Pattern detection.** "Agent A only ever sends to Agent B" → suggest pipeline pattern. "Three agents all read the same five files" → suggest shared artifact + `opt-context`.

**Personas:** Engineer IC (T1), Platform engineer (T2), Manager (T2), Research lead (T3).

**Sequencing:** P3 ships single-session topology (existing). P4 ships org-level overlay. P5 ships time scrubber. P6 ships pattern detection.

### 3.13 Dual analytics — Dev + Product

**Inspiration:** LangSmith (dev side), Pendo (product side). Crawfish already has the dual-analytics toggle in dash; Stage 1 makes both sides actually deep.

**Dev-side analytics surface (LangSmith parity, plus the things they lack):**

- Trace per session, span per tool call, event per reasoning turn — exportable as OpenTelemetry (BRAINSTORM §6d). Drop into Datadog, Honeycomb, Tempo with no per-tool work.
- Per-agent: tokens by tool, cache hit rate, error rate, retry rate.
- Per-model: latency P50/P99, refusal rate, token efficiency vs. competitors.
- The compounding-factor scoreboard. Top three offenders, week over week.
- The diagnoses feed. Every rule that fired, with the recommended fix and whether it was acted on.

**Product-side analytics surface (Pendo parity, for agent-driven products):**

- Task-completion rate (did the agent solve what the user asked?).
- Re-prompt rate (how often did the user have to rephrase?).
- Escalation-to-human rate.
- Failure-mode clustering (LDA over `task_status="failed"` reasons).
- Token cost per resolved user request — the product-side cost-per-acquisition equivalent.
- Funnel views — onboarding agent → first-task agent → support-agent → upsell.

Both surfaces are exportable as CSV/Parquet, both have a webhook bus (`task.completed`, `diagnosis.flagged`, `policy.block`) for plumbing into Slack/Linear/Notion etc. The CEO persona reads the product side; the engineer reads the dev side; the manager reads both.

**Personas:** Small CEO (T1), Engineer IC (T1), Platform engineer (T2), Manager (T2), Support lead (T3).

---

## 4 · Stage 2 — Medium Companies (months 9–24)

The single-machine local-first posture works through Stage 1. Stage 2 is the move to **hosted, multi-user, multi-machine** — without breaking the local-first story for solo users. Stage 2 is also where pricing starts.

### 4.1 Hosted everything (opt-in, never required)

Inspiration: HyperAgent for hosted OpenClaw. The Stage 2 cloud is a complement, not a replacement.

- **Hosted OpenClaw orchestrator.** The current `crawfish-orchestrator` (planned C2.P3) bundles OpenClaw + a config + a lens hook into a local daemon. Stage 2 hosts that bundle: an organization clicks "deploy", gets a managed OpenClaw instance with the org's policy bundle preloaded, the org's MCP servers pre-wired, and SSO. Connects back to the user's local dash over a signed event stream (no plaintext transcripts leave the tenant).
- **Hosted agent filesystem.** The org-fs becomes a multi-tenant S3-backed store with per-file ACL, server-side encryption, and a hosted LightRAG index. Per the local-first contract, hosting is opt-in; the local copy remains canonical.
- **Hosted Codespaces.** §3.8's local spaces graduate to a hosted variant. Each agent's space is a real container in a real fleet, snapshot-able, branchable, billable to the org.
- **Hosted dashboard.** The team-mode dashboard that aggregates across all engineers in the org. Replaces "every engineer runs their own lens" with "every engineer streams to a shared lens."

Pricing trigger for Stage 2: the first time a team asks for cross-engineer aggregation we can't already supply.

**Personas:** Manager (T2), Platform engineer (T2), Finance (T3), Compliance (T3).

### 4.2 Recreate Pilot Protocol on Crawfish servers

**Inspiration:** Pilot Protocol's vision but built natively into the Crawfish hosted stack. By the time Stage 2 lands we will have shipped enough agent-web proxy adapters (§3.7 Track B) to make hosting the proxy a real product.

Specifically:

- **The agent-web gateway.** Crawfish-hosted; per-tenant rate limits, per-tenant capability scopes, per-tenant audit. Every adapter (Stripe, AWS, Linear, Notion, etc.) is a benchmark-gated module.
- **An open submission process** for adapters — `crawfish-web-adapters/<service>/`, MIT licensed, must pass the contract (token-thin response, structured shape, capability-scoped). Community-maintained.
- **Optional fall-through to upstream APIs.** If the user has direct API credentials for the upstream, the proxy is a passthrough that just attests to the call. If they don't, the proxy uses Crawfish credentials and bills the user.

This is the bridge between the local optimizer and a real internet of agents. Crawfish does not invent the protocol — it ships *the working version* until the standards catch up.

### 4.3 RL training of agent-first models

**Inspiration:** the realization that Crawfish has, by Stage 2, the world's largest dataset of *labeled* agent trajectories — every CrawfishTask carries acceptance criteria, every successful task has a verified outcome, every failure has a structured reason. This is the perfect substrate for RL fine-tuning.

The play is **not** "train a frontier model from scratch." The play is:

- **Per-org fine-tunes.** A medium company opts in to having its anonymized trajectories used to fine-tune (RLHF-style) the smallest open model that can plausibly run the org's task mix. The output is a single distilled checkpoint that ships to that org's hosted runtime and runs at fraction-of-cost vs. Sonnet on the org's actual task distribution. This is the "train the org" line.
- **Cross-org benchmark.** A public benchmark of "given this CrawfishTask schema and these MCP tools, do the task." Crawfish publishes weekly; vendors target it; competition drives down per-task cost and our customers benefit.
- **Distilled specialists.** The cost-manager agent, the triage agent, the test-generator — each becomes a distilled model card that small companies can run on a single GPU.

This is the Stage 2 R&D bet that earns the right to be expensive in Stage 3.

### 4.4 Invite employees — multi-user, multi-machine, real identities

Today every Crawfish org is single-machine. Stage 2 makes them real organizations:

- **Real human accounts.** Local sign-in upgrades to a tenant; every event in the org carries an actor ID; Crawfish becomes a real source of audit truth.
- **Per-employee Crawfish IDE preinstall.** A new engineer joins; their first day is `crawfish join acme.com`, IDE auto-configures, hooks auto-install, agents inherited from the team template are pre-attached.
- **Employee dashboards.** Each engineer sees their own session list, their own cost, their own compounding factor. Privacy-preserving: managers see aggregates not transcripts unless they own the policy that grants access.
- **"Train the org" telemetry.** Every employee's Claude Code session (opt-in) flows to the hosted lens. The org learns: what tools are most used, which optimizers would save the most, which agents have the highest leverage. This data goes back into §4.3 if the org opts in.

### 4.5 Manager-grade employee analytics

This is the medium-company-manager (T2) home screen. Aggregates of:

- Token spend by team, by engineer, by task type, by repo.
- Compounding factor by team. Week-over-week.
- "Top sinks" — which tools and which tasks across the org are eating the most. Always recommends an action.
- Engineer-level views, with the **privacy contract**: managers see counts and shapes (e.g., "Engineer A spent 4× their team's median on bash log-tailing this week"), but not transcripts. To see transcripts, the engineer must explicitly approve, or a compliance policy must grant access for incident review.
- Anomaly alerts — surfaced as Crawfish notifications, not emails the manager can ignore.

### 4.6 24/7 issue tracking

Today's board is a state machine that humans drive. Stage 2 makes it a **continuously-running pipeline**:

- **Always-on triage.** Inbound channels (support email, GitHub Issues, Slack hand-off, Notion forms, customer feedback widget) flow to a triage agent that runs 24/7. Every inbound event lands as a task in <2 minutes with proposed labels and acceptance criteria.
- **Always-on planning.** A planning agent on a 6h cron rebalances the cycle: detects slip, surfaces blockers, recommends re-prioritization.
- **Always-on customer-facing handoff.** If a triaged ticket needs a human and no human is on shift, the system holds the customer (auto-acknowledgement with realistic ETA) and pages the on-call human via the org's chosen channel.

### 4.7 Org knowledge layer + RAG, at scale

By Stage 2 we have rebuilt LightRAG and the LLM Wiki in §3.3. Stage 2 generalizes:

- **Cross-source ingestion** — Confluence, Notion, GitHub wikis, Google Drive, the company Slack archive (opt-in, scoped). All flow into `org-fs/external/` with provenance preserved.
- **Entity-aware graph.** People, projects, products, code-modules, customers — extracted from all sources, deduped, surfaced in the LLM Wiki.
- **Authority scoring.** Documents are ranked by recency, by who wrote them, by who edited them last, by how often they're cited internally. Stale ADRs get downweighted automatically.
- **Citation enforcement.** Every agent answer that draws on the knowledge layer must carry citations. The diagnoses engine fires on uncited claims.

### 4.8 Advanced agent generation

The Stage 1 templates are static. Stage 2 ships **agent synthesis**:

- **Generate-an-agent.** Describe the role in three sentences ("a code-reviewer who knows Rust and our error-handling conventions, comments inline only on changes that affect the public API, and never approves a PR that adds a `panic!`"). Crawfish synthesizes an `AgentContainer` JSON, a `SKILL.md` skill bundle, a starter policy, an initial benchmark suite.
- **Iterate-on-an-agent.** "Make my code-reviewer 30% cheaper without losing accuracy." The synthesizer profiles the current agent against its bench, swaps in cheaper tools, prunes the system prompt, re-evaluates, ships a new version. Old version stays one click away.
- **A/B between versions.** Run two versions of the same agent against the next 100 inbound tasks; surface the winner with token + accuracy deltas.

### 4.9 Marketplace — agents, skills, optimizers

The current marketplace is optimizers-only. Stage 2 generalizes to:

- **Agent containers.** Versioned, signed `AgentContainer` JSON with a starter `org-fs/agent-memory/` payload and a benchmark profile. Install drops them into your org with one click.
- **Skill packs.** Bundled `SKILL.md` collections. Free, MIT.
- **Optimizers.** As today.
- **Templates.** As today.

Submission flow: PR to the umbrella, CI runs the standard benchmark, the entry lands in the marketplace tab with verified numbers. Optional paid distribution (revenue share TBD) for premium agents.

### 4.10 Pricing posture — first hint

Stage 1 stays free and local. Stage 2 introduces paid tiers along these axes:

- **Hosted orchestrator** (per agent, per month).
- **Hosted Codespaces** (per agent-hour, with a free tier).
- **Hosted RAG** (per org, by document count).
- **Team aggregation** (per seat, after a free 3-seat tier).
- **Premium marketplace agents** (revenue share).

Compliance/SOC2 features are not paywalled separately — they ship in the team tier once they exist.

---

## 5 · Stage 3 — Enterprises (months 18+)

The user's brief said "and more"; this is the "more." We don't pursue Stage 3 unless Stage 2 is paying. But the surface area is worth pinning so we don't paint ourselves out of it.

- **SSO / SAML / OIDC.** Phase 6 lands this. Mandatory for any company over ~200.
- **RBAC.** Every action — task transition, policy edit, agent install, knowledge ingest — is gated on a role. Roles are org-scoped, customizable.
- **Compliance tier.** Audit export (SOC2-shaped), retention policies, agent action attestation (signed proof that action X was taken by agent Y under policy Z), data residency (EU tenant, on-prem option).
- **On-prem deployment.** Helm chart + sealed-secrets pattern. For the enterprises that won't accept a hosted Crawfish, every hosted feature has an on-prem mode that runs in their VPC.
- **Vendor procurement kit.** A pre-built BAA, a SOC2 Type II report, a model-card pack for every preinstalled agent. The procurement-friction killer.
- **The Crawfish Bench Suite as an enterprise dashboard.** Compounding factor, token spend per FTE-equivalent, agent ROI report. The thing a CFO uses to defend the AI line item.
- **Anthropic + OpenAI co-sell.** Crawfish becomes the orchestration layer those vendors recommend for serious customers; their billing flows through us so we can attribute per-task cost back to the source.

---

## 6 · Cross-cutting technical bets

A handful of decisions cut across both stages. Calling them out so they don't get re-litigated:

- **Local-first is non-negotiable through Stage 2.** Even hosted features have a local equivalent; data never leaves the user's machine without explicit opt-in.
- **JSONL is the source of truth.** SQLite indexes are rebuildable; the on-disk JSONL log under `~/.crawfish/orgs/<id>/` is canonical.
- **MCP everywhere.** Every cross-process surface — agents to orgctl, orgctl to lens, optimizers to runtimes — uses MCP. Anything else is an internal HTTP API.
- **Tokens are the unit of account.** Dollars are an opt-in overlay. Every metric in the system is denominated in tokens first.
- **Open standards over vendor JSON.** OTel for traces, Prometheus for metrics, OpenAPI for the REST surface, Yjs-shaped CRDT for shared text, SQLite FTS5 + sqlite-vec for indexes.
- **CRDT + worktree isolation is the multi-agent safety net.** AGENT-TEAMS.md describes the ownership rules a teammate must follow today. Stage 1's CRDT layer makes those rules enforceable without trusting the teammate.
- **The diagnoses engine is the conscience.** Every product surface that touches an agent should also be able to fire a rule. Diagnosis-first design.
- **No persistent database we can't replace.** SQLite is fine because it's a file. We do not adopt Postgres until the hosted tier mandates it.
- **No third-party push services by default.** Notifications go in-app and (via SMTP) by email. Slack / Discord / Teams bridges are user-installed adapters, not platform dependencies.

---

## 7 · Sequencing — what ships when, mapped to ROADMAP phases

The ROADMAP defines phases P0–P6. Grand Plan items slot into them as follows.

**P3 (now → 5 weeks):** Native task board + plan + governance v1. §3.2 (kanban + structured criteria), §3.4 (first six skills, `bin/`, `crontab`), §3.6 (founder dashboard), §3.10 (cron recipes), §3.12 (single-session topology), §3.13 (dual analytics MVP).

**P4 (5 → 11 weeks):** Multi-LLM runtimes + GitHub bridge + knowledge layer. §3.1 (industry templates), §3.2 (AI triage + auto-decomposition), §3.3 (three zones + LightRAG), §3.7 Track A (site recipes), §3.11 (`opt-context` + `opt-artifact`), §3.12 (org-level overlay).

**P5 (11 → 16 weeks):** Native messaging + cloud sync stub + team dashboard + marketplace. §3.3 (LLM Wiki + Obsidian sync), §3.5 (Crawfish IDE v0.1), §3.7 Track B (proxy MVP), §3.8 (local Codespaces), §3.9 (test-generation), §3.11 (caching trajectories + dynamic model switching + cost-manager agent), §3.12 (time scrubber), §3.13 (Pendo-parity product side).

**P6 (open-ended):** Native code review + compliance + CI + runtime adapters. §3.3 (CRDT + git-worktree), §3.5 (IDE worktree switcher), §3.7 Track B (more adapters), §3.9 (visual-auditor), §3.12 (pattern detection). Begin Stage 2.

**Stage 2 (months 9 → 24):** §4 wholesale.

**Stage 3 (months 18+):** §5, gated on Stage 2 revenue.

---

## 8 · Persona scorecard — does this plan light each persona up?

A check that the plan actually serves the people we're building for. Each cell is "yes / partial / no" for what's covered by the end of Stage 1.

| Persona | Templates (3.1) | Issue tracking (3.2) | Local FS (3.3) | Skills (3.4) | IDE (3.5) | Founder dash (3.6) | Web (3.7) | Codespaces (3.8) | CI/CD (3.9) | Crons (3.10) | Token min (3.11) | Comms graph (3.12) | Analytics (3.13) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Solo founder | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | partial | ✅ | ✅ | ✅ | ✅ |
| Small CEO | ✅ | ✅ | partial | ✅ | partial | ✅ | partial | no | no | ✅ | ✅ | partial | ✅ |
| Engineer IC | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Platform eng | partial | ✅ | ✅ | ✅ | ✅ | partial | ✅ | ✅ | ✅ | partial | ✅ | ✅ | ✅ |
| Manager | partial | ✅ | partial | partial | partial | partial | no | partial | ✅ | partial | ✅ | ✅ | ✅ |
| Finance | no | partial | no | no | no | partial | no | no | no | no | ✅ | no | ✅ |
| Support lead | ✅ | ✅ | partial | partial | no | no | ✅ | no | no | ✅ | partial | partial | ✅ |
| Research lead | ✅ | ✅ | ✅ | partial | partial | partial | partial | ✅ | no | partial | ✅ | ✅ | ✅ |
| Compliance | no | partial | partial | no | no | no | no | no | no | no | partial | partial | partial |

The gaps are deliberate. Compliance is a Stage 3 persona; Finance is half-covered because token-discipline serves them even if a P&L view doesn't ship until Stage 2; Support lead and Research lead are well-covered through analytics but need a few persona-specific polish items in Stage 2.

---

## 9 · Anti-goals — what we will not build

To keep the surface honest:

- **No required dependence on external trackers / chat / review.** Crawfish remains authoritative. Integrations are *additive*.
- **No hosted SaaS through Stage 1.** Single-machine for the first 9 months; cloud is Stage 2 and explicitly opt-in.
- **No "AI productivity score" for employees** that pretends to measure performance via token spend. The §4.5 manager analytics ship with a privacy contract; the contract is the product.
- **No auto-installation of optimizers / agents / skills.** Every install is explicit.
- **No autonomous mutation of the codebase by default.** The visual-auditor and test-generator post PRs; humans merge.
- **No persistent database we can't migrate off in a weekend.** JSONL + SQLite as long as humanly possible.
- **No paywalling of compliance.** SOC2 / SSO / audit live in the team tier and are not separately priced.
- **No frontier-model training from scratch.** We fine-tune over the agentic-task substrate; we do not pretend to be a model lab.
- **No bridging the local org to a third-party messaging tool as a workflow dependency.** Crawfish messaging is native.

---

## 10 · Success metrics

The numbers that say we're winning, by stage.

**Stage 1 (end of month 9):**

- 10,000 weekly active local installs.
- Median Crawfish org's compounding factor drops 35% within 30 days of install.
- Median solo founder ships their first agent task within 15 minutes of install.
- 50 community-submitted templates / skills / optimizers in the marketplace.
- ≥3 third-party runtime adapters live and benchmarked (`openclaw`, `cursor`, `cline` or equivalent).

**Stage 2 (end of month 24):**

- 100 paying teams.
- $X ARR (set internally; not a public target).
- 5 published RL fine-tune cards, each beating Sonnet-baseline on the org's task mix at <50% cost.
- 10 marketplace agents with >1000 installs each.
- Manager dashboards used weekly by ≥80% of paid orgs.

**Stage 3 (open-ended):**

- First Fortune 500 deployment, on-prem.
- SOC2 Type II.
- A line item on the typical agent-using company's tooling stack.

---

## 11 · One-paragraph summary

Crawfish in 24 months is the OS for agent-native companies: a founder picks a template and gets a working five-agent company in fifteen minutes; an engineer's Claude Code session is a first-class member of the org with a budget, a board task, a worktree, and a manager looking over its shoulder; a platform engineer at a 200-person company has one screen that shows every agent in the company, what it cost, what it produced, and whether it's about to do something stupid; a CFO has a forecastable line item; a compliance officer has an audit export; and a research lead has a swarm that doesn't read the same paper thirty times. All of it built on a JSONL substrate, all of it local-first until the user says otherwise, all of it priced in tokens, and all of it shipping as MIT until the day the team-mode features make the case for a paid tier.

That is the destination. The phases get us there. The personas tell us when we've arrived.

---

*Last updated: 2026-05-16. Source-of-truth for "what's shipped" remains `ROADMAP.md`; for the half-formed ideas not yet committed here, see `BRAINSTORM.md`.*
