# Crawfish Roadmap — Agent-Team Execution Playbook

> **For agentic workers:** This is a **master playbook**, not a single bite-sized plan. It defines team shapes, file ownership, contracts, and the order in which to spawn agent teams across the 28-week roadmap. Each phase below culminates in a **handoff line** that tells the lead which superpowers sub-skill to use next (almost always `superpowers:writing-plans` → `superpowers:subagent-driven-development`). The lead writes the bite-sized per-phase plan when the phase opens — not now — because contract details depend on the state of the codebase at that moment.

**Goal:** Execute the reprioritized [ROADMAP.md](../../../ROADMAP.md) (NOW = Linear-grade board, NEXT = RAG/optimizers/dash, LATER = Skills/IDE, LATER² = P6, Parallel = `crawfish.dev` web) using Claude Code **agent teams** ([AGENT-TEAMS.md](../../../AGENT-TEAMS.md)) — one teammate per submodule, lead serializes registry edits, worktrees for exploratory work.

**Architecture:** A single lead session (the human's terminal) coordinates teams of 2–5 teammates per phase. Each phase begins with a **contract** the lead writes and gets human OK on; teammates code against the contract in parallel; the lead serializes the registry edits at the end. Cross-cutting changes (shared CSS, `index.ts` route table, `package.json`) are **lead-only**. Per-phase teams are torn down before the next phase opens — **no nested teams, one team at a time per lead**.

**Tech stack:** Claude Code agent teams (in-process or tmux mode) · superpowers (`writing-plans`, `subagent-driven-development`, `executing-plans`, `brainstorming`, `test-driven-development`, `verification-before-completion`, `requesting-code-review`, `using-git-worktrees`, `finishing-a-development-branch`) · gsd skills where the slice maps to a GSD phase · Vitest per submodule for tests · `tsc --noEmit` for type-check gates.

---

## 0 · Cross-cutting rules — read once, apply every phase

These come from [`CLAUDE.md`](../../../CLAUDE.md) and [`AGENT-TEAMS.md`](../../../AGENT-TEAMS.md). Every phase below assumes them.

### 0.1 Lead-only files (NEVER hand to a teammate)

| File | Why |
|---|---|
| `crawfish-lens/src/diagnoses/index.ts` | `registerRule(...)` aggregator. |
| `crawfish-lens/src/diagnoses/tool-optimizer-map.ts` | Tool→optimizer aggregator. |
| `crawfish-lens/src/server/index.ts` | Route table — every fan-out adds routes. |
| `crawfish-dash/web/src/App.tsx` | Route table. |
| `crawfish-app/src-tauri/tauri.conf.json` | Single shell config. |
| `ROADMAP.md`, `BRAINSTORM.md`, `INTEGRATIONS.md`, `PRODUCT.md`, `GRAND_PLAN.md` | Narrative docs. |
| Any `package.json` (any submodule) | Dep-bumps must be coordinated. |
| Generated dirs (`dist/`, `web/dist/`) | Build outputs — only the lead builds. |
| `ui/tokens/globals.css` | Cross-submodule shared styles. |
| `docs/specs/*` (schema contracts) | Schema must precede teammate code. |

If a teammate needs to edit one of these, they **MUST `SendMessage` the lead and wait**.

### 0.2 Contract-first cadence (per phase)

The lead always runs this loop **before spawning teammates**:

- [ ] Open phase with `superpowers:brainstorming` to converge on scope (skip only if the ROADMAP entry is already unambiguous).
- [ ] Write the **schema/contract docs** the teammates need:
  - REST shapes → `docs/specs/<area>-contract.md`
  - Event types → update `docs/specs/org-contract.md`
  - UI tokens / shared components → land them on `ui/`
- [ ] Get the human's OK on the contract (one round-trip, plain English).
- [ ] Run `superpowers:writing-plans` to produce the bite-sized per-phase plan at `docs/superpowers/plans/YYYY-MM-DD-<phase>.md`.
- [ ] Spawn the team with the prompt template in §0.6.

### 0.3 Build serialization

Only the lead runs:
```
npx vite build
npx tsc -p tsconfig.json    # emit
npm test                    # full suite in a submodule
```
Teammates verify with **type-check only**:
```
npx tsc --noEmit -p tsconfig.json
```
plus their own per-file vitest fixtures.

### 0.4 Verification gate (the lead enforces)

Before any teammate is allowed to mark a task done, the lead applies `superpowers:verification-before-completion`:
- Type-check clean in the touched submodule.
- The phase's vitest suite green.
- A fixture/test exists for every new branch of logic.
- No new hex literals in components — only `ui/tokens/globals.css` classes.

A `TeammateIdle` hook (see §0.7) returns exit 2 with the failing gate as feedback.

### 0.5 Worktrees vs in-process

| Situation | Spawn with |
|---|---|
| Each teammate owns a different submodule | **In-process** (default). |
| Multiple teammates want to explore *the same* surface (e.g. visualizer layouts) | **`isolation: "worktree"`** so each lives in an isolated checkout. |
| Lead pulls submodule HEAD on shared CSS / schema | **Lead-only commit first**, then spawn so teammates inherit it. |

When in doubt: in-process. Reach for `superpowers:using-git-worktrees` only when teammates would write to overlapping paths.

### 0.6 Spawn-prompt template (copy-paste for every phase)

```
Create an agent team for <PHASE NAME>. Spawn <N> teammates:
  - <name-A>: owns <submodule path>, implements <task IDs from phase plan>.
  - <name-B>: owns <submodule path>, implements <task IDs>.
  - ...

Each teammate MUST:
  1. Read CLAUDE.md and AGENT-TEAMS.md before touching code.
  2. Read docs/specs/<contract>.md as their source of truth.
  3. Follow the bite-sized plan at docs/superpowers/plans/<phase>.md.
  4. Apply superpowers:test-driven-development for every task.
  5. SendMessage the lead before editing any file in §0.1.
  6. Run `npx tsc --noEmit -p tsconfig.json` before claiming done.

Use Sonnet for each teammate (Opus only if the teammate's task is reasoning-heavy).
Require plan approval before any teammate writes code.
```

### 0.7 Hooks (lead-side quality gates)

Configure once in `.claude/settings.json`:

```jsonc
{
  "hooks": {
    "TeammateIdle": ".claude/hooks/verify-teammate.sh",
    "TaskCompleted": ".claude/hooks/typecheck-and-test.sh"
  }
}
```

`verify-teammate.sh` exits 2 with a feedback message when:
- the teammate touched a §0.1 lead-only file,
- `npx tsc --noEmit` is failing in the teammate's submodule,
- the teammate's stated task ID is not in the phase plan.

This pushes them back instead of letting them mark done.

### 0.8 Phase close-out (lead-only, every time)

- [ ] Lead serializes registry edits (route table, `registerRule` calls, `App.tsx` routes).
- [ ] Lead runs full build + full vitest suite in each touched submodule.
- [ ] Lead invokes `superpowers:requesting-code-review` against the phase branch.
- [ ] Lead invokes `superpowers:finishing-a-development-branch` to choose merge path (PR via `gsd-pr-branch` if `.planning/` exists, otherwise `gh pr create`).
- [ ] Tear the team down: ask each teammate to shut down, then `"Clean up the team."` from the lead.
- [ ] Cut the milestone tag declared in the ROADMAP (e.g. `v0.3` end-of-NOW).

---

## 1 · Phase-by-phase team blueprints

For each phase: the team shape, exact file ownership, the contract the lead must write first, and the handoff at the end.

### Phase NOW-W1 — Cycles, epics, activity feed, member ACL

**Lead pre-work (contract):**
- [ ] Update `docs/specs/org-contract.md` — add `cycles.json` schema, `cycle_id` / `epic_id` on tasks, new event kinds (`status_changed`, `assigned`, `linked`, `labeled`, `budget_breach`), primary-assignee + contributor model.
- [ ] Get human OK on contract.
- [ ] Use `superpowers:writing-plans` → `docs/superpowers/plans/2026-05-XX-now-w1-cycles-acl.md`.

**Team shape — 3 teammates, in-process:**

| Teammate | Owns | Forbidden |
|---|---|---|
| `cycles-be` (Sonnet) | `crawfish-lens/src/server/cycles.ts`, `crawfish-lens/src/server/types.ts` (cycles+epics fields only), `crawfish-lens/test/cycles.test.ts` | `index.ts` route table, `board.ts`. |
| `activity-be` (Sonnet) | `crawfish-lens/src/server/activity.ts`, `crawfish-lens/test/activity.test.ts`, ACL hook in `crawfish-lens/src/server/board.ts:validateActor` (single function — see §0.1 caveat below) | All other `board.ts` regions. Must `SendMessage` lead before editing `validateActor` boundary. |
| `plan-fe` (Sonnet) | `crawfish-dash/web/src/routes/Plan.tsx`, `crawfish-dash/web/src/components/TaskDrawer.tsx` (activity drawer panel), `crawfish-dash/web/src/components/CycleBudgetBar.tsx` (new) | Any shared `ui/` token edits. |

**Lead-only at end:** wire `cycles.ts` + `activity.ts` into `crawfish-lens/src/server/index.ts` route table; final `tsc -p` + `npm test`; bump submodule SHAs.

**Handoff:** `superpowers:requesting-code-review` → close-out per §0.8 → open Phase NOW-W2.

---

### Phase NOW-W2 — Acceptance-criteria evidence + token-budget bar + agent preflight

**Lead pre-work:**
- [ ] Extend `docs/specs/org-contract.md` with `criteria: [{id, statement, kind, evidence?}]` shape and `done`-transition guard semantics.
- [ ] Write `docs/specs/preflight-contract.md` — what `preflight_attested` events look like and where the orgctl tool wrapper injects context.
- [ ] `superpowers:writing-plans` → `docs/superpowers/plans/2026-05-XX-now-w2-criteria-budget-preflight.md`.

**Team shape — 3 teammates:**

| Teammate | Owns | Forbidden |
|---|---|---|
| `criteria-be` | `crawfish-lens/src/server/board.ts:validateDoneTransition` (new function — append at file end), `crawfish-lens/src/server/types.ts` (criteria field), `crawfish-lens/test/criteria.test.ts` | Existing `board.ts` regions. |
| `budget-fe` | `crawfish-dash/web/src/components/TaskBudgetBar.tsx`, drawer integration in `TaskDrawer.tsx` (criteria editor + evidence chip — additive only), `crawfish-dash/web/test/budget-bar.test.tsx` | Other drawer regions; `globals.css` edits. |
| `preflight-orgctl` | `crawfish-orgctl/src/preflight.ts`, MCP tool wrapper, `crawfish-orgctl/test/preflight.test.ts` | Any lens code. Must `SendMessage` lead if a new MCP tool needs registering. |

**Lead-only at end:** `onBudgetBreach` event handler (lives in `crawfish-lens/src/server/board.ts` — central path, lead writes it); register preflight MCP tool in `crawfish-orgctl/src/index.ts`.

---

### Phase NOW-W3 — Capability-matched routing + AI triage + auto-decomposition

**Lead pre-work:**
- [ ] Write `docs/specs/router-contract.md` — agent stats schema, routing algorithm, tiebreakers.
- [ ] Write `docs/specs/inbound-adapter-contract.md` — the shape every inbound adapter (github-issues, email, notion-form, slack-handoff) MUST produce. **All four teammates code against this exact contract.**
- [ ] Pre-seed the `triage` and `planner` agent templates as **skeletons** in `crawfish-dash/src/templates/_agents/` so teammates fill them, not invent them.
- [ ] `superpowers:writing-plans` → phase plan.

**Team shape — 5 teammates** (this is the largest fan-out of the NOW slice; consider tmux mode for legibility):

| Teammate | Owns | Forbidden |
|---|---|---|
| `router` | `crawfish-lens/src/server/agent-stats.ts`, `crawfish-lens/src/server/router.ts`, tests | `crons.ts` (lead wires the router cron). |
| `triage` | `crawfish-dash/web/src/routes/Board.tsx` (Triage column only — additive), `crawfish-dash/src/templates/_agents/triage/{member.md,policy.json}` | Other board regions; route table. |
| `inbound` | `crawfish-lens/src/server/inbound/{github-issues,email,notion-form,slack-handoff}.ts`, tests | `index.ts` route table; `external-ref` mirroring (W4). |
| `planner` | `crawfish-lens/src/server/planner.ts`, `crawfish-dash/src/templates/_agents/planner/{member.md,policy.json}`, tests | Drawer UI. |
| `decomp-fe` | `crawfish-dash/web/src/components/DecompositionDrawer.tsx`, drawer mount, tests | Any backend code. |

**Coordination point:** `inbound` and `triage` share the `task_created` + `external_ref` event shape. Both code against `docs/specs/inbound-adapter-contract.md`. If either hits a gap, they `SendMessage` the lead — **never amend the contract themselves**.

**Lead-only at end:** route registration in `index.ts`; register the router cron in `crons.ts`; smoke-test all 4 inbound adapters end-to-end.

---

### Phase NOW-W4 — Linked-task graph + FTS5 search + external-ref ingestion

**Lead pre-work:**
- [ ] Add link kinds to `docs/specs/org-contract.md`; document reciprocal-edge semantics.
- [ ] Write `docs/specs/search-query.md` — the structured-query grammar (Linear-shaped).
- [ ] `superpowers:writing-plans` → phase plan.

**Team shape — 3 teammates:**

| Teammate | Owns | Forbidden |
|---|---|---|
| `links-be` | `crawfish-lens/src/server/types.ts` (links field — additive), link CRUD in `board.ts` (new functions at file end), tests | Pre-existing `board.ts` regions. |
| `links-fe` | `crawfish-dash/web/src/components/LinkGraph.tsx` (D3 or vis-network), drawer mount, tests | Backend. |
| `search` | `crawfish-lens/src/server/search.ts` (FTS5 + parser), `crawfish-dash/web/src/components/SearchBar.tsx`, tests | Lead-only files. |

**Run external-ref ingestion as a fourth task assigned to `links-be`** once `links-fe` is unblocked (sequential within that teammate is fine — no fan-out conflict).

---

### Phase NOW-W5 — Templates breadth + multi-org switcher + stats + cycle planner polish

**Team shape — 4 teammates, worktree-eligible** for the three template bodies (each touches its own dir, but consistency benefits from cross-review):

| Teammate | Owns | Forbidden |
|---|---|---|
| `tpl-dev-shop` | `crawfish-dash/src/templates/dev-shop/**` | Other template dirs; `_overlays/`. |
| `tpl-support` | `crawfish-dash/src/templates/support/**` | Other template dirs. |
| `tpl-research` | `crawfish-dash/src/templates/research/**` | Other template dirs. |
| `stats+switcher` | `crawfish-lens/src/server/stats.ts`, `crawfish-dash/web/src/components/OrgSwitcher.tsx`, Plan.tsx over-capacity row (additive), tests | Template dirs. |

**Lead-only at end:** `_overlays/*.json` files (7 of them — small, fast to write inline), the "Describe my org" wizard (cross-cuts runtime + templates), route table updates, `v0.3` tag + push.

**End-of-NOW handoff:** `superpowers:finishing-a-development-branch` → open external alpha → kick off Phase NEXT-W6 **and** Phase Parallel-A in the same week (two teams sequentially, since AGENT-TEAMS allows one team at a time per lead).

---

### Phase NEXT-W6 — RAG indexing + Knowledge tab

**Lead pre-work:**
- [ ] Resolve `sqlite-vec` prebuild risk before spawning (run `npm i better-sqlite3 sqlite-vec @xenova/transformers` in a scratch dir, confirm load).
- [ ] Write `docs/specs/rag-contract.md` — chunking parameters, embedding model, query shape.
- [ ] `superpowers:writing-plans` → phase plan.

**Team shape — 2 teammates:**

| Teammate | Owns | Forbidden |
|---|---|---|
| `rag-be` | `crawfish-lens/src/knowledge/{index,chunker,embed,watcher}.ts`, `crawfish-lens/src/server/knowledge.ts` (rewrite of handleIngest + query handler), tests | `index.ts` route table. |
| `knowledge-fe` | `crawfish-dash/web/src/routes/Knowledge.tsx`, tests | Backend. |

**Lead-only:** route registration; fallback cosine-path code (the risk-mitigation escape hatch in ROADMAP §5).

---

### Phase NEXT-W7 — Token-discipline optimizer pack

**Lead pre-work:**
- [ ] Scaffold `crawfish-opt-logs/` and `crawfish-opt-artifact/` as new submodules (lead adds them as git submodules — single-owner action).
- [ ] Write `docs/specs/optimizer-contract.md` — MCP tool shape, artifact-id semantics, benchmark format.
- [ ] `superpowers:writing-plans` → phase plan.

**Team shape — 2 teammates, worktree-isolated** (each teammate gets a fresh worktree of its new submodule):

| Teammate | Owns | Forbidden |
|---|---|---|
| `opt-logs` (worktree) | `crawfish-opt-logs/**` | Lens code. |
| `opt-artifact` (worktree) | `crawfish-opt-artifact/**` | Lens code. |

**Lead-only at end:** add the two entries to `crawfish-lens/src/diagnoses/tool-optimizer-map.ts` (the canonical aggregator); update `crawfish-dash/web/src/routes/optimizers.tsx` install-state cards (small, lead inlines it); write `scripts/bench-optimizer.ts`.

---

### Phase NEXT-W8 — Founder dashboard polish + demo

**Team shape — 2 teammates:**

| Teammate | Owns | Forbidden |
|---|---|---|
| `home-fe` | `crawfish-dash/web/src/routes/HomeDashboard.tsx` (cost widget + diagnoses inbox), `crawfish-dash/web/src/components/LiveSessionStrip.tsx`, `crawfish-dash/web/src/lib/spend.ts`, tests | Backend. |
| `compounding` | `crawfish-lens/src/stats.ts:computeCompoundingFactor`, tests | UI. |

**Lead-only:** `scripts/smoke-15min.ts` (cross-cuts everything — lead writes it), `docs/demo-stage1.mp4` (lead records).

**Weeks NEXT-W9–W10 (buffer):** no fan-out. The lead absorbs slip, polishes alpha-invitee onboarding, and writes the parallel-track Track-B contract (see Phase Parallel-B below) ahead of time.

---

### Phase LATER-W11–W16 — Skills, Codespaces, IDE, Wiki, Crons

**Pattern:** each week is its own team, run sequentially. Same contract-first cadence. Below is the recurring team shape.

| Week | Team |
|---|---|
| W11 — Skill backbone (first half) | 1 teammate: `skills-core` owns `crawfish-orgctl/src/skills/{loader,document,spreadsheet,presentation,pdf-fillform,email-draft,calendar}/`. Lead writes `docs/specs/skill-contract.md` first. |
| W12 — Skill backbone (second half) + Agentic-OS | 2 teammates: `skills-more` (web-research, code-*, brand, crm, standup, bench), `agentic-os` (`~/.crawfish/bin/`, `journal`, `crontab`, `proc/`). |
| W13 — Local Codespaces | 2 teammates: `space-cli` (CLI + lifecycle), `space-dash` (Spaces panel). Lead writes the devcontainer template scaffold. |
| W14 — Crawfish IDE v0.1 | **New repo (`crawfish-ide`)** — lead initializes; 2 teammates: `ide-shell` (extension + sidebar + status bar), `ide-hooks` (PreToolUse hook + dispatch). |
| W15 — LLM Wiki + Obsidian sync | 2 teammates: `wiki-be` (parser + backlinks + watcher), `wiki-fe` (wiki route + graph). |
| W16 — Cron recipes + dynamic routing + cost-manager | 2 teammates: `cron-recipes` (7 JSON entries + run-now UI), `cost-manager` (router + trajectory cache + cost-manager agent). |

**End-of-LATER:** `v0.5` tag → public alpha.

---

### Phase LATER²-W17–W28 — P6 work

Same recurring pattern. Notable points:

- **W17–18 native code review** — 3 teammates aligned with the C2.P1.M3 ownership in CLAUDE.md (single-call / journey / graph rule families). The lead handles `diagnoses/index.ts` aggregation at the end.
- **W19–20 test-gen + visual-auditor** — 2 teammates, both work in `crawfish-dash/src/templates/_agents/`, no overlap.
- **W21–22 agent-web proxy** — **New repo (`crawfish-proxy`)**. The lead writes the adapter contract `crawfish-proxy/CONTRACT.md` first (cross-references the C2.P3 work in CLAUDE.md). 3 teammates: `openclaw`, `cursor`, `sdk` (these are existing CLAUDE.md ownership rows — reuse them verbatim).
- **W23–24 CRDT + git-worktree (agent-side)** — 2 teammates: `crdt-yjs`, `worktree-spawn`. **Coordinate with Phase Parallel-C** which uses Yjs on the human side; lead must reconcile the two Yjs document schemas.
- **W25–27 communication-graph features** — 2 teammates: `flow-graph` (cross-session graph + time scrubber), `pattern-rules` (the two new diagnoses rules). Lead aggregates `diagnoses/index.ts`.
- **W28 hosted-mode prep** — 1 teammate: `export+packer`. Lead writes the hosted-mode spec.

---

### Parallel-Track Phases (`crawfish.dev` — runs alongside NEXT/LATER)

**Constraint:** Per AGENT-TEAMS.md, **one team at a time per lead**. So the lead alternates: spend Mon–Thu on the desktop phase team, then tear it down and run the parallel-track team Fri (or vice-versa, depending on which slice is blocking). For a full parallel cadence, the human can run a *second lead* in a separate terminal — that's two leads, two teams, fully isolated, which the AGENT-TEAMS rules support.

#### Phase Parallel-A (weeks 6–7) — Marketing + download portal

**Lead pre-work:**
- [ ] `mkdir crawfish-web && cd crawfish-web && pnpm create next-app` — single-owner scaffold.
- [ ] Wire Vercel deploy.
- [ ] Write `crawfish-web/docs/marketing-content.md` — final copy for hero, three-pillar pitch, pricing teaser (so teammates don't invent marketing copy).
- [ ] `superpowers:writing-plans` → plan.

**Team shape — 2 teammates, worktree-isolated:**

| Teammate | Owns | Forbidden |
|---|---|---|
| `marketing-pages` | `crawfish-web/app/(marketing)/{page,tour,download}.tsx` + OG/sitemap/robots | Auth code; download API. |
| `download-api` | `crawfish-web/app/api/releases/latest/route.ts`, `crawfish-web/app/(marketing)/download/ide/page.tsx`, IDE download card | Marketing copy. |

**Hard skill invocation:** the marketing teammate should explicitly invoke `frontend-design:frontend-design` (production-grade aesthetics, anti-AI-slop) since this is the public surface — and **only that skill**, not a chain of taste skills (per CLAUDE.md "never invoke more than one taste/design skill in the same turn").

---

#### Phase Parallel-B (weeks 8–10) — Authed web dashboard MVP

**Lead pre-work (CRITICAL — this is the biggest contract surface in the playbook):**
- [ ] Write `docs/specs/tunnel-contract.md` — outbound WebSocket handshake, per-org auth token signing, message framing.
- [ ] Extract shared components from `crawfish-dash/web/src/components/{Board,Plan,TaskDrawer,Wiki,Analytics}` into `ui/components/` — **lead-only refactor**, run it as a single commit before fan-out so both Tauri shell and Next.js consume the new paths.
- [ ] Write `docs/specs/web-dashboard-contract.md` — which routes mirror which Tauri tabs, how `crawfish://` deep links work.
- [ ] `superpowers:writing-plans` → plan.

**Team shape — 3 teammates:**

| Teammate | Owns | Forbidden |
|---|---|---|
| `tunnel` | `crawfish-lens/src/server/tunnel.ts`, `crawfish-web/lib/tunnel-client.ts`, tests | Shared UI components (lead extracted them). |
| `auth+web` | `crawfish-web/app/api/auth/[...nextauth]/route.ts`, `crawfish-web/app/(dash)/orgs/[id]/{board,plan,wiki,analytics}/page.tsx`, tests | Tunnel code; component edits beyond mounting. |
| `deep-link` | `crawfish-app/src-tauri/src/protocol.rs` (register `crawfish://` URI scheme), `crawfish-web/app/(dash)/components/OpenInDesktop.tsx`, tests | `tauri.conf.json` — lead-only. |

---

#### Phase Parallel-C (weeks 11–13) — Collaboration

**Lead pre-work:**
- [ ] Write `docs/specs/presence-contract.md` and `docs/specs/comments-contract.md`.
- [ ] **Reconcile Yjs document schema with LATER²-W23.** Pick one Yjs doc shape that works for both human-facing drawer fields and agent-facing markdown files. Document in `docs/specs/crdt-contract.md` *before* either phase spawns.
- [ ] `superpowers:writing-plans` → plan.

**Team shape — 4 teammates:**

| Teammate | Owns | Forbidden |
|---|---|---|
| `invites` | `crawfish-lens/src/server/invites.ts`, `crawfish-web/app/(dash)/orgs/[id]/members/page.tsx`, tests | Presence/comments. |
| `presence` | `crawfish-lens/src/server/presence.ts`, `ui/components/PresenceAvatars.tsx`, tests | Invites/comments. |
| `comments` | `crawfish-lens/src/server/comments.ts`, `ui/components/CommentThread.tsx`, `crawfish-lens/src/server/notify.ts` (Resend integration), `crawfish-web/app/(dash)/notifications/page.tsx`, tests | Presence; CRDT. |
| `crdt-drawer` | Yjs integration in `ui/components/TaskDrawer.tsx` (description + criteria fields only), `crawfish-lens/src/server/subscriptions.ts`, tests | Other drawer regions. |

---

#### Phase Parallel-D (weeks 14–16) — Team mode + Stripe billing + public org pages

**Lead pre-work:**
- [ ] Set up Stripe test account; create products + prices; export to env.
- [ ] Write `docs/specs/billing-contract.md` — seat semantics, webhook idempotency, plan limits.
- [ ] `superpowers:writing-plans` → plan.

**Team shape — 3 teammates:**

| Teammate | Owns | Forbidden |
|---|---|---|
| `billing-be` | `crawfish-lens/src/server/billing.ts`, `crawfish-web/app/api/billing/webhook/route.ts`, seat-enforcement hook in `board.ts:enforceSeatLimit` (single new function), tests | Existing `board.ts` regions. |
| `billing-fe` | `ui/routes/Billing.tsx` (consumed by both Tauri and web), tests | Backend. |
| `audit+public` | `crawfish-web/app/(dash)/orgs/[id]/audit/page.tsx`, `crawfish-web/app/(public)/o/[slug]/page.tsx`, tests | Billing code. |

**End-of-parallel-track:** `crawfish.dev/v1` tag; flip pricing-page CTA from waitlist to live signup.

---

## 2 · Recurring per-phase checklist (the lead's loop)

Apply this **every** phase. It's the single source of truth for how a phase begins and ends.

- [ ] **Step 1: Brainstorm (optional, skip if ROADMAP is unambiguous)**

Invoke `superpowers:brainstorming`. Goal: lock the phase's user-visible behavior and the contract surface.

- [ ] **Step 2: Write the contract(s)**

Edit `docs/specs/<area>-contract.md` with the schema, REST shapes, and event types teammates will rely on. **No teammate edits this file** — they read it.

- [ ] **Step 3: Get human OK on the contract**

One round-trip. Plain English summary. Wait for "go."

- [ ] **Step 4: Write the bite-sized phase plan**

Invoke `superpowers:writing-plans`. Save to `docs/superpowers/plans/YYYY-MM-DD-<phase-id>.md`. Plan must list every task, every file, every test. **No placeholders.**

- [ ] **Step 5: Land lead-only prep commits**

Anything shared (CSS classes in `ui/tokens/globals.css`, new submodules, refactors extracting shared components) — commit on a fresh branch *before* spawning. Teammates inherit a clean tree.

- [ ] **Step 6: Spawn the team**

Use the §0.6 template. Specify ownership, forbidden files, model, plan-approval requirement.

- [ ] **Step 7: Observe + serialize**

Watch for `TeammateIdle` events. When the hook returns exit 2 (touched a lead-only file, type-check failed, off-plan), push the teammate back with feedback. Do not let bad work merge.

- [ ] **Step 8: Land registry edits**

Once all teammates report done, the lead writes the route-table / `registerRule` / `App.tsx` aggregator entries in one commit.

- [ ] **Step 9: Full build + test**

```
cd crawfish-lens && npx tsc -p tsconfig.json && npm test
cd ../crawfish-dash && npx tsc -p tsconfig.json && npm test
# (repeat per touched submodule)
```

- [ ] **Step 10: Code review**

Invoke `superpowers:requesting-code-review`. Address findings before merging.

- [ ] **Step 11: Finish the branch**

Invoke `superpowers:finishing-a-development-branch`. Pick: merge to main, open PR, or squash + tag.

- [ ] **Step 12: Tear down the team**

```
Ask <teammate-A> to shut down.
Ask <teammate-B> to shut down.
...
Clean up the team.
```

- [ ] **Step 13: Commit + tag (if milestone)**

Cut the tag declared in the ROADMAP if this phase closes a milestone (`v0.3`, `v0.4`, `v0.5`, `crawfish.dev/v1`).

---

## 3 · Concrete kick-off — what the lead does **this week**

The roadmap was reprioritized 2026-05-17 (today). To start NOW-W1, the lead executes the §2 checklist with these specifics:

- [ ] **Step 1 — Brainstorm:** skip. ROADMAP §NOW-W1 already pins scope (cycles, epics, activity feed, member ACL).
- [ ] **Step 2 — Contracts:** open `docs/specs/org-contract.md` and add:
  - `cycles.json` shape per org: `{cycles: [{id, name, starts_at, ends_at, planned_tokens, spent_tokens}]}`
  - Task fields: `cycle_id?: string`, `epic_id?: string`
  - Activity event kinds: `status_changed`, `assigned`, `linked`, `labeled`, `budget_breach`
  - Primary-assignee model: when a `task_created` event has `assignee.humanity === "human"` and an agent is later attached, the agent lands as `role: "contributor"` not `assignee`.
- [ ] **Step 3 — Human OK:** post a one-paragraph summary; wait for go.
- [ ] **Step 4 — Plan:** invoke `superpowers:writing-plans`, save to `docs/superpowers/plans/2026-05-19-now-w1-cycles-acl.md`. Plan must include:
  - Task 1: schema + types (TDD)
  - Task 2: Cycles REST (TDD)
  - Task 3: Activity events (TDD)
  - Task 4: Member ACL (TDD)
  - Task 5: Plan tab cycle picker (TDD)
  - Task 6: Drawer activity panel (TDD)
- [ ] **Step 5 — Lead prep:** none needed (no shared CSS, no new submodule). Skip.
- [ ] **Step 6 — Spawn:**

```
Create an agent team for NOW-W1 (Cycles + Epics + Activity + Member ACL). Spawn 3 teammates:
  - cycles-be: owns crawfish-lens/src/server/cycles.ts + types.ts (cycle fields only) + test/cycles.test.ts. Implements Tasks 1, 2 from docs/superpowers/plans/2026-05-19-now-w1-cycles-acl.md.
  - activity-be: owns crawfish-lens/src/server/activity.ts + validateActor() in board.ts + test/{activity,board-acl}.test.ts. Implements Tasks 3, 4.
  - plan-fe: owns crawfish-dash/web/src/routes/Plan.tsx + components/TaskDrawer.tsx (activity panel additive only) + CycleBudgetBar.tsx. Implements Tasks 5, 6.

Each teammate MUST:
  1. Read CLAUDE.md and AGENT-TEAMS.md before touching code.
  2. Read docs/specs/org-contract.md as their source of truth.
  3. Follow the bite-sized plan at docs/superpowers/plans/2026-05-19-now-w1-cycles-acl.md.
  4. Apply superpowers:test-driven-development for every task.
  5. SendMessage the lead before editing any file in CLAUDE.md's "Files that two teammates must NEVER edit simultaneously" list.
  6. Run `npx tsc --noEmit -p tsconfig.json` in the relevant submodule before claiming done.

Use Sonnet for each teammate. Require plan approval before any teammate writes code.
```

- [ ] **Step 7 — Observe.**
- [ ] **Step 8 — Lead registry edit:** add `cycles` and `activity` route registrations to `crawfish-lens/src/server/index.ts`.
- [ ] **Step 9–12 — close-out per §2.**
- [ ] **Step 13 — no tag yet** (`v0.3` waits for end of NOW-W5).

---

## 4 · Self-review (run by the lead before treating this playbook as final)

- [x] **Spec coverage:** every ROADMAP phase (NOW-W1 through Stage 2 prep + all 4 Parallel-Track sub-phases) has a §1 entry with team shape, ownership, lead-only files, and handoff.
- [x] **Placeholder scan:** no "TBD" / "TODO" / "see appendix" / "fill in details" / unspecified teammate counts.
- [x] **Type/name consistency:** teammate role names (`cycles-be`, `tunnel`, `crdt-drawer` etc.) are unique within their phase; cross-phase reuse (e.g. `crdt-drawer` Parallel-C ↔ `crdt-yjs` LATER²-W23) is explicitly flagged with a reconciliation note in Parallel-C pre-work.
- [x] **Superpowers usage:** `brainstorming`, `writing-plans`, `subagent-driven-development` (implicit via team spawn), `test-driven-development`, `verification-before-completion`, `requesting-code-review`, `using-git-worktrees`, `finishing-a-development-branch` are all named at the point they apply. No skill is invoked without context.
- [x] **AGENT-TEAMS.md compliance:** lead-only registries, build serialization, one-team-at-a-time, worktree usage, spawn-prompt template all match the doc.

---

## 5 · What this playbook deliberately does NOT do

- **It does not write the per-phase bite-sized plans now.** Those are written by the lead when the phase opens, via `superpowers:writing-plans`, against the live state of the repo. Writing them now would freeze interfaces against assumptions that won't hold by week 8.
- **It does not lock the human into a single execution mode.** The lead can swap a phase's team for a single subagent run (via `superpowers:subagent-driven-development`) when the phase is small enough — the §1 blueprints are upper bounds, not minimums.
- **It does not pre-allocate calendar time.** ROADMAP weeks are nominal. If NOW-W1 takes 3 days or 9 days, the next phase opens when the previous closes, not on a fixed date.

---

## Handoff

Plan saved to `docs/superpowers/plans/2026-05-17-roadmap-agent-team-execution.md`.

This is a **master playbook**, not a single executable plan. The execution choice happens *per phase*, not on the playbook itself.

**Next step (you, the lead):** when you're ready to open NOW-W1, follow §3 — it walks you all the way from "open the contract doc" to "spawn the team." That's the moment to invoke `superpowers:writing-plans` for the W1 sub-plan and `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` for the actual execution.
