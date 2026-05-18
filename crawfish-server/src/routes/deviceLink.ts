/**
 * Device-link routes — GitHub-style device flow that binds a local Dash org
 * to a server-side Org row.
 *
 * Flow:
 *   1. Dash POSTs /api/device-link (no auth) with the localOrg payload.
 *      We find-or-create the Org, replace AgentMeta, mint a short code.
 *   2. User opens <PLATFORM_BASE_URL>/link/<code> in a browser, signs in
 *      via Clerk, and POSTs /api/device-link/:code/redeem to confirm.
 *      We attach the user as founder and mint a JWT, stored on the row.
 *   3. Dash polls GET /api/device-link/:code. Once redeemedAt is set, we
 *      hand back the JWT (single-use; the row is deleted after read).
 */
import { Router } from "express";
import { z } from "zod";
import { customAlphabet } from "nanoid";
import { db } from "../index.js";
import { httpError } from "../lib/errors.js";
import { signOrgToken } from "../lib/jwt.js";

export const deviceLinkRouter = Router();

const CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"; // drops I/L/O/0/1
// 10 chars from a 32-letter alphabet -> 50 bits, generated from the CSPRNG.
const newCode = customAlphabet(CODE_ALPHABET, 10);

const TEN_MIN_MS = 10 * 60 * 1000;

const PLATFORM_BASE_URL = (process.env.PLATFORM_BASE_URL ?? "http://localhost:5174").replace(/\/+$/, "");

const AgentSchema = z.object({
  name: z.string().min(1).max(64),
  role: z.string().min(1).max(280),
  runtime: z.string().min(1).max(64),
});

const PostBodySchema = z.object({
  localOrg: z.object({
    name: z
      .string()
      .min(1)
      .max(64)
      .regex(/^[a-z0-9][a-z0-9_-]*$/, "lowercase letters/digits/dashes/underscores only"),
    project: z.string().max(280).optional(),
    teamSize: z.string().max(64).optional(),
    primaryClient: z.string().max(64).optional(),
    agents: z.array(AgentSchema).default([]),
  }),
});

// POST /api/device-link — no auth; Dash hits this anonymously.
deviceLinkRouter.post("/", async (req, res) => {
  const parsed = PostBodySchema.safeParse(req.body);
  if (!parsed.success) {
    return httpError(
      res,
      400,
      "invalid_body",
      parsed.error.issues.map((i) => `${i.path.join(".")}: ${i.message}`).join("; "),
    );
  }
  const { localOrg } = parsed.data;

  try {
    const code = newCode();
    const expiresAt = new Date(Date.now() + TEN_MIN_MS);

    await db.$transaction(async (tx) => {
      // If the name is already claimed by an org that has a founder, refuse
      // anonymous mutation. Otherwise the squatter scenario (H1/H2) lets a
      // stranger pre-claim a name and silently attach to a real user's data.
      const existing = await tx.org.findUnique({
        where: { name: localOrg.name },
        include: { members: { where: { role: "founder" }, select: { id: true } } },
      });
      if (existing && existing.members.length > 0) {
        throw new Error("name_unavailable");
      }

      const org = existing
        ? existing
        : await tx.org.create({
            data: {
              name: localOrg.name,
              project: localOrg.project ?? null,
              teamSize: localOrg.teamSize ?? null,
              primaryClient: localOrg.primaryClient ?? null,
            },
          });

      // Sync-style: Dash is the source of truth on first link. Replace.
      await tx.agentMeta.deleteMany({ where: { orgId: org.id } });
      if (localOrg.agents.length > 0) {
        await tx.agentMeta.createMany({
          data: localOrg.agents.map((a) => ({
            orgId: org.id,
            name: a.name,
            role: a.role,
            runtime: a.runtime,
          })),
        });
      }

      await tx.deviceLinkCode.create({
        data: { code, orgId: org.id, expiresAt },
      });
    });

    return res.status(201).json({
      code,
      expiresIn: 600,
      verifyUrl: `${PLATFORM_BASE_URL}/link/${code}`,
    });
  } catch (err) {
    if (err instanceof Error && err.message === "name_unavailable") {
      return httpError(res, 409, "name_unavailable", "That org name is not available.");
    }
    return httpError(res, 500, "server_error", String(err));
  }
});

