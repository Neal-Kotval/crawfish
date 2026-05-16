# Crawfish — Brainstorm

> Working doc. Expansions of half-formed ideas, mapped to the existing platform (`PRODUCT.md`). Each section ends with **Where it plugs in** to keep the surface count from drifting.

The unifying frame: today crawfish answers *"where did the tokens go?"*. The next wave answers *"what is the agent **doing**, and was it the right thing?"* — i.e., move from cost accounting to **work accounting**. Same JSONL substrate, richer reductions over it.

---

## 1. Flow rates + graph analysis

### The idea
Right now lens reports **stocks** — total tokens in a session, total result bytes per tool. Stocks are billing-shaped; they're terrible for diagnosing live multi-agent work. **Flow rates** (tokens/min, tool-calls/min, reads/min) and the **graph structure** of fan-out are what reveal whether a team is healthy or thrashing.

### What this becomes
- **Token velocity per agent.** A subagent burning 40k tok/min is in a re-read loop or DOM-dump loop. A subagent at 200 tok/min is making real progress. The number to alert on isn't total — it's the slope.
- **Fan-out as a real graph.** Treat the parent/child topology as a DAG. Compute: branching factor, depth, redundancy (siblings reading the same files), critical path (longest dependent chain). These are the actual unit of multi-agent work.
- **Compounding factor as a first-class KPI.** `total_subagent_tokens / parent_useful_tokens`. >4× is the headline number for the budget meeting; lens makes it computable per session, per project, per engineer.
- **Graph-level diagnoses.** Today's rules fire on single tool calls (oversized Read). Graph rules fire on *patterns*: "three sibling subagents read the same five files" → `recommend: crawfish-opt-codebase`. "Parent re-spawned the same Explore subagent four times in 10 minutes" → `recommend: refactor agent definition`.
- **Live throughput strip in dash.** Sparklines for in-flight sessions: tok/min, tools/min, active subagent count. The thing the platform engineer leaves on a second monitor.

### Where it plugs in
- **lens** grows a `FlowStats` reduction next to `SessionStats`. Same JSONL input, time-bucketed.
- **lens** SSE stream emits flow deltas, not just file-change pings.
- **dash** Sessions tab gains a topology graph view (sibling to the existing list).
- New diagnosis category: **graph rules** in `crawfish-lens/src/rules/graph/`.

### Open questions
- What's the right time bucket — 30s windows, or per-tool-call deltas? Probably both, but the default matters.
- Is the topology graph a separate tab or an overlay on Sessions? Overlay keeps the surface count down.

---

## 2. Preparing codebases for multi-agent work

### The idea
Most fan-out waste isn't the agent's fault — it's that the codebase wasn't *prepared* for an agent. A repo with no top-level map, no naming conventions, and no module boundaries forces every subagent to re-derive structure from scratch. That re-derivation is the 4-5× compounding.

The intervention is a one-time **"prepare this codebase for crawfish"** pass that produces durable artifacts agents can read cheaply.

### What this becomes
A new tool / mode (working name: **`crawfish prep`**) that, run once per repo, generates:
- **`.crawfish/map.md`** — top-level architecture summary, ~2k tokens, hand-editable. Read once per session by the parent agent; subagents inherit a pointer instead of re-deriving.
- **`.crawfish/index.json`** — module → file → top-level decls, pre-computed. Backs `codebase_overview` / `codebase_outline` without per-call cost.
- **`.crawfish/conventions.md`** — naming, layout, "where does X live" answers, distilled from `git log` + actual file structure.
- **`.crawfish/hot-paths.json`** — the 20 files most often touched together (from `git log` co-change). When a subagent opens one, it knows what's likely next.
- **`.crawfish/agents/`** — recommended subagent definitions tuned to this repo. A monorepo gets different defaults than a single-package library.

The prep tool runs locally, uses Haiku for summarization (same engine as `crawfish-opt`), and is **idempotent** — re-run it after a refactor and it diffs the artifacts.

### Why this is product, not just a script
- It's the obvious upsell from optimizers. `crawfish-opt-codebase` makes individual reads cheap; `crawfish prep` makes the *whole repo* cheap.
- It's a natural team rollout vehicle: platform engineer runs prep, commits `.crawfish/`, every engineer's agents get cheaper overnight without installing anything.
- It's measurable: lens can A/B sessions on a repo before vs after prep.

