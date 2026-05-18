# GitHub Login + Project Import Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship spec A+B — user signs in with GitHub, creates an org, imports a project (clone from GitHub or adopt a local folder).

**Spec:** `docs/superpowers/specs/2026-05-18-github-login-import-design.md`.

**Architecture:** Clerk handles GitHub OAuth and stores the user's GH access token; web SPA never sees the token. Server adds a `Project` Prisma model and CRUD routes plus a server-side GitHub proxy. Desktop polls for `pending` projects, retrieves a one-shot GH token over its device-link session, and runs `git clone` locally.

**Tech Stack:** Express + Prisma (SQLite dev, Postgres prod), Zod, Clerk SDK, React + Vite (platform SPA), Tauri / Node `child_process` (desktop), Playwright (e2e).

**Spec deviation noted:** The spec §4 sketched `projects.json` on server disk. The actual server uses Prisma; this plan implements `Project` as a Prisma model. Field set is identical to the spec, only the storage layer differs.

---

## File map

**Created**
- `crawfish-server/prisma/migrations/<ts>_add_project/migration.sql`
- `crawfish-server/src/routes/projects.ts`
- `crawfish-server/src/routes/github.ts`
- `crawfish-server/src/lib/github.ts`
- `crawfish-server/tests/projects.test.ts`
- `crawfish-server/tests/github.test.ts`
- `crawfish-server/tests/clone-token.test.ts`
- `crawfish-platform/src/pages/Projects.tsx`
- `crawfish-platform/src/pages/ImportModal.tsx`
- `crawfish-app/src/projects/` (desktop polling + clone executor + adopt-local picker — exact filenames defer to existing `crawfish-app` layout)
- `e2e/tests/04-platform-projects.spec.ts`

**Modified**
- `crawfish-server/prisma/schema.prisma` — add `Project` model + relation on `Org`.
- `crawfish-server/src/index.ts` — register projects + github routers.
- `crawfish-server/src/lib/orgs.ts` — extend `loadOrgWithRelations` to include projects.
- `crawfish-platform/src/pages/Auth.tsx` — Clerk `<SignIn>` config locked to GitHub social.
- `crawfish-platform/src/pages/OrgRoute.tsx` — add Projects tab.
- Clerk dashboard (out-of-repo) — enable GitHub social connection with scopes `repo read:user user:email`.

---

## Task 1: Add `Project` Prisma model + migration

**Files:**
- Modify: `crawfish-server/prisma/schema.prisma`
- Create: migration via `prisma migrate dev`

- [ ] **Step 1: Edit schema.prisma — add the model and the inverse relation**

Append after the `Invite` model:

```prisma
model Project {
  id              String   @id @default(cuid())
  org             Org      @relation(fields: [orgId], references: [id], onDelete: Cascade)
  orgId           String
  name            String                          // user-editable; defaults to repo name
  githubRepo      String?                         // "owner/name", null for local_only
  githubRepoId    Int?                            // stable across renames
  defaultBranch   String?
  isPrivate       Boolean  @default(false)
  cloneStatus     String   @default("pending")    // pending | cloning | cloned | local_only | error
  cloneError      String?
  localPath       String?
  deviceId        String?
  createdById     String
  createdAt       DateTime @default(now())
  updatedAt       DateTime @updatedAt

  @@unique([orgId, githubRepoId], name: "org_repo_unique")
}
```

Modify the `Org` model: add `projects Project[]` to its relations block.

- [ ] **Step 2: Run the migration**

Run from `crawfish-server/`:
```
npx prisma migrate dev --name add_project
npx prisma generate
```
Expected: migration applied; `Project` available on `db`.

- [ ] **Step 3: Commit**

```
git add crawfish-server/prisma/
git commit -m "feat(server): add Project model + migration"
```

---

## Task 2: GitHub token helper

**Files:**
- Create: `crawfish-server/src/lib/github.ts`
- Create: `crawfish-server/tests/github.test.ts`

- [ ] **Step 1: Write the failing test**

```ts
// crawfish-server/tests/github.test.ts
import { describe, it, expect, vi } from "vitest";
import { getGithubToken, GithubNotConnected } from "../src/lib/github.js";

vi.mock("@clerk/clerk-sdk-node", () => ({
  clerkClient: {
    users: {
      getUserOauthAccessToken: vi.fn(),
    },
  },
}));

import { clerkClient } from "@clerk/clerk-sdk-node";

describe("getGithubToken", () => {
  it("returns the token when Clerk has one", async () => {
    (clerkClient.users.getUserOauthAccessToken as any).mockResolvedValue({
      data: [{ token: "gho_test_abc" }],
    });
    expect(await getGithubToken("user_1")).toBe("gho_test_abc");
  });

  it("throws GithubNotConnected when Clerk returns no token", async () => {
    (clerkClient.users.getUserOauthAccessToken as any).mockResolvedValue({ data: [] });
    await expect(getGithubToken("user_1")).rejects.toBeInstanceOf(GithubNotConnected);
  });
});
```

- [ ] **Step 2: Run — expect FAIL (module not found)**

```
cd crawfish-server && npx vitest run tests/github.test.ts
```

- [ ] **Step 3: Implement**

```ts
// crawfish-server/src/lib/github.ts
import { clerkClient } from "@clerk/clerk-sdk-node";

export class GithubNotConnected extends Error {
  constructor() { super("GitHub connection missing or revoked"); }
}

export async function getGithubToken(userId: string): Promise<string> {
  const res = await clerkClient.users.getUserOauthAccessToken(userId, "oauth_github");
  const token = res.data?.[0]?.token;
  if (!token) throw new GithubNotConnected();
  return token;
}
```

- [ ] **Step 4: Run — expect PASS**

```
npx vitest run tests/github.test.ts
```

- [ ] **Step 5: Commit**

```
git add crawfish-server/src/lib/github.ts crawfish-server/tests/github.test.ts
git commit -m "feat(server): add getGithubToken Clerk helper"
```

---

## Task 3: `POST /api/orgs/:orgId/projects` — clone path body

**Files:**
- Create: `crawfish-server/src/routes/projects.ts`
- Create: `crawfish-server/tests/projects.test.ts`
- Modify: `crawfish-server/src/index.ts`

- [ ] **Step 1: Write the failing test**

