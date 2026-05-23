---
name: Crawfish
description: Warm paper, vermillion accent, three typefaces, three surfaces — the studio for agent organizations.
colors:
  paper: "#f5f1e8"
  paper-2: "#ede7d6"
  surface: "#fbf8f1"
  surface-2: "#ffffff"
  surface-3: "#fdfaf2"
  ink: "#1a1a18"
  ink-soft: "#3a3a35"
  ink-mute: "#6f6b62"
  ink-faint: "#a09b8f"
  accent: "#c8442b"
  accent-hover: "#a83723"
  accent-soft: "#f3d6cb"
  accent-tint: "#fae8e0"
  good: "#2f7a4d"
  warn: "#b8862c"
  danger: "#b53224"
fonts:
  sans: "Geist"
  display: "Space Grotesk"
  mono: "JetBrains Mono"
reference: design/Crawfish - Hi-Fi Designs.html
---

# Crawfish — design system

Warm paper. Vermillion accent. Three typefaces. Three surfaces. One stack
of tokens shared across the marketing site (`crawfish-web/`), the desktop
studio (`crawfish-dash/` + `crawfish-app/`), and the CLI's ASCII-TUI when
rendered in a terminal that supports color.

The canonical visual reference is the hi-fi artboard in
`/design/Crawfish - Hi-Fi Designs.html`. When this document and the
artboard disagree, the artboard wins — update this file.

---

## 1 · Brand

**Warm paper, warm ink, one accent.** The surface is `#f5f1e8` — a cream
that is unmistakably *not* white. The ink is `#1a1a18` — a warm near-black
that reads as bookish rather than corporate. The single accent is
`#c8442b`, a vermillion that does the job a Jira blue would in a tool-
chain product but reads as a craft object instead of an enterprise dashboard.

**Why warm-paper.** Crawfish runs forever — agents work overnight, the
dash stays open for days. Cool blues make tired eyes tireder. Warm paper
is the same trick newspaper print uses. It also distinguishes us
visually from every other AI-for-developers tool, which uniformly defaults
to dark mode with neon accents.

**Why vermillion.** It's the color of a cooked crawfish. It also reads as
*action* — every "open PR", "hire agent", "apply fix" surface uses it.

**Why three typefaces.**
- **Geist** for body and UI copy — a geometric grotesk by Vercel, distinctive
  without being eccentric.
- **Space Grotesk** for display (heroes, page titles, agent names) — bigger
  personality, tighter tracking, used at 28–76px.
- **JetBrains Mono** for eyebrows, ticket IDs (`CRWF-118`), timestamps,
  token counts, code, and live traces. This is the typeface that says
  "we came from the CLI."

Instrument Serif has been **retired**. If you see `.cf-serif` in the
codebase, it now resolves to Space Grotesk.

**Dark mode — warm-dark.** Warm paper is the brand baseline and the
marketing site stays light; the **signed-in apps (dash + platform) default
to a *warm*-dark theme** (users can switch back to light in Settings →
Appearance). The dark theme uses espresso-paper backgrounds (`--paper: #1b1916`) with the vermillion
accent brightened a step (`--accent: #e35a3c`) so it stays legible on dark.
It is not a cool-neutral inversion — warming the ink and paper is still the
design point, at night too. Users switch via **Settings → Appearance**; the
choice persists in `localStorage` (`cf-theme`) and is applied as
`data-theme="dark"` on `<html>`. The dark token block in
`ui/tokens/globals.css` (`:root[data-theme="dark"]`) overrides the base
`--paper`/`--ink`/`--accent` tokens, so the whole `--cf-*` shim follows.
The apps default to dark; the marketing site is unaffected.
(This reverses the earlier "warm-paper-only, dark is a no-op" stance.)

**No glassmorphism, no neon, no gradient washes.** The body background
is solid `--paper`. Elevation comes from low-opacity neutral shadows
(`--shadow-sm/md/lg`) and 1px rules (`--rule`).

---

## 2 · Tokens

Canonical definitions live in `ui/tokens/globals.css` (the `:root` block).
Every token is a CSS variable. **Always reference the var, never the hex.**