### Where it plugs in
- New repo: **`crawfish-prep`** (sixth submodule), or a subcommand of `crawfish-opt-codebase`. Lean toward subcommand to avoid surface sprawl.
- **dash** gets a "Prep this repo" button in the Optimizers or a new **Codebase** tab.
- **lens** diagnoses gain `recommend: run crawfish prep` when graph rules detect repeated re-derivation.

### Open questions
- Does `.crawfish/` belong in the repo (committed) or in `~/.crawfish/repos/<hash>/` (per-machine)? Committed wins for team rollout but raises review-noise concerns.
- How aggressive should auto-refresh be? Watch mode is probably wrong (rebuild storms); a `pre-commit` hook is probably right.

---

## 3. Individual agent "journeys"

### The idea
Today lens shows tokens-per-tool. That's a histogram. What it should show — what platform engineers actually want to look at — is a **timeline of one agent's journey**: every tool call in order, how it branched, where it got stuck, where it succeeded.

A journey is the Gantt-chart-shaped artifact that lets a human go *"oh, that's why this session cost $40."*

### What this becomes
- **Journey timeline view.** Horizontal axis = time. One swimlane per agent (parent + each subagent). Each tool call is a block — width = duration, color = tool, height = result-byte cost. Stuck → dense vertical stack of repeated calls. Productive → clean stride.
- **Reasoning overlay.** Toggle to show assistant text turns inline as tooltips. Now the journey isn't just *what the agent did* but *what it was thinking when it did it*. (Reasoning text already in JSONL; not currently surfaced.)
- **Web overlay.** When a journey involves `crawfish-opt` browser calls, show the actual page state at each step — the zone summary, the chosen element, the action. The browser becomes part of the timeline, not a black box.
- **Replay scrubber.** Drag a cursor across the timeline; the right-pane shows the agent's context window as it existed at that moment. Lets a human reconstruct *why* the agent made a given decision without re-reading the whole transcript.
- **Journey diff.** Two sessions that solved the same task — show their journeys side by side. The cheap one and the expensive one. This is the artifact that turns "we should optimize" into "look at exactly where they diverged."

### Pattern detection on journeys
This is where the next wave of diagnosis rules lives:
- **Re-read loops** — same `Read(path)` ≥3× in a session. Recommends `crawfish-opt-codebase` *with the specific path that's being re-read*.
- **Grep-then-read storms** — `Grep` followed by ≥5 `Read` calls within 30s. Recommends `codebase_search` (returns previews so most reads become unnecessary).
- **DOM oscillation** — repeated `browser_navigate` to the same URL. Likely the agent didn't realize state was cached; recommend `browser_state`.
- **Subagent thrash** — parent spawns the same Agent type ≥3× in 5 minutes. The agent definition is probably wrong.
- **Context-window panic** — token velocity spikes ~80% of context window. The agent is about to compact and re-establish. Pre-empt with a checkpoint.

These rules are valuable on their own; together with the journey view they're a debugger.

### Where it plugs in
- **lens** new endpoint `/api/sessions/:id/journey` — returns the time-ordered event list with reasoning attached.
- **dash** Sessions tab gains a Journey detail view (and the topology overlay from §1 is its sibling).
- New rule directory `crawfish-lens/src/rules/journey/`.
- Replay scrubber needs a cheap context-reconstruction algorithm — replay the JSONL up to time T. Bounded work; fine for sessions up to ~1k turns.

### Open questions
- Reasoning text is sometimes long. Truncate aggressively in the timeline tooltip and link to a dedicated reasoning pane?
- Journey diff needs an alignment heuristic. Tool-call sequence alignment (Smith-Waterman style) is overkill; simple "first divergent tool call" is probably enough for v1.

---

## 4. Setup wizards

### The idea
Today crawfish has three install surfaces — lens, dash, optimizers — each with its own README. The desktop app papered over the boot sequence; nothing has papered over the *configuration* sequence. A new user installs the app, opens it, and faces empty tabs and no policy.

A wizard is the difference between "powerful platform" and "thing my team will actually adopt."

### What this becomes
Three wizards, ordered by user maturity:

**(a) First-run wizard — "what does crawfish see?"**
- Detects `~/.claude/projects/` (or fails gracefully).
- Imports the most recent week of sessions.
- Computes the user's personal compounding factor and shows it as a number with context: *"Your team is at 4.2× — typical for this size. Top sink: Read on `src/lib/`."*
- Offers one action: install `crawfish-opt-codebase` (copy-to-clipboard).
- Closes with: *"Lens will keep watching. Open dash anytime."*

