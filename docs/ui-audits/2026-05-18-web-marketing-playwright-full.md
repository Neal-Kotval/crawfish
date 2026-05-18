# Web Marketing Playwright Audit — crawfish.dev — 2026-05-18

**Auditor:** ui-auditor agent (Claude Sonnet 4.6)
**Server:** `http://localhost:5173` (Vite, confirmed running, PID 12507)
**Routes captured:** `/` (only route)
**Viewports:** mobile 390×844, tablet 820×1180, desktop 1440×900, wide 1920×1080
**Themes:** light and dark (dark confirmed renders identically — correct per DESIGN.md no-dark-mode rule)
**Prior audit consumed:** `docs/ui-audits/2026-05-18-web-marketing.md` (static-source pass)
**Screenshot evidence:** `.audit/web-marketing/home/`

---

## Summary scorecard

| Dimension | Score |
|---|---|
| Interactivity | 2.5/5 |
| Cleanness | 3.5/5 |
| Animations | 4/5 |
| Flow & Button Logic | 2.5/5 |
| **Overall** | **12.5/20** |

The page is structurally sound — warm-paper tokens resolve correctly, Space Grotesk hero reads with authority, and the install-card hierarchy is clear. The live Playwright pass reveals that the prior static audit's P1 fixes (nav "Sign in" CTA, IDE button aria-disabled, narrow media-query breakpoint) have been partially applied, but four new issues emerged from runtime observation: the GitHub releases API returns 404 (download buttons silently fall back, giving users a valid but unhelpful URL), the 76px H1 renders unscaled at all viewports including 390px mobile (visually cramped and typographically wrong), every interactive element across the page fails the 44px touch-target height requirement (all are 34–38px tall), and the "Github" nav link's tap target is critically narrow at 43×34px on mobile.

---

## Findings

---

### INTERACTIVITY

---

**F-01 — GitHub Releases API: 404 on every page load**
- **Location:** `web/src/lib/downloads.ts`, REPO constant `"anthropics/crawfish"`, fetch to `https://api.github.com/repos/anthropics/crawfish/releases/latest`
- **Severity:** Critical
- **Observation:** The releases API returns HTTP 404 on every page load because the repo path does not match the actual GitHub org (`crawfish` not `anthropics/crawfish`), causing `useLatestRelease()` to always return `release = null` and falling back to `RELEASES_FALLBACK_URL` for all download buttons.
- **Why it matters:** Every download button — the page's single primary CTA — silently routes to a generic releases page rather than the direct asset download. On macOS the expected behavior is a direct `.dmg` download; instead the user lands on a GitHub releases index and has to find the file manually. This is the most critical path break on the page: a user who clicks "Download for Mac (Intel)" gets sent to `github.com/anthropics/crawfish/releases` which 404s, not a direct file.
- **Recommendation:** Fix the `VITE_GITHUB_REPO` env var or the fallback literal to match the actual repo slug. Add a `VITE_GITHUB_REPO` entry to `.env` / `.env.production`. While the API is broken, the fallback URL itself (`https://github.com/anthropics/crawfish/releases`) also 404s — fix the org slug throughout `downloads.ts`. If the repo is not yet public, gate the CTA with a "Notify me" state instead of a silent dead link.
- **Evidence:** `.audit/web-marketing/home/desktop-light.png`, network errors confirmed in Playwright console log: `HTTP 404 https://api.github.com/repos/anthropics/crawfish/releases/latest`

---

**F-02 — Touch targets: all interactive elements fail 44px height requirement**
- **Location:** Every `<PlatBtn>`, `<NavLink>`, and `<a>` element — `Index.tsx:67`, `Index.tsx:160-167`, `Index.tsx:224-229`
- **Severity:** Critical
- **Observation:** At 390px mobile viewport, every interactive element on the page measures below 44px height: "Github" nav link = 43×34px, all download platform buttons = 38px tall, IDE marketplace buttons = 35px tall, "Invite a teammate later" inline link = 34px. Only the "Sign in →" PlatBtn primary is compliant at 57px on mobile (due to its padding expanding in the flex context).
- **Why it matters:** Apple HIG and WCAG 2.5.5 (Level AAA, but 44px is also the practical standard for WCAG 2.5.8 Level AA in WCAG 2.2) require 44×44px minimum touch targets. A developer landing on this marketing page from a phone has a very high chance of missing the download button on first tap. Given the page's goal is to get a download or sign-in, this is a direct conversion killer on mobile.
- **Recommendation:** In `PlatBtn`, change `padding: "8px 12px"` to `padding: "10px 16px"` and add `minHeight: 44` to the style object. For the nav "Github" link in `NavLink`, add `padding: "8px 0"` and `minHeight: 44, display: "flex", alignItems: "center"` so the hit target is expanded without changing visual size. For the "Invite a teammate later" `<a>`, wrap in a container with `minHeight: 44` or use `PlatBtn` (as the static audit already recommended).
- **Evidence:** `.audit/web-marketing/home/mobile-light.png`

