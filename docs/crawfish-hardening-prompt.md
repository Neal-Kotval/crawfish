# Crawfish Phase 1 Hardening Prompt (Claude Code — Agent Teams)

> Paste the block below into a Claude Code session opened in the **`crawfish-framework`** repo (the existing first-pass framework).
> **Prerequisite:** enable agent teams — add to `~/.claude/settings.json`:
> `{ "env": { "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1" } }`
> Recommended: run with the Linear MCP connected (to read/update CRA-150 and its sub-issues) and `--teammate-mode auto`.

---

You are the **team lead**. The Crawfish framework's first pass is built and (assumed) green — primitives, runtimes, security spine, docs, and a `demo/triage-bot` dogfood project all exist. Your job is to deliver epic **`CRA-150` — Phase 1 Hardening: Operate, Observe & Integrate** to completion: the layer that turns "runs a pipeline once" into "deploys, watches, and manages always-on pipelines," plus Claude Code integration and a clearer project structure. Complete, bug-free, and secure.

## Source of truth (read first)

1. **Linear epic `CRA-150`** and its 7 sub-issues — each has a goal, build tasks, acceptance criteria, and a worked example. Build to those.
2. The **existing repo**: `CLAUDE.md`, `docs/architecture/` (ARCHITECTURE, SECURITY, the ADRs), `docs/roadmap/`, and the current `packages/crawfish/src/crawfish/` source + tests. Match the established conventions and seams.
3. Notion: "Architecture — OSS Framework, craw CLI & Discovery" and "Architectural Gap Review" for context.

## Sub-issues (build order)

Mirror these into the shared task list with the dependency edges below; build top-down, parallelize within a tier.

1. **CRA-154 · Observer output + run-info surface** — `ObserverEvent` + `RunInfo` persisted via `Store` (tenant-scoped, scrubbed), a stable `ctx.emit(...)` API, queryable + append-only. *Foundational — observers, manage, and visualize all read it.*
2. **CRA-157 · Clearer + configurable structure** — documented canonical layout, config-driven `[project.paths]`, `craw doctor`. *Do early; it defines where `observers/` live.*
3. **CRA-151 · `craw deploy`** — always-on detached/tmux-style runner, auto-restart, trigger-driven, resumes via the execution ledger, writes a deploy registry.
4. **CRA-153 · Observer primitive** — polls a pipeline's event/health stream (rule-based + optional LLM/Definition-backed judge), emits `ObserverEvent`s. *Depends on CRA-154.*
5. **CRA-152 · `craw manage`** — list/stop/restart running pipelines from the deploy registry + ledger + cost meter. *Depends on CRA-151 + CRA-154.*
6. **CRA-155 · `craw visualize`** — minimal hardcoded localhost dashboard over the observer/run-info feed. *Depends on CRA-154 (+ CRA-151 registry).*
7. **CRA-156 · Claude Code integration** — `craw export --claude-code` turns a Definition into a CC subagent/skill. *Independent; parallelize.*

## Operating principles (non-negotiable)

- **Do not stop to ask questions.** On any architectural or security fork, investigate, pick the best option, and record it as a new ADR in `docs/architecture/decisions/` (next number after 0007) with rationale + rejected alternatives. Keep moving.
- **Don't break what works.** The existing test suite must stay green at every step (`uv run pytest`, `ruff`, `mypy`). Treat a red suite as a stop-the-line event.
- **Honor the seams and conventions.** No SDK imports outside `AgentRuntime`; no raw SQL outside a `Store` impl; new persistence goes through `Store` (with the `org_id`/tenancy key and WAL semantics already established). Read `CLAUDE.md` and match it.
- **One owner per file.** Partition by sub-issue/module so teammates don't edit the same file.
- **Every feature is "done" only when its quality gates pass** (below); mark the Linear issue `Done` only after QA + security sign-off.

## Security spine for *this* epic (enforce on every new surface)

- **Observer events + run-info are scrubbed before the Store write** (reuse the existing `ScrubbingStore`); no secrets, tokens, or raw fluid content leak into events, the dashboard, or logs. Tenancy key on every new row.
- **`craw visualize` binds loopback-only** (`127.0.0.1`), no auth-bypass, no secret values rendered; it reads the scrubbed run-info surface only.
- **`craw deploy` never leaks secrets** into the tmux pane name, process args, env dumps, or logs; the detached process resolves secrets by reference exactly as a foreground run does.
- **LLM observers run under the same cost cap + injection boundary** as any Definition: the run data they judge is *data*, never instructions; their spend is capped and telemetered.
- **`craw export --claude-code` carries no secrets** into the generated subagent file; it maps tool/MCP *references*, not credentials.

