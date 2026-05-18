# Crawfish Platform SPA — Full Playwright Audit
**Date:** 2026-05-18
**Auditor:** ui-auditor agent (claude-sonnet-4-6)
**Dev server:** http://localhost:5174 (user-started, not killed)
**Auth mode:** Dev façade active (`VITE_CLERK_PUBLISHABLE_KEY=` in `.env.local`)
**Viewports:** mobile 390×844, tablet 820×1180, desktop 1440×900
**Screenshots:** `/Users/nealkotval/crawfish/.audit/userflow/platform-full/<route>/<viewport>.png`
**Findings JSON:** `/Users/nealkotval/crawfish/.audit/userflow/platform-full/findings.json`
**Prior audits referenced:** `2026-05-18-platform-spa.md`, `2026-05-18-org-workspace.md`, `2026-05-18-platform-spa-playwright.md`

---

## Infrastructure finding (blocks all data-driven routes)

**VITE_SERVER_URL port mismatch.** Both `cloud/platform/.env` and `.env.local` set `VITE_SERVER_URL="http://127.0.0.1:7882"`. The crawfish-server process (PID 68130, cwd `cloud/server`) did not successfully bind to any port — `lsof` shows no `7882` listener. Every authenticated surface therefore receives `ERR_CONNECTION_REFUSED` on every API call.

The result: every signed-in page in this audit renders its error state. The org picker shows `"Failed to fetch"`. Canvas shows `"Couldn't load this org / Failed to fetch"`. Team shows `"Failed to fetch"` with no H1. Projects shows the raw JSON parse error `"Unexpected token '<', \"<!doctype \"... is not valid JSON"` (the Vite dev server is responding with its HTML fallback instead of a JSON body).

This is not a UI bug in the front-end code — the UI handles it gracefully in most places — but it means:
1. The "happy path" (org with agents, team members, projects) was **not visually tested** in this run.
2. The `"Failed to fetch"` string leaking into user-visible error text is itself a UX bug (see Critical-1 below).
3. The Projects page error string `"Unexpected token '<'…"` is a raw JSON parse exception surfaced verbatim (see Critical-2).

**To get the happy-path screenshots the next auditor should:**
- Confirm `cloud/server` is listening (run `npm run dev` in `cloud/server/`; it defaults to `PORT=7882`).
- Or update `.env.local` `VITE_SERVER_URL` to the actual port (`7878` if that is the server rather than lens).

---

## Findings by severity

**Counts:** Critical 4 · Major 9 · Polish 8

---

### Critical

**C-1 — "Failed to fetch" raw exception surfaced on org picker, canvas, and team**
Location: `pages/OrgPicker.tsx` (error banner), `pages/OrgRoute.tsx:133` (canvas error body), `pages/OrgMembers.tsx` (error state).
Observation: When `apiFetch` throws a network error, `err.message` is the raw browser string `"Failed to fetch"` — the literal internal JavaScript exception. It appears prominently in danger-colored text on the first signed-in screen users see.
Screenshot evidence: `org-picker/desktop.png` — a warm-amber banner in the content area reads `Failed to fetch` in monospace before the "Start onboarding →" CTA. On `team/desktop.png` the page shows only the eyebrow `AUDIT-ORG · TEAM` and the single line `Failed to fetch` — no H1, no CTA, no recovery path.
Why it matters: This is a first-impression screen. A real user hitting a brief outage sees this and interprets it as a crash. `"Failed to fetch"` is not a human sentence.
Recommendation: In the `catch` block for all `apiFetch` calls, map `"Failed to fetch"` and `"NetworkError"` → `"We couldn't reach the server. Check your connection and try again."`. Add a retry button. For the team page specifically, render an H1 and a back-link even in the error state so the user is not stranded on a blank screen.