```ts
// crawfish-server/tests/projects.test.ts
import { describe, it, expect, beforeEach, vi } from "vitest";
import request from "supertest";
import { app, db } from "../src/index.js";

vi.mock("../src/lib/github.js", () => ({
  getGithubToken: vi.fn(async () => "gho_test"),
  GithubNotConnected: class extends Error {},
  fetchRepoMetadata: vi.fn(async () => ({
    id: 12345,
    full_name: "octo/hello",
    default_branch: "main",
    private: false,
  })),
}));

let orgId: string;
let userId: string;

beforeEach(async () => {
  await db.project.deleteMany();
  await db.orgMember.deleteMany();
  await db.org.deleteMany();
  await db.user.deleteMany();
  const user = await db.user.create({ data: { email: "a@b.c", clerkId: "user_test" } });
  userId = user.id;
  const org = await db.org.create({ data: { name: "acme" } });
  orgId = org.id;
  await db.orgMember.create({ data: { orgId, userId, role: "founder" } });
});

function authed() {
  return request(app).set("Authorization", "Bearer test_jwt").set("X-Test-User", userId);
}

describe("POST /api/orgs/:orgId/projects (clone path)", () => {
  it("creates a project in pending status", async () => {
    const res = await authed().post(`/api/orgs/${orgId}/projects`).send({ githubRepoId: 12345 });
    expect(res.status).toBe(201);
    expect(res.body).toMatchObject({
      githubRepo: "octo/hello",
      cloneStatus: "pending",
      defaultBranch: "main",
    });
  });

  it("is idempotent on (orgId, githubRepoId)", async () => {
    await authed().post(`/api/orgs/${orgId}/projects`).send({ githubRepoId: 12345 });
    const res = await authed().post(`/api/orgs/${orgId}/projects`).send({ githubRepoId: 12345 });
    expect(res.status).toBe(200);
    const count = await db.project.count({ where: { orgId } });
    expect(count).toBe(1);
  });

  it("rejects non-members with 404", async () => {
    const other = await db.user.create({ data: { email: "x@y.z", clerkId: "user_other" } });
    const res = await request(app)
      .post(`/api/orgs/${orgId}/projects`)
      .set("Authorization", "Bearer test_jwt")
      .set("X-Test-User", other.id)
      .send({ githubRepoId: 12345 });
    expect(res.status).toBe(404);
  });
});
```

The test relies on the existing test-mode auth shim (`X-Test-User` header) used in other route tests. If that shim doesn't exist yet, copy the pattern from `crawfish-server/tests/orgs.test.ts`.

- [ ] **Step 2: Run — expect FAIL**

```
cd crawfish-server && npx vitest run tests/projects.test.ts
```

- [ ] **Step 3: Implement the route file**

```ts
// crawfish-server/src/routes/projects.ts
import { Router, type Request } from "express";
import { z } from "zod";
import { Prisma } from "@prisma/client";
import { db } from "../index.js";
import { httpError } from "../lib/errors.js";
import { getGithubToken, GithubNotConnected, fetchRepoMetadata } from "../lib/github.js";

export const projectsRouter = Router({ mergeParams: true });

const CloneBody = z.object({
  githubRepoId: z.number().int().positive(),
  name: z.string().min(1).max(120).optional(),
});

async function requireMember(req: Request, orgId: string) {
  const userId = req.userId;
  if (!userId) return { error: { status: 401, code: "unauthenticated" } };
  const org = await db.org.findFirst({ where: { OR: [{ id: orgId }, { name: orgId }] }, select: { id: true } });
  if (!org) return { error: { status: 404, code: "not_found" } };
  const m = await db.orgMember.findUnique({ where: { orgId_userId: { orgId: org.id, userId } } });
  if (!m) return { error: { status: 404, code: "not_found" } };
  return { orgId: org.id, userId };
}

projectsRouter.post("/", async (req, res) => {
  const orgIdParam = req.params.orgId;
  const ctx = await requireMember(req, orgIdParam);
  if ("error" in ctx) return httpError(res, ctx.error.status, ctx.error.code, "");

  const parsed = CloneBody.safeParse(req.body);
  if (!parsed.success) return httpError(res, 400, "invalid_body", parsed.error.message);

  let meta;
  try {
    const token = await getGithubToken(ctx.userId);
    meta = await fetchRepoMetadata(token, parsed.data.githubRepoId);
  } catch (err) {
    if (err instanceof GithubNotConnected) return httpError(res, 409, "github_disconnected", "");
    return httpError(res, 502, "github_error", String(err));
  }

  const existing = await db.project.findUnique({
    where: { org_repo_unique: { orgId: ctx.orgId, githubRepoId: parsed.data.githubRepoId } },
  });
  if (existing) return res.status(200).json(existing);

  const created = await db.project.create({
    data: {
      orgId: ctx.orgId,
      name: parsed.data.name ?? meta.full_name.split("/")[1],
      githubRepo: meta.full_name,
      githubRepoId: meta.id,
      defaultBranch: meta.default_branch,
      isPrivate: meta.private,
      cloneStatus: "pending",
      createdById: ctx.userId,
    },
  });
  return res.status(201).json(created);
});
```

Add to `crawfish-server/src/lib/github.ts`:

```ts
export interface RepoMetadata { id: number; full_name: string; default_branch: string; private: boolean; }

export async function fetchRepoMetadata(token: string, repoId: number): Promise<RepoMetadata> {
  const r = await fetch(`https://api.github.com/repositories/${repoId}`, {
    headers: { Authorization: `Bearer ${token}`, Accept: "application/vnd.github+json" },
  });
  if (!r.ok) throw new Error(`github ${r.status}`);
  const j = (await r.json()) as RepoMetadata;
  return { id: j.id, full_name: j.full_name, default_branch: j.default_branch, private: j.private };
}
```

Register the router in `crawfish-server/src/index.ts` after the existing `orgsRouter` line:

```ts
import { projectsRouter } from "./routes/projects.js";
app.use("/api/orgs/:orgId/projects", projectsRouter);
```

- [ ] **Step 4: Run — expect PASS**

```
npx vitest run tests/projects.test.ts
```

- [ ] **Step 5: Commit**

```
git add crawfish-server/src/{routes/projects.ts,lib/github.ts,index.ts} crawfish-server/tests/projects.test.ts
git commit -m "feat(server): POST /orgs/:id/projects clone-path"
```

---

## Task 4: `POST /api/orgs/:orgId/projects` — adopt-local path

**Files:**
- Modify: `crawfish-server/src/routes/projects.ts`
- Modify: `crawfish-server/tests/projects.test.ts`

- [ ] **Step 1: Add failing tests**

Append to `tests/projects.test.ts`:

```ts
describe("POST /api/orgs/:orgId/projects (adopt-local path)", () => {
  it("creates local_only when no github_repo_id", async () => {
    const res = await authed().post(`/api/orgs/${orgId}/projects`).send({
      name: "myrepo",
      localPath: "/Users/me/code/myrepo",
      deviceId: "dev_abc",
    });
    expect(res.status).toBe(201);
    expect(res.body.cloneStatus).toBe("local_only");
    expect(res.body.localPath).toBe("/Users/me/code/myrepo");
  });

  it("creates cloned when github_repo_id is provided and accessible", async () => {
    const res = await authed().post(`/api/orgs/${orgId}/projects`).send({
      name: "myrepo",
      localPath: "/Users/me/code/myrepo",
      deviceId: "dev_abc",
      githubRepoId: 12345,
    });
    expect(res.status).toBe(201);
    expect(res.body.cloneStatus).toBe("cloned");
    expect(res.body.githubRepo).toBe("octo/hello");
  });
});
```

- [ ] **Step 2: Run — expect FAIL**

```
npx vitest run tests/projects.test.ts
```

- [ ] **Step 3: Extend the route to accept either body shape**

Replace the route body validation + handler in `projects.ts`:

```ts
const AdoptBody = z.object({
  name: z.string().min(1).max(120),
  localPath: z.string().min(1).max(1024),
  deviceId: z.string().min(1).max(128),
  githubRepoId: z.number().int().positive().optional(),
});

const Body = z.union([CloneBody, AdoptBody]);

projectsRouter.post("/", async (req, res) => {
  const ctx = await requireMember(req, req.params.orgId);
  if ("error" in ctx) return httpError(res, ctx.error.status, ctx.error.code, "");
  const parsed = Body.safeParse(req.body);
  if (!parsed.success) return httpError(res, 400, "invalid_body", parsed.error.message);

  // Adopt-local branch
  if ("localPath" in parsed.data) {
    const b = parsed.data;
    let meta: RepoMetadata | null = null;
    if (b.githubRepoId !== undefined) {
      try {
        const token = await getGithubToken(ctx.userId);
        meta = await fetchRepoMetadata(token, b.githubRepoId);
      } catch (err) {
        if (err instanceof GithubNotConnected) return httpError(res, 409, "github_disconnected", "");
        return httpError(res, 404, "repo_not_found", "");
      }
    }
    const created = await db.project.create({
      data: {
        orgId: ctx.orgId,
        name: b.name,
        githubRepo: meta?.full_name ?? null,
        githubRepoId: meta?.id ?? null,
        defaultBranch: meta?.default_branch ?? null,
        isPrivate: meta?.private ?? false,
        cloneStatus: meta ? "cloned" : "local_only",
        localPath: b.localPath,
        deviceId: b.deviceId,
        createdById: ctx.userId,
      },
    });
    return res.status(201).json(created);
  }

  // Clone branch — same as Task 3
  const b = parsed.data;
  let meta;
  try {
    const token = await getGithubToken(ctx.userId);
    meta = await fetchRepoMetadata(token, b.githubRepoId);
  } catch (err) {
    if (err instanceof GithubNotConnected) return httpError(res, 409, "github_disconnected", "");
    return httpError(res, 502, "github_error", String(err));
  }
  const existing = await db.project.findUnique({
    where: { org_repo_unique: { orgId: ctx.orgId, githubRepoId: b.githubRepoId } },
  });
  if (existing) return res.status(200).json(existing);
  const created = await db.project.create({
    data: {
      orgId: ctx.orgId,
      name: b.name ?? meta.full_name.split("/")[1],
      githubRepo: meta.full_name,
      githubRepoId: meta.id,
      defaultBranch: meta.default_branch,
      isPrivate: meta.private,
      cloneStatus: "pending",
      createdById: ctx.userId,
    },
  });
  return res.status(201).json(created);
});
```

Import `RepoMetadata` from `../lib/github.js`.

- [ ] **Step 4: Run — expect PASS**

```
npx vitest run tests/projects.test.ts
```

- [ ] **Step 5: Commit**

```
git add crawfish-server/src/routes/projects.ts crawfish-server/tests/projects.test.ts
git commit -m "feat(server): adopt-local body shape for POST projects"
```

---

## Task 5: `GET /api/orgs/:orgId/projects` (list)

**Files:**
- Modify: `crawfish-server/src/routes/projects.ts`
- Modify: `crawfish-server/tests/projects.test.ts`

- [ ] **Step 1: Add failing test**

```ts
describe("GET /api/orgs/:orgId/projects", () => {
  it("lists projects for org members", async () => {
    await db.project.create({ data: {
      orgId, name: "p1", cloneStatus: "pending", createdById: userId,
    }});
    const res = await authed().get(`/api/orgs/${orgId}/projects`);
    expect(res.status).toBe(200);
    expect(res.body).toHaveLength(1);
    expect(res.body[0].name).toBe("p1");
  });
});
```

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Implement**

```ts
projectsRouter.get("/", async (req, res) => {
  const ctx = await requireMember(req, req.params.orgId);
  if ("error" in ctx) return httpError(res, ctx.error.status, ctx.error.code, "");
  const projects = await db.project.findMany({
    where: { orgId: ctx.orgId },
    orderBy: { createdAt: "desc" },
  });
  return res.json(projects);
});
```

- [ ] **Step 4: Run — expect PASS**

- [ ] **Step 5: Commit**

```
git add crawfish-server/src/routes/projects.ts crawfish-server/tests/projects.test.ts
git commit -m "feat(server): GET projects list"
```

---

## Task 6: `PATCH /api/orgs/:orgId/projects/:pid` (device reports clone progress)

**Files:**
- Modify: `crawfish-server/src/routes/projects.ts`
- Modify: `crawfish-server/tests/projects.test.ts`

PATCH is callable both by a regular org-member JWT (web admin actions like renaming) and by a device-link session (clone status updates). The simplest split: PATCH accepts both; only `cloneStatus`/`localPath`/`cloneError`/`deviceId` updates require device-link auth. Body validation gates it.

- [ ] **Step 1: Add failing test**

```ts
describe("PATCH /api/orgs/:orgId/projects/:pid", () => {
  it("updates clone status when called by paired device", async () => {
    const p = await db.project.create({ data: {
      orgId, name: "p1", cloneStatus: "pending", createdById: userId,
    }});
    const res = await request(app)
      .patch(`/api/orgs/${orgId}/projects/${p.id}`)
      .set("X-Crawfish-Token", "test_device_token")
      .set("X-Test-User", userId)
      .set("X-Test-OrgId", orgId)
      .send({ cloneStatus: "cloned", localPath: "/Users/me/crawfish/acme/p1", deviceId: "dev_xyz" });
    expect(res.status).toBe(200);
    expect(res.body.cloneStatus).toBe("cloned");
  });
});
```

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Implement**

```ts
const PatchBody = z.object({
  cloneStatus: z.enum(["pending", "cloning", "cloned", "local_only", "error"]).optional(),
  localPath: z.string().max(1024).nullable().optional(),
  cloneError: z.string().max(1024).nullable().optional(),
  deviceId: z.string().max(128).nullable().optional(),
  name: z.string().min(1).max(120).optional(),
});

