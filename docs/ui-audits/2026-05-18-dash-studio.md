# Dash Studio UI Audit — 2026-05-18

**Scope:** `desktop/dash/web/src/routes/` — Canvas.tsx, Board.tsx, Plan.tsx, sessions.tsx, SessionDetail.tsx, AgentCanvas.tsx, Org.tsx, Settings.tsx, Home.tsx — plus `desktop/dash/web/src/components/**`.

**Canvas.tsx reconciliation note:** The six P1 blockers identified in the 2026-05-18-org-workspace audit were fully resolved in commit `590f244` ("feat(dash): retire mock data from Canvas — 5 P1 blockers resolved"). `HUMAN_NODES` injection is removed (comment at line 231 confirms), the seeded header subtitle is gone (line 404), hardcoded KPIs are gated, and the `seedTrace` is now a fallback-only display trace (`liveTrace ?? [...seedTrace]`). These items are **not re-opened here**. The remaining `seedTrace` fallback shown when no org is connected is acceptable — it is demo data for an empty/offline state, not a data lie to authenticated users.

## Scorecard

| Dimension | AgentCanvas | Board | Plan | Sessions | SessionDetail | Org | Settings | Home |
|---|---|---|---|---|---|---|---|---|
| Info architecture | 3/5 | 4/5 | 4/5 | 4/5 | 4/5 | 4/5 | 4/5 | 4/5 |
| Visual hierarchy | 3/5 | 4/5 | 4/5 | 4/5 | 4/5 | 3/5 | 3/5 | 4/5 |
| Empty / loading / error states | 2/5 | 4/5 | 4/5 | 5/5 | 4/5 | 4/5 | 4/5 | 4/5 |
| Visual polish | 3/5 | 4/5 | 4/5 | 4/5 | 4/5 | 3/5 | 3/5 | 4/5 |
| Real-vs-mock data | 1/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 |
| Responsive | 2/5 | 3/5 | 3/5 | 4/5 | 4/5 | 3/5 | 3/5 | 4/5 |
| Accessibility | 2/5 | 3/5 | 4/5 | 4/5 | 4/5 | 3/5 | 3/5 | 4/5 |
| **Overall** | **16/35** | **27/35** | **28/35** | **30/35** | **29/35** | **25/35** | **25/35** | **29/35** |

Most of the studio cluster is in good shape — Board, Plan, Sessions, and SessionDetail are near-production quality with real data, proper empty/error states, and no mock leaks. `AgentCanvas.tsx` is the critical outlier: it is an unreleased hi-fi scaffold whose seeded data (hardcoded task list, rail KPIs, fabricated agent description) would be shown to real users navigating to `/canvas/:id` today. Settings and Org have minor polish debts. Plan carries stale `--cf-*` legacy token calls throughout inline styles (technically shimmed, but authoring violations per DESIGN.md).

## Blockers (must-fix)

- [P1] `AgentCanvas.tsx:24-29` — `seedTasks` array is defined at module scope and always rendered on "Overview" and "History" tabs (line 87). Every user navigating to any agent detail page sees the same four fake tasks (`CRWF-118`, `CRWF-117`, `CRWF-116`, `CRWF-114`). Fix: fetch real tasks from `/api/orgs/:orgId/agents/:agentId/tasks` and gate the task list behind the result; show `EmptyState` with a `cf-spinner` while loading, and an idle-state eyebrow ("No tasks yet") when the list is empty.

- [P1] `AgentCanvas.tsx:108,111,117,120` — Rail KPIs (`$3.14`, `42.8k`, `13%`, `62%`) are hardcoded string and width literals in the right rail, visible to every user on every agent regardless of actual spend or token usage. This is the exact same class of bug as the Canvas.tsx KPI leak that was already fixed. Fix: fetch from `/api/orgs/:orgId/agents/:agentId/stats` and replace with a skeleton/empty state until data arrives; remove `style={{ width: "13%" }}` / `style={{ width: "62%" }}` literals entirely.

- [P1] `AgentCanvas.tsx:71-72` — Agent description is a hardcoded string ("Routes backend tickets through capability lookup, opens PRs against the org repo, and posts back to the board with budget receipts. Hired 14 days ago.") rendered for every agent regardless of their actual role or hire date. Fix: source description and hire date from the agent object returned by the API; show an `<Eyebrow>No description</Eyebrow>` fallback when blank.