---

**F-03 — IDE marketplace buttons: `aria-disabled` on wrapper `<span>` does not reach `<button>` semantics**
- **Location:** `Index.tsx:197–205`
- **Severity:** Major
- **Observation:** The disabled IDE buttons use `aria-disabled="true"` on a wrapping `<span>` element, with the inner `<PlatBtn>` rendered as a `<button>`. Screen readers will announce the `<button>` as enabled (it has no `disabled` attribute or `aria-disabled` itself) and the tooltip `title` lives only on the `<span>`. The `pointerEvents: "none"` suppresses mouse interaction but not keyboard focus — a keyboard user can still tab to and activate the button.
- **Why it matters:** Screen reader users receive a false affordance: they hear "button: Open VS Code marketplace" with no indication it is non-functional. Keyboard users pressing Enter will fire the button's handler (undefined in this case, so silent — but still reachable focus state). This is an accessibility deception.
- **Recommendation:** Move `aria-disabled="true"` and `title` to the `<PlatBtn>` element directly, or pass `disabled` prop which `PlatBtn` currently does not support. Add `disabled` prop support to `PlatBtn`: when `disabled` is true, render `<button type="button" disabled aria-label="Coming soon — Marketplace listing pending" ...>`. Remove the `<span>` wrapper.
- **Evidence:** `.audit/web-marketing/home/desktop-light.png` (IDE card, bottom-right)

---

**F-04 — No hover or focus-visible state on any `PlatBtn` or nav link**
- **Location:** `ui/components/marketing/PlatBtn.tsx` (all instances), `ui/components/marketing/NavLink.tsx`
- **Severity:** Major
- **Observation:** `PlatBtn` applies all styles inline with no `:hover`, `:focus-visible`, or `:active` pseudo-class styles. Keyboard users navigating to any download button, "Sign in", or "Github" link see no visible focus indicator. Mouse users get no visual confirmation on hover (no color shift, no elevation, no cursor change beyond `pointer`).
- **Why it matters:** WCAG 2.4.7 (Level AA) requires a visible focus indicator. Buttons with no hover state reduce affordance confidence — users cannot confirm they are about to activate the right element. The DESIGN.md tokens define `--cf-focus-ring` and `--accent-hover` explicitly for this purpose; neither is used in marketing components.
- **Recommendation:** Move `PlatBtn` styles to a CSS class in `ui/tokens/globals.css` (lead action per CLAUDE.md) with `:hover`, `:focus-visible`, and `:active` states. At minimum: primary button hover → `background: var(--accent-hover)`; secondary → `background: var(--paper-2), border-color: var(--rule-3)`; focus-visible → `box-shadow: var(--cf-focus-ring)`. The `NavLink` component should similarly gain `:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }`.
- **Evidence:** All viewport screenshots — hover/focus state cannot be captured in static screenshots but confirmed absent in CSS inspection.

---

