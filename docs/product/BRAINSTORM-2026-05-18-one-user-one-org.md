# Brainstorm — One user, one org, projects everywhere (2026-05-18)

> Re-evaluating the user flow. We're collapsing the "Pick an org" + device-link
> dance for the v0 product. One user has exactly one workspace; projects live
> under it; the platform is the cloud mirror; the dash is the working surface.

## What this changes

### Before (today)
- Sign in → Pick an org (or onboard to create one) → Pick a project (in dash).
- Multi-org grids on platform and dash.
- Device-link per org per device with verify-URL popup.
- Anti-squat in `POST /api/device-link` blocks re-link of claimed orgs.
- "Org isn't online" empty state surfaces whenever the local dash doesn't yet
  have a per-org token.

### After (this brainstorm)
- Sign in → see **your projects** and the **install Dash + install CLI** CTAs.
- One implicit workspace per user, auto-created on signup. The "org" data model
  stays in the DB for future multi-tenant, but it's invisible to the user.
- Dash auths to the platform **once per device, as the user** (Clerk JWT in
  prod, X-User-Id shim in dev). After that, all org/project data flows from
  the platform via that user bearer.
- Dash sidebar's Projects tab becomes the primary surface. **Three ways to
  add a project:** open local · create · import from GitHub.
- Filesystem watcher in dash: any folder with `.crawfish/index.json` shows
  up as a local project automatically.

## Surface-by-surface

### Platform (`cloud/platform`)
- `/` → **Dashboard** (not OrgPicker):
  - Hero: "Welcome back, {name}." with avatar.
  - Two install cards side-by-side: **Install Dash** (download) and **Install CLI** (`brew install crawfish` / `curl install`).
  - Below: your projects list, mirroring what dash sees, with status pills
    (local / cloned / cloning).
  - Each project row → "Open in Dash →" link (deep-link).
- `/onboarding/*` → trim to "Install Dash + Install CLI + you're done." No
  team-name / team-size / agent-preview steps. The org is already created by
  the time the user lands here.
- `/orgs/:org/*` routes → still mounted (back-compat for the demo orgs already
  in the DB). The sidebar's org switcher hides when the user has exactly one
  org. New users only ever see their own.
- `Shell.tsx` sidebar:
  - Drop "Your orgs" eyebrow + multi-org list when user has one org.
  - "Workspace" eyebrow + nav items (Canvas, Projects, Team, Settings).

### CLI (`cli/projectctl`, alias `craw`)
- `craw init` (already shipped) — scaffold `.crawfish/` in the current dir.
- (Future) `craw login` — opens a browser to the platform, completes auth,
  drops a bearer at `~/.crawfish/auth.json`. Used by dash and the CLI both.
- (Future) `craw new <name>` — `mkdir + cd + craw init` in one step.

### Dash (`desktop/dash`)
- **Login screen** on first launch: button that opens
  `<platform>/dash-link?device=<id>` in the user's browser. Platform redirects
  back to `crawfish-dash://link?token=<jwt>` (custom URL scheme handled by
  Tauri). The token is the user's bearer; persist at
  `~/.crawfish/auth.json`. **One token per device, not per org.**
- After login: dash bootstraps the user's workspace from the platform once
  (`GET /api/me/workspace`), writes `~/crawfish/`.
- Sidebar nav:
  - Canvas · Board · Sessions · Knowledge · Diagnoses (unchanged).
  - **Projects** is now the landing route (replaces Canvas as `/`).
  - Settings · Account.
- Projects route shows your projects list. At top, three buttons:
  - **Open locally** → file-picker → if folder has `.crawfish/`, adopt as-is;
    else offer to `craw init` it.
  - **Create** → file-picker (parent dir) + name → `mkdir` + `craw init` +
    POST adopt-local to platform.
  - **Import from GitHub** → existing GH clone path.
- Filesystem watcher (`chokidar` on `~/`) → discovers any new `.crawfish/`
  folder → registers as local project under the user's workspace.

### CLI ↔ Dash ↔ Platform sync
- The dash backend is the only direct caller of platform API (in dev). It
  forwards `X-User-Id: <user>` (dev) or `Authorization: Bearer <token>` (prod
  Clerk).
- The CLI talks to the dash backend on `127.0.0.1:7880` for project registry
  reads. (Future: it can talk to platform directly via `~/.crawfish/auth.json`.)
- Dash polls `GET /api/me/workspace?since=<ts>` every 30s for changes.

## Data model changes (minimal)

The `Org` model stays — we just hide it. Two add-ons:

```prisma
model User {
  // …existing fields…
  primaryOrgId String? @unique // pointer to the user's auto-created workspace
}
```

Auto-create logic, server side, on first user materialization (`ensureDevUser`
for dev, Clerk-upsert path for prod):

```ts
if (!user.primaryOrgId) {
  const slug = sanitize(user.email.split("@")[0]) || "workspace";
  const org = await db.org.create({
    data: {
      name: uniqueSlug(slug),       // append -2, -3 on collision
      teamSize: "Just me",
      primaryClient: "Dash",
      members: { create: { userId: user.id, role: "founder" } },
      agents: { create: DEFAULT_AGENTS },
    },
  });
  await db.user.update({ where: { id: user.id }, data: { primaryOrgId: org.id } });
}
```

(`DEFAULT_AGENTS` already exists; same set as today's onboarding stamps.)

## What goes away

Code paths to retire (not delete this round; just stop reaching):
- `OrgPicker.tsx` — replaced by `Dashboard.tsx`.
- `OnboardingFlow.tsx` welcome / propose / install steps (just retain handoff
  as "install Dash" if needed).
- `OnlineLink` device-link UI in dash (replaced by once-per-device login).
- `POST /api/device-link` anti-squat path (becomes irrelevant; orgs aren't
  user-creatable from outside the platform anymore).

## Decisions captured

- **One user, one org. Confirmed.**
- **Drop device-link's per-org gating. Dash auths as the user, once per device.** Confirmed.
- The Org data model isn't dropped (future multi-tenant survives), just made invisible.
- Pre-existing demo orgs (`alby`, `audit-org`, `playwright-demo`) keep working — multi-org sidebar shows when a user has >1 org, so we don't break test accounts.

## Implementation slices (each shippable independently)

1. **Server: auto-create org on user materialization + add `primaryOrgId`.** Prisma migration + `ensureDevUser` + Clerk upsert path. Existing users get a primary org backfilled on next sign-in if missing. ~80 LOC.
2. **Platform: `Dashboard.tsx` replaces OrgPicker at `/`.** Hero, two install cards, projects list pulling from `primaryOrgId`. ~150 LOC.
3. **Platform: simplify onboarding to install screen only.** Trim 3 of the 5 steps. ~50 LOC.
4. **Platform: hide multi-org sidebar when user has one org.** Conditional render in `Shell.tsx`. ~10 LOC.
5. **Dash: user-bearer auth replacing device-link.** New `crawfish-dash://link?token=` URL scheme handler + `~/.crawfish/auth.json` writer + dash backend forwards `Authorization: Bearer` to platform. ~120 LOC.
6. **Dash: three Projects buttons (Open / Create / GitHub) + Tauri file-picker integration.** ~200 LOC.
7. **Dash: `.crawfish/` filesystem watcher → auto-register projects.** ~80 LOC.

Slices 1–4 are platform-only, low-risk, immediate UX win. 5–7 require Tauri-side work and are the bigger lift.

## Out of scope (for this brainstorm)

- Multi-tenant / org invites / role management (the Org model stays in case
  we want this later, but no UI for it).
- Multi-device per-user conflict resolution.
- Project transfer between users.
- Billing.
