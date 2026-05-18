# Dash Data Views UI Audit — 2026-05-18

**Scope:** `desktop/dash/web/src/routes/` — Analytics.tsx (337 ln), Knowledge.tsx (297 ln), Diagnoses.tsx (190 ln), Files.tsx (216 ln), Crons.tsx (529 ln), compare.tsx (339 ln), benchmarks.tsx (321 ln), HomeDashboard.tsx (218 ln), Projects.tsx (532 ln), dashboard.tsx (831 ln), agents.tsx (162 ln), optimizers.tsx (138 ln), policies.tsx (659 ln), runtimes.tsx (132 ln), integrations.tsx (199 ln). **5,100 lines total.**

**Theme:** Honest empty states. Most routes do not show fake data — the cluster is in significantly better shape than Dash Canvas. However three token-related issues are user-visible lies, and a pervasive pattern of non-token CSS variables (`--cf-success`, `--cf-danger`, `--cf-warning`) violates the design system.

---

## Scorecard

| Dimension | Score | Notes |
|---|---|---|
| Info architecture | 4/5 | Clear per-route purpose; tab navigation in Analytics is clean |
| Visual hierarchy | 3/5 | Several loading/error states use raw `<div style={{ color }}>` instead of `<EmptyState>` |
| Empty / loading / error states | 3/5 | Most routes handle these, but some are inconsistent in pattern |
| Visual polish | 3/5 | Inline `style` props pervasive; bar charts use raw `background:` colors |
| Real-vs-mock data | 4/5 | No hardcoded seed arrays; a few fallback values are misleading |
| Responsive | 3/5 | Grid layouts use fixed `gridTemplateColumns` with no breakpoint handling |
| Accessibility | 2/5 | Tab buttons lack `aria-controls`/`id` pairing; many `<div>` spinners |
| **Overall** | **22/35** | Better than Canvas; main problem is token misuse and uneven empty-state patterns |

---

## Blockers (must-fix)

- **[P1] `runtimes.tsx:120,125`** — `RuntimeCard` renders inline `style={{ color: "var(--cf-success)" }}` and `style={{ color: "var(--cf-danger)" }}` for the test-result feedback. `--cf-success` and `--cf-danger` ARE defined via the legacy `--cf-*` shim in `ui/tokens/globals.css` (mapped to `--good` / `--danger` respectively), so the colors render correctly today. However, per DESIGN.md §2.8, new code must not use `--cf-*` aliases — the shim is for legacy compile-only compatibility and is deleted in Wave 5. **Brand-contract violation: fix now before Wave 5 makes it a breaking render bug.** Fix: replace with `var(--good)` / `var(--bad)`. *(Rationale updated: original audit incorrectly flagged this as a current visibility bug; it is a forward-compatibility / brand-contract issue.)*

- **[P1] `Projects.tsx:339,408,443,475,486`** — Five `style={{ color: "var(--bad, #b1452f)" }}` inline fallbacks use a hardcoded hex `#b1452f` as the fallback for `--bad`. Per the prior audit, `--bad` was added to the token file but the fallback persists as a code smell that can silently override the token if the import order shifts. The hex is slightly off from the canonical danger color `#b53224`. **Fix: remove the hex fallback — write `color: "var(--bad)"` only.** Also `Projects.tsx:290,321` uses `var(--line, #e5e1d8)` — `--line` is not a defined token; the correct token is `--rule`. Fix: replace with `var(--rule)`.

- **[P1] `Analytics.tsx` — `DevPane` loading state** — the loading text `<div style={{ color: "var(--cf-fg-secondary)" }}>Loading dev analytics…</div>` uses the aliased token `--cf-fg-secondary` (which resolves via the `--cf-*` shim to `--ink-mute`) but the surrounding error state uses `<div className="cf-callout">` which is the correct pattern. **Fix:** replace the loading `<div>` with `<EmptyState title="Loading dev analytics…" body={<span className="cf-spinner" />} />` for consistency. Same for `ProductPane` loading state (same line pattern).

- **[P1] `dashboard.tsx` — `CompoundingKPI` and `SpendWidget` surface `--cf-*` non-token variables** — `CompoundingKPI.tsx` (not owned but called from owned `HomeDashboard.tsx`) computes a tone via `var(--cf-success)`, `var(--cf-warning)`, `var(--cf-danger)` — undefined aliases. Since `HomeDashboard.tsx` renders `<CompoundingKPI />` unconditionally when `orgs.length > 0`, every user with an org sees an invisible compounding-factor number (the color renders as ink rather than green/amber/red, defeating the visual signal). **This is a user-visible silent lie: the color coding that communicates health status does not render.** Fix: SendMessage `dash-studio` to update `CompoundingKPI.tsx` (shared component), or apply the token fix in `runtimes.tsx` and flag for the lead to propagate.