### 2.1 Surfaces

| Token         | Hex          | Use                                              |
|---------------|--------------|--------------------------------------------------|
| `--paper`     | `#f5f1e8`    | Page background, canvas surface                  |
| `--paper-2`   | `#ede7d6`    | Sunken backgrounds (kanban troughs, badges)      |
| `--surface`   | `#fbf8f1`    | Subtle elevation (info strips, hover wells)      |
| `--surface-2` | `#ffffff`    | Cards, sheets, drawers, install cards            |
| `--surface-3` | `#fdfaf2`    | Chrome (titlebar, sidebar, right rail)           |

### 2.2 Ink

| Token         | Hex          | Use                                              |
|---------------|--------------|--------------------------------------------------|
| `--ink`       | `#1a1a18`    | Primary text, hero "you" / ink-on-paper elements |
| `--ink-soft`  | `#3a3a35`    | Secondary text, meta                             |
| `--ink-mute`  | `#6f6b62`    | Eyebrows, captions, tertiary text                |
| `--ink-faint` | `#a09b8f`    | Timestamps, disabled, faintest meta              |

### 2.3 Rules

| Token       | Value                       | Use                              |
|-------------|-----------------------------|----------------------------------|
| `--rule`    | `rgba(26,26,24,0.10)`       | Default 1px border               |
| `--rule-2`  | `rgba(26,26,24,0.06)`       | Faint inner divider              |
| `--rule-3`  | `rgba(26,26,24,0.18)`       | Strong border (buttons, hover)   |

### 2.4 Accent (vermillion)

| Token            | Hex          | Use                                       |
|------------------|--------------|-------------------------------------------|
| `--accent`       | `#c8442b`    | Primary CTAs, active routes, live status  |
| `--accent-hover` | `#a83723`    | Hover/pressed state                       |
| `--accent-soft`  | `#f3d6cb`    | Borders on accent-tinted surfaces         |
| `--accent-tint`  | `#fae8e0`    | Subtle accent fills (selection, hover)    |

### 2.5 Semantic

| Token       | Hex       | Use                          |
|-------------|-----------|------------------------------|
| `--good`    | `#2f7a4d` | Success FG (ready, opened)   |
| `--good-bg` | `#d8e8de` | Success BG (chips, progress) |
| `--warn`    | `#b8862c` | Warning FG                   |
| `--warn-bg` | `#f3e6c4` | Warning BG                   |
| `--danger`  | `#b53224` | Destructive (stop, refund)   |

### 2.6 Surface chrome

| Token         | Value                                                            |
|---------------|------------------------------------------------------------------|
| `--shadow-sm` | `0 1px 0 rgba(26,26,24,0.04), 0 1px 2px rgba(26,26,24,0.04)`     |
| `--shadow-md` | `0 1px 0 rgba(26,26,24,0.04), 0 4px 12px rgba(26,26,24,0.06)`    |
| `--shadow-lg` | `0 1px 0 rgba(26,26,24,0.04), 0 12px 32px rgba(26,26,24,0.08)`   |
| `--r-xs`      | `4px`                                                            |
| `--r-sm`      | `6px`                                                            |
| `--r-md`      | `8px`                                                            |
| `--r-lg`      | `12px`                                                           |
| `--r-xl`      | `16px`                                                           |

### 2.7 Type families

| Token           | Value                                                                |
|-----------------|----------------------------------------------------------------------|
| `--ff-sans`     | `"Geist", -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui`  |
| `--ff-display`  | `"Space Grotesk", "Geist", ...`                                      |
| `--ff-mono`     | `"JetBrains Mono", ui-monospace, "SF Mono", Menlo, Consolas`         |

### 2.8 Legacy `--cf-*` shim

The block at the bottom of `:root` aliases every retired `--cf-bg`,
`--cf-fg`, `--cf-accent`, `--cf-radius-md`, etc. to its closest warm-paper
equivalent. **Do not write new code against `--cf-*`.** It exists only so
the 3000+ lines of legacy utility classes (`.cf-card`, `.cf-sidebar__item`,
`.cf-pill`, etc.) compile during the migration. Wave 5 deletes the shim.

---

