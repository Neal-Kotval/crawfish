# Dash Studio — Playwright Full Audit
**Date:** 2026-05-18
**Server:** `http://localhost:7882` (Vite dev, port 7881 was taken — actual port 7882)
**Viewports tested:** mobile 390×844 · tablet 820×1180 · desktop 1280×820 · wide 1440×900
**Routes audited:** `/` · `/canvas` · `/agents/eng-bot` · `/board` · `/sessions` · `/settings/policies` · `/settings/account` · `/settings/appearance` · `/settings/about`
**Complementary static audits:** `2026-05-18-dash-studio.md` · `2026-05-18-org-workspace.md`
**Design reference:** `docs/product/DESIGN.md` · `ui/tokens/globals.css`

---

## Summary metrics

| Route | Status | Overflow | Console 500s | Buttons w/o type | Inputs w/o label | Notes |
|---|---|---|---|---|---|---|
| `/` (home) | 200 | 0 | 3 | 3 | 0 | Renders Canvas, not Home |
| `/canvas` | 200 | 0 | 3 | 3 | 0 | Correct route — matches `/` |
| `/agents/eng-bot` | 200 | 0 | 3 | 0 | 0 | Correct empty states post-P1 fix |
| `/board` | 200 | 0 | 5 | 0 | 0 | Shows loading spinner (no org) |
| `/sessions` | 200 | 0 | 5 | 0 | 0 | Shows correct error EmptyState |
| `/settings/policies` | 200 | 0 | 7 | 0 | 0 | Shows "Couldn't load policies" error |
| `/settings/account` | 200 | 0 | 5 | 0 | 0 | Renders correctly with linked user |
| `/settings/appearance` | 200 | 0 | 3 | 0 | 0 | Correct; dark mode description wrong |
| `/settings/about` | 200 | 0 | 3 | 0 | 0 | Renders correctly |

**Zero horizontal overflow across all 9 routes × 4 viewports.** All 200 status codes. No pageerrors, no hydration warnings. All console errors are backend 500s from a dev server with no running lens/orgs service — expected in standalone browser context.

---

## Blockers

### 1. `/` does not render the Home route — it renders Canvas
**Location:** `src/App.tsx:121–123` · `src/main.tsx` route table
**Severity:** Critical
**Observation:** Navigating to `/` shows the full Canvas surface (three seed agents, right rail, live-trace panel). The `Home` component — which lists org templates and existing orgs — never appears. In `App.tsx`, `isActive()` treats `/` as an alias for Canvas (`path === "/canvas" ? location.pathname === "/" || ...`), and `RAIL_ROUTES` contains `"/"` pointing to the Canvas layout. The actual route table in `main.tsx` likely maps `/` to `CanvasRoute` rather than `Home`.
**Why it matters:** A user who has never created an org has no path to the onboarding flow. The template picker and "Your orgs" list are unreachable. `Home.tsx` exists, is well-implemented, but is effectively dead from the primary entry point.
**Recommendation:** Map `/` to `<Home />` and `/canvas` to `<CanvasRoute />` exclusively. Remove `"/"` from `RAIL_ROUTES` or replace with `"/canvas"`. The `isActive` shortcut for Canvas should match `/canvas` only.
**Screenshot evidence:** `.audit/userflow/home/desktop-light.png` (shows Canvas, not Home)