**C-2 — Projects page surfaces a raw JSON parse exception**
Location: `pages/Projects.tsx` — the error message passed to `setState({ kind: "error", message: ... })` is the raw `SyntaxError.message` from `res.json()` when the server returns HTML (404 page, Vite fallback).
Observation: `projects/desktop.png` shows `"Couldn't load projects: Unexpected token '<', \"<!doctype \"... is not valid JSON"` as paragraph text below the H1. This is a JavaScript engine error string, not a user message.
Why it matters: Exposes implementation details. For a developer-audience product this is especially jarring because it looks like an unhandled exception rather than a network error.
Recommendation: Wrap `res.json()` in a try/catch in `Projects.tsx` and rethrow a user-friendly error: `"We couldn't load your projects. The server may be unreachable."` Alternatively, check `res.ok` and `res.headers.get("content-type")` before parsing — if the content-type is `text/html`, it's a proxy or server error, not a JSON error.

**C-3 — Onboarding deep-links bounce to welcome with no feedback; steps 2–5 inaccessible by URL**
Location: `onboarding/OnboardingFlow.tsx:94-98`.
Observation: Direct navigation to `/onboarding/propose`, `/install`, `/hired`, `/handoff` redirects to `/onboarding/welcome` because `sessionStorage` is empty in a fresh Playwright context (or any fresh tab). Playwright confirmed: `finalUrl` for all four deep-links is `http://localhost:5174/onboarding/welcome`. The `showResumeNotice` state flag is set, but the notice is rendered inside the welcome stage markup — and since the redirect fires before the welcome content paints, the notice was not captured in the screenshot.
Why it matters: External links to a later onboarding step (e.g., in support emails, onboarding reminder emails, or test runs) silently drop the user at step 1 with no explanation. In the prior playwright audit (Clerk-enabled) this exact issue was flagged but could not be verified — now confirmed.
Recommendation: The `showResumeNotice` banner must render prominently at the top of the welcome form, above the H1. Verify it's mounted, not just set in state. Also consider URL-persisting answers (base64 in the hash) so a genuine deep-link to propose works. As a minimum: when `showResumeNotice` is true, render a warm info banner: `"Your previous session expired — fill in your details to continue."` Make it visible above the fold on mobile.

**C-4 — Server URL misconfiguration: `.env.local` VITE_SERVER_URL points to port 7882 but server is not listening there**
Location: `cloud/platform/.env.local:2`, `cloud/platform/.env:5`.
Observation: `lsof` confirms no process is listening on `:7882`. Every `apiFetch` call receives `ERR_CONNECTION_REFUSED`. The Vite dev server on `:5174` also has no proxy configured for `/api/...` routes (confirmed in `vite.config.ts`), so relative `/api/...` URLs in `Projects.tsx:48` (`fetch("/api/orgs/...")`) hit the Vite server and receive an HTML fallback.
Why it matters: The entire authenticated half of the app is broken in the current dev setup. Any developer or auditor who clones and runs the project gets a broken first-run experience.
Recommendation: (a) Confirm whether `cloud/server` is meant to run on `7882` or `7878` — if `7878`, update `.env.local`. (b) Add a Vite proxy in `vite.config.ts` for `/api` → the server URL so relative API calls in `Projects.tsx` work. (c) Add a startup health-check or a dev-mode banner that detects `ERR_CONNECTION_REFUSED` and renders `"Server not reachable at <SERVER_URL> — run cloud/server with npm run dev"` rather than silently failing per-request.

---

### Major

**M-1 — Titlebar search box is 29px tall — below 44px WCAG touch target**
Location: `ui/components/TitleBar.tsx` / `.cfp-titlebar__search`.
Observation: `findings.json` captures the search button at `w: 360, h: 29` at desktop. On mobile it measures similar. WCAG 2.5.5 requires 44×44px minimum. The search button is the most prominent element in the titlebar — users will tap it first on mobile.
Why it matters: The tap target is 33% short of the minimum. On a touch device the user misses it or hits the titlebar region, which has no fallback behavior.
Recommendation: Increase `.cfp-titlebar__search` min-height to 44px (or 36px padded vertically, whichever achieves the 44px touch area). The visual appearance can stay compact with `line-height` control.

