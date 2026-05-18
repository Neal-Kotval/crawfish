# Playwright Cross-Surface Synthesis — 2026-05-18

Synthesis of four `ui-auditor` Playwright walks against the live dev servers (web :5173, platform :5174, dash :7881). Each agent applied a senior-product-designer critique pass across four dimensions (Interactivity / Cleanness / Animations / Flow & Button Logic), with multi-viewport screenshot evidence (mobile 390 / tablet 820 / desktop 1280–1440 / wide 1920).

**Source audits**
- [`2026-05-18-web-marketing-playwright-full.md`](./2026-05-18-web-marketing-playwright-full.md) — 23 findings (2 Crit, 7 Maj, 11 Min, 3 Pol)
- [`2026-05-18-platform-spa-playwright-full.md`](./2026-05-18-platform-spa-playwright-full.md) — 21 findings (4 Crit, 9 Maj, 8 Pol)
- [`2026-05-18-dash-studio-playwright-full.md`](./2026-05-18-dash-studio-playwright-full.md) — 18 findings (3 Crit, 5 Maj, 5 Min, 5 Pol)
- [`2026-05-18-dash-data-views-playwright-full.md`](./2026-05-18-dash-data-views-playwright-full.md) — 18 findings (3 Crit, 5 Maj, 5 Min, 5 Pol)

**Aggregate: 80 findings (12 Critical, 26 Major, 21 Minor, 21 Polish).**

---

## The big story: the static audits missed almost everything

This cycle's static-source audits caught 26 P1/P2 issues. The Playwright walks caught **80**, including **12 Criticals** that source-only review couldn't see:

- Routes that silently redirect (onboarding deep links, `/` → Canvas → no path to Home)
- API config that breaks every signed-in surface (`VITE_SERVER_URL` → wrong port)
- Raw exception strings ("Failed to fetch", "Error: policy log: 500") rendered as primary empty-state content
- Touch targets below 44px across every mobile viewport
- Focus rings missing on every interactive element across every surface
- Three-column shell layouts collapsing to zero-width main panes on mobile

**The static audit was correct about what's in the code. The Playwright audit was correct about what users actually experience.** Both passes are necessary; neither is sufficient alone.

---

## Critical findings, ranked

### 1. Backend connectivity is broken everywhere it matters

The single highest-impact issue, surfacing in 3 of 4 surfaces:

- **Platform (C-4):** `VITE_SERVER_URL=http://127.0.0.1:7882` but no process listens on `:7882`. The actual cloud/server is at `:7878`. Every `apiFetch` returns `ERR_CONNECTION_REFUSED`.
- **Platform (C-1):** As a consequence, raw `"Failed to fetch"` JavaScript error strings render as user-facing body text on `/`, `/orgs/:org`, `/orgs/:org/team`, and `/invites/:code`. Evidence: `team/desktop.png` shows a single monospace line "Failed to fetch" with no heading, no recovery path.
- **Platform (Projects.tsx):** Uses bare relative `/api/...` URLs (not prefixed with `SERVER_URL`); hits Vite directly, gets HTML fallback, then `res.json()` throws — the error string surfaces.
- **Dash data views (B3):** All five Settings data tabs (Policies, Runtimes, Integrations, Diagnoses, Knowledge) render raw HTTP error strings: `"Error: policy log: 500"`, `"GET /api/runtimes 500"`, `"orgs: 500"`. Default state for any cold-launch user without lens running.

**Fix path:**
1. Confirm the actual cloud/server port (probably `:7878` — visible via `lsof -nP -iTCP -sTCP:LISTEN`).
2. Fix `cloud/platform/.env.local` `VITE_SERVER_URL`.
3. Add a Vite proxy for `/api` routes (eliminates the SERVER_URL-vs-relative-path footgun).
4. **Globally** wrap `apiFetch` failures in a `<ServiceOffline>` empty state with a "Retry" button. Never let raw `"Failed to fetch"` reach the DOM.

### 2. Mobile is broken on every surface

- **Web marketing (F-02):** Every interactive element fails 44×44px. Download buttons render 38px; nav link 34px; IDE buttons 35px. At 390px viewport a download tap has a high miss rate.
- **Dash studio (Critical):** `cfp-shell` three-column grid (232 sidebar + main + 304 rail) has no responsive breakpoints. At 390px, sidebar and rail consume the full width and `cfp-shell__main` is **zero pixels wide**. Canvas renders no agent nodes; AgentCanvas hero entirely disappears, leaving only three empty KPI cards.
- **Platform (multiple):** `OrgPicker`'s `auto-fill, minmax(320px,1fr)` grid means at 390 viewport (minus padding) the grid is 1 column → ok, but loading skeleton (one dashed card) reads as a broken org row. Onboarding's `1fr 1fr` handoff cards have no responsive fallback.
- **Universal:** No surface has a documented breakpoint set. Each surface invents its own — none of them work below 768.