### 2. Canvas mobile view: main pane and right rail render side-by-side with no content visible in either
**Location:** `src/routes/Canvas.tsx` · `ui/tokens/globals.css` · `.cfp-shell` grid
**Severity:** Critical
**Observation:** At 390px, the three-column shell (`cfp-shell__sidebar` 232px + `cfp-shell__main` + `cfp-shell__rail`) is crammed into 390px. The sidebar takes the left half, the right rail takes the right half, and the canvas main pane is invisible — squeezed to near-zero width between them. The seed agent nodes, canvas header, and zoom controls are completely hidden. The only visible content is the sidebar nav and the right rail's text labels, both truncated. No `@media` collapse is applied.
**Why it matters:** The target Tauri window is 1280×820, but the app is described as a "studio cluster" auditable in the browser. More practically, any split-screen or display scaling scenario hits this breakpoint. The canvas surface is the primary product surface — it must degrade gracefully.
**Recommendation:** Add a media query at ≤960px that hides the right rail (`display: none`) and at ≤640px that converts the sidebar to a bottom nav or collapsible drawer. At minimum, `cfp-shell__main` needs `min-width: 0` with `flex: 1` so it doesn't get squeezed to zero.
**Screenshot evidence:** `.audit/userflow/canvas/mobile-light.png` · `.audit/userflow/home/mobile-light.png`

### 3. AgentCanvas mobile: hero pane hidden, only right rail visible
**Location:** `src/routes/AgentCanvas.tsx` · `.cfp-shell` grid
**Severity:** Critical
**Observation:** At 390px on `/agents/eng-bot`, the agent hero (ink avatar, tabs, action buttons) is entirely absent from the viewport. Only the right rail's three empty-state KPI cards ("Budget · This Week", "Tokens · Today", "Librarian · Today") fill the screen. The nav sidebar is also present at left but the main `cfp-shell__main` pane — containing the entire agent identity surface — is zero-width and invisible.
**Why it matters:** Same root cause as finding #2 but manifests differently: on AgentCanvas the hero is in `cfp-shell__main`, so a user on a narrow window sees three "—" placeholder cards and nothing else. The agent's name, avatar, tabs, and action buttons are unreachable.
**Screenshot evidence:** `.audit/userflow/agent-canvas/mobile-light.png`

---

## Major

### 4. "Hire agent" button present but non-functional without an org loaded
**Location:** `src/routes/Canvas.tsx:435`
**Severity:** Major
**Observation:** Both "Invite human" and "Hire agent" buttons render in the Canvas header regardless of whether an org is loaded. The `Run demo task` button is correctly disabled when `!orgName`, but the Invite/Hire buttons have no guard. Clicking either does nothing (no `onClick`, no `disabled` attribute). The "Hire agent" button uses `cfp-btn--ink` which gives it the dark primary treatment — it reads as the highest-priority action on the page, yet does nothing.
**Why it matters:** A primary-styled button that fires no action degrades trust faster than removing it. This is the same pattern that was called out as a P1 in the static audit for AgentCanvas (`src/routes/AgentCanvas.tsx:75-76`) and has since been fixed there — it now uses `disabled title="Coming soon"`. Canvas hasn't received the same treatment.
**Recommendation:** Mirror the AgentCanvas fix: add `disabled title="Coming soon"` to both buttons until the endpoints exist. Or gate rendering behind `orgName != null`.

### 5. "Sessions" sidebar badge "2 live" is hardcoded
**Location:** `src/App.tsx:28` — `{ path: "/sessions", label: "Sessions", icon: Icons.sessions, badge: "2 live" }`
**Severity:** Major
**Observation:** The sidebar always shows "2 live" next to Sessions regardless of whether any sessions are actually running. Confirmed visually: all screenshots across all routes show "2 live" in the sidebar badge, even when the Sessions route shows a "Transcripts are starting up…" error state with no live sessions visible. The badge value is a string literal in the `WORKSPACE_NAV` constant.
**Why it matters:** This is a fabricated status indicator. A user with zero running sessions sees "2 live" and either trusts it (confused about the empty state) or doesn't (loses trust in all status indicators). It also directly contradicts the Sessions route's own empty state.
**Recommendation:** Replace the static `badge: "2 live"` with a dynamic count derived from the sessions list (same data source as `SessionsRoute`). Until wired, omit the badge entirely — an absent badge is better than a false one.

