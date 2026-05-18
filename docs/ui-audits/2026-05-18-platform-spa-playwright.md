# Crawfish Platform — UI Audit

**Date:** 2026-05-18
**Auditor:** Claude (ui-auditor agent)
**Target:** `cloud/platform` SPA at `http://localhost:5174`
**Walk script:** `/Users/nealkotval/crawfish/.audit/platform-walk.mjs`
**Screenshots:** `/Users/nealkotval/crawfish/.audit/userflow/platform/<route>/<viewport>.png`
**Raw findings JSON:** `/Users/nealkotval/crawfish/.audit/userflow/platform/findings.json`

---

## What I could and couldn't reach

The build I walked has `CLERK_ENABLED=true` (Clerk publishable key set in env). That means:

- The `localStorage.cf_dev_user` trick in `src/lib/useAuth.tsx:40` is a **dead code path** in this build — Clerk owns auth. `RequireAuth` redirected every protected route to `/signin`.
- I could not headlessly complete GitHub OAuth (third-party redirect to github.com), so **no authenticated screenshots exist** for `/`, `/orgs/*/canvas`, `/orgs/*/team`, `/orgs/*/projects`, `/orgs/*/board`, `/orgs/*/sessions`, `/orgs/*/knowledge`, `/orgs/*/diagnoses`, `/orgs/*/billing`, `/orgs/*/settings`, `/link/:code`.
- The platform **backend server is also not running** — every `/api/...` call returned `ERR_CONNECTION_REFUSED` (verified in console errors on `/invites/:code` and `/onboarding/install`). So even if I had auth, every data-driven surface would render its error state instead of its real state.

What I **did** walk:

| Route | Auth required | What rendered |
|---|---|---|
| `/signin` | no | Clerk widget |
| `/signup` | no | Clerk widget |
| `/onboarding`, `/onboarding/welcome` | no | step-1 questionnaire |
| `/onboarding/propose` → `/handoff` | no, but answers-gated | resume-redirect kicks user back to `/welcome` because sessionStorage is empty in a fresh context |
| `/invites/:bad-code` | no | "Couldn't load invite — Failed to fetch" error card (backend down) |
| `/link/:code` | yes | bounces to `/signin` |
| `/`, `/orgs/...` | yes | bounces to `/signin` |

Recommendation: the next agent should run the server (`cloud/server`) **and** a dev-mode build (`VITE_CLERK_PUBLISHABLE_KEY` unset, or add a flag the auditor can flip) to actually walk the org surfaces. Until then, the per-route audit below is split into **observed** (real screenshots) and **source-only** (inferred from code).

---

## Per-route screenshots

```
.audit/userflow/platform/
├── auth-signin/{mobile,desktop}.png         observed: Clerk widget
├── auth-signup/{mobile,desktop}.png         observed: Clerk widget
├── onboarding-welcome/{mobile,desktop}.png  observed: step-1 form
├── onboarding-propose/{mobile,desktop}.png  observed: redirected back to welcome
├── onboarding-install/{mobile,desktop}.png  observed: redirected back to welcome
├── onboarding-hired/{mobile,desktop}.png    observed: redirected back to welcome
├── onboarding-handoff/{mobile,desktop}.png  observed: redirected back to welcome
├── invite-notfound/{mobile,desktop}.png     observed: error card "Couldn't load invite"
├── device-link/{mobile,desktop}.png         observed: bounced to /signin (auth-gated)
├── org-picker/{mobile,desktop}.png          bounced to /signin
└── org-{canvas,board,sessions,knowledge,diagnoses,team,projects,billing,settings}/
    {mobile,desktop}.png                     bounced to /signin
```

---

## Console errors and network failures captured during the walk

