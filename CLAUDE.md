# Crawfish — agent-team conventions

This file is loaded by every Claude Code session in this directory and (via
`CLAUDE.md` propagation) every spawned teammate. It exists to keep parallel
work safe — i.e., to keep two teammates from overwriting each other's edits
when running in agent-team mode.

If you are a *single* Claude Code session (no team), most of this is
informational. If you are a *teammate* spawned by a lead, treat the file-
ownership rules below as binding.

---

## Skill auto-routing — reach for these without being asked

When a user request matches one of the situations below, invoke the listed skill via the `Skill` tool **proactively, without waiting for the user to type the slash command**. Pick the most specific match. If two match, prefer the one further down (more specific overrides more general). If none match, work directly.

### Frontend / UI work in this repo

- **Building or scaffolding a new component, page, or screen from scratch** → `frontend-design:frontend-design` (production-grade, anti-generic aesthetics). This is the default for "build X UI" / "add a Y page".
- **Polishing, redesigning, critiquing, or "this looks generic / cheap / AI-ish" on existing UI** → `impeccable` (the 23-command anti-slop kit; entry point covers craft/audit/critique/polish/distill/etc.).
- **Bug report against one specific element ("the button is misaligned", "the modal overflows")** → `ui-diagnose` agent (already configured). Don't reach for a skill.
- **Whole-page or whole-flow design QA / accessibility / responsive audit on a running dev server** → `ui-auditor` agent (already configured). Don't reach for a skill.
- **Retroactive 6-pillar visual audit of code that already shipped** → `gsd-ui-review`.
- **User wants a *throwaway hi-fi HTML prototype, slide deck, animation, or design-direction exploration*** (not production code) → `huashu-design`.
- **User asks for a specific look-and-feel (minimalist editorial, industrial brutalist, premium agency, etc.)** → match the taste skill: `minimalist-ui`, `industrial-brutalist-ui`, `high-end-visual-design`, `design-taste-frontend`, or `gpt-taste`. Use one, not several.
- **Upgrading an existing project's design quality without breaking it** → `redesign-existing-projects`.
- **Generating reference *images* (not code) for web or mobile screens, or brand boards** → `imagegen-frontend-web`, `imagegen-frontend-mobile`, or `brandkit`.
- **Image → code (recreate a design from a screenshot)** → `image-to-code`.

### Code quality / review / safety

- **Just finished writing code and want a quality pass before committing** → `simplify` (review changed code for reuse/quality/efficiency, fix issues).
- **User asks for "code review" of a PR or branch** → `review` (built-in PR reviewer).
- **User asks for a security check before merging** → `security-review` (scans pending changes).
- **Building / debugging / tuning code that imports `anthropic` or `@anthropic-ai/sdk`, or touching prompt caching / tool use / thinking budgets** → `claude-api`.

### GSD (Get Shit Done) — only when the user is in a GSD workflow

GSD is opinionated and writes to `.planning/`. **Do not auto-invoke any `gsd-*` skill unless the user is clearly running a GSD workflow already** (i.e., `.planning/` exists in the cwd or the user mentioned GSD / a phase / a milestone). When they are:

- **Brand new project, no `.planning/` yet** → `gsd-new-project`.
- **Existing repo, want to bootstrap GSD from existing docs** → `gsd-ingest-docs`.
- **"Explore an idea before committing"** → `gsd-explore`.
- **Quick map of an unfamiliar codebase** → `gsd-map-codebase`.
- **In the middle of a phase and lost** → `gsd-resume-work` or `gsd-progress`.
- **Trivial one-off task inside a GSD repo** → `gsd-fast` or `gsd-quick`.

Outside a GSD workflow, don't mention GSD. Use TaskCreate / Plan instead.

### Memory and context

- **Setting up recurring tasks, polling, or scheduled agents** → `loop` (interval) or `schedule` (cron / remote routine).
- **User explicitly asks "remember X across sessions" beyond what auto-memory captures** → fall back to auto-memory; don't invoke another memory tool.

### Config / harness changes

- **"Allow X command", "add permission", "set env var", "when claude does X then Y", hook setup, settings.json edits** → `update-config`.
- **Custom keybindings / chords / rebinding submit key** → `keybindings-help`.
- **User noticing they get too many permission prompts** → `fewer-permission-prompts`.
- **Creating a brand-new skill** → `skill-creator` (from the official plugin).

### Superpowers (planning-heavy work)

- **"Brainstorm with me"** → `superpowers:brainstorm`.
- **"Write a plan for X" before implementing** → `superpowers:write-plan`, then `superpowers:execute-plan` to run it.

### Hard rules

- **Never invoke more than one taste/design skill in the same turn.** They conflict.
- **Never auto-invoke a skill that writes to disk (`gsd-*`, `skill-creator`, `init`) without first stating in one sentence what you're about to do.** The user can redirect.
- **If a skill's preconditions aren't met** (e.g., `gsd-execute-phase` with no `PLAN.md`), don't invoke it — say what's missing instead.
- **A skill invocation does not replace the [Files that two teammates must NEVER edit simultaneously] rules below.** If a skill would touch a registry file, treat it as a lead-only action.

