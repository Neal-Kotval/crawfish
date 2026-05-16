# Agent runtime integrations

> Crawfish today is Claude-Code-native. This doc lists the runtimes worth integrating with, the integration shape for each, and the priority order. Ordered by realistic leverage, not alphabetically.

## Why integrations matter

The biggest VC pushback on crawfish is **single-platform dependency** — *"if Anthropic changes their transcript format, you die."* Each additional runtime adapter neutralizes that question and expands the addressable market without changing the core lens / dash / opt architecture. Multi-runtime is also a moat (see [`ROADMAP.md` § 0b — Edge 2](./ROADMAP.md)).

The data layer is already runtime-agnostic. What's runtime-specific is:

1. **Transcript shape** — where are turns / tool calls / token usage stored on disk
2. **Tool-call interception** — does the runtime expose pre-tool hooks (like Claude Code's `PreToolUse`) or middleware
3. **MCP support** — can our optimizers be installed without runtime-specific glue
4. **Configuration distribution** — where does the runtime read its tool / model / agent config

A runtime is **integratable** if at least #1 and #3 are addressable. The other two strengthen the product but aren't gating.

---

## Integration patterns

Each runtime gets ranked across five integration depths, cheapest to most invasive:

| Pattern | What it does | Crawfish surface affected |
|---|---|---|
| **Transcript adapter** (passive) | Read the runtime's local session files; surface in lens. | `crawfish-lens/src/adapters/<runtime>.ts` |
| **MCP consumption** (existing) | Runtime supports MCP → our optimizers work as-is. | None — the runtime does the work. |
| **Hook injection** (active enforcement) | Runtime exposes pre-tool hooks; install crawfish-hook. | Per-runtime `install-hooks` command in dash. |
| **SDK wrapper** (deepest cooperation) | Runtime imports a crawfish library to emit topology spans. | A new `@crawfish/sdk` package. |
| **Proxy interception** (most aggressive) | Sit on the wire between runtime and model API. | A new `crawfish-proxy` daemon — separate product. |

For a v1 integration the pattern usually goes *transcript adapter → MCP consumption* (covers ~80% of the value). Hook injection is the team-mode upsell. SDK and proxy are the longer plays.

---

## Target runtimes

Sorted by **leverage × ease**, not popularity. Numbers are honest engineering estimates, solo evening pace.

| Runtime | Audience size | Pattern fit | Engineering effort | Priority |
|---|---|---|---|---|
| **Claude multi-agent teams** | growing fast (Claude Code native) | transcript adapter + topology | ~2-4 days | **High** — already in our wheelhouse; the `team_name` fan-out is exactly the topology view's killer demo. |
| **OpenClaw** | small but motivated | transcript + MCP | ~3-5 days | **High** — the user is local-first OSS-aligned, exactly our buyer. |
| **LangGraph** | large + enterprise | SDK + transcript | ~1-2 weeks | **High** — token compounding shines on multi-step graphs. |
| **Aider** | medium, terminal-first | transcript only | ~2-3 days | Medium — small daily-active dev cohort that loves OSS tools. |
| **Cline / Roo Code (VS Code)** | large + growing | transcript adapter | ~3-5 days | Medium — free distribution via marketplace. |
| **Cursor (agent mode)** | very large | transcript only (closed) | unclear | Low — Cursor is closed-source, log access uncertain. |
| **Continue.dev** | medium | SDK or proxy | ~1 week | Medium — open-source coding agent, friendly extension surface. |
| **Mastra** | small but technical | SDK | ~3-5 days | Medium — TypeScript-first, friendly to tooling integrations. |
| **AutoGen (Microsoft)** | large in research | SDK | ~1-2 weeks | Medium — multi-agent fan-out is their bread and butter; perfect topology fit. |
| **CrewAI** | growing fast | SDK | ~1 week | Medium-high — multi-agent native, popular in product-y use cases. |
| **OpenHands (formerly OpenDevin)** | medium, OSS | transcript + SDK | ~1 week | Medium — autonomous coding agent, runs locally, fan-out heavy. |
| **Goose (Block)** | small + OSS | transcript + MCP | ~3-5 days | Low-medium — strong technical alignment but small audience today. |
| **Vercel AI SDK** | huge | SDK | ~1 week | Low (today) — most users build short-lived agents; less compounding pain. |
| **Anthropic Computer Use direct API** | small + early | proxy | ~2 weeks | Low — early audience, our hook model doesn't naturally apply. |

---

## Claude multi-agent teams — the lowest-friction win

Claude Code's Agent tool exposes a `team_name` parameter that lets the parent spawn subagents into named teams, with cross-team coordination via `SendMessage`. From a topology standpoint this is the single richest fan-out shape we'll see in the wild — multiple named agents, persistent IDs, sometimes long-running, sometimes coordinating laterally rather than strictly parent → child.

**Pattern fit:** transcript adapter (passive, already 90% there) + topology view extension.

The transcripts already land in `~/.claude/projects/<project>/*.jsonl` — same path crawfish-lens already reads. What's missing:

1. **Team-aware grouping.** Today's topology view assumes one parent + a flat row of subagents. Teams introduce a second level: parent → team → agents. The radial layout we just shipped extends naturally — render team boundaries as concentric arcs or color-coded sectors.
2. **`SendMessage` edges.** Cross-agent messages are *lateral* edges, not tree edges. The graph layout needs to handle them without the radial assumption breaking. Probably: dotted edges between sibling nodes, drawn last so they don't dominate the parent → child fan-out.
3. **Long-running agent state.** Background agents (`run_in_background: true`) outlive the turn that spawned them. Lens needs to surface "still running" vs "completed" state — token totals are a moving target until the agent terminates.

**Engineering:** ~2-4 days. The adapter work is minimal because we already parse the transcripts; the lift is the topology view extensions and a "Teams" subsection in dash that mirrors the existing Agents tab.

**Why this is priority 1, not OpenClaw:** the data is *already* in the lens. We're the only ones who can ship this without leaving our existing audience. Every Claude Code user who runs multi-agent teams becomes a free demo for the topology view. OpenClaw is still the biggest *new-audience* opportunity, but Claude teams is the biggest *existing-audience* depth play.

---

## OpenClaw — the highest-priority new-audience integration

[OpenClaw](https://openclaw.ai/) ([github.com/openclaw/openclaw](https://github.com/openclaw/openclaw)) is Peter Steinberger's open-source local agent runtime. Personal AI assistant framework, persistent memory, 50+ skills, runs as a launchd daemon, MCP-aware, model-agnostic (Claude or GPT). It's the closest fit to crawfish's audience: **local-first, OSS-aligned, multi-skill (≈ multi-agent), already MCP-fluent.**

OpenClaw users running through Claude Code already get crawfish coverage indirectly — Claude Code's PreToolUse hook fires on the OpenClaw MCP's tool calls, and lens reads the resulting transcript. So the **easy 80%** is already there for users who orchestrate via Claude Code.

For users running OpenClaw skills directly through the gateway (port 18789), there's a real integration job:

### OpenClaw runtime model (what we need to read)

- **Daemon:** `openclaw gateway --port 18789` runs as a user-level launchd service.
- **Workspace:** `~/.openclaw/workspace/` — this is the data layer.
- **Skills:** `~/.openclaw/workspace/skills/<skill>/SKILL.md` — markdown with frontmatter, plus `AGENTS.md` / `SOUL.md` / `TOOLS.md` for prompt injection. Equivalent in shape to Claude Code's `~/.claude/agents/*.md`.
- **Sessions:** session transcripts and logs almost certainly live under `~/.openclaw/workspace/` somewhere, but exact format isn't documented in the public README. Needs reverse-engineering — same approach we used for Claude Code's `~/.claude/projects/*.jsonl`.
- **Tool families:** `bash`, `process`, `read`, `write`, `edit`, `sessions_list`, `sessions_history`, `sessions_send`, `sessions_spawn`. The `sessions_*` family is direct evidence of multi-agent fan-out — exactly the pattern crawfish's topology view targets.

### Integration phases

**Phase 1 — transcript adapter** (~2-3 days)
Reverse-engineer OpenClaw's session storage. Add `crawfish-lens/src/adapters/openclaw.ts` with the same shape as `transcript.ts` but reading OpenClaw's format. Lens's Sessions tab now shows OpenClaw sessions next to Claude Code sessions. Topology view works the same way for OpenClaw skill fan-out.

**Phase 2 — Skills tab in dash** (~1-2 days)
Already partially scoped in `ROADMAP.md` — the dash Agents tab gains an "OpenClaw skills" subsection that lists `~/.openclaw/workspace/skills/<skill>/SKILL.md` files, parses frontmatter, lets you create / edit / delete (mirroring the existing Claude Code subagent CRUD).

**Phase 3 — Hook injection** (~3-5 days)
This is the unknown — OpenClaw's documentation doesn't expose a `PreToolUse`-equivalent hook. If one exists (or if the project would accept a PR adding one), install crawfish-hook the same way we do for Claude Code. If not, fall back to either:
- **Proxy mode** (sit between OpenClaw gateway and the model API), or
- **Skill-level guidance** (publish a `crawfish-policy` SKILL.md that lives in the workspace and warns the agent in-prompt about expensive patterns — softer enforcement, no hook required).

### Specific assets we already have

- `~/.claude/projects/-Users-nealkotval--openclaw-workspace/` exists locally — direct evidence the user has run OpenClaw via Claude Code. The `mcp-logs-openclaw/` directory under `~/Library/Caches/claude-cli-nodejs/` proves OpenClaw runs as a Claude Code MCP server. So we already have real session data to test the adapter against.
- The user's `crawfish-dash` Agents tab is already designed with a "tabs by runtime" structure in mind ([dash plan in `ROADMAP.md` § P2](./ROADMAP.md)).

### Outreach angle

Steinberger is the kind of OSS-aligned developer who responds to specific PRs, not pitch decks. The right introduction is: ship the transcript adapter publicly, post a GIF of the topology graph showing his own OpenClaw session's skill fan-out, and *then* DM him with "we made this; thoughts on a hook API?" Showing > telling.

---

## LangGraph — the highest enterprise leverage

[LangGraph](https://github.com/langchain-ai/langgraph) is the agent orchestration framework most large orgs are already shipping in production. The audience is enterprise AI infra teams — exactly the Tier 2 buyer crawfish wants.

**Pattern fit:** SDK + transcript adapter.

LangGraph emits trace events through LangSmith by default, but supports custom callback handlers. The integration is:

1. Publish `@crawfish/langgraph` (npm + PyPI).
2. The package ships a `CrawfishCallbackHandler` that emits **topology spans** in the same OpenTelemetry-compatible format we publish from the lens (see Edge 1 in `ROADMAP.md`).
3. Users add one line to their LangGraph app: `graph.add_callback_handler(CrawfishCallbackHandler())`.
4. lens reads the spans (either from a local sink or from a self-hosted aggregator) and renders the same topology view we already have for Claude Code.

Strategic note: **shipping a LangGraph adapter forces us to commit to Edge 1 (topology spans as a standard).** The two are the same project. That's a feature — it pulls a moat-defining decision into the work.

---

## Aider — fastest credibility win

[Aider](https://aider.chat/) writes its full chat transcripts to `.aider.chat.history.md` and `.aider.chat.history.json` in the project root by default. Adapter is one file, ~150 lines.

Pattern: transcript adapter only. No hook injection (Aider has no equivalent). MCP is unsupported, so optimizer line doesn't apply.

The pitch is *"observability, not enforcement"* — but Aider users are exactly the kind of OSS-friendly hackers who'd star the repo and tweet a screenshot.

Engineering: ~2-3 days. Perfect "weekend project" to ship alongside the Tier 1 npm publish for distribution velocity.

---

## VS Code extensions (Cline, Roo Code, Continue)

Cline (formerly Claude Dev), Roo Code, and Continue all run as VS Code extensions. Each writes its session state into `~/Library/Application Support/Code/User/globalStorage/<extension-id>/` (macOS).

Pattern: transcript adapter per extension. There's no shared format — each is bespoke.

Engineering: ~3-5 days **per extension** because the formats differ. Reasonable order: Cline first (largest user base), then Continue, then Roo Code. Each one is a small lift but compounding distribution. VS Code marketplace presence + a `crawfish-cline-adapter` repo gets us free SEO from each extension's docs.

---

## What's deliberately NOT on the list

- **Cursor.** Closed-source, no published log format, ToS questions about scraping. Revisit if/when they publish a transcript spec.
- **Replit Agent / Bolt.new.** Hosted services with no local data layer. Doesn't fit the local-first wedge.
- **Gemini CLI / OpenAI Assistants.** Different model providers. Crawfish's optimizer line is currently Anthropic-shaped (the `tokens_used` contract assumes Anthropic-style cache billing). Multi-provider is a v2 problem.
- **n8n / Zapier-style workflow tools.** Not "agents" in the multi-step LLM sense; the topology metaphor doesn't apply.

---

## Recommended sequence

If we have one builder and want to ship in this order:

1. **Claude multi-agent teams (topology v2)** — extends the radial graph to handle teams + lateral `SendMessage` edges. Zero new audience required; immediate demo lift for every existing user. ~2-4 days.
2. **OpenClaw transcript adapter** — fastest credibility with the OSS-aligned local-first audience that *is* our buyer. ~3-5 days.
3. **Aider transcript adapter** — second cheapest new-audience play, distinct distribution channel, drives GitHub stars. ~2-3 days.
4. **LangGraph + topology spans** — the moat-defining bet (forces us to publish Edge 1's open standard). ~1-2 weeks.
5. **Cline / Continue / Roo** — VS Code marketplace surface; spread distribution. ~1-2 weeks combined.
6. **OpenClaw hook injection or proxy** — if Steinberger is open to a PR, this is the team-mode upsell for OpenClaw users. Otherwise the soft-guidance SKILL.md path.
7. **CrewAI + AutoGen + Mastra** — the SDK family, after `@crawfish/sdk` is published.

Each step is independently shippable and produces a public artifact (a repo, a Show HN, a marketplace listing). The sequence is also a hedge — if any single integration flops, the next one is on a different audience and timeline.

---

## What this doc isn't

- A commitment. The roadmap (§ P3, P4, P5) still gates which of these get built when.
- An architectural spec. Each runtime gets its own design doc once it's actively scoped.
- A complete list. Adapter requests should land here as a PR with a one-paragraph rationale; runtimes that don't fit the local-first / multi-agent / token-compounding shape get rejected.
