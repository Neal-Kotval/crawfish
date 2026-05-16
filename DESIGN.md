# Crawfish Design System

The single source of truth for Crawfish UI. Every surface — the lens
session-detail view, the dash agent-org workplace, the onboarding wizard,
the Tauri desktop shell — pulls from the tokens, classes, and components
defined here.

If you are about to write `style={{...}}` for color, spacing, typography,
or a flex container, **stop and read this file first**. There is almost
always a class or component that does the job.

---

## 1 · Design philosophy

Crawfish is **local software with personality** — not a SaaS dashboard.
Four principles, applied in order:

1. **Ocean.** Light mode is pale sea-foam (`#f6f9fb`) with a deep teal
   accent (`#0e7490`) — the calm surface of the water. Dark mode is
   midnight navy (`#07182b`) with a bright cyan accent (`#38bdf8`) — the
   glow you see from below. The palette signals "calm, clear, deep,"
   appropriate for a tool that watches what your agents are doing.

2. **One door per concern.** The sidebar is four tabs: **Home** (what to
   do next), **Workspaces** (your orgs), **Sessions** (transcripts), and
   **Settings** (policies / agents / optimizers / about, sub-tabbed
   inside). A founder shouldn't have to scan seven tabs to find what
   they need; everything is reachable via Home suggestions or one click
   from the four primary doors.