---

## Multi-repo layout — cheap conflict avoidance

The umbrella holds five sibling submodules. **Each submodule is a natural
ownership boundary for one teammate.** When work fans out across submodules,
hand each teammate a single submodule path and don't let them edit anywhere
else.

```
crawfish/
├── ui/                       # shared design tokens + components (canonical CSS lives here)
├── cloud/
│   ├── platform/             # signed-in web SPA (Clerk, org/project import)
│   └── server/               # platform backend (Express + Prisma)
├── desktop/
│   ├── app/                  # (submodule) Tauri shell that spawns lens+dash as children
│   ├── dash/                 # (submodule) dashboard UI, proxies to lens, owns policies + benchmarks
│   ├── lens/                 # (submodule) transcript reader, REST API, server-side reductions
│   ├── opt/                  # (submodule) browser optimizer (MCP server)
│   ├── opt-codebase/         # (submodule) codebase optimizer
│   ├── opt-artifact/         # artifact-id optimizer (in-tree)
│   └── opt-logs/             # logs-summarize optimizer (in-tree)
├── cli/
│   ├── orgctl/               # org-control MCP server
│   └── projectctl/           # per-project .crawfish/ engine
└── web/                      # marketing & onboarding site
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
| `desktop/lens/src/diagnoses/index.ts` | One `registerRule(...)` line per new rule. Two teammates appending creates a merge conflict every time. |
| `desktop/lens/src/diagnoses/tool-optimizer-map.ts` | Tool→optimizer map; each new optimizer adds an entry. |
| `desktop/lens/src/server/index.ts` | Route registration. |
| `desktop/dash/web/src/App.tsx` (and equivalent route registries) | Route table. |
| `desktop/app/src-tauri/tauri.conf.json` | Single source of truth for the desktop shell. |
| `ROADMAP.md`, `PRODUCT.md`, `docs/product/BRAINSTORM.md`, `docs/product/INTEGRATIONS.md` | Cross-team narrative documents. |
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
| `single-call` | `desktop/lens/src/diagnoses/rules/{dom-dump-detected,log-truncation-pattern,thinking-overhead}.ts` + `test/fixtures/diagnoses/single-call/` | All other rule files; `index.ts`. |
| `journey` | `desktop/lens/src/diagnoses/rules/{re-read-loops,grep-then-read-storms,context-window-panic}.ts` + `test/fixtures/diagnoses/journey/` | All other rule files; `index.ts`; `timeline.ts` (contract is fixed). |
| `graph` | `desktop/lens/src/diagnoses/rules/{sibling-redundancy,agent-fanout-cost,low-cache-hit-rate}.ts` + `test/fixtures/diagnoses/graph/` | All other rule files; `index.ts`; `topology.ts`. |

**Lead does at the end:** appends the eight new `registerRule(...)` calls to
`diagnoses/index.ts` in one commit. Hand-merging is faster than three
teammates fighting over the same file.

### C2.P3 — runtime adapters (3 teammates)

| Teammate | Owns | Forbidden |
|---|---|---|
| `openclaw` | `desktop/lens/src/adapters/openclaw.ts` (polish only — adapter already shipped) | Other adapters; `transcript.ts`. |
| `cursor` | `desktop/lens/src/adapters/cursor.ts` (new) | Other adapters; `transcript.ts`. |
| `sdk` | `desktop/lens/src/adapters/sdk.ts` (new) | Other adapters; `transcript.ts`. |

**Spec first:** the lead writes `docs/specs/adapter-contract.md` and gets
the user's OK on it before spawning. All three teammates code against that
contract. If a teammate hits a schema field the contract doesn't cover, they
**`SendMessage` the lead** rather than editing the contract themselves.

### C2.P2 — adoption wizards (3 teammates)

| Teammate | Owns | Forbidden |
|---|---|---|
| `first-run` | `desktop/dash/web/src/wizards/first-run/**` + `desktop/dash/src/server/first-run.ts` | Other wizard dirs. |
| `policy` | `desktop/dash/web/src/wizards/policy/**` + `desktop/dash/src/server/policy.ts` | Other wizard dirs. |
| `prep` | `desktop/opt-codebase/src/cli/prep.ts` + `desktop/dash/web/src/wizards/prep/**` | Other wizard dirs. |

Lead handles the cross-wizard navigation and the `App.tsx` route table.

### C2.P1 § 3.0 — visualizer prototype (3 teammates, worktrees)

Run with `isolation: "worktree"` so each layout exploration lives in its own
copy of the repo. Each teammate is told to render the same fixture session
(`a774c151-c2f5-4923-9fbb-9cc095483c4c` in OpenClaw or any session with
subagents in Claude Code) using a different layout primitive. They review
each other's output and converge on a winner. Lead picks. No production
files touched by any teammate — all work in `desktop/dash/web/src/components/topology/<layout>/` or similar.

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
