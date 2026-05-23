/**
 * Shared org-membership RBAC guard.
 *
 * Resolves the org by id-or-slug, confirms the caller (req.userId, set by
 * authMiddleware) is a member, and collapses the non-member case to 404 so the
 * route never leaks org existence. Used by the projects, integrations, and
 * board routers — single source of truth, no per-router copies.
 *
 * `requireRole` adds the canonical write-gate (ADR-003): a member whose role is
 * below the minimum gets 403 (they already know the org exists, so no 404
 * collapse). Roles are normalized via the domain contract (founder→owner,
 * contributor→member).
 */
import type { Request } from "express";
import { db } from "../index.js";
import { roleAtLeast, type Role } from "../domain/contract.js";

export type RequireMemberResult =
  | { ok: true; orgId: string; userId: string; memberId: string; role: string }
  | { ok: false; status: number; code: string };

export async function requireMember(
  req: Request,
  orgIdParam: string,
): Promise<RequireMemberResult> {
  const userId = req.userId;
  if (!userId) return { ok: false, status: 401, code: "unauthenticated" };
  const org = await db.org.findFirst({
    where: { OR: [{ id: orgIdParam }, { name: orgIdParam }] },
    select: { id: true },
  });
  if (!org) return { ok: false, status: 404, code: "not_found" };
  const m = await db.orgMember.findUnique({
    where: { orgId_userId: { orgId: org.id, userId } },
    select: { id: true, role: true },
  });
  if (!m) return { ok: false, status: 404, code: "not_found" };
  return { ok: true, orgId: org.id, userId, memberId: m.id, role: m.role };
}

/**
 * Like requireMember, but also enforces a minimum canonical role. Non-members
 * still collapse to 404; members below `min` get 403 `forbidden`.
 */
export async function requireRole(
  req: Request,
  orgIdParam: string,
  min: Role,
): Promise<RequireMemberResult> {
  const ctx = await requireMember(req, orgIdParam);
  if (!ctx.ok) return ctx;
  if (!roleAtLeast(ctx.role, min)) {
    return { ok: false, status: 403, code: "forbidden" };
  }
  return ctx;
}
