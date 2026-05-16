# Polish Rehaul Notes — pass 2

## Files refactored (9 files, ~700 LOC touched)

**Routes:** `Plan.tsx`, `Board.tsx`, `SessionDetail.tsx`, `policies.tsx`, `benchmarks.tsx`, `compare.tsx`, `Files.tsx`, `dashboard.tsx`, `Org.tsx`, `Analytics.tsx`
**Components:** `FlowGraph.tsx`, `Spot.tsx`

Key changes per file:
- **policies.tsx** — replaced hand-rolled `KPI()` component (4 tiles) with `<StatCard>`, replaced inline `savingMsg` color div with `<Message>`, replaced `<div className="cf-empty">` error/loading with `<EmptyState>` + spinner div, replaced hand-rolled chip spans with `<Badge>`, removed `fontSize`/`color` inline styles throughout.
- **benchmarks.tsx** — replaced hand-rolled `Stat()` + `HeroStrip` grid with `<StatCard>` row, replaced bare `<div className="cf-empty">` error with `<EmptyState>`, replaced inline `fontSize`/`color` spans with utility classes throughout `ScenarioBars`/`BarRow`/`OptimizerSection`/`FromYourSessions`.
- **compare.tsx** — replaced hand-rolled `SessionPicker` card with `<Card>`, replaced hand-rolled `Stat()` with `StatKV` using utility classes, replaced inline chip `style={{}}` in `SidePanelCard` with `<Badge>`, replaced table cell color inline styles with utility classes.
- **dashboard.tsx** — replaced local `SectionHeader` shadow with imported one from `@crawfish/ui`, replaced `Wizard` wrapper `style={{}}` with `cf-card`, replaced `Stepper` inline styles with utility classes, replaced `ReviewRow` inline styles with utility classes, replaced error `style={{color: "var(--cf-danger)"}}` with `<Message tone="error">`.
- **Files.tsx** — replaced hand-rolled "Pick a file" empty block with `<EmptyState>`, replaced `style={{color: "var(--cf-danger)"}}` file error with `<Message tone="error">`, replaced `fontFamily` literal string in textarea with `cf-mono`.
- **SessionDetail.tsx** / **Board.tsx** / **FlowGraph.tsx** — replaced bare `<div className="cf-empty">` error paths with `<EmptyState>`, cleaned `display:flex` rows with `cf-row`.

## Lens-vocab swaps (8 user-facing strings changed)

- `compare.tsx`: "lens unreachable" → "Transcripts service unreachable", "compare failed (lens reachable?)" → "Compare failed — is the transcripts service running?", callout detail updated.
- `benchmarks.tsx`: "open it in lens" → "open its transcript", fixture description removed "lens repo" reference.
- `dashboard.tsx`: "lens not running or no data" → "transcripts service not running or no data".
- `Org.tsx`: "lens online/offline" label → "transcripts online/offline", analytics description updated.
- `Analytics.tsx`: "lens unavailable" (×2) → "Transcripts service unavailable", "recorded by lens" → "from your transcripts".

## Coral residue removed (1 item)

- `Spot.tsx` comment: "a coral spark" → "an accent spark". No hex literals found.
- No hardcoded `#0e7490`/`#38bdf8` or other ocean-era hex in component files (confirmed by grep). All token references remain as `var(--cf-*)`.

## Build status

- `npx tsc --noEmit`: **zero errors**
- `npx vite build`: **success** (538 kB bundle, one expected chunk-size advisory)

## Playwright audit

All 7 routes at 1440×900 rendered without JS exceptions. 500 errors on `/workspaces`, `/sessions`, `/settings*` are backend API 500s (no DB state in sandbox) — not UI regressions. Screenshots saved to `docs/teams/polish-screenshots/`.

## Punted

- Mobile viewport screenshots — spec says desktop 1440×900 only, so none taken.
- `Org.tsx` route `/orgs/:id` — not visited because no live org ULID exists in sandbox DB; would 404 gracefully.
