# Phase 20: Cloud Issue Ingestion — Linear + GitHub Connectors — Research

**Researched:** 2026-05-22
**Domain:** OAuth2 connector integration (Linear GraphQL + GitHub REST), Prisma/sqlite schema migration, idempotent sync engine, Express RBAC routes, React platform UI
**Confidence:** HIGH (codebase patterns verified by direct read; external APIs verified against official docs via WebSearch; one MEDIUM item flagged on GitHub OAuth scope)

## Summary

This phase adds pull-on-demand issue ingestion to the existing `cloud/server` + `cloud/platform` stack. The codebase already ships every supporting primitive: a Clerk-backed GitHub OAuth token retrieval (`lib/github.ts`), an auto-provisioned one-workspace-per-user model (`lib/workspace.ts` — do not touch), a `mergeParams` org-scoped router pattern with collapse-403-to-404 RBAC (`routes/projects.ts` / `routes/orgs.ts`), and a contract-test harness that wipes sqlite via `prisma db push --force-reset`. The work is therefore mostly *extension* of well-established local patterns plus two external API integrations.

The two external integrations differ sharply. **GitHub issues** reuse the existing Clerk token and the `Project.githubRepo` binding — a single REST call to `GET /repos/{owner}/{repo}/issues` with `pull_request`-key filtering. **Linear** requires a net-new OAuth2 authorization-code flow (Linear-hosted authorize page → server-side token exchange → token stored in the `Integration` row), then GraphQL queries against `https://api.linear.app/graphql`. The single biggest landmine: **Linear migrated all OAuth apps to a mandatory refresh-token system on 2026-04-01; access tokens now expire after 24 hours**, so the `Integration` model MUST persist `refreshToken` and the Linear client MUST refresh-on-401. This is not optional and is the most likely source of a "works today, breaks tomorrow" bug.

**Primary recommendation:** Build `lib/linear.ts` (OAuth + GraphQL client with refresh-on-expiry) and extend `lib/github.ts` with `listRepoIssues`. Add `Integration` + `Issue` models and `Project.linearTeamId/linearTeamKey` via `prisma migrate dev --name add_integration_issue` (the repo has a real migrations history — do not use bare `db push` to author the change). Store JSON as `String` (sqlite convention). Persist Linear `refreshToken`; refresh access tokens on 401. Use `prisma.issue.upsert` keyed on the compound `(projectId, provider, externalId)` for idempotent sync.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| OAuth token exchange (Linear) | API / Backend (`cloud/server`) | — | client_secret must never touch the browser; callback lands on Express |
| OAuth token storage | Database (`Integration` row) | API | tokens are server-only secrets |
| GitHub issue fetch | API / Backend | — | reuses server-held Clerk token; CORS + secret containment |
| Linear GraphQL fetch + token refresh | API / Backend | — | refresh requires client_secret |
| Issue persistence + idempotent upsert | Database (Prisma) | API | source of truth is Postgres/sqlite `Issue` model |
| Provider→normalized state mapping | API / Backend | — | business logic, belongs in sync engine |
| Connections panel (connected/disconnected) | Platform UI (`cloud/platform`) | API (`GET .../integrations`) | presentational; reads server state |
| Per-Project Team selection (Linear) | Platform UI | API (`PATCH project` / dedicated route) | user picks Team → persisted to `Project.linearTeamId` |
| "Sync now" trigger | Platform UI | API (`POST .../sync`) | user-initiated; server does the work |
| Issues list view | Platform UI | API (`GET .../issues`) | presentational |

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Org model (fork 1 — "auto-provision, keep teams"):**
- One workspace org auto-provisioned per user is **already shipped** in `cloud/server/src/lib/workspace.ts` (`ensureUserHasWorkspace`), called from `authMiddleware`. Idempotent, seeds default agents. **No schema change for the org model.** Do NOT collapse to a 1:1 ownerId model. Keep `OrgMember` + `Invite`.

**Issue store (fork 2 — "new cloud Issue model"):**
- Issues persisted in a new Postgres `Issue` model, scoped to `Project`. Cloud platform is source of truth. NOT pushed to the on-disk board this phase.

**Linear mapping (fork 3 — "Linear Team → Crawfish Project"):**
- Each Linear **Team** maps to one Crawfish `Project`. Linear "Projects" and "Cycles" are carried as issue metadata/labels, NOT the mapping unit. Rationale: the Team is the stable issue container (`ENG-123` prefix); a Linear Project is cross-team and optional, so it would be lossy.

**Schema shape (LOCKED):**
- `Integration { id, orgId (FK Org, cascade), provider ("github"|"linear"), accessToken, refreshToken?, externalWorkspaceId?, externalWorkspaceName?, createdAt, updatedAt, @@unique([orgId, provider]) }`
- `Issue { id, projectId (FK Project, cascade), provider ("github"|"linear"|"native"), externalId, externalKey ("ENG-123" | "#42"), number?, title, body?, state, url?, labels (JSON string under sqlite), assigneeExternal?, externalUpdatedAt?, syncedAt, createdAt, updatedAt, @@unique([projectId, provider, externalId]) }`
- `Project` gains `linearTeamId String?` and `linearTeamKey String?`.
- Datasource is `sqlite`. JSON fields stored as `String` (sqlite has no native JSON/array). Match existing schema convention.