---

## Majors (should-fix before next release)

- **`Analytics.tsx:~204`** — `FlowGraph` pane is an unimplemented third tab ("Flow") in the Analytics tab strip. When selected, it renders `<FlowGraph orgId={orgId} />`. Whether that component shows anything meaningful or an empty state depends on the component (outside ownership). The tab label "Flow" is unexplained to the user — no tooltip, no description. Should add an `aria-describedby` hint or a sub-title below the tab strip.

- **`Analytics.tsx:~260–280` — `ProductPane` task-per-member bar** — the bar's fill color is `background: "var(--cf-fg)"` — the aliased form of `--ink`. This renders as dark ink on a slightly-lighter bar, which works visually but is semantically wrong (the bar looks like a text element, not a progress indicator). Should be `var(--accent)` to match the brand's vermillion accent for action/data.

- **`dashboard.tsx` — `Overview` `StatCard` for "Estimated savings"** — when `savings` is null (no transcripts running), the card shows `"—"` as the value with the sub-line "transcripts service not running or no data". This is correct, but the StatCard is shown regardless with a dead value. A user with no sessions sees a misleading three-up stat grid with two live values and one dead placeholder. The dead card should be gated behind `savings !== null` or replaced by a CTA card.

- **`Crons.tsx`** — No `aria-label` on the `<select>` for member assignment (the `member_id` dropdown). The label text "Agent member" is visually adjacent but not `htmlFor`-linked. Screen readers will announce a nameless select.

- **`policies.tsx:~300`** — The Compliance Strip (`<ComplianceStrip log={log} />`) renders only when `log` is truthy, but there is no loading indicator and no empty state when the log is still being fetched. A user clicking to the Policies route sees the full bundle UI minus the compliance strip with no indication that it is loading — a silent omission. Fix: add `{log === undefined && <div className="cf-text-xs cf-fg-tertiary">Loading compliance history…</div>}`.

- **`compare.tsx` — `labels` default values** — the two session picker labels default to `"Vanilla"` / `"Optimized"`. These are conceptually correct but could create confusion if users pick two sessions neither of which has any optimizer installed. The labels should default to `"Session A"` / `"Session B"` with a prompt to rename, making the comparison semantically neutral until the user assigns meaning.

---

## Polish (nice-to-have)

- **`Analytics.tsx`** — The `DevPane` "no sessions yet" message is a bare `<div style={{ color: "var(--cf-fg-secondary)" }}>` rather than an `<EmptyState>`. This is inconsistent with the other three routes that use `<EmptyState>` with an illustration. Use `<EmptyState>` for consistency.

- **`Knowledge.tsx`** — `AddSourceForm` uses `<input className="cf-input">` for both the ID and the path, but the `kind` dropdown uses the same `cf-input` class. The select inherits font-size from the input but the arrow indicator doesn't match the input's border-radius token. Minor visual jank. Consider wrapping in `<select className="cf-select">` if that class is defined, otherwise leave.

- **`Crons.tsx`** — `nextFire()` re-scans up to 525,960 iterations (one year of minutes) in the render thread. For a cron list of 20 items this runs 10M iterations synchronously on mount. Should be memoized with `useMemo` keyed on the cron expression and a stable reference time.

- **`HomeDashboard.tsx`** — The greeting `displayName` falls back to `""` (empty string) when the profile has no display name, rendering `"Hello, !"`. Should fall back to `"Hello"` or `"Hello there"`.

- **`integrations.tsx`** — The `Section` component's `hasContent` check uses `arr.some(Boolean)` which treats `0` and `false` as empty. This is correct for typical React children but fragile — a `<React.Fragment>` wrapping actual nodes would read as falsy. Consider `Children.count(children) > 0`.

- **`runtimes.tsx`** — Page title is `<div className="cf-text-xl cf-weight-semibold">Runtimes</div>` rather than an `<h1>` or `<h2>`. The heading landmark is missing. Same pattern in `integrations.tsx`.

---

## Consistency gaps (data-views ↔ Canvas / org-workspace)

- **Loading pattern split:** `dashboard.tsx` and `compare.tsx` use `<div className="cf-empty"><span className="cf-spinner" /> Loading…</div>`, while `agents.tsx`, `optimizers.tsx`, and `runtimes.tsx` use `<EmptyState title="Loading…" body={<span className="cf-spinner" />} />`. Neither is wrong, but the two patterns should be unified. Recommend `EmptyState` since it handles alignment and max-width automatically.

