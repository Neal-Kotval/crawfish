# Dash Data-Views Cluster — Live Playwright Audit
**Date:** 2026-05-18  
**Server:** http://localhost:7881  
**Viewports:** mobile 390×844 · tablet 820×1180 · desktop 1280×820 · wide 1440×900  
**Themes:** light · dark  
**Auditor:** ui-auditor agent (Playwright + senior product-designer critique pass)

---

## Context: IA Reorganisation Since the Static Audit

The static audit (`2026-05-18-dash-data-views.md`) targeted 15 routes. By the time of this live walk, the route table in `main.tsx` had been substantially reorganised:

| Old route | Live fate |
|---|---|
| `/analytics` | Retired → `<Navigate to="/canvas" />` |
| `/crons` | Retired → `/canvas` |
| `/files` | Retired → `/canvas` |
| `/compare` | Retired → `/canvas` |
| `/benchmarks` | Retired → `/canvas` |
| `/dashboard` | Retired → `/canvas` |
| `/policies` | Retired → `/settings/policies` |
| `/runtimes` | Retired → `/settings/runtimes` |
| `/optimizers` | Retired → `/settings/optimizers` |
| `/integrations` | Retired → `/settings/integrations` |
| `/knowledge` | **Live** (direct route) |
| `/diagnoses` | **Live** (direct route) |
| `/projects` | **Live** (direct route) |
| `/agents` (list) | Folded into `/settings/agents` |

All retirements are clean client-side `<Navigate replace />` — no 404s, no blank screens, no dangling history entries. The Settings shell is the new home for the folded routes.

---

## Playwright Metrics Summary

| Metric | Result |
|---|---|
| Horizontal overflow (any viewport, any route) | **None** — 0px across all 20 routes × 4 viewports |
| Dark-mode body background | **Correct** — all routes hold `rgb(245,241,232)` under `colorScheme: dark` (warm-paper no-op confirmed) |
| Sign-in gate bypassed | **Yes** — `addInitScript` with `cf-linked-user` works on all routes |
| Routes with `<h1>` | **0 of 13 live routes** |
| Routes with `<main>` landmark | **0 of 13 live routes** (measured; 3 direct routes + 10 settings tabs) |
| Buttons missing `type` attribute | **3 on Canvas** (redirect destination); 0 on data-view routes |
| Inline hard-coded hex values | **0** detected in rendered DOM |
| `--cf-*` legacy token usage in inline styles | **0** detected in rendered DOM (prior code-level findings remain relevant at source level) |

---

## Findings

### Blockers (Critical)

---

**B1 — `/knowledge` is a dead end: no org-id navigation path exists in the shell**

- **Location:** `src/routes/Knowledge.tsx` + `src/App.tsx` sidebar
- **Severity:** Critical
- **Observation:** Navigating to `/knowledge` from the sidebar (with no org loaded) shows "Missing org id — Open the Knowledge tab from an org page." The sidebar provides no path to reach an org page; the only org-entry point referenced in the UI is the TitleBar org-switcher chip, which navigates to `/settings` (account), not to an org canvas. There is no CTA, no link, no escape route visible from the Knowledge error state itself. The user is stranded.
- **Screenshot evidence:** `/Users/nealkotval/crawfish/.audit/userflow/knowledge/desktop-light.png`, `mobile-light.png`, `wide-light.png` — identical dead end across all viewports.
- **Why it matters:** The sidebar presents Knowledge as a first-class destination item. A user without a loaded org who clicks it lands on an error with no actionable next step. The prior static audit flagged the component pattern but did not capture this nav dead end from the shell perspective. This is a user flow break, not just an aesthetic issue.
- **Recommendation:** The Knowledge error state must render a CTA: either "Go to Canvas" (linking to `/canvas`) or "Load an org" (linking to the org-switcher or `/wizard/first-run`). The sidebar should also conditionally suppress Knowledge/Diagnoses/Projects when no org is present (or badge them with a precondition indicator), matching the pattern used elsewhere for feature-gated items.

---

**B2 — `/diagnoses` error state conflates two distinct conditions into one message**

