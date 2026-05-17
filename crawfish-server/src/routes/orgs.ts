/**
 * Org routes — create, list-mine, read-one.
 *
 * RBAC: every route requires req.userId (set by authMiddleware). Read access
 * requires OrgMember row. There's no role gate yet — any member can read.
 */
import { Router, type Request } from "express";
import { z } from "zod";
import { Prisma } from "@prisma/client";
import { db } from "../index.js";
import { httpError } from "../lib/errors.js";
import { loadOrgWithRelations } from "../lib/orgs.js";

export const orgsRouter = Router();
export const meRouter = Router();

const DEFAULT_AGENTS = [
  { name: "eng-bot", role: "engineer", runtime: "claude-code" },
  { name: "designer-bot", role: "designer", runtime: "claude-api" },
  { name: "support-bot", role: "tier-1 support", runtime: "cma" },
  { name: "ops-bot", role: "operations", runtime: "claude-api" },
];

const CreateOrgSchema = z.object({
  name: z
    .string()
    .min(1)
    .max(64)
    .regex(/^[a-z0-9][a-z0-9-]*$/, "lowercase letters/digits/dashes only"),
  project: z.string().max(280).optional(),
  teamSize: z.enum(["Just me", "2–5", "5–20", "20+"]).optional(),
  primaryClient: z.enum(["Dash", "CLI", "IDE", "All three"]).optional(),
  agents: z
    .array(
      z.object({
        name: z.string().min(1).max(64),
        role: z.string().min(1).max(280),
        runtime: z.string().min(1).max(64),
      }),
    )
    .default(DEFAULT_AGENTS),
});

function requireUser(req: Request): string | null {
  return req.userId ?? null;
}

// POST /api/orgs — create a new org owned by the caller.
orgsRouter.post("/", async (req, res) => {
  const userId = requireUser(req);
  if (!userId) return httpError(res, 401, "unauthenticated", "Missing user.");

  const parsed = CreateOrgSchema.safeParse(req.body);
  if (!parsed.success) {
    return httpError(
      res,
      400,
      "invalid_body",
      parsed.error.issues.map((i) => `${i.path.join(".")}: ${i.message}`).join("; "),
    );
  }
  const body = parsed.data;

  try {
    const org = await db.$transaction(async (tx) => {
      const created = await tx.org.create({
        data: {
          name: body.name,
          project: body.project ?? null,
          teamSize: body.teamSize ?? null,
          primaryClient: body.primaryClient ?? null,
        },
      });
      await tx.orgMember.create({
        data: { orgId: created.id, userId, role: "founder" },
      });
      if (body.agents.length > 0) {
        await tx.agentMeta.createMany({
          data: body.agents.map((a) => ({
            orgId: created.id,
            name: a.name,
            role: a.role,
            runtime: a.runtime,
          })),
        });
      }
      return created;
    });

    const full = await loadOrgWithRelations(org.id);
    if (!full) return httpError(res, 500, "load_failed", "Org created but could not be reloaded.");
    return res.status(201).json(full);
  } catch (err) {
    if (err instanceof Prisma.PrismaClientKnownRequestError && err.code === "P2002") {
      return httpError(res, 409, "name_taken", `Org name ${body.name} already exists`);
    }
    return httpError(res, 500, "server_error", String(err));
  }
});

// GET /api/orgs/:id — full org if caller is a member.
orgsRouter.get("/:id", async (req, res) => {
  const userId = requireUser(req);
  if (!userId) return httpError(res, 401, "unauthenticated", "Missing user.");

  const { id } = req.params;

  // Allow lookup by either cuid or slug (org.name). The platform routes use
  // the slug in the URL because it's human-readable.
  const org = await db.org.findFirst({
    where: { OR: [{ id }, { name: id }] },
    select: { id: true },
  });
  if (!org) return httpError(res, 404, "not_found", "Org not found.");

  const membership = await db.orgMember.findUnique({
    where: { orgId_userId: { orgId: org.id, userId } },
  });
  if (!membership) return httpError(res, 403, "forbidden", "Not a member of this org.");

  const full = await loadOrgWithRelations(org.id);
  if (!full) return httpError(res, 404, "not_found", "Org not found.");
  return res.json(full);
});

// PUT /api/orgs/:id/agents — sync the full agent list for this org.
// Dash sends the full agent list on each change; we replace.
const SyncAgentsSchema = z.object({
  agents: z.array(
    z.object({
      name: z.string().min(1).max(64),
      role: z.string().min(1).max(280),
      runtime: z.string().min(1).max(64),
    }),
  ),
});
orgsRouter.put("/:id/agents", async (req, res) => {
  const userId = requireUser(req);
  if (!userId) return httpError(res, 401, "unauthenticated", "Missing user.");

  const { id } = req.params;
  const org = await db.org.findFirst({
    where: { OR: [{ id }, { name: id }] },
    select: { id: true },
  });
  if (!org) return httpError(res, 404, "not_found", "Org not found.");

  const membership = await db.orgMember.findUnique({
    where: { orgId_userId: { orgId: org.id, userId } },
  });
  if (!membership) return httpError(res, 403, "forbidden", "Not a member of this org.");
  if (membership.role !== "founder" && membership.role !== "contributor") {
    return httpError(res, 403, "forbidden", "Need contributor or founder to sync agents.");
  }

  const parsed = SyncAgentsSchema.safeParse(req.body);
  if (!parsed.success) {
    return httpError(
      res,
      400,
      "invalid_body",
      parsed.error.issues.map((i) => `${i.path.join(".")}: ${i.message}`).join("; "),
    );
  }

  try {
    await db.$transaction(async (tx) => {
      await tx.agentMeta.deleteMany({ where: { orgId: org.id } });
      if (parsed.data.agents.length > 0) {
        await tx.agentMeta.createMany({
          data: parsed.data.agents.map((a) => ({
            orgId: org.id,
            name: a.name,
            role: a.role,
            runtime: a.runtime,
          })),
        });
      }
    });
    const after = await db.agentMeta.findMany({
      where: { orgId: org.id },
      orderBy: { hiredAt: "asc" },
      select: { name: true, role: true, runtime: true, hiredAt: true },
    });
    return res.json({
      ok: true,
      agents: after.map((a) => ({
        name: a.name,
        role: a.role,
        runtime: a.runtime,
        hiredAt: a.hiredAt.toISOString(),
      })),
    });
  } catch (err) {
    return httpError(res, 500, "server_error", String(err));
  }
});

// GET /api/me/orgs — orgs the current user is a member of, with counts.
meRouter.get("/orgs", async (req, res) => {
  const userId = requireUser(req);
  if (!userId) return httpError(res, 401, "unauthenticated", "Missing user.");

  const memberships = await db.orgMember.findMany({
    where: { userId },
    orderBy: { createdAt: "asc" },
    include: {
      org: {
        include: {
          _count: { select: { members: true, agents: true } },
        },
      },
    },
  });

  const summaries = memberships.map((m) => ({
    id: m.org.id,
    name: m.org.name,
    project: m.org.project,
    teamSize: m.org.teamSize,
    primaryClient: m.org.primaryClient,
    createdAt: m.org.createdAt.toISOString(),
    role: m.role,
    memberCount: m.org._count.members,
    agentCount: m.org._count.agents,
  }));

  return res.json(summaries);
});
