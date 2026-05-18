# Web Marketing UI Audit — 2026-05-18

**Scope:** `web/src/pages/Index.tsx` (sole route — the front door), `web/src/lib/downloads.ts` (release-fetch helpers), `web/index.html`, `web/src/main.tsx`. Companion components in `ui/components/marketing/` are noted but owned by `ui-tokens` lead.

## Scorecard

| Dimension | Score |
|---|---|
| Info architecture | 4/5 |
| Visual hierarchy | 4/5 |
| Empty / loading / error states | 2/5 |
| Visual polish | 3/5 |
| Real-vs-mock data | 2/5 |
| Responsive | 1/5 |
| Accessibility | 2/5 |
| **Overall** | **18/35** |

The page's bones are sound — warm paper, vermillion accent, correct typefaces, a single focused CTA. But it has no responsive layout whatsoever (hard CSS grid with `px` gaps at a fixed 1440-wide design width collapses on any viewport narrower than ~1100px), two IDE install buttons with no `href` or `onClick` (dead CTAs in a block that is the page's #3 card), hardcoded stat numbers presented as social proof, and an inline CLI code block with raw hex literals instead of tokens. These three issues together — dead buttons, unresponsive grid, fake stats — block a first-time user's golden path step 1.

---

## Blockers (must-fix)

- **[P1] `Index.tsx:171-172` — IDE install buttons have no `href` and no `onClick`.** Both `<PlatBtn>Open VS Code marketplace ↗</PlatBtn>` and `<PlatBtn>Open Cursor marketplace ↗</PlatBtn>` render as `<button>` elements (because `PlatBtn` renders `<a>` only when `href` is supplied). Clicking them does nothing. Two primary-looking CTAs on the install card that do nothing destroy trust. Fix: add `href` to the VS Code and Cursor Marketplace URLs, or if not yet available, disable the buttons and add a `title` tooltip explaining the status.

- **[P1] `Index.tsx:59-108` — The hero section is a two-column CSS `grid` with no media query; below ~1100px the right stats aside overflows or collapses into zero width.** The install card section (`Index.tsx:126`) is a `1.05fr 1fr 1fr` three-column grid with the same problem. On a 1280-wide laptop screen the hero already clips; on a typical 1024-wide monitor or split-screen the page is broken. The DESIGN.md spec says "fluid down to 1280" — today it is not. Fix: wrap both grid sections in CSS that collapses to `1fr` below 1280px. Because CSS classes must live in `ui/tokens/globals.css` (lead-only), the interim fix is to add a React-owned `<style>` block or `useEffect`/`matchMedia`-driven class toggle in `Index.tsx` until the lead lands classes. (See Recommendations — flag to lead for `globals.css` addition.)

- **[P1] `Index.tsx:151-160` — CLI code block uses five raw hex literals instead of design tokens.** Specifically: background `"#1a1a18"`, text `"#e9e4d0"`, prompt `"#6fb98f"` (×2), comment `"#7a766c"`. This is a brand-contract violation (`DESIGN.md §8`: "Always reference the var, never the hex"). The `--ink` surface token exists (`#1a1a18`); the green prompt color has no token. Fix: replace `background: "#1a1a18"` → `"var(--ink)"`, `color: "#e9e4d0"` → `"var(--surface)"` (closest warm cream), comment color → `"var(--ink-mute)"`. The green prompt `"#6fb98f"` has no canonical token; flag to lead to add `--good-cli` or similar to `ui/tokens/globals.css`; interim: use `var(--good)` (`#2f7a4d`) which is already defined and close in intent (success / "running" green).

---

## Majors (should-fix before next release)

- **[P2] `Index.tsx:94-107` — Hero stats grid contains four hardcoded numbers presented as real social proof.** `"10,412"` weekly active orgs, `"−35%"` compounding factor, `"3.25×"` token reduction, `"$0"` price are all static strings. While the $0 price is a real claim, the other three look like live metrics but are literals. New users who look these up or return to compare will see them unchanged. Fix: either (a) mark them explicitly as "at launch" / "based on beta data" with an eyebrow label, or (b) remove the stats aside entirely until there is a real data feed. The stat numbers also lack `.cf-num` (tabular-nums) on the large numerals per `DESIGN.md §3`.

