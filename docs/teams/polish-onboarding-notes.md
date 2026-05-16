# Polish & Onboarding — Implementation Notes

## Workstream 1 — Guided first-run wizard (onboarding teammate)

Replaced the existing token-scan first-run wizard with a 4-step guided onboarding flow per the approved plan. All microcopy sourced exclusively from `wizards/shared/copy.ts`. All layout uses `.cf-warm` + DESIGN.md primitives — no inline color, spacing, or typography.

**Files created or modified:**

- `crawfish-dash/web/src/wizards/first-run/steps/profile.tsx` — Step 1. Collects display name (required) and email (optional). Persists `profile` to wizard state via `writeWizardState`.
- `crawfish-dash/web/src/wizards/first-run/steps/template.tsx` — Step 2. Fetches `GET /api/templates`, renders each as a clickable `<Card>`. Passes selected slug up to orchestrator.
- `crawfish-dash/web/src/wizards/first-run/steps/org.tsx` — Step 3. Auto-suggests `${displayName}'s workspace`. Calls `POST /api/templates/:slug/instantiate` on submit and captures `org_id`.
- `crawfish-dash/web/src/wizards/first-run/steps/seed.tsx` — Step 4. Calls `POST /api/orgs/:id/cycles` then `POST /api/orgs/:id/board` (task_created event). On success writes `completedAt`, `done.firstRun: true`, and navigates to `/orgs/:orgId`.
- `crawfish-dash/web/src/wizards/first-run/index.tsx` — Full rewrite. 4-step orchestrator that threads slug and orgId through steps. Uses existing `<WizardLayout>` with step/total counters.
- `crawfish-dash/web/src/components/Coachmark.tsx` — New component. Positions itself next to an anchor ref using `getBoundingClientRect`. Uses `.cf-coachmark*` classes from globals.css. Dismiss writes `firstRunCoachmarkSeen: true`.
- `crawfish-dash/web/src/main.tsx` — Added `HomeOrOnboarding` component: redirects `/` to `/wizard/first-run` if `!isOnboarded()`.
- `crawfish-dash/web/src/App.tsx` — Added `showCoachmark` logic reading `firstOrgId` and `firstRunCoachmarkSeen`. Renders `<Coachmark>` anchored to the Plan (kanban) nav item after onboarding completes.

**Type check:** `npx tsc --noEmit -p tsconfig.json` passes clean in `crawfish-dash/web`.

**Coordinate with lens-fold:** Did not touch `crawfish-dash/web/src/routes/sessions*`. Route `/sessions/:id` addition to main.tsx is deferred to lens-fold teammate per instructions.

## Workstream 3 — Fold lens session-detail into dash (lens-fold teammate)

Lifted the session-detail view from `crawfish-lens/web/` into `crawfish-dash/web/` so clicking a session card in `/sessions` navigates to `/sessions/:id` inside the dash shell — no port jump to 7878.

**Files created:**

- `crawfish-dash/web/src/lib/sessionDetail.ts` — Typed fetch helpers (`fetchSessionDetail`, `fetchSessionSavings`, `fetchSessionGraph`, `useSessionEvents`) plus all required TypeScript types lifted from lens. All fetch paths route through the dash proxy at `/api/lens/*` (see `crawfish-dash/src/server.ts` §Lens proxy).
- `crawfish-dash/web/src/components/session/Timeline.tsx` — Lifted from lens; fetch updated to `/api/lens/sessions/:id/timeline`.
- `crawfish-dash/web/src/components/session/Topology.tsx` — Lifted from lens; uses `fetchSessionGraph` from `sessionDetail.ts`.
- `crawfish-dash/web/src/components/session/Savings.tsx` — Lifted from lens; uses `fetchSessionSavings` from `sessionDetail.ts`.
- `crawfish-dash/web/src/routes/SessionDetail.tsx` — Top-level detail route; reads `:id` via `useParams`, renders Timeline / Topology / Savings inside dash's shell. Back link goes to `/sessions`.

**Files modified:**

- `crawfish-dash/web/src/routes/sessions.tsx` — Replaced external `<a href="http://127.0.0.1:7878/session/:id">` with `<Link to="/sessions/:id">`. Removed "Open lens →" external anchor. Replaced the raw shell-command callout with a disabled `<button>Start lens</button>` (tooltip explains; TODO left for POST /api/lens/start endpoint).
- `crawfish-dash/web/src/main.tsx` — Added `import { SessionDetail }` and `<Route path="/sessions/:id" element={<SessionDetail />}/>` after the `/sessions` route. Coordinated with onboarding teammate before editing.

**Invariants preserved:** `crawfish-lens/web/` is untouched — lens binary still works standalone at port 7878. `ui/tokens/globals.css` not touched.

**Type check:** `npx tsc --noEmit -p tsconfig.json` passes clean in `crawfish-dash/web`.