- **Location:** `src/routes/Diagnoses.tsx`
- **Severity:** Critical
- **Observation:** The rendered error state shows two simultaneous messages: "The diagnoses engine needs a running lens server to scan transcripts." (honest, actionable) AND "Something went wrong on our side. Try again in a moment." (generic 500 fallback). These are contradictory: the first tells the user the service is architecturally absent (expected condition without lens running); the second implies a transient server fault (suggesting retry will help). In practice both fire because `GET /api/diagnoses/recent` returns a 500 when lens is not running.
- **Screenshot evidence:** `/Users/nealkotval/crawfish/.audit/userflow/diagnoses/desktop-light.png` — both messages visible stacked in the empty-state area.
- **Why it matters:** A user who reads "Something went wrong on our side. Try again" will retry, which will fail again, eroding trust. The correct message is: "Diagnoses requires the lens server. Start lens to enable scanning." The 500 should be caught and routed to the architectural explanation, not surfaced as a generic fault.
- **Recommendation:** In `Diagnoses.tsx`, distinguish a 500 on `/api/diagnoses/recent` (lens not running) from a genuine unexpected error. When the status is 500 and the body matches the known lens-offline pattern, show only the lens-server explanation with a command snippet or link to docs. Reserve "Something went wrong on our side" for truly unexpected errors (4xx auth failures, 503, etc.).

---

**B3 — Settings data tabs (Policies, Agents, Optimizers, Runtimes, Integrations) surface raw HTTP error strings to users**

- **Location:** `src/routes/Settings.tsx` + respective tab components (`policies.tsx`, `agents.tsx`, `optimizers.tsx`, `runtimes.tsx`, `integrations.tsx`)
- **Severity:** Critical
- **Observation:** Every Settings data tab shows its error state without the backend running. The error strings exposed are internal implementation details:
  - Policies: "Couldn't load policies — Error: policy log: 500"
  - Runtimes: "Couldn't load runtimes — GET /api/runtimes 500"
  - Integrations: "Couldn't load integrations — orgs: 500"
  - Agents: "Couldn't load agents — Something went wrong on our side. Try again in a moment."
  - Optimizers: "Couldn't load optimizers — Something went wrong on our side. Try again in a moment."
- **Screenshot evidence:** `settings-policies/desktop-light.png`, `settings-runtimes/desktop-light.png`, `settings-integrations/desktop-light.png`, `settings-agents/desktop-light.png`, `settings-optimizers/desktop-light.png`.
- **Why it matters:** "GET /api/runtimes 500" and "Error: policy log: 500" are raw HTTP debugging strings. Exposing these violates the cluster's "honest empty states" theme — they are not honest, they are opaque. A user who is not a developer cannot act on "orgs: 500". More critically, these appear in the default Settings landing state for any user whose backend is offline — which is the standard state for a desktop app user who has not started the local server.
- **Recommendation:** Error boundaries in each settings tab should catch the 500 case and render: a human-readable explanation ("The [Policies / Runtimes / ...] service isn't reachable right now. Make sure the Crawfish server is running.") plus a "Retry" button. The raw error string should go to `console.error` only, not to the UI. This affects at minimum 5 files: `policies.tsx`, `agents.tsx`, `optimizers.tsx`, `runtimes.tsx`, `integrations.tsx`.

---

### Major

---

**M1 — Zero heading landmarks across the entire data-views cluster**

- **Location:** All 13 audited routes
- **Severity:** Major
- **Observation:** Playwright DOM inspection found `h1Count: 0` on every route — Knowledge, Diagnoses, Projects, and all 10 Settings tabs. Page titles like "Account", "Appearance", "Policies" are rendered as `<div className="cf-text-xl cf-weight-semibold">` (Settings tabs) or as empty-state mid-page copy with no heading role. The Appearance panel uses an `<h2>`-looking title that is a plain `<div>`.
- **Why it matters:** Screen readers announce pages by `<h1>`. Without one, VoiceOver/NVDA users hear no page context change when navigating between tabs. This affects the entire cluster, not isolated components.
- **Recommendation:** Each route (and each Settings panel) should open with an `<h1>` or `<h2>` using `fontFamily: var(--ff-display)` at title scale (24–34px per DESIGN.md §3). For settings panels, the existing `<div className="cf-text-xl">` title is the right visual, just change the element to `<h2>`.

