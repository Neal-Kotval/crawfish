# Crawfish — Platform Roadmap

> **2026-05-15 pivot:** Crawfish reframed from "agent-team observability" to **Agent Organizations** — the OS for companies that run on AI agents. See [`PRODUCT.md`](./PRODUCT.md). The old observability framing (sections below from §0 onward) is **superseded** but kept for historical context until the relevant pieces are either absorbed into the new model or deleted.

This is the **umbrella roadmap**.

- **Product overview:** [`PRODUCT.md`](./PRODUCT.md)
- **v1 spec:** [`docs/specs/org-contract.md`](./docs/specs/org-contract.md)
- **Forward ideas:** [`BRAINSTORM.md`](./BRAINSTORM.md) *(pre-pivot)*
- **Lens roadmap:** [`crawfish-lens/ROADMAP.md`](./crawfish-lens/ROADMAP.md) *(pre-pivot)*
- **Integration targets:** [`INTEGRATIONS.md`](./INTEGRATIONS.md) *(pre-pivot)*

---

## v1 — Agent Organizations (shipped 2026-05-15)

**Goal:** smallest slice that demonstrates the new framing end-to-end for the bottoms-up motion. A solo founder installs Crawfish, picks the Startup template, gets 5 preconfigured agent members + seeded kanban + shared FS + one manager cron, and points work at them.

**What landed:**

- **Org as first-class container.** On-disk at `~/.crawfish/orgs/<id>/` with `org.json`, `board.jsonl`, `crons.json`, `members/`, `files/`. Schema in [`docs/specs/org-contract.md`](./docs/specs/org-contract.md).
- **Templates.** `crawfish-dash/src/templates/startup/` (5 members: Founder, Eng, Design, Support, Ops). Forking = `cp -r`. `dev-shop`, `support`, `research` scaffolded as empty placeholders.
- **Agent Jira board.** JSONL event log (`task_created | task_updated | task_commented | task_deleted`) + SSE tail in lens. Kanban UI in dash.
- **Hosted org FS.** REST surface (GET/PUT/DELETE) over `files/` with path-escape rules + 1 MiB cap. UI in dash.
- **Manager crons.** `node-cron` daemon in lens reads `crons.json` per org; manual trigger + scheduled fires append to the board. Stub for LLM invocation (TODO marker).
- **Dual analytics.** Dash UI toggle: Dev (existing session token stats via lens proxy) / Product (board aggregations — done count, completion %, tasks per member).
- **`crawfish-orgctl`.** New MCP server exposing `board_*` and `org_fs_*` tools so agents can read/write the board and shared FS. Conforms to optimizer contract v1.0 (`tokens_used` on every response).
- **Marketplace** kept as-is (existing Optimizers tab).

**Architecture in v1:** flat only (one default — `architecture: "flat"` in `org.json`). Switchable architectures (hierarchical / pipeline / hybrid) deferred.

**Out of scope (deferred):**
- Enterprise governance (SSO, RBAC, audit log beyond board.jsonl)
- Switchable agent architectures
- Additional templates beyond Startup
- Multi-org switcher in the desktop shell
- Real LLM invocation from cron runs (TODO in `crawfish-lens/src/server/crons.ts`)
- Member validation on board events (server accepts any `by` / `assignee` string)

---

## v2 candidates (post-launch)

In rough priority order — each is independently shippable.

1. **Real cron runs.** Wire `node-cron` fire → Anthropic SDK call using the member's prompt file + tool list. Output target per `output_to` field.
2. **Member ACL.** Validate `by` / `assignee` against `org.json`; reject unknown members with `invalid_member`.
3. **More templates.** Flesh out `dev-shop` (agency model: PM + 3 engineers + QA), `support` (tier-1 + escalation), `research` (lead + 3 specialists).
4. **Architecture picker.** Hierarchical (manager → workers) and pipeline (sequential handoffs) variants of the Startup template.
5. **Stats endpoint.** Implement `GET /api/orgs/:id/stats?view=dev|product` server-side so the Analytics UI doesn't fold client-side.
6. **Multi-org switcher.** Top-bar dropdown to switch active org in the Tauri shell.
7. **Human members.** Promote the v1 human stub (name + avatar) to a real identity with sign-in, mention notifications.

---

## Historical: pre-pivot observability roadmap (superseded)

The sections below described the observability tool Crawfish was before 2026-05-15. They remain here so the diagnoses / policy enforcement / savings work still in the codebase has a paper trail. Sections from §0 ("North star") downward all belong to that pre-pivot model.

---

## 0. North star *(pre-pivot)*

**One sentence:** *Make multi-agent token waste visible at the team level, then enforce the optimizers that fix it — locally, with no transcripts leaving customer machines.*

**Done looks like:** A platform engineer at an AI-forward team installs the desktop app, runs the first-run wizard, sees their team's compounding factor (4.2× across last week's sessions), runs the policy wizard with a dry-run preview that quotes a measured savings number, distributes the resulting bundle via git, and the next week's bill drops measurably. Engineers' agents hit the policy hook → wasteful patterns auto-route to the relevant optimizer → savings show up in the per-session view → the platform engineer watches the trend in dash. Everything runs on `127.0.0.1`. No transcript ever leaves a customer machine.

