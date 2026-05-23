# Phase 20: Cloud Issue Ingestion — Context

**Gathered:** 2026-05-22
**Status:** Ready for planning
**Source:** Interactive design session (three forks resolved with the user) + codebase audit

<domain>
## Phase Boundary

Add issue ingestion to the **cloud platform** (`cloud/server` + `cloud/platform`). A signed-in user connects GitHub and Linear to their workspace org and auto-loads issues into a per-Project issues view, persisted in a new Postgres `Issue` model and re-syncable idempotently.

**In scope:**
- Prisma schema: `Integration` (per-org per-provider OAuth token store), `Issue` (scoped to `Project`), and `Project.linearTeamId` / `Project.linearTeamKey`.
- GitHub issue sync reusing the existing Clerk GitHub OAuth token (`lib/github.ts`) and the existing 1:1 `Project.githubRepo` binding.
- Linear OAuth2 connect + GraphQL client; per-Project Linear-Team selection; issue sync.
- Sync engine: idempotent upsert keyed on `(projectId, provider, externalId)`.
- `cloud/platform` UI: integrations/connections panel + per-Project issues list with a "Sync now" control.

**Out of scope (deferred):**
- Real-time webhooks / push sync (Linear webhook receiver + GitHub poller are M3 Phase 13 / O1 — this phase is pull-on-demand sync). The cloud `Issue` model introduced here is the source of truth those can later feed.
- Bidirectional write-back (creating/closing issues in Linear/GitHub from Crawfish).
- Syncing issues into the on-disk `.crawfish/` board / lens. Issues live in Postgres only this phase.
- Enforcing hard one-org-per-user (removing `POST /orgs` / `OrgPicker`). Auto-provision already ships; tightening is a separate cleanup.
- Token encryption-at-rest hardening (note it as a follow-up; store tokens in a dedicated column and keep the surface small).
</domain>

<decisions>
## Implementation Decisions (LOCKED)

### Org model (fork 1 — resolved: "auto-provision, keep teams")
- One workspace org auto-provisioned per user on first sign-in is **already shipped** in `cloud/server/src/lib/workspace.ts` (`ensureUserHasWorkspace`), called from `authMiddleware` on both dev and prod paths. It is idempotent (no-op if any `OrgMember` exists) and seeds default agents.
- Keep `OrgMember` + `Invite` so teammates can still be added (teams preserved). Do NOT collapse to a hard 1:1 ownerId model. No schema change required for the org model in this phase.

### Issue store (fork 2 — resolved: "new cloud Issue model")
- Issues are persisted in a new Postgres `Issue` model, scoped to `Project`. The cloud platform is the source of truth for synced issues. Not pushed to the on-disk board this phase.

### Linear mapping (fork 3 — resolved: "Linear Team → Crawfish Project")
- Each Linear **Team** maps to one Crawfish `Project` (every Linear issue belongs to a team → complete, lossless mapping). Linear "Projects" and "Cycles" are carried as issue metadata/labels, NOT as the mapping unit.
- Rationale: in Linear the issue container is the Team (stable prefix `ENG-123`), not the Project. A Linear Project is cross-team and optional per issue, so it would be a lossy mapping unit.

### Schema shape
- `Integration { id, orgId (FK Org, cascade), provider ("github"|"linear"), accessToken, refreshToken?, externalWorkspaceId?, externalWorkspaceName?, createdAt, updatedAt, @@unique([orgId, provider]) }`
- `Issue { id, projectId (FK Project, cascade), provider ("github"|"linear"|"native"), externalId, externalKey ("ENG-123" | "#42"), number?, title, body?, state, url?, labels (JSON string under sqlite), assigneeExternal?, externalUpdatedAt?, syncedAt, createdAt, updatedAt, @@unique([projectId, provider, externalId]) }`
- `Project` gains `linearTeamId String?` and `linearTeamKey String?`.
- Datasource is currently `sqlite` (`schema.prisma` comment says "swap to postgresql for prod"). JSON fields must be stored as `String` (sqlite has no native JSON/array). Match the existing convention in the schema.