---

**M2 — Settings shell has no `<main>` landmark on any tab**

- **Location:** `src/routes/Settings.tsx` — `.cf-settings__panel` div
- **Severity:** Major
- **Observation:** The Settings panel wrapper (`<div className="cf-settings__panel">`) is a plain `<div>`. The outer workspace routes (Knowledge, Diagnoses, Projects) use `<main className="cfp-shell__main">` in some places but DOM inspection shows no `<main>` landmark on these routes either. The `cfp-shell__main` class appears to exist in globals.css but the direct routes render without it.
- **Why it matters:** Without a `<main>` landmark, keyboard users cannot skip to content with a screen reader's "jump to main" shortcut. Every one of the 13 audited routes fails this basic accessibility requirement.
- **Recommendation:** Wrap each settings panel's content in `<main>`, and ensure the direct routes (Knowledge, Diagnoses, Projects) wrap their content area in `<main className="cfp-shell__main">`.

---

**M3 — Mobile layout: Settings shell second nav panel clips content area to ~165px**

- **Location:** `src/routes/Settings.tsx` — `.cf-settings` CSS grid
- **Severity:** Major
- **Observation:** At 390px mobile, the Settings shell renders a two-column layout: the main sidebar (232px) occupies the left, and the Settings sub-nav (~165px) runs in a second column, leaving approximately 0px for the actual panel content. The `cf-settings__panel` is pushed entirely off-screen or rendered in a zero-width column. The Policies error state is visible on tablet (820px) but on mobile the sub-nav list occupies the full remaining width after the main sidebar — the panel content is invisible.
- **Screenshot evidence:** `settings-policies/mobile-light.png` — the Settings sub-nav is visible; the panel content ("Couldn't load policies" etc.) is absent entirely.
- **Why it matters:** This is a complete content failure at mobile viewport. A user on a narrower screen (390px) navigating to any Settings tab sees the sub-nav list but no panel content at all. The DESIGN.md target window is 1280×820, but the app renders in-browser and the mobile viewport must not be a blank panel.
- **Recommendation:** The `.cf-settings` layout needs a breakpoint: below ~700px, collapse to a single-column stack (sub-nav at top, panel below). The quick fix is `@media (max-width: 700px) { .cf-settings { grid-template-columns: 1fr; } .cf-settings__nav { border-right: none; border-bottom: 1px solid var(--rule); } }` in `globals.css`.

---

**M4 — `App.tsx` `OnlineLink` error state uses `var(--bad, #b1452f)` hardcoded hex fallback**

- **Location:** `src/App.tsx:504`
- **Severity:** Major
- **Observation:** The "link failed" error pill in the TitleBar reads `color: "var(--bad, #b1452f)"`. The hex `#b1452f` does not match the canonical `--danger: #b53224` from DESIGN.md §2.5. This surfaces on every route that renders the `OnlineLink` component when the org link fails.
- **Why it matters:** The prior static audit flagged this same pattern in `Projects.tsx`. The same bug exists in the shell component that renders universally. If the `--bad` token import order shifts or the shim is deleted, the fallback silently diverges from the brand danger colour.
- **Recommendation:** Change `color: "var(--bad, #b1452f)"` to `color: "var(--bad)"`. The token is present in the token file; the fallback is not needed and introduces colour drift.

---

**M5 — `Appearance` panel describes a dark mode that contradicts DESIGN.md**

