# Cross-Surface UI Audit — 2026-05-18

Synthesis of four teammate audits + the prior org-workspace audit. Identifies the patterns that repeat across surfaces, the lead-only cross-cutting backlog they imply, and the brand-contract drift to address before the next release.

**Source audits**
- [`2026-05-18-org-workspace.md`](./2026-05-18-org-workspace.md) — prior audit, Platform OrgRoute + Dash Canvas
- [`2026-05-18-web-marketing.md`](./2026-05-18-web-marketing.md) — `web/src/`
- [`2026-05-18-platform-spa.md`](./2026-05-18-platform-spa.md) — `cloud/platform/src/` (excl. OrgRoute)
- [`2026-05-18-platform-spa-playwright.md`](./2026-05-18-platform-spa-playwright.md) — Playwright walk of the platform SPA
- [`2026-05-18-dash-studio.md`](./2026-05-18-dash-studio.md) — Canvas/Board/Plan/Sessions/etc.
- [`2026-05-18-dash-data-views.md`](./2026-05-18-dash-data-views.md) — Analytics/Knowledge/Diagnoses/etc.

---

## Scorecard at a glance

| Surface | Overall | Real-vs-mock | Responsive | Accessibility | Worst pillar |
|---|---|---|---|---|---|
| Web marketing | 18/35 | 2/5 | 1/5 | 2/5 | Responsive (1/5) |
| Platform SPA (ex OrgRoute) | 20/35 | 3/5 | 2/5 | 2/5 | Polish (2/5) |
| Platform OrgRoute (prior) | 24/35 | 4/5 | 3/5 | 3/5 | — strongest |
| Dash Canvas (prior) | 14/35 → fixed | 1/5 → 5/5 | 1/5 | 2/5 | Was real-vs-mock; now responsive |
| Dash Studio (excl Canvas) | 16/35 (AgentCanvas) → 25–30/35 (others) | 1/5 (AC) → 5/5 (rest) | 2–4/5 | 2–4/5 | AgentCanvas seed data (fixed) |
| Dash Data Views | 22/35 | 4/5 | 3/5 | 2/5 | Accessibility (2/5) |

**Bottom line:** the studio cluster is strongest after the Canvas + AgentCanvas fixes shipped this cycle. The weakest surface is `web/` — single page, no responsive plan, no sign-in CTA, dead IDE marketplace buttons (now disabled). Platform SPA is structurally correct but visually rough — every primitive is rolled inline.

---

## Patterns that repeat across surfaces

### 1. Hex literals leak through every surface

Every audit found hex literals despite DESIGN.md §8 ("Always reference the var, never the hex."). All resolved this cycle:

| Surface | File | Hex | Replaced with |
|---|---|---|---|
| Web | `Index.tsx:153-159` | `#1a1a18`, `#e9e4d0`, `#6fb98f`, `#7a766c` | `--ink`, `--surface`, `--good`, `--ink-mute` |
| Platform | `OnboardingFlow.tsx:486,573,691` | `#e9e4d0`, `#f7f3ea` | `--paper-2` |
| Platform | `ImportModal.tsx:65,81` | `rgba(0,0,0,…)` | `rgba(26,26,24,0.45)`, `--shadow-lg` |
| Dash Studio | `AgentCanvas.tsx:50`, `Settings.tsx:298` | `#f7f3ea` | `--paper` |
| Dash Data | `Projects.tsx:339,408,443,475,486` | `var(--bad, #b1452f)` | `var(--bad)` |
| Dash Data | `Projects.tsx:290,321` | `var(--line, #e5e1d8)` | `var(--rule)` |

**Recurring need:** two of these mappings used `--paper-2` as a stand-in for "warm paper text on an ink surface" — that's not what `--paper-2` is for (it's a sunken background token). The right long-term fix is a new **`--ink-on`** semantic token. Same story for the modal scrim — `rgba(26,26,24,0.45)` should become a **`--scrim`** token. Both are lead-only `ui/tokens/globals.css` additions (see cross-cutting backlog).

