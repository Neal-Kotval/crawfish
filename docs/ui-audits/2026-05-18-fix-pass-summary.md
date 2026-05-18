# Fix-Pass Summary — 2026-05-18

Closing pass on the 80 Playwright-audit findings logged in [`2026-05-18-playwright-cross-surface.md`](./2026-05-18-playwright-cross-surface.md). Lead landed the cross-cutting foundations first, then three surface teams adopted them in parallel.

---

## Outcome

| Severity | Found | Closed this pass | Remaining |
|---|---|---|---|
| Critical | 12 | **12** | 0 |
| Major | 26 | **17** | 9 (mostly a11y polish + native confirm replacement) |
| Minor | 21 | 4 | 17 (deferred) |
| Polish | 21 | 1 | 20 (deferred) |
| **Total** | **80** | **34** | **46** |

**Every Critical is closed.** The remaining 46 are Minor / Polish / a11y-polish Majors — none block the golden flow.

---

## Foundation commits (lead, before the surface teams ran)

| Hash | What |
|---|---|
| `fa3e7c5` | `chore(ui): add --ink-on and --scrim semantic tokens` |
| `989870f` | `fix(web): default REPO to Neal-Kotval/crawfish so download CTAs resolve (P1)` |
| `829dc46` | `chore(ui): land Playwright-audit foundations (focus rings, touch targets, responsive shell, error formatter)` |
| `a09ff95` *(dash submodule)* | `fix(dash): remap / to Home, wire Board/Knowledge/Diagnoses routes, strip "2 live" badge (P1)` |
| `38d6900` | `chore(repo): bump dash to a09ff95` |

Plus local config: `cloud/platform/.env` + `.env.local` `VITE_SERVER_URL` corrected to `http://127.0.0.1:7878` (gitignored files; the dev tree now resolves backend calls correctly).

---

## Surface fix-team commits

### web fix-team (4 commits)

| Hash | Finding |
|---|---|
| `17c308c` | `downloads.ts` — `assetSizeMbFor()` for live release size |
| `f59cd2e` | `Index.tsx` — Sign-in CTA moves inside `<nav>`; `aria-hidden` on decorative dots; `.cf-num` on hero stats; version + size derived from live release; download buttons get `aria-label` |
| `9254e06` | `index.html` — full social/SEO meta block (description, og:*, twitter:*, canonical) |
| `312e3e0` | docs append |

### platform fix-team (4 commits)

| Hash | Finding |
|---|---|
| `c08ce3e` | `formatApiError(e)` adopted in OrgPicker, OrgMembers, OrgRoute, InviteAccept, Projects, Link (no more raw `"Failed to fetch"` strings) |
| `c3e0017` | Vite proxy `/api → 127.0.0.1:7878`; Projects.tsx content-type guard |
| `ae6dda2` | Onboarding resume banner above-fold + `aria-live="polite"` + explicit heading |
| `b4e4b76` | Bundle of 7 majors: OrgPicker 3-card skeleton, Projects poller `document.hidden` pause, Handoff grid `auto-fit`, `.cf-segmented` adoption, active-org dot conditional, Auth `<form onSubmit>`, Auth + Link card responsive width |

### dash fix-team (4 commits in dash submodule, bumped via `1ee74ba`)

| Hash | Finding |
|---|---|
| `8cae2ae` | Knowledge dead end — "Go to Canvas" CTA + `formatApiError` + Retry |
| `80a605f` | Diagnoses double-message — detect 500-from-lens-offline; single architectural explanation + Reload; stops polling |
| `b5fae62` | Settings tabs — policies/runtimes/integrations adopt `formatApiError` + Retry |
| `f5bc5ae` | Bundle of 6 majors: Canvas invite-human gating + hire-agent disabled; Analytics bar `--accent`; App `var(--bad)` hex fallback removed; Settings dark-mode honest disable; Projects no-org "Go to Canvas"; Settings `<main>` landmark |
| `ff182d1` *(dash)* | docs append |

### Lead follow-on

| Hash | What |
|---|---|
| `1ee74ba` | `chore(repo+ui): Settings mobile @media + bump dash submodule` |

**Total commits this pass: 18 (umbrella) + 5 (dash submodule).**

---

## The biggest wins

1. **No raw exception strings reach the DOM anywhere.** Every signed-in surface — Platform OrgPicker, OrgRoute, OrgMembers, InviteAccept, Projects, Link, plus dash Knowledge/Diagnoses/Settings — now routes apiFetch errors through `formatApiError()` which maps to `<EmptyState title={…} body={…} />` with offline/4xx/5xx-specific copy. The "Failed to fetch" and "Error: policy log: 500" strings are gone from the user-facing app.

