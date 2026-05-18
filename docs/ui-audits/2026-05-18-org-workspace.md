# Org Workspace UI Audit — 2026-05-18

**Scope:** `cloud/platform/src/pages/OrgRoute.tsx` (read-only canvas) + `desktop/dash/web/src/routes/Canvas.tsx` (writable studio).

## Scorecard

| Dimension | Platform OrgRoute | Dash Canvas |
|---|---|---|
| Info architecture | 4/5 | 2/5 |
| Visual hierarchy | 3/5 | 3/5 |
| Empty / loading / error states | 4/5 | 2/5 |
| Visual polish | 3/5 | 3/5 |
| Real-vs-mock data | 4/5 | 1/5 |
| Responsive | 3/5 | 1/5 |
| Accessibility | 3/5 | 2/5 |
| **Overall** | **24/35** | **14/35** |

Platform reads as a calm, correct, intentionally minimal landing surface. Dash Canvas reads as a hi-fi mockup that was wired to real data only at the edges — the bulk of the canvas (edges, KPIs, trace fallback, header subtitle, token-flow chip) is still seed data shown to real users.

## Blockers (must-fix)

- [P1] `Canvas.tsx:400-405` — Six SVG `<path>` edges are hardcoded with absolute coordinates that no longer correspond to actual agent positions once a user drags or once a non-seed org loads. The comment even says "Wave 2 will derive from agent topology." Fix: hide the SVG entirely when `orgAgents` is non-null, or render `null` until topology data exists.
- [P1] `Canvas.tsx:430-441` — The "+412 tok · $0.014" token-flow chip is fixed at `left: 250, top: 178` regardless of node positions or activity. It floats over wherever and lies about throughput. Fix: remove until live trace can compute it; or anchor to the streaming edge.
- [P1] `Canvas.tsx:500-513` — Right-rail KPIs are literal strings: `$3.14 / $25`, `13%` bar, `92%` success, `+4`. Real users see these regardless of org. Fix: gate behind `orgAgents != null` and replace with a "no data yet" eyebrow until backend exposes them.
- [P1] `Canvas.tsx:363-364` — Fallback header subtitle is `"5 members · 1 active right now · last task completed 6 min ago"` when there's no org loaded. Fix: replace with `"No org loaded — open ?org=<name>"` or hide.
- [P1] `Canvas.tsx:525-535` — "Add a /healthz endpoint · CRWF-118" current-task block is hardcoded. The progress bar fills `34%` / `100%` from a literal. Fix: render this block only when a real task is streaming, with an empty state otherwise.
- [P1] `Canvas.tsx:36-66` — `HUMAN_NODES` (You, Pat) and `seedTrace` are always merged into the rendered list even with a real org (`agents = [...HUMAN_NODES, ...orgAgents]`, line 223). "Pat" appears on every user's canvas. Fix: drop `HUMAN_NODES` from the merged list; only show "You" sourced from `useCurrentUser()`.

## Majors (should-fix before next release)

- [P2] `Canvas.tsx:444-470` — Zoom controls and "compounding factor 1.0×" legend are non-functional (no `onClick`). Either wire them or remove.
- [P2] `Canvas.tsx:391-393` — "Invite human" and "Hire agent" buttons have no `onClick`. Buttons that look primary but do nothing erode trust. Fix: wire or disable with a tooltip.
- [P2] `Canvas.tsx:397, 414` — `position: "absolute"` everywhere with no responsive fallback. Below ~960px wide the canvas overflows horizontally and the right rail eats most of the viewport. Fix: collapse rail under `@media (max-width: 960px)`, switch agents to flex-wrap like OrgRoute does.
- [P2] `Canvas.tsx:413-417` — Draggable nodes are `<div onPointerDown>` with no keyboard handler, no `role`, no `aria-grabbed`. Fix: add `role="button"`, `tabIndex={0}`, and arrow-key nudge as a follow-up.
- [P2] `OrgRoute.tsx:138-149` — "← Back to all orgs" is a `<Link>` but visually styled like body text. Fix: add hover/focus underline and bump weight slightly so it reads as a control.
- [P2] `OrgRoute.tsx:289-304` — Every agent after index 0 gets `variant="neutral"` so all agents render visually identical. With 6+ agents the grid is a wall of identical pills. Fix: vary by role/runtime, or stop coloring index 0 specially and instead use the `accent` variant for the agent the viewer most recently interacted with.
- [P2] `Canvas.tsx:553` — `var(--bad, #b1452f)` falls back to a hex literal because `--bad` isn't defined in tokens (only `--good` is). Fix: add `--bad` to `ui/tokens/globals.css` and drop the hex fallback.

## Polish (nice-to-have)

