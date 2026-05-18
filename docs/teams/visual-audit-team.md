# Visual Audit Team — full-app flow & redesign pass

> **Goal:** A full visual + UX audit of every user-facing surface in Crawfish, with permission to redesign aggressively where the current UI fails the user. The output is (1) a scorecard per surface, (2) a prioritized fix list, and (3) actual code changes — not just notes. We want a first-time user to walk the whole flow without confusion.
>
> Companion docs: [`CLAUDE.md`](../../CLAUDE.md) · [`AGENT-TEAMS.md`](../ops/AGENT-TEAMS.md) · [`DESIGN.md`](../product/DESIGN.md) · prior audit [`ui-audits/2026-05-18-org-workspace.md`](../ui-audits/2026-05-18-org-workspace.md).

---

## 1 · Why a team (not one Claude)

Crawfish has **four user-facing surfaces** that ship from different submodules and have different design vocabularies. One Claude auditing all four in one context would either (a) blow the window or (b) lose the mental model halfway through. One teammate per surface keeps each audit deep, and the lead serializes the cross-cutting work (shared tokens, naming consistency, IA decisions).

The surfaces share `ui/tokens/globals.css` and the `@crawfish/ui` primitives, but each owns its own routes, layouts, and empty states. So: 4 surface teammates, each owning one submodule path, plus a 5th cross-cutter who only touches `ui/`.

## 2 · Team shape

| Teammate | Owns (exclusive) | Forbidden | Model |
|---|---|---|---|
| `web-marketing` | `web/src/**` + `web/tests/**` | All other surfaces; `ui/` (request via lead) | sonnet |
| `platform-spa` | `cloud/platform/src/**` (auth, org/project import, OrgRoute) | All other surfaces; `cloud/server/`; `ui/` | sonnet |
| `dash-studio` | `desktop/dash/web/src/**` (Tauri studio: Canvas/Board/Plan/Sessions/Settings/etc.) | Other surfaces; `desktop/lens/`; `ui/` | sonnet |
| `dash-data-views` | `desktop/dash/web/src/routes/{Analytics,Knowledge,Diagnoses,Files,Crons,Compare,Benchmarks,HomeDashboard}.tsx` + their components | The Canvas/Board/Plan/Sessions/Settings cluster (owned by `dash-studio`); other surfaces | sonnet |
| `ui-tokens` (lead-only, see §4) | `ui/tokens/globals.css`, `ui/components/**` | n/a — only the lead writes here | n/a |

> The Dash studio is split in two because it has ~22 routes — splitting Canvas/Board/Plan/Sessions/Settings (the live-action surfaces) from Analytics/Knowledge/Diagnoses/Files/etc. (the data-view surfaces) keeps each teammate's context tight enough to do real redesigns rather than skim.

## 3 · What each teammate produces

For their surface, every teammate produces **three artifacts in this order**:

1. **`docs/ui-audits/2026-05-18-<surface>.md`** — scorecard + blockers + majors + polish + mock-data inventory + consistency gaps + recommendations. Mirror the format of [`2026-05-18-org-workspace.md`](../ui-audits/2026-05-18-org-workspace.md) verbatim.
2. **A code redesign of every P1 blocker** in their owned files. Big redesigns are allowed and encouraged where the surface is broken (e.g. Dash Canvas's seed-data leak from the prior audit). Big redesigns must:
   - Stay inside the brand: warm paper, vermillion, three typefaces, no dark mode, no glassmorphism. See [`DESIGN.md`](../product/DESIGN.md).
   - Use existing `@crawfish/ui` components and `ui/tokens/globals.css` classes — **never** hex literals, **never** new component-scoped `.css` files.
   - Type-check clean (`npx tsc --noEmit` from the submodule root) before claiming done.
   - Be committed in small, atomic commits with messages like `audit(<surface>): fix Canvas seed-data leak (P1)`.
3. **A flow walkthrough note appended to their audit md** — three sentences max: "First-time user lands on `/`. They are most likely to get stuck at X because Y. The fix in this commit addresses it by Z." This is what the lead uses to decide whether the flow is intuitive end-to-end.

## 4 · Lead's job

The lead is the orchestrator and the **only one who writes to shared files**.

Lead-only edits during this team run:
- Anything under `ui/tokens/globals.css` or `ui/components/**` (cross-cutting design system).
- Anything under `docs/product/DESIGN.md` (design contract; teammates may *propose* via SendMessage but only the lead writes).
- Anything under `docs/ui-audits/INDEX.md` (the audit index file, written at the end).
- Cross-surface IA decisions (e.g. "Dash and Platform should both show `{org.name}` as H1") — the lead drafts the rule, the teammates implement on their side.
- All builds (`npx vite build`, etc.). Teammates only run `tsc --noEmit`.

Lead's sequence:
1. Spawn 4 teammates with the assignments in §2.
2. Wait for all four audit mds to land.
3. Read all four mds in series. Extract cross-surface consistency gaps into a single `docs/ui-audits/2026-05-18-cross-surface.md`.
4. Make the cross-cutting fixes in `ui/` (add `--bad` token, extract shared components, etc.).
5. SendMessage each teammate the cross-cutting result so they can reconcile their local fixes.
6. Wait for each teammate's redesign commits.
7. Run `npx vite build` per submodule. Fix any build errors *yourself* — do not bounce teammates back unless a teammate's own code is the cause.
8. Write `docs/ui-audits/2026-05-18-summary.md` — one paragraph per surface plus a "would a new user complete the golden flow?" verdict.
9. `git status` + present the diff. Do **not** commit `ROADMAP.md`, `PRODUCT.md`, or `docs/product/DESIGN.md` changes without user OK.

## 5 · Skills to reach for (proactive, no slash needed)

Per [`CLAUDE.md`](../../CLAUDE.md) routing rules, each teammate should auto-invoke skills as they hit the matching situation:

- Polish / redesign / "this looks generic or AI-ish" on an existing surface → `impeccable`.
- Building a brand-new component (rare in this audit — most work is editing existing) → `frontend-design:frontend-design`.
- A specific element renders wrong ("the modal overflows", "this button is misaligned") → spawn `ui-diagnose` subagent.
- Whole-page accessibility / responsive QA on a running dev server → spawn `ui-auditor` subagent.
- Anything that touches Anthropic SDK calls — not expected in this run, but if encountered → `claude-api`.

Hard rules (from CLAUDE.md):
- **Never invoke more than one taste/design skill in the same turn.**
- **Never auto-invoke a skill that writes to disk without first stating in one sentence what you're about to do.**

## 6 · Scope guardrails

What this team **does**:
- Audit and redesign user-facing UI on the four surfaces.
- Fix mock-data leaks (e.g. fake "Pat" agent showing on every user's canvas).
- Tighten flows so a first-time user can complete: install → sign in → create org → import project → see real data populate, without a dead end.
- Add empty / loading / error states where they're missing.
- Wire up dead buttons or hide them (no more "looks primary, does nothing").

What this team **does not** do:
- Backend changes (`cloud/server/`, `desktop/lens/`, CLIs). Surface a missing endpoint via SendMessage to lead — don't try to implement it.
- New features beyond what's already on the screen.
- Dependency bumps.
- Touching `ROADMAP.md` / `PRODUCT.md` / `BRAINSTORM.md` / `INTEGRATIONS.md`.
- Anything under `dist/` or any generated files.

## 7 · Golden flow to keep in mind

Every teammate's redesigns must defend this end-to-end path:

1. **Marketing (`web/`)** — visitor lands at `crawfish.dev`, understands the pitch in 5 seconds, clicks "Download" or "Sign in".
2. **Platform (`cloud/platform/`)** — signs in with GitHub via Clerk, creates an Organization, imports one repo as a Project. Sees the project card with an "Init" or "Open in Dash" affordance.
3. **Dash studio (`desktop/dash/`)** — opens the desktop app, sees their org canvas populated with real members / agents (not seed `HUMAN_NODES`), navigates Board / Plan / Sessions without hitting a fake-data wall.
4. **Dash data views (`desktop/dash/`)** — opens Analytics / Knowledge / Diagnoses and sees empty states that say *"no data yet — do X"*, not seed numbers that lie.

If any teammate's surface breaks this path, fix it. If fixing requires a sibling surface to change too, SendMessage the relevant teammate.

## 8 · Tear-down

When all teammates are done, the lead:
1. Confirms `git status` is clean except for intended diffs.
2. Confirms all four submodule type-checks pass.
3. Runs `npx vite build` in each submodule that has one.
4. Asks each teammate to shut down, then "Clean up the team."
5. Hands the user a one-paragraph summary + the path to `docs/ui-audits/2026-05-18-summary.md`.