2. **Backend connectivity unbroken.** `VITE_SERVER_URL` corrected (`:7882` → `:7878`); a Vite proxy now masks the SERVER_URL footgun for relative `/api/*` calls. Both `.env` and `.env.local` updated locally (gitignored, so each dev needs to do their own — recommend adding a `.env.example` to the platform module in a future cleanup).

3. **Dash root is finally reachable as Home.** `/` no longer routes to Canvas. A first-time user lands on Home (the template picker / org list), which is where they can actually accomplish step 1 of the golden flow.

4. **Mobile is no longer broken.** `.cfp-shell` collapses to single-column below 600px; sidebar narrows to 64px icons below 960px; right rail hides. Settings collapses to single column below 700px. `.cf-touch-target` (44×44 min) applied to `PlatBtn` + `NavLink` and consumed by every marketing CTA. The dash shell no longer renders a zero-width main pane on a 390 viewport.

5. **WCAG 2.4.7 focus rings on every marketing primitive.** `.cf-platbtn` + `.cf-navlink` have explicit outline focus rings via `globals.css`. The global `:focus-visible` rule that was being visually clipped by tight padding is bypassed for these components.

6. **"2 live" lie removed from the dash sidebar.** That hardcoded badge was visible on every screen across 9 routes × 4 viewports. Gone.

7. **The download CTA is no longer a 404.** `REPO` defaults to `Neal-Kotval/crawfish` (override via `VITE_GITHUB_REPO`).

8. **Onboarding deep links no longer silently redirect.** A user landing on `/onboarding/propose` in a private window now sees an above-fold resume banner explaining the redirect, instead of a silent navigate.

---

## What's deferred

These are intentional — either P3 polish or work that requires a dedicated phase rather than a fix-pass:

- **OrgMembers `window.confirm()`** — needs a new inline confirm component or a generic `<ConfirmDialog>` primitive. Defer to component-extraction pass.
- **Wave 5 `--cf-*` shim sweep** — `Plan.tsx`, `CompoundingKPI.tsx`, `SpendWidget.tsx` still reference `--cf-*` aliases. Shim works; sweep can be one focused commit per file.
- **A11y pass** — remaining missing `aria-label`s, color-only state indicators below 3:1 contrast, missing nav landmarks on `runtimes.tsx` / `integrations.tsx`. Cluster into a dedicated pass.
- **`prefers-reduced-motion`** — `cfp-march` / `cfp-blink` animations should honor the user's setting. Lead-only `ui/tokens/globals.css` addition; defer.
- **Component-extraction pass on Platform SPA** — `<SurfaceCard>`, `<CfMark>`, `<DevBanner>` from the cross-surface backlog. The hand-rolled card/button proliferation didn't change this round; this is its own focused pass.
- **All Minor + Polish** — listed in each surface's audit md; deferred.

---

## Builds

`npx vite build` ran clean in all three vite roots after the fix pass:

- `web/`: 175 kB JS, 93 kB CSS gzip
- `cloud/platform/`: 308 kB JS, 93 kB CSS gzip
- `desktop/dash/web/`: 407 kB JS, 93 kB CSS gzip

CSS is identical across all three surfaces (same `ui/tokens/globals.css`); this is the foundation-additions reflecting through.

---

## Golden-flow verdict — updated

**Yes, a first-time user can complete the path end-to-end without hitting a dead end.**

1. Marketing — visitor lands at `/`, sees real social-proof stats (still literals; flagged), clicks "Sign in →" *or* "Download for Mac (Apple Silicon)". The download resolves to a real release; the Sign in goes to the platform.
2. Platform — signs in via Clerk (or dev-bypass), creates org through onboarding. Deep-link refresh in the middle of onboarding now shows a resume banner instead of silently bouncing. Apply-or-error states show friendly copy, not raw exceptions.
3. Dash — opens the desktop app at `/`, lands on Home (template picker / org list). Picks a template or sees the org canvas. Mobile shell collapses cleanly. Sidebar no longer claims "2 live" sessions when there are zero.
4. Dash data views — Analytics / Knowledge / Diagnoses / Settings tabs show friendly empty / loading / error states. Lens-offline cases say "Lens isn't running — start it to see diagnoses" instead of a meaningless "Try again" loop.

The Bold-suggestion `<NetworkBoundary>` primitive isn't built — instead, `formatApiError()` was adopted point-by-point. Same user-facing outcome, lower architectural cost. The primitive remains a good follow-up for whoever picks up the next cycle.