- **Every page** triggered one `307 https://relaxed-dane-29.clerk.accounts.dev/npm/@clerk/clerk-js@5/dist/clerk.browser.js` redirect (this is normal Clerk CDN behavior, not a bug).
- `/invites/missing-code` and `/onboarding/install` each fired two `ERR_CONNECTION_REFUSED` console errors against the backend at `:8787` (the API). Symptom of `cloud/server` being down, not a frontend bug. But: the error UI on `/invites/missing-code` says **"Failed to fetch"** verbatim, which is a raw browser exception string leaking into the user's face. Fix: map common fetch failures to "We couldn't reach our servers. Check your connection and try again." (See [P1-N] below.)
- No JS pageerrors, no hydration warnings, no missing assets.

---

# Findings — prioritized

Tag legend:
- **P0** — blocks the user's stated complaint ("unintuitive and clunky"). Fix in the first batch.
- **P1** — bad, but unblocking. Fix in the second batch.
- **P2** — polish.

Each finding has a **source location** and a **concrete edit**. The next agent should not need to re-derive any of this.

---

## P0 — the user's specific call-out plus the clunkiness it represents

### [P0-A] Kill the fake macOS traffic lights
**Source:** `ui/components/TitleBar.tsx:29-44`, classes in `ui/tokens/globals.css:3322-3329`.
**Problem:** In the browser SPA the TitleBar renders three decorative dots (red/yellow/green) at the top-left of the chrome that look like macOS window controls but do nothing. They are explicitly described in the source as "decorative dots so the chrome still reads as a 'window' in the hi-fi artboard sense." That artboard sense is the wrong frame for a web app — it makes the surface feel like a screenshot of an app, not an app. The user named this specifically.
**Edit:**
1. Delete the `.cfp-titlebar__lights` / `.cfp-titlebar__light*` rules in `ui/tokens/globals.css` (lines 3322-3329).
2. Delete the `inTauri ? null : (<div className="cfp-titlebar__lights">...)` block in `TitleBar.tsx` (lines 38-44). Keep the `inTauri` branch that adds `paddingLeft: 78` for the Tauri shell — that's still needed where the OS does draw real lights.
3. In the browser, replace the left-edge padding with `padding-left: 14px` on `.cfp-titlebar` so the org switcher sits closer to the edge (currently the dots push everything right).

### [P0-B] Org switcher button is the *only* nav affordance for switching orgs but looks like a logo
**Source:** `ui/components/TitleBar.tsx:46-50`, `cfp-titlebar__org` in `globals.css:3330-3336`.
**Problem:** The "cf · <org name> · ▾" button is the org switcher. The chevron is tiny (`Icons.chevD`), there's no hover state pop, no visible focus ring, no border, and it shares typography with the surrounding chrome. New users will not understand they can click it. The Shell also passes `onOrgSwitch={() => navigate("/")}` which goes to the picker rather than opening a dropdown — fine as a behavior, but the affordance has to read as a menu.
**Edit:**
1. In `globals.css`, give `.cfp-titlebar__org` a `border: 1px solid transparent; border-radius: var(--r-sm); padding: 4px 8px; transition: background 120ms, border-color 120ms;` and hover/focus rules: `:hover { background: var(--surface); border-color: var(--rule-3); }` and `:focus-visible { outline: 2px solid var(--accent); outline-offset: 1px; }`.
2. Increase the chevron size (use `Icons.chevD` wrapped in a 14px span) and add a subtle `aria-label="Switch organization"`.
3. Replace the navigate-to-`/` behavior with a real popover that lists the user's orgs (data is already fetched in `Shell.tsx:51-62` — lift it up). Out of scope for this audit but worth filing.