### 2. Card and button primitives are hand-rolled everywhere

Each surface re-rolls a "surface card" or "primary button" inline:

- **Platform** has 5+ hand-rolled card implementations (OrgPicker, Projects, OrgMembers, InviteAccept, Link) and 3 primary-button implementations (`.cfp-btn--primary`, inline `background: var(--accent)`, `.cfp-btn--ink`).
- **Dash Studio** mostly uses `.cf-card` / `.cf-btn` but `AgentCanvas.tsx` uses `cfp-stat__bar` / `cfp-stat__fill` / `cfp-shell__rail` — the older `cfp-*` namespace. Confirmed undefined in globals.css → progress bars render zero-height.
- **Web marketing** uses `<PlatBtn>` but the "Invite a teammate later" link reimplements button styling inline.

**Action:** lead audit of `cfp-*` class completeness. Either define the missing rules in globals.css or migrate AgentCanvas to `cf-*` equivalents. Long-term, extract `<Card>` / `<SurfaceCard>` / `<CfMark>` / `<DevBanner>` into shared platform/`components/` (within Platform ownership) and `@crawfish/ui` (lead-only).

### 3. Legacy `--cf-*` shim still has live consumers

DESIGN.md §2.8 explicitly bans new code against `--cf-*`. Live consumers across surfaces:

- `desktop/dash/web/src/routes/Plan.tsx` — 13 occurrences (`--cf-radius-md`, `--cf-border`, `--cf-bg`, etc.) — *deferred this cycle as scope creep.*
- `desktop/dash/web/src/components/CompoundingKPI.tsx` — `--cf-success/warning/danger` (status colors that render invisible because aliases don't propagate the way the code assumes — see audit).
- `desktop/dash/web/src/components/SpendWidget.tsx` — same.
- `desktop/dash/web/src/routes/Analytics.tsx` — `--cf-fg-secondary` (loading text).

The status aliases `--cf-success`, `--cf-danger`, `--cf-warning` **are** defined (lines 117–119 of globals.css map them to `--good` / `--danger` / `--warn`), so the dash-data audit's "invisible signal" claim is partially wrong; visibility is fine via the shim. But the shim deletes in Wave 5. Migrating these four files to canonical tokens (`--good`, `--bad`, `--warn`, `--ink-mute`) is a 30-minute job and removes Wave-5 risk.

**Action:** schedule a "Wave 5 prep" sweep — one commit per file, no other changes.

### 4. Loading-state pattern split

Three patterns coexist:

- `<EmptyState title="Loading…" body={<span className="cf-spinner" />} />` — canonical (Sessions, Home, Org, agents, optimizers, runtimes)
- `<div className="cf-empty"><span className="cf-spinner" /> Loading…</div>` — partial (dashboard, compare)
- Bare `<div style={{ color: "var(--cf-fg-secondary)" }}>loading…</div>` — wrong (Analytics, OrgPicker)

This cycle migrated Analytics' loading divs to `<EmptyState>`. The remaining `cf-empty` pattern in `dashboard.tsx` and `compare.tsx` is deferred (it renders correctly, just inconsistent).

**Action:** documented; no code change required this cycle.

### 5. Mock data masquerading as real data

The signature bug across the product. The Canvas/AgentCanvas seed-data leaks were the worst-of-class examples; both are now fixed. Remaining offenders:

- **Web `Index.tsx` hero stats** (`10,412 orgs`, `−35% factor`, `3.25× reduction`) — static literals presented as social proof. P2.
- **Web install card `114 MB · v0.4.1`** — hardcoded version that will silently drift. P2.
- **Platform `OnboardingFlow.tsx` install stream** — `setInterval(160ms)` drip-feed of synthetic "install lines" is theater. Fine as theater, but doesn't pause on error. P2.
- **Dash `dashboard.tsx` Estimated savings card** — was a dead `"—"` value; now gated behind real `savings` data.
- **Dash `HomeDashboard.tsx` greeting** — was `"Hello, !"` for users with no display name; now reads `"Welcome back, there."`.

The recurring pattern: **fallback values that look real are always worse than empty states that say so**. Whenever a component falls back to a literal, it lies. Use `<EmptyState>` or `<Eyebrow>No X yet</Eyebrow>` instead.

### 6. Responsive failures are everywhere

Each surface fails responsive in a different way:

- **Web** — two-column hero grid and three-column install grid have no breakpoints below 1280px. **Fixed** this cycle via inline `matchMedia + data-layout` toggle.
- **Platform Onboarding** — `gridTemplateColumns: "1fr 1fr"` on the Handoff cards has no responsive fallback. *Deferred — P2.*
- **Platform Shell** — has an inline `<style>` block adding a 768px rule with `!important` overrides. Brand-contract violation; deferred (needs lead-owned CSS class).
- **Dash Canvas** — `position: absolute` everywhere; collapses below 960px. P2 from prior audit, not addressed this cycle.

**No surface has a consistent breakpoint plan.** A single set of breakpoints in `globals.css` (`@media (max-width: 1280px)`, `768px`, `480px`) consumed via utility classes would let every surface drop their bespoke approach.

### 7. Accessibility gaps repeat

- Missing `aria-label` on icon-only buttons (revoke, close, copy).
- Native `window.confirm()` in OrgMembers (P2).
- `<div role="button">` with `onClick` but no `onKeyDown` (Home, Canvas agent nodes).
- Inline-styled active indicators using only color (sidebar active-org dot, Org tab indicator) — fails 3:1 contrast.
- Missing heading landmarks (`runtimes.tsx`, `integrations.tsx`).

None addressed this cycle; all P2/P3. Cluster into an a11y-focused phase.

### 8. Eyebrow / title hierarchy isn't consistent

- Page H1 sizes range from 26px → 36px across pages within Platform SPA.
- Eyebrow context format is mixed: `{org.name} · team` (OrgMembers) vs `{orgId} · projects` (Projects). The slug-vs-name divergence is on the lead's documentation backlog.

**Action:** document the 3-step page-title scale (page 32 / flow-step 28 / modal 20) in DESIGN.md §3. Lead-only.

---

## Lead cross-cutting backlog

Items the teammates raised but only the lead can land (touches `ui/tokens/globals.css`, `ui/components/`, or `DESIGN.md`):

### Token additions

- [ ] `--ink-on` — paper text color on ink surfaces. Today's workaround uses `--paper-2` (a background token).
- [ ] `--scrim` — modal overlay color. Today's workaround inlines `rgba(26,26,24,0.45)`.
- [ ] (Optional) `--good-cli` — lighter mint for CLI prompt arrows on dark surfaces. Today the web marketing CLI block uses `--good` (`#2f7a4d`) which reads darker than the original design.

### Class additions

- [ ] `.cfp-shell--responsive` — the 768px responsive rule for the platform sidebar. Currently lives as an inline `<style>` block in `Shell.tsx`, which is a binding ownership-rule violation per CLAUDE.md.
- [ ] `.cfp-btn:disabled` — default disabled styling so `OrgMembers.tsx:228-247` can drop its inline overrides.
- [ ] Audit `cfp-*` class completeness — `AgentCanvas.tsx` uses `cfp-stat__bar`, `cfp-stat__fill`, `cfp-shell__rail`. Verify they're defined and not silently orphaned.

### Component extractions (next pass; lead drafts contract, teammates implement)

- [ ] `<SurfaceCard>` — collapses the 5+ hand-rolled card implementations in Platform SPA.
- [ ] `<CfMark size={28|24|20}>` — currently re-implemented in Auth, OrgPicker, OnboardingFlow, OrgRoute.
- [ ] `<DevBanner>` — single component for "dev mode" notices (currently 2 hand-rolled variants).
- [ ] `<OpenInDashCard>` — shared between Platform OrgRoute and Onboarding Handoff.

### Wave 5 prep (kill `--cf-*` shim)

A focused migration sweep, one commit per file:
- [ ] `desktop/dash/web/src/routes/Plan.tsx` (~13 occurrences)
- [ ] `desktop/dash/web/src/components/CompoundingKPI.tsx`
- [ ] `desktop/dash/web/src/components/SpendWidget.tsx`
- [ ] `desktop/dash/web/src/routes/Analytics.tsx` (any remaining `--cf-fg-secondary` after this cycle's EmptyState migration)

After these land, search `desktop/dash/web/src` and `cloud/platform/src` for `--cf-` to confirm zero hits, then DESIGN.md §2.8 can be updated to schedule shim deletion.

### Documentation

- [ ] Document the 3-step page-title scale in DESIGN.md §3.
- [ ] Document the empty/loading-state rule: H1-style "Loading…" for full-page state; mono-style `loading…` for inline placeholders.
- [ ] Add the responsive breakpoint set (1280 / 768 / 480) to DESIGN.md §4 as the canonical viewports.
- [ ] Note that the four surfaces share `ui/tokens/globals.css` but ship from different submodules with independent release cadences — coordinate token additions via the lead-only rule.

---

## Golden-flow checkpoint

The team spec's golden flow (§7):

1. **Marketing** — visitor lands at `crawfish.dev`, understands pitch in 5s, clicks Download/Sign in.
2. **Platform** — signs in via Clerk (or dev-bypass), creates org, imports a project.
3. **Dash Canvas** — opens desktop, sees real org canvas (no seed Pat / no fake KPIs).
4. **Dash data views** — Analytics/Knowledge/Diagnoses show honest empty states.

### Where the user can still get stuck after this cycle

- **Step 1 → Step 2 handoff.** The marketing page still has no "Sign in" CTA in the nav. A user wanting to skip the download lands on `/` and finds only a GitHub link. P2 surface to follow up — small lift.
- **Step 2 onboarding propose-stage copy.** Fixed this cycle — no longer promises a non-existent rename screen.
- **Step 2 dev-facade.** Fixed — magic-link dead button removed.
- **Step 3 Canvas.** Fixed in prior cycle (commit `590f244`) + this cycle's AgentCanvas pass.
- **Step 4 dashboard / Analytics.** Fixed — loading states are now `<EmptyState>`; the savings card is gated; the greeting no longer reads `"Hello, !"`.

### Where the flow remains fragile

- **No "Sign in" CTA in marketing nav.** The download CTA exists but a returning user looking to sign in must guess that the platform lives at a different subdomain.
- **Platform sidebar's Knowledge / Diagnoses entries** route to `OrgRoute` which doesn't render either. Sidebar links to non-existent screens. Deferred — needs route table + backend work.
- **Onboarding install stream** doesn't pause/red when the server returns an error. The drip-feed completes, then the user is bounced back to Propose. Mild but disorienting. P2.

---

## Recommendations for the next cycle

In priority order:

1. **Land the `--ink-on` and `--scrim` tokens, plus the `.cfp-shell--responsive` class.** Three small lead-only commits unlock a follow-up sweep that removes the last hex literals from Platform Shell, the modal scrim's inline rgba, and the inline `<style>` block.
2. **Wave 5 prep sweep.** Migrate the 4 `--cf-*` files in one focused pass.
3. **Add a "Sign in →" CTA to web marketing nav.** Smallest possible fix to plug the only remaining golden-flow gap.
4. **Component extraction pass on Platform SPA.** `<SurfaceCard>`, `<CfMark>`, `<DevBanner>` — cuts ~30 inline style blocks down to ~10 component invocations. Big polish lift for low risk.
5. **A11y phase.** Cluster the missing aria-labels, native confirm() replacements, and active-indicator contrast bumps into a single dedicated pass.
6. **Documentation update.** Page-title scale + breakpoint set + empty-state rule in DESIGN.md. Reduces ambiguity for future teammates.