## 3 · Type scale

| Role        | Family         | Size  | Weight | Tracking   | Example use                          |
|-------------|----------------|-------|--------|------------|--------------------------------------|
| Hero        | Space Grotesk  | 76    | 500    | `-0.035em` | `crawfish.dev/` headline             |
| Display     | Space Grotesk  | 36    | 500    | `-0.028em` | Install-card titles, page heroes     |
| Title       | Space Grotesk  | 24–34 | 500    | `-0.025em` | Section heads, dialog titles         |
| Subtitle    | Geist          | 18    | 400    | `-0.005em` | Lede paragraphs                      |
| Body        | Geist          | 14    | 400    | `-0.005em` | Default text                         |
| Small       | Geist          | 12–13 | 400    | `-0.003em` | Meta, table cells                    |
| Eyebrow     | JetBrains Mono | 11    | 500    | `+0.12em`  | `.cf-eyebrow` (`UPPERCASE LABELS`)   |
| Mono inline | JetBrains Mono | 11–13 | 400    | `0`        | `repo-map.json`, `CRWF-118`, `$0.14` |
| Numerics    | Geist + tnum   | varies| 500    | `-0.01em`  | Big stat numbers (add `.cf-num`)     |

Display headlines: always tighten tracking. Body: `-0.005em`. Mono and
eyebrow: never italicize. **Numerics on any number-looking element get
`.cf-num`** (`font-variant-numeric: tabular-nums`).

---

## 4 · Surface conventions

| Surface           | Background      | Border           | Purpose                                                |
|-------------------|-----------------|------------------|--------------------------------------------------------|
| Page canvas       | `--paper`       | none             | The main content stage (dash canvas, marketing hero)   |
| Chrome            | `--surface-3`   | `--rule`         | Titlebar, sidebar, right rail                          |
| Card              | `--surface-2`   | `--rule-3`       | Install cards, agent cards, drawers                    |
| Sunken well       | `--paper-2`     | `--rule`         | Progress-bar tracks, kanban troughs, hover wells       |
| Accent surface    | `--accent`      | `--accent`       | Primary CTAs, "live" state pills                       |
| Ink surface       | `--ink`         | `--ink`          | The "you" node, primary download button, dark CLI block|
| Accent-tint card  | `--accent-tint` | `--accent-soft`  | Diagnosis cards, inline accent hints                   |

Always 1px borders. Always low-elevation shadows. Never `backdrop-filter`.

---

## 5 · Component primitives

Lives in `ui/components/`. Each one is a typed React component exported
via `@crawfish/ui`. Build new screens out of these — don't reach for
inline styles.

| Primitive       | Purpose                                                                 |
|-----------------|-------------------------------------------------------------------------|
| `Pill`          | Status badge (neutral/accent/good/warn/danger/ink tones)                |
| `Eyebrow`       | Mono uppercase label (`.cf-eyebrow` typed wrapper)                      |
| `Tab` / `Tabs`  | Underline-active tabs with optional count badge                         |
| `SideItem`      | Sidebar nav row (icon + label + badge + sub variant)                    |
| `StatCard`      | Eyebrow + big number + bar + delta                                      |
| `TaskRow`       | Status dot, title, ticket id, progress, token cost                      |
| `Node`          | Canvas node (you / accent / neutral / idle variants)                    |
| `Icon`          | 16px stroke-1.6 SVG set (canvas, board, sessions, etc.)                 |
| `TitleBar`      | Tauri titlebar (traffic lights, org switcher, ⌘K, meters, bell, avatar) |
| `Button`        | Primary (vermillion), secondary (paper), ghost                          |
| `Toolbar`       | Top-of-pane action strip                                                |
| `Avatar`        | Round, warm-palette, initial-based                                      |
| `IconDisc`      | Circular icon container                                                 |
| `KPI`           | Compact stat (number + delta)                                           |
| `Switch`        | Toggle                                                                  |
| `Segmented`     | Segmented control                                                       |
| `Card`          | Plain `--surface-2` container                                           |
| `Empty`         | Empty state (illustration + title + body + CTA)                         |
| `DiagnosisCard` | Accent-tint card with title + fix CTA                                   |
| `TokenBar`      | Stacked horizontal bar for token bucket usage                           |
| `InstallCard`*  | Marketing-only: install picker card                                     |
| `PlatBtn`*      | Marketing-only: platform-specific download button                       |
| `NavLink`*      | Marketing-only: underline-on-active nav link                            |