### [P0-C] ⌘K search is a fake button that goes nowhere
**Source:** `ui/components/TitleBar.tsx:52-58`, called from `Shell.tsx:99-105` with no `onSearch` prop.
**Problem:** The titlebar shows a giant search input with the placeholder "Find a task, agent, or chunk…" and a ⌘K hint. Clicking it does nothing. Pressing ⌘K does nothing. It is the largest piece of UI on the chrome and it is a lie.
**Edit:**
1. Wire it. Add a minimal command-palette modal (even if it only contains "Go to canvas / Go to team / Sign out / Switch org" for now). Mount a `keydown` listener for `(e.metaKey||e.ctrlKey) && e.key==='k'` in `Shell.tsx` that opens it.
2. Until that ships: pass `searchPlaceholder="Coming soon — keyboard search"` and `disabled` styling, or remove the search button from the titlebar entirely. A visible-but-disabled stub is better than a clickable lie.
3. The ⌘K hint should also work on Windows/Linux (^K). Detect platform and render the right glyph.

### [P0-D] Cost / tokens meter is dead chrome
**Source:** `ui/components/TitleBar.tsx:60-80`, `Shell.tsx:99-105` (no `costToday` / `tokensPerHr` passed).
**Problem:** The component supports `costToday` and `tokensPerHr` but the platform Shell never passes them. So the meter just… doesn't render. Harmless today, but the next agent should either wire it to real numbers or remove the prop slots from the platform's titlebar so the surface doesn't look like the dash shell.
**Edit:** Either (a) remove the `costToday`/`tokensPerHr` lines from the `TitleBar` invocation in `Shell.tsx:99-105` and from the props in `TitleBar.tsx:8-9` (platform doesn't need a meter on this chrome), or (b) wire it from a `/api/orgs/:org/usage` endpoint when one exists.

### [P0-E] Bell and avatar buttons are dead clicks
**Source:** `ui/components/TitleBar.tsx:81-82`, `Shell.tsx:99-105` (no `onBell` / `onAvatar` props passed).
**Problem:** Both `.cfp-titlebar__bell` and `.cfp-titlebar__avatar` render as buttons but the Shell never wires their handlers, so they're inert click targets that look interactive. The avatar in particular is the most obvious "click here to sign out / view profile" spot in the entire app and it does nothing.
**Edit:**
1. In `Shell.tsx`, pass `onAvatar={() => /* open user menu */}` that drops a small popover with rows: "Signed in as <email>", "Account settings", "Switch org…", "Sign out". The `signOut` function (`Shell.tsx:64-76`) is already defined — wire it here.
2. For now, remove the bell button until there's notification machinery (it's just visual noise on a route that has no notifications).
3. Add `aria-label` to both. Currently the avatar is just an initial letter `<button>F</button>` — screen readers say "F button."

### [P0-F] Sidebar items have no focus ring, no keyboard nav, no `aria-current`
**Source:** `ui/components/SideItem.tsx`, `globals.css:3211-3227`.
**Problem:** Sidebar items use `:hover` only. There's no `:focus-visible` rule. Tabbing through the chrome shows no indication of where focus is. The active item is signaled only by `background: var(--rule)`, which is too low-contrast against `var(--paper-2)`. No `aria-current="page"` is set, so screen reader users can't tell which page they're on.
**Edit:**
1. In `globals.css`, add `.cfp-side:focus-visible { outline: 2px solid var(--accent); outline-offset: -2px; }`.
2. In `SideItem.tsx`, when `active`, add `aria-current="page"` to the `<button>` / `<a>`.
3. Bump the active-state background to something higher contrast: `background: var(--surface-2); box-shadow: inset 2px 0 0 var(--accent);` to give it a left-edge accent rail. This is the standard "you are here" treatment.
4. Wrap the sidebar `<aside>` with `<nav aria-label="Workspace">` (or two, one for Workspace one for Org admin).

### [P0-G] Sidebar groups are unlabeled to keyboard / screen-reader users
**Source:** `Shell.tsx:108-138`. Uses `<Eyebrow>` for "Workspace" and "Org admin" — that's a `<span>`, not a region label.
**Edit:** Wrap each group in `<section aria-labelledby="...">` with a real `<h2 id="...">` (visually styled as the eyebrow). Today the structure is a flat list of buttons with no grouping affordance for screen readers.