**Done does NOT look like:** A vendor-hosted SaaS. A generic LLM observability tool. A framework. A prompt-rewriter. An agent vendor. See [`PRODUCT.md` § Anti-goals](./PRODUCT.md).

---

## 0a. Posture for this cycle: free, local, OSS

Decision from [BRAINSTORM.md § Decisions](./BRAINSTORM.md): **stay free and local-first through this cycle.** Everything ships MIT, runs on `127.0.0.1`, assumes a single-machine user. Pricing is a later move once adoption is real; the candidate paid tiers when that time comes are team-mode aggregation and the hosted-orchestrator deployment shape — not the solo experience.

This decision cascades:

- **Solo engineer first** for any orchestrator work — single-machine OpenClaw bundle, no auth, no multi-tenant.
- **In-repo `.crawfish/`** for codebase prep artifacts — committed-to-share is the cheapest team distribution we have without server infra.
- **OpenTelemetry first** for analysis-tool integration — open standard fits local-first better than vendor-shaped Grafana JSON.

Pricing trigger is a *signal*, not a date: the first team that asks for multi-engineer aggregation we don't already have.

---

## 0b. Moats — what makes crawfish defensible

The current pitch is a *feature combination*, not a moat. To be a fundable company (not a tool), at least one of three edges has to become load-bearing. **Pick one. Double down. The rest are supporting cast.**

### Edge 1 — Multi-agent topology as a standard
Emit OpenTelemetry-compatible **agent fan-out spans** (parent-child relationship, prompt-spawn tokens, child-internal tokens). Define `crawfish-topology-spans@1.0` as an open spec. Submit to OpenTelemetry's GenAI semantic conventions group. Outcome: any vendor that wants to talk about subagent costs adopts your schema.

### Edge 2 — Policy bundles as a portable format
Define `crawfish-policy@1.0` as an open spec — JSON schema, signed bundles, runtime adapters for Claude Code / OpenClaw / Cursor / custom orchestrators. crawfish ships the reference implementation; the format is the moat.

### Edge 3 — Closed-loop optimization (the data product)
Lens watches transcripts and **automatically proposes new policies and optimizer configs** based on observed waste, with confidence scores and predicted savings. Statistical heuristics in v1, opt-in aggregate model in v2.

**Working assumption for this cycle:** Edge 1 (topology spans) lands first because it's a byproduct of the journey + flow work in C2.P1, and it sets up Edge 2 cleanly. Edge 3 needs aggregate data we don't have yet — gated on the post-cycle pricing trigger.

**Why Edge 1 lands first, concretely:** the topology visualizer (§ 3.0) makes the schema visible. Spans aren't compelling on their own; a 30-second visualization of multi-agent waste with a *real* policy intervention layered on top is. The visualizer creates demand for the engine; the engine makes the visualizer credible. Neither moves alone — but the visualizer is what gets the schema adopted, not the schema doc. Adoption follows demos, not specs.

---

## 1. Cycle 2 — overview

The first cycle (C1: phases P0 → P1.5) shipped the platform substrate. **Cycle 2 turns the substrate into something a team adopts.**

The unifying frame: C1 answered *"where did the tokens go?"* C2 answers *"what is the agent **doing**, and was it the right thing?"* — i.e., move from cost accounting to **work accounting**. Same JSONL substrate, richer reductions over it, plus the on-ramps that turn it into adoption.

| Phase | What lands | What unlocks | Honest weeks |
|---|---|---|---|
| **C1.P0–P1.5** | Lens M1, dash v0.2, crawfish-opt v0.2, crawfish-opt-codebase v0.1, crawfish-app v0.1 | Local data is readable; "see → fix" loop runs end-to-end; policy enforcement shipped; native shell. | ✅ done |
| **C2.P1 — Journeys & flow** | Engine: journey timeline + flow/graph reductions + Lens M2 diagnoses + JSON API v1 + OTel exporter. Legibility: topology visualizer that renders all of it. | Per-agent legibility *and* the engine substance behind it. Engine creates the value; visualizer makes it sellable. Edge 1 anchor. | 4-6 |
| **C2.P2 — Adoption on-ramps** | First-run wizard, policy wizard with dry-run preview, codebase prep wizard + `.crawfish/` artifacts | A new user gets to a measurable win in <10 minutes. | 3-4 |
| **C2.P3 — Multi-runtime** | `crawfish-orchestrator` daemon (solo OpenClaw bundle), lens adapters per [INTEGRATIONS.md](./INTEGRATIONS.md), dash runtime selector | Single-platform-dependency objection neutralized; Edge 2 anchor. | 5-7 |
| **C2.P4 — Integration breadth** | Webhook bus, Linear/Slack hooks, BI export, Grafana dashboards (after OTel), additional optimizers (logs, search) | The data is useful where the team already lives. | 4-5 |
| **C2.P5 — Pricing trigger gate** | Team-mode aggregator design (build only if signal arrives) | First paid surface, only if real demand. | gated |

**Total cycle:** 16-22 focused weeks. Solo, evening/weekend pace, no surprises. The signal-gated phase doesn't count.