- [P1] `AgentCanvas.tsx:75-76` — "Attach shell" and "Assign task" are `<button>` elements with no `onClick`, no `disabled`, and no tooltip. The primary-styled "Assign task" button does nothing on click — erodes trust more than removing it would. Fix: either wire to the planned task-assignment drawer, or add `disabled title="Coming soon"` until the endpoint exists.

## Majors (should-fix before next release)

- [P2] `AgentCanvas.tsx:50` — Avatar background uses hex literal `#f7f3ea` (warm paper color). Should be `var(--paper)`. Same hex appears in `Settings.tsx:298` for the linked-account avatar. Fix: replace both with `var(--paper)`.

- [P2] `Plan.tsx:76-77, 85-86, 232, 236, 252, 256, 264, 268, 453, 671, 799-801` — Thirteen inline `var(--cf-*)` token calls use the legacy shim namespace. All resolve correctly through globals.css shims, so there is no visual breakage, but DESIGN.md authoring rules explicitly say "Never write a new `--cf-*` variable." These must migrate to the canonical namespace (`--paper-2`, `--accent`, `--r-xs`, `--r-sm`, `--rule`, `--ink-faint`) before the shim layer is retired. Fix: systematic find-and-replace in Plan.tsx only; no other files need changes.

- [P2] `AgentCanvas.tsx` — No loading or error state at the route level. If the API call to fetch agent data fails, the seed data remains visible rather than showing an error. Fix: add `loading` / `error` state to the `AgentCanvasRoute` component, render `EmptyState` on error.

- [P2] `AgentCanvas.tsx:32` — Default param `id = "eng-bot"` means a direct navigation to `/canvas/` (no agent ID) silently uses a fake agent ID as the API key. Fix: if `id` is undefined, redirect to `/canvas` or render an `EmptyState` prompting the user to select an agent.

- [P2] `Org.tsx` — The tab navigation (members / canvas / knowledge / analytics / crons / settings) renders five tabs whose content areas are either live or route-redirects, but the visual active-tab indicator uses only `fontWeight` change — no underline, no color shift. Contrast ratio between active and inactive is below 3:1. Fix: add `border-bottom: 2px solid var(--accent)` on the active tab item (matching the cf-toggle pattern used elsewhere).

- [P2] `Settings.tsx` — The "Link" CTA in the org list is an inline `<button>` with raw `style` overrides rather than using the `cf-btn` class. Typography (`fontSize: 12`) and padding (`"6px 10px"`) are one-offs that don't track the 4px grid. Fix: replace with `<button className="cf-btn cf-btn--sm">Link</button>`.

## Polish (nice-to-have)

- [P3] `AgentCanvas.tsx` — Tabs "Capabilities", "Knowledge", and "Librarian" render a centered `"<tab> surface coming soon."` message using raw inline `div` with `fontSize: 13`. This is correct behavior but the text does not use the `.cf-fg-secondary` semantic class — it uses `color: "var(--ink-mute)"` inline. Consolidate to `<div className="cf-text-sm cf-fg-secondary">`.

- [P3] `Sessions.tsx` — The live-session pulse dot (`width: 6, height: 6, background: var(--accent)`) uses raw inline style. A reusable `.cf-pulse` class in globals.css would make this pattern available to Board and AgentCanvas as well.

- [P3] `Plan.tsx` — The `TaskDetailPanel` comment block uses `var(--cf-bg)`, `var(--cf-radius-md)`, and `var(--cf-border)` — the shim names appear in user-visible comment markup (lines 799-801). Consolidate to `var(--paper)`, `var(--r-sm)`, `var(--rule)`.

- [P3] `Home.tsx` — `cf-org-list__row` uses a raw `<div>` with `role="button"` and `onClick`. Prefer a genuine `<button>` element for keyboard accessibility (Tab-focus + Enter/Space) without the need for an `onKeyDown` handler.

- [P3] `Board.tsx` — No `--cf-*` legacy usage found. Clean. Minor: the kanban column empty state ("No tasks in this column") would benefit from an illustration matching the `Spot.tsx` pattern used in Sessions.

## Consistency gaps (studio ↔ brand)

