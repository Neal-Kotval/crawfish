/**
 * JWT helpers for device-link tokens.
 *
 * - JWT_SECRET comes from env. If absent in dev, we generate a 64-byte hex
 *   secret and *append* it to .env so subsequent restarts use the same key.
 * - Tokens have a 90-day TTL and carry `{ sub: userId, orgId }`.
 */
import jwt from "jsonwebtoken";
import { randomBytes } from "node:crypto";
import { existsSync, readFileSync, appendFileSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";

const ENV_PATH = resolve(process.cwd(), ".env");
let cachedSecret: string | null = null;

export function getOrCreateJwtSecret(): string {
  if (cachedSecret) return cachedSecret;
  const fromEnv = process.env.JWT_SECRET;
  if (fromEnv && fromEnv.length >= 32) {
    cachedSecret = fromEnv;
    return cachedSecret;
  }
  // Generate, persist to .env (so next boot reuses it), and warn once.
  const generated = randomBytes(64).toString("hex");
  try {
    if (existsSync(ENV_PATH)) {
      const raw = readFileSync(ENV_PATH, "utf8");
      if (!/^JWT_SECRET=/m.test(raw)) {
        const sep = raw.endsWith("\n") ? "" : "\n";
        appendFileSync(ENV_PATH, `${sep}JWT_SECRET="${generated}"\n`, "utf8");
      }
    } else {
      writeFileSync(ENV_PATH, `JWT_SECRET="${generated}"\n`, "utf8");
    }
    // eslint-disable-next-line no-console
    console.warn(
      "[jwt] JWT_SECRET was missing; generated a new one and wrote it to .env. " +
        "Restart the server to load it from env on next boot.",
    );
  } catch (err) {
    // eslint-disable-next-line no-console
    console.warn("[jwt] Could not persist generated JWT_SECRET to .env:", err);
  }
  process.env.JWT_SECRET = generated;
  cachedSecret = generated;
  return cachedSecret;
}

export interface OrgTokenPayload {
  sub: string;
  orgId: string;
}

export function signOrgToken(userId: string, orgId: string): string {
  const secret = getOrCreateJwtSecret();
  return jwt.sign({ sub: userId, orgId }, secret, { expiresIn: "90d" });
}

export function verifyOrgToken(token: string): OrgTokenPayload {
  const secret = getOrCreateJwtSecret();
  const decoded = jwt.verify(token, secret) as jwt.JwtPayload;
  if (typeof decoded.sub !== "string" || typeof decoded.orgId !== "string") {
    throw new Error("invalid token payload");
  }
  return { sub: decoded.sub, orgId: decoded.orgId };
}