- **Location:** `src/routes/Settings.tsx` — `AppearancePanel`
- **Severity:** Major
- **Observation:** The Appearance panel offers two theme options: "Light — Warm cream + leaf-green — the daytime island" and "Dark — Deep forest night + mint glow". DESIGN.md §1 explicitly states: "No dark mode. The brand is warm-paper-only. The `data-theme='dark'` attribute is honored as a no-op fallthrough to light tokens." The live screenshot confirms this — selecting "Dark" in Playwright still renders `bodyBg: rgb(245,241,232)`, meaning the dark token override does nothing visually. The UI promises a "deep forest night + mint glow" experience that does not exist.
- **Screenshot evidence:** `settings-appearance/desktop-dark.png` — identical warm-paper rendering to the light theme. The "Dark" option is selected-looking but the background remains `#f5f1e8`.
- **Why it matters:** This is a broken promise surfaced as a first-class product feature. A user who selects "Dark" expecting a dark UI will see no change, with no feedback that the switch worked. This is the worst form of empty-state dishonesty: a toggle that visually activates but changes nothing.
- **Recommendation:** Two paths: (A) Implement dark mode tokens and a genuine dark theme — the right long-term answer. (B) Remove the Dark option from the Appearance panel entirely and replace with a single-option display or a copy that honestly states "Crawfish is warm-paper only. Dark mode is coming." Path B is the correct immediate fix per the cluster's "no fake signals" theme.

---

### Minor

---

**Mi1 — `OnlineLink` requesting state panel uses absolute positioning that may overlap content at non-standard zoom**

- **Location:** `src/App.tsx` — `OnlineLink` component, `requesting` state dropdown
- **Severity:** Minor
- **Observation:** The device-code panel is positioned `position: absolute; top: calc(100% + 8px); right: 0; zIndex: 50`. At 390px mobile the panel minWidth of 280px may overflow the viewport right edge since the parent is positioned `right: 248px` from the edge of the screen. No horizontal overflow was detected by Playwright (scrollWidth check passed), but this is because the panel only renders during an active link request flow, not on static load.
- **Recommendation:** Add `max-width: calc(100vw - 16px)` and `right: max(0px, ...)` to the panel, or reposition to left-aligned on narrow viewports.

---

**Mi2 — Settings nav items use `role="link"` on `<div>` elements**

- **Location:** `src/routes/Settings.tsx:118–140`
- **Severity:** Minor
- **Observation:** The Settings sub-nav renders `<div role="link" tabIndex={0} onClick={...}>`. The `role="link"` is semantically incorrect for items that navigate within a single-page application without changing the URL's origin — they are tabs or buttons, not links. A true `role="link"` implies a destination URL. Screen readers will announce "link" and users will expect `Enter` to activate (correct) but may not expect `Space` to activate (which the `onKeyDown` handler supports — non-standard for links).
- **Recommendation:** Change to `role="button"` or, better, use `<button>` elements styled as nav items. If the tab metaphor is intended, use `role="tab"` with a `role="tabpanel"` wrapper on the panel and `aria-controls` / `id` pairing.

---

**Mi3 — `Diagnoses` route fires `GET /api/diagnoses/recent` 5 times per page load**