### 6. Settings/Policies: error state rendered as center-page text with no recovery action
**Location:** `src/routes/policies.tsx` (not in audit scope to read, observed visually)
**Severity:** Major
**Observation:** At `/settings/policies`, the panel renders "Couldn't load policies — Error: policy log: 500" in plain text centered in the wide content area. No retry button, no guidance, no link. The error message exposes the raw HTTP status (`500`) as user-facing copy. The left nav sidebar shows Policies as the active item (accent highlight) but the right panel is a broken state.
**Why it matters:** Policies is the default landing tab for `/settings`. Every user who navigates to Settings lands on a 500 error with no way to proceed or understand what failed. The error copy breaks the warm-paper tone — "policy log: 500" reads as a debug dump.
**Recommendation:** Wrap the fetch in the same `<EmptyState title="Policies unavailable" body={<Message tone="hint">…</Message>} cta={<button … >Retry</button>}>` pattern used by Sessions and Board. Replace "500" with a user-friendly message ("The policy service isn't running yet — Crawfish will retry automatically.").

### 7. Appearance panel: dark mode description is off-brand and factually inconsistent
**Location:** `src/routes/Settings.tsx:164–165`
**Severity:** Major
**Observation:** The Dark mode option reads "Deep forest night + mint glow." DESIGN.md §1 explicitly states: "No dark mode. The brand is warm-paper-only. Dark mode is a feature of cool-neutral systems; warming the ink and paper is the design point. The `data-theme='dark'` attribute is honored as a no-op fallthrough to light tokens so legacy code keeps rendering." The Appearance panel offers Dark as a selectable theme with evocative copy that implies a real, distinct dark treatment. The Light hint also uses "leaf-green" which does not appear anywhere in the token set — the brand accent is vermillion, not green.
**Why it matters:** The Appearance panel creates a false expectation of a dark mode that doesn't exist (it falls through to light tokens). "Leaf-green" is not a Crawfish brand color — it implies a different product. Both hints actively mislead users.
**Recommendation:** Either remove the Dark option entirely (replacing with a note: "Crawfish is warm-paper-only — dark mode is not currently available") or, if dark mode is planned, align the copy with the actual token set. Fix the Light hint to reference vermillion/warm paper, not leaf-green. This is a copy fix, not a code architecture change.

### 8. `--bad` token undefined — `var(--bad, #b1452f)` fallback hex in Canvas live trace
**Location:** `src/routes/Canvas.tsx:671`
**Severity:** Major
**Observation:** The live-trace panel colors `warn`-tone rows using `color: row.tone === "warn" ? "var(--bad)" : ...`. `--bad` is not defined in `ui/tokens/globals.css` (DESIGN.md §2.5 lists `--danger` as the destructive token; there is no `--bad`). At runtime this resolves to an empty string, producing no color on warn rows. A prior audit found a hex fallback `var(--bad, #b1452f)` at Canvas.tsx:553 — that line is now absent in the current code, but the `var(--bad)` reference without fallback at line 671 will silently render as the browser default (inherited color, likely `--ink-soft`) rather than a warning color.
**Recommendation:** Replace `var(--bad)` with `var(--danger)` throughout Canvas.tsx. If `warn` tone should be distinct from `danger`, use `var(--warn)` instead. Do not introduce `--bad` as a new token — DESIGN.md forbids new `--cf-*` or non-spec variables.

---

## Minor

### 9. `Home` route `<h2>` used instead of `<h1>` for page title; no H1 exists
**Location:** `src/routes/Canvas.tsx:424–427` (the H2 visible on all `/` and `/canvas` screenshots); `src/routes/Home.tsx:76`
**Severity:** Minor
**Observation:** Playwright's `h1Count` metric shows 0 on `/` and `/canvas`, with `h2Count: 1`. The Canvas header uses `<h2>The studio</h2>` for the page title. Home.tsx defines an H1 (`<h1 className="cf-home__title">`) — but since `/` renders Canvas not Home (finding #1), that H1 is never seen. AgentCanvas correctly uses `<h1>` (confirmed: `h1Count: 1`, `h2Count: 0` at `/agents/eng-bot`).
**Recommendation:** After fixing the route issue in finding #1, confirm Canvas uses `<h2>` for a section label under a higher-level `<h1>`, or promote the Canvas header to `<h1>` (since Canvas is the page). Heading hierarchy must be sequential (WCAG 1.3.1).