- [P3] `OrgRoute.tsx:38-40` — Every stubbed sub-tab renders a "scaffold · wire later" pill. Real users on Board / Sessions / Knowledge / Diagnoses / Billing / Settings see this. Fix: replace with a calm "Coming soon — Dash is where this lives today" CTA that links to Dash, matching the read-only banner tone.
- [P3] `OrgRoute.tsx:107-109` — Loading state is just `"loading…"` in mono. The error state is a full page with H1 + CTA, but loading is a single line. Fix: render the header skeleton during loading so the page doesn't jump.
- [P3] `Canvas.tsx:482` — Selected-agent avatar is a vermillion square with the first letter — fine, but it bypasses the `Avatar` component used in OrgRoute. Fix: use `@crawfish/ui/components/Avatar` for consistency.
- [P3] `Canvas.tsx:573-586` — "Pause", "Stop & refund", "Open PR ↗" are all disabled stubs. Either implement or hide for MVP.
- [P3] `OrgRoute.tsx:26-36` heading style is reproduced verbatim three times. Extract a `<PageTitle>` from `@crawfish/ui`.

## Consistency gaps (platform ↔ dash)

- **Header**: Platform shows `Org name · canvas` with member/agent counts and an "Open in Dash" CTA. Dash shows `"The studio"` as the H2 with the org name demoted to a Pill. The Dash version reads as a designer's title; the Platform version reads as a user's title. Recommend Dash also show `{org.name}` as the H2, with "studio" as the eyebrow, mirroring Platform.
- **Agent layout**: Platform uses `flex-wrap` so agents reflow on narrow viewports. Dash uses absolute positioning. Recommend Dash fall back to flex-wrap when `window.innerWidth < 960`, or always when there are no saved positions.
- **Variant logic**: Platform makes `i === 0` accent; Dash makes `i === 0` accent + live + selected. Recommend a single rule defined in `lib/orgs.ts` and consumed by both.
- **Empty state**: Platform shows "No agents in this org yet." Dash falls back to a demo with "Eng-bot/Designer-bot/Support-bot/Ops-bot" — a real user on Dash with an empty org sees four fake agents. Recommend Dash use the same empty state as Platform when `orgAgents.length === 0`.

## Mock-data inventory

Every hardcoded value visible to the user:

- `Canvas.tsx:37-39` — `HUMAN_NODES` "You" / "Pat" — should come from `/api/orgs/:id/members` joined with current user.
- `Canvas.tsx:43-49` — `seedAgents` Eng-bot / Designer-bot / Support-bot / Ops-bot — should be hidden when no `?org=` is set, not used as fallback.
- `Canvas.tsx:59-66` — `seedTrace` rows with fixed `12:04:11` timestamps — should be empty array until a session streams.
- `Canvas.tsx:69-71` — `DEMO_TASK` literal — fine for the demo button, but the task title `"Add a /healthz endpoint"` (line 525) duplicates this and is shown as the "current task" without context.
- `Canvas.tsx:364` — `"5 members · 1 active right now · last task completed 6 min ago"` — fallback subtitle.
- `Canvas.tsx:384` — `"org · canvas"` fallback pill — innocuous but visible.
- `Canvas.tsx:400-405` — six SVG path strings with absolute coords (the edges the user flagged).
- `Canvas.tsx:431-440` — `+412 tok`, `$0.014` floating chip.
- `Canvas.tsx:452` — zoom level `100%` literal (control doesn't zoom).
- `Canvas.tsx:469` — `compounding factor 1.0×` legend literal.
- `Canvas.tsx:501-502` — `$3.14 / $25` weekly budget.
- `Canvas.tsx:504` — `width: "13%"` budget bar fill.
- `Canvas.tsx:509-510` — `92%` success, `+4` delta.
- `Canvas.tsx:512` — `width: "92%"` success bar fill.
- `Canvas.tsx:525` — `"Add a /healthz endpoint"` current-task title.
- `Canvas.tsx:527` — `"CRWF-118"` ticket id.
- `Canvas.tsx:531` — progress bar `34%` / `100%` / `70%` literals.
- `Canvas.tsx:534` — `"$0.14 / $0.40"` cost fallback.
- `OrgRoute.tsx:79-80` — `DEFAULT_GRID_Y = 252`, `DEFAULT_GRID_XS = [84, 328, 572, 816]` — unused after the flex-wrap refactor (lines 280-305 use flex-wrap with `gap: 20`). Dead constants; remove.

## Recommendations

The single most leveraged changes, in order:

1. **Quarantine the demo data in Dash Canvas behind a `?demo=1` flag.** Right now seed agents, seed trace, seed KPIs, hardcoded edges, fake current task, and fake token chip all render unconditionally when no `?org=` is supplied — and several still render even when one is. One flag would clean up 90% of the P1s.
2. **Move edges, KPIs, current-task block, and token-flow chip to render only when their data exists.** Each becomes an empty-state component until backed by real data. Match Platform's "No agents in this org yet." tone.
3. **Unify the canvas header between Platform and Dash.** Same H1 (`{org.name}`), same eyebrow (`{org.name} · canvas` vs `studio`), same member/agent count subline. Drop "The studio" branding from the chrome.
4. **Make Dash Canvas responsive.** Replace absolute positioning + sidebar rail with a flex-wrap layout below 960px, mirroring Platform. Today a phone or split-screen viewport sees a broken canvas.
5. **Define `--bad` in `ui/tokens/globals.css`** and remove the inline hex fallback at `Canvas.tsx:553`. Tiny but emblematic — every other color in both files goes through tokens.