### [P0-H] Mobile responsive: sidebar becomes a 200px-tall vertical scroll **above** the content
**Source:** `Shell.tsx:80-97` injects a `<style>` block doing this. Below 768px, the layout collapses to titlebar / sidebar / content stacked, with the sidebar capped at `max-height: 200px; overflow-y: auto`.
**Problem:** This is the single ugliest thing in the responsive story. The user lands on a phone and sees a wall of navigation chrome before any content. Common SPA patterns (bottom tab bar, hamburger drawer, or collapsing the sidebar entirely on `<768px`) all beat this.
**Edit:** Replace with a hamburger pattern:
1. Below 768px, hide the sidebar by default (`display: none`).
2. Render a "≡" button in the titlebar (left of the org switcher) that toggles a left-side drawer overlay.
3. The drawer uses the existing `SideItem` markup; close it on route change.
4. Inline `<style>` injection in a component body is also itself a smell — promote these rules into `globals.css` under a `@media (max-width: 768px)` block.

---

## P1 — fix in the second pass

### [P1-A] Auth card is a card-inside-a-card
**Source:** `pages/Auth.tsx:43-74` (outer panel) + Clerk's own bordered card inside it (visible in the screenshot).
**Problem:** Crawfish wraps the Clerk widget in an outer 460×~300 `var(--surface-2)` card; Clerk renders its own white card inside that. Result: two stacked cards with the same background, the "Crawfish" branding row on top, and a sea of empty whitespace around them. Looks unfinished.
**Edit:** Remove the outer card chrome when `CLERK_ENABLED`. Render only:
1. The Crawfish wordmark, centered above the Clerk widget.
2. The Clerk widget itself (its own card chrome is enough).
3. A tiny "Trouble signing in? hello@crawfish.dev" link below. Or merge them by passing Clerk an `appearance.elements.rootBox` that styles the widget to take over the outer card.

### [P1-B] Auth chrome has a 9px horizontal overflow at 375 / 1440
**Source:** Same as P1-A. `findings.json` shows `scrollW - clientW = 9` on every Clerk-rendered route at both breakpoints.
**Likely cause:** The Clerk widget min-width or a flex item with a fixed width that exceeds the container at 375px. Confirm in DevTools and either (a) shrink the Clerk widget's min-width via appearance, or (b) give `.cf` outer wrapper `overflow-x: hidden`.

### [P1-C] Onboarding propose/install/hired/handoff deep-links bounce silently
**Source:** `onboarding/OnboardingFlow.tsx:92-97`. If `answers.name` or `answers.project` is empty (cleared session, private window, fresh device), `useEffect` calls `navigate("/onboarding/welcome", { replace: true })` and sets `showResumeNotice = true`. But I see the redirect in every screenshot of `/onboarding/propose..handoff` and no resume notice rendered above the welcome form — it's defined in state but I never see it in the markup of `OnboardingFlow` (it should be rendered near the top of the welcome stage). Either the notice is below the fold of the screenshot, or it's never rendered. Worth verifying.
**Edit:** Verify the notice is rendered when `showResumeNotice` is true on the welcome stage. If not, add an info banner above the H1: "Looks like your previous session expired — let's start over."

### [P1-D] `/invites/:code` error state surfaces the raw browser exception "Failed to fetch"
**Source:** `pages/InviteAccept.tsx:58` — uses `err.message` directly from `api.ts` thrown errors.
**Edit:** In the body component, when `state.kind === "error"`, map known string patterns ("Failed to fetch", "NetworkError") to a friendly "We couldn't reach our servers. Check your connection or try again in a moment." Keep the raw text in a `<details>` block for support.

### [P1-E] `OrgPicker`'s loading state is the literal string `"loading…"` in a dashed-border box
**Source:** `pages/OrgPicker.tsx:73-86`.
**Problem:** A skeleton card with shimmer (or even just a pulsing rectangle) would be a 90th-percentile loading state. A monospace "loading…" string in a dashed border is brand-style but feels deliberately retro in a context (first signed-in screen) where premium polish matters.
**Edit:** Add three skeleton cards using the same `gridTemplateColumns` and a `background: linear-gradient(...) 0% 0% / 200% 100%` shimmer animation. Cap at 3 cards visible.