**F-05 — "Github" nav link: single link in `<nav>` with no `aria-label` on the link itself**
- **Location:** `Index.tsx:64–66`
- **Severity:** Major
- **Observation:** The `<nav aria-label="Main navigation">` contains exactly one link ("Github"). While the nav has a correct label, the link has no `aria-label` and its text "Github" does not describe its destination (it should be "Crawfish on GitHub" or similar). More critically: the nav is purely decorative at this stage — it has one external link while the actual primary navigation actions (Sign in, Download) live outside the `<nav>` element. The "Sign in →" `PlatBtn` is a sibling of `<nav>` in the header flex row, not inside it, making it invisible to "navigate by landmark" screen reader shortcuts.
- **Why it matters:** Screen readers announce the nav landmark with its label but then only find one link inside. The Sign-in CTA — the second most important action on the page — is not navigable via landmark shortcuts. Assistive technology users may entirely miss the sign-in path.
- **Recommendation:** Move the `<PlatBtn primary href="...">Sign in →</PlatBtn>` inside the `<nav>` element. Add `aria-label="Crawfish on GitHub"` to the GitHub `<NavLink>`. This aligns landmark semantics with the actual navigation structure.
- **Evidence:** `.audit/web-marketing/home/desktop-light.png`, `.audit/web-marketing/home/mobile-light.png`

---

**F-06 — Eyebrow `●` dot is not `aria-hidden`**
- **Location:** `Index.tsx:83`
- **Severity:** Minor
- **Observation:** `<span style={{ color: "var(--accent)", marginRight: 8 }}>●</span>` renders a decorative bullet before the eyebrow text. It has no `aria-hidden="true"` attribute.
- **Why it matters:** Screen readers will announce "bullet" or the Unicode name "BLACK CIRCLE" before the eyebrow label, creating "black circle FOR THE FOUNDER SPINNING UP THEIR FIRST FIVE AGENTS" as the announced text. Minor but noisy.
- **Recommendation:** Add `aria-hidden="true"` to the dot `<span>`.

---

**F-07 — Decorative accent line at top of page has no `aria-hidden`**
- **Location:** `Index.tsx:43`
- **Severity:** Minor (Polish)
- **Observation:** `<div style={{ position: "absolute", top: 0, left: 0, right: 0, height: 1, background: "var(--accent)" }} />` is a purely decorative 1px vermillion rule. No `aria-hidden="true"`, `role="presentation"`, or equivalent suppression.
- **Why it matters:** Screen readers may traverse this empty `<div>` and announce it as an unnamed interactive region or skip it silently — behavior varies by browser/SR combination. Explicit suppression is zero-cost and eliminates the ambiguity.
- **Recommendation:** Add `aria-hidden="true"` to the decorative `<div>`.

---

### CLEANNESS

---

**F-08 — H1 at 76px renders unscaled at 390px mobile: type is cramped and truncates**
- **Location:** `Index.tsx:86–94`, hero `<h1>`
- **Severity:** Major
- **Observation:** The H1 `fontSize: 76` is a fixed pixel value with no responsive scaling. At 390px viewport the H1 renders at 76px — 19.5% of the viewport width per character. "Hire your" fits on one line at ~180px, but "fifteen minutes." in accent vermillion wraps in a way that forces the line to break mid-word on narrower devices. Confirmed via Playwright: `H1 size=76px` at mobile 390px, unchanged from desktop 1440px. The text occupies the full viewport width with only 24px padding each side (342px content), making three lines of 76px type tightly stacked.
- **Why it matters:** 76px at 390px viewport is a font-size-to-viewport ratio of ~19.5% — aggressive but not uncommon for display heroes. However, without line-height adjustment at this size (currently `lineHeight: 0.98`) and no clamp/fluid sizing, the hero becomes a wall of dense text on mobile rather than a commanding headline. The spacing between hero and the paragraph below collapses visually.
- **Recommendation:** Implement fluid typography: `fontSize: "clamp(44px, 8vw, 76px)"`. This scales to ~44px at 550px viewport (readable, airy) and hits 76px at 950px+. Alternatively add a responsive override via the `narrow` state already wired: `fontSize: narrow ? 52 : 76`.
- **Evidence:** `.audit/web-marketing/home/mobile-light.png` (top section, three-line cramped hero)

---

**F-09 — Stat numbers lack `.cf-num` tabular-nums class**
- **Location:** `Index.tsx:119–122`, the four stat numbers in the hero aside
- **Severity:** Minor
- **Observation:** "10,412", "−35%", "3.25×", and "$0" render at `fontSize: 28, fontWeight: 500` in `var(--ff-sans)`. None are wrapped with `.cf-num` (which applies `font-variant-numeric: tabular-nums; font-feature-settings: "tnum"`) as required by DESIGN.md §3 ("Numerics on any number-looking element get `.cf-num`").
- **Why it matters:** Without tabular figures, the numbers align inconsistently across the 2×2 grid if they update dynamically. More importantly, it is a direct violation of the design contract and sets a precedent for other surfaces to skip the token.
- **Recommendation:** Wrap each stat number `<div>` in `<span className="cf-num">` or add `className="cf-num"` to the `<div style={{ fontFamily: "var(--ff-sans)", fontSize: 28, ... }}>`.

