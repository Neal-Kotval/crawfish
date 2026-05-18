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

type RequireMemberResult =
  | { ok: true; orgId: string; userId: string }
  | { ok: false; status: number; code: string };

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