---

## 2. The optimizer contract (shared spec, unchanged from C1)

Every crawfish-line MCP server MUST:

1. **Self-report `tokens_used`** on every tool response:
   ```jsonc
   { "tokens_used": { "input_estimate": 312, "output_estimate": 28, "method": "haiku|tiktoken|bytes/4" } }
   ```
2. **Be idempotent on retry.** An agent re-calling after a stall must not multiply API cost.
3. **Degrade gracefully without an API key.** Fall back to deterministic logic; surface a `degraded: true` flag.
4. **Address one token sink.** Browser, codebase, logs, search — not "everything."
5. **Ship a benchmark.** `bench/baseline-vs-optimizer.ts` with tokens-saved on a fixed task set.
6. **Version compatibility:** declare `crawfish-contract: "1.0"` in `package.json`.

Lens MUST:

1. **Read** `tokens_used` from tool results when present, treat as authoritative.
2. **Detect contract violations** by diffing self-report against the next assistant turn's `cache_creation_input_tokens` delta. Flag drift > 20%.
3. **Never depend on an optimizer being installed.** Base experience works against any session.

---

## 3. C2.P1 — Journeys & flow

**Goal:** turn lens from a cost histogram into a work-accounting tool. Per-agent timelines, flow rates, graph structure of fan-out, and the open-format span schema that anchors Edge 1.

This is the load-bearing phase of the cycle. Everything in C2.P2-P4 reduces to "make these new reductions adoptable."

**Two halves of this phase, both first-class:**

1. **The engine** (§ 3.1–3.4) — the measurements, rules, reductions, and schema that *do something*: detect waste, attribute it to a cause, and feed the policy/optimizer line that fixes it. This is the substance.
2. **The legibility layer** (§ 3.0 — topology visualizer) — the artifact that makes the engine's invisible value visible to a buyer evaluating the platform, a platform engineer justifying the budget line, a team lead picking which policy to ship. This is what creates demand for the substance.

**Both halves are required.** A great engine without legibility is a tool nobody adopts because they can't see what it does. A great visualizer without an engine is a screensaver that doesn't survive contact with real usage. The roadmap historically overweighted the engine; this phase corrects the balance by ranking § 3.0 as a peer of § 3.1–3.4, not a UI afterthought.

**Litmus test for any work in this phase:** does it *do something* (reduce tokens / prevent waste / enforce policy) or does it *make something visible* (surface waste / reveal topology / show before-after)? Healthy phase has both. Either alone doesn't sell.

### 3.0 Topology visualizer — the legibility layer (BRAINSTORM §3, elevated)

The artifact that makes the platform's invisible value visible. **Necessary, but not sufficient on its own** — it presents what the engine in § 3.1–3.4 produces; it doesn't replace it. Multi-agent waste is invisible by default (which is why teams overspend on agents in the first place). The visualizer makes the picture.

**Three beats, in this order. Every pixel maps to a real lens measurement — no simulation, no synthetic flows, no smoothing.**

1. **The waste.** Animate a real session. Parent at top, subagents spawn under it. Edges are token flows — thickness proportional to volume, color encoding usefulness vs redundancy. Sibling reads of the same file draw a red link between siblings. A path Read 3× with no Edit between pulses. A subagent that burned 40k tokens to produce 200 useful pulses red. The viewer feels waste *viscerally*.
2. **The intervention.** Replay the same session with a Crawfish policy active. Blocked tool calls flash and disappear. Redundant subagents never spawn. Compounding factor counter at the top drops from 5.2× to 1.8× in real time. Total tokens drop from 240k to 70k. **This is the screenshot the platform engineer sends their VP.**
3. **The control.** Show the policy that did it: a JSON snippet, four rules, signed bundle, distributed via git, three lines in `~/.claude/settings.json`. The viewer understands they could ship this to their team this afternoon.

**Required properties:**