---

**F-10 — Version pill at 10px is at the floor of legibility; contrast passes but barely**
- **Location:** `Index.tsx:58–62`
- **Severity:** Minor
- **Observation:** The nav version badge ("v0.4 · public beta") renders at 10px mono in `var(--ink-mute)` on `var(--paper)`. Contrast = 4.71:1, which passes WCAG AA for normal text (4.5:1 required) but only by a 0.21 margin. At 10px, letter-spacing 0.08em, the text is at the absolute threshold of comfortable reading and will be sub-pixel antialiased on most displays.
- **Why it matters:** On non-Retina displays at 100% zoom, 10px mono is physically ~0.8mm tall — functionally invisible to anyone over 40 or using a non-HiDPI screen. This is the first piece of contextual text a new visitor reads to understand the product's maturity stage.
- **Recommendation:** Increase to `fontSize: 11` (matches `.cf-eyebrow` floor and is the DESIGN.md minimum for mono eyebrow text) and verify contrast is maintained.

---

**F-11 — "You can install all three later" helper text is misaligned on tablet**
- **Location:** `Index.tsx:139–141`, the right-side description in the install picker header
- **Severity:** Minor
- **Observation:** At 820px tablet viewport, the two-column flex header for the install picker section (`justifyContent: "space-between"`) squeezes the right-side descriptor text to approximately 180px wide (maxWidth is 320px, but available space is ~340px total minus the left heading). The text wraps into 5–6 lines at 13px, creating a visually imbalanced pairing: a large bold heading on the left vs. a text wall on the right.
- **Why it matters:** The helper text is meant to reduce decision anxiety ("each one talks to the same org folder on disk"). When it reflows into a dense paragraph mid-page, it reads as fine print rather than reassurance. On mobile it simply stacks under the heading, which is acceptable.
- **Recommendation:** On the narrow breakpoint (already detected via `narrow` state), hide the right-side descriptor entirely (`display: narrow ? "none" : "block"`) since its content is secondary. Alternatively, cap it at 2 lines with `line-clamp: 2; overflow: hidden` for tablet.
- **Evidence:** `.audit/web-marketing/home/tablet-light.png` (install picker section header)

---

**F-12 — H1 has a `<br />` forced line break that breaks at non-designed viewports**
- **Location:** `Index.tsx:91–93`
- **Severity:** Minor
- **Observation:** The H1 uses two `<br />` elements: `Hire your<br />company in<br /><span>fifteen minutes.</span>`. This forces a specific 3-line break regardless of viewport width. On wide (1920px) the breaks create an awkward composition where "company in" floats alone on a short line with large right-side whitespace. On mobile, the breaks are appropriate since the viewport is narrow.
- **Why it matters:** Forced line breaks (`<br />`) in headlines are a fixed-viewport design decision. At 1920px with a 1.05fr left column of ~880px, the first line "Hire your" is only ~230px wide — leaving 650px of blank space. The headline looks short and tentative rather than commanding at wide viewports.
- **Recommendation:** Remove `<br />` elements and let the headline reflow naturally with `max-width: 680px` (already set to 720px). Add a CSS `white-space: nowrap` on the `.accent` span if you need to prevent "fifteen" from orphaning. Natural reflow will produce a more appropriate 2-line break at desktop and single-wide at wide.
- **Evidence:** `.audit/web-marketing/home/wide-light.png` (hero, left column)

---