**Routes (extend existing Express app):**
- `GET  /api/orgs/:id/integrations`
- `POST /api/orgs/:id/integrations/:provider/connect` (+ OAuth callback for Linear)
- `GET  /api/orgs/:id/projects/:pid/issues`
- `POST /api/orgs/:id/projects/:pid/sync`
- Reuse RBAC: every route requires `req.userId` + an `OrgMember` row; collapse 403→404 for non-members.

**Sync engine:**
- `syncProjectIssues(project)` upserts each remote issue keyed on `(projectId, provider, externalId)`. Re-running must not duplicate. Map provider state → normalized `state` (open/closed). Set `syncedAt`.

### Claude's Discretion
- Exact Linear GraphQL query shape, GitHub REST vs GraphQL for issues, OAuth callback URL wiring, platform component structure — pick the simplest path consistent with existing patterns. (Researcher pinned these below.)

### Deferred Ideas (OUT OF SCOPE)
- Linear webhooks + GitHub issues poller (real-time) → M3 Phase 13 (O1).
- Token encryption-at-rest / secret-manager integration. (Note as follow-up; keep token surface small.)
- One-org-per-user hard enforcement (remove `POST /orgs` + `OrgPicker`).
- Bidirectional write-back to provider.
- Syncing issues into the on-disk `.crawfish/` board / lens.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| REQ-knowledge-connectors | Tier-1 connectors ship as benchmarked craws (email, chat, docs, GitHub/GitLab, Linear/Jira, local vaults) with keychain auth + incremental sync | This phase delivers the GitHub + Linear connector slice with OAuth auth + idempotent (incremental-capable) sync. Pull-on-demand now; webhook/poller deferred to Phase 13. `externalUpdatedAt` field supports future incremental sync. |
| REQ-orch-issue-intake | Read Linear ticket / GitHub Issues and ingest into the platform | This phase establishes the cloud `Issue` model as the source of truth that the Phase-13 orchestrator intake (webhook <10s, classifier) will later feed. The Team→Project mapping and idempotent upsert are the persistence substrate for intake. |
</phase_requirements>

## Standard Stack

No new runtime dependencies are required. Everything is built from primitives already in `cloud/server/package.json`.

### Core (already installed — verified in package.json)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `@prisma/client` | ^5.22.0 | ORM, `Issue`/`Integration` models, `upsert` | Already the project ORM [VERIFIED: package.json] |
| `prisma` (CLI) | ^5.22.0 | `migrate dev` to author the new migration | Repo has a real migrations history [VERIFIED: prisma/migrations/] |
| `express` | ^4.21.1 | New routers (integrations, issues, sync, OAuth callback) | Existing app framework [VERIFIED] |
| `zod` | ^3.23.8 | Request body/query validation (mirror `projects.ts`) | Existing validation lib [VERIFIED] |
| `@clerk/backend` | ^3.4.9 | GitHub OAuth token via `getUserOauthAccessToken` | Already used by `lib/github.ts` [VERIFIED] |
| `nanoid` | ^5.0.9 | OAuth `state` param generation (CSRF token) | Already installed [VERIFIED] |
| global `fetch` | Node 22 built-in | HTTP to GitHub REST + Linear GraphQL | Existing `lib/github.ts` uses bare `fetch` [VERIFIED] |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `vitest` + `supertest` | ^4.1.6 / ^7.2.2 | Contract tests for new routes + sync idempotency | All new-route verification [VERIFIED] |

**Do NOT add `@linear/sdk` or `@octokit/*`.** The codebase deliberately uses bare `fetch` against the REST/GraphQL endpoints (see `lib/github.ts`). Adding an SDK would (a) introduce a new dependency requiring slopcheck, (b) break the established stub-`globalThis.fetch` test pattern, and (c) pull in transitive deps for a handful of calls. A hand-rolled GraphQL POST is ~10 lines and matches the existing house style. [ASSUMED — house-style inference from `lib/github.ts`]

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| GitHub REST `/issues` | GitHub GraphQL `repository.issues` | GraphQL avoids the PR-in-issues problem (separate `issues` and `pullRequests` connections) but requires a different token-scope check and a new query builder; REST matches existing `lib/github.ts` `fetch` style. Recommend **REST** for consistency, filter PRs by the `pull_request` key. |
| Bare `fetch` GraphQL | `@linear/sdk` | SDK is ergonomic but adds a dependency + breaks the fetch-stub test pattern. Recommend **bare fetch**. |
| `prisma migrate dev` | `prisma db push` | `db push` does not create a migration file; the repo has a tracked migrations history (`0_init`, `20260518133119_add_project`). Use **`migrate dev`** to stay consistent. (Test harness still uses `db push --force-reset` independently — that is fine, see Pitfall 4.) |

**Installation:** None. (No `npm install`.)

## Package Legitimacy Audit

> No external packages are installed this phase. All capabilities use dependencies already present in `cloud/server/package.json` (verified by direct read). Therefore the slopcheck gate is N/A — there is nothing to audit.

| Package | Registry | Disposition |
|---------|----------|-------------|
| (none — no new installs) | — | N/A |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

## Architecture Patterns

### System Architecture Diagram

