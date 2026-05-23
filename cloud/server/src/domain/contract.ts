/**
 * Canonical domain contract (ADR-003).
 *
 * Single source of truth for the board vocabularies that were previously
 * forked across tiers (audit B1): TaskStatus, member roles, task-link kinds,
 * acceptance-criterion kinds. sqlite has no enum type, so these are enforced
 * here (zod) at the app layer, not in the schema.
 *
 * When a second tier needs these (desktop thin client), extract this module to
 * a shared `@crawfish/contracts` package — for now cloud/server is the only
 * writer, so it lives here to avoid premature cross-package wiring.
 */
import { z } from "zod";

// ─── TaskStatus ─────────────────────────────────────────────────────────────
export const TASK_STATUSES = [
  "triage",
  "backlog",
  "in_progress",
  "in_review",
  "blocked",
  "done",
  "canceled",
] as const;
export type TaskStatus = (typeof TASK_STATUSES)[number];
export const taskStatusSchema = z.enum(TASK_STATUSES);

// ─── Roles (write-gate ordering) ─────────────────────────────────────────────
// owner > admin > member > viewer. Mutations require >= member; org settings
// require >= admin. Legacy values (founder/contributor) map in normalizeRole.
export const ROLES = ["owner", "admin", "member", "viewer"] as const;
export type Role = (typeof ROLES)[number];
const ROLE_RANK: Record<Role, number> = { owner: 3, admin: 2, member: 1, viewer: 0 };

/** Map legacy lexicons (founder/contributor) onto the canonical role set. */
export function normalizeRole(raw: string): Role {
  switch (raw) {
    case "founder":
      return "owner";
    case "contributor":
      return "member";
    case "owner":
    case "admin":
    case "member":
    case "viewer":
      return raw;
    default:
      return "viewer";
  }
}

export function roleAtLeast(role: string, min: Role): boolean {
  return ROLE_RANK[normalizeRole(role)] >= ROLE_RANK[min];
}

// ─── Task links & acceptance criteria ────────────────────────────────────────
export const TASK_LINK_KINDS = [
  "blocks",
  "depends_on",
  "duplicates",
  "relates_to",
  "subtask_of",
] as const;
export const taskLinkKindSchema = z.enum(TASK_LINK_KINDS);

export const CRITERION_KINDS = ["test", "manual", "spec_match"] as const;
export const criterionKindSchema = z.enum(CRITERION_KINDS);

// ─── Activity kinds ──────────────────────────────────────────────────────────
export const ACTIVITY_KINDS = [
  "task_created",
  "status_changed",
  "assigned",
  "linked",
  "labeled",
  "budget_breach",
  "cycle_changed",
  "epic_changed",
] as const;
export type ActivityKind = (typeof ACTIVITY_KINDS)[number];

// ─── Request bodies ──────────────────────────────────────────────────────────
export const createTaskSchema = z.object({
  title: z.string().min(1).max(280),
  description: z.string().max(10_000).optional(),
  status: taskStatusSchema.optional(),
  cycleId: z.string().min(1).optional(),
  epicId: z.string().min(1).optional(),
  assigneeId: z.string().min(1).optional(),
  tokenBudget: z.number().int().nonnegative().optional(),
});

export const updateTaskSchema = z.object({
  title: z.string().min(1).max(280).optional(),
  description: z.string().max(10_000).nullable().optional(),
  status: taskStatusSchema.optional(),
  escalated: z.boolean().optional(),
  cycleId: z.string().min(1).nullable().optional(),
  epicId: z.string().min(1).nullable().optional(),
  assigneeId: z.string().min(1).nullable().optional(),
  tokenBudget: z.number().int().nonnegative().nullable().optional(),
});

export const createCycleSchema = z.object({
  name: z.string().min(1).max(120),
  status: z.enum(["upcoming", "active", "completed"]).optional(),
  startsAt: z.string().datetime().optional(),
  endsAt: z.string().datetime().optional(),
});

export const createEpicSchema = z.object({
  title: z.string().min(1).max(280),
  description: z.string().max(10_000).optional(),
  status: taskStatusSchema.optional(),
});

export const createCriterionSchema = z.object({
  kind: criterionKindSchema,
  description: z.string().min(1).max(2_000),
});

export const updateCriterionSchema = z.object({
  description: z.string().min(1).max(2_000).optional(),
  met: z.boolean().optional(),
  evidence: z.string().max(10_000).nullable().optional(),
});