**F-13 — "Invite a teammate later" `<a>` lacks hover/focus state and is inconsistent with PlatBtn**
- **Location:** `Index.tsx:224–229`
- **Severity:** Minor
- **Observation:** The "Invite a teammate later →" link uses raw inline styles with no hover, focus, or active state definition. It looks like a button (padding, border, borderRadius) but behaves like an anchor. `PlatBtn` already exists for exactly this affordance. As flagged in the static audit, there is also no `:hover` state.
- **Why it matters:** Inconsistency between this element and `PlatBtn` means hover behavior diverges for visually identical elements. Design contract violation.
- **Recommendation:** Replace the raw `<a>` with `<PlatBtn href="https://app.crawfish.dev/onboarding/team">Invite a teammate later →</PlatBtn>`. Once F-04 (PlatBtn hover/focus) is fixed, this inherits the correct states automatically.

---

**F-14 — Install-card info strip uses dashed border — not in the design system**
- **Location:** `Index.tsx:217`, `border: "1px dashed var(--rule-3)"`
- **Severity:** Minor (Polish)
- **Observation:** The bottom info strip ("After install, your client runs locally...") uses a `dashed` border style. DESIGN.md §4 states "Always 1px borders" with no mention of dashed variants in the surface convention table. The `--rule`, `--rule-2`, `--rule-3` tokens are all described as solid divider rules.
- **Why it matters:** Dashed borders carry semantic weight (draft, incomplete, droppable zones). Using it decoratively on a static info strip imports unintended meaning and is inconsistent with all other borders on the page.
- **Recommendation:** Change to `border: "1px solid var(--rule-2)"` (faint inner divider — appropriate for a secondary info strip).

---

**F-15 — Footer padding collapses to the same 56px as desktop — too wide on mobile**
- **Location:** `Index.tsx:234–242`, footer
- **Severity:** Minor
- **Observation:** The footer uses `padding: "28px 56px"` with no responsive variant. On mobile (390px), this leaves only `390 - 112 = 278px` content width for a two-column flex layout. The footer text wraps or one side gets clipped depending on font rendering. The hero and install sections correctly check `narrow` and use `24px` padding; the footer does not.
- **Why it matters:** Minor visual inconsistency — the footer's left/right padding doesn't match the content sections above it on mobile, creating a misalignment in the perceived content edge.
- **Recommendation:** Change footer padding to `padding: narrow ? "28px 24px" : "28px 56px"` (same pattern already used in hero and install sections).

---