- **[P2] `Index.tsx:145` — Install card footer `"114 MB · v0.4.1"` is a hardcoded string.** The `useLatestRelease()` hook fetches the real release tag (`release.tag_name`), but the version shown in the card footer is a static literal. It will silently drift out of sync. Fix: read the version from `release?.tag_name ?? "v0.4.1"` (fallback to literal while loading), and read the file size from the asset metadata when available.

- **[P2] `Index.tsx:162` — CLI card footer `"v0.4.1"` is also hardcoded.** Same issue — should derive from `release?.tag_name`. The download hook is already in scope; the CLI card just doesn't consume it.

- **[P2] `Index.tsx:34-56` — `<header>` has no `<nav aria-label>` landmark.** The `<nav>` element is present but the single `<NavLink>` inside renders an `<a>` without `aria-current="page"` or any accessible distinction. Screen readers get a nav with one unlabeled link. Fix: add `aria-label="Main navigation"` to `<nav>`, and `aria-current="page"` (or `aria-label`) to the GitHub link.

- **[P2] `Index.tsx:191-196` — "Invite a teammate later →" is an `<a>` with fully inline styles — background, border, color, font, padding, radius — none of which reference tokens.** The `--ink` border and color are correct, but they are not referenced via `var(--ink)`; they are written as the `"var(--ink)"` string in an inline style, which is fine. However, there is no `:hover`, `:focus-visible` state defined, so keyboard and hover users get no feedback on this CTA. Fix: wrap in the `PlatBtn` component (which already has correct styling), or add a `className` from `globals.css` that provides hover/focus states.

- **[P2] `Index.tsx:28-30` — Root `<div>` has `overflow: hidden` on `position: relative` without a defined width.** On viewport widths narrower than the grid's natural min-content, this hides overflow rather than reflows. Fix is same as the P1 responsive fix — remove `overflow: hidden` once grid reflows correctly.

---

## Polish (nice-to-have)

- **[P3] `Index.tsx:64-66` — Eyebrow dot `"●"` is hardcoded as text with `color: "var(--accent)"`.** The `cf-eyebrow` class sets `color: var(--ink-mute)` globally. The inline override for the `●` symbol is fine, but the character is semantically decoration (`aria-hidden`). Add `aria-hidden="true"` to the dot `<span>`.

- **[P3] `Index.tsx:44-49` — Version pill in the wordmark uses inline `fontFamily`, `fontSize`, `letterSpacing`, `color`, `padding`, `border`, `borderRadius`.** This is the exact shape of a `<Pill>` or `<Eyebrow>` from `@crawfish/ui`. It is not breaking but violates DESIGN.md rule "Build new screens out of these — don't reach for inline styles." Convert to `<Pill variant="outline">v0.4 · public beta</Pill>` when the `Pill` component supports `variant="outline"`.

- **[P3] `Index.tsx:202-209` — Footer "● all systems" status is a static string.** It will always say "all systems" regardless of real status. Fix: either link it to `https://status.crawfish.dev` (if that exists) or add a `<a>` that opens a status page. Minor, but trust-related.

- **[P3] `Index.tsx:121` — "How would you like to work?" section heading is inline `<h2>` without an `id`.** The install picker section has no anchor target and no `aria-labelledby` linking the visible heading to the section. Adding `id="install-picker"` to the `<h2>` and `aria-labelledby="install-picker"` to the `<section>` costs one line.

- **[P3] `index.html` — No `<meta name="description">`, `<meta property="og:title">`, `<meta property="og:image">`, or canonical URL.** The `<title>` is correct and descriptive, but there are no social sharing or SEO tags. Crawfish is a marketing page; these matter for link previews.

---

## Mock-data inventory

Every hardcoded value visible to the user:

- `Index.tsx:95` — `"10,412"` weekly active orgs (static)
- `Index.tsx:96` — `"−35%"` median compounding factor, day 30 (static)
- `Index.tsx:97` — `"3.25×"` token reduction (static)
- `Index.tsx:98` — `"$0"` price through stage 1 (legitimate but static)
- `Index.tsx:145` — `"114 MB · v0.4.1"` Dash binary size and version (static, drifts)
- `Index.tsx:162` — `"v0.4.1"` CLI version (static, drifts)
- `Index.tsx:176` — `"v0.3 · 24k installs"` IDE plugin version and install count (static)
- `Index.tsx:157-159` — CLI prompt strings `"brew install crawfish"` / `"crawfish login"` / `"curl -fsSL crawfish.dev/i | sh"` (static by nature — install commands — fine to leave, but the styling uses hex literals)

---

## Consistency gaps (web ↔ platform / dash)

- **"Sign in" CTA is absent.** The nav has only "Github". The golden flow (step 1) says the visitor should be able to click "Download" or "Sign in". There is a "Invite a teammate later" link at the bottom of the install picker, but no primary "Sign in" or "Open Dash" CTA in the nav chrome. Platform has a Clerk sign-in at `cloud/platform/`; the marketing site should link to it prominently. Recommend adding a `<PlatBtn href="https://app.crawfish.dev/signin">Sign in →</PlatBtn>` to the nav alongside (or in place of) the empty right-side spacer `<div style={{ width: 1 }} />` at line 55.

- **Nav has a symmetry bug.** `Index.tsx:55` has `<div style={{ width: 1 }} />` as a fake right column to center the logo via `justifyContent: "space-between"`. This is a layout hack. If a "Sign in" link is added to the right it becomes unnecessary — but until then it should at least be `aria-hidden="true"` to avoid confusing screen readers.

- **Stat number typography.** The hero aside renders large numbers at `fontSize: 28, fontWeight: 500` (correct per DESIGN.md Display scale), but the numbers are not wrapped in `.cf-num` for `font-variant-numeric: tabular-nums`. Platform and Dash both use `.cf-num` on numerics; marketing should match.

- **"Sign in" CTA color.** The "Invite a teammate later" button uses `border: "1px solid var(--ink)"` — an ink-bordered secondary button. If a "Sign in" CTA is added to the nav, it should use `<PlatBtn primary>` (vermillion) for visual hierarchy parity with how Platform renders its primary auth CTA.

---

## Recommendations

The single most leveraged changes, in order:

1. **Add `href` to the IDE marketplace buttons (VS Code + Cursor)** and wire them or disable + tooltip them. A dead CTA on the #3 install card is the first thing a power user (IDE-centric dev) will try. Two dead buttons is a trust crater.

2. **Make the page responsive.** Add `@media (max-width: 1280px)` (and `max-width: 768px`) classes to `globals.css` (lead action) and reference them from `Index.tsx`. The two-column hero and three-column install grid both need to stack vertically. Until the lead lands the classes, use a React `useEffect + matchMedia` toggle on a `data-layout` attribute — not ideal but unblocks the P1 fix within ownership bounds.

3. **Replace raw hex literals in the CLI code block** with tokens. Three of the five hexes map directly to existing tokens (`--ink`, `--surface`, `--ink-mute`). The green prompt needs a new `--good-cli` token — flag to lead for `globals.css` addition. This is a 15-minute fix that enforces brand integrity across surfaces.

4. **Add a "Sign in →" CTA to the nav.** The marketing page's job (per the golden flow) is to funnel visitors to either Download or Sign-in. Right now there is no sign-in path above the fold. One `<PlatBtn>` link in the nav header resolves this.

---

## Flow walkthrough — post-P1 commit note

First-time user lands on `/`. They are most likely to get stuck at the IDE install card because both the VS Code and Cursor marketplace buttons were live-looking CTAs with no `href`, making them appear functional while silently doing nothing — a trust crater for the IDE-native developer who is the most likely power-user persona. The fixes in these commits address it by wrapping both buttons in `aria-disabled` spans with `pointer-events: none`, `opacity: 0.45`, and a `title="Coming soon — Marketplace listing pending"` tooltip, making the unavailability explicit and honest rather than silent.

5. **Derive the Dash version from `release.tag_name`** in the install card footer. The hook is already called and the data is available. Using it prevents version drift on every release without any code change.