**M-2 — Avatar button is 28×28 — severely below 44px minimum**
Location: `ui/components/TitleBar.tsx` / `.cfp-titlebar__avatar`.
Observation: `findings.json` shows the avatar button at `w: 28, h: 28` consistently across all viewports. The avatar is the primary entry point for sign-out and profile — undersized touch targets here directly harm retention on mobile.
Recommendation: Wrap the 28px visual circle in a 44×44 invisible tap area via `padding` + `min-width/min-height: 44px` on the `<button>`. The circle stays 28px visually.

**M-3 — Org switcher button text reads "cfyour orgs" — label concatenation bug**
Location: `Shell.tsx:264` — `org={inOrg ? (org as string) : "your orgs"}` passed to `TitleBar`.
Observation: `findings.json` shows the button labeled `"cfyour orgs"` — the `"cf"` org glyph prefix is not space-separated from `"your orgs"`. Screenshot `org-picker/desktop.png` confirms: the titlebar button reads `cf your orgs` with a small gap, but the accessible button text is `"cfyour orgs"` (no space), so screen-readers say "cf your orgs" run together.
Why it matters: Accessible label is malformed. When read by a screen-reader it sounds like one word.
Recommendation: The accessible label for the org switcher should be `aria-label="Switch organization"` set explicitly on the button, not derived from concatenated text content.

**M-4 — React Router v6 future-flag warnings fire on every page load**
Location: `cloud/platform/src/main.tsx` — `<BrowserRouter>` has no `future` prop.
Observation: Every page in `findings.json` has two identical console warnings: `"⚠️ React Router Future Flag Warning: React Router will begin wrapping state updates in React.startTransition in v7…"` and `"…Relative route resolution within Splat routes is changing in v7…"`. These fire on every navigation.
Why it matters: These warnings clutter the console, masking real errors. They are trivially silenced by adding `future={{ v7_startTransition: true, v7_relativeSplatPath: true }}` to `<BrowserRouter>`.
Recommendation: Add the two future flags. This is a one-line change per flag and avoids the warnings cascading into noise that hides real issues.

**M-5 — All segmented control options ("Just me", "2–5", etc.) are 29px tall**
Location: `onboarding/OnboardingFlow.tsx` segmented controls.
Observation: Every segment button (`Just me`, `2–5`, `5–20`, `20+`, `Dash`, `CLI`, `IDE`, `All three`) measures 29px tall across all viewports. On mobile these are the primary interaction controls for the only inputs in the onboarding flow.
Screenshot evidence: `onboarding-welcome/mobile.png` — the segmented row is clearly compact; finger-sized taps on `"CLI"` (48px wide, 29px tall) or `"IDE"` (49px wide, 29px tall) are imprecise.
Why it matters: The onboarding step is the highest-stakes screen — if the user mis-taps and picks the wrong team size or primary client, they may not notice and the proposed org will reflect wrong answers.
Recommendation: Increase segment button `min-height` to at minimum 36px (WCAG advisory), ideally 44px. On mobile especially, taller is better.

**M-6 — "Continue →" and "← Back" nav buttons in onboarding are 33px tall**
Location: `onboarding/OnboardingFlow.tsx` footer row.
Observation: `Continue →` measures `w: 95, h: 33` on mobile. `← Back` measures `w: 72, h: 33`. Both are below 44px.
Why it matters: These are the primary forward/back controls for the entire 5-step flow. Undersized on mobile.
Recommendation: Increase to `min-height: 44px` and `min-width: 88px` for `Continue`, matching the `cfp-btn` spec in `globals.css`.

**M-7 — "scaffold · wire later" pill visible to real users on Board, Sessions, Knowledge, Diagnoses, Billing, Settings**
Location: `pages/OrgRoute.tsx:38-42` — `Surface` component renders a `<Pill tone="warn">scaffold · wire later</Pill>` for every unimplemented tab.
Observation: `board/desktop.png`, `billing/desktop.png` — warm amber pill in engineering language, below the tab description. Five nav entries lead here.
Why it matters: Engineering status metadata shown to users erodes trust. "scaffold · wire later" reads as "this app is unfinished" to a founder evaluating the product.
Recommendation: Replace with a calm coming-soon state: `"This surface is in the roadmap — for now, Dash is where this lives. [Open in Dash →]"`. This turns a developer note into a product redirect. Prior audits flagged this; it has not been actioned.

