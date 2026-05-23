import { Router, type Request } from "express";
import { z } from "zod";
import { db } from "../index.js";
import { httpError } from "../lib/errors.js";
import {
  getGithubToken,
  GithubNotConnected,
  fetchRepoMetadata,
  type RepoMetadata,
} from "../lib/github.js";
import { syncProjectIssues, NothingToSync, IntegrationNotConnected } from "../lib/sync.js";
import { requireMember } from "../lib/rbac.js";

export const projectsRouter = Router({ mergeParams: true });

const CloneBody = z.object({
  githubRepoId: z.number().int().positive(),
  name: z.string().min(1).max(120).optional(),
});

const AdoptBody = z.object({
  name: z.string().min(1).max(120),
  localPath: z.string().min(1).max(1024),
  deviceId: z.string().min(1).max(128),
  githubRepoId: z.number().int().positive().optional(),
});

const Body = z.union([AdoptBody, CloneBody]);

projectsRouter.get("/", async (req, res) => {
  const ctx = await requireMember(req, (req.params as { orgId: string }).orgId);
  if (!ctx.ok) return httpError(res, ctx.status, ctx.code, "");
  const projects = await db.project.findMany({
    where: { orgId: ctx.orgId },
    orderBy: { createdAt: "desc" },
  });
  return res.json(projects);
});