- [ ] **Real session data, not demos.** The user's own topology renders within seconds of opening the view. No marketing fixtures.
- [ ] **Embeddable.** A snapshot can be pasted into Slack and the recipient sees the same picture (static SVG/PNG export of the current view, plus a link back to the live version on the sender's machine if they want to interact).
- [ ] **Before/after policy preview.** The dry-run preview from the policy wizard (C2.P2 § 4.2) is *visual*, not numeric — same topology with the waste edges removed and the new compounding factor on the badge.
- [ ] **Live updates.** During an active session, edges grow as tokens flow. This is what goes on the second monitor (currently § 3.2's "live throughput strip" — subsumed into this view).
- [ ] **60-second loop on the landing page** (eventually). Built from a real anonymized session, not hand-crafted. Loop = waste → intervention → control, three beats, no narration needed.

**Discipline (do not violate):**

- This is a **presentation layer for the engine.** It shows what lens, dash, and the policy hook already do. Every pixel maps to a measurement that already exists in lens. The visualizer doesn't reduce tokens; the policy hook reduces tokens. The visualizer doesn't fix re-read loops; the codebase optimizer fixes them. What the visualizer does is make the value of those things impossible to ignore.
- It is **not** an orchestration layer. We do not "improve how agents talk to each other" or provide "agent-to-agent control." Showing the topology = observability. Becoming the topology = framework. The first is the moat; the second dilutes it. See § 10 anti-goal.
- **Stays a screensaver if § 3.1–3.4 don't ship.** The visualizer's credibility depends on the engine. If users install it, see their topology, click intervene, and the savings number is wrong or the policy doesn't actually block — they leave. Substance under the surface, always.

**Acceptance:** Open the desktop app on a fresh checkout of a Claude Code project, click any session, see the three-beat demo render against that real session — waste highlighted, dry-run policy applied, control plane revealed — within 60 seconds with no setup. The interventions shown are *real* (the policy actually blocks those tool calls in the engine; the savings number is the real lens reduction, not a mockup). Take a screenshot, paste into Slack, recipient sees the same picture.

**Dependencies on the rest of § 3:** § 3.1 produces per-call entries the visualizer animates. § 3.2 produces the compounding factor and edge-weight numbers. § 3.3 produces the redness rules (sibling redundancy, re-read loops). § 3.4 produces the schema that makes a snapshot portable. The visualizer *renders* the engine; without § 3.1–3.4 it has nothing to show.

### 3.1 Journey timeline view (BRAINSTORM §3)

Per-agent Gantt-shaped artifact: one swimlane per agent (parent + each subagent), each tool call a block (width = duration, color = tool, height = result-byte cost).

- [ ] **Schema:** `JourneyEvent = { agentId, ts, kind: "tool_use" | "tool_result" | "reasoning" | "spawn", … }` in lens core.
- [ ] **Endpoint:** `GET /api/sessions/:id/journey` returns time-ordered event list with reasoning attached.
- [ ] **Dash view:** Sessions tab gains a Journey detail (sibling to the existing list). React component using a virtualized SVG timeline (no chart library — Reactflow / d3 are surface-area sprawl).
- [ ] **Reasoning overlay:** toggle to show assistant text inline as tooltips. **Default: on** (consistent with local-first posture; flip later if enterprise conversations push back).
- [ ] **Browser overlay:** when a journey involves `crawfish-opt` tool calls, show the zone summary, chosen element, and action inline.
- [ ] **Replay scrubber:** drag a cursor to reconstruct the agent's context window at time T. Bounded JSONL replay; fine for sessions up to ~1k turns.
- [ ] **Journey diff:** two sessions side-by-side with first-divergent-tool-call alignment. (Smith-Waterman is overkill for v1.)

**Acceptance:** Open any session, see every tool call laid out in time, scrub to any moment and see what the agent knew.

### 3.2 Flow rates + graph reductions (BRAINSTORM §1)

- [ ] **`FlowStats` reduction** in lens core, time-bucketed (default 30s windows + per-tool-call deltas, both available via API).
- [ ] **Per-agent token velocity** as a first-class metric. Alert threshold default: 40k tok/min sustained for 60s on a subagent.
- [ ] **Compounding factor** as a session-level KPI: `total_subagent_tokens / parent_useful_tokens`. Surface in lens session detail and dash header.
- [ ] **Graph reductions:** branching factor, depth, sibling-redundancy (siblings reading the same files), critical path. Computed once per session, cached per `Session.id` until JSONL mtime changes.
- [ ] **Live throughput strip in dash:** sparklines for in-flight sessions (tok/min, tools/min, active subagent count). Feeds the live-update mode of the topology demo (§ 3.0); the demo is the surface, the strip is the data feed.

### 3.3 Lens M2 — full diagnoses catalog

The C1 ship had only the oversized-tool-result rule. C2.P1 fills it out, including the new graph + journey rules unlocked by §3.1 and §3.2.

Each rule is `crawfish-lens/src/diagnoses/rules/<id>.ts`, registered in `registry.ts`. Each ships with a positive fixture, a negative fixture, and a one-paragraph doc fragment.

**Single-call rules (refined from C1):**
- [ ] `oversized-tool-result` — upgrade to real tokenizer (`@anthropic-ai/tokenizer` if available).
- [ ] `dom-dump-detected` — large `tool_result` matching `<html`/`<!doctype`. Recommends `crawfish-opt`.
- [ ] `log-truncation-pattern` — Bash result ending in `...` or `[truncated at N lines]`. Recommends `crawfish-opt-logs` (C2.P4).
- [ ] `thinking-overhead` — extended thinking on, output <100 tok. Wasted reasoning budget.

**Journey rules (new in C2.P1):**
- [ ] `re-read-loops` — same `Read(path)` ≥3× with no intervening Edit. Recommends `crawfish-opt-codebase` *with the specific path*.
- [ ] `grep-then-read-storms` — `Grep` followed by ≥5 `Read` calls within 30s. Recommends `codebase_search`.
- [ ] `dom-oscillation` — repeated `browser_navigate` to the same URL. Recommends `browser_state`.
- [ ] `subagent-thrash` — parent spawns same Agent type ≥3× in 5 minutes. Recommends agent-definition review.
- [ ] `context-window-panic` — token velocity at >80% of context window. Pre-empt with checkpoint.

**Graph rules (new in C2.P1):**
- [ ] `sibling-redundancy` — N≥3 sibling subagents reading the same file. Recommends `crawfish-opt-codebase` + `crawfish prep` (C2.P2).
- [ ] `agent-fanout-cost` — Agent's subagent total >10× the parent's tokens. Severity scales with multiplier.
- [ ] `low-cache-hit-rate` — long session (>20 turns), hit rate <50%. Surface the *delta* in `cache_creation_input_tokens` between adjacent turns.

### 3.4 JSON API v1 + OpenTelemetry exporter (Edge 1 anchor)

- [ ] **Stabilize and version** the lens HTTP API under `/api/v1/`. Publish a JSON schema in `crawfish-lens/docs/api-schema.json`.
- [ ] **Document every endpoint** in `crawfish-lens/docs/api.md`. Backwards-compatibility starts here.
- [ ] **OTel exporter** — every journey is a trace, every tool call is a span, reasoning is a span event. Use the GenAI semantic conventions where applicable; extend with `crawfish-topology-spans@1.0` for the fan-out fields no current spec covers.
- [ ] **Span schema spec** in `docs/specs/topology-spans-1.0.md`. Public, versioned.
- [ ] **Submit to OTel GenAI WG** as an information item once shipped.

**Acceptance for C2.P1 (both halves):**

- *Engine half (§ 3.1–3.4):* journey timeline produces per-call entries with reasoning + duration; flow + graph reductions produce per-session compounding factor and live throughput; ≥8 of the 11 diagnoses fire on real fixtures with concrete fixes; API is versioned and OTel spans validate against the published schema.
- *Legibility half (§ 3.0):* the visualizer renders the three beats — waste / intervention / control — against the user's own data within 60 seconds of opening it; the intervention beat reflects what the *real* policy hook does, not a mockup; a snapshot is shareable as a static image plus an OTel trace.

Either half missing → C2.P1 doesn't ship. The engine without the visualizer is invisible work. The visualizer without the engine is a screensaver. Both, together, are the phase.

---

## 4. C2.P2 — Adoption on-ramps

**Goal:** any new user gets to a measurable win in <10 minutes. Three wizards, ordered by maturity.

### 4.1 First-run wizard (BRAINSTORM §4a)

- [ ] Detects `~/.claude/projects/` (or fails gracefully).
- [ ] Imports the most recent week of sessions.
- [ ] Computes the user's compounding factor and shows it as a number with context: *"Your team is at 4.2× — typical for this size. Top sink: Read on `src/lib/`."*
- [ ] Offers one action: install `crawfish-opt-codebase` (copy-to-clipboard).
- [ ] Closes with: *"Lens will keep watching. Open dash anytime."*
- [ ] Auto-launches when dash detects no prior session view.

### 4.2 Policy wizard (BRAINSTORM §4b)

The wedge for platform engineers. The dry-run preview is the entire pitch.

- [ ] Three questions: (i) what tools were most expensive in the last 30d? (ii) which should warn / block / log-only? (iii) which optimizer should each route to?
- [ ] **Dry-run preview**: replay past tool calls against the candidate policy, surface the number — *"if this policy had been live last week, it would have saved 3.4M tokens across 12 sessions."*
- [ ] Outputs `policy.json` and a one-line install command for engineers (`crawfish-dash install-hooks --policy <url>`).
- [ ] Bundle export: signed git URL distribution (sets up Edge 2 in the next phase).

### 4.3 Codebase prep + wizard (BRAINSTORM §2 + §4c)

The intervention before the journey starts. Subcommand of `crawfish-opt-codebase` (avoids surface sprawl) wrapped in a dash UI.

- [ ] **`crawfish prep` subcommand** generates idempotently:
  - `.crawfish/map.md` — top-level architecture summary, ~2k tokens, hand-editable.
  - `.crawfish/index.json` — module → file → top-level decls, pre-computed.
  - `.crawfish/conventions.md` — naming, layout, "where does X live", distilled from `git log` + structure.
  - `.crawfish/hot-paths.json` — the 20 files most often touched together (from `git log` co-change).
  - `.crawfish/agents/` — recommended subagent definitions tuned to this repo.
- [ ] **Decision: in-repo (committed `.crawfish/`).** Team rollout via PR.
- [ ] **Idempotent re-run** — diffs artifacts, doesn't churn.
- [ ] **`pre-commit` hook** to refresh on commit (avoid watch-mode rebuild storms).
- [ ] **Wizard UI in dash** — detect monorepo vs single-package, suggest defaults, let user review and edit `map.md` before commit, one-click "create PR" if `gh` is configured.
- [ ] **A/B telemetry**: lens marks sessions on a repo before/after the prep commit and reports the compounding-factor delta in dash. **This is the artifact that justifies the prep tool.**

**Acceptance for C2.P2:** A platform engineer on a fresh machine opens dash, runs first-run wizard, sees compounding factor, runs policy wizard with dry-run, exports a bundle, runs prep wizard on their main repo, opens a PR with the artifacts. Total time <15 minutes.

---

## 5. C2.P3 — Multi-runtime

**Goal:** neutralize the single-platform-dependency objection. The data layer is already runtime-agnostic ([INTEGRATIONS.md](./INTEGRATIONS.md)); this phase ships the adapters and the orchestrator wedge.

### 5.1 Lens transcript adapters

Cheap pattern, highest ROI per [INTEGRATIONS.md](./INTEGRATIONS.md). Each adapter is `crawfish-lens/src/adapters/<runtime>.ts` producing the same internal `SessionStats` + `JourneyEvents`.

- [ ] **OpenClaw adapter** — read OpenClaw session files, map to crawfish event schema.
- [ ] **Cursor adapter** — read `.cursor/logs/`, attribute tool calls.
- [ ] **Anthropic SDK adapter** — for custom orchestrators that import the SDK directly. Opt-in proxy or filesystem dump format.
- [ ] **Adapter contract doc** at `docs/specs/adapter-contract.md`. Defines the minimum fields a runtime must surface to be observable.

### 5.2 Dash runtime selector

- [ ] Runtime dropdown on the Sessions tab — Claude Code (default), OpenClaw, Cursor, custom.
- [ ] Cross-runtime aggregation — compounding factor per runtime, total spend per runtime.
- [ ] Per-runtime install instructions for the optimizer set.

### 5.3 `crawfish-orchestrator` — solo OpenClaw bundle (BRAINSTORM §5a)

**Decision:** solo engineer first. Single-machine launchd / sqlite, no auth, no multi-tenant. Team deployment is a future paid phase.

- [ ] **New submodule:** `crawfish-orchestrator`. Sixth submodule (or seventh if counting `crawfish-opt-codebase` separately — confirm before scaffolding).
- [ ] **Daemon:** wraps OpenClaw at a pinned version, binds `127.0.0.1`, writes transcripts to `~/.crawfish/openclaw/sessions/*.jsonl` in lens's schema.
- [ ] **PreToolUse middleware** equivalent: translate the policy bundle contract to OpenClaw's middleware shape.
- [ ] **Wizard** (C2.P2 sibling): pulls OpenClaw at pinned version, asks 3 questions (which models, context budget, preinstalled optimizers), generates config + launchd plist on macOS, starts daemon, verifies lens sees first transcript within 30s.
- [ ] **2-3 named profiles** ("solo dev", "platform team", "research") rather than one config.
- [ ] **Honest docs** about what crawfish adds vs. what's just OpenClaw — the wedge is defaults + integrated observability, not the runtime.

### 5.4 Hook injection per runtime

Per [INTEGRATIONS.md](./INTEGRATIONS.md), this is the team-mode upsell of the future paid tier. C2.P3 ships only the *contract* — `crawfish-policy@1.0` as an open spec — so adapters can be written.

- [ ] **`crawfish-policy@1.0` spec** at `docs/specs/policy-format-1.0.md`. JSON schema, signed-bundle format, runtime-adapter interface. Edge 2 anchor.
- [ ] **Reference adapter for Claude Code** is the existing `crawfish-hook` — refactor it to consume the spec'd format verbatim.
- [ ] **Reference adapter for OpenClaw** ships in `crawfish-orchestrator`.

**Schema must cover** (driven by the rules in [BRAINSTORM § 7](./BRAINSTORM.md#7-new-optimizers--policy-rules--token-discipline-wave) — record here so the spec doesn't miss anything when drafted):

*New `match` fields:*
- `tool_result_size: { gt | lt: <bytes> }` — match on the size of the prior tool's result (oversized DOM, oversized log, oversized fetch).
- `tool_schema_size: { gt: <bytes> }` — match on the registered schema size of an MCP tool (`opt-mcp-shrinker` trigger).
- `repeat_count: { tool, args_match, window_seconds, gte: <n> }` — same tool with matching args called ≥N times in a window (`re-read-loops`, `dom-oscillation`).
- `sequence: [<tool_pattern>, …, { within_seconds: N }]` — ordered tool sequence (`grep-then-read-storms`).
- `subagent: { siblings_gte, file_overlap_gte, depth_gte }` — graph-shape conditions (`sibling-redundancy`, fan-out blocks).
- `cache_state: { hit_rate_lt | tool_uses_accumulated_gt }` — context-discipline triggers for `opt-context`.
- `result_shape: { json_array_len_gt, content_type }` — for `opt-toon` routing.

*New `action` values (extending the current `warn` / `block` / `log-only`):*
- `rewrite: { via: "<optimizer-id>", mode: "transparent" | "prompt-user" }` — pass the call through an optimizer that returns a smaller equivalent (artifact-id substitution, TOON conversion, log condensation).
- `trigger: { hook: "<hook-id>" }` — fire a side-effecting hook (e.g., `opt-context` clear) without blocking the call.
- `route: { to: "<optimizer-id>" }` — proxy the call entirely to a different MCP server (shrinker case).

*New top-level rule fields:*
- `attribution: { agent_scope: "self" | "any-descendant" }` — does the rule apply to the current agent only, or to anything spawned under it? Required for graph-shape rules.
- `severity: "info" | "warn" | "high"` — feeds the Linear/Jira hook routing in C2.P4 § 6.2.
- `recommend.estimated_savings: { method: "static" | "dry-run", tokens: <n> }` — the dry-run preview number from C2.P2 § 4.2 needs a place to live per-rule.

The Claude Code reference adapter must be able to express every existing rule plus all of the above without escape hatches. If a rule needs a custom predicate, the spec is wrong — extend the schema, don't add a JS callback field.

**Acceptance for C2.P3:** Run `crawfish orchestrator init`, get a working local OpenClaw with policy enforcement and lens visibility. Switch the runtime selector in dash to OpenClaw, see the same compounding factor / journey / flow views work without modification.

---

## 6. C2.P4 — Integration breadth

**Goal:** the data is useful where the team already lives.

### 6.1 Optimizer breadth

The token-discipline wave from [BRAINSTORM § 7](./BRAINSTORM.md#7-new-optimizers--policy-rules--token-discipline-wave) lands here. Sequence by leverage:

- [ ] **`crawfish-opt-context` v0.1** — managed proxy in front of Anthropic's `clear_tool_uses_20250919` beta. Per-tool TTLs, exclude-from-clear lists, every clear logged to lens. Headline number: 84% reduction on a 100-turn web-search eval (Anthropic). Pairs with `opt-artifact` for the "stop silently dropping context" story.
- [ ] **`crawfish-opt-artifact` v0.1** — durable-reference returns. Tools producing big payloads write to `~/.crawfish/artifacts/<id>` and return `{artifact_id, summary, next_action}`. Maps to MCP `_meta` persistence + `anthropic/maxResultSizeChars`.
- [ ] **`crawfish-opt-mcp-shrinker` v0.1** — proxy that lazy-loads other MCP servers' tool schemas. Highest cross-stack leverage — benefits every MCP server in the user's environment, not just crawfish's own. Atlassian measured 70-97% schema bloat.
- [ ] **`crawfish-opt-fork` v0.1** — fork-aware subagent spawner. Collapses N parallel `cache_control` markers into a single trailing breakpoint; prefers forked subagents reusing parent prompt cache. Moves the compounding-factor headline number directly.
- [ ] **`crawfish-opt-logs` v0.1** — `logs_summarize`, `logs_grep`, `logs_tail_smart`. Benchmark: 10 representative dumps (npm install, build output, stack traces, K8s events). Wired to `log-truncation-pattern` diagnosis.
- [ ] **`crawfish-opt-codebase` v0.2 — repomap mode** — Aider-style tree-sitter symbol map, PageRank-ranked, token-budgeted. Cursor A/B'd 46.9% reduction on equivalent. Subcommand of existing optimizer, not a new submodule.
- [ ] **`crawfish-opt-search` v0.1** — top-3 + summary, not full SERP.
- [ ] **TOON formatter** — utility inside `crawfish-opt-codebase` (and any MCP returning tabular data). 30-60% input-token reduction on uniform records. Tiny; not its own server.
- [ ] All optimizers wired to journey + graph diagnoses (`log-truncation-pattern` → logs; `re-read-loops` → codebase repomap; `sibling-redundancy` → fork; oversized-result → artifact + context).

**Validation gate before scaffolding:** the 84% / 59% / 70-97% / 46.9% claims came from vendor blogs. Before committing engineering weeks to any of these, run lens against a representative sample of real Claude Code transcripts and confirm the savings would have held. The journey rules in C2.P1 § 3.3 produce the data needed to estimate this.

### 6.2 Webhooks + event bus (BRAINSTORM §6e)

- [ ] **Lens event bus** — subscribers for `policy.block`, `diagnosis.flagged`, `session.complete`.
- [ ] **Local queue** with best-effort delivery (the user's machine isn't always online).
- [ ] **Slack adapter** — post on policy block: *"Crawfish blocked an oversized DOM dump in @engineer's session — saved 18k tokens."*
- [ ] **Linear/Jira adapter** — `severity: high` diagnosis opens a ticket: *"Repo `foo` is at 5.2× compounding. Recommend running `crawfish prep`."*

### 6.3 BI export

- [ ] Nightly dump to `~/.crawfish/data/*.parquet`. User copies to wherever they want.
- [ ] Schema doc at `docs/specs/data-export-1.0.md`.

### 6.4 Grafana dashboards (after OTel landed in C2.P1)

- [ ] **`crawfish-integrations/grafana/`** — three pre-built dashboards:
  - "Team weekly spend"
  - "Compounding factor over time"
  - "Policy compliance"
- [ ] PR-driven, not a framework.

### 6.5 Prometheus exporter

- [ ] `/metrics` endpoint on lens: `crawfish_session_tokens_total`, `crawfish_compounding_factor`, `crawfish_policy_decisions_total{action="block"}`.

**Acceptance for C2.P4:** A platform engineer with an existing observability stack imports the Grafana dashboards, points their OTel collector at lens, gets a Slack ping the first time the policy hook blocks something, and never opens dash again unless they want to. Crawfish becomes ambient.

---

## 7. C2.P5 — Pricing trigger gate

**Not built unless the trigger fires.** The trigger: first team that asks for multi-engineer aggregation we don't already have.

If/when that happens:

- [ ] **`crawfish-team`** — new submodule, self-hosted aggregator.
- [ ] **Opt-in stat sharing** from ICs to org aggregator. Anonymous-by-default. Reversible.
- [ ] **Bundle distribution** via signed git URLs — `crawfish team install <url>` consumes policy + optimizer set + aggregator endpoint.
- [ ] **Aggregator UI** — cross-engineer rollups, team-wide compounding factor trends, repo-level prep status.
- [ ] **Pricing model decision** at this point — open core (everything else stays free, team aggregator is paid) is the most likely shape.

This is the moment crawfish becomes a company. **Don't build it on spec.**

---

## 8. Continuing work in parallel

Things that don't fit a single phase but should keep moving:

- **Tauri shell maturation** — code-signing + notarization, Linux + Windows verified bundles, auto-updater, bundled Node runtime. Currently deferred per `crawfish-app/BUILD.md`.
- **Optimizer benchmark harness** — shared `bench/` in umbrella, CI runs nightly across all known optimizers, dash shows historical trends.
- **Public release polish** — landing page (markdown-only, GitHub Pages), `npm publish` for the umbrella, announce on HN / Anthropic Discord / agents-themed Twitter.
- **Reference agents** (carried over from product discussion) — open MIT, demonstrate the platform end-to-end. ACTOR / DESIGNER / ARCHITECT / USER / DEVELOPER as forkable definitions wired to the matching optimizers. Ship as the orchestrator's default profile.

---

## 9. Risks, ranked

1. **Transcript schema drift.** Claude Code (or OpenClaw, or Cursor) releases change the JSONL shape. *Mitigation:* version-pin in per-adapter `transcript-format.md`, golden-file tests, tolerant parser. The multi-runtime work in C2.P3 is partly insurance against this.
2. **Optimizer benchmarks are gameable.** Authors tune to the bench; real-world wins don't materialize. *Mitigation:* benchmarks public and reproducible; lens detects contract violations from real session data.
3. **Scope creep into generic LLM observability.** Every feature must answer *"does this help a user spend fewer tokens or run a healthier multi-agent setup?"* If "well, it's nice telemetry" — cut.
4. **Solo bandwidth.** C2 is 16-22 weeks. Realistic at evening pace with discipline. *Mitigation:* C2.P1 is the load-bearing phase; earn the right to keep going by shipping it.
5. **Privacy panic.** Someone screenshots a transcript with a secret in it. *Mitigation:* localhost-only, redact mode for `--json` exports, prominent privacy doc, reasoning-overlay toggle if enterprise pushback materializes.
6. **OTel spec submission stalls.** The GenAI WG moves slowly; *crawfish-topology-spans@1.0* may sit unadopted for quarters. *Mitigation:* the schema is valuable to *us* whether or not it's ratified; ship it as our public spec and let adoption follow.
7. **Anthropic ships first-party multi-agent observability.** Possible but unlikely at this granularity, and even then, the multi-runtime work in C2.P3 + the optimizer line are independently valuable.
8. **OpenClaw upstream changes.** Pinning a version is fine until a security fix lands and the pin diverges. *Mitigation:* explicit "pinned at vN; bump cadence quarterly" doc, clear escape hatch ("just run OpenClaw yourself").

---

## 10. What we're NOT building this cycle

Listed here so we don't drift:

- **A hosted-by-us SaaS.** Local-first is a feature, not a temporary state.
- **A generic LLM observability tool.** No OpenAI/Bedrock/Gemini support — dilutes the moat, doubles the maintenance surface.
- **A prompt-engineering tool.** No "rewrite your system prompt" suggestions.
- **An evals platform.** Token efficiency ≠ task accuracy.
- **A framework.** No `crawfish.config.ts`, no plugin lifecycle hooks. Each optimizer stands alone; policies are JSON.
- **An agent vendor.** Reference agents in §8 are *demonstrations*, not a product line. Open, forkable, replaceable.
- **An agent orchestration / agent-to-agent communication layer.** The topology demo (§ 3.0) *visualizes* parent-child agent control so users can see what's happening; it does not *provide* that control. The moment the pitch becomes "we improve how agents talk to each other," we're an agent framework competing with everyone, not a measurement-and-control platform. Showing the topology = observability (the moat). Becoming the topology = framework (dilutes everything).
- **A persistent database.** The filesystem IS the database.
- **Cost-in-dollars as the primary unit.** Tokens are the unit. Pricing overlay (`pricing.json`) is opt-in, off by default.
- **Auto-installation of optimizers or policy bundles.** User confirms every install.
- **Authentication.** Localhost-only.
- **Cross-machine session aggregation.** Gated on the C2.P5 trigger.

---

## 11. Source of truth

- **What's shipped:** `main` branch of each submodule.
- **What's planned:** this file.
- **What's been considered and decided against:** § 10 above + [`PRODUCT.md` § Anti-goals](./PRODUCT.md).
- **Half-formed ideas with assigned phase pointers:** [`BRAINSTORM.md`](./BRAINSTORM.md).
- **Decisions log:** [`BRAINSTORM.md` § Decisions](./BRAINSTORM.md).

Last updated: 2026-05-08.
