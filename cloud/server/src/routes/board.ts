/**
 * Board routes — the canonical cloud Task board (ADR-003).
 *
 * Mounted at /api/orgs/:orgId/projects (alongside projectsRouter); handles the
 * /:pid/{tasks,cycles,epics,activity} sub-paths. Tasks are project-scoped
 * authored work items (distinct from provider Issues). Reads require membership
 * (viewer+); writes require >= member via the role write-gate. Mutations append
 * to the Activity feed.
 */
import { Router } from "express";
import { db } from "../index.js";
import { httpError } from "../lib/errors.js";
import { requireMember, requireRole } from "../lib/rbac.js";
import { publishBoard, subscribeBoard } from "../lib/events.js";
import {
  createTaskSchema,
  updateTaskSchema,
  createCycleSchema,
  createEpicSchema,
  createCriterionSchema,
  updateCriterionSchema,
  recordUsageSchema,
  type ActivityKind,
} from "../domain/contract.js";

export const boardRouter = Router({ mergeParams: true });

type Params = { orgId: string; pid: string };

/** Append an Activity row. Best-effort log of a board mutation. */
async function logActivity(args: {
  projectId: string;
  taskId?: string | null;
  actorMemberId?: string | null;
  kind: ActivityKind;
  payload?: Record<string, unknown>;
}): Promise<void> {
  await db.activity.create({
    data: {
      projectId: args.projectId,
      taskId: args.taskId ?? null,
      actorMemberId: args.actorMemberId ?? null,
      kind: args.kind,
      payload: JSON.stringify(args.payload ?? {}),
    },
  });
  // Fan out to live SSE subscribers (best-effort, in-process).
  publishBoard(args.projectId, {
    kind: args.kind,
    taskId: args.taskId ?? null,
    payload: args.payload ?? {},
    at: new Date().toISOString(),
  });
}

/** Resolve the project within the org, or null. */
async function findProject(orgId: string, pid: string) {
  return db.project.findFirst({ where: { id: pid, orgId }, select: { id: true } });
}

// ─── Tasks ───────────────────────────────────────────────────────────────────

boardRouter.get("/:pid/tasks", async (req, res) => {
  const p = req.params as Params;
  const ctx = await requireMember(req, p.orgId);
  if (!ctx.ok) return httpError(res, ctx.status, ctx.code, "");
  const project = await findProject(ctx.orgId, p.pid);
  if (!project) return httpError(res, 404, "not_found", "");
  const tasks = await db.task.findMany({
    where: { projectId: project.id },
    orderBy: { updatedAt: "desc" },
  });
  return res.json(tasks);
});

boardRouter.post("/:pid/tasks", async (req, res) => {
  const p = req.params as Params;
  const ctx = await requireRole(req, p.orgId, "member");
  if (!ctx.ok) return httpError(res, ctx.status, ctx.code, "");
  const project = await findProject(ctx.orgId, p.pid);
  if (!project) return httpError(res, 404, "not_found", "");

  const parsed = createTaskSchema.safeParse(req.body);
  if (!parsed.success) return httpError(res, 400, "invalid_body", parsed.error.message);
  const b = parsed.data;

  const task = await db.task.create({
    data: {
      projectId: project.id,
      title: b.title,
      description: b.description ?? null,
      status: b.status ?? "triage",
      cycleId: b.cycleId ?? null,
      epicId: b.epicId ?? null,
      assigneeId: b.assigneeId ?? null,
      tokenBudget: b.tokenBudget ?? null,
      createdById: ctx.userId,
    },
  });
  await logActivity({
    projectId: project.id,
    taskId: task.id,
    actorMemberId: ctx.memberId,
    kind: "task_created",
    payload: { title: task.title, status: task.status },
  });
  return res.status(201).json(task);
});

boardRouter.get("/:pid/tasks/:taskId", async (req, res) => {
  const p = req.params as Params & { taskId: string };
  const ctx = await requireMember(req, p.orgId);
  if (!ctx.ok) return httpError(res, ctx.status, ctx.code, "");
  const task = await db.task.findFirst({
    where: { id: p.taskId, project: { id: p.pid, orgId: ctx.orgId } },
    include: { criteria: true, linksFrom: true, linksTo: true },
  });
  if (!task) return httpError(res, 404, "not_found", "");
  return res.json(task);
});