**Fix path:** Land one shared breakpoint set in `ui/tokens/globals.css` (`@media (max-width: 1280px)`, `768px`, `480px`) and a `.cf-touch-target` utility class that enforces `min-height: 44px; min-width: 44px`. Every surface adopts it.

### 3. Routing dead ends

- **Dash studio (Critical):** `/` routes to `CanvasRoute`. `Home.tsx` (the template picker + org list) is **completely unreachable from the UI**. A first-time user has no path to create an org from the dash.
- **Platform (C-3):** `/onboarding/propose`, `/install`, `/hired`, `/handoff` all silently redirect to `/onboarding/welcome` when `sessionStorage` is empty (fresh tab, private window, browser refresh, deep link). The `showResumeNotice` banner explaining the redirect doesn't render above the fold — likely doesn't render at all. The progress bar reads "Step 1 of 5 · welcome" on all four screenshots.
- **Dash data views (B1):** `/knowledge` shows "Missing org id" empty state with **zero CTAs**. User is stranded.
- **Dash data views (B2):** `/diagnoses` shows two contradictory error messages simultaneously when lens is offline: the architectural explanation ("needs a running lens server") AND the generic transient-fault message ("Try again in a moment"). User retrying gets nowhere.

**Fix path:** Route audit — every route table entry needs (a) a happy path, (b) an explicit "precondition unmet" empty state with a primary CTA pointing to the next step, and (c) a "this URL is deep-linkable" verification. Onboarding's session-storage gate is a special case — either persist far enough to make deep links work, or add the missing resume banner above the fold.

### 4. Trust violations from fabricated data

- **Web marketing (F-01):** `REPO = "anthropics/crawfish"` doesn't resolve. **Every download button silently 404s** via the fallback `https://github.com/anthropics/crawfish/releases`. 100% of visitors hit a dead primary CTA.
- **Dash studio (Major, but visible on every screen):** `WORKSPACE_NAV.badge = "2 live"` as a string literal. The sidebar shows "2 live" on every screenshot across 9 routes × 4 viewports — including Sessions' own empty state, which confirms there are zero live sessions. A fabricated status indicator visible on **every screen of the app**.
- **Web marketing (P2):** Hero stats (`10,412 orgs`, `−35% factor`, `3.25× reduction`) are still literals presented as social proof. Carried over from the static audit.

**Fix path:** Search-and-destroy on all `badge:` literals, `count:` literals, and `stat:` literals in nav components and marketing copy. If the number isn't sourced from data, it's a lie.

### 5. WCAG violations across every surface

- **Web (F-04):** Zero hover or focus-visible state on `PlatBtn` or `NavLink`. Keyboard users see no focus ring. **WCAG 2.4.7 Level AA violation.**
- **Universal:** Audits found missing focus rings, missing aria-labels on icon-only buttons (revoke, close, copy), missing nav landmarks, native `window.confirm()` instead of accessible dialogs, `<div role="button">` without `onKeyDown`, color-only active indicators below 3:1 contrast.

**Fix path:** A11y phase — add `:focus-visible` to `PlatBtn`, `NavLink`, `cf-btn`, `cfp-btn`, every nav row. Use `--accent-hover` for the ring color (already a token). Replace `window.confirm()` with the `ImportModal` pattern. Audit color-only state.

---

## Cross-surface patterns by dimension

### Interactivity

| Issue | Surfaces affected |
|---|---|
| Missing focus-visible rings | web, platform, dash-studio, dash-data |
| Touch targets <44px on mobile | web (universal), platform (forms), dash (sidebar items) |
| Silent failures (network errors → no user feedback) | platform (all), dash-data (Settings tabs) |
| Dead/broken primary CTAs | web (download → 404), dash-studio ("Attach shell" — fixed) |
| Native `window.confirm()` | platform (OrgMembers) |

### Cleanness

| Issue | Surfaces affected |
|---|---|
| Hex literals in inline styles | platform-spa (fixed), web (fixed), dash-studio (fixed), dash-data (fixed) |
| Hand-rolled card/button primitives | platform (5+ variants), dash-studio (cfp-* mixed with cf-*) |
| Loading state pattern split (`EmptyState` vs `cf-empty` vs bare div) | dash-studio, dash-data, platform |
| Cramped or unprincipled whitespace | platform (auth dev-facade), dash (AgentCanvas) |
| Missing `prefers-reduced-motion` honor | universal |

### Animations

| Issue | Surfaces affected |
|---|---|
| Static loading states (no skeletons, just text) | platform, dash-data |
| No state-morph between empty → loaded | universal |
| `setInterval` drip-feeds presented as live work | platform onboarding (install stream) |
| No interruption handling (animations block input) | dash-studio (`AgentCanvas` tab transitions) |