// GET /api/device-link/:code — no auth; Dash polls this.
deviceLinkRouter.get("/:code", async (req, res) => {
  const code = req.params.code.toUpperCase();
  const row = await db.deviceLinkCode.findUnique({
    where: { code },
    include: { org: { select: { id: true, name: true } } },
  });
  if (!row) return httpError(res, 404, "not_found", "Device-link code not found.");
  if (row.expiresAt.getTime() < Date.now()) {
    await db.deviceLinkCode.delete({ where: { code } }).catch(() => {});
    return res.status(410).json({ error: { code: "expired", message: "Code expired." } });
  }
  if (!row.redeemedAt) {
    return res.json({ pending: true });
  }
  // Single-use: after handing back the token, drop the row.
  const authToken = row.authToken;
  await db.deviceLinkCode.delete({ where: { code } }).catch(() => {});
  return res.json({
    redeemedAt: row.redeemedAt.toISOString(),
    authToken,
    org: { id: row.org.id, name: row.org.name },
  });
});

// POST /api/device-link/:code/redeem — auth required (signed-in user).
// Note: deviceLinkRouter is mounted BEFORE authMiddleware in index.ts, so we
// run authMiddleware inline here.
import { authMiddleware as _redeemAuth } from "../middleware/auth.js";
deviceLinkRouter.post("/:code/redeem", _redeemAuth, async (req, res) => {
  const userId = req.userId;
  if (!userId) return httpError(res, 401, "unauthenticated", "Sign in to confirm a device.");

  const code = req.params.code.toUpperCase();
  const row = await db.deviceLinkCode.findUnique({ where: { code } });
  if (!row) return httpError(res, 404, "not_found", "Device-link code not found.");
  if (row.expiresAt.getTime() < Date.now()) {
    await db.deviceLinkCode.delete({ where: { code } }).catch(() => {});
    return res.status(410).json({ error: { code: "expired", message: "Code expired." } });
  }
  if (row.redeemedAt) {
    return res.status(409).json({ error: { code: "already_redeemed", message: "Code already used." } });
  }

  try {
    const org = await db.org.findUnique({
      where: { id: row.orgId },
      select: { id: true, name: true },
    });
    if (!org) return httpError(res, 404, "not_found", "Org no longer exists.");

    // Membership rules: only allow founder-self-promotion if the org has no
    // founder yet. Otherwise add as contributor (or keep existing role).
    // This blocks the H2 path where a pre-existing member auto-becomes
    // founder simply by redeeming.
    const existingFounder = await db.orgMember.findFirst({
      where: { orgId: org.id, role: "founder" },
      select: { userId: true },
    });
    const existing = await db.orgMember.findUnique({
      where: { orgId_userId: { orgId: org.id, userId } },
    });
    const canBeFounder = !existingFounder || existingFounder.userId === userId;
    if (existing) {
      if (canBeFounder && existing.role !== "founder") {
        await db.orgMember.update({
          where: { orgId_userId: { orgId: org.id, userId } },
          data: { role: "founder" },
        });
      }
      // else: keep existing role; don't silently change it.
    } else {
      await db.orgMember.create({
        data: {
          orgId: org.id,
          userId,
          role: canBeFounder ? "founder" : "contributor",
        },
      });
    }

    const authToken = signOrgToken(userId, org.id);
    await db.deviceLinkCode.update({
      where: { code },
      data: {
        redeemedAt: new Date(),
        redeemedByUserId: userId,
        authToken,
      },
    });

    return res.json({ ok: true, org: { id: org.id, name: org.name } });
  } catch (err) {
    return httpError(res, 500, "server_error", String(err));
  }
});
