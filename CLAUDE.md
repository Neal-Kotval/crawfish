# Crawfish — agent-team conventions

This file is loaded by every Claude Code session in this directory and (via
`CLAUDE.md` propagation) every spawned teammate. It exists to keep parallel
work safe — i.e., to keep two teammates from overwriting each other's edits
when running in agent-team mode.

If you are a *single* Claude Code session (no team), most of this is
informational. If you are a *teammate* spawned by a lead, treat the file-
ownership rules below as binding.

---

## Multi-repo layout — cheap conflict avoidance

The umbrella holds five sibling submodules. **Each submodule is a natural
ownership boundary for one teammate.** When work fans out across submodules,
hand each teammate a single submodule path and don't let them edit anywhere
else.

```
crawfish/
├── ui/                    # shared design tokens + components (canonical CSS lives here)
├── crawfish-lens/         # transcript reader, REST API, server-side reductions
├── crawfish-dash/         # dashboard UI, proxies to lens, owns policies + benchmarks
├── crawfish-opt/          # browser optimizer (MCP server)
├── crawfish-opt-codebase/ # codebase optimizer
├── crawfish-app/          # Tauri shell that spawns lens+dash as children
└── crawfish-orchestrator/ # (future, C2.P3) OpenClaw bundle
```

Cross-cutting changes (e.g., a new shared CSS class in `ui/tokens/globals.css`
referenced by both lens and dash) are **lead-only** — never delegate them to
a teammate, because two teammates would each pull the change locally and
race. The lead lands the shared change, then spawns teammates against the
post-change tree.

---

## Files that two teammates must NEVER edit simultaneously

These are the registry / aggregator files where every fan-out item lands a
line. Edit conflicts here are the most common cause of lost work in agent-
team mode. **The lead owns these. Teammates request the line, lead writes
it.** (Or: each teammate finishes their feature file, then the lead does a
single sequential pass through the registries at the end.)

| File | Why it conflicts |
|---|---|
| `crawfish-lens/src/diagnoses/index.ts` | One `registerRule(...)` line per new rule. Two teammates appending creates a merge conflict every time. |
| `crawfish-lens/src/diagnoses/tool-optimizer-map.ts` | Tool→optimizer map; each new optimizer adds an entry. |
| `crawfish-lens/src/server/index.ts` | Route registration. |
| `crawfish-dash/web/src/App.tsx` (and equivalent route registries) | Route table. |
| `crawfish-app/src-tauri/tauri.conf.json` | Single source of truth for the desktop shell. |
| `ROADMAP.md`, `BRAINSTORM.md`, `INTEGRATIONS.md`, `PRODUCT.md` | Cross-team narrative documents. |
| `package.json` (any submodule) | Dep-bumps and script renames must be coordinated. |
| Any generated file (`dist/`, `web/dist/`, JSON schemas) | Builds from source; running parallel builds clobber each other. |

If a teammate genuinely needs to edit one of these, they MUST `SendMessage`
the lead first and get explicit OK. The lead serializes those edits.

---

## File-ownership rules per known fan-out

These match the team shapes in `ROADMAP.md` § 3 and the parallelization plan
in the agent-teams discussion. When the lead spawns a team for one of these
phases, hand each teammate the listed paths *exclusively*.

### C2.P1.M3 — diagnoses catalog (3 teammates)

| Teammate | Owns | Forbidden |
|---|---|---|
| `single-call` | `crawfish-lens/src/diagnoses/rules/{dom-dump-detected,log-truncation-pattern,thinking-overhead}.ts` + `test/fixtures/diagnoses/single-call/` | All other rule files; `index.ts`. |
| `journey` | `crawfish-lens/src/diagnoses/rules/{re-read-loops,grep-then-read-storms,context-window-panic}.ts` + `test/fixtures/diagnoses/journey/` | All other rule files; `index.ts`; `timeline.ts` (contract is fixed). |
| `graph` | `crawfish-lens/src/diagnoses/rules/{sibling-redundancy,agent-fanout-cost,low-cache-hit-rate}.ts` + `test/fixtures/diagnoses/graph/` | All other rule files; `index.ts`; `topology.ts`. |

**Lead does at the end:** appends the eight new `registerRule(...)` calls to
`diagnoses/index.ts` in one commit. Hand-merging is faster than three
teammates fighting over the same file.

### C2.P3 — runtime adapters (3 teammates)

| Teammate | Owns | Forbidden |
|---|---|---|
| `openclaw` | `crawfish-lens/src/adapters/openclaw.ts` (polish only — adapter already shipped) | Other adapters; `transcript.ts`. |
| `cursor` | `crawfish-lens/src/adapters/cursor.ts` (new) | Other adapters; `transcript.ts`. |
| `sdk` | `crawfish-lens/src/adapters/sdk.ts` (new) | Other adapters; `transcript.ts`. |

**Spec first:** the lead writes `docs/specs/adapter-contract.md` and gets
the user's OK on it before spawning. All three teammates code against that
contract. If a teammate hits a schema field the contract doesn't cover, they
**`SendMessage` the lead** rather than editing the contract themselves.

### C2.P2 — adoption wizards (3 teammates)

| Teammate | Owns | Forbidden |
|---|---|---|
| `first-run` | `crawfish-dash/web/src/wizards/first-run/**` + `crawfish-dash/src/server/first-run.ts` | Other wizard dirs. |
| `policy` | `crawfish-dash/web/src/wizards/policy/**` + `crawfish-dash/src/server/policy.ts` | Other wizard dirs. |
| `prep` | `crawfish-opt-codebase/src/cli/prep.ts` + `crawfish-dash/web/src/wizards/prep/**` | Other wizard dirs. |

Lead handles the cross-wizard navigation and the `App.tsx` route table.

### C2.P1 § 3.0 — visualizer prototype (3 teammates, worktrees)

Run with `isolation: "worktree"` so each layout exploration lives in its own
copy of the repo. Each teammate is told to render the same fixture session
(`a774c151-c2f5-4923-9fbb-9cc095483c4c` in OpenClaw or any session with
subagents in Claude Code) using a different layout primitive. They review
each other's output and converge on a winner. Lead picks. No production
files touched by any teammate — all work in `crawfish-dash/web/src/components/topology/<layout>/` or similar.

---

## Conventions every teammate should know

- **CSS lives in `ui/tokens/globals.css` only.** Both lens and dash alias
  `@crawfish/ui` → `../../ui` via Vite + tsconfig paths. Don't write component-
  scoped CSS files; add classes to `globals.css` and reference them.
- **Don't run builds in parallel.** `npx vite build`, `npx tsc -p ...`, etc.
  write to `dist/` which is shared if two teammates do it at the same time.
  The lead runs builds; teammates run type-check only (`tsc --noEmit`) when
  verifying.
- **Don't edit `dist/`.** It's generated. If a teammate needs to verify their
  change, they read source, not built output.
- **Don't kill processes you didn't start.** Other teammates may be running
  test servers on adjacent ports.
- **Type-check before claiming done.** `npx tsc --noEmit -p tsconfig.json`
  in the relevant submodule. The lead enforces this via a `TaskCompleted`
  hook when one is configured.

---

## When in doubt — `SendMessage` the lead

The lead has the cross-team picture; teammates don't. If a teammate finds
themselves needing to:

- edit a file outside their assigned ownership,
- bump a dependency,
- rename a public API (any export from `src/index.ts`),
- or touch any of the registries in the table above,

→ `SendMessage` the lead, explain what and why, and wait. Cheaper than
unwinding a conflict.
