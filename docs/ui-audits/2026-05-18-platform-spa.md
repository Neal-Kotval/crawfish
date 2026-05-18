# Platform SPA UI Audit — 2026-05-18

Scope: every user-facing surface under `cloud/platform/src/**` *except* `OrgRoute.tsx`,
which is covered by the org-workspace audit. Files in scope:

- `Shell.tsx` — signed-in app chrome (titlebar + sidebar).
- `main.tsx` — route table.
- `pages/Auth.tsx` — `/signin` and `/signup` (Clerk widget + dev façade).
- `pages/OrgPicker.tsx` — `/` signed-in landing (org grid).
- `pages/OrgMembers.tsx` — `/orgs/:org/team` (members + invites).
- `pages/Projects.tsx` — projects list, used as a panel.
- `pages/ImportModal.tsx` — GitHub-repo import modal.
- `pages/InviteAccept.tsx` — `/invites/:code` (open to unsigned users).
- `pages/Link.tsx` — `/link/:code` (Dash device-link redeem).
- `onboarding/OnboardingFlow.tsx` — `/onboarding/:step?` (5-stage flow).

`OrgRoute.tsx` findings already in `2026-05-18-org-workspace.md` are referenced
but not duplicated; new gaps observed there appear in *Consistency gaps* below.

## Scorecard

| Dimension | Platform SPA (excl. OrgRoute) |
|---|---|
| Info architecture | 4/5 |
| Visual hierarchy | 3/5 |
| Empty / loading / error states | 4/5 |
| Visual polish | 2/5 |
| Real-vs-mock data | 3/5 |
| Responsive | 2/5 |
| Accessibility | 2/5 |
| **Overall** | **20/35** |

Platform SPA is structurally sound — every page has explicit loading, empty,
and error states, the IA matches Dash, Clerk vs dev-façade is cleanly
isolated. The weak axes are *visual polish* and *accessibility*: nearly every
component re-rolls primitives via inline style objects (`<button style={{
appearance: "none", border: "1px solid var(--rule-3)"...}}>`) instead of
reusing `.cfp-btn` / `.cf-card` / `Pill` etc. that already exist. The result
is a surface that *looks* consistent because all the tokens are the same,
but every button is implemented six different ways. Two literal hex colors
(`#e9e4d0`, `#f7f3ea`) leak through onboarding. The modal scrim uses
`rgba(0,0,0,0.45)` — pure black, not warm ink.

## Blockers (must-fix)