boardRouter.patch("/:pid/tasks/:taskId", async (req, res) => {
  const p = req.params as Params & { taskId: string };
  const ctx = await requireRole(req, p.orgId, "member");
  if (!ctx.ok) return httpError(res, ctx.status, ctx.code, "");

  const parsed = updateTaskSchema.safeParse(req.body);
  if (!parsed.success) return httpError(res, 400, "invalid_body", parsed.error.message);

  const existing = await db.task.findFirst({
    where: { id: p.taskId, project: { id: p.pid, orgId: ctx.orgId } },
  });
  if (!existing) return httpError(res, 404, "not_found", "");

  // Evidence guard (Phase 5): a task can only move to `done` once every
  // acceptance criterion is met. Unmet criteria → 400 criteria_missing_evidence.
  if (parsed.data.status === "done" && existing.status !== "done") {
    const unmet = await db.acceptanceCriterion.count({
      where: { taskId: existing.id, met: false },
    });
    if (unmet > 0) {
      return httpError(
        res,
        400,
        "criteria_missing_evidence",
        `${unmet} acceptance criterion(s) not met`,
      );
    }
  }

  const updated = await db.task.update({ where: { id: existing.id }, data: parsed.data });

  // Emit activity for the meaningful transitions.
  if (parsed.data.status !== undefined && parsed.data.status !== existing.status) {
    await logActivity({
      projectId: existing.projectId,
      taskId: existing.id,
      actorMemberId: ctx.memberId,
      kind: "status_changed",
      payload: { from: existing.status, to: parsed.data.status },
    });
  }
  if (parsed.data.assigneeId !== undefined && parsed.data.assigneeId !== existing.assigneeId) {
    await logActivity({
      projectId: existing.projectId,
      taskId: existing.id,
      actorMemberId: ctx.memberId,
      kind: "assigned",
      payload: { assigneeId: parsed.data.assigneeId },
    });
  }
  return res.json(updated);
});

// ─── Acceptance criteria (Phase 5 — evidence guard) ──────────────────────────

async function taskInOrg(orgId: string, pid: string, taskId: string) {
  return db.task.findFirst({ where: { id: taskId, project: { id: pid, orgId } }, select: { id: true } });
}

// Add an acceptance criterion to a task.
boardRouter.post("/:pid/tasks/:taskId/criteria", async (req, res) => {
  const p = req.params as Params & { taskId: string };
  const ctx = await requireRole(req, p.orgId, "member");
  if (!ctx.ok) return httpError(res, ctx.status, ctx.code, "");
  const task = await taskInOrg(ctx.orgId, p.pid, p.taskId);
  if (!task) return httpError(res, 404, "not_found", "");
  const parsed = createCriterionSchema.safeParse(req.body);
  if (!parsed.success) return httpError(res, 400, "invalid_body", parsed.error.message);
  const criterion = await db.acceptanceCriterion.create({
    data: { taskId: task.id, kind: parsed.data.kind, description: parsed.data.description },
  });
  return res.status(201).json(criterion);
});

// Update a criterion (mark met + attach evidence).
boardRouter.patch("/:pid/tasks/:taskId/criteria/:cid", async (req, res) => {
  const p = req.params as Params & { taskId: string; cid: string };
  const ctx = await requireRole(req, p.orgId, "member");
  if (!ctx.ok) return httpError(res, ctx.status, ctx.code, "");
  const task = await taskInOrg(ctx.orgId, p.pid, p.taskId);
  if (!task) return httpError(res, 404, "not_found", "");
  const parsed = updateCriterionSchema.safeParse(req.body);
  if (!parsed.success) return httpError(res, 400, "invalid_body", parsed.error.message);
  const existing = await db.acceptanceCriterion.findFirst({
    where: { id: p.cid, taskId: task.id },
    select: { id: true },
  });
  if (!existing) return httpError(res, 404, "not_found", "");
  const updated = await db.acceptanceCriterion.update({ where: { id: existing.id }, data: parsed.data });
  return res.json(updated);
});

// ─── Token budget (Phase 5 — record spend + breach → escalated) ──────────────

boardRouter.post("/:pid/tasks/:taskId/usage", async (req, res) => {
  const p = req.params as Params & { taskId: string };
  const ctx = await requireRole(req, p.orgId, "member");
  if (!ctx.ok) return httpError(res, ctx.status, ctx.code, "");
  const parsed = recordUsageSchema.safeParse(req.body);
  if (!parsed.success) return httpError(res, 400, "invalid_body", parsed.error.message);

  const task = await db.task.findFirst({
    where: { id: p.taskId, project: { id: p.pid, orgId: ctx.orgId } },
  });
  if (!task) return httpError(res, 404, "not_found", "");

  const tokensSpent = task.tokensSpent + parsed.data.tokens;
  // Breach fires once, on the transition from under-budget to >=100%.
  const breached =
    task.tokenBudget != null && tokensSpent >= task.tokenBudget && !task.escalated;

  const updated = await db.task.update({
    where: { id: task.id },
    data: { tokensSpent, ...(breached ? { escalated: true } : {}) },
  });

  if (breached) {
    await logActivity({
      projectId: task.projectId,
      taskId: task.id,
      actorMemberId: ctx.memberId,
      kind: "budget_breach",
      payload: { spent: tokensSpent, budget: task.tokenBudget },
    });
  }
  return res.json(updated);
});

