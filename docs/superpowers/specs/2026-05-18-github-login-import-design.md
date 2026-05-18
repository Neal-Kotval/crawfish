# Spec A+B — GitHub login + project import (clone or adopt-local)

**Status:** Draft — design approved 2026-05-18.
**Scope:** First slice of the larger "log in → create org → import project → use Claude Code → analytics + agents + issues" vision. This spec covers **login** and **project import** only. Specs C–G (local↔platform bridge, generated `ROADMAP.md` / `DESIGN.md`, analytics, agent templates, issue tracking) are deferred to later cycles.

---

## 1. Goals

1. A user lands on the platform, clicks **Continue with GitHub**, and is signed in with a session that includes a usable GitHub access token (full `repo` scope).
2. Inside an organization, the user can **Import a project**:
   - **From GitHub** — pick a repo from their GitHub account; the bookmark is created on the server; the paired desktop app exposes a one-click **Clone** action that clones it into `~/crawfish/<org-slug>/<repo>/`.
   - **From local folder** (desktop app only) — pick an existing directory; if its `git remote origin` resolves to a GitHub repo the user has access to, adopt it as-is; otherwise mark it as a local-only project.
3. The web UI reflects every project's `clone_status` (`pending`, `cloning`, `cloned`, `local_only`, `error`) in near-real-time via polling.

Non-goals: server-side clones, multi-device sync, SSH cloning, repo writeback, file generation, analytics, issue sync. All deferred.

## 2. Architecture

```
  Browser (platform SPA)  ──login──►  Clerk (GitHub OAuth, repo scope)
        │                                   │
        │ Bearer JWT                        │ stores GH access token
        ▼                                   ▼
  crawfish-server  ──getOauthToken──►  Clerk API
        │  GET /api/github/repos      (server-side only)
        │  POST /api/orgs/:id/projects
        ▼
  projects.json (per-org, on server disk)
        ▲
        │ poll: GET /api/orgs/:id/projects
        │
  crawfish-app (desktop, paired via deviceLink)
        │ click "Clone" or "Import local folder"
        ▼
  git clone → ~/crawfish/<org-slug>/<repo>/   (clone path)
  -or- adopt existing dir as local_path        (local path)
  PATCH /api/orgs/:id/projects/:pid
```

Trust boundary: the GitHub access token never reaches the browser. The web SPA holds only the Clerk session JWT. The desktop receives the GH token only when it needs it for `git clone`, via a one-shot, device-link-authenticated endpoint.

## 3. Auth — Clerk + GitHub OAuth

- **Clerk dashboard config:** GitHub social connection enabled with scopes `repo read:user user:email`.
- **Login UI** (`crawfish-platform/src/pages/Login.tsx` or the current equivalent): a single "Continue with GitHub" button using Clerk's `<SignIn>`, with all other social/email options hidden. One auth path simplifies edge cases.
- **Server helper** (`crawfish-server/src/lib/github.ts`):

  ```ts
  export async function getGithubToken(userId: string): Promise<string>;
  // Calls clerkClient.users.getUserOauthAccessToken(userId, 'oauth_github').
  // Throws GithubNotConnected if missing or revoked.
  ```

- **Error mapping:** `GithubNotConnected` → HTTP `409 github_disconnected`. Web surfaces a "Reconnect GitHub" pill on every projects screen when it sees this.

Out of scope: re-requesting scopes incrementally (we ask once at login); SSO / org-managed GitHub (Stage 3 concern).

## 4. Data model — `projects.json`

Stored per org at `~/.crawfish/orgs/<org-id>/projects.json` (matches existing on-disk org layout from `crawfish-org` v1).

```json
{
  "projects": [
    {
      "id": "prj_01HXYZ...",
      "name": "crawfish",
      "github_repo": "nealkotval/crawfish",
      "github_repo_id": 123456789,
      "default_branch": "main",
      "private": true,
      "clone_status": "pending",
      "clone_error": null,
      "local_path": null,
      "device_id": null,
      "created_by": "user_clerk_id",
      "created_at": "2026-05-18T12:34:56Z"
    }
  ]
}
```

Field rules:

- `github_repo`, `github_repo_id`, `default_branch`, `private` — **nullable** to allow `local_only` projects with no GitHub remote.
- `github_repo_id` (numeric, not the string `owner/name`) is the stable join key — survives repo renames.
- `clone_status` ∈ { `pending`, `cloning`, `cloned`, `local_only`, `error` }.
- `local_path` and `device_id` are nullable until clone completes or a local folder is adopted.
- `name` is user-editable; defaults to the repo name on import.
- Per-org uniqueness: `(orgId, github_repo_id)` is unique when both are non-null. Two local-only projects with the same `name` are allowed but discouraged in UI.