### Routes (extend the existing Express app)
- `GET  /api/orgs/:id/integrations` — list connected providers for the org.
- `POST /api/orgs/:id/integrations/:provider/connect` (+ OAuth callback route for Linear) — establish/store the integration.
- `GET  /api/orgs/:id/projects/:pid/issues` — list persisted issues for a project.
- `POST /api/orgs/:id/projects/:pid/sync` — trigger ingestion for that project (GitHub via repo binding; Linear via bound team).
- Reuse existing RBAC pattern: every route requires `req.userId` (set by `authMiddleware`) and an `OrgMember` row; collapse 403→404 for non-members (see `orgs.ts` `GET /:id`).

### Sync engine
- `syncProjectIssues(project)` upserts each remote issue into `Issue` keyed on `(projectId, provider, externalId)`. Re-running must not duplicate. Map provider state → a normalized `state` (e.g. open/closed). Set `syncedAt`.

### Claude's Discretion
- Exact Linear GraphQL query shape, GitHub REST vs GraphQL for issues, OAuth callback URL wiring, and platform component structure — pick the simplest path consistent with existing patterns. Researcher should pin Linear OAuth scopes + the `teams`/`issues` queries and confirm the GitHub issues call works with the Clerk-provided token in `lib/github.ts`.
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Data model + migration
- `cloud/server/prisma/schema.prisma` — current models (`User`, `Org`, `OrgMember`, `AgentMeta`, `Session`, `DeviceLinkCode`, `Invite`, `Project`). Datasource is sqlite; `Project` already has `githubRepo`/`githubRepoId`/`@@unique([orgId, githubRepoId])`.

### Auth + org/workspace (already-shipped one-workspace-per-user)
- `cloud/server/src/middleware/auth.ts` — dev shim (`X-User-Id`) + prod Clerk path; both call `ensureUserHasWorkspace`. RBAC is `req.userId`-based.
- `cloud/server/src/lib/workspace.ts` — `ensureUserHasWorkspace` (do not duplicate; rely on it).
- `cloud/server/src/lib/orgs.ts` — `loadOrgWithRelations` (org read shape).
- `cloud/server/src/routes/orgs.ts` — RBAC + slug-or-id lookup pattern to mirror.

### GitHub integration (reuse, extend to issues)
- `cloud/server/src/lib/github.ts` — Clerk-based GitHub OAuth token retrieval (`getClerkClient`), used for repo listing today.
- `cloud/server/src/routes/github.ts` — `GET /github/repos`, repo check, clone-token. No issues yet.
- `cloud/server/src/routes/projects.ts` — project CRUD; `Project` ↔ repo binding; `mergeParams` router mounted under an org.

### Platform UI
- `cloud/platform/src/pages/Projects.tsx`, `OrgRoute.tsx`, `ImportModal.tsx`, `lib/api.ts`, `lib/useAuth.tsx` — existing patterns for org/project pages and API calls. New issues view + connections panel should reuse these conventions and `@crawfish/ui` tokens.
- `cloud/platform/DEV-AUTH.md` — dev auth bypass (blank Clerk key → `X-User-Id` shim) for any Playwright/manual verification.

### App wiring
- `cloud/server/src/index.ts` — Express app + router registration (new routers register here).
</canonical_refs>

<specifics>
## Specific Ideas

- Idempotency proof: run sync twice on a project, assert `Issue` row count is unchanged and `syncedAt` advances.
- GitHub issues: filter out pull requests (the GitHub issues endpoint returns PRs too — exclude `pull_request` items).
- Linear: store `externalKey` as the human identifier (`ENG-123`); `externalId` as the stable node id for the unique key.
- Connections panel: show connected/disconnected state per provider; Linear connect requires picking a Team per Project before sync is enabled.
</specifics>

<deferred>
## Deferred Ideas

- Linear webhooks + GitHub issues poller (real-time) → M3 Phase 13 (O1).
- Token encryption-at-rest / secret-manager integration.
- One-org-per-user hard enforcement (remove `POST /orgs` + `OrgPicker`).
- Writing issues back to the provider; syncing into the on-disk lens board.
</deferred>

---

*Phase: 20-cloud-issue-ingestion-linear-github-connectors-with-postgres*
*Context gathered: 2026-05-22 via interactive design session*