**(b) Policy wizard — "set up enforcement for your team"**
- Aimed at the platform engineer.
- Walks through three questions: (i) what tools are most expensive in your last 30d? (ii) which of those should warn / block / log-only? (iii) which optimizer should each route to?
- Outputs a `policy.json` and a one-line install command for engineers (`crawfish-dash install-hooks --policy <url>`).
- Critically: shows a **dry-run preview** — *"if this policy had been live last week, it would have saved 3.4M tokens across 12 sessions."* That number is the sale.

**(c) Codebase prep wizard — "prepare this repo for agents"**
- Wraps `crawfish prep` (§2) in a UI.
- Detects monorepo vs single-package, suggests defaults.
- Lets the user review and edit the generated `.crawfish/map.md` before committing.
- One-click "create PR" if `gh` is configured.

### Where it plugs in
- **dash** owns all three wizards. New `/wizard/:name` routes.
- Wizards are stateless — they read on-disk state, ask questions, write on-disk state. No DB.
- The first-run wizard auto-launches when dash detects no prior session view.

### Open questions
- Should the first-run wizard run inside the Tauri app on first launch or be triggered by visiting dash? Tauri-side feels heavier-weight; web-side keeps wizards portable.
- Policy wizard's "dry-run preview" requires replaying past tool calls against a candidate policy — this is real engineering, not just UI. But it's also the entire pitch.

---

## 5. Host OpenClaw (and friends) locally — orchestrator distribution

### The idea
Today crawfish is Claude-Code-native: it reads `~/.claude/projects/`, installs hooks into `~/.claude/settings.json`, and speaks Claude Code's transcript schema. **OpenClaw** (and similar open multi-agent runtimes) are the obvious next surface — same fan-out problem, no incumbent observability, and the projects often *want* an opinionated org-level setup but ship as raw libraries.

This idea has two halves:

**(a) "Orchestrator-as-a-product" — host OpenClaw locally, configured for your org.**
The way Claude Code works — one binary, opinionated defaults, transcripts on disk — is an artifact of Anthropic owning the runtime. OpenClaw doesn't have that luxury; it's a framework. Crawfish can wrap it: bundle OpenClaw + a sane default config + the lens hook + a policy bundle into a single `crawfish-orchestrator` daemon. A platform engineer runs `crawfish orchestrator init` and gets:
- A locally-running OpenClaw instance bound to `127.0.0.1`.
- Pre-wired transcript writes to `~/.crawfish/openclaw/sessions/*.jsonl` in lens's schema.
- The same PreToolUse hook contract (translated to OpenClaw's middleware shape).
- The same policy bundle from `~/.crawfish/policy.json` enforced consistently.

This is what makes "crawfish supports OpenClaw" a real product instead of a checkbox.

**(b) "Bring-your-own-runtime" — multiple agent backends behind one platform.**
Dash gains a runtime selector: Claude Code (default), OpenClaw (hosted-locally), Cursor agent mode, custom Anthropic-SDK app. Each runtime has an **adapter** in lens (per `INTEGRATIONS.md`'s pattern) that produces the same internal `SessionStats` + `JourneyEvents`. The user-visible surface is identical regardless of runtime.

This is the move that converts crawfish from "Claude Code observability" to "the multi-agent platform layer." It also neutralizes the single-platform-dependency VC objection without rewriting the core.

### Setup wizard for OpenClaw specifically
The wizard is the wedge. Today, standing up OpenClaw for an org takes a day of YAML wrangling and a custom transcript layer. The crawfish wizard:
1. Pulls OpenClaw at a pinned version.
2. Asks three questions: which models can your team use, what's your context-window budget, which optimizers are pre-installed?
3. Generates a config + a `docker-compose.yml` (or a launchd plist on macOS) and starts the daemon.
4. Verifies lens sees its first transcript within 30s.
5. Outputs a one-page "what you got" summary.

That wizard is worth a real evening of engineering — it's the moment OpenClaw stops being a library and starts being your team's runtime.

### Where it plugs in
- New repo: **`crawfish-orchestrator`** (sixth or seventh submodule). Owns the daemon + adapter wiring.
- **lens** grows `crawfish-lens/src/adapters/openclaw.ts` per the existing INTEGRATIONS spec.
- **dash** gains a **Runtime** selector and a "deploy orchestrator" wizard (§4c sibling).
- The optimizer contract is unchanged — MCP works for both runtimes.

### Open questions
- Hosted-locally OpenClaw competes with running OpenClaw yourself. The wedge is the *defaults* and the *integrated observability*, not the runtime. Make sure the docs are honest about what crawfish adds vs. what's just OpenClaw.
- How opinionated should the bundled config be? Too generic and it's not worth running through crawfish; too opinionated and orgs reject it. Probably ship 2-3 named profiles ("solo dev", "platform team", "research") rather than one config.
- Is this a separate paid tier? Plausibly. The orchestrator-as-a-product wedge is the first thing in the platform that materially saves an engineering day per team.

---

## 6. Plug into analysis tools

### The idea
Crawfish's data is valuable *outside* dash. Engineers already live in Grafana, Datadog, Linear, Slack, Notion, custom BI. Today they'd have to write a transcript scraper themselves; crawfish should expose its reductions as a clean integration surface.

This is **not** "ship to a hosted SaaS." It's "make the local data easy to ship anywhere the *user* chooses."

### What this becomes
**(a) Stable JSON API.** Lens already has `/api/sessions/*`. Document it, version it, add a `/api/v1/` prefix, publish a JSON schema. This is what every other integration depends on.

**(b) Prometheus exporter.** Lens exposes `/metrics` in Prometheus format: `crawfish_session_tokens_total`, `crawfish_compounding_factor`, `crawfish_policy_decisions_total{action="block"}`. Drop into any existing observability stack.

**(c) Grafana dashboards.** Pre-built JSON dashboards a platform engineer imports. Three to start: "team weekly spend", "compounding factor over time", "policy compliance".

**(d) OpenTelemetry traces.** Each agent journey is a trace; each tool call is a span; reasoning is a span event. This is the form that plugs into Datadog / Honeycomb / Tempo without per-tool work. **High-value, medium-effort** — the standard wins here.

**(e) Webhook / event stream.** Subscribe to `policy.block`, `diagnosis.flagged`, `session.complete` events. A platform team can wire `policy.block` into Slack ("Crawfish blocked an oversized DOM dump in @engineer's session — saved 18k tokens").

**(f) BI export.** Nightly dump of `~/.crawfish/data/*.parquet` so analytics teams can query token spend in their warehouse. Local file, user copies it where they want.

**(g) Linear / Jira integration.** A diagnosis with `severity: high` can open a ticket: *"Repo `foo` is at 5.2× compounding, 80% from re-reads in `src/lib/`. Recommend running `crawfish prep`."* Closes the loop from observation to engineering work.

### What we explicitly don't ship
- A hosted dashboard. (Anti-goal in PRODUCT.md.)
- An auto-pusher to vendor SaaS. The user picks the destination; crawfish exposes the data.

### Where it plugs in
- **lens** owns the JSON API, Prometheus exporter, OTel exporter, webhook bus.
- **dash** has an **Integrations** tab listing available exporters and their config (mirror of marketplace UI).
- New small repo or subdirectory: `crawfish-integrations/grafana/*.json`, `crawfish-integrations/linear/`, etc. PR-driven, not a framework.

### Open questions
- OTel is the highest-leverage single integration but the design needs care — what's a span vs. an event vs. a metric? Worth a separate design doc before code.
- Webhook delivery from a local-first tool is awkward (the user's machine isn't always online). Probably ship a queue + best-effort delivery rather than guaranteed.

---

## 7. New optimizers + policy rules — token-discipline wave

### The idea
The C1 optimizer line (`crawfish-opt`, `crawfish-opt-codebase`) addressed the two most-cited sinks: browser DOM and codebase navigation. Field research on what 2025-2026 agentic coding setups actually burn tokens on points to a different, larger sink: **context discipline** — stale tool_use/tool_result pairs accumulating across turns, MCP tool schemas re-sent every turn, huge tool payloads pasted inline, subagents re-paying the system-prompt bill on every spawn.

These aren't addressed by smarter Reads or smarter browsers. They're addressed by *wrapping the things the runtime already does badly* and turning each into an observable, policy-driven surface.

### What this becomes

Seven candidate optimizers, ranked by leverage:

1. **`crawfish-opt-context`** — managed proxy in front of Anthropic's `clear_tool_uses_20250919` context-editing beta. Per-tool TTLs, exclude-from-clear lists, every clear logged to lens. Anthropic's own number: **84% reduction on a 100-turn web-search eval.** OpenHands' equivalent condenser cut cost ~50% and converted quadratic→linear scaling. The wrapper is the product — the beta exists, but using it raw silently drops load-bearing context. Crawfish makes it observable and reversible.
2. **`crawfish-opt-artifact`** — durable-reference returns. Tools producing big payloads (test logs, web fetches, DB dumps, screenshots) write to `~/.crawfish/artifacts/<id>` and return `{artifact_id, summary, next_action}`. Pairs with §7.1 — together they're the "stop silently dropping context" story. Maps to MCP `_meta` persistence + `anthropic/maxResultSizeChars`.
3. **`crawfish-opt-mcp-shrinker`** — proxy that lazy-loads other MCP servers' tool schemas. `list_tools` returns names + one-liners; full JSON-Schema fetched on demand. Atlassian measured **70-97% bloat** in re-sent tool definitions. Highest cross-stack leverage of the bunch — benefits every MCP server in the user's environment, not just crawfish's own.
4. **`crawfish-opt-fork`** — fork-aware subagent spawner. Collapses N parallel `cache_control` markers into a single trailing breakpoint; prefers forked subagents reusing parent prompt cache. ProjectDiscovery measured **59% savings** from this alone. Maps cleanly to the compounding-factor KPI (§1) — this is the optimizer that *moves* the headline number.
5. **`crawfish-opt-logs`** (already on roadmap C2.P4 — promote priority) — streaming tail+head+error-extraction filter for `npm test`, `cargo build`, stack traces, `kubectl logs`. LLMLingua-2 optional for prose-y output. The journey rule `log-truncation-pattern` already in C2.P1's catalog points straight at this.
6. **`crawfish-opt-codebase` v0.2 mode: repomap** — Aider-style tree-sitter symbol map, PageRank-ranked, token-budgeted. Cursor's "dynamic context discovery" version A/B'd at **46.9% total agent token reduction.** Subcommand of the existing optimizer, not a new submodule.
7. **`crawfish-opt-toon`** — format-shifter for tabular tool returns (DB rows, `ls`, search hits). Convert uniform records to TOON before they hit context: **30-60% input-token reduction.** Tiny utility, ship inside an existing optimizer rather than as its own server.

### New policy rules

These plug into the existing `crawfish-hook` PreToolUse contract and extend the C2.P1 diagnoses catalog. Format: detect → action → recommends.

| Detect | Action | Recommends |
|---|---|---|
| `Read` >800 lines without prior outline call | block | `codebase_outline` |
| Same file `Read` ≥3× in session, no Edit between | warn | `crawfish-opt-codebase` (extends the existing `re-read-loops` rule with a pin-suggestion) |
| `cat`/`head`/`tail` of build/test logs >5KB | rewrite | `crawfish-opt-logs` |
| `WebFetch` returning >20KB | rewrite | `crawfish-opt-artifact` |
| Bash `grep -r` / `find /` over tracked dirs | warn | `codebase_search` |
| Parallel subagent fan-out >3 with overlapping file reads | block | shared artifact or single agent |
| MCP tool schema >2KB on registration | route | `crawfish-opt-mcp-shrinker` |
| Tool returning JSON array >50 rows | rewrite | `crawfish-opt-toon` |
| Old tool_use/tool_result pairs accumulated >N | trigger | `crawfish-opt-context` clear |
| `npm install` / `pip install` inside agent loop | block | rarely useful in-context, payload is huge |
| CLAUDE.md edit pushing file >200 lines | warn | Anthropic's own guidance |
| `cache_control` marker on a fan-out tool message | rewrite | collapse to last-message-only (§7.4) |

### Things that look promising but probably don't pencil out

Worth recording so they don't get re-litigated:

- **Pure LLMLingua-1 on source code** — built for prose, mangles identifiers. v2 is better but still risky on source. Restrict to logs/docs only.
- **Embeddings wholesale replacing grep** — Augment and Anthropic both found grep wins on small/medium repos. Ship semantic search as a *complement*, not a replacement. An optimizer that always wins is a feature; one that sometimes loses is a footgun.
- **Aggressive auto-compaction mid-task** — silent context drops make agents "lie." The artifact-id indirection (§7.2) is the safer answer: drop the bytes, keep the handle.
- **Forcing structured JSON during reasoning** — 10-15% accuracy hit. Format at the boundary, not mid-thought.
- **65-tool "token optimizer" grab-bags** — adding 65 tool schemas often costs more than it saves. Keep each crawfish optimizer narrow per the contract.

### Strategic note

§7.1 + §7.2 form a **context-discipline pair** that wraps an Anthropic beta everyone else is fumbling. That's exactly the crawfish positioning: turn a vendor footgun into an observable, policy-driven feature. §7.3 is the third pick because it benefits the user's *entire* MCP stack — which gives crawfish a wedge into every team that's already adopted MCP for non-crawfish reasons.

### Where it plugs in
- **lens** ships the new diagnosis rules in `crawfish-lens/src/diagnoses/rules/` (extends the C2.P1 catalog without changing the registry contract).
- **dash** Optimizers tab marketplace gains entries for the new servers; Policies tab gains the new rules as defaults.
- **`crawfish-opt-context`**, **`crawfish-opt-artifact`**, **`crawfish-opt-mcp-shrinker`**, **`crawfish-opt-fork`** — each a new submodule following the contract in [PRODUCT.md § The optimizer contract].
- **`crawfish-opt-logs`** — already in roadmap (C2.P4); promote ahead of `crawfish-opt-search`.
- **repomap + TOON** — modes inside `crawfish-opt-codebase`, not new submodules. Avoids surface sprawl.

### Open questions
- Sequencing: ship `opt-context` + `opt-artifact` together (the pair sells the story) or `opt-mcp-shrinker` first (lower scope, broadest benefit)? Probably the pair, with shrinker as the next deliverable.
- The `cache_control` collapse rule (§7.4 + the matching policy) requires inspecting outgoing prompts, not just tool calls — this is a different hook surface than PreToolUse. May need a new hook point or a wrapper at the SDK adapter layer (C2.P3 territory).
- `opt-context` overlaps semantically with the runtime's own compaction. Need a clear story for "when does crawfish's clear fire vs the runtime's auto-compact" — probably: crawfish runs first with policy-driven precision, runtime auto-compact is the safety net.

---

## How these connect

These six aren't independent features — they reinforce each other:

```
[6. Analysis tools]   <-- export the data anywhere
       ▲
       │
[3. Agent journeys] <-- the unit of analysis
       ▲
       │
[1. Flow + graph]   <-- the reductions over journeys
       ▲
       │
[2. Codebase prep]  <-- intervention before the journey starts
       │
[5. Orchestrators]  <-- multi-runtime substrate
       │
[4. Setup wizards]  <-- the on-ramp that makes any of this adoptable
```

Read top-down: every analysis sits on top of journeys, journeys come from runtimes, runtimes need on-ramps. Read bottom-up: wizards adopt orchestrators, orchestrators emit journeys, journeys reduce to flows + graphs, flows + graphs export to wherever the team already lives.

The ordering for a credible 2026 Q3 plan is probably: **§3 journeys → §1 flow/graph → §6 OTel + JSON API → §4 first-run wizard**. Each step makes the next one cheaper. §2 (prep) and §5 (orchestrators) are bigger bets, gated on the first four landing well.

§7 (token-discipline optimizers) is **orthogonal** to the §1-6 stack — it ships against the existing optimizer + policy surface, doesn't depend on journeys/flow/wizards, and can land in parallel. Slot the highest-leverage pair (`opt-context` + `opt-artifact`) into C2.P4 (or earlier as a sidecar to C2.P1's diagnoses work, since the new policy rules need somewhere to recommend *to*).

---

## Decisions

**Pricing & posture (2026-05-08):** Stay **free and local-first** for now. Everything in this doc ships MIT, runs on `127.0.0.1`, and assumes a single-machine user. Pricing is a later move once adoption is real; the candidate paid tiers when that time comes are team-mode aggregation (§5b multi-engineer rollups) and the hosted orchestrator (§5a deployment shape) — not the solo experience.

This decision cascades into the open questions below:

- **§5 audience** → **solo engineer first.** Build the single-machine OpenClaw bundle (launchd, sqlite, no auth). Team-mode deployment is the future paid product, not a v1 surface.
- **§2 prep artifacts** → lean **in-repo (committed `.crawfish/`)**. Free + local makes the team-rollout play viable without server infra; commit-to-share is the cheapest distribution mechanism we have.
- **§6 OTel vs Grafana** → lean **OTel first.** Open standard fits the local-first posture better than vendor-shaped Grafana JSON; users already running observability stacks get value without crawfish hosting anything.

## Open questions

Still worth pinning down, but not gating:

- **§3 reasoning overlay default.** Show reasoning text inline on journeys by default, or behind a toggle? Local-first posture leans *on by default* (it's all on your machine), but enterprise conversations later may flip this.
- **When does pricing actually start?** Trigger is probably "first team that asks for multi-engineer aggregation we don't already have." Not a date — a signal.