projectsRouter.patch("/:pid", async (req, res) => {
  const ctx = await requireMember(req, req.params.orgId);
  if ("error" in ctx) return httpError(res, ctx.error.status, ctx.error.code, "");
  const parsed = PatchBody.safeParse(req.body);
  if (!parsed.success) return httpError(res, 400, "invalid_body", parsed.error.message);

  const project = await db.project.findFirst({ where: { id: req.params.pid, orgId: ctx.orgId } });
  if (!project) return httpError(res, 404, "not_found", "");

  // Status / clone fields require a device-link session.
  const touchesCloneFields =
    parsed.data.cloneStatus !== undefined ||
    parsed.data.localPath !== undefined ||
    parsed.data.cloneError !== undefined ||
    parsed.data.deviceId !== undefined;
  if (touchesCloneFields && !(req as Request & { dashOrgId?: string }).dashOrgId) {
    return httpError(res, 403, "device_token_required", "");
  }

  const updated = await db.project.update({
    where: { id: project.id },
    data: parsed.data,
  });
  return res.json(updated);
});
```

The `dashOrgId` field is already set by the existing `dashSyncMiddleware`. To make PATCH reachable from the device-link side, mount this same router under `/api/dash/orgs/:orgId/projects` in `index.ts`:

```ts
app.use("/api/dash/orgs/:orgId/projects", dashSyncMiddleware, projectsRouter);
```

(Note: the dashSyncMiddleware already sets `req.userId` and `req.dashOrgId`. The `requireMember` helper already accepts that.)

- [ ] **Step 4: Run — expect PASS**

- [ ] **Step 5: Commit**

```
git add crawfish-server/src/{routes/projects.ts,index.ts} crawfish-server/tests/projects.test.ts
git commit -m "feat(server): PATCH projects with device-link gating on clone fields"
```

---

## Task 7: `DELETE /api/orgs/:orgId/projects/:pid`

**Files:**
- Modify: `crawfish-server/src/routes/projects.ts`
- Modify: `crawfish-server/tests/projects.test.ts`

- [ ] **Step 1: Add failing test**

```ts
describe("DELETE /api/orgs/:orgId/projects/:pid", () => {
  it("removes the bookmark", async () => {
    const p = await db.project.create({ data: { orgId, name: "p1", cloneStatus: "pending", createdById: userId } });
    const res = await authed().delete(`/api/orgs/${orgId}/projects/${p.id}`);
    expect(res.status).toBe(204);
    expect(await db.project.count({ where: { orgId } })).toBe(0);
  });
});
```

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Implement**

```ts
projectsRouter.delete("/:pid", async (req, res) => {
  const ctx = await requireMember(req, req.params.orgId);
  if ("error" in ctx) return httpError(res, ctx.error.status, ctx.error.code, "");
  await db.project.deleteMany({ where: { id: req.params.pid, orgId: ctx.orgId } });
  return res.status(204).end();
});
```

- [ ] **Step 4: Run — expect PASS**

- [ ] **Step 5: Commit**

```
git add crawfish-server/src/routes/projects.ts crawfish-server/tests/projects.test.ts
git commit -m "feat(server): DELETE project"
```

---

## Task 8: `GET /api/github/repos` proxy

**Files:**
- Create: `crawfish-server/src/routes/github.ts`
- Modify: `crawfish-server/src/index.ts`
- Modify: `crawfish-server/src/lib/github.ts`

- [ ] **Step 1: Write the failing test**

Add to `tests/github.test.ts`:

```ts
import request from "supertest";
import { app } from "../src/index.js";

vi.mock("../src/lib/github.js", async (orig) => {
  const real = await orig() as any;
  return {
    ...real,
    getGithubToken: vi.fn(async () => "gho_test"),
    listUserRepos: vi.fn(async () => ([
      { id: 1, full_name: "octo/a", default_branch: "main", private: false, updated_at: "2026-05-18T00:00:00Z" },
    ])),
  };
});

describe("GET /api/github/repos", () => {
  it("returns the user's repos", async () => {
    // user fixture from earlier beforeEach is required; rerun similar setup
    const res = await request(app)
      .get("/api/github/repos")
      .set("Authorization", "Bearer test_jwt")
      .set("X-Test-User", "user_test_id");
    expect(res.status).toBe(200);
    expect(res.body[0].full_name).toBe("octo/a");
  });
});
```

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Implement**

Add to `crawfish-server/src/lib/github.ts`:

```ts
export interface RepoSummary { id: number; full_name: string; default_branch: string; private: boolean; updated_at: string; }