### [P1-F] `OrgMembers` and `Projects` cards use raw inline styles; no hover affordance on the row buttons
**Source:** `pages/OrgMembers.tsx:155-178`, `pages/Projects.tsx:188-244`, `pages/ImportModal.tsx:426-484`.
**Problem:** The ImportModal repo rows in particular are full-width buttons with `cursor: pointer` but no `:hover` background change. Without a hover affordance, the row reads as a static list item with a hand cursor for some reason.
**Edit:** Extract the repeated "row in a card list" pattern into a `<ListRow>` component in `ui/components/`. Give it `:hover { background: var(--surface-2); }` and `:focus-visible { outline: 2px solid var(--accent); outline-offset: -2px; }`. Use it in OrgMembers, ImportModal, and the pending-invites list. This also moves a lot of inline styles out of the page files.

### [P1-G] No `dark` mode at all
**Source:** Every page renders against `var(--paper)`. No `prefers-color-scheme: dark` rules anywhere in `ui/tokens/globals.css` (verified via `grep -n prefers-color-scheme`). The CSS variables are defined once, light-only.
**Edit:** This is a phase, not a one-liner — out of scope here. File a separate ticket: add a `@media (prefers-color-scheme: dark)` block in `globals.css` that re-defines `--paper`, `--paper-2`, `--surface`, `--surface-2`, `--ink`, `--ink-soft`, `--ink-mute`, `--ink-faint`, `--rule`, `--rule-3`. Keep `--accent` (the vermillion) approximately constant.

### [P1-H] The "viewing as <email>" pill in the canvas header is shoulder-clutter
**Source:** `pages/OrgRoute.tsx:237`.
**Problem:** Showing the user's own email in a pill on every page is informational over-share. The user already knows who they are. The avatar in the titlebar is the right place for identity.
**Edit:** Remove the pill, keep the avatar (or the AvatarStack for multi-member orgs).

### [P1-I] "READ-ONLY" banner uses tiny mono caps; the "Install Dash →" link is the same size and right-justified, but you don't know it's a link until you hover
**Source:** `pages/OrgRoute.tsx:160-191`.
**Edit:** Give the link a visible underline or arrow chip. Tone: this banner is the only place the user learns there's a desktop product that does more — it should *sell*, not whisper.

### [P1-J] Form buttons toggle between two completely different CSS class strings instead of using a disabled state
**Source:** `pages/OrgMembers.tsx:228-247`.
**Edit:** Use a single `cfp-btn cfp-btn--primary` and `:disabled` styles in `globals.css`. Today the code does `submitting || !emailDraft.trim() ? "" : "cfp-btn--primary"`, which is a brittle pattern and produces a button that visually morphs as the user types.

### [P1-K] `OrgMembers` revoke uses native `window.confirm()` and errors use `window.alert()`
**Source:** `pages/OrgMembers.tsx:86, 92`.
**Edit:** Replace with a small inline confirmation in the row ("Revoke? Yes / Cancel") and an inline toast/banner for the error. Native confirm/alert dialogs are the most obvious "this is unfinished" tell in a web app.

### [P1-L] `ImportModal` close button (`×`) is a 28×28 square with a border — looks like a chip, not a close affordance
**Source:** `pages/ImportModal.tsx:111-131`.
**Edit:** Remove the border, increase to 32×32, use `:hover { background: var(--surface-2); }`. Same fix should apply to the revoke "×" on `OrgMembers.tsx:388-408`.

### [P1-M] No skip link, no `<main>` landmark on auth/invite pages, no document `<title>` updates per route
**Source:** All page files. `document.title` stays "Crawfish Platform" (or whatever `index.html` sets) across every route. Tab stripes look identical, hurting users with many tabs.
**Edit:** Add `useEffect(() => { document.title = "Sign in — Crawfish"; }, [])` per page, or a tiny `useTitle()` helper.