## The team

Spawn ~5 active teammates (reuse project `security-reviewer` / `test-runner` subagent definitions if present); spawn the researcher on demand.

- **Architect** — owns where the new surface plugs into the seams (the `Store` schema additions for `ObserverEvent`/`RunInfo`, the deploy registry, the `[project.paths]` config, the discovery changes for `observers/`). Reviews every ADR. Require plan approval for `Store`/config/seam changes.
- **Implementer A** — operate track: CRA-154 → CRA-151 → CRA-152 (run-info surface, deploy, manage).
- **Implementer B** — observe + integrate track: CRA-153 → CRA-155, and CRA-156 + CRA-157 (observer, visualize, CC export, structure).
- **QA engineer** — extends the suite for every new feature: `pytest` + `craw test`, deterministic (mock/replay runtime, no live model calls), plus the acceptance criteria from each issue. Adds an integration test that **deploys the demo, observes it, and reads the dashboard feed**.
- **Security reviewer** — audits each new surface against the spine above (scrubbing, loopback bind, secret non-leakage in detached processes, LLM-observer cost/injection). Blocks completion on any High/Critical.
- **Researcher** (on demand, cheaper model) — looks up best practices when needed (e.g. process supervision / tmux detachment patterns, append-only event-log polling, minimal no-build dashboards, Claude Code subagent frontmatter format), returns a concise note, and **folds conclusions into `docs/roadmap/`**.
- **Roadmap reviewer** — reviews each research folding before implementation; rejects if wrong/thin/conflicting with an ADR.

Tell the lead to **wait for teammates** rather than implementing itself, and to steer continuously.

## Per-feature build loop

1. Lead claims the next unblocked sub-issue and assigns it.
2. If the feature touches unfamiliar territory, the implementer requests a **researcher** pass → findings folded into `docs/roadmap/<feature>.md` → **roadmap reviewer approves** before code.
3. Implementer builds it (plan approval first for seam/`Store`/config changes), matching the issue's worked example and the repo's conventions.
4. QA writes/runs tests; full suite stays green and deterministic.
5. Security reviewer audits against the spine.
6. Dogfood in `demo/` (below) and run end to end.
7. Only then mark the Linear issue `Done`.

## Dogfood in `demo/`

Extend the existing `demo/triage-bot` to exercise the new layer, and run it after each tier:

- Add a pipeline trigger and **`craw deploy`** the triage-bot; confirm it runs detached, fires on schedule, and survives a kill (auto-restart + ledger resume).
- Add an **observer** (one rule-based, one LLM/Definition-backed `observers/quality`) that watches the deployed bot and emits events.
- Run **`craw manage`** (shows the bot running) and **`craw visualize`** (dashboard renders pipelines, runs, cost, observer feed).
- **`craw export --claude-code definitions/...`** and confirm the generated subagent runs in a CC session.
- Update `docs/guide/` with how-to pages for `deploy` / `manage` / `visualize` / observers / CC export, and document the configurable structure (`[project.paths]`, `craw doctor`).

## Definition of Done

Per feature: matches the issue spec + example; `ruff` + `mypy` clean; QA tests green and deterministic; security audit clean; demo exercises it; `docs/guide/` updated. **The epic is complete when:**

- `craw deploy` runs the demo pipeline always-on (detached, auto-restart, trigger-fired, ledger-resumed); `craw manage` lists/controls it; `craw visualize` shows live pipelines + runs + cost + observer events; an LLM observer flags an induced bad run; `craw export --claude-code` produces a working CC subagent; the project layout is documented + configurable and `craw doctor` reports health.
- The **entire test suite is green** (old + new), and the security reviewer signs off with **no open High/Critical** (special attention: dashboard loopback + no-secret rendering, detached-process secret non-leakage, observer-event scrubbing, LLM-observer cost/injection).
- All 7 CRA-150 issues are `Done`.

## Final pass

Spawn three reviewers in parallel — **security** (audit + a secret-leak/injection red-team against the deployed demo and the dashboard), **correctness/QA** (run the whole suite + the deploy→observe→visualize→export demo flow), **architecture** (verify the seams held: new persistence only via `Store`, no SDK leak, tenancy + scrubbing applied to every new row). Have them challenge each other, fix everything surfaced, then report the epic complete.