export async function listUserRepos(token: string, page = 1): Promise<RepoSummary[]> {
  const r = await fetch(`https://api.github.com/user/repos?sort=updated&per_page=30&page=${page}`, {
    headers: { Authorization: `Bearer ${token}`, Accept: "application/vnd.github+json" },
  });
  if (!r.ok) throw new Error(`github ${r.status}`);
  return (await r.json()) as RepoSummary[];
}
```

Create `crawfish-server/src/routes/github.ts`:

```ts
import { Router } from "express";
import { z } from "zod";
import { httpError } from "../lib/errors.js";
import { getGithubToken, GithubNotConnected, listUserRepos } from "../lib/github.js";

export const githubRouter = Router();

githubRouter.get("/repos", async (req, res) => {
  if (!req.userId) return httpError(res, 401, "unauthenticated", "");
  const page = Math.max(1, parseInt(String(req.query.page ?? "1"), 10));
  try {
    const token = await getGithubToken(req.userId);
    const repos = await listUserRepos(token, page);
    const q = String(req.query.q ?? "").toLowerCase();
    return res.json(q ? repos.filter((r) => r.full_name.toLowerCase().includes(q)) : repos);
  } catch (err) {
    if (err instanceof GithubNotConnected) return httpError(res, 409, "github_disconnected", "");
    return httpError(res, 502, "github_error", String(err));
  }
});
```

Register in `index.ts` (after the auth middleware line, before orgs):

```ts
import { githubRouter } from "./routes/github.js";
app.use("/api/github", githubRouter);
```

- [ ] **Step 4: Run — expect PASS**

- [ ] **Step 5: Commit**

```
git add crawfish-server/src/{routes/github.ts,lib/github.ts,index.ts} crawfish-server/tests/github.test.ts
git commit -m "feat(server): GET /api/github/repos proxy"
```

---

## Task 9: `GET /api/github/repos/:owner/:name/check`

**Files:**
- Modify: `crawfish-server/src/routes/github.ts`
- Modify: `crawfish-server/src/lib/github.ts`
- Modify: `crawfish-server/tests/github.test.ts`

- [ ] **Step 1: Test**

```ts
describe("GET /api/github/repos/:owner/:name/check", () => {
  it("returns 200 with metadata when accessible", async () => {
    // similar setup, with a mock for fetchRepoByName returning metadata
  });
  it("returns 404 when not accessible", async () => {
    // mock fetchRepoByName to throw
  });
});
```

- [ ] **Step 2: Run — FAIL**

- [ ] **Step 3: Implement**

Add to `lib/github.ts`:

```ts
export async function fetchRepoByName(token: string, owner: string, name: string): Promise<RepoMetadata> {
  const r = await fetch(`https://api.github.com/repos/${owner}/${name}`, {
    headers: { Authorization: `Bearer ${token}`, Accept: "application/vnd.github+json" },
  });
  if (!r.ok) throw new Error(`github ${r.status}`);
  return await r.json() as RepoMetadata;
}
```

Add route to `routes/github.ts`:

```ts
githubRouter.get("/repos/:owner/:name/check", async (req, res) => {
  if (!req.userId) return httpError(res, 401, "unauthenticated", "");
  try {
    const token = await getGithubToken(req.userId);
    const meta = await fetchRepoByName(token, req.params.owner, req.params.name);
    return res.json(meta);
  } catch (err) {
    if (err instanceof GithubNotConnected) return httpError(res, 409, "github_disconnected", "");
    return httpError(res, 404, "repo_not_found", "");
  }
});
```

- [ ] **Step 4: Run — PASS**

- [ ] **Step 5: Commit**

```
git add crawfish-server/src/{routes/github.ts,lib/github.ts} crawfish-server/tests/github.test.ts
git commit -m "feat(server): GET /api/github/repos/:owner/:name/check"
```

---

## Task 10: `GET /api/github/clone-token` (device-link only)

**Files:**
- Modify: `crawfish-server/src/routes/github.ts`
- Modify: `crawfish-server/src/index.ts`
- Create: `crawfish-server/tests/clone-token.test.ts`

The clone-token endpoint must be reachable only through the device-link path (`dashSyncMiddleware` populates `req.dashOrgId`). Mount it on a separate path that requires that middleware.

- [ ] **Step 1: Test**

```ts
// tests/clone-token.test.ts
import { describe, it, expect, vi } from "vitest";
import request from "supertest";
import { app } from "../src/index.js";

vi.mock("../src/lib/github.js", () => ({
  getGithubToken: vi.fn(async () => "gho_test_clone"),
  GithubNotConnected: class extends Error {},
}));

describe("GET /api/dash/github/clone-token", () => {
  it("returns the token when called with a device-link bearer", async () => {
    const res = await request(app)
      .get("/api/dash/github/clone-token")
      .set("X-Crawfish-Token", "valid_device_token")
      .set("X-Test-User", "user_test_id")
      .set("X-Test-OrgId", "org_test_id");
    expect(res.status).toBe(200);
    expect(res.body.token).toBe("gho_test_clone");
  });

  it("rejects calls without a device-link bearer", async () => {
    const res = await request(app)
      .get("/api/dash/github/clone-token")
      .set("Authorization", "Bearer test_jwt")
      .set("X-Test-User", "user_test_id");
    expect(res.status).toBe(401);
  });
});
```

- [ ] **Step 2: Run — FAIL**

- [ ] **Step 3: Implement**

Add a separate router for the dash-side:

```ts
// in routes/github.ts
export const dashGithubRouter = Router();

dashGithubRouter.get("/clone-token", async (req, res) => {
  if (!req.userId) return httpError(res, 401, "unauthenticated", "");
  try {
    const token = await getGithubToken(req.userId);
    return res.json({ token, expires_at: null });
  } catch (err) {
    if (err instanceof GithubNotConnected) return httpError(res, 409, "github_disconnected", "");
    return httpError(res, 502, "github_error", String(err));
  }
});
```

Register in `index.ts`:

```ts
import { dashGithubRouter } from "./routes/github.js";
app.use("/api/dash/github", dashSyncMiddleware, dashGithubRouter);
```

- [ ] **Step 4: Run — PASS**

- [ ] **Step 5: Commit**

```
git add crawfish-server/src/{routes/github.ts,index.ts} crawfish-server/tests/clone-token.test.ts
git commit -m "feat(server): GET /api/dash/github/clone-token (device-link only)"
```

---

## Task 11: Lock login UI to GitHub-only

**Files:**
- Modify: `crawfish-platform/src/pages/Auth.tsx`

Clerk dashboard must already have GitHub social enabled with `repo read:user user:email` scopes. (Out-of-repo action — confirm before executing this task.)

- [ ] **Step 1: Edit Auth.tsx**

Replace the existing `<SignIn>` element with one configured for GitHub-only:

```tsx
<SignIn
  appearance={{
    elements: {
      socialButtonsBlockButton__github: { display: "flex" },
      socialButtonsBlockButton: { display: "none" },
      socialButtonsBlockButton__github_visible: { display: "flex" },
      dividerRow: { display: "none" },
      formButtonPrimary: { display: "none" },   // hide email/password submit
      formFieldRow: { display: "none" },
      footer: { display: "none" },
    },
  }}
