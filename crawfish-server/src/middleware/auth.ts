import type { Request, Response, NextFunction } from "express";
import { db } from "../index.js";
import { verifyOrgToken } from "../lib/jwt.js";

const DEV_USER_ID_HEADER = "x-user-id";
const DEV_USER_EMAIL_HEADER = "x-user-email";
const CRAWFISH_TOKEN_HEADER = "x-crawfish-token";
const DEV_FALLBACK_USER = "dev-user";

let devUserEnsured = false;

async function ensureDevUser(externalId: string, emailOverride?: string): Promise<string> {
  // Reuse a single User row keyed by a stable email derived from the header
  // value. In dev mode every header value becomes its own user.
  // If X-User-Email is supplied (tests / email-match flows), use that email
  // instead of the synthetic `<id>@local` form so invite EMAIL_MISMATCH
  // checks can be exercised end-to-end.
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

export async function authMiddleware(
  req: Request,
  res: Response,
  next: NextFunction,
): Promise<void> {
  try {
    // 1. Dash-issued JWT (X-Crawfish-Token) — used by the dash-server when
    //    syncing agent metadata for an org that's been linked online.
    const crawfishTok = req.header(CRAWFISH_TOKEN_HEADER);
    if (crawfishTok) {
      try {
        const decoded = verifyOrgToken(crawfishTok);
        req.userId = decoded.sub;
        return next();
      } catch (err) {
        res.status(401).json({ error: { code: "invalid_token", message: String(err) } });
        return;
      }
    }

    if (process.env.CLERK_SECRET_KEY) {
      // TODO(P1): verify the Clerk JWT from Authorization: Bearer <token>,
      // resolve to a User row by clerkId. For now this scaffold falls
      // through to dev behavior so the rest of the server is exercisable.
    }

    const headerVal = req.header(DEV_USER_ID_HEADER) ?? DEV_FALLBACK_USER;
    const emailOverride = req.header(DEV_USER_EMAIL_HEADER);
    const userId = await ensureDevUser(headerVal, emailOverride);
    req.userId = userId;
    devUserEnsured = true;
    next();
  } catch (err) {
    res.status(500).json({ ok: false, error: String(err) });
  }
}

// Exported for tests / introspection.
export function _devUserEnsured(): boolean {
  return devUserEnsured;
}