## 5. Server routes (`crawfish-server/src/routes/projects.ts`, new file)

All routes gated by existing `auth.ts` middleware + a reusable `orgMember(orgId)` check (already present for invites).

| Method + Path | Purpose | Notes |
|---|---|---|
| `GET /api/github/repos?q=&page=` | List repos visible to the user's GH token, paginated. | Proxies `GET https://api.github.com/user/repos?sort=updated&per_page=30`. Per-user 60s cache to soften rate limits. `q` filters client-side on `full_name`. |
| `POST /api/orgs/:orgId/projects` | Create a project bookmark. | Two body shapes — see §5a. Idempotent on `(orgId, github_repo_id)`. |
| `GET /api/orgs/:orgId/projects` | List projects in the org. | Used by web UI + desktop polling. |
| `PATCH /api/orgs/:orgId/projects/:pid` | Desktop reports clone progress. | Body `{ clone_status, local_path?, clone_error?, device_id }`. Auth: the patching device must be paired to a member of the org. |
| `DELETE /api/orgs/:orgId/projects/:pid` | Remove the bookmark. | Does **not** touch the local clone. |
| `GET /api/github/clone-token` | One-shot retrieval of the user's GitHub token over a device-link session. | Returns `{ token, expires_at }`. Token is the Clerk-stored GH OAuth token; expiration mirrors GitHub's. Never callable from the web SPA — requires a device-link session bearer. |
| `GET /api/github/repos/:owner/:name/check` | Verify the authenticated user has access to a specific repo. | Returns `{ id, full_name, default_branch, private }` on success, `404 repo_not_found` if missing/no-access. Used by the desktop's adopt-local flow to confirm before POSTing. |

### 5a. `POST /api/orgs/:orgId/projects` — two body shapes

**Clone path** (initiated from web):

```json
{ "github_repo_id": 123456789, "name": "crawfish" }
```

Server fetches repo metadata from GitHub to fill `github_repo`, `default_branch`, `private`. Creates the project in `clone_status: "pending"`.

**Adopt-local path** (initiated from desktop):

```json
{
  "name": "my-thing",
  "local_path": "/Users/me/code/my-thing",
  "device_id": "dev_...",
  "github_repo_id": 123456789
}
```

`github_repo_id` is optional. If present, the server verifies the user has access to that repo via the GH token before creating the project in `clone_status: "cloned"`. If absent, the project is created in `clone_status: "local_only"`.

## 6. Web UI

Three new surfaces, all under `crawfish-platform/src/pages/`:

- **Login** — single "Continue with GitHub" button. No email fallback in v1.
- **Org → Projects tab** — sibling tab to the existing agent canvas. Lists projects with `name`, `repo` (or "Local only"), `clone_status` badge, and `local_path` when set. Empty state: "Import your first repo." Header has an **Import project** button.
- **Import modal** — two tabs:
  - **From GitHub** — search input + scrollable list backed by `GET /api/github/repos`. Click a row → POST → close → list refreshes with the new card in `pending`.
  - **From local folder** — only enabled when a paired desktop device is detected (via existing `deviceLink` presence). If none paired, shows: *"Open the Crawfish desktop app to import a local folder."* Otherwise the button hands off to the desktop, which opens its native file picker.

Polling: the projects tab calls `GET /api/orgs/:orgId/projects` every 5s while focused, so the desktop's clone progress is reflected without a manual refresh.

## 7. Desktop — clone & adopt executor (`crawfish-app`)

- **Polling:** on launch and every 30s while focused, `GET /api/orgs/:orgId/projects` for every org the device is paired to.
- **Pending projects:** rendered in the desktop's project sidebar with a **Clone** button.
- **Clone flow:**
  1. `PATCH /api/orgs/:orgId/projects/:pid { clone_status: "cloning", device_id }`
  2. `GET /api/github/clone-token` → `{ token }`
  3. Run `git clone https://<token>@github.com/<owner>/<repo>.git ~/crawfish/<org-slug>/<repo>` via `child_process.spawn`. Token is removed from the resulting `origin` URL post-clone (`git remote set-url origin https://github.com/<owner>/<repo>.git`) to avoid persisting it on disk.
  4. On success: `PATCH ... { clone_status: "cloned", local_path, device_id }`.
  5. On failure: `PATCH ... { clone_status: "error", clone_error, device_id }`.