- **Error pattern split:** `Analytics.tsx` uses `<div className="cf-callout">` (three nested divs) for errors. All other routes use `<EmptyState title="…" body={<Message tone="error">…</Message>} />`. The callout pattern is lower-level and inconsistent. Recommend moving Analytics error states to the `EmptyState + Message` pattern.

- **`--cf-*` alias tokens** — `runtimes.tsx`, `CompoundingKPI`, `SpendWidget`, and `Analytics.tsx` reference `--cf-success`, `--cf-danger`, `--cf-warning`, `--cf-fg-secondary`, `--cf-bg`, `--cf-border`. The `--cf-*` shim in the design system maps the short aliases but not the semantic status aliases (`--cf-success`, `--cf-danger`). Every route should use the canonical tokens: `--good`, `--bad`, `--warn`, `--ink-soft`, `--surface`, `--rule`.

---

## Mock-data inventory

| File | Mock/seed data | User-visible? | Fix |
|---|---|---|---|
| `Analytics.tsx` | None — all data from `/api` + lens | No | — |
| `Knowledge.tsx` | None | No | — |
| `Diagnoses.tsx` | None — polls `/api/diagnoses/recent` | No | — |
| `Files.tsx` | None | No | — |
| `Crons.tsx` | `BLANK_DRAFT` default cron expression `"0 9 * * *"` — placeholder only, not rendered to user | No | — |
| `compare.tsx` | Default label strings `"Vanilla"` / `"Optimized"` | Yes — mild | Change to neutral defaults |
| `benchmarks.tsx` | No seed data; `data.missing` state is correctly gated | No | — |
| `HomeDashboard.tsx` | Renders `<CompoundingKPI />` which uses `--cf-success/danger/warning` — color invisible | Yes | Fix token references in component |
| `Projects.tsx` | No seed data; `var(--bad, #b1452f)` hex fallback is a style lie | Yes — wrong color | Remove hex fallback |
| `dashboard.tsx` | No seed data; "Estimated savings" card shows `"—"` when no sessions | Mild — dead card | Gate card behind `savings !== null` |
| `agents.tsx` | None | No | — |
| `optimizers.tsx` | None | No | — |
| `policies.tsx` | No seed data; compliance strip silently absent during load | Yes — silent omission | Add loading state for strip |
| `runtimes.tsx` | Test-result colors `--cf-success/danger` undefined — invisible signal | Yes | Replace with `--good` / `--bad` |
| `integrations.tsx` | None | No | — |

---

## Recommendations

1. **Fix `--cf-success` / `--cf-danger` / `--cf-warning` in `runtimes.tsx` immediately.** This is the most visible token bug — the "Test" button result (the primary interaction in that route) renders invisible color feedback. One-line fix per occurrence: `var(--good)` and `var(--bad)`.

2. **Strip `var(--bad, #b1452f)` hex fallbacks and `var(--line, #e5e1d8)` in `Projects.tsx`.** These are the only hardcoded hex values in the entire cluster. Removing the fallbacks forces the token system to be the single source of truth.

3. **Unify loading/error state patterns.** Pick `<EmptyState>` as the canonical pattern and migrate `Analytics.tsx` callout blocks. This is a 2–3 line change per site and makes the whole cluster read as one system.

4. **Add a `null` guard on the "Estimated savings" `StatCard` in `dashboard.tsx`.** Users with no transcripts running see a three-up grid with a dead `"—"` card — a subtle but real confusion about whether the product is working.

5. **Fix `HomeDashboard.tsx` greeting fallback.** `displayName ?? ""` causes `"Hello, !"`. One-char fix: `displayName || "there"`.

---

## Flow walkthrough note

A first-time user who has just opened the desktop app lands on `HomeDashboard` (greeted with "Welcome back, there." when no display name is set) and is directed to create a workspace. They navigate to Analytics and see three tabs — Dev, Product, Flow — where loading states now render as proper `<EmptyState>` spinners consistent with every other route, rather than bare unstyled divs that looked like rendering errors. After exploring analytics they check Runtimes to test their Claude Code connection: the Test button feedback now uses `var(--good)` / `var(--bad)` canonical tokens, so the green/red result signal is brand-contract-safe through Wave 5's shim deletion. Back on the Dashboard Overview, the "Estimated savings" card is suppressed until the transcripts service returns real aggregate data, so new users see a clean stat grid with only live values rather than a dead placeholder that implies the product isn't working.

*(Phase 2 execution note: all 5 P1 fixes shipped as atomic commits `f708d78`, `cc43ac8`, `cd09e13`, `8f262d2`, `fa30552`. Type-check remained at exit 0 throughout. P1 #1 rationale corrected per lead review — visibility bug reclassified as brand-contract/forward-compatibility issue.)*