- [P1] `onboarding/OnboardingFlow.tsx:486` — `<pre style={{ background: "var(--ink)", color: "#e9e4d0" ... }}>` uses an inline hex literal for the terminal text color. Same surface, same hex, recurs in `Install` at line 573. Fix: replace `"#e9e4d0"` with `var(--paper-2)` (or define `--ink-on` in tokens; lead-only, request via SendMessage). The Handoff "Open in Dash" card at line 691 has a third one: `color: "#f7f3ea"`. All three are the same paper-on-ink text and must come from a token.
- [P1] `pages/ImportModal.tsx:65` — Modal scrim is `background: "rgba(0,0,0,0.45)"` — pure black. The brand has no pure-black surface; every other overlay uses warm-ink RGB. Fix: use `rgba(26, 26, 24, 0.45)` derived from `--ink` (`#1a1a18`), or a `--scrim` token if one exists. Same fix for `boxShadow: "0 24px 60px rgba(0,0,0,0.25)"` on line 81.
- [P1] `Shell.tsx:80-97` — A `<style>` tag is *injected inline inside the component* to add a 768px responsive breakpoint. Inline `<style>` blocks (a) re-emit on every render, (b) break the file-ownership rule that "CSS lives in `ui/tokens/globals.css` only" (`CLAUDE.md`), and (c) the rule uses `!important` overrides because it has no way to win against the original utility classes. Fix: remove the inline `<style>` from `Shell.tsx` and SendMessage the lead to add `.cfp-shell--responsive` rules to `ui/tokens/globals.css`. As written, this is a teammate-touching-shared-CSS violation.
- [P1] `pages/Auth.tsx:46-211` — The "dev façade" renders an email input + "Send magic link" / "Continue with GitHub" buttons that **do nothing real**: both buttons just call `onContinue` which sets `localStorage.cf_dev_user = "dev@local"` and routes to `/`. The email field is decorative — the value is never read. This is the "wired-up dead button" the team spec calls out by name (`§6: Wire up dead buttons or hide them — no more 'looks primary, does nothing'`). Fix: in dev façade, hide the email input + "Send magic link" entirely; leave only "Continue with GitHub →" which honestly stamps the dev user. Add a small "dev mode" eyebrow above so the user understands. Lines 150-176 (email + magic-link button + divider) come out; the existing dev-mode footer note already explains the state.
- [P1] `Shell.tsx:111-142` — Inline `<Eyebrow style={{...}}>` and ad-hoc paddings duplicate sidebar group-header styling instead of using the existing `.cf-sidebar__group` / `.cf-sidebar__heading` classes already in `globals.css`. The bigger issue: `orgs.length === 0` empty state at line 143 renders inline-styled muted text "No orgs yet. Create one to get started." while the OrgPicker already renders a full "No orgs yet" page. With both visible, the sidebar's empty state is redundant chrome that pre-empts the main page's empty state. Fix: when `orgs.length === 0` in the sidebar, hide the "Your orgs" heading entirely and render only "New org" — let the main panel own the empty state.
- [P1] `onboarding/OnboardingFlow.tsx:35-40` — `DEFAULT_AGENTS` (eng-bot / designer-bot / support-bot / ops-bot) is rendered in the Propose stage (line 492-503) and the Install stage (line 534) as the "your company's agents." The user has no input on who gets hired — the screen says "you can rename anything … on the next screen" (line 506) but there is no such screen; the next stage is Install which already commits to these four. This is mock data shown as a real promise. Fix: either (a) drop the rename-promise copy, or (b) make the agent list editable in Propose. Cheapest fix: change the copy at line 506 to "You can rename agents and swap runtimes from the canvas once you're in." Cross-surface concern: server-side `createOrg` also seeds these four — surface to lead via SendMessage if the seed list should also become configurable.
- [P1] `pages/InviteAccept.tsx:297` and `Shell.tsx:49` — Both files call `useClerk()` conditionally with an ESLint disable. This works today because `CLERK_ENABLED` is a build-time constant, but it is fragile (an HMR reload across an env change between builds will React-error) *and* surfaces a code smell to anyone reading the file. Fix: lift the hook unconditionally and gate the *value*, not the *call*: `const clerk = useClerk();` inside a `<ClerkProvider>` and a stub when not. (Today's main.tsx already renders `tree` outside the provider when `!CLERK_ENABLED`; a single conditional-component pattern at module boundary removes the per-call disables.) If full fix is risky, at minimum add a comment block above each disable explaining why it's safe; today only one of the two has it.

## Majors (should-fix before next release)

- [P2] `pages/OrgPicker.tsx:73-86` — Loading state renders a single dashed card "loading…" *inside* the org grid. With `gridTemplateColumns: auto-fill, minmax(320px,1fr)`, that one card spans only one column and looks like a real (broken) org row. Fix: render the skeleton outside the grid, or render 3 skeleton cards so the layout reads as loading rather than as one weird item.
- [P2] `pages/OrgPicker.tsx:88-147` — Org cards are hand-rolled `<button>` elements with appearance:none + 15 inline style props. The same pattern already exists in dash (`cf-card` + `cf-card--interactive`). Fix: extract to `<OrgCard>` in `cloud/platform/src/components/` that renders a `.cf-card` and consumes `Pill`. (Component creation is OK — lives entirely under owned path.)
- [P2] `pages/OrgMembers.tsx:228-247` — "Send invite" button toggles between `.cfp-btn` and `.cfp-btn cfp-btn--primary` via string concatenation and adds inline override styles when disabled. The disabled state literally swaps the className back to plain `cfp-btn` while also passing `style={{ background: "transparent", color: "var(--ink-mute)", border: "1px solid var(--rule-3)" }}` — those should be in `.cfp-btn:disabled` in tokens. Fix: always render `cfp-btn cfp-btn--primary`, drop the inline disabled overrides, and SendMessage lead to ensure `.cfp-btn:disabled` is styled in `globals.css`.
- [P2] `pages/OrgMembers.tsx:407` — Revoke button is a 28×28 `×` glyph. No `aria-label="Revoke invite"` (it has `title="Revoke invite"` only). Fix: add `aria-label`. Same gap on `ImportModal.tsx:114` (close `×` has `aria-label="Close"` — keep — but the `OrgMembers` revoke and the copy-link button are unlabeled or use only `title`).
- [P2] `pages/OrgMembers.tsx:86` — `if (!window.confirm(...))` — native `confirm()` is brand-incongruous. Fix: replace with an inline confirm step (click → "Click again to confirm" within 2s) or a `<dialog>`-based prompt; the codebase already has `ImportModal` styling to reuse.
- [P2] `pages/Projects.tsx:73-77` — Polls `/api/orgs/:orgId/projects` every 5s indefinitely. No pause when tab is hidden (`document.visibilityState !== 'visible'`). On a long-lived signed-in session this burns server requests forever. Fix: stop the interval when `document.hidden`, restart on focus.
- [P2] `onboarding/OnboardingFlow.tsx:683` — `gridTemplateColumns: "1fr 1fr"` for the Handoff cards has no responsive fallback. Below ~640px the "Open in Dash" / "Stay in browser" cards become two unreadable squashed tiles. Fix: `gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))"`.
- [P2] `onboarding/OnboardingFlow.tsx:407-454` — `SegRow` is a custom segmented control that does not reuse `.cf-segmented` from `globals.css` (which is the canonical iOS-style pill segmented control). Fix: replace inline implementation with `.cf-segmented`.
- [P2] `Shell.tsx:159-167` — The active-org indicator dot is `width: 6, height: 6, background: "var(--accent)"` — but **every** org in the sidebar gets the dot regardless of which is currently active. Compare with `SideItem`'s own `active` prop on the same line. Fix: only render the dot when the row is active, or differentiate active vs inactive (filled vs outline).
- [P2] `pages/Auth.tsx:108-194` — DevFacade has no `<form>` wrapper, so pressing Enter in the email input does nothing. Fix: wrap in `<form onSubmit={onContinue}>`.
- [P2] `pages/InviteAccept.tsx:280` — `<a className="cfp-btn cfp-btn--primary">Sign in to continue</a>` — anchor styled as a button, no `role="button"`. Tabbing reads it as a link, which is correct semantically; but the visual is a primary CTA. Either accept the discrepancy (it's fine for screen-readers) or wrap target in a programmatic navigate. Lower-impact P2.
- [P2] `pages/Link.tsx:64` — Card is `width: 460` (fixed). Below 460px viewport it overflows. Fix: `width: "100%", maxWidth: 460`. Same issue at `Auth.tsx:46`.

## Polish (nice-to-have)

- [P3] `Shell.tsx:21-27` — `NAV` includes `Knowledge` and `Diagnoses`, but `main.tsx` only registers `/orgs/:org/:tab` — clicking these routes dispatches `<OrgRoute>` which (per the org-workspace audit) only renders Canvas content. Sidebar links to non-existent screens. Either implement stub pages or hide entries until they exist.
- [P3] `pages/OrgPicker.tsx:139` — `<Pill tone="ink">{o.role}</Pill>` shows raw role string. If server returns `"owner"`/`"contributor"` lowercase it reads engineering-ish. Title-case it in display.
- [P3] `pages/OrgMembers.tsx:225-226` — `<option value="contributor">contributor</option>` (lowercase). Title-case in the dropdown; keep value lowercase.
- [P3] `pages/ImportModal.tsx:468` — `updated {new Date(...).toLocaleDateString()}` — show relative time ("updated 3d ago") for repos updated in the last 30 days; absolute date older.
- [P3] `pages/Projects.tsx:81-117` — H1 reads "Projects" without the org context. Eyebrow above has `{orgId} · projects`. Drop the H1 to `{org.name}` mirroring `OrgMembers.tsx`.
- [P3] `onboarding/OnboardingFlow.tsx:211-231` — Step indicator + progress bar are separately implemented in the header. Combine: `"Step 2 of 5 · propose"` could be the eyebrow above the progress bar instead of a separate column.
- [P3] `onboarding/OnboardingFlow.tsx:603` — "● Your company is hired" eyebrow uses a manual `●` glyph and `color: "var(--good)"`. Reuse `<Pill tone="good" live>` (already used at line 622) instead of a styled span.
- [P3] `pages/Auth.tsx:53-73` — The 28×28 cf logo block is re-implemented in 4 places (`Auth.tsx:53`, `OrgPicker.tsx:111`, `OnboardingFlow.tsx:191`, `OrgRoute.tsx` per the other audit). Extract to `<CfMark size={28|24|...} />` in `cloud/platform/src/components/`.
- [P3] `pages/Link.tsx:140` — Letter-spacing `0.06em` on a 48px font is fine but cells visually wander; consider `font-feature-settings: "tnum"` on the mono token so all digits are equal width.
- [P3] `pages/OrgMembers.tsx:281` — "MOCK EMAIL, dev mode, no SMTP yet" — fine for dev. In Clerk-enabled builds this should disappear (the invite-by-email flow still synthesizes a `mockEmail` field from the server). SendMessage lead to clarify server behavior.

## Mock-data inventory

Every literal that ships to the user verbatim:

- `OnboardingFlow.tsx:35-40` — `DEFAULT_AGENTS` (eng-bot / designer-bot / support-bot / ops-bot) — rendered in Propose pre at line 492-503 and again in Install stream at line 534. These ARE installed server-side at `createOrg`, so they are real in the sense that the org gets them. But the user is told (line 506) they can rename them, which is not true today.
- `OnboardingFlow.tsx:493-503` — ASCII tree literal (knowledge dirs, policies, crawfish.toml) — informational, but `api-conventions.md` and `runbooks/` are specific filenames that look like things the user can open. They are not opened anywhere in the app yet.
- `OnboardingFlow.tsx:531-538` — `allLines` install log strings (`crawfish init`, `writing crawfish.toml`, etc.) — entirely synthetic, drip-fed via `setInterval(160ms)`. The server call (line 148-154) is the real install; this is theater. Fine as theater, but if the server errors the user sees the stream complete *then* gets bounced to propose with an error. Should pause/red the stream when `error` is set.
- `OnboardingFlow.tsx:632` — `MARKETING_URL` falls back to `"http://localhost:5173"` if env unset. In a prod build with a missing env, the "Download Dash" link points at localhost. Fine for dev; surface via lead if prod build is at risk.
- `OnboardingFlow.tsx:691, 573, 486` — `#f7f3ea`, `#e9e4d0`, `#e9e4d0` — hex literals (see P1 above).
- `ImportModal.tsx:65, 81` — `rgba(0,0,0,...)` — black, not warm ink (see P1 above).
- `Shell.tsx:101` — `orgGlyph={inOrg ? "cf" : "··"}` — when not in an org the titlebar glyph is `··` (two dots). Innocuous but undocumented.
- `Auth.tsx:152` — `"you@company.com"` placeholder — generic. Could read `"founder@yourstartup.com"` to match brand voice (this is "hire your company"). Polish-level.
- `OnboardingFlow.tsx:350, 360` — placeholders `"e.g., a B2B SaaS analytics tool"` and `"e.g., acme-co"` — fine, leave.

## Consistency gaps (platform SPA vs Dash, and OrgRoute vs siblings)

- **Card primitive.** OrgPicker, Projects, OrgMembers, InviteAccept, and Link each hand-roll a "surface card" with `background: var(--surface-2)`, `border: 1px solid var(--rule-3)`, `borderRadius: var(--r-lg)`, `padding: 18|24|28`. Dash uses `.cf-card`. Recommend: collapse to a single `<Card>` (or `.cfp-card` class via lead) and use it everywhere.
- **Primary button.** Three implementations coexist: `.cfp-btn.cfp-btn--primary` (OrgMembers send, InviteAccept accept, OnboardingFlow continue), inline `background: var(--accent)` strings, and `.cfp-btn.cfp-btn--ink` (Auth dev-façade GitHub). Recommend: every primary CTA → `.cfp-btn.cfp-btn--primary`; the inked variant is a one-off for "Continue with GitHub" specifically and that's fine but document it.
- **Title hierarchy.** OrgPicker H1 = 36px, OrgMembers H1 = 32px, Projects H1 = 32px, Auth H1 = 28px, Link H1 = 26px, InviteAccept H1 = 28px. Recommend: 3-step scale — page H1 = 32px, page-within-flow H1 = 28px, modal H1 = 20px (Import).
- **Eyebrow context.** OrgMembers uses `{org.name} · team`, Projects uses `{orgId} · projects`, OrgRoute (per other audit) uses `{org.name} · canvas`. The lowercase trailing word is consistent; the slug-vs-name is not. Recommend: always `{org.name}` (resolve from the loaded `Org`).
- **Empty-state copy.** "No orgs yet." (OrgPicker) vs "no pending invites" (OrgMembers) vs "no repos match" (ImportModal) vs "No projects yet." (Projects). Some sentence-case + period, some lowercase + no period. Recommend: sentence-case with period for body-tone empties; lowercase mono for table-row empties. The current mix is roughly right but `OrgMembers.tsx:328` "no pending invites" should match table-row style → keep as-is, mark `Projects.tsx:259` "No projects yet" as body-style → keep as-is. Action: document the rule in a README comment; no code change.
- **Loading copy.** "Loading…" (OrgPicker H1), "loading…" (mono everywhere else). Two styles. Recommend: H1 stays sentence-case; mono spinner stays lowercase; rule is "if the loading message is the page's H1, sentence-case it; if it's a small placeholder, lowercase mono."
- **OrgRoute consistency.** The org-workspace audit notes `OrgRoute.tsx:79-80` has dead constants (`DEFAULT_GRID_Y`, `DEFAULT_GRID_XS`) and at `:138-149` the "← Back to all orgs" link is under-styled. Both remain. The "Open in Dash" CTA at OrgRoute is duplicated by the `Handoff` card in onboarding — extract a shared `<OpenInDashCard>` component.
- **Dev-mode banners.** OrgMembers shows a dashed `MOCK EMAIL, dev mode` card; Auth shows `dev mode · set VITE_CLERK_PUBLISHABLE_KEY for real auth`; neither shares formatting. Recommend: a single `<DevBanner>` component with consistent tone.

## Recommendations

The single most leveraged changes, in order:

1. **Extract three components** under `cloud/platform/src/components/`: `<CfMark>`, `<Card>` (or `<SurfaceCard>`), and `<DevBanner>`. Migrate Auth, OrgPicker, OrgMembers, Projects, InviteAccept, Link, OnboardingFlow to consume them. This single refactor turns ~30 hand-rolled inline-style blocks into 4-7 component invocations and gets the platform back on token discipline. **Cuts most P2s in one pass.**
2. **Kill every hex literal and rgba-black** in this surface: three `#e9e4d0`/`#f7f3ea` instances in onboarding + two `rgba(0,0,0,...)` in ImportModal. Either reuse an existing token or SendMessage the lead to add `--ink-on` and `--scrim`.
3. **Remove the inline `<style>` block from `Shell.tsx`** and SendMessage lead to land the 768px responsive rule in `globals.css`. This is a binding ownership-rule violation today.
4. **Trim the dev-facade Auth page** to a single "Continue with GitHub" button. Today it's a fake email form that pretends to send a magic link.
5. **Fix the onboarding rename-promise copy** so the Propose stage doesn't claim users can edit agents on a non-existent next screen.
6. **Add a `document.hidden` pause** to the projects-list poller, and a small skeleton row count to the OrgPicker loading state so it doesn't look like a single broken org.

Backend gaps to surface to lead via SendMessage (do **not** implement):

- `Shell.tsx` Knowledge / Diagnoses sidebar entries route to `OrgRoute` which doesn't render them. Either route table needs new branches or sidebar entries need to be hidden.
- `OnboardingFlow.tsx` Propose stage promises an editable agent list that the server doesn't expose. Either add a `PATCH /api/orgs/:id/agents` endpoint or drop the promise.
- A `--ink-on` token (paper text on ink surfaces) and `--scrim` token (modal overlay) are referenced by code today via hex literals; add to `ui/tokens/globals.css` per CLAUDE.md (lead-only).
- `.cfp-shell--responsive` rule needs to live in `globals.css`, not inline in `Shell.tsx`.
- `.cfp-btn:disabled` styling — request a default disabled state so `OrgMembers.tsx:228-247` can drop its inline overrides.

---

## Flow walkthrough note — 2026-05-18 Phase 2 commits

First-time user lands on `/signup`, sees the DevFacade card with "Continue with GitHub →" as the sole auth action (magic-link stub removed), stamps `cf_dev_user` in localStorage, and is routed to `/` where the OrgPicker renders an empty grid with a "Create your first org" CTA. They're most likely to get stuck at the Propose stage of onboarding because the old copy promised an editable agent list "on the next screen" that doesn't exist — leading to confusion when Install fires immediately and no editing screen appears. The fix in this commit replaces that promise with "You can rename agents and swap runtimes from the canvas once you're in," correctly directing users to the post-onboarding canvas rather than a non-existent intermediate step.