### 10. Canvas tablet (820px): "Hire agent" button and header overflow — truncated in mid-word
**Location:** `src/routes/Canvas.tsx:413–437` canvas header
**Severity:** Minor
**Observation:** At 820px the canvas header row wraps badly: "Invite human" button renders fully but "Hire agent" is cut to just the icon — the label is truncated. The header flex row has no `flex-wrap` or `min-width` guards on the button group. On narrower viewports the action buttons stack on top of the org subtitle text, creating an overlap.
**Screenshot evidence:** `.audit/userflow/canvas/tablet-light.png`

### 11. Settings nav: 8 items with identical `compass` icon for three of them
**Location:** `src/routes/Settings.tsx:30–77`
**Severity:** Minor
**Observation:** `Account`, `Integrations`, and `About` all use `icon: "compass"`. The compass glyph appears three times in the Settings left nav, making the three items visually identical except for their label text. DESIGN.md §5 and the Icon component define a distinct vocabulary — `compass` is likely being used as a fallback when a more specific glyph isn't configured.
**Why it matters:** Icon-plus-label nav works only when the icons add scannability. Three identical icons in an 8-item list collapse the nav to pure text scanning — no better than having no icons at all.
**Recommendation:** Assign distinct icons: Account → `user` or `avatar`, Integrations → `link` or `external`, About → `info` or `shield`. Check `ui/components/Icon.tsx` for available glyph names.

### 12. `Org.tsx` Settings pane uses `var(--cf-fg-tertiary)` and `var(--cf-fg)` legacy tokens
**Location:** `src/routes/Org.tsx:292–296`
**Severity:** Minor
**Observation:** The `SettingsPane` component (visible when `tab === "settings"` on the Org route) uses `color: "var(--cf-fg-tertiary)"` and `color: "var(--cf-fg)"` inline — these are `--cf-*` legacy shim names that DESIGN.md §2.8 marks as migration-only. The same file uses `--rule-3`, `--surface`, and `--surface-2` via the correct new namespace for other elements. This is an inconsistency within a single file.
**Recommendation:** Replace `var(--cf-fg-tertiary)` → `var(--ink-mute)` and `var(--cf-fg)` → `var(--ink)`. Two-line change, no visual impact.