```
                         cloud/platform (React SPA)
   ┌──────────────────────────────────────────────────────────────┐
   │  Connections panel        Project Issues view + "Sync now"     │
   │  (per-provider state)     (list + Team picker for Linear)      │
   └───────┬───────────────────────────┬───────────────────┬───────┘
           │ apiFetch (X-User-Id dev /  │                   │
           │  Bearer Clerk prod)        │                   │
           ▼                            ▼                   ▼
   ┌──────────────────────────────────────────────────────────────┐
   │  cloud/server (Express)   authMiddleware → req.userId          │
   │                            requireMember(orgId) → 403→404      │
   │                                                                │
   │  GET  /api/orgs/:id/integrations ──► list Integration rows     │
   │  POST /api/orgs/:id/integrations/github/connect ─┐             │
   │  POST /api/orgs/:id/integrations/linear/connect ─┤             │
   │  GET  /api/integrations/linear/callback ◄────────┘ (OAuth)     │
   │  GET  /api/orgs/:id/projects/:pid/issues ──► read Issue rows   │
   │  POST /api/orgs/:id/projects/:pid/sync ──► syncProjectIssues() │
   └───────┬───────────────────────┬───────────────────┬───────────┘
           │                       │                    │
   lib/github.ts            lib/linear.ts          Prisma (sqlite dev.db)
   getGithubToken(Clerk)    OAuth + GraphQL +       Integration / Issue /
   listRepoIssues()         refresh-on-401          Project (+linearTeamId)
           │                       │
           ▼                       ▼
   api.github.com/repos     linear.app/oauth/authorize (browser redirect)
   /{o}/{r}/issues          api.linear.app/oauth/token (server exchange)
   (filter pull_request)    api.linear.app/graphql  (teams + issues)
```

Primary use case (Linear sync), traced: user clicks "Connect Linear" → server returns the `linear.app/oauth/authorize` URL with `state` → user authorizes → Linear redirects to `/api/integrations/linear/callback?code=&state=` → server POSTs to `api.linear.app/oauth/token`, stores `accessToken`+`refreshToken` in `Integration` → user picks a Team for the Project (`Project.linearTeamId` set) → user clicks "Sync now" → `POST .../sync` → `syncProjectIssues` GraphQL-pages the Team's issues → `prisma.issue.upsert` per issue → issues list view reads them back.

### Recommended Project Structure
```
cloud/server/src/
├── lib/
│   ├── github.ts        # EXTEND: add listRepoIssues(token, owner, name, page)
│   └── linear.ts        # NEW: buildAuthorizeUrl, exchangeCode, refreshToken,
│                        #      graphql<T>(), listTeams, listTeamIssues
├── routes/
│   ├── integrations.ts  # NEW: list / connect / linear OAuth callback
│   └── issues.ts        # NEW (or fold into projects.ts): GET issues, POST sync
├── lib/
│   └── sync.ts          # NEW: syncProjectIssues(project) — provider dispatch + upsert
└── index.ts             # EXTEND: register new routers
cloud/platform/src/
├── lib/api.ts           # EXTEND: listIntegrations, connectProvider, listIssues, syncProject
├── pages/
│   ├── Connections.tsx  # NEW: per-provider connect/disconnect panel
│   └── ProjectIssues.tsx# NEW: issues list + Sync now + Linear Team picker
```

### Pattern 1: Org-scoped RBAC router (mirror `projects.ts`)
**What:** Every org-scoped route resolves `:orgId` by id-or-slug, checks `OrgMember`, collapses non-member to 404.
**When to use:** All four new routes.
**Example:**
```typescript
// Source: cloud/server/src/routes/projects.ts (verified by read)
async function requireMember(req: Request, orgIdParam: string): Promise<RequireMemberResult> {
  const userId = req.userId;
  if (!userId) return { ok: false, status: 401, code: "unauthenticated" };
  const org = await db.org.findFirst({
    where: { OR: [{ id: orgIdParam }, { name: orgIdParam }] },
    select: { id: true },
  });
  if (!org) return { ok: false, status: 404, code: "not_found" };
  const m = await db.orgMember.findUnique({ where: { orgId_userId: { orgId: org.id, userId } } });
  if (!m) return { ok: false, status: 404, code: "not_found" };
  return { ok: true, orgId: org.id, userId };
}
```
Mount with `mergeParams: true` and register in `index.ts` under `/api/orgs/:orgId/...`.

### Pattern 2: GitHub fetch with Clerk token (extend `lib/github.ts`)
**What:** Bare `fetch` to GitHub REST with the Clerk-provided OAuth token; throw typed errors.
**Example:**
```typescript
// Source: extends cloud/server/src/lib/github.ts (verified pattern)
export interface GithubIssue {
  number: number; title: string; body: string | null; state: string;
  labels: { name: string }[]; assignee: { login: string } | null;
  html_url: string; updated_at: string; node_id: string;
  pull_request?: unknown;   // present ONLY on PRs — used to filter
}
export async function listRepoIssues(
  token: string, owner: string, name: string, page: number,
): Promise<GithubIssue[]> {
  const url = `https://api.github.com/repos/${encodeURIComponent(owner)}/${encodeURIComponent(name)}`
    + `/issues?state=all&per_page=100&page=${page}`;
  const r = await fetch(url, {
    headers: { Authorization: `Bearer ${token}`, Accept: "application/vnd.github+json",
               "User-Agent": "crawfish-server", "X-GitHub-Api-Version": "2022-11-28" },
  });
  if (!r.ok) throw new Error(`github ${r.status}`);
  const arr = (await r.json()) as GithubIssue[];
  return arr.filter((i) => i.pull_request === undefined);   // EXCLUDE PRs
}
```

### Pattern 3: Linear OAuth + GraphQL client (`lib/linear.ts`, NEW)
**What:** Authorization-code flow + GraphQL POST + refresh-on-401.
**Example:**
```typescript
// Source: linear.app/developers/oauth-2-0-authentication + /pagination (CITED)
const AUTHORIZE = "https://linear.app/oauth/authorize";
const TOKEN = "https://api.linear.app/oauth/token";
const GRAPHQL = "https://api.linear.app/graphql";