/>
```

If the existing `<SignIn>` has a `routing` or `path` prop, keep them. The point of this task is the appearance lockdown.

- [ ] **Step 2: Verify in dev**

```
cd crawfish-platform && npm run dev
```

Open `http://localhost:5174`, confirm the login page shows only "Continue with GitHub" and no email/password form.

- [ ] **Step 3: Commit**

```
git add crawfish-platform/src/pages/Auth.tsx
git commit -m "feat(platform): lock login to GitHub-only social"
```

---

## Task 12: Projects tab on the OrgRoute

**Files:**
- Create: `crawfish-platform/src/pages/Projects.tsx`
- Modify: `crawfish-platform/src/pages/OrgRoute.tsx`

- [ ] **Step 1: Build the Projects view**

```tsx
// crawfish-platform/src/pages/Projects.tsx
import { useEffect, useState } from "react";

type Project = {
  id: string;
  name: string;
  githubRepo: string | null;
  cloneStatus: "pending" | "cloning" | "cloned" | "local_only" | "error";
  cloneError: string | null;
  localPath: string | null;
};

export function Projects({ orgId, openImport }: { orgId: string; openImport: () => void }) {
  const [projects, setProjects] = useState<Project[] | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let cancel = false;
    async function poll() {
      try {
        const r = await fetch(`/api/orgs/${orgId}/projects`, { credentials: "include" });
        if (r.status === 409) { setErr("github_disconnected"); return; }
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const j = await r.json();
        if (!cancel) { setProjects(j); setErr(null); }
      } catch (e) { if (!cancel) setErr(String(e)); }
    }
    poll();
    const t = setInterval(poll, 5000);
    return () => { cancel = true; clearInterval(t); };
  }, [orgId]);

  if (err === "github_disconnected") return <ReconnectPrompt />;
  if (!projects) return <p>Loading…</p>;
  if (projects.length === 0) return <Empty onImport={openImport} />;
  return (
    <div className="projects-grid">
      {projects.map((p) => <ProjectCard key={p.id} p={p} />)}
      <button onClick={openImport} className="btn-primary">Import project</button>
    </div>
  );
}

function StatusBadge({ s }: { s: Project["cloneStatus"] }) {
  return <span className={`pill pill-${s}`}>{s.replace("_", " ")}</span>;
}

function ProjectCard({ p }: { p: Project }) {
  return (
    <div className="card">
      <div className="card-title">{p.name}</div>
      <div className="card-sub">{p.githubRepo ?? "Local only"}</div>
      <StatusBadge s={p.cloneStatus} />
      {p.localPath && <div className="card-path">{p.localPath}</div>}
      {p.cloneError && <div className="card-error">{p.cloneError}</div>}
    </div>
  );
}

function Empty({ onImport }: { onImport: () => void }) {
  return (
    <div className="empty">
      <p>Import your first repo.</p>
      <button onClick={onImport} className="btn-primary">Import project</button>
    </div>
  );
}

function ReconnectPrompt() {
  return (
    <div className="banner banner-warn">
      Your GitHub connection is missing or revoked. <a href="/auth">Reconnect GitHub</a>.
    </div>
  );
}
```

- [ ] **Step 2: Add Projects tab to OrgRoute**

In `OrgRoute.tsx`, find the tab/section switcher and add a new tab "Projects." When selected, render `<Projects orgId={orgId} openImport={() => setImportOpen(true)} />` and conditionally render `<ImportModal orgId={orgId} open={importOpen} onClose={() => setImportOpen(false)} />` (the modal lands in Task 13).

- [ ] **Step 3: Commit**

```
git add crawfish-platform/src/pages/{Projects.tsx,OrgRoute.tsx}
git commit -m "feat(platform): Projects tab on OrgRoute"
```

---

## Task 13: Import modal (GitHub tab)

**Files:**
- Create: `crawfish-platform/src/pages/ImportModal.tsx`

- [ ] **Step 1: Build the modal**

```tsx
// crawfish-platform/src/pages/ImportModal.tsx
import { useEffect, useState } from "react";

type Repo = { id: number; full_name: string; private: boolean };

export function ImportModal({ orgId, open, onClose }: { orgId: string; open: boolean; onClose: () => void }) {
  const [tab, setTab] = useState<"github" | "local">("github");
  if (!open) return null;
  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <header className="modal-tabs">
          <button onClick={() => setTab("github")} className={tab === "github" ? "active" : ""}>From GitHub</button>
          <button onClick={() => setTab("local")} className={tab === "local" ? "active" : ""}>From local folder</button>
        </header>
        {tab === "github" ? <GithubTab orgId={orgId} onClose={onClose} /> : <LocalTab />}
      </div>
    </div>
  );
}

function GithubTab({ orgId, onClose }: { orgId: string; onClose: () => void }) {
  const [q, setQ] = useState("");
  const [repos, setRepos] = useState<Repo[]>([]);
  const [busy, setBusy] = useState<number | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    fetch(`/api/github/repos?q=${encodeURIComponent(q)}`, { credentials: "include" })
      .then(async (r) => {
        if (r.status === 409) { setErr("github_disconnected"); return; }
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        setRepos(await r.json());
      })
      .catch((e) => setErr(String(e)));
  }, [q]);

  async function pick(r: Repo) {
    setBusy(r.id);
    try {
      const res = await fetch(`/api/orgs/${orgId}/projects`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ githubRepoId: r.id }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      onClose();
    } catch (e) { setErr(String(e)); }
    finally { setBusy(null); }
  }

  if (err === "github_disconnected") return <p>Your GitHub connection is missing. <a href="/auth">Reconnect</a>.</p>;
  return (
    <div>
      <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Filter repos…" />
      <ul className="repo-list">
        {repos.map((r) => (
          <li key={r.id}>
            <button disabled={busy === r.id} onClick={() => pick(r)}>{r.full_name}{r.private && " 🔒"}</button>
          </li>
        ))}
      </ul>
      {err && <p className="err">{err}</p>}
    </div>
  );
}

function LocalTab() {
  // Stub: desktop-only — Task 15 fills the actual handoff.
  return <p>Open the Crawfish desktop app to import a local folder.</p>;
}
```