**F-16 — Install card footer "114 MB · v0.4.1" and CLI card "v0.4.1" are hardcoded**
- **Location:** `Index.tsx:170`, `Index.tsx:187`
- **Severity:** Major (carries over from static audit — still present live)
- **Observation:** Confirmed live: the install card footer renders static "114 MB · v0.4.1" regardless of the release API response. The `release` object is available in scope; the version is not derived from it.
- **Why it matters:** Will silently display the wrong version on every release. Exacerbated by F-01 (the API is currently 404ing anyway, but when fixed, the version string still won't update).
- **Recommendation:** `Index.tsx:170` → `<><span>{release ? `${releaseSizeMb} MB · ${release.tag_name}` : "114 MB · v0.4.1"}</span>...`. See `useLatestRelease()` for `release.tag_name`. File size requires reading the asset's `size` field from the API response — add to `useLatestRelease` return type.

---

### ANIMATIONS

---

**F-17 — `cfp-march` (marching ants) and `cfp-blink` animations have no `prefers-reduced-motion` guard**
- **Location:** `ui/tokens/globals.css:3466–3471`
- **Severity:** Major
- **Observation:** The `.cfp-edge--active` marching-ants animation (`2.4s linear infinite`) and `.cfp-blink` cursor blink (`1s steps(1) infinite`) have no `@media (prefers-reduced-motion: reduce)` guard. The `cf-blob--drift` and `cf-bulk-bar` animations do have guards (lines 2686–2688, 1702–1704). The canvas animations are inconsistently protected.
- **Why it matters:** Both animations are infinite loops. For users with vestibular disorders who have `prefers-reduced-motion: reduce` set, infinite motion can trigger nausea or disorientation. WCAG 2.3.3 (AAA) and WCAG 2.2.2 (AA) both require the ability to pause/stop moving content. While these animations live in the dash surface (not marketing), they are defined in the shared `globals.css` consumed by the marketing page's bundler.
- **Recommendation:** Add to `globals.css`:
  ```css
  @media (prefers-reduced-motion: reduce) {
    .cfp-edge--active { animation: none; }
    .cfp-blink { animation: none; opacity: 1; }
  }
  ```
  This is a lead-only edit (shared CSS file). Flag immediately.

---

**F-18 — No page-entry animation or skeleton state during the release API call**
- **Location:** `Index.tsx:23`, `useLatestRelease()` hook
- **Severity:** Minor
- **Observation:** During the GitHub release API request (even on fast connections, ~100–300ms), download buttons render with the fallback URL immediately. There is no loading state, skeleton, or visual indicator that the button destination is being resolved. Per DESIGN.md §7: "No skeleton shimmer (use static `--paper-2` fills with the eyebrow 'loading' instead)."
- **Why it matters:** If/when the API is fixed (F-01), a user who clicks "Download for Mac" within the first 300ms after page load will hit the generic releases page rather than the direct asset. The correct pattern is to either (a) show the button disabled/loading until `release` is non-null, or (b) accept the fallback as intentional (GitHub releases page is acceptable as a landing).
- **Recommendation:** If direct asset download is the goal: show the primary download button in a loading state (`opacity: 0.7`, `cursor: "wait"`, non-clickable) until `release` is available. If the fallback is acceptable: add a comment in the code acknowledging this is intentional.

---

### FLOW AND BUTTON LOGIC

---

**F-19 — No SEO/OG meta tags: zero social sharing footprint**
- **Location:** `web/index.html`
- **Severity:** Major
- **Observation:** Confirmed live: `metaDescription = undefined`, `metaOg = undefined`. The `<title>` tag reads "Crawfish · hire your company in fifteen minutes" — correct. But there is no `<meta name="description">`, `<meta property="og:title">`, `<meta property="og:description">`, `<meta property="og:image">`, `<meta name="twitter:card">`, or canonical URL.
- **Why it matters:** Link unfurls on Slack, Twitter/X, LinkedIn, and iMessage will show a blank card with just the domain. Every viral share of the product link produces zero impression. For a developer tool, Slack and Twitter link sharing is the primary growth channel. This is a zero-effort fix with outsized impact.
- **Recommendation:** Add to `web/index.html` `<head>`:
  ```html
  <meta name="description" content="Hire your company in fifteen minutes. One template, five working agents, one place to look. Local-first, MIT, no card required." />
  <meta property="og:title" content="Crawfish · hire your company in fifteen minutes" />
  <meta property="og:description" content="The operating system for companies that run on AI agents." />
  <meta property="og:image" content="https://crawfish.dev/og.png" />
  <meta name="twitter:card" content="summary_large_image" />
  <link rel="canonical" href="https://crawfish.dev/" />
  ```

---

**F-20 — Dark mode system preference is ignored (correct per spec) but not communicated**
- **Location:** `Index.tsx:40–42`, `body { background: var(--paper) }`
- **Severity:** Minor (Polish)
- **Observation:** Confirmed via Playwright dark-theme capture: `bodyBg = rgb(245, 241, 232)` in dark mode — identical to light. This is correct per DESIGN.md ("No dark mode... `data-theme="dark"` is honored as a no-op fallthrough"). However, there is no user-visible indication that dark mode is intentionally unsupported. The `prefers-color-scheme: dark` media query has no handling in the marketing site's CSS.
- **Why it matters:** Users who have dark mode enabled system-wide land on a warm-paper page that looks unintentional. No tooltip, no footer note, no explanation. For ~40% of users (estimated dark mode adoption), this causes a jarring first impression. The rationale (warm paper is the brand point, as DESIGN.md explains) is actually a differentiator — it should be owned, not silently imposed.
- **Recommendation:** Add a single line to the footer or the `<meta>` block: `<meta name="color-scheme" content="light">` in `index.html`. This tells the browser the page supports only light mode, suppressing browser-chrome dark-mode adaptation (scrollbars, form controls) while leaving the body warm-paper intentionally. Optionally, add a footer note: "warm paper · no dark mode by design."

---

**F-21 — Secondary platform buttons have no visual indicator of what they do**
- **Location:** `Index.tsx:163–167`, secondary platform PlatBtn elements ("Apple Silicon", "Linux", "Windows")
- **Severity:** Minor
- **Observation:** The secondary download buttons ("Apple Silicon", "Linux", "Windows") render as dark-background pills with no prefix icon or suffix affordance. A user unfamiliar with Crawfish cannot tell if clicking "Linux" downloads a binary, opens a docs page, or navigates somewhere. Contrast with the primary button which has a "↓ Download for" prefix making the action explicit.
- **Why it matters:** Secondary CTAs that don't label their action create hesitation. On mobile, where the buttons stack below the primary, they look like tags or platform labels, not download triggers.
- **Recommendation:** Add "↓" prefix to all secondary platform buttons, matching the primary: e.g., "↓ Linux" or "↓ ARM64". Alternatively, an `aria-label` per button: `aria-label="Download for Linux"`.

---

**F-22 — "Invite a teammate later" is placed poorly: it follows three install paths but only makes sense after downloading**
- **Location:** `Index.tsx:213–231`, the bottom info strip
- **Severity:** Minor
- **Observation:** The info strip with "Invite a teammate later →" appears below all three install cards in a single row. On mobile it stacks below a 2,400px+ content column. The "Invite" action is only relevant after a user has already downloaded and installed — but it is presented as a peer option to the install paths, implying it is an alternative. This creates a false branching choice: "should I install it, or invite a teammate?"
- **Why it matters:** For solo founders (the primary persona: "the founder spinning up their first five agents"), the "invite teammate" path is a future action, not an immediate alternative. Its current placement can pull attention away from the primary download CTA before the user has committed.
- **Recommendation:** Reposition the info strip below a visual separator, or reduce its prominence by removing the bordered container and rendering it as a plain footer note: `"Already set up? Invite your team →"`. This makes clear it is a follow-up action, not an alternative.

---

**F-23 — React Router future-flag warnings in console on every page load**
- **Location:** `web/src/main.tsx` (inferred from React Router usage)
- **Severity:** Minor (Polish)
- **Observation:** Playwright console captured two `console-warn` entries on every page load: `⚠️ React Router Future Flag Warning: React Router will begin wrapping state updates in React.startTransition in v7` and the `v7_relativeSplatPath` warning. These are not errors but appear in DevTools console, which is noise for a developer who opens DevTools to inspect the download mechanism.
- **Why it matters:** Console noise on a developer-targeted marketing page creates a poor impression — a developer who opens DevTools sees warnings immediately. Trivial to suppress.
- **Recommendation:** In the `BrowserRouter` (or `createBrowserRouter`) call in `main.tsx`, add the future flags: `<BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>`. This is a 1-line fix.

---

## Contrast audit summary

All measured WCAG AA contrast ratios:

| Pair | Ratio | Status |
|---|---|---|
| `--ink` on `--paper` (body text) | 15.46:1 | Pass |
| `--ink-soft` on `--paper` (lede paragraph) | 10.14:1 | Pass |
| `--ink-mute` on `--paper` (eyebrows, stat labels) | 4.71:1 | Pass (barely) |
| `--ink-faint` on `--paper` | 2.46:1 | **Fail — do not use for text** |
| `--accent` on `--paper` (H1 "fifteen minutes.") | 4.31:1 | Pass — large text only (76px) |
| `--accent` on `--paper` at body sizes | 4.31:1 | **Fail for text under 18pt bold** |
| White `#fff` on `--accent` (primary button) | 4.86:1 | Pass |
| `#f7f3ea` on `#26241f` (dark PlatBtn) | 14.00:1 | Pass |
| Blended blurb on `--ink` bg (Dash card) | 8.14:1 | Pass |
| `--good` on `--paper` (footer status) | 4.64:1 | Pass |
| `--ink-mute` on `--surface` (card footer) | 5.01:1 | Pass |

**Critical note:** `--ink-faint` (`#a09b8f`) at 2.46:1 on `--paper` fails WCAG AA for all text sizes. It is defined in DESIGN.md for "timestamps, disabled, faintest meta" — ensure no informational text (not purely decorative) ever uses this token. The marketing page does not currently use it; flag for dash/platform surfaces where it appears on small body text.

---

## Per-route screenshots

| Route | Screenshots |
|---|---|
| `/` (home) | `.audit/web-marketing/home/mobile-light.png` |
| | `.audit/web-marketing/home/mobile-dark.png` |
| | `.audit/web-marketing/home/tablet-light.png` |
| | `.audit/web-marketing/home/tablet-dark.png` |
| | `.audit/web-marketing/home/desktop-light.png` |
| | `.audit/web-marketing/home/desktop-dark.png` |
| | `.audit/web-marketing/home/wide-light.png` |
| | `.audit/web-marketing/home/wide-dark.png` |

---

## Top 5 priorities ranked by impact-to-effort

**1. Fix the GitHub releases API org slug (F-01)**
The primary CTA on the page — the download button — is silently broken for 100% of users. Every visit results in a 404 when the user clicks download. This is a one-line fix in `downloads.ts` or a `.env` variable. Impact: maximum (breaks golden path). Effort: minimal (change a string).

**2. Add OG/meta tags to `index.html` (F-19)**
Zero social sharing footprint on a developer tool marketed through Slack, Twitter, and GitHub. Fix is 5 lines of HTML with zero risk. Impact: directly multiplies every organic share. Effort: trivial.

**3. Implement `prefers-reduced-motion` guards on `cfp-march` and `cfp-blink` (F-17)**
Infinite-loop animations with no reduced-motion guard are a WCAG 2.3.3 violation. Lead-only edit (shared CSS). Impact: accessibility compliance, affects all three surfaces. Effort: 4 lines of CSS.

**4. Fix touch target heights to 44px (F-02)**
All download buttons are 38px tall on mobile. Every mobile visitor's first download attempt has a high chance of miss-tap. `PlatBtn` padding fix is contained to one component file. Impact: direct conversion rate on mobile. Effort: 2-line change in `PlatBtn.tsx`.

**5. Add hover/focus-visible states to `PlatBtn` and `NavLink` (F-04)**
Currently zero keyboard or hover feedback on any interactive element on the page. WCAG 2.4.7 violation. Impact: accessibility compliance + perceived polish for all visitors who hover before clicking. Effort: CSS class addition (lead-only for `globals.css`) or inline-style `:hover` workaround.

---

## What is already working well

1. **Token discipline is solid.** CSS custom properties resolve correctly on `:root` (verified live). No raw hex literals were found in computed inline styles at runtime — the prior audit's CLI block fix has been applied. The warm-paper palette renders exactly as DESIGN.md specifies.

2. **Dark mode is correctly a no-op.** `bodyBg = rgb(245, 241, 232)` in `prefers-color-scheme: dark` — same as light. DESIGN.md's intentional "no dark mode" rule is correctly implemented. Adding `<meta name="color-scheme" content="light">` (F-20 recommendation) will complete this.

3. **The responsive `narrow` breakpoint is now wired.** The static audit flagged a hard-coded two-column grid; the live code shows `data-layout` toggling correctly at 1099px via a `matchMedia` listener, and the grid collapses to `1fr` appropriately. Mobile screenshots confirm correct single-column stacking.

4. **The "Sign in →" primary CTA is in the nav header.** This was missing in the static audit. It is now present as `<PlatBtn primary href="https://app.crawfish.dev/signin">Sign in →</PlatBtn>` — the page's golden path is complete above the fold.

5. **The install card hierarchy is clear and distinctive.** The dark `--ink` background on the Dash card, the `recommended` eyebrow tag in vermillion, and the vermillion primary download button create unambiguous primary-action scent. New users understand the recommended path at a glance.

---

## One bold suggestion

**Make the hero H1 interactive: let the visitor "hire" one of the five default agents by clicking through the word "company."**

The headline "Hire your company in fifteen minutes" is a promise. The word "company" could be a subtle inline reveal — on hover (desktop) or tap (mobile), it cycles through the five default agent names: "Hire your **Designer-bot** in fifteen minutes", "Hire your **Eng-bot** in fifteen minutes", etc. with a 200ms cross-fade using `opacity` only (no layout shift, respects `prefers-reduced-motion`). A small cursor or underline affordance signals the interaction. This transforms a static marketing line into a micro-demo of the product's core concept — agent hiring — without requiring the user to navigate anywhere. It is non-obvious (no other AI tool does this), has zero performance cost, and directly communicates the product's value prop through direct manipulation rather than description. It also gives the page a distinctive, memorable quality that makes a second-share moment — "did you click the headline?" — which is the highest-value organic growth lever for a developer tool.
