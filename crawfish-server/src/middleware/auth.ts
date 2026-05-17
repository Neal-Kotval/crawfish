import type { Request, Response, NextFunction } from "express";
import { db } from "../index.js";

const DEV_USER_ID_HEADER = "x-user-id";
const DEV_FALLBACK_USER = "dev-user";

let devUserEnsured = false;

async function ensureDevUser(externalId: string): Promise<string> {
  // Reuse a single User row keyed by a stable email derived from the header
  // value. In dev mode every header value becomes its own user.
  const email = externalId === DEV_FALLBACK_USER
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
    if (process.env.CLERK_SECRET_KEY) {
      // TODO(P1): verify the Clerk JWT from Authorization: Bearer <token>,
      // resolve to a User row by clerkId. For now this scaffold falls
      // through to dev behavior so the rest of the server is exercisable.
    }

    const headerVal = req.header(DEV_USER_ID_HEADER) ?? DEV_FALLBACK_USER;
    const userId = await ensureDevUser(headerVal);
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