---

## P2 — polish

- **[P2-a]** `pages/Auth.tsx:108` H1 font size jumps to 28 then plunges to 13 body — too steep. Pad with a 16/18px deck line.
- **[P2-b]** `pages/OrgPicker.tsx:35-45` H1 says "Loading…" then "Pick an org" — the headline shouldn't reflect state. Use a static title "Your organizations" and let the cards carry the state.
- **[P2-c]** All "stub · wire later" pages (`OrgRoute.tsx:22-43`) render identical layout. They need at least an illustration or a "what this will be" mockup so they don't feel like 404s. Five identical stubs back-to-back makes the app feel hollow.
- **[P2-d]** Onboarding step counter "Step 1 of 5 · welcome" in the titlebar is good, but the progress bar (top-right) ends at the edge of the screen with no breathing room — give the right rail at least 24px of padding so it doesn't collide with the viewport edge on narrow desktops.
- **[P2-e]** The TitleBar `.cfp-titlebar__brand` is a 28×28 vermillion-on-ink chip showing "cf" — when the user is on the org picker (no org), `Shell.tsx:101` passes `orgGlyph="··"`. Two dots in a chip is a weird state — better to show the Crawfish wordmark when there's no org context.
- **[P2-f]** `pages/Projects.tsx` polls `/api/.../projects` every 5s with no visibility into what's polling. If the user leaves it open it'll hammer the server quietly. Add a `document.visibilityState` check to pause polling when the tab is hidden.
- **[P2-g]** Inline-style sprawl across every page. `OrgRoute.tsx`, `OrgMembers.tsx`, `Projects.tsx`, `ImportModal.tsx`, `OnboardingFlow.tsx`, `Link.tsx`, `InviteAccept.tsx` — every page reinvents the same "h1 with `fontFamily: var(--ff-display); fontWeight: 500; fontSize: 28-36; letterSpacing: -0.022em`". Promote a `<PageHeader title eyebrow subtitle>` to `ui/components/` and use it everywhere. This alone would let the next refactor change every page's typography in one place.
- **[P2-h]** Empty-state copy is fine but cards lack illustration. Even a tiny SVG glyph in the dashed-border boxes (`Projects.tsx:246-272`, `OrgPicker.tsx:149-172`) would lift the feel a tier.

---

## Notes for the implementing agent

1. The CSS variable system (`--ink`, `--paper`, `--accent`, etc.) is solid. Lean on it. **Don't introduce hex colors in component files.**
2. There is no DESIGN.md. Before doing P1-G (dark mode) someone should create one and codify the palette, type ramp, spacing, and motion. Right now the visual language lives in `ui/tokens/globals.css` only.
3. The "single CSS file in `ui/tokens/globals.css`" rule from CLAUDE.md is good for shared concerns but is being violated by inline `<style>` blocks in `Shell.tsx:80-97`. Move those to `globals.css`.
4. The Tauri-vs-browser branching in `TitleBar.tsx:32-34` is fragile (it sniffs window globals). After [P0-A] lands, the branch becomes a one-line `paddingLeft` adjustment; consider whether the desktop shell even needs the platform's TitleBar component or if a separate `BrowserTitleBar` is cleaner. Same component serving two very different shells is the root cause of the "this is desktop chrome on the web" complaint.
5. The dev server I walked is at `:5174`. The backend appears to live at `:8787` (per fetch URLs in `Projects.tsx` / `ImportModal.tsx`, which use the Vite proxy). For full coverage, the implementing agent should boot `cloud/server` too.
6. The `cf_dev_user` localStorage façade in `useAuth.tsx` is dead code in production builds. Either remove it, or add a `VITE_AUTH_MODE=dev` env that explicitly disables Clerk so future audits can walk the authenticated routes headlessly.