export function buildAuthorizeUrl(state: string): string {
  const p = new URLSearchParams({
    client_id: process.env.LINEAR_CLIENT_ID!,
    redirect_uri: process.env.LINEAR_REDIRECT_URI!,
    response_type: "code",
    scope: "read",              // read is sufficient for teams + issues
    state,
  });
  return `${AUTHORIZE}?${p.toString()}`;
}

export async function exchangeCode(code: string): Promise<{
  access_token: string; refresh_token: string; expires_in: number;
}> {
  const r = await fetch(TOKEN, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      grant_type: "authorization_code",
      code,
      redirect_uri: process.env.LINEAR_REDIRECT_URI!,
      client_id: process.env.LINEAR_CLIENT_ID!,
      client_secret: process.env.LINEAR_CLIENT_SECRET!,
    }).toString(),
  });
  if (!r.ok) throw new Error(`linear token ${r.status}`);
  return r.json();
}

// Refresh (REQUIRED — tokens expire in 24h since 2026-04-01)
export async function refreshAccessToken(refreshToken: string) {
  const r = await fetch(TOKEN, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      grant_type: "refresh_token",
      refresh_token: refreshToken,
      client_id: process.env.LINEAR_CLIENT_ID!,
      client_secret: process.env.LINEAR_CLIENT_SECRET!,
    }).toString(),
  });
  if (!r.ok) throw new Error(`linear refresh ${r.status}`);
  return r.json();
}

async function graphql<T>(token: string, query: string, variables?: object): Promise<T> {
  const r = await fetch(GRAPHQL, {
    method: "POST",
    headers: { Authorization: token, "Content-Type": "application/json" },
    //         ^ Linear accepts the raw OAuth access token (no "Bearer " prefix
    //           is required for OAuth tokens, though Bearer is also accepted)
    body: JSON.stringify({ query, variables }),
  });
  const j = await r.json();
  if (j.errors) throw new Error(JSON.stringify(j.errors));
  return j.data as T;
}
```

### Pattern 4: Linear GraphQL queries (teams + paged team issues)
```graphql
# List the viewer's teams (for the connect → Team-picker flow)
query Teams { teams { nodes { id key name } } }