**M-8 — Sidebar section headings "WORKSPACE" and "ORG ADMIN" are `<h2>` elements visually styled as eyebrows but are semantic headings inside `<nav>` — the heading level is inconsistent with page H1**
Location: `Shell.tsx:170, 182` — `<h2 className="cfp-side-section__heading">`.
Observation: The page H1 is 28–36px display text in the main content. The sidebar H2 is an eyebrow-style mono label. Screen readers will announce "Workspace, heading level 2" immediately after entering the sidebar, which implies the sidebar sections are children of a top-level section. This is structurally accurate but `<h2>` is too prominent for eyebrow-level labels — use `<h3>` if there's an outer page `<h2>`, or mark them with `role="presentation"` if they're purely visual labels.
Recommendation: Demote to `<h3>` or add `aria-hidden="true"` and use a visible-only label. Low-impact but worth noting for a dev-tools product whose target user base includes accessibility-conscious engineers.

**M-9 — "Failed to fetch" on the invite accept page with no recovery action**
Location: `pages/InviteAccept.tsx` — renders `"Couldn't load invite / Failed to fetch"` with no retry button and no link back to sign-in.
Observation: `invites/desktop.png` — centered card on warm paper: `"SOMETHING WENT WRONG"` eyebrow, `"Couldn't load invite"` H1, `"Failed to fetch"` body. That is the entire page — no button, no retry, no escape path.
Why it matters: Invite links are sent to brand-new users who have never seen the app before. If their first view is `"Failed to fetch"` with no escape, they will close the tab and never return.
Recommendation: Add (a) a friendly rewritten error message (see C-1), (b) a "Try again" button that retries the fetch, (c) a "Go to sign in" link so the user has somewhere to go. The prior static audit flagged this; it remains unaddressed.

---

### Polish

**P-1 — "Dev mode" footer note visible at tiny 10px on sign-in page**
Location: `pages/Auth.tsx:153-165` — `fontSize: 10, letterSpacing: "0.06em"`.
Observation: The dev mode footer ("DEV MODE · SET VITE_CLERK_PUBLISHABLE_KEY FOR REAL AUTH") is `10px` monospace all-caps. At 1440px desktop it reads but at 390px mobile it is nearly illegible.
Recommendation: Bump to `11px`. It's diagnostic text so it should be subtle, but not unreadable.

**P-2 — Onboarding inputs lack associated `<label>` elements**
Location: `onboarding/OnboardingFlow.tsx` — two text inputs ("What are you building?", "What's your team called?").
Observation: `findings.json` flags `formInputsWithoutLabel: 2` on every onboarding viewport. The question labels above the inputs are `<p className="cf-eyebrow">` elements, not `<label for="...">` elements. Screen readers will not announce the question when focusing the input.
Recommendation: Replace the `<p>` labels with `<label htmlFor="...">` elements pointing at the corresponding `<input id="...">`. This is a two-line change per field.

**P-3 — "Start onboarding →" CTA on org picker has no hover state**
Location: `pages/OrgPicker.tsx:149-171` — the create-org `<button>` has a transparent background and no CSS transition.
Observation: On `org-picker/desktop.png` the button renders as a plain bordered rectangle. Hovering shows no visual change (no `:hover` rule in inline styles or via class).
Recommendation: Add `transition: background 120ms` and `:hover { background: var(--surface-2); }` via a class.

**P-4 — Sidebar "Sign out" link sits at the bottom-left corner with no visual separation from nav items**
Location: `Shell.tsx:244-248` — `<SideItem label="Sign out" onClick={signOut} />` inside a `<div style={{ marginTop: "auto" }}>`.
Observation: `org-picker/desktop.png` — "Sign out" appears flush at the bottom of the sidebar with no separator rule above it. On mobile it would be easy to mis-tap.
Recommendation: Add a `1px solid var(--rule)` separator above the sign-out item, and `padding-top: 8px`. This separates a destructive action from navigation items.

