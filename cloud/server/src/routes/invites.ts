/**
 * Invite routes — invite-by-email in mock-email dev mode.
 *
 * RBAC: create/list/revoke require OrgMember on :orgId. The public
 * `GET /api/invites/:code` lets a not-yet-signed-in user preview what
 * they're accepting. `POST /api/invites/:code/accept` requires auth and
 * the signed-in user's email must match the invite (case-insensitive).
 *
 * Mock-email mode: no SMTP. We console.log a formatted block and also
 * return `mockEmail` in the create response so the dev UI can show the
 * link inline.
 */
import { Router, type Request } from "express";
import crypto from "node:crypto";
import { z } from "zod";
import { db } from "../index.js";
import { httpError } from "../lib/errors.js";

export const invitesRouter = Router({ mergeParams: true });   // mounted at /api/orgs/:orgId/invites
export const publicInvitesRouter = Router();                  // mounted at /api/invites

const PLATFORM_URL = process.env.PLATFORM_URL ?? "http://127.0.0.1:5174";
const INVITE_TTL_MS = 7 * 24 * 60 * 60 * 1000; // 7 days

const CreateInviteSchema = z.object({
  email: z.string().email().max(320),
  role: z.enum(["owner", "contributor"]).default("contributor"),
});

function requireUser(req: Request): string | null {
  return req.userId ?? null;
}

function generateCode(): string {
  return crypto.randomBytes(9).toString("base64url"); // 12 chars
}

async function ensureOrgMembership(orgId: string, userId: string) {
  const org = await db.org.findFirst({
    where: { OR: [{ id: orgId }, { name: orgId }] },
    select: { id: true, name: true },
  });
  if (!org) return { ok: false as const, status: 404, code: "not_found", msg: "Org not found." };
  const membership = await db.orgMember.findUnique({
    where: { orgId_userId: { orgId: org.id, userId } },
  });
  if (!membership) {
    return { ok: false as const, status: 403, code: "forbidden", msg: "Not a member of this org." };
  }
  return { ok: true as const, org, membership };
}

// POST /api/orgs/:orgId/invites
invitesRouter.post("/", async (req, res) => {
  const userId = requireUser(req);
  if (!userId) return httpError(res, 401, "unauthenticated", "Missing user.");

  const orgId = (req.params as { orgId: string }).orgId;
  const check = await ensureOrgMembership(orgId, userId);
  if (!check.ok) return httpError(res, check.status, check.code, check.msg);

  const parsed = CreateInviteSchema.safeParse(req.body);
  if (!parsed.success) {
    return httpError(
      res,
      400,
      "invalid_body",
      parsed.error.issues.map((i) => `${i.path.join(".")}: ${i.message}`).join("; "),
    );
  }

  const email = parsed.data.email.toLowerCase().trim();
  const role = parsed.data.role;
  const code = generateCode();
  const expiresAt = new Date(Date.now() + INVITE_TTL_MS);

  try {
    const invite = await db.invite.create({
      data: {
        orgId: check.org.id,
        email,
        role,
        code,
        createdById: userId,
        expiresAt,
      },
    });

    const link = `${PLATFORM_URL}/invites/${code}`;
    const subject = `You're invited to ${check.org.name} on Crawfish`;
    if (process.env.NODE_ENV !== "production") {
      // eslint-disable-next-line no-console
      console.log(
        `[mock-email] To: ${email}\n[mock-email] Subject: ${subject}\n[mock-email] Link: ${link}`,
      );
    }

    return res.status(201).json({
      id: invite.id,
      email: invite.email,
      role: invite.role,
      code: invite.code,
      expiresAt: invite.expiresAt.toISOString(),
      mockEmail: { to: email, subject, link },
    });
  } catch (err) {
    return httpError(res, 500, "server_error", String(err));
  }
});