# Page through a team's issues. endCursor/hasNextPage drive pagination.
# Default page size is 50; pass first + after.
query TeamIssues($teamId: String!, $after: String) {
  team(id: $teamId) {
    issues(first: 50, after: $after) {
      nodes {
        id identifier title description url updatedAt
        state { name type }            # type ∈ {backlog,unstarted,started,completed,canceled}
        assignee { displayName email }
        labels { nodes { name } }
        project { name }
        cycle { number }
      }
      pageInfo { hasNextPage endCursor }
    }
  }
}
```
[CITED: linear.app/developers/pagination — `first`/`after`, `pageInfo.hasNextPage`/`endCursor`, default 50]

### Pattern 5: Idempotent upsert (sync engine)
```typescript
// Source: Prisma upsert on compound @@unique (verified Prisma 5.22 semantics)
await db.issue.upsert({
  where: { projectId_provider_externalId: {     // compound unique selector name
    projectId: project.id, provider: "linear", externalId: node.id,
  }},
  create: {
    projectId: project.id, provider: "linear",
    externalId: node.id, externalKey: node.identifier,
    title: node.title, body: node.description ?? null,
    state: normalizeLinearState(node.state.type),  // → "open" | "closed"
    url: node.url,
    labels: JSON.stringify(node.labels.nodes.map((l) => l.name)),  // JSON-as-String
    assigneeExternal: node.assignee?.displayName ?? null,
    externalUpdatedAt: new Date(node.updatedAt),
    syncedAt: new Date(),
  },
  update: {
    externalKey: node.identifier, title: node.title, body: node.description ?? null,
    state: normalizeLinearState(node.state.type), url: node.url,
    labels: JSON.stringify(node.labels.nodes.map((l) => l.name)),
    assigneeExternal: node.assignee?.displayName ?? null,
    externalUpdatedAt: new Date(node.updatedAt),
    syncedAt: new Date(),
  },
});
```
The compound-`where` selector name Prisma generates for `@@unique([projectId, provider, externalId])` is `projectId_provider_externalId` (mirrors the existing `org_repo_unique` named index usage in `projects.ts` — note that `@@unique` with an explicit `name:` lets you alias it; without a name, Prisma derives the field-joined name).

### Anti-Patterns to Avoid
- **Putting OAuth `client_secret` or token exchange in the browser.** The Linear callback and token exchange MUST be server-side. The platform only ever sees the *authorize URL* and a success/failure signal.
- **Storing the Linear access token without the refresh token.** Tokens expire in 24h (post-2026-04-01). A sync that worked at connect time will 401 the next day. `refreshToken` is in the locked schema for exactly this reason — wire the refresh path.
- **Treating GitHub `/issues` results as all-issues.** PRs are returned too; filter `pull_request === undefined`.
- **Re-implementing `ensureUserHasWorkspace` or the org model.** Already shipped; locked out of scope.
- **Authoring the schema change with `db push` only.** It skips the migrations history the repo tracks. Use `migrate dev`.
- **Per-component CSS files.** Project convention: CSS lives in `ui/tokens/globals.css`, aliased via `@crawfish/ui`. Reuse `Eyebrow`/`Pill` and existing tokens (see `Projects.tsx`).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| GitHub OAuth token acquisition | A second GitHub OAuth app | `getGithubToken(userId)` via Clerk (`lib/github.ts`) | Clerk already brokers the GitHub connection; CONTEXT locks reuse of this token |
| Org→user membership check | New auth logic | `requireMember()` copied from `projects.ts` | Established 403→404 RBAC pattern |
| Idempotent insert-or-update | Manual `findFirst` then `create`/`update` | `prisma.issue.upsert` on the compound key | Atomic; the locked `@@unique` exists precisely for this |
| OAuth CSRF protection | Custom nonce store | `nanoid()` `state` param round-tripped through callback | Already an installed dep |
| Workspace provisioning | Anything | `ensureUserHasWorkspace` (already shipped) | Locked out of scope |

**Key insight:** This phase is 80% wiring of existing primitives. The only genuinely new code is the Linear OAuth+GraphQL client and the React panels. Resist adding SDKs — the bare-`fetch` house style is load-bearing for the test harness (which stubs `globalThis.fetch`).

## Runtime State Inventory

> This is an *additive* phase (new models + new routes), not a rename/refactor. No existing runtime string is being renamed. The relevant "state" question is instead: *what new external/runtime config must exist for this to run?*

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | New `Integration` rows hold live OAuth tokens (plaintext this phase). `Issue` rows hold synced issues. | Schema migration (new tables). Token encryption is a deferred follow-up (CONTEXT). |
| Live service config | A **Linear OAuth application** must be registered in the Linear workspace developer settings, with the redirect URI matching `LINEAR_REDIRECT_URI`. This config lives in Linear's UI, NOT in git. | Manual: register the OAuth app; record `client_id`/`client_secret`/redirect URI. Planner should add a `checkpoint:human-verify` for this. |
| OS-registered state | None. | None — verified: no Task Scheduler / launchd / pm2 involvement in `cloud/server`. |
| Secrets/env vars | NEW env vars required: `LINEAR_CLIENT_ID`, `LINEAR_CLIENT_SECRET`, `LINEAR_REDIRECT_URI`. GitHub uses the existing Clerk path (`CLERK_SECRET_KEY`) — no new GitHub secret. `DATABASE_URL` unchanged (`file:./dev.db`). | Add to `.env` (not in git) + document. |
| Build artifacts | `@prisma/client` is regenerated on schema change (`prisma generate`, run automatically by `migrate dev`). `dist/` is git-ignored; do not hand-edit. | Run `prisma generate` after schema edit (migrate dev does this). |

## Common Pitfalls

### Pitfall 1: Linear access tokens expire (24h) — refresh is mandatory
**What goes wrong:** Sync works immediately after connecting, then returns 401 the next day.
**Why it happens:** Linear migrated ALL OAuth apps to a mandatory refresh-token system on **2026-04-01**. Access tokens are valid ~24h. [CITED: linear.app/developers/oauth-2-0-authentication]
**How to avoid:** Persist `refresh_token` in `Integration.refreshToken` at connect time. In the Linear client, on a 401/expired response, call `refreshAccessToken`, persist the new pair, and retry once.
**Warning signs:** Sync succeeds in tests/demo, fails for any user >24h after connecting.

### Pitfall 2: GitHub `/issues` returns pull requests
**What goes wrong:** PR rows pollute the `Issue` table; counts are wrong.
**Why it happens:** GitHub treats PRs as a subtype of issue; `GET /repos/{o}/{r}/issues` returns both. [CITED: docs.github.com/en/rest/issues/issues]
**How to avoid:** Filter out any item where the `pull_request` key is present (`i.pull_request === undefined`).
**Warning signs:** Issue count exceeds the repo's actual open-issues number.

### Pitfall 3: GitHub OAuth scope may not include private-repo issues (MEDIUM confidence)
**What goes wrong:** `listRepoIssues` 404s or returns empty for a private repo even though the user can see it.
**Why it happens:** GitHub OAuth has **no separate "issues" scope** — issue read is granted by `repo` (private+public) or `public_repo` (public only). [CITED: docs.github.com/.../scopes-for-oauth-apps] The Clerk GitHub connection's configured scope determines this. The existing code already reads *private* repo metadata and `.crawfish/` file contents via the same token (`projects.ts` `fetchRepoMetadata`, contents endpoint), which strongly implies the Clerk connection requests `repo` — so issues should be readable. **Verify** by syncing a private repo during testing.
**How to avoid:** During verification, sync a private repo's issues. If it fails, the Clerk GitHub OAuth scope config (in the Clerk dashboard) needs `repo`, not just `public_repo`/`read:user`.
**Warning signs:** Public-repo issues work, private-repo issues 404/empty.

### Pitfall 4: `migrate dev` vs the test harness `db push --force-reset`
**What goes wrong:** Confusion about which command applies the schema.
**Why it happens:** Two independent flows exist. The repo *authors* schema via `prisma migrate dev` (real migrations in `prisma/migrations/`). The *contract test harness* (`tests/contract/setup.ts`) wipes and recreates the DB via `npx prisma db push --force-reset --skip-generate` — it reads `schema.prisma` directly, ignoring migration files. [VERIFIED: setup.ts read]
**How to avoid:** Author the change with `npx prisma migrate dev --name add_integration_issue` (creates the migration file + regenerates the client). The test harness will independently pick up the new models from `schema.prisma`. Both must agree because both derive from the same `schema.prisma`. Non-interactive CI: `prisma migrate deploy`.
**Warning signs:** New tables exist in tests but no migration file was committed (means you only ran `db push`).

### Pitfall 5: sqlite limitations that bite on the eventual Postgres swap
**What goes wrong:** Code written against sqlite quirks breaks when `provider` flips to `postgresql`.
**Why it happens:** (a) sqlite has no native JSON/array — the locked schema stores `labels` as a `String`; on Postgres you could use `Json`/`String[]` but the migration files are **provider-specific and incompatible** [CITED: prisma.io limitations-and-known-issues]. (b) sqlite `String` has no length limits; Postgres `text` is fine but be deliberate. (c) Case-sensitivity and `mode: "insensitive"` filters differ. (d) Switching providers requires deleting the migrations dir and re-baselining (or an expand/contract migration). [CITED: prisma.io data-migration]
**How to avoid:** Keep `labels` as JSON-encoded `String` now (matches locked schema + existing convention). Treat the Postgres swap as a separate, planned migration — do NOT pre-optimize for it. Document `JSON.parse(labels)` as the read-side contract so the eventual swap to a `Json` column is mechanical.
**Warning signs:** Querying inside `labels` with SQL (don't — parse in app code).

### Pitfall 6: OAuth callback route must be public (pre-auth), state-validated
**What goes wrong:** The Linear callback hits `authMiddleware` and 401s because the browser redirect from Linear carries no `X-User-Id`/Bearer.
**Why it happens:** `index.ts` mounts `app.use("/api", authMiddleware)` for everything under `/api`. A browser redirect from `linear.app` won't carry the platform's auth header.
**How to avoid:** Mount the callback route **before** the `authMiddleware` line (like `/api/health`, `/api/device-link`, `/api/invites` are), and recover the user/org from the `state` parameter (sign or store `state → {userId, orgId}` at connect time, validate on callback). Mirror the existing public-route mounting pattern in `index.ts`. [VERIFIED: index.ts read]
**Warning signs:** Callback returns 401; user lands on an auth error after authorizing on Linear.

## Code Examples

### Normalize provider state → {open, closed}
```typescript
// Linear state.type ∈ backlog|unstarted|started|completed|canceled
function normalizeLinearState(t: string): "open" | "closed" {
  return t === "completed" || t === "canceled" ? "closed" : "open";
}
// GitHub state is already "open"|"closed"
function normalizeGithubState(s: string): "open" | "closed" {
  return s === "closed" ? "closed" : "open";
}
```

### Public callback mounting (in index.ts, BEFORE authMiddleware)
```typescript
// Source: mirrors existing public-route block in cloud/server/src/index.ts
app.use("/api/integrations/linear/callback", linearCallbackRouter); // public
// ... existing public routes ...
app.use("/api", authMiddleware);                                    // gate
app.use("/api/orgs/:orgId/integrations", integrationsRouter);       // gated
app.use("/api/orgs/:orgId/projects", projectsRouter);               // existing
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Linear long-lived OAuth tokens | Mandatory refresh tokens, 24h access-token TTL | 2026-04-01 (all apps migrated) | MUST persist + use `refresh_token` |
| GitHub `application/vnd.github.v3+json` | `application/vnd.github+json` + `X-GitHub-Api-Version: 2022-11-28` | 2022 API versioning | Use the dated header (existing `lib/github.ts` uses `+json` without the version header — adding the version header is best practice) |