**P-5 — Eyebrow labels use org slug (all-caps from CSS) but the visible text is the raw slug, not the org display name**
Location: Every OrgRoute page — eyebrow reads `AUDIT-ORG · CANVAS` (slug, not display name).
Observation: In `OrgRoute.tsx`, the `org` variable is the URL slug (`audit-org`). The eyebrow therefore renders `audit-org · canvas` which is transformed to `AUDIT-ORG · CANVAS` by CSS `text-transform: uppercase`. If the org name is `"Acme Co"` and the slug is `"acme-co"`, the eyebrow reads `ACME-CO · CANVAS` — the hyphen survives text-transform and reads oddly.
Recommendation: In `CanvasSurface`, once the org loads, replace `orgSlug` in the eyebrow with `org.name` (from the API response). For the loading state, the slug is fine since the name is not yet available.

**P-6 — Command palette `<div role="option">` rows lack `tabIndex`**
Location: `components/CommandPalette.tsx:100-112`.
Observation: Palette rows are `<div role="option">` with no `tabIndex`. Mouse navigation works (hover + click), keyboard navigation works (arrow keys + enter), but tab-key focus does not move into the list rows. A user who tabbed into the palette and then pressed Tab again would exit to the backdrop rather than stepping through options.
Recommendation: Add `tabIndex={-1}` on each row so they are programmatically focusable (keyboard arrow navigation already works; this is about focus ring visibility on hover-enter). The input has focus on open, which is correct — this is a polish point not a blocker.

**P-7 — "← All orgs" sidebar link has no icon**
Location: `Shell.tsx:196` — `<SideItem label="← All orgs" onClick={() => navigate("/")} />`.
Observation: All other SideItem entries in the sidebar have an icon. The back-link uses a text arrow `←` as a substitute. This is inconsistent and the text arrow renders smaller than the icon grid.
Recommendation: Either pass `icon={Icons.history}` (already used in the command palette for the same semantic), or accept the text-arrow style but add a consistent secondary-color treatment (`color: var(--ink-mute)`) to signal it's a utility link, not a nav destination.

**P-8 — Error state on canvas ("Couldn't load this org") has no visible focus ring on the "← Back to all orgs" link**
Location: `pages/OrgRoute.tsx:139-148` — inline `style={{ color: "var(--accent)", textDecoration: "none" }}`.
Observation: The link has no `:focus-visible` treatment. Tab-navigating to it shows the default browser outline (which may be clipped by the accent color on some OS/browser combos) but no branded focus ring.
Recommendation: Add `className="cfp-link"` and define `.cfp-link:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }` in `globals.css`.

---

## Flow-by-flow walk

### `/signin` and `/signup`

Both render cleanly in dev mode. Single `"Continue with GitHub →"` button, correct brand copy, warm-paper background. The `"dev mode"` footer note is present and unintrusive. The card is vertically and horizontally centered across all three viewports.

Issues: CTA button is 39px tall (see M-5 pattern). Cross-link anchor ("Create an account", "Sign in") is 16px tall — a tap target of 16px height is unusable on mobile.

### `/onboarding/welcome`

Strong visual design. The `"Let's hire your company."` headline in Space Grotesk is well-weighted. The step counter + progress bar in the header is clear. The form fields are clean.

Issues: Two unlabeled inputs (P-2). All segment buttons 29px tall (M-5). `"Continue →"` and `"← Back"` are 33px (M-6). Deep-link guard means `/propose` through `/handoff` all bounce here (C-3).

### `/onboarding/propose` through `/handoff`

Inaccessible by direct URL in any clean session — all redirect to welcome (C-3). Screenshots therefore all show the welcome stage. The prior static audit notes these screens; their visual quality cannot be confirmed in this run.

### `/` (org picker)