- **Adopt-local flow** (triggered from the desktop UI):
  1. Native file picker → user picks a directory.
  2. Desktop reads `git config --get remote.origin.url` in that directory.
  3. If `origin` resolves to a GitHub repo: desktop calls `GET /api/github/repos/:owner/:name/check` (small server helper) to verify the user has access via their GH token, then `POST` with the adopt-local body shape including `github_repo_id`.
  4. If no `origin`: `POST` adopt-local body without `github_repo_id` → `clone_status: "local_only"`.
  5. If `origin` is GitHub but the user has no access: desktop shows `repo_access_denied` and aborts.

### 7a. Path-collision handling on clone

If `~/crawfish/<org-slug>/<repo>` already exists:

- And is a git repo with `origin` matching the target → mark `cloned`, set `local_path`, skip the clone (adopt).
- And is anything else → `PATCH ... { clone_status: "error", clone_error: "path_conflict" }`. The Clone button becomes "Path conflict — fix manually" with a one-line hint. Renaming/moving the dir is manual for v1.

## 8. Error handling

| Failure | Detection | Surfaced as |
|---|---|---|
| User revoked GitHub in Clerk | Server call to `getGithubToken` throws `GithubNotConnected` | `409 github_disconnected` → web shows "Reconnect GitHub" pill. |
| Repo deleted/renamed on GitHub | `GET /user/repos` no longer returns it; project's `github_repo_id` lookup 404s | Project card shows "Repo not found on GitHub." Bookmark stays so user can delete. |
| Clone auth fails (token expired/invalid) | `git clone` exits non-zero with auth error | Desktop PATCHes `clone_status: "error"`, `clone_error: "auth_expired"`. Web shows reconnect prompt. |
| Path conflict | Existing non-matching directory at target path | `clone_status: "error"`, `clone_error: "path_conflict"`. |
| Adopt-local with no GitHub access | Server's repo-access check returns 404/403 | Desktop shows `repo_access_denied`, does not POST. |
| Network / unknown clone failure | `git clone` exits non-zero, no specific match | `clone_status: "error"`, `clone_error: <last 200 chars of stderr>`. |

## 9. Out of scope (deferred to later specs)

- Webhooks / push from server to desktop (polling is sufficient for v1).
- Generated `ROADMAP.md` / `DESIGN.md` writeback → spec D.
- Per-project board, cycles, analytics — these stay org-scoped for now → specs E and G.
- Multi-device clone (first device that picks up a `pending` project wins).
- SSH-key cloning (HTTPS + ephemeral token only).
- "Reconnect GitHub" without a full re-login (Clerk handles this; no extra UI plumbing yet).
- Importing folders that aren't git repos at all (`git init` from inside Crawfish is a later nicety).
- Bidirectional link between an existing `local_only` project and a later-created GitHub remote (user re-imports for now).

## 10. Testing

- `crawfish-server/tests/projects.test.ts` — POST idempotency on `(orgId, github_repo_id)`; ACL (non-member cannot create/list/patch); PATCH allowed only by a device paired to a member; DELETE removes the bookmark only.
- `crawfish-server/tests/github.test.ts` — `getGithubToken` happy path (Clerk mocked); `GithubNotConnected` → 409 mapping; repo-access check happy/sad paths.
- `crawfish-server/tests/clone-token.test.ts` — `/api/github/clone-token` callable only with a device-link bearer, not a web JWT.
- `e2e/tests/04-platform-projects.spec.ts` — login (Clerk dev mode) → open org → import modal → POST from GitHub tab → card appears in `pending` → simulated desktop PATCH → card flips to `cloned`. Also: simulated `local_only` adoption.

## 11. Files changed

**New:**
- `crawfish-platform/src/pages/Projects.tsx`, `ImportModal.tsx`, `Login.tsx` (or update existing equivalents).
- `crawfish-server/src/routes/projects.ts`
- `crawfish-server/src/lib/github.ts`
- `crawfish-app` desktop additions for the projects sidebar, clone executor, and adopt-local picker.
- `crawfish-server/tests/{projects,github,clone-token}.test.ts`
- `e2e/tests/04-platform-projects.spec.ts`

**Edited (lead-only per `CLAUDE.md`):**
- `crawfish-server/src/index.ts` — register `projects.ts` routes.
- `crawfish-platform/src/Shell.tsx` — add Projects tab to the org route.
- Clerk dashboard config (out-of-repo) — enable GitHub connection with `repo read:user user:email`.

## 12. Open questions

None blocking. Two flagged for follow-up specs:

- **Desktop discovery from the web UI** — current design assumes the existing `deviceLink` presence signal is good enough to enable/disable the "From local folder" tab. If that signal proves unreliable, spec C (bridge) will revisit.
- **Token refresh** — Clerk currently does not refresh GitHub OAuth tokens; if a token is revoked or expires, the user re-logs in. Acceptable for v1; revisit if we see real friction.