**Deprecated/outdated:**
- Linear non-refresh OAuth tokens: removed 2026-04-01. Any guide showing a non-expiring Linear OAuth access token is stale.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Clerk's GitHub OAuth connection requests the `repo` scope (so private-repo issues are readable) | Pitfall 3 | If only `public_repo`, private-repo issue sync fails — needs a Clerk dashboard scope change. Verify by syncing a private repo. |
| A2 | `scope=read` is sufficient for `teams` + `team.issues` GraphQL queries | Pattern 3 | If insufficient, connect succeeds but queries 403. Low risk — `read` is documented as full read access. |
| A3 | Bare `fetch` (no SDK) is the intended house style | Standard Stack | If the team prefers `@linear/sdk`, the test-stub pattern changes. Inferred from `lib/github.ts`. |
| A4 | Linear GraphQL accepts the raw access token in `Authorization` (no `Bearer` prefix needed for OAuth tokens) | Pattern 3 | If `Bearer` prefix is required, a one-line fix. Linear docs show both forms; using the raw token is the documented OAuth form. |
| A5 | The compound `@@unique` selector name is `projectId_provider_externalId` | Pattern 5 | If Prisma derives a different name, the upsert `where` key needs adjustment — caught immediately by type-check. |

## Open Questions

1. **GitHub OAuth scope (private repos).**
   - What we know: issue read needs `repo` (private) or `public_repo` (public); no separate issues scope. Existing code reads private repo data via the same token.
   - What's unclear: the exact scope string Clerk's GitHub social connection was configured with.
   - Recommendation: verify during testing by syncing a private repo; if it fails, fix the Clerk dashboard GitHub OAuth scope.