Renders correctly in layout. Sidebar shows "No orgs yet. Create one to get started." + "New org" below. Main content shows the eyebrow "YOUR ORGS", an H1 "No orgs yet", the amber "Failed to fetch" error banner (C-1), and the "Start onboarding →" CTA card.

Specific issues: The error banner and empty-state CTA are simultaneously visible — the user sees both a failure message and a call-to-action card, which are contradictory at first glance. If the server were reachable and returned zero orgs, only the CTA card should appear; the error banner should only appear on network failure, not on empty list. The current code correctly distinguishes `setError` vs `setOrgs([])`, but in this environment both fire because the fetch rejects rather than returning an empty array.

Tablet layout: Sidebar remains visible at 820px width, consuming ~230px of the 820px viewport, leaving ~590px for content. This is workable but the content area uses `padding: 28` so the effective content width is 534px — fine.

Mobile layout: Hamburger navigation works. Sidebar is hidden by default on mobile. The "cf audit-org" org switcher and avatar button are in the titlebar strip. Clean.

### `/orgs/:org/canvas`

Error state ("Couldn't load this org / Failed to fetch") renders correctly in all three viewports. The error card has an H1, a body, and a "← Back to all orgs" accent link. Layout is coherent.

Missing from happy-path: the Read-Only banner, the dotted canvas with agent nodes, the "Open in Dash →" button, the member AvatarStack, and the canvas flex-wrap agent grid are all only visible when the API responds.

### `/orgs/:org/projects`

Shows `"Couldn't load projects: Unexpected token '<'…"` — the raw JSON parse error (C-2). The H1 "Projects" is visible. The eyebrow is correct. But the error body is a JavaScript exception string.

Note: Projects uses a relative `/api/orgs/…` URL without the `SERVER_URL` prefix (it calls bare `fetch("/api/…")`), so it hits Vite which serves its HTML fallback — the subsequent `res.json()` parse fails on `<!doctype`. This is distinct from the `apiFetch` pattern used by other pages and is the cause of the different (and worse) error message.

### `/orgs/:org/board`, `/sessions`, `/knowledge`, `/diagnoses`, `/billing`, `/settings`

All render the `Surface` scaffold component: eyebrow, H1, one-line description, amber "SCAFFOLD · WIRE LATER" pill (M-7). The sidebar navigation is functional and correct — active state highlights the current tab with a left-edge accent rail. These pages are not error states — they render their intended stub content. The "scaffold · wire later" pill is the concern.

### `/orgs/:org/team`

Renders only: eyebrow "AUDIT-ORG · TEAM" and the body text "Failed to fetch". No H1, no CTA, no recovery path (M-9, C-1). The OrgMembers component's loading state correctly shows "loading…" then transitions to the error state, but the error state lacks structure.

### `/invites/:code`

Centered error card: `"SOMETHING WENT WRONG"` eyebrow, `"Couldn't load invite"` H1, `"Failed to fetch"` body. No retry, no escape link (M-9).

---

## Four-dimension critique

### 1. Interactivity

**Strengths:** Command palette (⌘K) is fully wired — fuzzy search, keyboard navigation (arrow keys, Enter, Escape), grouped results. AvatarMenu is properly focused on open, closes on Escape, has `role="menu"` and `role="menuitem"`. Hamburger drawer fires on mobile, closes on route change. TitleBar org switcher opens the picker on click.

**Gaps:** Search box tap target 29px (M-1). Avatar tap target 28px (M-2). Segmented control options 29px on a first-impression screen (M-5). Navigation buttons in onboarding 33px (M-6). Cross-links ("Create an account", "Sign in") on auth pages are 16px tall — the smallest tap target in the app. Form inputs in onboarding lack `<label>` elements (P-2). Error states on team and invites have no recovery affordance (M-9).

### 2. Cleanness

**Strengths:** The warm-paper palette is consistent across all pages — `--paper` background, `--surface-2` cards, `--ink`/`--ink-mute` text hierarchy. Token discipline is largely intact (no raw hex observed in this pass except in the prior-audit-flagged onboarding cases). Typography is cohesive: Space Grotesk for display, Geist for body, JetBrains Mono for eyebrows and meta. The sidebar section structure (WORKSPACE / ORG ADMIN) with icon-labeled items is clean and scannable.