### Flow & Button Logic

| Issue | Surfaces affected |
|---|---|
| Primary action invisible or fighting another button | web (no sign-in CTA — fixed), platform (Auth — fixed), dash (Canvas zoom + compounding) |
| Generic labels ("Submit", "OK", "Continue") | platform (onboarding next button), dash (some forms) |
| Dead ends without recovery CTA | dash-data Knowledge / Diagnoses, platform onboarding redirects |
| Backwards/escape paths missing | dash-studio (modal dialogs), platform onboarding |
| Permission/state mismatch (enabled buttons that do nothing) | dash-studio (zoom + compounding controls in Canvas), platform (Auth dev-facade — fixed) |

---

## Top 10 fix priorities (impact-to-effort)

1. **Fix `VITE_SERVER_URL` port in `cloud/platform/.env.local`.** Single config line. Unbreaks every signed-in surface.
2. **Add a global `apiFetch` error boundary that renders `<ServiceOffline>` instead of throwing.** ~20 LOC. Replaces every "Failed to fetch" / "Error: 500" leak.
3. **Remap dash's `/` route to `<Home />` (or whatever the org-picker is) and `/canvas` to `CanvasRoute`.** One line in the route table. Makes the dash actually navigable for new users.
4. **Strip `WORKSPACE_NAV.badge = "2 live"` from the dash sidebar.** Single line. Removes a brand-credibility lie visible on every screen.
5. **Land `:focus-visible` on `PlatBtn`, `NavLink`, `cf-btn`, `cfp-btn` in `ui/tokens/globals.css`.** ~10 LOC. Resolves WCAG 2.4.7 on every surface.
6. **Add `.cf-touch-target` utility class** with `min-height: 44px; min-width: 44px` and apply to `PlatBtn`, `NavLink`, dash sidebar rows. Fixes mobile-tap miss-rate.
7. **Fix `REPO` in `web/src/lib/downloads.ts`** to the actual repo or pull from `VITE_GITHUB_REPO`. Unbreaks the primary download CTA.
8. **Add a `@media (max-width: 960px)` rule to `.cfp-shell`** that collapses or hides the right rail and sets `min-width: 0` on `cfp-shell__main`. Unbreaks dash mobile.
9. **Fix onboarding step 2–5 deep links.** Either persist enough sessionStorage at session start, or render the resume banner above the fold. Today browser refresh = lose 30 seconds of progress.
10. **Replace dash-data Knowledge / Diagnoses empty-state messages** with a primary CTA pointing to the next step ("Go to Canvas to create an org", or similar).

---

## What's working well (from the audits)

Themes that came up positively across reports:

1. **Token system is correct.** Where surfaces use `var(--…)`, contrast is sound and colors stay on-brand. The breakdowns are at the seams (inline rgba / hex / `--cf-*` shim), not at the foundation.
2. **Empty-state component pattern is good when used.** `<EmptyState title="…" body={…} />` is widely deployed and reads consistently. The fixable issue is the surfaces that *don't* use it.
3. **Onboarding's narrative arc.** Welcome → Propose → Install → Hired → Handoff is a strong shape. The 5-stage progression and the install drip-feed (despite being theater) communicate "your company is being assembled" effectively. The dead deep-link bug is a configuration issue, not a flow issue.
4. **Dash studio cluster's data-real progress.** Board, Plan, Sessions, SessionDetail all render real data with proper empty/error states post-Canvas/AgentCanvas fixes. The cluster has gotten dramatically better in two cycles.
5. **Marketing's brand identity is strong.** Warm paper + vermillion + correct typefaces land convincingly. The hero "Hire your company in fifteen minutes." headline is sharp. The audit's complaints are about plumbing (touch targets, focus rings, dead downloads), not voice or visual direction.

---

## One bold suggestion

**Build a shared `<NetworkBoundary>` primitive in `@crawfish/ui` and wrap every data-loading surface in it.** Today every surface re-rolls its own "fetch → empty / loading / error" pattern, and the audits found that 100% of them leak something to the user when the backend is down. A single `<NetworkBoundary>` component that:

- catches `apiFetch` errors,
- distinguishes network-down vs 4xx vs 5xx,
- renders `<EmptyState>` with a contextual title (`"Service offline — start cloud/server to load your orgs"` for ERR_CONNECTION_REFUSED, `"You're not signed in"` for 401, etc.),
- exposes a Retry button,
- and never lets a raw exception string near the DOM,

…would eliminate the **largest single class of bug** identified across all four audits. It's also a high-leverage change: it teaches the codebase a vocabulary, not just a fix. New surfaces inherit the correct behavior by composition.

This is the kind of primitive a senior product designer would push for first, before any visual polish — because no amount of warm paper and vermillion saves a UI that says "Failed to fetch" as its primary content.