2. **Where does the Linear Team picker persist?**
   - What we know: `Project.linearTeamId`/`linearTeamKey` are the target columns.
   - What's unclear: whether to add a dedicated `PUT .../linear-team` route or extend the existing `PATCH /:pid` (which currently gates clone-fields behind a dash token).
   - Recommendation: add a small dedicated route (`POST .../integrations/linear/select-team` or extend `PATCH` with a non-clone field path) rather than loosening the dash-token gate on `PATCH`.

3. **`state` round-trip storage for OAuth CSRF.**
   - What we know: `state` must carry `{userId, orgId}` to the public callback.
   - What's unclear: signed JWT (`lib/jwt.ts` exists) vs a short-lived DB row.
   - Recommendation: sign a short-lived JWT with `lib/jwt.ts` (no schema change, no cleanup job) — simplest path consistent with existing code.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Node + global `fetch` | All HTTP calls | ✓ | Node 22 (`@types/node` ^22) | — |
| prisma CLI | migration | ✓ | 5.22.0 [VERIFIED via `npx prisma --version`] | — |
| sqlite (`dev.db`) | data layer | ✓ | file:./dev.db [VERIFIED in .env] | — |
| Clerk GitHub OAuth token | GitHub issue sync | ✓ (path shipped) | @clerk/backend ^3.4.9 | dev: stub `getClerkClient` (existing test pattern) |
| Linear OAuth app (client_id/secret/redirect) | Linear connect | ✗ — must be registered | — | none — blocks Linear sync until registered |
| `LINEAR_CLIENT_ID/SECRET/REDIRECT_URI` env | Linear OAuth | ✗ — not set | — | none — blocks Linear connect |

**Missing dependencies with no fallback:**
- Linear OAuth application registration + the three `LINEAR_*` env vars. Linear connect/sync cannot function until these exist. GitHub sync is unaffected and can ship/verify independently. Planner should sequence GitHub sync first and gate Linear connect behind a `checkpoint:human-verify` for the OAuth app registration.

**Missing dependencies with fallback:**
- Clerk in tests: the existing harness stubs `getClerkClient` and `globalThis.fetch` — reuse that to test GitHub sync without a live token.

## Validation Architecture

> `.planning/config.json` was not found; treating nyquist_validation as enabled (default). This phase clearly warrants it.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | vitest ^4.1.6 + supertest ^7.2.2 (contract tests) |
| Config file | `cloud/server/vitest.config.ts` (include `tests/contract/**/*.spec.ts`, sequential, shared sqlite) |
| Quick run command | `cd cloud/server && npx vitest run tests/contract/issues.spec.ts` |
| Full suite command | `cd cloud/server && npm test` (`vitest run`) |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| REQ-knowledge-connectors | Migration applies cleanly (Integration/Issue/Project.linearTeamId exist) | integration | `npx vitest run tests/contract/issues.spec.ts -t "schema"` | ❌ Wave 0 |
| REQ-knowledge-connectors | Idempotent re-sync: run sync twice, row count unchanged, `syncedAt` advances | integration | `npx vitest run tests/contract/sync.spec.ts -t "idempotent"` | ❌ Wave 0 |
| REQ-knowledge-connectors | GitHub PR exclusion: items with `pull_request` key are not persisted | integration | `npx vitest run tests/contract/sync.spec.ts -t "excludes pull requests"` | ❌ Wave 0 |
| REQ-orch-issue-intake | Linear Team→Project mapping: `linearTeamId` selection drives which team's issues sync | integration | `npx vitest run tests/contract/sync.spec.ts -t "team mapping"` | ❌ Wave 0 |
| REQ-orch-issue-intake | OAuth round-trip: connect returns authorize URL; callback with valid `state`+`code` stores Integration (token exchange stubbed via `globalThis.fetch`) | integration | `npx vitest run tests/contract/integrations.spec.ts -t "oauth"` | ❌ Wave 0 |
| REQ-knowledge-connectors | RBAC: non-member gets 404 on integrations/issues/sync routes | integration | `npx vitest run tests/contract/integrations.spec.ts -t "non-member"` | ✅ pattern exists (copy from projects.spec.ts) |
| REQ-knowledge-connectors | Linear token refresh: a 401 from GraphQL triggers refresh + retry (stub fetch to 401-then-200) | unit/integration | `npx vitest run tests/contract/sync.spec.ts -t "refresh"` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `cd cloud/server && npx tsc --noEmit && npx vitest run tests/contract/<touched>.spec.ts`
- **Per wave merge:** `cd cloud/server && npm test`
- **Phase gate:** full `npm test` green + `npx tsc --noEmit` clean before `/gsd:verify-work`.

