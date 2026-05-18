import type { Request, Response, NextFunction } from "express";
import { verifyToken } from "@clerk/backend";
import { db } from "../index.js";
import { verifyOrgToken } from "../lib/jwt.js";
import { getClerkClient } from "../lib/github.js";

const DEV_USER_ID_HEADER = "x-user-id";
const DEV_USER_EMAIL_HEADER = "x-user-email";
const CRAWFISH_TOKEN_HEADER = "x-crawfish-token";
const DEV_FALLBACK_USER = "dev-user";

const IS_PROD = process.env.NODE_ENV === "production";
// Dev shim runs whenever NODE_ENV !== "production". The presence of a Clerk
// key in dev .env doesn't disable the shim (dev boxes routinely have test
// keys), but in prod the shim is never available and we fail closed.
const DEV_SHIM_ENABLED = !IS_PROD;

let devUserEnsured = false;

async function ensureDevUser(externalId: string, emailOverride?: string): Promise<string> {
  const email = emailOverride
    ? emailOverride.toLowerCase().trim()
    : externalId === DEV_FALLBACK_USER
      ? "dev@local"
      : `${externalId}@local`;
  const user = await db.user.upsert({
    where: { email },
    update: {},
    create: {
      email,
      name: externalId === DEV_FALLBACK_USER ? "dev" : externalId,
    },
  });
  return user.id;
}

/**
 * Auth middleware. Order:
 *   1. X-Crawfish-Token (dash-sync JWT, aud-scoped). Only honored for routes
 *      that opt in via `requireDashSync` — this middleware annotates the req
 *      but does NOT accept dash tokens as user-equivalent on user routes.
 *   2. Clerk Bearer in prod. Not yet wired; until then any unauth'd request
 *      in prod returns 401 (no fall-through to dev).
 *   3. Dev shim (X-User-Id), only when NODE_ENV !== "production" AND no
 *      CLERK_SECRET_KEY is configured.
 */
export async function authMiddleware(
  req: Request,
  res: Response,
  next: NextFunction,
): Promise<void> {
  try {
    if (DEV_SHIM_ENABLED) {
      const headerVal = req.header(DEV_USER_ID_HEADER) ?? DEV_FALLBACK_USER;
      const emailOverride = req.header(DEV_USER_EMAIL_HEADER);
      const userId = await ensureDevUser(headerVal, emailOverride);
      req.userId = userId;
      devUserEnsured = true;
      return next();
    }

    // Prod path. Verify a Clerk Bearer token and resolve to a User row by
    // clerkId. Fails closed — no fall-through to the dev shim.
    if (process.env.CLERK_SECRET_KEY) {
      const authHeader = req.header("authorization") ?? "";
      const m = /^Bearer\s+(.+)$/i.exec(authHeader);
      if (!m) {
        res.status(401).json({
          error: { code: "invalid_token", message: "Missing Bearer token." },
        });
        return;
      }
      const token = m[1];
      let clerkUserId: string;
      try {
        const payload = await verifyToken(token, {
          secretKey: process.env.CLERK_SECRET_KEY,
        });
        if (typeof payload.sub !== "string" || !payload.sub) {
          throw new Error("missing sub");
        }
        clerkUserId = payload.sub;
      } catch (err) {
        res.status(401).json({
          error: { code: "invalid_token", message: String(err) },
        });
        return;
      }

      // Try to find an existing user by clerkId first; if missing, fetch the
      // primary email from Clerk and upsert. Email is unique on User, so if a
      // row already exists for that email (e.g. created in dev), link it.
      let user = await db.user.findUnique({ where: { clerkId: clerkUserId } });
      if (!user) {
        let email: string;
        try {
          const clerkUser = await getClerkClient().users.getUser(clerkUserId);
          const primaryId = clerkUser.primaryEmailAddressId;
          const primary = clerkUser.emailAddresses.find((e) => e.id === primaryId)
            ?? clerkUser.emailAddresses[0];
          if (!primary?.emailAddress) throw new Error("no primary email");
          email = primary.emailAddress.toLowerCase().trim();
        } catch (err) {
          res.status(401).json({
            error: { code: "invalid_token", message: `clerk user lookup failed: ${String(err)}` },
          });
          return;
        }
        user = await db.user.upsert({
          where: { email },
          update: { clerkId: clerkUserId },
          create: { clerkId: clerkUserId, email },
        });
      }
      req.userId = user.id;
      return next();
    }

    res.status(401).json({
      error: {
        code: "unauthenticated",
        message: "Authentication required.",
      },
    });
  } catch (err) {
    res.status(500).json({ ok: false, error: String(err) });
  }
}

/**
 * Middleware for routes that accept dash-sync JWTs (e.g. PUT /api/orgs/:id/agents).
 * Mount BEFORE authMiddleware on those routes; if the token is valid, set
 * req.userId and skip user auth. If absent, fall through to authMiddleware.
 */
export function dashSyncMiddleware(
  req: Request,
  res: Response,
  next: NextFunction,
): void {
  const tok = req.header(CRAWFISH_TOKEN_HEADER);
  if (!tok) return next();
  try {
    const decoded = verifyOrgToken(tok);
    req.userId = decoded.sub;
    (req as Request & { dashOrgId?: string }).dashOrgId = decoded.orgId;
    return next();
  } catch (err) {
    res.status(401).json({ error: { code: "invalid_token", message: String(err) } });
  }
}

export function _devUserEnsured(): boolean {
  return devUserEnsured;
}