`*` = `ui/components/marketing/`.

**Retired** (replaced or deleted): `GlassPanel`, `Finding`, `Suggestion`,
`Message`. `StatCard` and `Icon` have been rewritten in place.

---

## 6 · Three-surface IA

Crawfish is one product on three surfaces. Each surface owns a different
job; the data on disk is shared (the `acme-co/` org folder is the source
of truth, edited by all three).

### 6.1 Web (`crawfish-web/`, deploys to crawfish.dev)

The **front door**. Routes: `/` (install picker), `/onboarding/*` (the
21-step founder flow), `/product`, `/templates`, `/docs`, `/pricing`,
`/roadmap`, `/signin`, `/create-org`, `/team`. Width: 1440 (designed),
fluid down to 1280. Mobile: read-only — install picker collapses, no
app surfaces.

### 6.2 Dash (`crawfish-dash/web/` + `crawfish-app/`, Tauri desktop)

The **studio**. Routes: `/canvas` (org canvas), `/board`, `/sessions` /
`/sessions/:id`, `/knowledge`, `/diagnoses`, `/agents/:id` (agent canvas),
`/skills`, `/settings/*`. Window: 1280×820. Tauri titlebar **hidden**;
the `TitleBar` component owns the chrome (traffic lights, org switcher,
search, meters, avatar).

Sidebar (232px) → main canvas → right rail (304px). The 5-item sidebar:

```
Workspace        Members           Footer
─ Canvas (●)     ─ You · founder    ─ Skills · 12
─ Board (3)      ─ Pat              ─ Settings
─ Sessions (2)   ─ Eng-bot          ─ [Diagnosis card]
─ Knowledge      ─ Designer-bot
─ Diagnoses (1)  ─ Support-bot
```

### 6.3 CLI (`crawfish-orgctl`, ASCII TUI)

The **scriptable engine**. Same data, no GUI. Ships the `orgctl` MCP
server. Color in the TUI maps to the same tokens (accent → ANSI 166,
good → 28, warn → 136, danger → 124).

---

## 7 · Motion

Use sparingly. The system is mostly still — motion calls attention to
*change* (a token flowing, a PR opening) not to *presence*.

| Pattern              | When                                                            |
|----------------------|-----------------------------------------------------------------|
| Marching ants        | Active canvas edges (`stroke-dasharray` animation, 2.4s loop)   |
| Blink cursor         | Live trace "working" indicator (`@keyframes cf-blink` 1s steps) |
| Fade-in              | Agent nodes appearing on first launch                           |
| Bar fill             | Budget bars, progress bars (`width` transition 320ms `ease`)    |
| Hover lift           | Cards: `translateY(-1px)` (90–140ms)                            |
| Token-flow chip      | Floating pill on active edge: appears, fades 2s                 |

No bouncing. No parallax. No skeleton shimmer (use static `--paper-2`
fills with the eyebrow "loading" instead).

---

## 8 · Authoring rules

- **CSS lives in `ui/tokens/globals.css` only.** No component-scoped
  `.css` files. Add a class to `globals.css`, then reference it from JSX.
- **Inline `style={{...}}` is allowed for one-off positions** (canvas node
  coordinates, hero margins). Anything that recurs gets a class.
- **Never write a new `--cf-*` variable.** Use the new `--paper / --ink /
  --accent / etc.` namespace.
- **Number-looking text gets `.cf-num`.** Mono text gets `.cf-mono`.
  Eyebrows get `.cf-eyebrow`.
- **Pixel-snap.** All borders 1px, all radii from `--r-*`, all spacing on
  the 4px grid. No `1.5px` borders, no `5px` paddings.
- **Verify against `/design/Crawfish - Hi-Fi Designs.html`** before
  shipping a UI change. If your screen does not match the artboard's
  vocabulary, the screen is wrong.