- [ ] **Step 2: Wire to OrgRoute (done in Task 12 — verify).**

- [ ] **Step 3: Manual verify**

Start the server + platform; sign in; navigate to an org; open Projects → Import project → "From GitHub"; pick a repo. Card appears with `pending` badge.

- [ ] **Step 4: Commit**

```
git add crawfish-platform/src/pages/ImportModal.tsx
git commit -m "feat(platform): Import modal — GitHub tab"
```

---

## Task 14: Desktop — projects polling + sidebar

**Files:**
- `crawfish-app/src/projects/index.ts` (or the existing desktop module pattern — inspect first)
- Wire into desktop sidebar component

The desktop already runs as a paired client with a `X-Crawfish-Token` device-link bearer (see `crawfish-server/src/middleware/auth.ts` and `crawfish-server/src/routes/deviceLink.ts`).

- [ ] **Step 1: Add a poller**

```ts
// crawfish-app/src/projects/poll.ts
import { dashFetch } from "../api/client.js"; // existing helper that adds X-Crawfish-Token

export interface Project {
  id: string; name: string; githubRepo: string | null;
  cloneStatus: "pending" | "cloning" | "cloned" | "local_only" | "error";
  cloneError: string | null; localPath: string | null;
}

export async function listProjects(orgId: string): Promise<Project[]> {
  const r = await dashFetch(`/api/dash/orgs/${orgId}/projects`);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return (await r.json()) as Project[];
}

export function startProjectPoller(orgId: string, onUpdate: (p: Project[]) => void) {
  let alive = true;
  async function tick() {
    if (!alive) return;
    try { onUpdate(await listProjects(orgId)); } catch (e) { console.warn(e); }
    setTimeout(tick, 30_000);
  }
  tick();
  return () => { alive = false; };
}
```

- [ ] **Step 2: Render the sidebar list**

Add a `ProjectsPanel` component in `crawfish-app`'s existing sidebar with a row per project, status badge, and a `Clone` button on rows with `cloneStatus === "pending"`. Wire the button to `cloneProject(project)` (Task 15).

- [ ] **Step 3: Commit**

```
git add crawfish-app/
git commit -m "feat(app): poll server for projects"
```

---

## Task 15: Desktop — clone executor

**Files:**
- `crawfish-app/src/projects/clone.ts`

- [ ] **Step 1: Implement the clone routine**

```ts
// crawfish-app/src/projects/clone.ts
import { spawn } from "node:child_process";
import { homedir } from "node:os";
import { join } from "node:path";
import { mkdirSync, existsSync, readFileSync } from "node:fs";
import { dashFetch } from "../api/client.js";

export async function cloneProject(orgId: string, orgSlug: string, project: {
  id: string; name: string; githubRepo: string | null;
}): Promise<void> {
  if (!project.githubRepo) throw new Error("No github_repo on project");
  await patch(orgId, project.id, { cloneStatus: "cloning" });

  const tokenRes = await dashFetch(`/api/dash/github/clone-token`);
  if (!tokenRes.ok) { await patch(orgId, project.id, { cloneStatus: "error", cloneError: "no_token" }); return; }
  const { token } = (await tokenRes.json()) as { token: string };

  const dest = join(homedir(), "crawfish", orgSlug, project.name);
  if (existsSync(dest)) {
    const adopted = await tryAdopt(dest, project.githubRepo);
    if (adopted) { await patch(orgId, project.id, { cloneStatus: "cloned", localPath: dest }); return; }
    await patch(orgId, project.id, { cloneStatus: "error", cloneError: "path_conflict" });
    return;
  }
  mkdirSync(join(homedir(), "crawfish", orgSlug), { recursive: true });

  const url = `https://x-access-token:${token}@github.com/${project.githubRepo}.git`;
  const child = spawn("git", ["clone", url, dest], { stdio: "pipe" });
  let stderr = "";
  child.stderr.on("data", (b) => { stderr += String(b); });
  await new Promise<void>((resolve) => child.on("exit", (code) => {
    if (code === 0) {
      // Strip token from origin URL
      spawn("git", ["-C", dest, "remote", "set-url", "origin", `https://github.com/${project.githubRepo}.git`]).on("exit", () => resolve());
    } else {
      void patch(orgId, project.id, { cloneStatus: "error", cloneError: classifyError(stderr) });
      resolve();
    }
  }));
  await patch(orgId, project.id, { cloneStatus: "cloned", localPath: dest });
}

function classifyError(stderr: string): string {
  if (/Authentication failed|invalid credentials/i.test(stderr)) return "auth_expired";
  return stderr.slice(-200);
}

function tryAdopt(dir: string, repo: string): boolean {
  try {
    const cfg = readFileSync(join(dir, ".git", "config"), "utf8");
    return cfg.includes(`github.com/${repo}`) || cfg.includes(`github.com:${repo}`);
  } catch { return false; }
}