3. **Suggestions over surfaces.** Home is state-aware: it shows the next
   likely action ("create your first workspace", "plan a cycle", "decide
   what your agents can do") instead of a wall of KPI tiles. New users
   are guided; daily-driver users pin recent workspaces and don't see
   suggestions they've dismissed.

4. **Component reuse, ruthlessly.** Every recurring pattern is a
   component. If you find yourself reaching for `style={{...}}`, look
   for the utility class first; if no utility, look for the primitive
   component; if no primitive, add one and update §5/§6 of this file.
   Inline styles are a tax, not a tool.

### Two modes

The same tokens render in two modes:

- **Dense (default)** — board, plan, sessions list, lens detail, kanban,
  graphs. 14px base, 1.5 line-height, tight letter-spacing, generous
  chips. Density signals "tool" and packs information without feeling
  cramped now that the base type is larger.

- **Warm** — wizards, empty states, the first-launch experience, any
  surface where the user is *meeting* the app for the first time.
  Larger headings, softer cards, more breathing room, friendlier
  microcopy. Apply by wrapping the surface in `<div className="cf-warm">`.
  Warm mode does NOT change the color palette — same coral, same warm
  neutrals — it just relaxes the rhythm.

### Anti-goals

- No marketing-site gradients, animated blobs, glassmorphism, or
  hero-section drama.
- No dark surface on light surface (vibrancy / glass) — flat, layered.
- No skeuomorphic chrome (no faux paper, no inner shadows on inputs).
- Dark mode is automatic via `@media (prefers-color-scheme: dark)`;
  there is no toggle. Component code only references variables.

---

## 2 · Where things live

```
ui/
├── tokens/
│   ├── globals.css       canonical stylesheet — variables, layout, every .cf-* class
│   └── design-tokens.ts  programmatic access (TS) to the same scale
├── components/           React primitives consumed via @crawfish/ui/components/<Name>
│   ├── Card.tsx          .cf-card frame + optional corner glyph
│   ├── StatCard.tsx      overview tile (kicker + value + sub)
│   ├── Badge.tsx         .cf-chip wrapper (variants + sizes)
│   ├── EmptyState.tsx    .cf-empty wrapper
│   ├── SectionHeader.tsx icon + title + sub + status
│   ├── Message.tsx       inline error/warn/hint/success
│   ├── Finding.tsx       diagnosis banner
│   ├── TokenBar.tsx      4-bucket token visualization + TokenLegend
│   └── CardCorner.tsx    decorative diagonal glyph
└── lib/format.ts         fmtCompact, fmtBytes, fmtMtime, copyToClipboard, …
```

Both `crawfish-dash/web` and `crawfish-lens/web` consume this through a
Vite alias `@crawfish/ui → ../../ui`. **Never copy a component into a
submodule — always import.**

The Tauri shell inherits the stylesheet at the webview boundary. There
is no per-platform CSS.

---

## 3 · Tokens

All tokens are CSS custom properties on `:root`. Dark mode flips them
inside the `@media (prefers-color-scheme: dark)` block. **Always
reference by name — never the underlying hex.**

### Surfaces (ocean scale)
| Variable             | Light      | Dark       | Use                              |
| -------------------- | ---------- | ---------- | -------------------------------- |
| `--cf-bg`            | #f6f9fb    | #07182b    | app background                   |
| `--cf-bg-elevated`   | #ffffff    | #102942    | cards, sheets, drawers           |
| `--cf-bg-sunken`     | #eaf1f5    | #04101e    | under cards, kanban troughs      |
| `--cf-bg-sidebar`    | #f6f9fb    | #07182b    | sidebar — matches app bg         |
| `--cf-bg-hover`      | rgba(…)    | rgba(…)    | row/button hover                 |
| `--cf-bg-selected`   | rgba(…)    | rgba(…)    | selected row                     |

### Foregrounds (deep navy ink → sea foam in dark)
`--cf-fg` (#0c1f2e / #e8f3f8) → `--cf-fg-secondary` → `--cf-fg-tertiary`
→ `--cf-fg-muted`. Use the utility class `.cf-fg-secondary` etc. rather
than applying the variable inline.

### Accent + semantic
- `--cf-accent` (#0e7490 light / #38bdf8 dark) — **deep teal in light,
  bright cyan in dark**. *One* accent, used sparingly. The single primary
  action per surface.
- `--cf-success` #047857 (sea green), `--cf-warning` #d97706 (harbor amber),
  `--cf-danger` #dc2626 — clearly separated from accent.
- Token-bucket colors `--cf-color-bucket-{input,output,cache-read,cache-write}`
  for the 4-bucket token visualization only.

### Status palette (workflow)
`--cf-status-{todo,progress,review,done}-{bg,fg}`. The `progress` state
intentionally reuses the accent (coral on coral-tinted bg) — workflow
status is the only place outside primary actions where accent appears.
`review` is violet (#6d28d9), `done` is emerald (#047857), `todo` is
neutral stone.

### Borders, radii, shadows
- `--cf-border` (#ece8e1 light / #3f3a36 dark) — warm soft border for
  default card and divider use.
- `--cf-border-strong` (#d6d0c7 / #57534e) — for inputs in focused state
  and dense table dividers.
- `--cf-radius-{sm,md,lg,xl}` = 4 / 8 / 10 / 14 px — bumped from the
  prior Jira-tight scale.
- `--cf-shadow-{sm,md,lg}` — soft shadows over a warm base. No
  pronounced corporate drop-shadow.

### Type
- `--cf-font`: Inter + system stack
- `--cf-font-mono`: SF Mono + Menlo stack
- Base body: **14px / 1.5**, letter-spacing -0.005em, ligatures on, tnum on
- Type scale (utility classes): xs 11 / sm 12 / base 13 / md 14 / lg 16 /
  xl 20 / 2xl 28 / 3xl 34

---

## 4 · Utility classes

Atomic helpers for the patterns that show up everywhere. The rule: **if
you reach for an inline style for one of these, use the utility
instead.**

### Layout
- `.cf-row` / `.cf-col` — flex row/column with default gap 8
- `.cf-row--between`, `.cf-row--end`, `.cf-row--start`, `.cf-row--baseline`, `.cf-row--wrap`
- `.cf-col--end` (align-items: flex-end)
- `.cf-gap-{1..6}` → 4, 8, 12, 16, 20, 24 px
- `.cf-grow` — flex: 1, min-width: 0 (truncation-safe)

### Type
- Sizes: `.cf-text-xs` (11) `.cf-text-sm` (12) `.cf-text-base` (13)
  `.cf-text-md` (14) `.cf-text-lg` (16) `.cf-text-xl` (20)
  `.cf-text-2xl` (28) `.cf-text-3xl` (34)
- Weight: `.cf-weight-medium`, `.cf-weight-semibold`
- `.cf-kicker` — small all-caps section label
- `.cf-mono` — monospace + tabular-nums
- `.cf-num` — tabular-nums only
- `.cf-truncate` — ellipsis + nowrap + min-width:0

### Color
- `.cf-fg`, `.cf-fg-secondary`, `.cf-fg-tertiary`, `.cf-fg-muted`
- `.cf-fg-accent`, `.cf-fg-success`, `.cf-fg-warning`, `.cf-fg-danger`

These exist exactly to kill `style={{ fontSize: 12, color: "var(--cf-fg-secondary)" }}`.

### Warm-mode helpers (only valid inside `.cf-warm`)
- `.cf-warm__hero`, `.cf-warm__hero-eyebrow` — wizard / first-encounter
  hero rhythm
- `.cf-coachmark`, `.cf-coachmark__title`, `.cf-coachmark__body`,
  `.cf-coachmark__actions`, `.cf-coachmark__cta`, `.cf-coachmark__dismiss`,
  `.cf-coachmark__arrow` — used by `<Coachmark>`

---

## 5 · Component primitives

Always prefer a component over reconstructing the markup. New shared
patterns get a component here, not a 4th inlined copy.

### `<Card>` — `@crawfish/ui/components/Card`
The base frame. Wraps `.cf-card`, handles `active` (accent border),
optional diagonal corner glyph. Use anywhere you'd otherwise hand-roll
a div with `background: var(--cf-bg-elevated); border; border-radius;
padding`.

### `<StatCard>` — `@crawfish/ui/components/StatCard`
Overview tile: kicker (icon + label), big value, optional sub. The
*only* sanctioned way to render a KPI tile.

### `<Badge>` — `@crawfish/ui/components/Badge`
Wraps `.cf-chip` with variants (`default | accent | success | warning |
danger | output | outline`) and sizes (`sm | md | lg`). Replace any
hand-rolled chip span with this.

### `<EmptyState>` — `@crawfish/ui/components/EmptyState`
`.cf-empty` + `.cf-empty__title`. Title + body + optional CTA children.
**Every dataless surface uses this** — no hand-rolled "Nothing to show"
divs.

### `<SectionHeader>` — `@crawfish/ui/components/SectionHeader`
Icon/emoji + title + optional sub + trailing status slot. Use at the top
of every panel/section instead of a custom flex row.

### `<Message tone="error|warn|hint|success">` — `@crawfish/ui/components/Message`
Inline status text. Replaces `<div style={{ color: "var(--cf-danger)", fontSize: 12 }}>`.

### `<FindingBanner>` — `@crawfish/ui/components/Finding`
Severity icon + title + detail + optional fix command. Used by the lens
diagnoses view.

### `<TokenBar>` and `<TokenLegend>` — `@crawfish/ui/components/TokenBar`
The canonical 4-bucket token visualization. **Never** reimplement this
inline — the bucket order, colors, and percentages are part of the brand.

### `<Coachmark>` — `crawfish-dash/web/src/components/Coachmark`
Floating pointer used by the first-run flow to highlight the next action
(e.g., "Your first task is on the Board"). Anchored to a DOM ref via
inline coordinates; dismissal flagged in wizard state. Lives in dash
because it's onboarding-specific.

### `<Suggestion>` — `@crawfish/ui/components/Suggestion`
The Home dashboard's primary unit. A row card with icon + title + body +
optional CTA + optional dismiss `×`. State-aware logic in
`crawfish-dash/web/src/routes/HomeDashboard.tsx` decides which
suggestions to surface based on org count, cycle presence, budget
breaches, etc. Dismissals persist in `localStorage` so a card doesn't
reappear once acknowledged.

---

## 6 · Compound classes (still in CSS, no component yet)

These behave like components but only via CSS. Add a React wrapper if you
find yourself repeating the markup more than twice.

- `.cf-app` / `.cf-sidebar` / `.cf-main` / `.cf-toolbar` / `.cf-content` — app shell grid
- `.cf-card` + `.cf-card__header` / `__title` / `__sub` / `__metrics` / `__active`
- `.cf-toggle` + `.cf-toggle__btn` / `--active` — segmented control
- `.cf-tabs` + `.cf-tab` / `--active`
- `.cf-table` / `.cf-tool-table` — dense data tables (tnum, right-aligned numerics)
- `.cf-status--{todo,progress,review,done}` — workflow pills
- `.cf-btn` (default | `--primary` | `--ghost`) and `.cf-pill` (default | `--primary`)
- `.cf-drawer` + `.cf-drawer-backdrop` — slide-over panels
- `.cf-md` — markdown rendering scope (used in agent output, diagnoses)
- `.cf-graph-*` — topology canvas, edges, nodes, overlays
- `.cf-board`, `.cf-kanban-column`, `.cf-task-card` — workflow board
- `.cf-files`, `.cf-file-tree`, `.cf-file-viewer` — file browser
- `.cf-org`, `.cf-org-list`, `.cf-members`, `.cf-avatar` — agent-org surfaces
- `.cf-activity`, `.cf-comment`, `.cf-composer`, `.cf-mention-popup`,
  `.cf-watchers` — activity feed + comments + mentions
- `.cf-warm` — warm-mode scope (see §1)

---

## 7 · Authoring rules

These are not stylistic preferences. Violations create drift that
compounds.

1. **No literal colors in app code.** Never `#xxxxxx` or `rgb(...)`
   outside `ui/tokens/`. If a color is missing, add it to the token set
   first.
2. **No raw px for radii or shadows in app code.** Use the variables.
3. **No `fontFamily` strings outside tokens.** Use `.cf-mono` or inherit.
4. **No `fontSize` numbers in component code.** Use a `.cf-text-*` class.
5. **No `display: flex` inline styles for trivial rows/columns.** Use
   `.cf-row` / `.cf-col` / `.cf-gap-N`. Inline flex is acceptable only
   for non-reusable, structurally unique layouts.
6. **No new component-scoped CSS files.** Everything lives in
   `ui/tokens/globals.css`. Per-component CSS produces specificity wars
   and copies of the same tokens.
7. **Dark mode is not optional.** Every new color must have both a light
   and dark token value. If you reference `--cf-bg-elevated` you get
   dark mode for free; if you hardcode `#fff` you do not.
8. **The bucket colors are reserved.** `--cf-color-bucket-*` exists only
   for token visualizations. Don't reuse them for unrelated UI.
9. **The accent is scarce.** One primary action per surface. Hover/focus
   rings use `--cf-accent-subtle`, not the full accent.
10. **Empty states use `<EmptyState>`.** Never `<div className="cf-empty">`
    hand-rolled — even though the class works, the component owns the
    rhythm and microcopy slot.
11. **KPI tiles use `<StatCard>`.** Never hand-rolled value+label divs.

### Allowed inline style

You may still use `style={{}}` for:
- Computed values (a width derived from data, a transform from a layout
  algorithm, a percent in a progress bar)
- One-off structural CSS that won't repeat (a specific
  `grid-template-columns` for a unique screen)
- `margin-left: auto` style spacers that don't deserve a utility

When in doubt: if the same `style={{}}` appears in two files, it should
be a utility class.

---

## 8 · Adding to the system

**A new color, radius, or shadow** → edit `ui/tokens/globals.css` (both
light `:root` and the dark `@media` block) and add a TS entry in
`design-tokens.ts` if it should be programmatically reachable.

**A new utility class** → append to the "Utility classes" section at the
bottom of `globals.css`. Keep the name `.cf-<concept>-<modifier>`.
Document in this file under §4.

**A new component** → drop `ui/components/<Name>.tsx`. Use only existing
tokens and `.cf-*` classes inside it. Import with
`@crawfish/ui/components/<Name>`. Document in this file under §5.

**A new compound class with no React** → add to `globals.css` under the
appropriate section; document under §6.

The CLAUDE.md ownership rules still apply: `globals.css` is a
registry-like file, so cross-cutting additions are **lead-only** when
running in agent-team mode. Teammates request the addition rather than
racing on it.

---

## 9 · Microcopy

Plain English everywhere. Stop the codey/Jira/imperative voice on
user-facing surfaces.

| Don't                                | Do                                               |
| ------------------------------------ | ------------------------------------------------ |
| "Configure org policy"               | "Decide how your team works — 30 seconds"        |
| "policy_violation"                   | "Couldn't start — this week's token budget is full" |
| "Token budget exhausted"             | "You've used this week's token budget"           |
| "Click to instantiate org template"  | "Create your workspace"                          |
| "No findings"                        | "Nothing to flag — you're in good shape"         |
| "session_id" / raw ULIDs in user UI  | the session's project name + first few hex chars |

All onboarding + empty-state + error-envelope strings live in
`crawfish-dash/web/src/wizards/shared/copy.ts`. Server error codes
(`policy_violation`, `path_escape`, `too_large`, etc.) have plain-English
translations in `friendlyError()` in the same file — **render the
friendly string, never the raw code**.

---

## 10 · Reuse expectations per surface

To keep the apps visually identical, certain features must use the listed
shared primitives. Treat this as the contract — diverging requires a
DESIGN.md change first.

| Feature                            | Required primitives |
| ---------------------------------- | ------------------- |
| Session list (lens detail + dash)  | `Card`, `Badge`, `TokenBar`, `EmptyState` |
| Overview tiles / KPIs              | `StatCard` (always — no hand-rolled tiles) |
| Diagnoses & findings               | `FindingBanner`     |
| Empty data states                  | `EmptyState` (always — never bare `.cf-empty`) |
| Inline errors/hints                | `Message`           |
| Section headers (panels, wizards)  | `SectionHeader`     |
| Token visualizations               | `TokenBar` + `TokenLegend` (never custom) |
| Status (workflow)                  | `.cf-status--*` classes |
| Tag/label chips                    | `Badge`             |
| Cards in general                   | `Card` (never raw `div` with card styling) |
| First-launch / wizards             | `<div className="cf-warm">` wrapper + `WizardLayout` |
| Onboarding pointer                 | `<Coachmark>`       |

---

## 11 · Quick lookup — "what should I use for…?"

| You want…                                | Use                                          |
| ---------------------------------------- | -------------------------------------------- |
| A flex row with gap                      | `<div className="cf-row cf-gap-3">`          |
| A vertical stack                         | `<div className="cf-col cf-gap-2">`          |
| Secondary gray text                      | `<span className="cf-text-sm cf-fg-secondary">` |
| A tabular number                         | `<span className="cf-num">`                  |
| A code snippet                           | `<code>` (inherits) or `.cf-mono`            |
| A status chip                            | `<Badge variant="success">Done</Badge>`      |
| A page-level "no data" block             | `<EmptyState title="…">…</EmptyState>`       |
| An inline error message                  | `<Message tone="error">…</Message>`          |
| A panel header                           | `<SectionHeader icon="🦀" title="…" />`      |
| A card-shaped container                  | `<Card>…</Card>`                             |
| A KPI tile                               | `<StatCard label=… value=… />`               |
| An onboarding-tier surface               | `<div className="cf-warm">…</div>`           |
| A floating "do this next" pointer        | `<Coachmark>`                                |

If your "you want" isn't in this table and you can't find it in §4–6,
that is a signal to extend the design system, not to bypass it.
