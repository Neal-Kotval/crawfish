# Crawfish bench prompts — code review on this repo

Three multi-subagent code-review prompts targeting the crawfish repo itself. Designed to:

- Trigger fan-out (each prompt explicitly asks Claude Code to spawn 2-3 Explore subagents in parallel)
- Hit tools that crawfish-codebase optimizes (`Read` of multi-KB files, recursive `grep` via `Bash`)
- Be deterministic enough that two runs are comparable: same files, same expected behaviors, no external state

Run **all three in the same Claude Code session** for each side. Don't mix vanilla and optimized prompts in one session.

## Setup before each side

```bash
cd ~/crawfish

# Show me everything I have on this prompt set so I can re-read it during the run
cat bench/prompts.md
```

Then paste each of the three prompts below in order, waiting for each to fully complete before sending the next.

---

## Prompt 1 — three-way code audit of crawfish-lens

```
Audit the crawfish-lens TypeScript codebase for code quality issues.

Spawn 3 Explore subagents in parallel:
1. One to review the server layer (src/server/index.ts, src/server/api.ts, src/server/graph.ts, src/server/tail.ts, src/server/sse.ts, src/server/static.ts) — look for missing error handling, request validation gaps, race conditions in the SSE hub, and incorrect Content-Type/CORS handling.
2. One to review the data layer (src/transcript.ts, src/stats.ts, src/topology.ts, src/savings.ts, src/diagnoses/) — look for parser brittleness on malformed transcripts, off-by-one errors in aggregation, savings model assumptions that don't hold, and untested edge cases.
3. One to review the React frontend (web/src/App.tsx, web/src/routes/sessions.tsx, web/src/routes/session.tsx, web/src/components/Topology.tsx, web/src/components/Savings.tsx) — look for missing key props, useEffect deps issues, unhandled promise rejections, accessibility problems, and CSS class drift from the @crawfish/ui shared package.

Each subagent should report findings with file:line references. Aggregate the top three issues from each into a final summary.
```

---

## Prompt 2 — security audit of dash policy enforcement

```
Audit the dash policy enforcement layer for security and edge-case gaps.

Spawn 2 Explore subagents in parallel:
1. One to review crawfish-dash/src/policy/* — schema.ts, evaluator.ts, store.ts, hook.ts, install.ts. Look for: regex injection in match patterns, path-traversal risks in install.ts, log file growth without rotation in store.ts, hook crashes that could brick a user's Claude Code session, and missing validation on incoming PUT bundles.
2. One to review the Policies tab UI (crawfish-dash/web/src/routes/policies.tsx + AgentEditor.tsx). Look for: XSS risks in policy descriptions and user-supplied agent fields, missing confirmation prompts on destructive actions (delete agent, disable critical policy), state staleness when the bundle changes externally, and accessibility issues in the toggle controls.

Each subagent quotes vulnerable code snippets with file:line. Aggregate critical-vs-warning severity per finding.
```

---

## Prompt 3 — Benchmarks tab end-to-end review

```
Review the dash Benchmarks feature end-to-end and identify how to make the 13-scenario suite more compelling for a buyer.

Spawn 2 Explore subagents in parallel:
1. One to read crawfish-dash/src/bench/runner.ts in detail. Identify: scenarios that are weak proof points (negative or single-digit savings), gameable methodology (cherry-picked fixtures, biased thresholds), missing scenarios for token sinks we don't yet measure, and the cache amplification model in src/savings.ts.
2. One to read crawfish-dash/web/src/routes/benchmarks.tsx. Identify: missing visualization choices (per-tool stacked bars, time-series across runs, side-by-side optimizer comparison), the 'From your sessions' leaderboard's truthfulness, and what a non-technical stakeholder would actually understand on first look.

Aggregate into a numbered list of concrete improvements ranked by impact.
```

---

## After both sides

1. Open dash → **Compare** tab.
2. Side A picker → pick the vanilla session (the first run); rename label to `Vanilla`.
3. Side B picker → pick the optimized session; rename label to `+ crawfish-codebase`.
4. Read the headline (delta tokens, %), side-by-side panels (turns, cache hit, subagent counts), and per-tool delta table.

Honest expectations:
- Total tokens won't drop dramatically — most session cost is cached prefix.
- The big wins should land on `Read` and `Bash` byte deltas (where the optimizer routes things).
- Subagent count will likely match (same prompts → same fan-out plan); their *internal* tool usage is what differs.