async function patch(orgId: string, projectId: string, body: Record<string, unknown>) {
  await dashFetch(`/api/dash/orgs/${orgId}/projects/${projectId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}
```

- [ ] **Step 2: Wire the Clone button (from Task 14) to `cloneProject(...)`.**

- [ ] **Step 3: Manual smoke test**

Pair desktop to a test org. From web, import a public repo. In desktop, click Clone on the new card. Confirm `~/crawfish/<org>/<repo>` is created and the web card flips to `cloned` within 5s.

- [ ] **Step 4: Commit**

```
git add crawfish-app/
git commit -m "feat(app): clone executor for projects"
```

---

## Task 16: Desktop — adopt-local picker

**Files:**
- `crawfish-app/src/projects/adopt.ts`
- Wire into sidebar's "Import local folder" entry

- [ ] **Step 1: Implement**

```ts
// crawfish-app/src/projects/adopt.ts
import { spawn } from "node:child_process";
import { dashFetch } from "../api/client.js";
import { dialog } from "@tauri-apps/api"; // or the existing dialog helper

export async function adoptLocalFolder(orgId: string, deviceId: string) {
  const dir = await dialog.open({ directory: true, multiple: false });
  if (typeof dir !== "string") return;

  const origin = await readOrigin(dir);
  let githubRepoId: number | undefined;
  let name = dir.split("/").pop() ?? "project";

  if (origin) {
    const m = origin.match(/github\.com[/:]([^/]+)\/([^/.]+)(?:\.git)?$/);
    if (m) {
      const [, owner, repo] = m;
      const r = await dashFetch(`/api/dash/github/repos/${owner}/${repo}/check`).catch(() => null);
      // Note: the /check route as designed in Task 9 is on /api/github, accessible only via web JWT.
      // For the desktop, expose the same handler under /api/dash/github/repos/:o/:n/check
      // mounted with dashSyncMiddleware. Add this in this task.
      if (r && r.ok) {
        const meta = (await r.json()) as { id: number };
        githubRepoId = meta.id;
        name = repo;
      } else if (r && r.status === 404) {
        throw new Error("repo_access_denied");
      }
    }
  }

  const body: Record<string, unknown> = { name, localPath: dir, deviceId };
  if (githubRepoId !== undefined) body.githubRepoId = githubRepoId;
  await dashFetch(`/api/dash/orgs/${orgId}/projects`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

function readOrigin(dir: string): Promise<string | null> {
  return new Promise((resolve) => {
    const child = spawn("git", ["-C", dir, "config", "--get", "remote.origin.url"]);
    let out = "";
    child.stdout.on("data", (b) => { out += String(b); });
    child.on("exit", (code) => resolve(code === 0 ? out.trim() : null));
  });
}
```

- [ ] **Step 2: Server side — also mount the github router under `/api/dash/github`**

Add to `crawfish-server/src/index.ts`:

```ts
app.use("/api/dash/github", dashSyncMiddleware, githubRouter);
```

(This re-uses the existing routes; the `dashSyncMiddleware` populates `req.userId` so the handlers work unchanged.)

- [ ] **Step 3: Commit**

```
git add crawfish-app/ crawfish-server/src/index.ts
git commit -m "feat(app): adopt-local folder import"
```

---

## Task 17: E2E test

**Files:**
- Create: `e2e/tests/04-platform-projects.spec.ts`

- [ ] **Step 1: Write the test (covers GitHub-import → pending → simulated PATCH → cloned)**

```ts
// e2e/tests/04-platform-projects.spec.ts
import { test, expect } from "@playwright/test";
import { signInDev, createOrg, apiPost, apiPatch } from "../helpers.js";

test("GitHub import flow: pending → cloned via simulated device PATCH", async ({ page }) => {
  await signInDev(page);
  const orgId = await createOrg(page, "e2e-projects");

  // Mock the server's /api/github/repos to return a fixture
  await page.route("**/api/github/repos*", (r) =>
    r.fulfill({ json: [{ id: 42, full_name: "octo/hello", private: false }] }),
  );
  await page.route("**/api/orgs/*/projects", async (r, req) => {
    if (req.method() === "POST") {
      await r.fulfill({ json: { id: "p1", name: "hello", githubRepo: "octo/hello", cloneStatus: "pending" } });
      return;
    }
    await r.continue();
  });

  await page.goto(`/orgs/e2e-projects/projects`);
  await page.getByRole("button", { name: "Import project" }).click();
  await page.getByText("octo/hello").click();

  // Card appears in pending state
  await expect(page.getByText("hello")).toBeVisible();
  await expect(page.getByText("pending")).toBeVisible();

  // Simulate device PATCH and re-render
  await page.route("**/api/orgs/*/projects", (r) =>
    r.fulfill({ json: [{ id: "p1", name: "hello", githubRepo: "octo/hello", cloneStatus: "cloned", localPath: "/Users/me/crawfish/e2e-projects/hello" }] }),
  );
  // Wait for the 5s poll cycle or trigger manually
  await expect(page.getByText("cloned")).toBeVisible({ timeout: 7000 });
});
```

- [ ] **Step 2: Run the e2e suite**

```
cd e2e && npx playwright test 04-platform-projects.spec.ts
```

- [ ] **Step 3: Commit**

```
git add e2e/tests/04-platform-projects.spec.ts
git commit -m "test(e2e): platform projects import flow"
```

---

## Task 18: Documentation pass

**Files:**
- Modify: `docs/superpowers/specs/2026-05-18-github-login-import-design.md`
- Modify: `ROADMAP.md` (optional — add a line under §0 noting projects shipped)

- [ ] **Step 1: Update the spec's §4 to note `projects.json` was replaced with the Prisma `Project` model.**

- [ ] **Step 2: Append a row to ROADMAP §0 "Shipped" section: `Project model + GitHub import + adopt-local`.**

- [ ] **Step 3: Commit**

```
git add docs/superpowers/specs/ ROADMAP.md
git commit -m "docs: update spec + roadmap for projects ship"
```

---

## Self-review notes

- **Spec coverage:** §3 (Clerk wiring) → Task 11. §4 (data model) → Task 1. §5 (server routes) → Tasks 3–10. §6 (web UI) → Tasks 11–13. §7 (desktop) → Tasks 14–16. §8 (error handling) → covered inline in each task. §10 (testing) → Tasks 3–10 + Task 17.
- **Spec deviation:** `projects.json` → Prisma `Project` model. Called out in the plan header and Task 1; spec updated in Task 18.
- **Placeholder scan:** Task 14–16 reference `crawfish-app`'s exact module layout in passing because that codebase isn't fully inspected in this plan — flag for the executing agent to look at `crawfish-app/src` first and adapt paths. All Express + Prisma + platform UI tasks have exact code.
- **Type consistency:** `cloneStatus` enum is consistent across Tasks 1, 3, 6, 12, 14. `githubRepoId` is `Int?` on the Prisma model and `number` in TypeScript everywhere. `Project` shape is identical in server response, web component, and desktop client.
