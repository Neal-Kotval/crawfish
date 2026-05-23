/**
 * Shared org-membership RBAC guard.
 *
 * Resolves the org by id-or-slug, confirms the caller (req.userId, set by
 * authMiddleware) is a member, and collapses the non-member case to 404 so the
 * route never leaks org existence. Used by the projects and integrations
 * routers — single source of truth, no per-router copies.
 */
import type { Request } from "express";
import { db } from "../index.js";

export type RequireMemberResult =
  | { ok: true; orgId: string; userId: string }
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
  });
  if (!m) return { ok: false, status: 404, code: "not_found" };
  return { ok: true, orgId: org.id, userId };
}