// ─── Cycles ──────────────────────────────────────────────────────────────────

boardRouter.get("/:pid/cycles", async (req, res) => {
  const p = req.params as Params;
  const ctx = await requireMember(req, p.orgId);
  if (!ctx.ok) return httpError(res, ctx.status, ctx.code, "");
  const project = await findProject(ctx.orgId, p.pid);
  if (!project) return httpError(res, 404, "not_found", "");
  const cycles = await db.cycle.findMany({
    where: { projectId: project.id },
    orderBy: { createdAt: "desc" },
  });
  return res.json(cycles);
});

boardRouter.post("/:pid/cycles", async (req, res) => {
  const p = req.params as Params;
  const ctx = await requireRole(req, p.orgId, "member");
  if (!ctx.ok) return httpError(res, ctx.status, ctx.code, "");
  const project = await findProject(ctx.orgId, p.pid);
  if (!project) return httpError(res, 404, "not_found", "");
  const parsed = createCycleSchema.safeParse(req.body);
  if (!parsed.success) return httpError(res, 400, "invalid_body", parsed.error.message);
  const b = parsed.data;
  const cycle = await db.cycle.create({
    data: {
      projectId: project.id,
      name: b.name,
      status: b.status ?? "upcoming",
      startsAt: b.startsAt ? new Date(b.startsAt) : null,
      endsAt: b.endsAt ? new Date(b.endsAt) : null,
    },
  });
  return res.status(201).json(cycle);
});

// ─── Epics ───────────────────────────────────────────────────────────────────

boardRouter.get("/:pid/epics", async (req, res) => {
  const p = req.params as Params;
  const ctx = await requireMember(req, p.orgId);
  if (!ctx.ok) return httpError(res, ctx.status, ctx.code, "");
  const project = await findProject(ctx.orgId, p.pid);
  if (!project) return httpError(res, 404, "not_found", "");
  const epics = await db.epic.findMany({
    where: { projectId: project.id },
    orderBy: { createdAt: "desc" },
  });
  return res.json(epics);
});

boardRouter.post("/:pid/epics", async (req, res) => {
  const p = req.params as Params;
  const ctx = await requireRole(req, p.orgId, "member");
  if (!ctx.ok) return httpError(res, ctx.status, ctx.code, "");
  const project = await findProject(ctx.orgId, p.pid);
  if (!project) return httpError(res, 404, "not_found", "");
  const parsed = createEpicSchema.safeParse(req.body);
  if (!parsed.success) return httpError(res, 400, "invalid_body", parsed.error.message);
  const b = parsed.data;
  const epic = await db.epic.create({
    data: {
      projectId: project.id,
      title: b.title,
      description: b.description ?? null,
      status: b.status ?? "backlog",
    },
  });
  return res.status(201).json(epic);
});

// ─── Live stream (SSE) ─────────────────────────────────────────────────────────

boardRouter.get("/:pid/stream", async (req, res) => {
  const p = req.params as Params;
  const ctx = await requireMember(req, p.orgId);
  if (!ctx.ok) return httpError(res, ctx.status, ctx.code, "");
  const project = await findProject(ctx.orgId, p.pid);
  if (!project) return httpError(res, 404, "not_found", "");

  res.set({
    "Content-Type": "text/event-stream",
    "Cache-Control": "no-cache, no-transform",
    Connection: "keep-alive",
    "X-Accel-Buffering": "no", // disable proxy buffering
  });
  res.flushHeaders?.();
  res.write(": connected\n\n");

  const unsubscribe = subscribeBoard(project.id, (ev) => {
    res.write(`event: board\ndata: ${JSON.stringify(ev)}\n\n`);
  });
  // Heartbeat keeps the connection alive through idle periods / proxies.
  const heartbeat = setInterval(() => res.write(": ping\n\n"), 25_000);

  req.on("close", () => {
    clearInterval(heartbeat);
    unsubscribe();
    res.end();
  });
});

// ─── Activity feed ─────────────────────────────────────────────────────────────

boardRouter.get("/:pid/activity", async (req, res) => {
  const p = req.params as Params;
  const ctx = await requireMember(req, p.orgId);
  if (!ctx.ok) return httpError(res, ctx.status, ctx.code, "");
  const project = await findProject(ctx.orgId, p.pid);
  if (!project) return httpError(res, 404, "not_found", "");
  const activity = await db.activity.findMany({
    where: { projectId: project.id },
    orderBy: { createdAt: "desc" },
    take: 100,
  });
  return res.json(
    activity.map((a) => ({
      ...a,
      payload: ((): unknown => {
        try {
          return JSON.parse(a.payload);
        } catch {
          return {};
        }
      })(),
    })),
  );
});