// GET /api/orgs/:orgId/invites — pending only
invitesRouter.get("/", async (req, res) => {
  const userId = requireUser(req);
  if (!userId) return httpError(res, 401, "unauthenticated", "Missing user.");

  const check = await ensureOrgMembership((req.params as { orgId: string }).orgId, userId);
  if (!check.ok) return httpError(res, check.status, check.code, check.msg);

  const now = new Date();
  const invites = await db.invite.findMany({
    where: {
      orgId: check.org.id,
      redeemedAt: null,
      expiresAt: { gt: now },
    },
    orderBy: { createdAt: "desc" },
    select: {
      id: true,
      email: true,
      role: true,
      createdAt: true,
      expiresAt: true,
      code: true,
    },
  });

  const isDev = process.env.NODE_ENV !== "production";
  return res.json(
    invites.map((i) => ({
      id: i.id,
      email: i.email,
      role: i.role,
      createdAt: i.createdAt.toISOString(),
      expiresAt: i.expiresAt.toISOString(),
      ...(isDev ? { code: i.code } : {}),
    })),
  );
});

// DELETE /api/orgs/:orgId/invites/:inviteId
invitesRouter.delete("/:inviteId", async (req, res) => {
  const userId = requireUser(req);
  if (!userId) return httpError(res, 401, "unauthenticated", "Missing user.");

  const params = req.params as { orgId: string; inviteId: string };
  const check = await ensureOrgMembership(params.orgId, userId);
  if (!check.ok) return httpError(res, check.status, check.code, check.msg);

  const invite = await db.invite.findUnique({ where: { id: params.inviteId } });
  if (!invite || invite.orgId !== check.org.id) {
    return httpError(res, 404, "not_found", "Invite not found.");
  }
  if (invite.redeemedAt) {
    return httpError(res, 410, "already_redeemed", "Invite already redeemed.");
  }

  await db.invite.delete({ where: { id: invite.id } });
  return res.status(204).end();
});

// ─── Public + accept ───────────────────────────────────────────────────────

// GET /api/invites/:code — public; no membership needed
publicInvitesRouter.get("/:code", async (req, res) => {
  const invite = await db.invite.findUnique({
    where: { code: req.params.code },
    include: { org: { select: { id: true, name: true } } },
  });
  if (!invite) return httpError(res, 404, "not_found", "Invite not found.");
  if (invite.redeemedAt) {
    return httpError(res, 410, "already_redeemed", "This invite has already been used.");
  }
  if (invite.expiresAt.getTime() < Date.now()) {
    return httpError(res, 410, "expired", "This invite has expired.");
  }
  return res.json({
    org: { id: invite.org.id, name: invite.org.name },
    email: invite.email,
    role: invite.role,
    expiresAt: invite.expiresAt.toISOString(),
  });
});

// POST /api/invites/:code/accept — auth required.
// publicInvitesRouter is mounted before the global authMiddleware (so GET
// remains anonymous), so the accept route applies auth inline.
import { authMiddleware as _acceptAuth } from "../middleware/auth.js";
publicInvitesRouter.post("/:code/accept", _acceptAuth, async (req, res) => {
  const userId = requireUser(req);
  if (!userId) return httpError(res, 401, "unauthenticated", "Sign in to accept this invite.");

  const invite = await db.invite.findUnique({
    where: { code: req.params.code },
    include: { org: { select: { id: true, name: true } } },
  });
  if (!invite) return httpError(res, 404, "not_found", "Invite not found.");
  if (invite.redeemedAt) {
    return httpError(res, 410, "already_redeemed", "This invite has already been used.");
  }
  if (invite.expiresAt.getTime() < Date.now()) {
    return httpError(res, 410, "expired", "This invite has expired.");
  }

  const user = await db.user.findUnique({ where: { id: userId } });
  if (!user) return httpError(res, 401, "unauthenticated", "User not found.");

  if (user.email.toLowerCase() !== invite.email.toLowerCase()) {
    return httpError(
      res,
      403,
      "EMAIL_MISMATCH",
      `This invite is for ${invite.email}`,
    );
  }

  try {
    await db.$transaction(async (tx) => {
      // Upsert the member row in case they were already invited via a different path.
      await tx.orgMember.upsert({
        where: { orgId_userId: { orgId: invite.orgId, userId: user.id } },
        update: {},
        create: { orgId: invite.orgId, userId: user.id, role: invite.role },
      });
      await tx.invite.update({
        where: { id: invite.id },
        data: { redeemedAt: new Date(), redeemedById: user.id },
      });
    });
  } catch (err) {
    return httpError(res, 500, "server_error", String(err));
  }

  return res.json({
    org: { id: invite.org.id, slug: invite.org.name, name: invite.org.name },
  });
});