**Gaps:** Five pages render identical scaffold placeholders — at 1440px desktop these look like a wall of near-empty screens. The "SCAFFOLD · WIRE LATER" pill is engineering jargon. Three distinct error presentation patterns coexist: (a) full page H1 + body + accent link (canvas), (b) amber banner + empty grid (org picker), (c) bare body text with no H1 (team, projects). No shared `<ErrorState>` component. The org-picker error banner (`background: var(--warn-bg)`) uses the warning color scheme for a network error that is not really a user warning — consider `--paper-2` with a `--ink-mute` text tone instead, which is lower alarm but cleaner.

### 3. Animations

**Strengths:** The progress bar at the top of onboarding fills incrementally as the step advances. The brand uses restraint — no shimmer loaders, no bouncing, no parallax. The hover transitions on sidebar items are fast.

**Gaps:** No `prefers-reduced-motion` check was found in the scan (no `@media (prefers-reduced-motion: reduce)` block in the onboarding progress bar animation). The command palette has no open/close transition — it appears and disappears instantly, which is jarring for a modal that occupies the center of the screen. A simple `opacity` + `translateY` fade over 120ms would suffice. The drawer on mobile has no slide animation — it appears instantaneously. Both gaps make the UI feel snappier than intended but also cheaper than the warm-paper brand suggests.

### 4. Flow and Button Logic

**Strengths:** The onboarding flow has a clear 5-step spine. The "Continue →" / "← Back" navigation is consistent. The titlebar step counter ("Step 1 of 5 · welcome") plus the progress bar give persistent orientation. The command palette is genuinely useful for power-user navigation between orgs and sections.

**Gaps:**

- **Dead-end after server failure.** On team and invites, the user has no path forward. No retry, no back-link, no escape. Any backend hiccup strands the user (C-1, M-9).
- **Onboarding steps 2–5 cannot be reached directly.** This blocks testing, support links in emails, and any browser-refresh during the flow (C-3).
- **"Start onboarding →" appears even when there is a fetch error.** A user who sees "Failed to fetch" followed by "Start onboarding →" will be confused: did they have orgs? Did the fetch fail silently before they could see them? The CTA should be suppressed or visually separated from the error until the fetch is resolved.
- **Sign-out is in the sidebar at root and in the AvatarMenu — but not when inside an org.** When inside an org the sidebar shows "← All orgs" at the bottom. The AvatarMenu provides sign-out, but its anchor (the avatar button) is 28px tall (M-2). The primary sign-out affordance is therefore a near-invisible button.
- **Scaffold pages have no "coming soon" redirect.** Board, Sessions, Knowledge, Diagnoses, Billing, Settings show description text but give the user nothing to do. A "Open in Dash" link for the locally-runnable equivalents (Board, Sessions) would reduce dead ends.

---

## Top 5 priorities by impact-to-effort

1. **Fix the server URL / proxy so API calls reach the backend.** Update `.env.local` to point to the actual running port, add a Vite proxy for `/api`, or add a dev-mode health-check banner. Until this is fixed, most of the app shows error states to every developer who runs it. Impact: unblocks the entire authenticated surface. Effort: 30 minutes.

2. **Replace raw error strings with user-readable messages.** Three distinct locations (`apiFetch` catch, `Projects.tsx` JSON parse, `InviteAccept` error state) surface JavaScript exception text. A shared `humanizeError(e)` helper in `lib/api.ts` that maps `"Failed to fetch"` and `SyntaxError` → friendly strings would fix all three. Impact: first-impression screen quality, support ticket volume. Effort: 1–2 hours.

3. **Add recovery actions to empty error states.** Team (`OrgMembers`) and Invites (`InviteAccept`) error states have no H1 and no escape path. Minimum: add an H1, a one-line message, and a "← Back" / "Try again" button. Impact: user retention on error. Effort: 1 hour.