### Wave 0 Gaps
- [ ] `tests/contract/integrations.spec.ts` — covers REQ-orch-issue-intake (OAuth round-trip, list, RBAC)
- [ ] `tests/contract/sync.spec.ts` — covers REQ-knowledge-connectors (idempotency, PR exclusion, team mapping, refresh)
- [ ] Reuse `tests/contract/setup.ts` harness + the `_setClerkClientForTests` / `globalThis.fetch` stub pattern from `github.spec.ts` — no new framework install needed.
- [ ] No framework install required (vitest + supertest already present).

## Security Domain

> `security_enforcement` not found in config; treating as enabled (default).

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | Existing `authMiddleware` (Clerk prod / dev shim); OAuth2 authorization-code for Linear (server-side token exchange) |
| V3 Session Management | yes | OAuth `state` param as CSRF token (signed JWT via `lib/jwt.ts`); short TTL |
| V4 Access Control | yes | `requireMember()` org-scoped RBAC; collapse 403→404 (existing pattern) |
| V5 Input Validation | yes | zod on all route bodies/params (mirror `projects.ts`); validate `provider ∈ {github,linear}` |
| V6 Cryptography | partial | OAuth tokens stored **plaintext this phase** (encryption-at-rest is a CONTEXT-deferred follow-up). Do NOT log tokens. Keep token columns out of any API response. |
| V9 Communication | yes | All provider calls over HTTPS; redirect_uri must be HTTPS in prod |

### Known Threat Patterns for {OAuth connector / Express}

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| OAuth CSRF (forged callback) | Spoofing | Validate `state` round-trip (signed JWT carrying userId+orgId) |
| Token leakage in logs/responses | Information Disclosure | Never log tokens; exclude `accessToken`/`refreshToken` from `GET /integrations` response (return only `provider`, `connected`, `externalWorkspaceName`) |
| client_secret exposure | Information Disclosure | Token exchange + refresh server-side only; secret in env, never in browser/git |
| IDOR on issues/sync | Elevation of Privilege | `requireMember()` + scope every query by resolved `orgId`/`projectId` |
| SSRF via attacker-controlled repo/team | Tampering | URLs are constructed from validated stored values, not raw user input; `encodeURIComponent` on path segments (existing pattern) |
| Open redirect on callback | Tampering | `redirect_uri` is a fixed server env value, not user-supplied |
| Plaintext token at rest | Information Disclosure | **Accepted risk this phase** (CONTEXT defers encryption). Mitigate: minimal token surface, no logging, follow-up ticket. Flag to user. |

## Sources

### Primary (HIGH confidence)
- Codebase (direct read): `cloud/server/prisma/schema.prisma`, `src/lib/github.ts`, `src/lib/workspace.ts`, `src/middleware/auth.ts`, `src/routes/{orgs,projects,github}.ts`, `src/index.ts`, `src/lib/errors.ts`, `tests/contract/setup.ts` + `projects.spec.ts`, `package.json`, `vitest.config.ts`, `prisma/migrations/`, `cloud/platform/src/lib/{api,useAuth,clerk}.tsx/.ts`, `pages/Projects.tsx`
- `npx prisma --version` → prisma + @prisma/client 5.22.0 [VERIFIED]

### Secondary (MEDIUM confidence — official docs via WebSearch)
- linear.app/developers/oauth-2-0-authentication — authorize URL `https://linear.app/oauth/authorize`, token endpoint `https://api.linear.app/oauth/token`, form-urlencoded, 24h access token + mandatory refresh (migrated 2026-04-01)
- linear.app/developers/pagination — `first`/`after`, `pageInfo.hasNextPage`/`endCursor`, default 50
- linear.app/developers/rate-limiting — GraphQL endpoint `https://api.linear.app/graphql`; OAuth app ~500 req/hr/user (third-party-reported), leaky-bucket complexity limiting; verify exact figures against the live doc
- linear.app OAuth scopes — `read` (default, full read), `write`, `issues:create`, `comments:create`, `admin`, `app:assignable`, `app:mentionable`
- docs.github.com/en/rest/issues/issues — `/issues` returns PRs, distinguished by `pull_request` key; `per_page`/`page`, `state` filter, Link header pagination
- docs.github.com/.../scopes-for-oauth-apps — no separate issues scope; `repo` (private+public) / `public_repo` (public) grant issue read
- prisma.io/.../limitations-and-known-issues + /guides/data-migration — provider-specific migration files; provider switch requires re-baseline

### Tertiary (LOW confidence — needs validation)
- Exact Linear OAuth per-app rate limit (sources conflict: 500 vs 1500 req/hr). Treat as "well under a few hundred req/hr is safe"; verify on the live rate-limiting page if high-volume sync is added.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — verified by direct package.json + code read; zero new deps
- Architecture/patterns: HIGH — mirrors existing verified `projects.ts`/`github.ts`/`index.ts` patterns
- External APIs (Linear/GitHub): MEDIUM-HIGH — endpoints/flows confirmed via official docs; exact rate limits LOW
- Pitfalls: HIGH — refresh-token, PR-exclusion, migrate-vs-push, sqlite-swap all cross-checked against official docs + codebase

**Research date:** 2026-05-22
**Valid until:** 2026-06-21 (30 days) — EXCEPT Linear OAuth, which is fast-moving (post-2026-04-01 refresh migration); re-verify Linear token semantics if planning slips past ~2 weeks.
