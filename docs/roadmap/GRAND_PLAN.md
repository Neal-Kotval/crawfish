# Crawfish — Grand Plan

> **The operating system for companies that run on AI agents.**
>
> From the solo founder spinning up their first agent to the 500-person org running a thousand of them — one platform, one task schema, one accounting unit (tokens), one place to look.

This document is the long-horizon vision. It assumes the v1 agent-org layer is already in production (see `ROADMAP.md` for what shipped on 2026-05-15) and the Phase 2–6 schedule is the near-term plan. **Grand Plan** is what we want Crawfish to be in 18–24 months, organized around the people who will use it.

Companion docs:

- `../../PRODUCT.md` — repo map / one-page pitch
- `../../ROADMAP.md` — phased build schedule (P0–P6)
- `../product/BRAINSTORM.md` — half-formed ideas, ranked
- `../product/DESIGN.md` — design system + tokens
- `../product/INTEGRATIONS.md` — runtime adapter matrix
- `../ops/AGENT-TEAMS.md` — multi-teammate working conventions

---

## 0 · Where we are today (May 2026)

A clean baseline so the rest of this doc has somewhere to push off from.

The umbrella holds six submodules: `crawfish-lens` (observability + REST + SSE), `crawfish-dash` (Tauri-shelled React UI), `crawfish-orgctl` (MCP server giving agents `board_*` and `org_fs_*` tools), `crawfish-opt` (browser optimizer), `crawfish-opt-codebase` (codebase optimizer, 3.25× token reduction on bench), and `crawfish-app` (the native shell). Eight diagnoses rules are live (`oversized-tool-result`, `re-read-loops`, `low-cache-hit-rate`, `dom-dump-detected`, `log-truncation-pattern`, `thinking-overhead`, `grep-then-read-storms`, `agent-fanout-cost`). Four runtime providers exist (`claude-code`, `claude-api`, `openai-api`, `codex`). Six org templates are scaffolded (`startup`, `dev-shop`, `support`, `research`, `solo-builder`, `blank`). Three wizards are partly in place (`first-run`, `policy`, `prep`). OpenClaw is the only non-Claude adapter so far. Everything binds to `127.0.0.1`.

This is enough surface to demo "agents as first-class employees." It is not yet enough to be the OS for a 200-person engineering org. The Grand Plan covers that gap.

---

## 1 · The north-star vision

**The agent filesystem + librarian is the moat.** Anthropic, OpenAI, and Google will keep eating the harness layer — Managed Agents, AgentKit, Vertex Agent Builder. They will not build the **org-level knowledge substrate** plus its **learning router**: the long-lived filesystem an agent company actually runs on, with the LLM Wiki that exposes it, the RAG that retrieves over it, and — critically — the contextual-bandit librarian (§3.3.1) that learns per-org which sources to consult for which question type. The substrate alone is replicable in a quarter. The substrate plus six months of an org's accumulated bandit state is not. That is the durable surface frontier vendors structurally cannot own, because doing so means picking sides between every tool an org uses *and* spending six months learning each org's individual taxonomy from production traffic.

Crawfish becomes the place where an agent organization's institutional memory lives. The CrawfishTask is the unit of work. The **org filesystem is the unit of memory.** The flow graph is the org chart. The token meter is the wage bill.

A founder gets a working five-agent company from a template in fifteen minutes; six months later that org-fs has eaten the founder's email archive, code, Notion vault, support tickets, and meeting transcripts, and *every new agent the founder hires inherits the entire company's context* because it queries one canonical knowledge layer instead of being prompt-stuffed.

A platform engineer at a 200-person org sees every agent in the company on one flow graph, can clamp a runaway agent in two clicks, and exports the audit trail to SOC2 without writing a query.

A research team mints a new specialist by forking a marketplace container, points it at their `org-fs/knowledge/`, and that agent inherits the company's writing style, taxonomy, runbooks, and prior decisions — because the knowledge layer is a real RAG with citations and a learned source taxonomy, not a prompt-stuffing exercise.

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