4. **Increase tap target sizes for titlebar controls and onboarding inputs.** Search box, avatar button, segment controls, and the primary onboarding CTA are all below 44px. Min-height changes in globals.css. Impact: mobile usability on the highest-traffic screens. Effort: 2 hours.

5. **Suppress / replace "scaffold · wire later" pill on production-facing tabs.** Replace with a calm "coming soon" state that links to Dash for the desktop-equivalent feature. Impact: trust and product polish on routes users can reach through the sidebar. Effort: 30 minutes (change the `Surface` component body text and replace the Pill).

---

## What is already working well

1. **Dev-mode auth bypass works correctly.** `localStorage.cf_dev_user` is set, `RequireAuth` passes, the shell renders, and the app is auditable without Clerk. The prior playwright audit failed entirely on this — now it works cleanly.

2. **Mobile hamburger navigation is solid.** The drawer opens and closes correctly, route changes close it automatically, and the `aria-label`/`aria-expanded` attributes are correctly set. At 390px the titlebar is clean and uncluttered with the hamburger, org switcher, and avatar in a reasonable strip.

3. **Command palette (⌘K) is genuinely good.** Fuzzy search, keyboard navigation, grouped actions, correct ARIA (`role="dialog"`, `role="listbox"`, `aria-selected`), Escape to close, focuses on open. This is the best-implemented interactive component in the app.

4. **Onboarding welcome screen is the strongest visual surface.** The display headline, eyebrow, progress bar, and segmented controls are well-composed at all three viewports. The warm-paper palette works especially well here — the form feels lightweight rather than bureaucratic.

5. **Token discipline in new code is strong.** No raw hex values were found in `Shell.tsx`, `OrgRoute.tsx`, `Auth.tsx`, `AvatarMenu.tsx`, or `CommandPalette.tsx` — all use `var(--...)` references. The prior audits called out inline hex; those specific instances appear to have been cleaned up.

---

## One bold suggestion

**Make the error state a product moment.** Right now "Couldn't load this org / Failed to fetch" is a dead end. But this is a developer product whose users understand network errors. Instead of a generic error card, render an inline diagnostic: the URL the app tried to reach (`http://127.0.0.1:7882/api/orgs/audit-org`), whether it was a connection refused or a non-OK status, and — critically — the exact shell command to start the server (`cd cloud/server && npm run dev`). This turns the error screen from a user-unfriendly dead end into a useful debug panel for the developer audience, reinforces the "CLI-first" brand voice, and dramatically reduces "why is nothing loading?" support friction. Gate it behind `CLERK_ENABLED === false` (dev mode only) so production users never see it.

---

## Per-route screenshots

```
/Users/nealkotval/crawfish/.audit/userflow/platform-full/
├── signin/{mobile,tablet,desktop}.png
├── signup/{mobile,tablet,desktop}.png
├── onboarding-welcome/{mobile,tablet,desktop}.png
├── onboarding-propose/{mobile,tablet,desktop}.png     ← bounced to /welcome (C-3)
├── onboarding-install/{mobile,tablet,desktop}.png     ← bounced to /welcome (C-3)
├── onboarding-hired/{mobile,tablet,desktop}.png       ← bounced to /welcome (C-3)
├── onboarding-handoff/{mobile,tablet,desktop}.png     ← bounced to /welcome (C-3)
├── org-picker/{mobile,tablet,desktop}.png             ← error banner (C-4)
├── canvas/{mobile,tablet,desktop}.png                 ← error state (C-4)
├── projects/{mobile,tablet,desktop}.png               ← JSON parse error (C-2)
├── board/{mobile,tablet,desktop}.png
├── sessions/{mobile,tablet,desktop}.png
├── knowledge/{mobile,tablet,desktop}.png
├── diagnoses/{mobile,tablet,desktop}.png
├── team/{mobile,tablet,desktop}.png                   ← no H1, no recovery (M-9)
├── billing/{mobile,tablet,desktop}.png
├── settings/{mobile,tablet,desktop}.png
└── invites/{mobile,tablet,desktop}.png                ← no recovery (M-9)
```