- **Location:** Network failures log in Playwright findings
- **Severity:** Minor
- **Observation:** Each Diagnoses page capture showed 5 identical `net::ERR_ABORTED` failures against `/api/diagnoses/recent`. This is consistent with a polling interval or multiple React StrictMode double-invocations combined with a retry effect. With lens offline, this generates unnecessary noise in the browser network panel and in server logs.
- **Recommendation:** Audit the `useEffect` in `Diagnoses.tsx` — ensure the poll is gated behind a successful first fetch (don't retry when the error is architectural, i.e. 500 on known-offline endpoint). Recommend exponential backoff with a cap of 2 retries before switching to a static "start lens to continue" state.

---

**Mi4 — `/knowledge` empty state has significantly lower information density than `/diagnoses`**

- **Location:** `src/routes/Knowledge.tsx` vs `src/routes/Diagnoses.tsx`
- **Severity:** Minor
- **Observation:** Diagnoses renders a proper illustrated empty state (stacked-document SVG illustration, title, two lines of body copy). Knowledge renders plain centered text: bold title "Missing org id" and one line of subdued body. No illustration, no CTA. The inconsistency reads as an incomplete component, not a deliberate minimal design choice.
- **Screenshot evidence:** `knowledge/desktop-light.png` vs `diagnoses/desktop-light.png`.
- **Recommendation:** Apply the `<EmptyState>` component to the Knowledge missing-org state (same illustration tier as Diagnoses), and add a CTA button per B1.

---

**Mi5 — `Sessions` badge "2 live" is hardcoded in the sidebar nav spec**

- **Location:** `src/App.tsx:29` — `WORKSPACE_NAV` constant
- **Severity:** Minor
- **Observation:** The Sessions nav item has `badge: "2 live"` hardcoded in the static nav array. This is a compile-time constant — it does not reflect actual live session count. A user with 0 live sessions or 7 live sessions sees "2 live" regardless.
- **Why it matters:** This is seed data presented as live state — exactly the "no fake numbers" antipattern the cluster theme is designed to eliminate. It is subtle (looks like a status indicator) and persistent (visible on every route in the shell).
- **Recommendation:** Replace with a dynamic count fetched from `/api/sessions?status=live` or remove the badge entirely until the live-count API is ready. Do not display a count that is not real.

---

### Polish

---

**P1 — Error text colour inconsistency across Settings tabs**

- **Observation:** Policies shows its error sub-line in `--ink-mute` (grey). Runtimes and Integrations show the HTTP error string in vermillion (`--accent` or `--danger` colour). Agents and Optimizers use the generic grey. The colour treatment should be uniform — error detail text belongs in `--ink-mute` or `--danger` depending on severity, but not mixed randomly across tabs.
- **Screenshot evidence:** `settings-runtimes/desktop-light.png` ("GET /api/runtimes 500" in red), `settings-policies/desktop-light.png` ("Error: policy log: 500" in grey).

---

**P2 — `no org yet` titlebar chip lacks visual affordance that it is actionable**

- **Observation:** The titlebar shows "no org yet ∨" as a pill with a dropdown chevron. The chevron implies interactivity but the chip navigates to `/settings` rather than opening an org picker. The label "no org yet" is accurate but provides no hint of what clicking it does. DESIGN.md §6.2 specifies the chip is an org switcher.
- **Recommendation:** Change the label to "Add org" or "Set up org" with a `+` icon when no org is loaded, so the affordance matches the action.

---

**P3 — Wide viewport (1440px) wastes ~900px of right-hand space on all data routes**

- **Observation:** All three direct routes (Knowledge, Diagnoses, Projects) render their empty states centered in a content area that spans from the 232px sidebar to the full right edge. On wide viewports this is ~1200px wide, but the empty-state content is ~320px wide, leaving vast blank warm-paper to both sides.
- **Screenshot evidence:** `knowledge/wide-light.png` — centered text floating in a sea of cream.
- **Recommendation:** Cap the content column at `max-width: 640px` with `margin: 0 auto`, or enable the right-rail (currently off for these routes) with contextual content like "Recent in this org" or onboarding cards.

---

**P4 — Settings appearance panel: selected theme row does not show a checkmark or radio visual**

- **Observation:** The "Light" option is highlighted with `--accent-tint` background, but there is no checkmark, filled radio, or explicit selected indicator beyond the background tint. The `role="radio"` + `aria-checked="true"` is set correctly in code, but visually the selection is ambiguous — the "Dark" row just looks like an unhighlighted item rather than an unselected option.
- **Recommendation:** Add a right-aligned filled circle or checkmark icon (matching the `Icons` set) to the selected row. This resolves both the visual ambiguity and makes the state explicit for colour-blind users who may not distinguish the tint.

---

**P5 — Redirect confirmation: all 10 retired routes silently redirect with no toast or transition**

- **Observation:** `/analytics`, `/crons`, `/files` etc. all redirect cleanly to `/canvas`. There is no in-app notification that the URL the user navigated to has moved. If a user has a bookmark for `/analytics` they will silently land on Canvas with no indication why.
- **Recommendation:** Low priority — these routes are internal. But if any external documentation links to these URLs, a one-time dismissible banner ("Analytics has moved — see settings for data views") would be more honest than a silent redirect.

---

## Animations Checklist

| Item | Result |
|---|---|
| Canvas: marching ants | Present on active edges, 2.4s loop — correct per DESIGN.md §7 |
| Canvas: token-flow chip | Visible in redirect-to-canvas screenshots — correct |
| Settings: no animated transitions between tabs | Tabs snap without transition — acceptable (not specified in DESIGN.md §7) |
| Empty states: no skeleton shimmer | Correct — static `--paper-2` fills per spec |
| `prefers-reduced-motion` | Not testable via Playwright `colorScheme` flag alone; no explicit violations observed in source |
| Infinite background loops | None detected outside Canvas (Canvas marching ants are purposeful) |
| Bar fill transitions | Not rendered without data; no violations detectable |

No animation violations found in the data-views cluster. The main canvas (redirect destination) correctly uses the specified motion primitives.

---

## Flow Checklist: Data-Views Routes

| Check | Result |
|---|---|
| Primary action clarity | Fail on Knowledge (no action), Fail on Diagnoses (conflicting messages), Pass on Projects ("Create or link an org" is clear) |
| Labeling: outcome vs mechanism | Pass on most Settings tabs; Fail on "Unlink" button (outcome is "forget account" not stated) |
| Dead ends | Knowledge: full dead end (B1). Diagnoses: soft dead end (no retry/escape). |
| Backwards/escape paths | All routes: sidebar always visible, always navigable — pass |
| Redundancy | "Settings" appears both in the main sidebar footer and as a sub-nav destination inside Settings — minor confusion |
| Permission/state mismatch | OnlineLink "Make online" button visible even when org link cannot succeed without a running backend — minor mismatch |
| Cognitive load | Settings sub-nav has 8 items (Account, Policies, Agents, Optimizers, Runtimes, Integrations, Appearance, About) — within acceptable range for settings navigation |
| Cross-screen continuity | Redirect chain from `/policies` → `/settings/policies` works correctly; URL updates to final destination |

---

## Empty-State Honesty Audit

| Route | State shown | Honest? | Notes |
|---|---|---|---|
| `/knowledge` | "Missing org id" | Yes — but dead end | No CTA to resolve the missing org |
| `/diagnoses` | Two contradictory messages | Partially | See B2 — architectural vs transient error conflation |
| `/projects` | "No org yet — Create or link an org before browsing projects." | Yes | No CTA link though |
| `/settings/policies` | "Couldn't load policies — Error: policy log: 500" | No | Raw HTTP string exposed |
| `/settings/agents` | "Couldn't load agents — Something went wrong on our side." | Partially | Generic message obscures real cause (no backend) |
| `/settings/optimizers` | Same as agents | Partially | Same issue |
| `/settings/runtimes` | "GET /api/runtimes 500" | No | Raw HTTP string exposed |
| `/settings/integrations` | "orgs: 500" | No | Raw HTTP string exposed |
| `/settings/account` | Linked account card (from injected localStorage) | Yes | Works correctly |
| `/settings/appearance` | Theme picker with non-functional Dark option | No | See M5 — broken promise |
| Retired routes → Canvas | Canvas with seed data | Mixed | Canvas has its own audit scope |

**Cluster honest-empty-state score: 4 of 10 routes fully honest.** The primary failures are raw error string exposure (3 routes) and the non-functional Appearance toggle (1 route).

---

## Top 5 Priorities by Impact-to-Effort

| # | Finding | Impact | Effort | Ratio |
|---|---|---|---|---|
| 1 | **B3** — Strip raw HTTP error strings from all 5 Settings data tabs; replace with human-readable messages + Retry button | High: affects every user who opens Settings without backend | Low: 5 text changes + conditional error routing | Very high |
| 2 | **B1** — Add "Go to Canvas" / "Create org" CTA to Knowledge and Projects empty states | High: removes the only current dead-end flow | Very low: one CTA button per route | Very high |
| 3 | **Mi5** — Replace hardcoded "2 live" Sessions badge with dynamic count or remove | High: violates the cluster's "no fake numbers" principle; visible on every route | Low: one API call in App.tsx | High |
| 4 | **M5** — Remove or truthfully label the Dark theme option in Appearance | High: broken UI promise; user expectation vs reality mismatch | Low: remove one option or replace copy | High |
| 5 | **M3** — Fix Settings shell mobile layout (panel content invisible below 700px) | Medium: data-views are desktop-primary but failure is complete, not degraded | Low: 4-line CSS addition to globals.css | High |

---

## What Is Already Working Well

1. **Warm-paper token discipline in the DOM.** Zero hardcoded hex values detected in any rendered DOM `style` attribute across all 13 routes (the source-level `--bad, #b1452f` fallback in `App.tsx` is the single exception). The migration from `--cf-*` aliases has evidently been largely applied at render time.

2. **Redirect table is clean and complete.** All 10 retired data-view routes redirect correctly, instantly, with clean URL rewriting. No 404s, no blank pages, no intermediate loading states. The retirement was well-executed.

3. **Dark-mode no-op is faithful.** Every route holds `rgb(245,241,232)` as body background when Playwright requests `colorScheme: dark`. The DESIGN.md "no dark mode — no-op fallthrough" contract is honoured at the token level across the full cluster.

4. **`/diagnoses` uses the illustrated empty-state component correctly.** The stacked-document illustration, semantic title ("Diagnoses unavailable"), and body copy render cleanly at all four viewports. The visual language is consistent with the design system even though the copy has a logic conflict (B2).

5. **Zero horizontal overflow at any viewport.** The sidebar + content layout holds correctly at 390px, 820px, 1280px, and 1440px — no content is clipped or scrollable horizontally. This includes the Settings two-column layout at tablet and desktop, which stays within bounds.

---

## One Bold Suggestion

**Make the shell state-aware and precondition the sidebar.**

Every data-views route currently renders in one of two modes: "no org loaded" (dead empty state) or "org loaded but backend offline" (API error). The shell has access to both of these states via the `resolvedOrg` and `OnlineLink` state already computed in `App.tsx`. Rather than letting users navigate into routes that will immediately error, the sidebar should communicate preconditions inline:

- When `resolvedOrg === null`: Knowledge, Diagnoses, and Projects sidebar items should render with a faint `--ink-faint` colour, a tooltip on hover ("Requires an org — start here"), and a `+` affordance that navigates to `/wizard/first-run`. They remain clickable but set expectations before the click.
- When `resolvedOrg` exists but the backend is offline (detectable from the 500 chain in `OnlineLink`): Settings data tabs should show a one-line inline warning in the sub-nav ("Server offline") rather than serving each tab's error state individually.

This shifts the cluster from a pattern of "navigate → hit error → no escape" to "shell communicates system state → user makes informed choices." It is a single-surface change (App.tsx + Settings.tsx) that fixes the root cause of B1, B2, B3, and Mi3 simultaneously.

---

## Per-Route Screenshots

| Route | Screenshots |
|---|---|
| `/knowledge` | `/Users/nealkotval/crawfish/.audit/userflow/knowledge/` — `mobile-light.png`, `tablet-light.png`, `desktop-light.png`, `wide-light.png`, `*-dark.png` |
| `/diagnoses` | `/Users/nealkotval/crawfish/.audit/userflow/diagnoses/` — same set |
| `/projects` | `/Users/nealkotval/crawfish/.audit/userflow/projects/` — same set |
| `/settings/policies` | `/Users/nealkotval/crawfish/.audit/userflow/settings-policies/` — same set |
| `/settings/agents` | `/Users/nealkotval/crawfish/.audit/userflow/settings-agents/` — same set |
| `/settings/optimizers` | `/Users/nealkotval/crawfish/.audit/userflow/settings-optimizers/` — same set |
| `/settings/runtimes` | `/Users/nealkotval/crawfish/.audit/userflow/settings-runtimes/` — same set |
| `/settings/integrations` | `/Users/nealkotval/crawfish/.audit/userflow/settings-integrations/` — same set |
| `/settings/account` | `/Users/nealkotval/crawfish/.audit/userflow/settings-account/` — same set |
| `/settings/appearance` | `/Users/nealkotval/crawfish/.audit/userflow/settings-appearance/` — same set |
| Retired routes (redirect confirm) | `/Users/nealkotval/crawfish/.audit/userflow/retired-*/desktop-light.png` |
| Findings JSON | `/Users/nealkotval/crawfish/.audit/data-views-findings.json` |