**Inspiration:** Gumloop ([gumloop.com](https://www.gumloop.com)) — public template gallery with hundreds of pre-built AI workflows organized by function (marketing, sales-ops, recruiting, finance, support) and by integration (Slack/Notion/HubSpot/Salesforce). Vercel's "deploy template" one-click gesture. Linear's "create from preset" project shape.

**Specifically borrowed from Gumloop:**
- The function-axis template categorization (Marketing, Sales, Operations, Engineering, Support — Gumloop's 170+ community templates are organized exactly this way).
- "Gummie"-style **build-an-org-from-a-description** wizard: Gumloop's AI assistant takes a plain-English requirement and synthesizes the node graph; Crawfish's wizard takes a four-question intake and synthesizes the AgentContainer set + crons + initial board.
- 115+ pre-built automation blocks → Crawfish ships a comparable library of *task templates* (recurring CrawfishTask shapes with pre-filled acceptance criteria) on the same numbers scale.
- 130+ integrations → for Stage 1, Crawfish aims at 30+ MCP integrations (Slack, Notion, GitHub, Linear, HubSpot, Stripe, etc.) bundled with the relevant org templates.
- Public template marketplace with install counts as social proof (Gumloop's gallery doubles as discovery for new users).

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

**Inspiration:** Linear's core product (velocity, structured-query filters, unapologetic opinionatedness) *plus* their **Linear for Agents** release on [linear.app/agents](https://linear.app/agents) and the **Linear Agent** beta in [linear.app/next](https://linear.app/next). Linear is now the canonical example of "agents as first-class workspace members" and the bar we have to beat.

**Specifically borrowed from Linear for Agents:**
- **Agents are first-class users** — assignable to issues, addable to teams/projects, @mentionable in comments, exactly like humans. Crawfish's `AgentContainer` already maps to this; Stage 1 makes the membership UX identical to Linear's.
- **Primary assignee + contributor model** — when an issue is delegated to an agent, the human stays the primary assignee while the agent is added as a contributor. Crawfish adopts this so the human-in-the-loop signal is structural, not a comment convention.
- **Agents don't count as billable seats** — directly applicable to Crawfish's Stage 2 pricing posture: humans bill, agents don't.
- **Linear Agent** features to mirror: roadmap/issue/code-aware AI that synthesizes context, makes recommendations, takes action. This is exactly our planning + triage + auto-decomposition story below.
- **Skills + Automations + Code Intelligence** tier split (Skills on all plans, Automations/Code Intelligence on Business/Enterprise) — clean precedent for our pricing: planning surface is free, advanced governance/RL is paid.
- **Developer platform** (Linear's agent SDK + auth + behavior docs) — Crawfish ships an equivalent so third-party agents can register, mention, and act in Crawfish orgs without forking.

The current ROADMAP already commits to the native task board; the Stage 1 work below is what makes that board *better than Linear* for an agent-native company.

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

### 3.3 The agent filesystem — the moat

**This is the workstream the rest of the platform serves.** Anthropic, OpenAI, and Google will not build it; they're racing each other on the harness layer, and building a vendor-neutral knowledge substrate would force them to pick sides between every tool a company uses. That leaves the field open.

**Inspiration:** Obsidian's local-first markdown vault, Notion's database-as-a-page model, LightRAG's hybrid retrieval, CRDT-coordinated concurrent editing, Git worktrees for per-agent isolation, and the LLM Wiki pattern (entities + backlinks + graph traversal exposed to agents as a navigable surface).

The current `~/.crawfish/orgs/<id>/files/` ships REST CRUD with path-escape protection and a 1 MiB cap. That is the floor. The Stage 1 vision is dramatically larger — and the **org-fs becomes Crawfish's primary product surface** by the end of Stage 1, with the board, the dash, and the runtimes acting as views and writers on top of it.

**Three logical zones, evolved from Phase 4:**

1. **`org-fs/scratchpad/`, `org-fs/outputs/`, `org-fs/agent-memory/`** — internal working memory. Mutable, *not* indexed for RAG.
2. **`org-fs/knowledge/`** — human-curated markdown (runbooks, ADRs, specs, decisions). Indexed.
3. **`org-fs/external/`** — declared in `org.json.knowledge_sources`: `{ kind: "repo"|"url"|"files", path|url, include?, exclude? }`. Indexed by reference.

**New mechanisms layered on top:**

- **Heterogeneous-context ingestion.** The point of an agent filesystem is *not* that it stores text — it's that it ingests every kind of context a company produces and figures out how to put them in the same retrieval space without contaminating each other. The ingestion pipeline grows specialist parsers and **per-source taxonomies** for: code (tree-sitter symbol trees, repo-map ranks), email (thread reconstruction, sender authority, action-extraction), Slack/Discord/Teams archives (channel topic learning, conversation segmentation), meeting transcripts (speaker turns, decision extraction), customer-support tickets (intent + sentiment + outcome), product docs / runbooks / ADRs (canonical-status promotion), CRM records (entity binding to people/accounts), and arbitrary attachments (PDFs, images via VLM caption, spreadsheets via SheetJS). Each source has its own chunker, its own metadata schema, its own authority-decay function. The query layer is unified; the *ingest* is specialized.
- **Learned source separation.** The biggest mistake other RAGs make is merging email and code into the same chunk space. Crawfish maintains *per-source-class* embedding spaces plus a meta-router that decides, per query, which spaces to consult and how to weight them. "How do we handle refund disputes?" routes to support-tickets + runbooks + Slack-archive (not to code). "Why did we choose JSONL over Postgres?" routes to ADRs + code-review-comments + meeting-transcripts (not to email). The router is fine-tuned on the org's own click-through and citation-validation signal — every accepted answer is positive feedback for that source mix.
- **Authority + recency decay.** Documents are scored by (a) source class (an ADR outranks a Slack message on a design question), (b) author (the CTO's writeup outranks the intern's draft on the same topic), (c) recency (with class-specific decay — code's half-life is weeks, ADRs' is years), (d) citation count (how often other docs in the org-fs reference this one), and (e) explicit pinning. The scoring is surfaced in the LLM Wiki so a user can disagree and tweak.
- **CRDT for concurrent writes.** Two agents on the same file in different worktrees should not race. Each markdown file is materialized through a Yjs-equivalent CRDT layer (text-only, no rich-text gymnastics). The on-disk form remains plain markdown; the CRDT lives in `.crawfish/state/crdt/`. Conflicts resolve to a single authoritative file plus a `merge.jsonl` audit trail.
- **Git worktrees per agent.** Long-running agents on overlapping code paths each operate inside `git worktree`-isolated checkouts under `~/.crawfish/worktrees/<agent-id>/`. The lead agent reviews PRs into the canonical worktree. This kills the "two teammates clobber each other's edits" failure mode that AGENT-TEAMS.md warns about today.
- **LightRAG over the knowledge zone.** Local-only RAG: SQLite + `sqlite-vec`, embeddings via `transformers.js` (`Xenova/all-MiniLM-L6-v2`, CPU). Adds **knowledge graph extraction** — entities + relationships per document, surfaced as a navigable LLM Wiki. Citations carry `source_id`, `path_or_url`, `chunk_text`, `score`, `source_class`, and (where the graph applies) `entity_path`.
- **The LLM Wiki — the user-facing surface for the moat.** A dash tab that renders `org-fs/knowledge/` as a wiki: backlinks, graph view, full-text search, source-class facets, "what links here," "what would an agent retrieve if it asked this question right now," and a citation-validation widget where the user grades retrieved chunks ("this one is canonical / stale / wrong") and that signal feeds the router. This is the founder's *"what does my company actually know"* surface. It doubles as the quality-control surface for the RAG and as the trust-building visualization for the buyer.
- **Cross-source entity binding.** People, projects, products, code modules, customers, accounts — extracted from every source, de-duped across sources, surfaced as canonical entities in the wiki. "Acme Corp" in an email, "@acme" in Slack, "acme-co" in the customer-support DB, and `customer_id: 14` in the warehouse are recognized as the same entity and merged.
- **MCP tool surface.** `knowledge_query`, `knowledge_ingest`, `knowledge_list_sources`, plus new `knowledge_write` (with the CRDT layer enforcing safety), `knowledge_graph_walk` for entity relationships, `knowledge_explain_routing` (so an agent can introspect why it got the chunks it got), and `knowledge_promote` (to mark a source-of-truth document).
- **Sync to Obsidian.** Optional: if the user has an Obsidian vault, point `org-fs/knowledge/` at it. Obsidian is the editor; Crawfish is the agent-facing index. No fork, no plugin, no proprietary format.
- **Append-only event log on top.** Every write to the org-fs lands in `~/.crawfish/orgs/<id>/fs-events.jsonl`. The index is a projection over the log, fully rebuildable. No data is lost; every chunk's lineage is auditable back to the source document and the actor who ingested it.

**Personas:** Solo founder (T1), Small CEO (T1), Engineer IC (T1), Manager (T2), Research lead (T3), Compliance (T3).

**Sequencing:** P4 ships the three zones + LightRAG + code/email/markdown ingestion + the librarian v1 (§3.3.1). P5 ships the LLM Wiki view + Obsidian sync + Slack/Discord/Teams ingestion + per-source-class spaces + librarian v2 with cluster-aware bandits. P6 ships CRDT-coordinated writes + git-worktree isolation + cross-source entity binding + librarian v3 with two-tower retrieval and PageRank authority.

#### 3.3.1 The librarian — contextual-bandit retrieval routing

This is the mechanism that operationalizes the moat. Without it, §3.3 is "another RAG with markdown files." With it, every Crawfish org has a *learning policy* that gets visibly better over time, and that policy itself is the artifact a buyer sees.

**The problem the librarian solves.** When a new agent spawns and asks the knowledge layer a question, naïve RAG runs embedding-similarity over a single chunk store and returns the top-k. This is wrong for an agent organization for three reasons. First, the right answer depends on the *source class* — a refund-policy question wants support tickets + runbooks, a code-architecture question wants ADRs + diffs + meeting transcripts, an HR question wants policy docs + the handbook, and merging all of these into one space contaminates each. Second, the right answer depends on the *agent* — a code-review agent and a customer-support agent asking "what's our error handling convention" want different chunks. Third, the right answer depends on *what worked last time* — if the support agent's last ten "how do we handle X" queries got resolved using a specific source mix, the eleventh query should probably use that mix as a prior.

**The architecture.** A small fast LLM does the slow batch work; a non-LLM online-learning policy does the per-query routing.

- **LLM batch work (Haiku-class, runs on a nightly cron or on-ingest):**
  - **Entity extraction.** New documents are walked once; entities, relationships, authorship, and per-class metadata are extracted and stored in the knowledge graph.
  - **Cold-start priors.** When a query cluster has no feedback yet, one Haiku call seeds the initial source-mix arm probabilities — "for queries that look like this, plausible source mix is 60% code, 30% runbooks, 10% Slack."
  - **Cluster naming + drift detection.** Nightly, the LLM reads a sample of queries in each cluster, names it ("refund disputes," "deployment incidents," "pricing-page edits"), and flags clusters that look incoherent. The router re-clusters on the flag.
  - **Explanation generation.** When an agent or human asks *why* a particular set of chunks was returned, the LLM generates a one-paragraph rationale from the bandit's arm probabilities + the cluster name. This is the citation-validation UI in §3.3 made interpretable.

- **Non-LLM online policy (runs in microseconds, no GPU, no API call):**
  - **Query clustering.** Each query is embedded (transformers.js, CPU) and assigned to the nearest cluster centroid via k-means (or HDBSCAN for the adaptive cluster-count case). New queries that fall far from every centroid trigger a re-cluster on the next nightly pass.
  - **Contextual bandit per cluster.** LinUCB or Thompson sampling. Each cluster has its own bandit; arms are source-mix vectors `[code_weight, email_weight, slack_weight, runbooks_weight, tickets_weight, transcripts_weight, crm_weight]`; the bandit picks an arm based on the query's feature vector (agent role, time of day, recent task context) and the observed historical reward.
  - **Reward signal.** Every retrieval emits a reward computed from downstream signals: (a) the agent cited at least one chunk from the returned set, (b) the user did *not* immediately re-ask or rephrase, (c) the task that triggered the retrieval completed successfully, (d) the user explicitly upvoted/promoted a returned chunk in the LLM Wiki. Each signal is a separate term with a tunable weight; defaults are reasonable, the user can tweak in Settings.
  - **Learning-to-rank for within-source ordering.** Once the bandit has picked the source mix, a small gradient-boosted ranker (XGBoost or LightGBM) decides *which* chunks from each source to return. Features: recency, author authority, citation count in the org-fs graph, click history. Retrains nightly from the feedback log.
  - **PageRank over the citation graph.** Documents that other org-fs documents cite a lot get an authority boost. Purely structural; no LLM. Runs nightly.
  - **Two-tower retrieval (v3).** When the bandit has enough signal to justify it, train a tiny neural net (two parallel embedding towers, one for queries, one for chunks) on the org's own click data. Replaces the generic embedding model at query time for this specific org. CPU-trainable in an hour on a year of feedback.

**File layout.** Everything lives under `~/.crawfish/orgs/<id>/librarian/`:

- `clusters.json` — k-means centroids + cluster names + last-recluster timestamp
- `bandits.sqlite` — one table per cluster, rows are arm-vector + count + reward-sum + last-update; updated atomically per retrieval
- `ranker.lightgbm` — serialized gradient-boosted ranker, retrained nightly
- `pagerank.json` — current authority scores per document
- `feedback.jsonl` — append-only log of every retrieval + reward + signal source. The source of truth; the SQLite is a projection
- `tower.onnx` — (v3 only) the two-tower model weights

**MCP tool surface.** Three tools, mirroring the three layers:

- `knowledge_route({ query, agent_id?, task_id? }) → { source_mix, rationale, retrieved_chunks, librarian_decision_id }` — the librarian picks the source mix, retrieves, returns chunks plus a decision-id the agent can later feed back into `knowledge_feedback`.
- `knowledge_feedback({ decision_id, signal, weight? })` — the agent (or the diagnoses engine, or the user via the LLM Wiki) reports a signal. Updates the bandit + the feedback log.
- `knowledge_explain({ decision_id }) → { rationale, arm_probabilities, cluster_name, alternatives_considered })` — for debugging and for the user-facing "why did you retrieve this" view.

**The flywheel.** Every retrieval that emits a usable reward signal makes the org's librarian incrementally smarter. Over six months an org accumulates ~10k–100k labeled retrievals. The bandit's arm distribution per cluster shifts visibly; the user can see "the day Slack went from 0.22 to 0.08 of our architecture-query source mix — your team started keeping ADRs." That visualization is the moat made tangible.

**Why this is shipping-quality, not research.** Every component is decades-old well-understood ML:

- LinUCB: Li, Chu, Langford, Schapire (2010), 5,000+ citations
- Thompson sampling: 1933 original, modern bandits-textbook canon
- k-means / HDBSCAN: 1957 / 2013, every clustering library
- LightGBM / XGBoost: 2017 / 2016, the workhorse rankers
- PageRank: 1998, runs in a few seconds on a 1M-edge graph
- Two-tower retrieval: standard since 2019 (Google's "Sampling-Bias-Corrected Neural Modeling"); ONNX-deployable

There is no novel research here. The novelty is the *integration* — that all of these run locally, on a JSONL substrate, against a heterogeneously-ingested org-fs, with feedback wired to actual user behavior and task outcomes. That integration is the engineering that earns the moat.

**Demo screenshot that travels.** Six-month-old Crawfish org. The user clicks an agent's response. The Wiki opens to a dashboard: cluster name ("refund disputes"), current arm distribution (62% support tickets, 25% runbooks, 8% Slack, 5% email, 0% code), the arm-evolution graph over the last sixty days with three labeled inflection points, the three chunks returned with citation scores, the alternative chunks considered with rejection reasons. Underneath: "47 prior retrievals from this cluster, 91% completion rate, last failure 11 days ago — root cause: stale runbook (promoted to canonical)." That is the screenshot that proves the moat.

**Personas:** Solo founder (T1) — sees the visible-improvement-over-time graph and tells friends; Engineer IC (T1) — uses `knowledge_explain` to debug why an agent retrieved the wrong context; Manager (T2) — sees librarian-decision audit trail; Research lead (T3) — relies on per-cluster arm visibility to know which sources their swarm is leaning on; Compliance (T3) — every retrieval decision is logged with rationale, satisfies "explain why this agent saw this document."

**Sequencing:** P4 ships v1 — clustering + LinUCB + cold-start priors + reward signal + the three MCP tools. P5 ships v2 — LightGBM within-source ranker + PageRank authority + LLM Wiki visualization. P6 ships v3 — two-tower retrieval + drift detection + cluster auto-naming + the "arm evolution over time" view.

### 3.4 Preinstalled skill backbone + Agentic OS features

**Inspiration:** Anthropic's Skills pattern (a skill is a folder with a `SKILL.md` and any helper assets; the runtime loads it when a trigger matches — covered in the agentic-OS talk at [youtube.com/watch?v=pfPi04pIfaw](https://www.youtube.com/watch?v=pfPi04pIfaw)). Crawfish should not just ship agents — it should ship *agents that know how to do real office work out of the box.*

**Specifically borrowed from the Anthropic Skills model:**
- **Folder-as-skill** format (`SKILL.md` frontmatter + assets) is adopted verbatim. Skills installed in `~/.crawfish/skills/<name>/` work on any Claude-runtime agent without translation.
- **Trigger-by-description** — skills declare what they do; the runtime decides when to load them. Crawfish extends this with **per-org enablement** (a research org can disable `crm.touch`, an SDR org can disable `code.review`).
- **Composable building blocks** — multiple skills load into one session without conflict (the talk's core agentic-OS point). Crawfish enforces this with a per-skill capabilities manifest.

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

**Inspiration:** the founder demographic. They are 80% on Claude Code already; they need a dashboard *for that*, not yet-another-thing-to-install. Anchored on the official cost model at [code.claude.com/docs/en/costs](https://code.claude.com/docs/en/costs) — `/usage` and `/cost` slash commands, 5-hour and weekly time-windowed quotas for subscription tiers, local JSONL logs as the source of truth.

**Specifically borrowed from the Claude Code costs surface:**
- **5-hour + weekly quota meters.** Claude Code's subscription tiers (Pro, Max, Team) reset every 5 hours and weekly. The Crawfish dash renders both meters in the status bar with predicted-exhaustion-time projection.
- **`/usage`-equivalent in dash** showing per-session token breakdown by tool, by cache state (cache_read / cache_write / input / output), by model.
- **`/cost`-equivalent with dollar overlay** (off by default per anti-goal; on when the user explicitly opts in).
- **Local JSONL as source of truth** — Crawfish already reads `~/.claude/projects/*.jsonl`. We add the same parsing for `~/.claude/teams/{team-name}/` (the new agent-teams location, see §3.10) so multi-agent sessions count in the same meter.
- **Lessons from community tools** (`ccusage`, `claude-usage`, `cc-statistics`): expose a "thinking time vs. waiting-for-human time" ratio — `cc-statistics` proved this is the metric a founder actually wants.

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

**Inspiration:** Pilot Protocol ([pilotprotocol.network](https://pilotprotocol.network/)). Today browser optimizers like `crawfish-opt` shave token cost on existing sites; Pilot's argument is that agents should not be visiting human-shaped sites at all — there should be an *agent-native* protocol layer. Pilot Protocol is the canonical reference architecture for that layer today, and the IETF draft (`draft-teodor-pilot-protocol-01`) gives it a real spec we can interoperate with.

**Specifically borrowed from Pilot Protocol:**
- **48-bit virtual agent addressing** (e.g., `0:A91F.0000.7C2E`) — Crawfish's `AgentId` extends to be a valid Pilot address so any Crawfish agent is reachable from the public Pilot backbone (190k+ agents, 19.7B+ requests routed as of May 2026).
- **Encrypted-by-default transport** — X25519 key exchange + AES-256-GCM matches the Pilot spec; we adopt it for inter-org agent comms instead of inventing our own.
- **NAT traversal** — STUN + UDP hole-punching + relay fallback. Crawfish federation (Stage 2 §4.4) inherits this so two engineers' agents can talk peer-to-peer without VPN gymnastics.
- **Bilateral trust + reputation** — Pilot's mutual-trust model maps to Crawfish's per-agent capability ACLs. Reputation scores from the Pilot network become a signal in Crawfish's marketplace.
- **Built-in services** Pilot ships (real-time messaging, file transfer, task distribution with load balancing/priority queues/retries) — we don't reimplement these; we proxy through Pilot when both ends are Pilot-aware.

Crawfish's pragmatic position is **dual-track**:

- **Track A — use today's web well.** The `crawfish-opt` browser optimizer (already shipped at v0.2) wraps Playwright + a Haiku semantic summarizer + a zone-based DOM index. This is the floor. Stage 1 adds (a) site-specific *recipes* for the highest-traffic agent destinations (Stripe, AWS, Linear, Notion, GitHub UI, Google Workspace admin), each cutting tokens 5–10× vs. blind DOM read; (b) a session-replay cache so the same `browser_navigate` to the same URL within a window hits a local store.
- **Track B — provide an agent-native edge.** A Crawfish-hosted (or self-hostable) **agent-web proxy** that re-exposes common consumer/SaaS endpoints in a token-thin, JSON-shaped, capability-scoped form. Each backend has an adapter; each adapter is benchmarked against the naive-Playwright baseline. Over time the proxy becomes the preferred path and the human-DOM optimizer is the fallback. When the destination *itself* publishes an agent-native protocol (PiP, Pilot Protocol, or similar), Crawfish adopts it natively and the proxy becomes a passthrough.

This is the only way to honestly resolve "use the web, replace the web" — give the user both, measure both, and let the proxy beat the optimizer over time.

**Personas:** Solo founder (T1), Engineer IC (T1), Support lead (T3).

**Sequencing:** P4 ships site-recipes + replay cache. P5 ships the proxy MVP with two backends. P6 onward grows the proxy.

### 3.8 Agent Codespaces — local + Claude Managed Agents

**Inspiration:** **GitHub Codespaces** ([github.com/features/codespaces](https://github.com/features/codespaces)) — the canonical cloud-dev-environment model: devcontainer-as-code config, 2–32 core VMs, port forwarding under policy, "your space, your way" via dotfiles, browser or IDE access, isolated environments with access + cost controls — *plus* Anthropic's **Claude Managed Agents (CMA)** shipped April 2026 ([platform.claude.com/docs/en/managed-agents/overview](https://platform.claude.com/docs/en/managed-agents/overview)), which runs an Agent (model + system prompt + tools + MCP + skills) inside a cloud Environment (container template) as a long-running Session with SSE events. CMA commoditizes the harness layer, which means Crawfish should **not** build a competing sandbox; it should ride on top of CMA and offer a local-equivalent for users who can't or won't use the cloud.

**Specifically borrowed from GitHub Codespaces:**
- **Devcontainer config as the unit of reproducibility** — every Crawfish space is described by a JSON config (forwarded ports, install commands, VS Code extensions, shell). Same JSON shape Codespaces uses; lifts straight off the ecosystem.
- **Three security pillars** Codespaces leads with: *Isolated Environments, Access Control, Cost Control.* Crawfish adopts the same three as its space security model.
- **Port forwarding under policy** — agents can forward ports; the policy decides whether they're public, org-only, or per-watcher.
- **Onboard at the speed of thought.** Codespaces' tagline becomes our onboarding test: a new engineer joins, runs `crawfish join`, and an agent space is provisioned before they've finished `git clone`.
- **Pay-as-you-go with a free tier.** Codespaces' 60-core-hours-per-month free tier is the price ceiling for Crawfish's hosted spaces in Stage 2.

**Specific feature set:**

- **`runtime: "claude-managed-agents"`.** A new `RuntimeProvider` in `crawfish-lens/src/runtimes/cma.ts`. Cron daemon dispatches sessions through CMA's API; lens consumes the SSE event stream as if it were a Claude Code transcript. The org's MCP tools (`board_*`, `org_fs_*`, `knowledge_*`) attach to the CMA Agent definition; the org's policy bundle becomes a CMA Permission Policy.
- **`crawfish space create <agent-id> --runtime cma`.** Creates a CMA Agent + Environment for that org member, persists the IDs in `org.json`. From the user's perspective there is one "space" per agent; the implementation can be CMA-hosted or local-Docker.
- **`crawfish space create <agent-id> --runtime local`.** The fallback for offline / non-Claude / cost-sensitive users: a Devcontainer-shaped Docker sandbox with the agent's worktree, `org-fs/`, policy bundle, and MCP tools mounted. Resource ceilings via cgroups (Linux) / launchd profile (macOS).
- **WASM sandbox** for narrowly-scoped agents that don't need a full container — same shape that Ruflo's `rvagent` uses. Faster start, smaller blast radius.
- **`crawfish space attach <agent-id>`.** Drops into a shell as that agent. For CMA, attach is a TTY proxy over the session's bash tool; for local, it's `docker exec`.
- **Snapshot + branch.** A space is a Git branch; freezing captures the working tree, env, and a hash of the policy bundle. "Re-run the same task under the same conditions next week."
- **One UI, two backends.** The Spaces tab in dash shows local and CMA spaces in one list with a backend chip; switching backends is a member-edit, not a fork.

**Why not just compete with CMA:** Anthropic's branding rules explicitly leave room above the harness ("Claude Agent" and "Powered by Claude" are allowed for partners; "Claude Code Agent" is forbidden). The harness is theirs; the org layer is ours. We win by being the org layer that *works with* CMA, plus the local fallback for users who don't want the dependency.

**Personas:** Solo founder (T1), Engineer IC (T1), Platform engineer (T2).

**Sequencing:** P5 ships the CMA adapter + local Docker. P6 ships WASM sandbox + snapshot/branch.

### 3.9 Agent CI/CD — the test-and-visual-audit pair

**Inspiration:** the current CI gate culture. Stage 1 introduces two specialist agents that earn their keep by closing the test feedback loop without a human.

- **Test-generating agent.** Triggered on every PR that lacks coverage delta. Reads the diff, the linked CrawfishTask's acceptance criteria, the repo's existing test conventions, and produces a coherent test file. Tests run in the agent's Codespace; failures land as comments on the PR with a proposed fix.
- **Visual-auditor agent.** Playwright-driven. Per PR, runs the app, takes screenshots of every route (baseline from `main`, candidate from the PR branch), diffs them, and posts a visual changelog. Catches the "I changed one CSS variable and the whole sidebar moved" class of bug. Wraps the existing `crawfish-opt` browser primitives.

These are both shipped as preinstalled agents inside the `dev-shop` template and as standalone marketplace containers any org can install. Both follow the optimizer contract (`tokens_used` on every response).

**Personas:** Engineer IC (T1), Platform engineer (T2), Manager (T2).

**Sequencing:** P5 ships test-generation. P6 ships visual audit.

### 3.10 Developer-task crons + Claude Code Agent Teams integration

**Inspiration:** the existing `crons.json`/`node-cron` daemon, *plus* the **Claude Code Agent Teams** primitive at [code.claude.com/docs/en/agent-teams](https://code.claude.com/docs/en/agent-teams) — `team_name`, `SendMessage` (DM + broadcast), `TaskCreate`/`TaskUpdate` for shared task lists, team config in `~/.claude/teams/{team-name}/`. Subagents can only report back to a parent; **agent teams remove that limitation** and unlock peer-to-peer communication.

**Specifically borrowed from Claude Code Agent Teams:**
- **`team_name` as a first-class membership.** Crawfish's `AgentContainer` already has `id` and `role`; Stage 1 adds a `team_name` that maps 1:1 to a Claude Code team. A Crawfish org spawns teams by declaring them in `org.json.teams[]`; lens reads `~/.claude/teams/{team-name}/` and binds team activity to the org.
- **`SendMessage`-shaped inter-agent comms.** Crawfish's communication graph (§3.12) ingests SendMessage events directly. The graph's lateral edges (sibling-to-sibling, not parent-child) come from this signal.
- **TaskCreate / TaskUpdate** — Crawfish's CrawfishTask schema is the superset; ingestion translates Claude Code task entries into CrawfishTask events without loss.
- **Team-lead pattern.** Claude Code's "one session = team lead, coordinates work" maps to Crawfish's `architecture: "hierarchical"` template. We ship a `claude-team-lead` agent container that follows this pattern out of the box.

Stage 1 ships the *cron recipes* a founder actually wants to run on a schedule:

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

Inspired by **Perplexity** ([perplexity.ai](https://www.perplexity.ai/)) and its Pro Search / Reasoning Search router. Perplexity's Pro Search exposes a manual model selector (Sonar, GPT-5, Claude 4.0 Sonnet, Gemini 2.5 Pro); Reasoning Search adds o3, Claude 4.0 Sonnet Thinking, Grok 4. The "Auto" default routes invisibly per query complexity but exposes the actual model in the API response.

Stage 1 ships Crawfish's equivalent: a **per-task model picker** that decides at cron-fire time based on the task's `label`, its acceptance criteria, and historical success rates per model. The agent's `runtime` field becomes a *default*; the router can downgrade to Haiku/GPT-4.1-mini for routine work and upgrade to Sonnet/Opus only when the task warrants it.

**Specifically borrowed from Perplexity's router:**
- **Auto mode with API transparency** — Perplexity hides the model in the consumer UI but exposes it in the API. Crawfish does the inverse: defaults to a manual override in dash, but the cron-time router auto-selects unless overridden, and the chosen model is always recorded on the task's communication log for auditability.
- **Task-class-aware routing** — Perplexity routes reasoning queries differently from retrieval queries. Crawfish routes `task.label` types (`bug` → cheaper model, `architecture` → reasoning model, `customer-message` → fastest model with citation support).
- **Reasoning-content visibility.** Sonar Reasoning Pro surfaces chain-of-thought through the API. Crawfish requires that any reasoning-class run emit its reasoning into the journey log for the diagnoses engine to inspect.
- **Surfaced as a "model strategy" column** in the Crons UI per task type — same shape as Perplexity's per-mode picker.

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

**Inspiration:** **LangSmith** ([smith.langchain.com](https://smith.langchain.com/)) for the dev side, **Pendo** ([pendo.io](https://www.pendo.io/)) for the product side. Crawfish already has the dual-analytics toggle in dash; Stage 1 makes both sides actually deep.

**Specifically borrowed from LangSmith (dev side):**
- **Full execution-tree traces.** LangSmith renders every LLM call, tool invocation, retrieval step, and reasoning turn as a connected tree with the exact parameters passed at each node. Crawfish's session-detail view ships the same shape with the journey timeline (BRAINSTORM §3) as the entry surface.
- **Framework-agnostic ingestion.** LangSmith's win is that it works with LangChain, LangGraph, or raw SDK calls. Crawfish does the same across runtimes (Claude Code, CMA, OpenClaw, Codex, OpenAI, Cursor, Aider).
- **Online + offline evaluation.** LangSmith runs evaluators on production traces (safety, format, quality, LLM-as-judge) and on labeled datasets. Crawfish's diagnoses engine is the online half; Stage 1 adds an **offline eval harness** in `crawfish-lens/src/evals/` that runs the same rules against fixture datasets and reports regressions per rule.
- **Prompt management as a first-class asset.** LangSmith's Prompt Playground + prompt versioning treat prompts like code. Crawfish's `AgentContainer.system_prompt` becomes versioned; every change is a commit; diff + rollback are one click.
- **Code-based evaluators alongside LLM judges.** Crawfish's diagnoses engine is code-based by design; we add LLM-as-judge as a complement for the quality dimension nothing programmatic captures.

**Specifically borrowed from Pendo (product side):**
- **Product Engagement Score (PES)** = Adoption + Stickiness + Growth. Crawfish ships an analogous **Agent Engagement Score** per agent: tasks completed × distinct task-types handled × week-over-week growth. The CEO's headline number.
- **Funnels + Paths.** Pendo shows how users move through an app step-by-step with drop-off attribution. Crawfish's product-side view shows the same for *agent-driven user flows*: customer ticket → triage agent → specialist agent → resolution or escalation. Surface drop-off and time-per-stage.
- **NPS as in-app guide.** Pendo embeds NPS surveys triggered by behavior/time/segment. Crawfish embeds the same shape in customer-facing agents: at conversation close, the agent emits a one-question survey; the score flows to the analytics surface.
- **No-tag, retroactive event capture.** Pendo's standout feature is that it captures history from day one without manual instrumentation. Crawfish has the same advantage from JSONL — every historic session is replayable into the analytics surface; the user never tags an event.
- **Connect NPS to feature usage.** Pendo correlates promoter/detractor scores to specific features. Crawfish correlates customer satisfaction to specific agent decisions (which prompt, which tool, which retrieval).
- **In-app guides + tooltips.** Pendo lets product teams ship walkthroughs without engineering. Crawfish ships an **agent-guide builder** so a CEO can write "when a user asks about pricing, the support agent should first do X, then mention Y" — saved as a Pendo-style guide, executed at runtime by the support agent.

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

**Inspiration:** the **HyperAgent** name disambiguates to several projects — the FSoft-AI4Code generalist SE multi-agent framework with `Planner / Navigator / Code Editor / Executor` roles, Hyperbrowser's Playwright-+-AI runtime, and the Hyperlight-dev sandboxed JS execution agent. All three share one model worth borrowing: **hosted multi-agent runtimes with role-specific containers**. With CMA now in market, the Stage 2 hosted layer specializes around **what Anthropic won't host**: the non-Claude runtimes, the org filesystem, and the team-mode dashboard.

**Specifically borrowed from the FSoft-AI4Code HyperAgent design:**
- **Role-specific container roster** per hosted org: a Planner runtime tuned for decomposition, a Navigator runtime tuned for codebase traversal, an Executor runtime tuned for bash + test execution. Each is a separately-billed Crawfish hosted runtime; the org composes them.
- **Whole-lifecycle coverage** (initial planning → final verification) — Crawfish's hosted offering claims the same vertical: from triage to acceptance-criteria verification, no gaps.
- **Multi-language support** (HyperAgent ships Python + Java first) — Crawfish hosted runtimes ship language-pinned variants (`crawfish-runtime-rust`, `crawfish-runtime-python`, etc.) so the indexing cache is hot per language.

- **Hosted non-Claude orchestrators.** Anthropic hosts the Claude harness (CMA). Crawfish hosts the rest: a managed OpenClaw daemon, managed Codex CLI workers, managed Cursor batch jobs, managed OpenAI agent loops. The `crawfish-orchestrator` (planned C2.P3) bundles each runtime + a config + a lens hook into a local daemon; Stage 2 promotes those to a managed fleet with SSO and per-org policy. Connects back to local dash over a signed event stream (no plaintext transcripts leave the tenant).
- **Hosted agent filesystem.** The org-fs becomes a multi-tenant S3-backed store with per-file ACL, server-side encryption, and a hosted LightRAG index. Per the local-first contract, hosting is opt-in; the local copy remains canonical. **This is the headline product of Stage 2.** See §6 below for why.
- **Hosted Codespaces.** §3.8's local Docker spaces graduate to a hosted variant for users who don't want CMA. CMA-backed spaces ride on Anthropic's infra; local spaces ride on ours. Crawfish owns the unified surface.
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

## 6 · Competitor landscape

A clear-eyed read of who else is in this market and where Crawfish wins or loses against each. Nine categories, sorted by how acute the threat is to the plan: **harness vendors**, **desktop agent products** (the existential question), **memory & knowledge-layer competitors** (the tightest direct fight), **OSS orchestration**, **autonomous-engineering platforms**, **vertical agent orgs**, **no-code SMB agent platforms**, **observability**, **adjacent infrastructure & standards**. Then a positioning matrix and the strategic posture.

### 6.1 Harness vendors (Anthropic, OpenAI, Google) — *do not compete*

**Claude Managed Agents (Anthropic, beta, April 2026).** A managed harness: Agent (model + system prompt + tools + MCP + skills), Environment (cloud container template), Session (running instance with SSE event stream). Built-in prompt caching, compaction, multi-agent (research preview), Outcomes (research preview). Claude-only. Hosted-only. Branding rules explicitly leave room for partner orchestration ("Claude Agent" is allowed; "Claude Code Agent" is forbidden).

What it kills in our plan: the build-your-own-sandbox version of §3.8 (Local Codespaces), and the "hosted Claude orchestrator" framing in Stage 2.

What it does *not* touch: the org layer (board, plan, comms graph, dual analytics, policy, diagnoses, manager crons, marketplace), the multi-runtime story, the local-first posture, and — most importantly — **the agent filesystem + librarian**. CMA gives you one agent with a per-session container; it does not give your company a long-lived institutional-memory substrate that ingests email, code, Slack, and runbooks and serves them back to every agent with a learned source-mix policy.

How we respond: §3.8 ships a CMA adapter as the *preferred* hosted backend for Claude-native users; local Docker / WASM is the fallback. Stage 2 hosting specializes in non-Claude runtimes. Anthropic gets the harness; we get the org layer above it.

**OpenAI AgentKit / Google Vertex Agent Builder.** Same shape, different vendor. They will commoditize the harness for their own models. Same response: we are the cross-vendor org layer + the knowledge substrate.

**Verdict:** Not killers. Tailwinds for the org-and-filesystem thesis; death blow only to the harness-rebuilding thesis we weren't pursuing.

### 6.2 Desktop agent products — *the existential question*

**Claude Cowork (Anthropic, GA April 2026).** This is the competitor that has to be addressed honestly because Crawfish currently runs *inside* Cowork mode. Cowork brings Claude Code's agentic capabilities to the desktop app for non-technical work — it reads, edits, creates, renames, moves, deletes, deduplicates, and converts files across formats; produces real .docx, .pptx, .xlsx, and PDF; runs Computer Use for desktop control; ships a Projects feature for workspace context; a Dispatch feature for continuous conversation from phone or desktop; and a Plugins system that bundles **skills + connectors + slash commands + sub-agents** for specific job functions, with **11 open-source starter plugins** Anthropic published covering sales, finance, legal, marketing, HR, and more.

**Why this is the existential question.** Every Stage 1 workstream that targets the non-engineer founder is a workstream Anthropic is one Plugins-extension away from shipping. The 11 starter plugins map directly onto the Crawfish startup template (sales, support, finance, ops, marketing). The Plugins primitive — skills + connectors + sub-agents bundled — is structurally the same as a Crawfish AgentContainer with `tools` + `system_prompt` + `runtime`. Microsoft Copilot Cowork (March 2026, powered by Claude) extended this stack into M365 distribution.

**What Cowork does *not* have, and structurally won't:**

- **A multi-agent organization.** Cowork is one agent per conversation, with sub-agents inside Plugins. There is no org-fs, no shared board, no peer-to-peer agent comms, no manager-cron pattern. Multiple agents in Cowork are scoped to the user's lifetime, not the company's.
- **Cross-runtime.** Cowork is Claude-only. Crawfish reads Claude Code + CMA + OpenClaw + Codex + OpenAI + Cursor + Aider + Cline + Goose. Every quarter this gap widens.
- **The learning librarian.** Projects is folder-and-context; it is not a contextual-bandit policy that learns per-org which sources to consult for which question type. Plugins are static bundles; the librarian is dynamic state.
- **Tokens-as-unit-of-account governance.** Cowork doesn't surface compounding factor, doesn't run a diagnoses engine that recommends optimizers, doesn't enforce token budgets per task. It's a great agent; it's not a governance layer.
- **Local-first non-negotiable.** Cowork requires a Claude account and runs through Anthropic infrastructure.

**How we respond:** lean into the layer above Cowork, not the layer beside it. Ship a `runtime: "claude-cowork"` adapter so a Crawfish org member can *be* a Cowork agent. The org layer governs; Cowork executes. Position Crawfish to Cowork users as "Cowork is your desktop agent; Crawfish is your agent company." If Anthropic eventually ships multi-agent org features inside Cowork, Crawfish's multi-runtime + multi-vendor positioning is the only durable response — bet against Cowork becoming the cross-vendor org layer, because the brand and the billing relationship structurally prevent it.

**Verdict:** Threat-level *yellow*. Not killing us today; will keep encroaching. The librarian and multi-runtime are the defense.

### 6.3 Memory & knowledge-layer competitors — *the tightest direct fight*

This is the category that's grown most in the last twelve months and is now the densest direct competition to §3.3 + §3.3.1.

**Mem0 ([mem0.ai](https://mem0.ai/)).** 48k GitHub stars, $24M raised, Apache 2.0, SOC 2. Vector + graph + key-value memory layer with a four-scope model (`user_id` / `agent_id` / `run_id` / `app_id` / `org_id`). Hybrid storage — Postgres for long-term facts, episodic summaries, temporal-recency-weighted retrieval, parallel scoring across semantic + keyword + entity signals fused via rank-scoring. **OpenMemory** is their local-first MCP-compatible memory server, working with Claude Desktop, Cursor, Windsurf, VS Code, and any MCP client. LOCOMO benchmark: 66.9% accuracy at 0.71s median latency / ~1,800 tokens per conversation.

**Where Crawfish wins vs. Mem0:** Mem0 is per-agent memory; Crawfish is per-org memory with peer-to-peer access. Mem0 has no learning policy on top of retrieval (their hybrid signal fusion is static); Crawfish's librarian (§3.3.1) is online-learned per-cluster. Mem0 has no org-level concept of source class (code vs. email vs. Slack are just metadata fields); Crawfish ships per-source-class embedding spaces and a meta-router that learns the right mix per query class. Mem0 has no LLM Wiki; Crawfish surfaces the knowledge graph as a navigable user-facing artifact.

**Where Mem0 is ahead:** distribution (48k stars vs. nothing), MCP compatibility shipped today, four-scope memory model is more granular than Crawfish's current org-scoped design — we should adopt their scope structure. Their architectural insight — "do the work at storage time, not retrieval time" — is correct and matches our librarian design.

**Threat-level *orange*** (was *yellow* — bumped because OpenMemory is local-first MCP-compatible, exactly Crawfish's posture).

**Letta (formerly MemGPT, [letta.com](https://www.letta.com/)).** UC Berkeley spinout. **The closest competitor on the "agent filesystem as platform" thesis.** Letta ships **Letta Code** as a runtime with git-backed memory, skills, subagents, and cross-provider deployment, plus **Context Repositories** — programmatic context management with git-based versioning. Their pitch is verbatim ours: "LLM-as-OS, stateful agents that learn during deployment not just training, memory in databases not Python variables, agents that self-edit their memory using tools." Production-ready REST APIs + Python/JavaScript/Rust SDKs. Local or cloud deployment.

**Where Crawfish wins vs. Letta:** Letta is *agent-centric* — every agent has its own state; the platform is the runtime for that agent. Crawfish is *org-centric* — the org has the state, agents are workers on top of it. Letta has no native task board, no humans-as-peers, no comms graph, no dual analytics, no marketplace. Letta is what an engineer uses to build a stateful agent; Crawfish is what a company runs.

**Where Letta is ahead:** their core technical thesis is more developed than ours on agent state, memory hierarchy (core/archival/recall as RAM/disk), and self-editing memory. We should explicitly adopt Letta's three-tier memory model (in-context core + external archival + recall index) in §3.3 — it's a better mental model than the three-zones we have.

**Threat-level *orange*.** They could realistically pivot to the org layer; their git-backed memory model is one architectural decision away from supporting per-org state.

**Cognee ([cognee.ai](https://www.cognee.ai/)).** $7.5M seed, GraphRAG with the **ECL pipeline** (Extract, Cognify, Load). 38+ source types, 30+ connectors (PDFs, Slack, Notion, Drive, images, audio, databases). Three storage layers unified — relational + vector + graph. Plugs into Claude Agent SDK, OpenAI Agents SDK, LangGraph. Feedback-loop refinement of the graph.

**Where Crawfish wins vs. Cognee:** Cognee is a memory control plane for AI agents — a backend developers wire into their own apps. Crawfish ships the user-facing surfaces (LLM Wiki, board, dash, analytics) over the same kind of substrate. Cognee doesn't ship the org framing.

**Where Cognee is ahead:** 38 source types and 30 pre-built connectors is a real distribution lead. Their ECL pipeline is the operational shape Crawfish §3.3's "heterogeneous-context ingestion" needs to match. **We should consider building on Cognee as an internal library rather than reimplementing.**

**Threat-level *yellow*.** Not the org layer; a substrate-layer competitor we could plausibly absorb.

**Zep ([getzep.com](https://www.getzep.com/)).** Temporal Knowledge Graph with timestamped facts and a relationship map that tracks state changes. Async background processing — Zep summarizes old chat history to keep prompts under the token limit without dropping content. High-scale production-shaped.

**Where Crawfish wins vs. Zep:** Zep is chat-history-centric (their primitive is a conversation); Crawfish is multi-source. Zep has no librarian-equivalent routing policy; no org-level UI surface.

**Where Zep is ahead:** the temporal dimension is real and §3.3 currently underweights it. We should explicitly add **timestamped facts + temporal queries** to the librarian's signal set ("what was true *as of* the date this question was asked?").

**Threat-level *yellow*.**

**Glean ([glean.com](https://www.glean.com/)).** $200M ARR (doubled in 2026). The enterprise version of what §3.3 wants to be. **Enterprise Graph** + per-employee personal graph; third-generation Assistant with agentic planning and multi-step execution; 100+ actions across Salesforce, Calendar, Asana, Canva, Jira, Confluence, GitHub. 15+ LLMs across Bedrock, Azure, Vertex plus direct vendor relationships. Canvas for content creation.

**Where Crawfish wins vs. Glean:** Glean is enterprise-only and hosted-only ($200M ARR comes from selling to BigCos). Crawfish is local-first and lands with founders and small teams. By the time a Glean-shape buyer is in play, Crawfish has six months of an org's librarian state — a moat Glean can't replicate per-customer.

**Where Glean is ahead:** *everything Stage 2 promises, they've shipped at scale.* Enterprise Graph is the strongest direct evidence that the "knowledge layer beneath the interface" thesis is correct. Their personal-graph-per-employee model is something we should adopt.

**Threat-level *red* in the enterprise lane** — at the bottoms-up level they're not competing for the same buyer, but for any Stage 3 enterprise sale, Glean is the incumbent we displace or partner with.

### 6.4 OSS orchestration — *direct overlap*

**Ruflo (ruvnet, formerly Claude Flow, [github.com/ruvnet/ruflo](https://github.com/ruvnet/ruflo)).** Still the closest direct competitor on the orchestration framing. MIT, OSS, momentum (Budapest summit, claude-flow → Ruflo rebrand, beta UI at flo.ruv.io). "Multi-agent AI orchestration for Claude Code" with 100+ specialized agents, swarms, self-learning memory, federation across machines, Cognitum.One Rust engine. 32 plugins as of May 2026 covering core orchestration, memory/knowledge (agentdb, rag-memory, rvf, ruvector, knowledge-graph), intelligence (intelligence, daa, ruvllm, goals), code (testgen, browser, jujutsu, docs), security (security-audit, aidefence), methodology (adr, ddd, sparc), DevOps (migrations, observability, cost-tracker), runtime (ruflo-agent with WASM + CMA), plus plugin-creator and domain packs.

**Where Crawfish wins vs. Ruflo:** framing (org vs. orchestrator), buyer (founder/CEO/manager vs. developer), humans-as-first-class-peers, native task board with structured acceptance criteria, dual analytics (Pendo-side is absent in Ruflo), multi-runtime breadth, the communication graph as a flagship visual, the diagnoses engine with click-to-fix, the librarian as a learned routing policy (Ruflo has separate plugins; we ship integration), design + UX discipline, local-first as a principle.

**Where Ruflo is ahead:** plugin granularity (32 plugins each doing one thing well), WASM sandbox (already adopted in §3.8), AI-Defence layer (prompt injection + PII — add to §3.11), methodology packs (SPARC/DDD/ADR — ship as Crawfish org-templates or skill packs).

**Threat-level *orange*.** If Ruflo ships an Obsidian-shaped knowledge layer with a learned source-separation router before we do, the fight gets meaningfully harder.

**Block Goose ([github.com/block/goose](https://github.com/block/goose)).** 29k GitHub stars. Apache 2.0. Native desktop apps macOS/Linux/Windows + full CLI. 30+ LLM providers (OpenAI, Anthropic, Ollama, local inference). MCP-native. Custom MCP servers and tools. **Joined the Linux Foundation's Agentic AI Foundation (AAIF) as an inaugural project in December 2025.**

**Where Crawfish wins vs. Goose:** Goose is a single-agent desktop coding agent; it has no org, no board, no humans-as-peers, no learning librarian, no marketplace, no analytics. Crawfish is the org layer above where Goose lives.

**Where Goose is ahead:** Linux Foundation backing changes the OSS legitimacy game. Block (Square/Cash App parent) distribution. 29k stars is real mindshare. **Recommendation: Crawfish should evaluate joining the AAIF as a credibility/distribution move** (see §6.10 below).

**Threat-level *yellow*.** Not the org layer; a runtime we can adapt and ingest from.

**LangChain / LangGraph + LangSmith.** Big incumbent. LangGraph for orchestration, LangSmith for observability. Strengths: enterprise mindshare, every framework integration, language-agnostic, framework-agnostic LangSmith tracing. Weaknesses: graph-of-functions framing (not org framing), Python-first, very developer-pitched, no knowledge layer, no shared FS, no native task surface.

**Threat-level *yellow*.** Crawfish wins on bottoms-up + filesystem moat + org framing.

**CrewAI ([crewai.com](https://crewai.com/)).** Role-and-task framing — closest to Crawfish's org framing in spirit. Free tier (50 executions/month); Professional $25/mo (100 executions); Enterprise estimated $60k–$120k/year with SOC2, SSO, HIPAA, on-prem/private-cloud deployment, RBAC, audit logs.

**Where Crawfish wins vs. CrewAI:** CrewAI is a Python multi-agent library; Crawfish is a product. CrewAI has no native task board, no shared FS, no librarian, no humans-as-peers. CrewAI's pricing model (per execution) is hostile to bottoms-up; Crawfish stays free for solo founders.

**Threat-level *yellow*.**

**Microsoft Agent Framework (MAF).** **AutoGen is now in maintenance mode** — MAF is the production successor. Magentic-One orchestration pattern (Orchestrator + FileSurfer + WebSurfer + Coder + Computer Terminal) plus sequential/concurrent/handoff/group-chat patterns. All patterns support streaming, checkpointing, human-in-the-loop approvals, pause/resume. Azure distribution baked in.

**Where Crawfish wins vs. MAF:** MAF is the orchestration *framework*; not the platform. No board, no FS, no librarian, no marketplace. Azure-tied where Crawfish is local-first.

**Where MAF is ahead:** Microsoft enterprise distribution. Magentic-One's specialist-roles roster (FileSurfer/WebSurfer/Coder/Terminal) is well-thought-through; we should adopt that shape for our default `dev-shop` template.

**Threat-level *yellow* for Stage 1, *orange* for Stage 3 enterprise sales** where Azure is mandated.

**OpenHands, Mastra.** OpenHands is the autonomous coding agent (open-source descendant of OpenDevin); Mastra is the TypeScript-friendly SDK. Both are runtimes Crawfish adapts via `crawfish-lens/src/adapters/`, not products that compete.

### 6.5 Autonomous-engineering platforms — *don't compete, ingest from*

**Cognition (Devin v3).** $25B valuation talks (April 2026). Devin v3 added dynamic re-planning, self-healing code, multi-agent parallelism, 20+ tool integrations (GitHub, Slack, Jira, Linear, major cloud providers). Cognition Core dropped from $500/mo (Devin 1) to $20/mo (Devin 2). 83% more junior-level tasks per Agent Compute Unit.

**Factory AI ([factory.ai](https://factory.ai/)).** $150M Series C at $1.5B valuation. "Agent-Native Software Development" with **Droids** as the unit — Coordinator decomposes work and dispatches to specialized Droids (code, review, docs, test, knowledge) with explicit role boundaries. **Linear and Jira integrations turn tickets into the native unit of work** — exactly the framing Crawfish is targeting on the dev-shop template, with more capital and a head start. Multi-model routing (Claude 4.5 for planning, DeepSeek for code generation, smaller open-source for test authoring).

**Cursor 3 + Background Agents.** Cloud Agents with Computer Use (Feb 2026). **`/multitask`** for async subagents spawning their own subagents (April 2026). Trees of coordinated work. Agent-first interface beyond the IDE model. Each agent gets a full desktop environment.

**Replit Agent v3.** Autonomous full-stack scaffolding from a prompt. Self-healing code. Cloud sandbox. Effort-based pricing. Core $25/mo, Teams $40/user/mo, Pro $100/mo (15 builders).

**Where Crawfish wins vs. all four:** none of them ship the *org layer*. They are agent execution surfaces; Crawfish is the company they execute inside. The honest play is to **adapt them as runtimes**, not compete with them. A Crawfish dev-shop template could be `Cognition Devin as the senior engineer agent + Factory Droids as the specialized worker agents + a Crawfish manager-cron coordinating them through CrawfishTasks`.

**Threat-level *yellow* (don't compete here, ingest from)** — but with one caveat: Factory's "Linear tickets as native unit of work + droid swarm picks them up with acceptance criteria attached" is *exactly* the §3.2 framing. If Factory adds humans-as-peers and a non-developer buyer pitch, that gets uncomfortable.

### 6.6 Vertical agent orgs — *don't compete, ingest from*

**Sierra ([sierra.ai](https://sierra.ai/)).** $15.8B valuation (May 2026 — $950M raised at that round, $1.4B total since 2023). Bret Taylor + Clay Bavor. Customer-service-vertical agent platform. **~40% of the Fortune 50 as customers** (WeightWatchers, SiriusXM, Sonos, ADT, Chime, Cigna, Nordstrom, Nubank, Ramp, Rivian, Rocket Mortgage, Singtel, Sutter Health, Wayfair). Outcome-based pricing (pay per successful resolution). **Agent OS** (omnichannel deployment), **Agent Data Platform** (cross-session memory — Sierra's version of the agent filesystem), **Agent Studio** (no-code builder), **Agent SDK** (developer layer), **Ghostwriter** (March 2026 conversational agent builder that creates agents from SOPs, call transcripts, even photos of whiteboard sketches). Constellation-of-15+-models approach. PCI-compliant payment handling as of April 2026.

**Decagon, 11x, similar verticals.** Decagon: AI customer support. 11x: AI SDR / sales reps.

**Where Crawfish loses vs. these:** they own their vertical. Don't compete.

**Where Crawfish wins:** Crawfish is horizontal. A Sierra customer who *also* needs sales agents, finance agents, ops agents, and engineering agents — the entire rest of the company — needs Crawfish. The play is to **be the org layer that orchestrates the vertical specialists.** A Crawfish org template includes a `vertical-specialist` member type whose runtime points at Sierra (for support), Cognition (for engineering), or 11x (for sales). Crawfish manages the task hand-off; the vertical does the actual work.

**Threat-level *green* on Crawfish's actual product surface.** They're not building what we're building.

### 6.7 No-code SMB agent platforms — *the closest bottoms-up competition*

**Lindy ([lindy.ai](https://www.lindy.ai/)).** **The closest direct competitor to Crawfish's bottoms-up wedge.** 50+ to 1,000+ pre-built templates covering meeting scheduling, CRM updates, onboarding, support triage. 5,000+ app integrations. **Computer Use** for sites without APIs. Conversational builder (customize templates through chat, not configuration UI). $19.99/mo Starter / 2,000 credits.

**Where Crawfish wins vs. Lindy:** Lindy is a no-code workflow platform; agents are workflow nodes. There is no org, no humans-as-peers, no shared FS, no librarian, no cross-runtime story, no developer credibility. A founder using Lindy hits a ceiling when their org starts coordinating multiple agents across functions — Crawfish is what they graduate into.

**Where Lindy is ahead:** **template count** (1,000+ vs. our 6) and integration count (5,000+ vs. our P4 target of 30+) are real distribution leads. The conversational template-customization gesture is the right pattern; we should adopt it.

**Threat-level *orange*.** Same buyer (small business / founder), same wedge (templates), more mature execution. We win on framing and on the runtime/governance layer they don't have — but only if we ship visibly fast.

**Relevance AI ([relevanceai.com](https://relevanceai.com/)).** Visual workforce canvas. Pre-built sales/content/support/data templates. 9,000+ integrations. Multi-agent "workforce" framing — directly competitive with our §3.1.

**Threat-level *yellow*.** Crawfish wins on local-first + multi-runtime + librarian; loses on integration count and visual builder maturity.

**Gumloop ([gumloop.com](https://www.gumloop.com/)).** 170+ community templates organized by Marketing/Sales/Operations/Engineering/Support. 130+ integrations, 115+ blocks. Gummie AI assistant. $37 Solo / $97 Pro. Visual node graph.

**Threat-level *yellow*.** Gumloop is a workflow tool with AI nodes; Crawfish is an agent org. Different shape, partial buyer overlap.

**Dust ([dust.tt](https://dust.tt/)).** Enterprise-credible. SOC 2 Type II + GDPR + data residency. 45+ tools, multi-model (GPT-5/Claude/Gemini/Mistral). **Spaces** for permission boundaries. Department-scoped agents.

**Threat-level *yellow* at SMB, *orange* at enterprise.** Dust has shipped the Stage 3 compliance posture Crawfish has only sketched. For any company that requires SOC 2 today, Dust is the incumbent we displace or partner with.

### 6.8 LLM/agent observability stack — *fully owned category; we only win as integrated*

**LangFuse (MIT, OSS, self-host).** Prompt versioning + structured logging.
**LangSmith (LangChain incumbent).** Full execution-tree traces, online/offline evals, framework-agnostic.
**Helicone (Apache 2.0, one-line proxy).** Cheapest request/response logging.
**Braintrust (closed-source, eval-first).** CI/CD blocking on regression, statistical-significance gates.
**Arize Phoenix.** OpenInference / OpenTelemetry-based, OSS, RAG-strong.
**Weights & Biases Weave.** ML-platform extension; MCP auto-logging.
**AgentOps.** Agent-specific observability with free tier.

A common 2026 production pattern is **LangFuse + Phoenix** (token costs + RAG quality) or **LangSmith + W&B Weave** (LangChain + experiment tracking).

**Where Crawfish wins vs. this category:** we are not a pure observability tool, so we don't compete head-to-head. Crawfish's lens is integrated with the org layer — every trace ties to a CrawfishTask, every span to an `AgentContainer`, every diagnosis to an actionable recommendation in the dash. Pure observability is a losing fight (these incumbents have lapped us on tracing UI). Integrated observability is our win.

**The honest response:** ship OpenTelemetry export from lens so users can pair Crawfish with their existing Phoenix/LangSmith setup. Don't try to replace those tools; complement them.

**Threat-level *green* on the org layer; *red* on standalone observability.**

### 6.9 Adjacent infrastructure — *integrate or absorb*

- **HyperAgent variants** (FSoft-AI4Code's generalist SE multi-agent, Hyperbrowser's Playwright+AI, Hyperlight's WASM sandboxed JS). Reference architectures, not direct competitors; potential partners / acquisition targets.
- **Obsidian.** Not a competitor; the editor we sync to in §3.3.
- **Notion / Confluence / Google Drive.** Knowledge silos we ingest into the org-fs, not competitors. Our value is the agent-facing index over their content.
- **Cursor / Aider / Cline / Continue.dev / Goose / OpenHands.** Agent runtimes we adapt via `crawfish-lens/src/adapters/`. Each is a free distribution channel.
- **Datadog / Honeycomb / Tempo / Grafana / Prometheus.** Adjacent observability; we export to them via OTel.
- **Linear / Jira / GitHub Issues.** External trackers we ingest from and remain authoritative over. **Linear's "agents as first-class workspace members" framing is the bar we have to clear.**
- **Slack / Discord / Teams.** External chat; we ingest archives into the org-fs (opt-in, scoped). No outbound bridge per anti-goals.
- **CodeRabbit / Greptile.** Code-review competitors absorbed by the Phase 6 native review surface.
- **Pilot Protocol.** Agent-native web protocol; complement, not competitor.

### 6.10 Standards bodies — *consider joining*

**Linux Foundation Agentic AI Foundation (AAIF), formed December 2025.** Three inaugural projects, Block Goose is one of them. Becoming a member is a credibility / distribution move that Crawfish should evaluate seriously. The AAIF is on track to become the OSS-agent equivalent of the CNCF — and being a member when the standards solidify (OTel-for-agents, MCP+, agent-identity protocols) is the cheap version of buying that influence later.

**MCP itself (Anthropic-led, increasingly multi-vendor).** Crawfish is already MCP-native. Stay aggressively on top of the spec; contribute the `org_fs_*` and `board_*` shape upstream where it generalizes.

**IETF Pilot Protocol draft (`draft-teodor-pilot-protocol-01`).** Engage with the WG if it forms. The 48-bit agent-addressing scheme is something we want to influence, not just adopt.

### 6.11 Positioning matrix — Crawfish vs. the field

Where Crawfish sits across the seven axes that actually decide buyer fit. ✅ = strong fit, ◐ = partial, ✗ = absent.

| Player | Org framing | Humans + agents as peers | Local-first | Multi-runtime | Memory/knowledge layer | Diagnoses + cost discipline | Non-developer buyer |
|---|---|---|---|---|---|---|---|
| **Crawfish (target)** | ✅ | ✅ | ✅ | ✅ | ✅ (substrate + librarian) | ✅ | ✅ |
| Claude Cowork | ✗ | ✗ | ✗ | ✗ (Claude only) | ◐ (Projects) | ✗ | ✅ |
| CMA | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |
| Ruflo | ◐ (orch frame) | ✗ | ✅ | ◐ (Claude+CMA) | ◐ (separate plugins) | ◐ (cost-tracker) | ✗ |
| Letta | ✗ (agent-centric) | ✗ | ◐ (local option) | ✅ | ✅ (agent state) | ✗ | ✗ |
| Mem0 | ✗ | ✗ | ✅ (OpenMemory) | ✅ | ✅ (per-agent) | ✗ | ✗ |
| Cognee | ✗ | ✗ | ◐ | ✅ | ✅ (substrate) | ✗ | ✗ |
| Glean | ◐ (enterprise) | ✗ | ✗ | ✅ | ✅ (Enterprise Graph) | ✗ | ✅ |
| Sierra | ✅ (vertical) | ◐ | ✗ | ✅ (15+ models) | ✅ (Agent Data Platform) | ◐ | ✅ |
| Cognition / Devin | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |
| Factory AI | ◐ (dev only) | ✗ | ✗ | ✅ | ◐ | ◐ | ✗ |
| Cursor 3 | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |
| Lindy | ◐ | ✗ | ✗ | ✅ | ✗ | ✗ | ✅ |
| Relevance AI | ✅ (workforce) | ✗ | ✗ | ✅ | ✗ | ✗ | ✅ |
| Dust | ◐ | ✗ | ✗ | ✅ | ◐ | ✗ | ✅ |
| Gumloop | ✗ (workflow) | ✗ | ✗ | ✅ | ✗ | ✗ | ✅ |
| Microsoft Agent Framework | ◐ (framework) | ✗ | ✗ | ✅ | ✗ | ✗ | ✗ |
| LangGraph + LangSmith | ✗ (graph) | ✗ | ◐ | ✅ | ✗ | ◐ | ✗ |

The cell that matters most: Crawfish is **the only entry that's ✅ across all seven axes simultaneously.** Every individual competitor is ✅ on a subset and ✗ on the rest. The win condition is to make the all-seven-✅ story credible in product, not just on this matrix.

### 6.12 The strategic posture

Six rules that fall out of this landscape:

1. **Do not fight harness vendors.** Anthropic, OpenAI, and Google will keep eating that layer; we ride on top.
2. **Treat Claude Cowork as the existential question, not a feature comparison.** Anthropic ships every Cowork extension into a market that overlaps with ours. Our defense is multi-runtime + librarian + humans-as-peers + the local-first posture they can't credibly adopt. Move on these visibly fast.
3. **Out-frame and out-substrate the orchestrators.** Ruflo wins on plugin count and dev mindshare; Letta wins on agent state; Mem0 wins on MCP distribution. We win on the *combination*: org framing + heterogeneous source-class router + non-developer buyer.
4. **The agent filesystem + librarian (§3.3.1) is the most-contested feature in this plan, not the safest.** Mem0, Letta, Cognee, Zep, and Glean are all building variants. Shipping fast and shipping the *learning* policy (not just the substrate) is what separates us. The librarian is the moat; the substrate is table stakes by mid-2027.
5. **Don't compete in verticals — orchestrate them.** Sierra owns customer-support agents; Cognition/Factory own autonomous engineering; 11x owns sales SDRs. Crawfish is the org layer that calls into all of them as specialist runtimes.
6. **Be on the standards bodies.** Evaluate joining the Linux Foundation AAIF in 2026. Contribute Crawfish-shaped extensions to MCP. Engage with the Pilot Protocol IETF draft. Standards influence is the cheap version of distribution.

---

## 7 · Cross-cutting technical bets

A handful of decisions cut across both stages. Calling them out so they don't get re-litigated:

- **The agent filesystem is the platform's primary product.** Every other surface — the board, the dash, the runtimes, the marketplace — is a view or a writer on top of the org-fs. When a design question is ambiguous, the answer is whichever option makes the knowledge layer richer or more queryable.
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

## 8 · Sequencing — what ships when, mapped to ROADMAP phases

The ROADMAP defines phases P0–P6. Grand Plan items slot into them as follows.

**P3 (now → 5 weeks):** Native task board + plan + governance v1. §3.2 (kanban + structured criteria), §3.4 (first six skills, `bin/`, `crontab`), §3.6 (founder dashboard), §3.10 (cron recipes), §3.12 (single-session topology), §3.13 (dual analytics MVP).

**P4 (5 → 11 weeks):** Multi-LLM runtimes + GitHub bridge + knowledge layer. §3.1 (industry templates), §3.2 (AI triage + auto-decomposition), §3.3 (three zones + LightRAG), §3.7 Track A (site recipes), §3.11 (`opt-context` + `opt-artifact`), §3.12 (org-level overlay).

**P5 (11 → 16 weeks):** Native messaging + cloud sync stub + team dashboard + marketplace. §3.3 (LLM Wiki + Obsidian sync), §3.5 (Crawfish IDE v0.1), §3.7 Track B (proxy MVP), §3.8 (local Codespaces), §3.9 (test-generation), §3.11 (caching trajectories + dynamic model switching + cost-manager agent), §3.12 (time scrubber), §3.13 (Pendo-parity product side).

**P6 (open-ended):** Native code review + compliance + CI + runtime adapters. §3.3 (CRDT + git-worktree), §3.5 (IDE worktree switcher), §3.7 Track B (more adapters), §3.9 (visual-auditor), §3.12 (pattern detection). Begin Stage 2.

**Stage 2 (months 9 → 24):** §4 wholesale.

**Stage 3 (months 18+):** §5, gated on Stage 2 revenue.

---

## 9 · Persona scorecard — does this plan light each persona up?

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

## 10 · Anti-goals — what we will not build

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

## 11 · Success metrics

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

## 12 · One-paragraph summary

Crawfish in 24 months is the OS for agent-native companies, and the **agent filesystem is its moat**: a founder picks a template and gets a working five-agent company in fifteen minutes; six months later that org's filesystem has eaten the founder's email, code, Slack archive, Notion vault, support tickets, and meeting transcripts, and every new agent the founder spins up inherits the entire company's context because it queries one canonical, source-class-aware, citation-validated knowledge layer; an engineer's Claude Code or CMA session is a first-class member of that org with a budget, a board task, a worktree, and a manager looking over its shoulder; a platform engineer at a 200-person company has one screen that shows every agent in the company, what it cost, what it produced, and whether it's about to do something stupid; a CFO has a forecastable line item; a compliance officer has an audit export; and a research lead has a swarm that doesn't read the same paper thirty times. All of it built on a JSONL substrate, all of it local-first until the user says otherwise, all of it priced in tokens, and all of it shipping as MIT until the day the team-mode features make the case for a paid tier. We ride on top of harness vendors (Anthropic CMA, OpenAI AgentKit, Vertex), out-frame the orchestrators (Ruflo, LangGraph, CrewAI) on org-and-buyer, and own the one surface a frontier vendor cannot: the institutional memory.

That is the destination. The phases get us there. The personas tell us when we've arrived. The filesystem is why we win.

---

*Last updated: 2026-05-16. Source-of-truth for "what's shipped" remains `ROADMAP.md`; for the half-formed ideas not yet committed here, see `BRAINSTORM.md`.*