- `AgentCanvas.tsx` right rail uses `cfp-stat__bar` / `cfp-stat__fill` classes — these are `cfp-*` prefixed (the old "crawfish platform" namespace) rather than `cf-*`. Confirm these classes are defined in globals.css; if not, they are silently no-op and the progress bars render as zero-height divs. (Note: `cfp-btn`, `cfp-shell__*`, `cfp-stat__*` appear to be legacy class names from a pre-merge naming convention — the cross-cutter teammate should audit globals.css for `cfp-*` completeness.)

- `AgentCanvas.tsx` breadcrumb uses raw inline `fontSize: 12.5` — a non-4px-grid value. Should be `13px` (closest step) or use the `.cf-text-xs` class.

- `Plan.tsx` progress bars use `borderRadius: 4` raw value — should be `var(--r-xs)` (4px, same value but now tracked by the token system).

- `SessionDetail.tsx` loading state uses `<div className="cf-empty">` instead of `<EmptyState>` — inconsistent with Sessions, Home, and Org which all use the `EmptyState` component. Fix: replace the loading `div` with `<EmptyState title="Loading session…" body={<span className="cf-spinner" />} />`.

## Mock-data inventory

| File | Mock-data item | Severity | Status |
|---|---|---|---|
| `AgentCanvas.tsx:24-29` | `seedTasks` array (4 fake tasks) always rendered | P1 | Open |
| `AgentCanvas.tsx:108,111,117,120` | Rail KPIs `$3.14`, `42.8k`, `13%`, `62%` hardcoded | P1 | Open |
| `AgentCanvas.tsx:71-72` | Agent description + "Hired 14 days ago" hardcoded | P1 | Open |
| `Canvas.tsx:60-90` | `seedTrace` rows used as fallback when no org | P2 | Acceptable — offline/demo fallback, not a data lie |
| `Board.tsx` | None found | — | Clean |
| `Plan.tsx` | None found | — | Clean |
| `Sessions.tsx` | None found | — | Clean |
| `SessionDetail.tsx` | None found | — | Clean |
| `Org.tsx` | None found | — | Clean |
| `Settings.tsx` | None found | — | Clean |
| `Home.tsx` | None found | — | Clean |

## Recommendations

1. **Gate `AgentCanvas.tsx` behind a data fetch before merging to main.** The route is currently accessible and shows fabricated data to any authenticated user. Either add a feature flag or complete the API wiring (P1s above) before the route appears in the nav.

2. **Migrate Plan.tsx `--cf-*` inline styles in one focused commit.** The shim layer works today but adds maintenance risk when the shim is eventually removed. A single pass through Plan.tsx to replace ~13 occurrences takes under 30 minutes and eliminates the technical debt.

3. **Audit `cfp-*` class completeness.** AgentCanvas uses `cfp-stat__bar`, `cfp-stat__fill`, `cfp-shell__rail`, and `cfp-btn` — the cross-cutter teammate should confirm all `cfp-*` classes are defined in globals.css and not silently orphaned.

4. **Standardize loading states.** SessionDetail uses a raw `<div className="cf-empty">` while every other route uses `<EmptyState>`. Standardize on `EmptyState` so the loading experience is consistent across the studio cluster.

---

## Phase 2 execution note — 2026-05-18

All five approved scope items were executed and landed in commit `cc43ac8` (desktop/dash submodule). A user navigating to the AgentCanvas route now sees a clean empty-state surface: the hero renders the agent's id initial in an ink tile using `var(--paper)` for contrast (no hex literal), the description area shows `<Eyebrow>No description yet</Eyebrow>`, and both action buttons are `disabled` with `title="Coming soon"`. The right rail's Budget, Tokens, and Librarian sections each display a `cf-mono` muted placeholder ("No spend data yet" or "—") instead of the fabricated $3.14 / 42.8k / 62%-bar figures; the overview and history tabs show "No tasks yet." rather than the four seeded `CRWF-*` task rows. The `#f7f3ea` hex was removed from both AgentCanvas and the Settings AccountPanel avatar, replaced with `var(--paper)` in both locations; `npx tsc --noEmit` completed with zero errors.

5. **No dev server was started for live QA.** The Dash dev server was not running at audit time; this audit is based on static code analysis only. Before Phase 2 execution, confirm the dev server is available (`cd desktop/dash && npx vite dev`) for manual verification of AgentCanvas mock-data fixes.