projectsRouter.post("/", async (req, res) => {
  const ctx = await requireMember(req, (req.params as { orgId: string }).orgId);
  if (!ctx.ok) return httpError(res, ctx.status, ctx.code, "");

  const parsed = Body.safeParse(req.body);
  if (!parsed.success) return httpError(res, 400, "invalid_body", parsed.error.message);

  // Adopt-local branch: body has localPath
  if ("localPath" in parsed.data) {
    const b = parsed.data;
    let meta: RepoMetadata | null = null;
    if (b.githubRepoId !== undefined) {
      try {
        const token = await getGithubToken(ctx.userId);
        meta = await fetchRepoMetadata(token, b.githubRepoId);
      } catch (err) {
        if (err instanceof GithubNotConnected)
          return httpError(res, 409, "github_disconnected", "");
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

  // Clone branch (existing behaviour)
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
      name: b.name ?? meta.full_name.split("/")[1]!,
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

const PatchBody = z.object({
  cloneStatus: z.enum(["pending", "cloning", "cloned", "local_only", "error"]).optional(),
  localPath: z.string().max(1024).nullable().optional(),
  cloneError: z.string().max(1024).nullable().optional(),
  deviceId: z.string().max(128).nullable().optional(),
  name: z.string().min(1).max(120).optional(),
});

projectsRouter.patch("/:pid", async (req, res) => {
  const params = req.params as { orgId: string; pid: string };
  const ctx = await requireMember(req, params.orgId);
  if (!ctx.ok) return httpError(res, ctx.status, ctx.code, "");

  const parsed = PatchBody.safeParse(req.body);
  if (!parsed.success) return httpError(res, 400, "invalid_body", parsed.error.message);

  const project = await db.project.findFirst({ where: { id: params.pid, orgId: ctx.orgId } });
  if (!project) return httpError(res, 404, "not_found", "");

  const touchesCloneFields =
    parsed.data.cloneStatus !== undefined ||
    parsed.data.localPath !== undefined ||
    parsed.data.cloneError !== undefined ||
    parsed.data.deviceId !== undefined;
  const dashOrgId = (req as Request & { dashOrgId?: string }).dashOrgId;
  if (touchesCloneFields && !dashOrgId) {
    return httpError(res, 403, "device_token_required", "");
  }

  const updated = await db.project.update({
    where: { id: project.id },
    data: parsed.data,
  });
  return res.json(updated);
});

const CRAWFISH_FILE_ALLOWLIST = new Set([
  "index.json",
  "memory.md",
  "context.md",
  "roadmap.md",
  "decisions.md",
  "activity.md",
]);

projectsRouter.get("/:pid/files/:filename", async (req, res) => {
  const params = req.params as { orgId: string; pid: string; filename: string };
  const ctx = await requireMember(req, params.orgId);
  if (!ctx.ok) return httpError(res, ctx.status, ctx.code, "");

  if (!CRAWFISH_FILE_ALLOWLIST.has(params.filename)) {
    return httpError(res, 400, "invalid_filename", "");
  }

  const project = await db.project.findFirst({ where: { id: params.pid, orgId: ctx.orgId } });
  if (!project) return httpError(res, 404, "not_found", "");

  if (project.cloneStatus !== "cloned" && project.cloneStatus !== "local_only") {
    return httpError(res, 409, "project_not_initialized", "");
  }
  if (!project.githubRepo) {
    return httpError(res, 404, "no_remote", "");
  }

  let token: string;
  try {
    token = await getGithubToken(ctx.userId);
  } catch (err) {
    if (err instanceof GithubNotConnected) return httpError(res, 409, "github_disconnected", "");
    return httpError(res, 502, "github_error", String(err));
  }

  const ref = project.defaultBranch ?? "main";
  const url = `https://api.github.com/repos/${project.githubRepo}/contents/.crawfish/${params.filename}?ref=${encodeURIComponent(ref)}`;
  const ghRes = await fetch(url, {
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: "application/vnd.github.raw+json",
      "User-Agent": "crawfish-server",
    },
  });

  if (ghRes.status === 404) return httpError(res, 404, "file_not_found", "");
  if (!ghRes.ok) return httpError(res, 502, "github_error", `status ${ghRes.status}`);

  const body = await ghRes.text();
  const contentType =
    params.filename === "index.json"
      ? "application/json; charset=utf-8"
      : "text/markdown; charset=utf-8";
  res.setHeader("Content-Type", contentType);
  res.setHeader("Cache-Control", "no-store");
  return res.status(200).send(body);
});

// GET /:pid/issues — list synced issues for a project (member-only). Labels
// are stored JSON-encoded; parsed back to an array for the response.
projectsRouter.get("/:pid/issues", async (req, res) => {
  const params = req.params as { orgId: string; pid: string };
  const ctx = await requireMember(req, params.orgId);
  if (!ctx.ok) return httpError(res, ctx.status, ctx.code, "");

  const project = await db.project.findFirst({ where: { id: params.pid, orgId: ctx.orgId } });
  if (!project) return httpError(res, 404, "not_found", "");

  const issues = await db.issue.findMany({
    where: { projectId: project.id },
    orderBy: [{ externalUpdatedAt: "desc" }, { createdAt: "desc" }],
  });
  return res.json(
    issues.map((i) => ({
      ...i,
      labels: ((): string[] => {
        try {
          const v = JSON.parse(i.labels) as unknown;
          return Array.isArray(v) ? (v as string[]) : [];
        } catch {
          return [];
        }
      })(),
    })),
  );
});

// POST /:pid/sync — pull issues from the project's connected provider and
// upsert them. Idempotent. GitHub is wired; Linear lands in a later wave.
projectsRouter.post("/:pid/sync", async (req, res) => {
  const params = req.params as { orgId: string; pid: string };
  const ctx = await requireMember(req, params.orgId);
  if (!ctx.ok) return httpError(res, ctx.status, ctx.code, "");

  const project = await db.project.findFirst({ where: { id: params.pid, orgId: ctx.orgId } });
  if (!project) return httpError(res, 404, "not_found", "");

  try {
    const result = await syncProjectIssues(db, project, ctx.userId);
    return res.json(result);
  } catch (err) {
    if (err instanceof NothingToSync) return httpError(res, 400, "nothing_to_sync", "");
    if (err instanceof IntegrationNotConnected)
      return httpError(res, 409, "linear_not_connected", "");
    if (err instanceof GithubNotConnected)
      return httpError(res, 409, "github_disconnected", "");
    return httpError(res, 502, "sync_error", String(err));
  }
});

projectsRouter.delete("/:pid", async (req, res) => {
  const params = req.params as { orgId: string; pid: string };
  const ctx = await requireMember(req, params.orgId);
  if (!ctx.ok) return httpError(res, ctx.status, ctx.code, "");

  const project = await db.project.findFirst({ where: { id: params.pid, orgId: ctx.orgId } });
  if (!project) return httpError(res, 404, "not_found", "");

  await db.project.delete({ where: { id: project.id } });
  return res.status(204).send();
});