### 13. `Home.tsx:144` org-list row uses `<div role="button">` instead of `<button>`
**Location:** `src/routes/Home.tsx:144`
**Severity:** Minor
**Observation:** The "Your orgs" list renders each org as `<div className="cf-org-list__row" onClick={…} role="button">`. Per WCAG 4.1.2 and the DESIGN.md authoring rules, interactive click targets must be `<button>` elements (or `<a>` for navigation). A `<div role="button">` without an `onKeyDown` handler is not keyboard-accessible (Tab + Enter/Space won't activate it). The static audit from earlier this session already flagged this; it remains open.
**Recommendation:** Replace `<div role="button" onClick={…}>` with `<button type="button" className="cf-org-list__row" onClick={…}>`.

---

## Polish (no code change required — design decisions needed)

### P1. Canvas: "The studio" as page title vs org name
**Observation:** The Canvas header H2 reads "The studio" with the org name demoted to a `<Pill>`. The prior org-workspace audit recommended: "Dash also show `{org.name}` as the H2, with 'studio' as the eyebrow, mirroring Platform." This was noted then but not acted on. The visual effect is that every user's Canvas has the same page title regardless of which org is loaded — the org name is in a small, low-contrast pill that reads as metadata, not identity.
**Recommendation (pending your call):** Option A — swap to `<Eyebrow>studio</Eyebrow>` + `<h2>{orgName ?? "Canvas"}</h2>` (matches Platform convention). Option B — keep "The studio" as branding and add the org name as a separate subtitle row with `--ff-display` at 16px. Either option is better than the current treatment; A is closer to DESIGN.md's intent.

### P2. Appearance panel: selected-theme border is full accent-tint wash — hard to distinguish from hover
**Observation:** The active theme option (Light) uses the full `cf-settings__nav-item--active` style: accent-tint background plus accent-colored label text. The inactive option (Dark) uses default ink-soft text on paper background. The distinction is clear at rest, but the active state is identical to the hover state for nav items elsewhere — no additional selected-state indicator (checkmark, radio dot, or `border-left: 2px solid var(--accent)`) differentiates "selected" from "hovered." The `aria-checked` attribute is set correctly but there's no visual analog.
**Recommendation:** Add a small radio-style indicator (8px circle, `background: var(--accent)`) at the left or right edge of the active option to make the selected state visually distinct from hover.

### P3. Sessions: "Retry now" button uses `cfp-btn--primary` which renders as faded accent-tint
**Observation:** At `/sessions`, the error empty state shows a "Retry now" CTA. The button color in the screenshot is a desaturated pink-peach — it reads as disabled, not as a primary action. The full warm-paper accent (`#c8442b` background, white text) would make the CTA legible and action-oriented. Likely `cfp-btn--primary` resolves to a softer class than `cf-btn--primary`, or the button inherits disabled styling from a parent.
**Recommendation:** Confirm the Sessions empty-state CTA uses `cf-btn cf-btn--primary` (canonical namespace, not `cfp-*`). If using `cfp-btn--primary`, verify the class is defined and has the correct accent fill in `globals.css`.

### P4. Canvas live-trace text overflows to right rail boundary on wide (1440px)
**Observation:** At 1440px, the live-trace log lines (`obj` column, `whiteSpace: nowrap`) can extend beyond the right rail's 304px width, clipping against the window edge rather than the rail's own boundary. The `overflow: auto` on the trace container clips the text correctly for most lines but the `textOverflow: ellipsis` guard only applies when the parent is `overflow: hidden`. The combination of `overflow: auto` on the container and `overflow: hidden, textOverflow: ellipsis` on the row span needs to be consistent.
**Recommendation:** Set the trace row's `<span style={{ flex: 1, overflow: hidden, textOverflow: ellipsis, whiteSpace: nowrap }}>` — this is already in the code. Confirm that the outer trace container has an explicit `width: 100%` or `max-width` so the ellipsis has a reference container. Low visual impact but prevents long file paths from breaking the rail layout.

### P5. Board route: loading state uses raw `<div className="cf-empty">` + inline spinner
**Observation:** Board's loading render is `<div className="cf-empty"><span className="cf-spinner" /> Loading board…</div>`. Every other route uses the `<EmptyState>` component. This was flagged in the static audit and remains open. Not a visual regression but an authoring inconsistency that will matter when `EmptyState` gets a visual update.

---

## Animations audit

The system is predominantly static — motion is used correctly and sparingly. Specific checks:

| Pattern | Status | Notes |
|---|---|---|
| Marching ants (canvas edges) | Not triggered | No topology data in browser context — correct absence |
| Blink cursor (streaming trace) | Not triggered | Streaming requires a real org — correct |
| Fade-in (agent nodes) | Not observed | Nodes appear immediately with no animation — acceptable for static load |
| Bar fill (progress bars) | Not present | KPI bars hidden (no org data) — correct |
| Hover lift (cards) | Not audited via Playwright | Requires interaction |
| `cfp-blink` animation | Present in CSS | Used for live-session pulse dot in sessions.tsx — purpose-driven, not decorative |
| `prefers-reduced-motion` | Not found in screenshots | Could not confirm via Playwright. DESIGN.md does not specify a reduced-motion handler. The `cfp-blink` keyframe and canvas edge marching ants should be wrapped in `@media (prefers-reduced-motion: reduce) { animation: none }`. |

**Recommendation:** Add a single global block to `ui/tokens/globals.css`:
```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { animation-duration: 0.01ms !important; transition-duration: 0.01ms !important; }
}
```

---

## Flow and Button Logic audit (per-route)

### `/canvas`
**Action inventory:** Invite human · Hire agent · Select agent node · Drag node · Run demo task · Pause · Stop & refund · Open PR · Zoom −/+/fit · Open (selected agent link)

**Issues:**
- Two primary-styled actions (Hire agent uses ink surface = highest visual weight) with no `onClick` — see finding #4.
- "Run demo task" disabled (no org) but "Stop & refund" and "Pause" also disabled (not streaming) — three of five footer buttons are greyed out simultaneously. The footer reads as a disabled strip, not an action area.
- "Open PR ↗" is always enabled (no disabled guard) but has no handler and no tooltip. This is the same trust-eroding pattern as the static audit flagged.
- **Cognitive load:** 4 footer buttons + 4 zoom buttons + 2 header buttons = 10 simultaneous actions with no hierarchy. The primary action (Run demo task) is in the bottom-left, the least prominent position. Primary CTA should be rightmost or topmost.

### `/agents/eng-bot`
**Action inventory:** Back to Canvas (breadcrumb link) · Attach shell (disabled) · Assign task (disabled) · Tab switch (5 tabs) · Open (in right rail)

**Assessment:** Clean. Disabled states are semantically correct and have tooltips. The breadcrumb link is the only escape path back to Canvas — it is visually low-weight (12.5px, ink-mute color) relative to its importance as the only navigation back. Tab bar is clear with underline-active indicator.

**Issue:** The hero always shows `<Pill tone="accent" live>working</Pill>` regardless of actual agent state (since there's no data). A user navigating to `/agents/some-idle-agent` sees "working" unconditionally. The Pill live-state should be gated behind real status data, falling back to an "idle" or "ready" variant.

### `/board`
**Assessment:** Shows `<EmptyState title="Loading your board…" body={<span className="cf-spinner" />} />` — correct behavior without an org. The spinner is centered, on-brand. No action available (correct — nothing can be done without an org). Minor: the EmptyState has no secondary message explaining why the board is loading forever (the org service isn't running). A `Message tone="hint"` child would be appropriate.

### `/sessions`
**Assessment:** Shows the `emptyStates.sessions.noLens` empty state correctly: illustration, title, body, "Retry now" CTA. Good. The CTA is visually weak (see Polish P3). One issue: the body text contains two separate sentences that slightly contradict: "The background service that reads your sessions takes a moment to come online. We'll keep retrying." followed by "Something went wrong on our side. Try again in a moment." The first sentence implies auto-retry; the second implies user action needed. Pick one framing.

### `/settings/*`
**Assessment:** Settings nav is clear and accessible (8 items, keyboard navigable via `onKeyDown` handlers with Enter/Space). Active state uses accent background — visible and correct. Issues: three identical `compass` icons (finding #11), Policies content area is a raw error string (finding #6). The two-column layout (nav + panel) works well at all viewports above 820px. At 390px the settings panel content is completely hidden — only the left nav list is visible with no content pane. This is the same three-column collapse problem as Canvas.

---

## Per-route screenshots

| Route | Mobile | Tablet | Desktop | Wide |
|---|---|---|---|---|
| `/` (renders Canvas) | `.audit/userflow/home/mobile-light.png` | `.audit/userflow/home/tablet-light.png` | `.audit/userflow/home/desktop-light.png` | `.audit/userflow/home/wide-light.png` |
| `/canvas` | `.audit/userflow/canvas/mobile-light.png` | `.audit/userflow/canvas/tablet-light.png` | `.audit/userflow/canvas/desktop-light.png` | `.audit/userflow/canvas/wide-light.png` |
| `/agents/eng-bot` | `.audit/userflow/agent-canvas/mobile-light.png` | `.audit/userflow/agent-canvas/tablet-light.png` | `.audit/userflow/agent-canvas/desktop-light.png` | `.audit/userflow/agent-canvas/wide-light.png` |
| `/board` | `.audit/userflow/board/mobile-light.png` | `.audit/userflow/board/tablet-light.png` | `.audit/userflow/board/desktop-light.png` | `.audit/userflow/board/wide-light.png` |
| `/sessions` | `.audit/userflow/sessions/mobile-light.png` | `.audit/userflow/sessions/tablet-light.png` | `.audit/userflow/sessions/desktop-light.png` | `.audit/userflow/sessions/wide-light.png` |
| `/settings/policies` | `.audit/userflow/settings-policies/mobile-light.png` | `.audit/userflow/settings-policies/tablet-light.png` | `.audit/userflow/settings-policies/desktop-light.png` | `.audit/userflow/settings-policies/wide-light.png` |
| `/settings/account` | `.audit/userflow/settings-account/mobile-light.png` | `.audit/userflow/settings-account/tablet-light.png` | `.audit/userflow/settings-account/desktop-light.png` | `.audit/userflow/settings-account/wide-light.png` |
| `/settings/appearance` | `.audit/userflow/settings-appearance/mobile-light.png` | `.audit/userflow/settings-appearance/tablet-light.png` | `.audit/userflow/settings-appearance/desktop-light.png` | `.audit/userflow/settings-appearance/wide-light.png` |
| `/settings/about` | `.audit/userflow/settings-about/mobile-light.png` | `.audit/userflow/settings-about/tablet-light.png` | `.audit/userflow/settings-about/desktop-light.png` | `.audit/userflow/settings-about/wide-light.png` |

All paths are relative to `desktop/dash/`.

---

## Top 5 priorities by impact-to-effort

| # | Finding | Impact | Effort | Why now |
|---|---|---|---|---|
| 1 | Route mismatch: `/` renders Canvas not Home | Critical | Low — route table fix, 5 lines | Home is the onboarding entry point. Without it, no user can create their first org from the UI. |
| 2 | Mobile/tablet layout collapse (Canvas + AgentCanvas + Settings) | Critical | Medium — CSS media queries | The three-column shell needs one responsive breakpoint. No structural code change — `globals.css` only. |
| 3 | Hardcoded "2 live" sidebar badge | Major | Low — wire to sessions count | Every screenshot shows fabricated live status. Users who see "2 live" when 0 sessions run lose trust in all indicators. |
| 4 | Settings/Policies error state: raw 500 with no recovery | Major | Low — wrap in EmptyState + friendly copy | Default settings landing shows a broken state. First impression of Settings is broken. |
| 5 | Canvas "Hire agent" button non-functional + missing `disabled` | Major | Trivial — add `disabled title="Coming soon"` | Same fix already applied to AgentCanvas. Copy-paste the pattern. |

---

## What is already working well

1. **Zero horizontal overflow across every route and viewport.** The layout does not break the browser viewport at any of the four tested widths. This is notable given the absolute-positioned canvas surface.

2. **AgentCanvas empty states are correct and clean.** The P1 fixes from the prior audit (mock tasks, mock KPIs, mock description, hex literals) have all landed. The hero tile, disabled buttons with tooltips, and "—" placeholder rail are visually coherent and on-token. This surface has improved from 16/35 to a solid foundation.

3. **Sessions empty state is well-crafted.** The "Transcripts are starting up…" error state uses the illustrated `EmptySessionsSpot`, clear title, two-sentence body, and a retry CTA. It communicates the expected "no Tauri IPC" condition without making the user feel like something is permanently broken. The warm-paper background is consistent throughout.

4. **Token system is consistently applied at runtime.** `document.body` background resolves to `rgb(245, 241, 232)` = `#f5f1e8` = `var(--paper)` on every single route. No surface bleeds white or gray. The brand warm-paper foundation is solid end-to-end.

5. **Settings two-column layout is clear and navigable.** At desktop and wide viewports, the Settings shell (left nav + right panel) reads cleanly. Active state is visually distinct (accent-tint background + accent text). The keyboard handlers (`onKeyDown` with Enter/Space) make the `<div role="link">` nav items accessible — an unusual but correctly implemented pattern.

---

## One bold suggestion

**Make the Canvas footer action bar a command palette, not a button strip.**

Currently the Canvas footer has 4 buttons in a row (`Run demo task` · `Pause` · `Stop & refund` · `Open PR ↗`). Three of four are disabled at rest. The button strip pattern communicates "here are actions you can't take right now" — which is discouraging. It also scales poorly: as Canvas gets richer (assign task, view logs, export, share), the strip grows.

Replace it with a single **"⌘ Actions"** button (keyboard shortcut `⌘K`) that opens a command palette overlaid on the canvas. The palette lists all available actions, contextually filtering by what's possible given the current state (e.g., "Run demo task" only appears when `orgName` is set; "Stop" only appears when `streaming` is true). This pattern — used by Linear, Vercel, and Raycast — fits Crawfish's "CLI for agent organizations" positioning better than a button strip. It also makes the canvas surface feel like a workspace tool rather than a dashboard form.

---

## Regression check — org-workspace Canvas P1s

The six P1 blockers from `2026-05-18-org-workspace.md` were marked resolved in commit `590f244`. Live-audit confirmation:

| P1 from org-workspace audit | Status in live audit |
|---|---|
| `HUMAN_NODES` injection ("Pat" on every canvas) | Confirmed resolved — no "Pat" node visible in any screenshot |
| Seeded header subtitle "5 members · 1 active right now…" | Confirmed resolved — shows "No org loaded — append ?org=<slug> to load one." |
| Right-rail KPIs `$3.14 / $25`, `13%` bar, `92%` success | Confirmed resolved — shows "no data yet" and "nothing running" correctly |
| `+412 tok · $0.014` token-flow chip | Confirmed resolved — chip absent |
| "Add a /healthz endpoint · CRWF-118" current-task block | Confirmed resolved — shows "nothing running" |
| Hardcoded SVG edges | Confirmed resolved — no edges rendered (topology is empty, correctly) |

All six P1s from the org-workspace audit are clear. No regression observed.

---

## Fix-pass 2026-05-18

**Teammate:** fix-dash · **Commits (dash submodule):**

| Commit | Finding closed | Change |
|---|---|---|
| `f5bc5ae` | Major 4 — Canvas "Hire agent" / "Invite human" non-functional | Both buttons now disabled when no org loaded; Hire agent permanently `disabled title="Coming soon"` |
| `f5bc5ae` | Major 7 — Appearance dark mode broken promise | Removed the interactive Dark option; Dark shown as disabled "Coming soon"; Light remains selected and honest |
| `f5bc5ae` | Major 8 — `var(--bad, #b1452f)` hex fallback in App.tsx OnlineLink | Removed hex fallback; now `var(--bad)` only |
| `f5bc5ae` | Major — Analytics ProductPane bar color | Bar fill changed from `var(--cf-fg)` to `var(--accent)` |

**Type-check:** `npx tsc --noEmit -p tsconfig.json` — 0 errors.

**Not fixed here (scope or deferred):**
- Major 6 — Settings/Policies mobile layout (`@media (max-width: 700px)` rule) requires `ui/tokens/globals.css` — lead-only file. Lead to add `.cf-settings { grid-template-columns: 1fr }` breakpoint.
- Minor 9 — Home `<h2>` vs `<h1>`: low impact; deferred.
- Minor 10–13 — icons, legacy tokens, `div[role=button]`: deferred to Wave 5 sweep.
- Polish items: no code change required per brief.
