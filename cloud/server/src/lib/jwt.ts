/**
 * JWT helpers for device-link tokens.
 *
 * JWT_SECRET MUST be set in prod (boot fails otherwise). In dev, if missing
 * we generate an in-memory secret and log it once. We never write to .env.
 *
 * Tokens carry `{ sub: userId, orgId, aud: "dash-sync" }` and TTL 30 days.
 * Verifiers MUST check `aud` so dash-sync tokens can only authorize the
 * dash-sync surface, not arbitrary user routes.
 */
import jwt from "jsonwebtoken";
import { randomBytes } from "node:crypto";

const TOKEN_AUDIENCE = "dash-sync";
let cachedSecret: string | null = null;

export function getOrCreateJwtSecret(): string {
  if (cachedSecret) return cachedSecret;
  const fromEnv = process.env.JWT_SECRET;
  if (fromEnv && fromEnv.length >= 32) {
    cachedSecret = fromEnv;
    return cachedSecret;
  }
  if (process.env.NODE_ENV === "production") {
    throw new Error(
      "JWT_SECRET is required in production (>= 32 chars). Set it in the deployment environment.",
    );
  }
  const generated = randomBytes(64).toString("hex");
  process.env.JWT_SECRET = generated;
  cachedSecret = generated;
  // eslint-disable-next-line no-console
  console.warn(
    "[jwt] JWT_SECRET missing in dev; generated an in-memory secret. " +
      "Set JWT_SECRET in your .env to persist tokens across restarts.",
  );
  return cachedSecret;
}

export interface OrgTokenPayload {
  sub: string;
  orgId: string;
}

export function signOrgToken(userId: string, orgId: string): string {
  const secret = getOrCreateJwtSecret();
  return jwt.sign({ sub: userId, orgId }, secret, {
    audience: TOKEN_AUDIENCE,
    expiresIn: "30d",
  });
}

export function verifyOrgToken(token: string): OrgTokenPayload {
  const secret = getOrCreateJwtSecret();
  const decoded = jwt.verify(token, secret, { audience: TOKEN_AUDIENCE }) as jwt.JwtPayload;
  if (typeof decoded.sub !== "string" || typeof decoded.orgId !== "string") {
    throw new Error("invalid token payload");
  }
  return { sub: decoded.sub, orgId: decoded.orgId };
}

// ---------------------------------------------------------------------------
// OAuth-state tokens.
//
// Used as the CSRF `state` for the Linear (and future) OAuth flow. A DISTINCT
// audience from dash-sync is the privilege-separation control: a dash-sync
// token can never authorize the OAuth callback and vice-versa. Short TTL — the
// state is only alive for the redirect round-trip.
// ---------------------------------------------------------------------------

const OAUTH_STATE_AUDIENCE = "oauth-state";

export interface OauthStatePayload {
  sub: string; // userId who initiated the connect
  orgId: string; // org the integration binds to
  provider: string; // "linear"
}

export function signOauthState(userId: string, orgId: string, provider: string): string {
  const secret = getOrCreateJwtSecret();
  return jwt.sign({ sub: userId, orgId, provider }, secret, {
    audience: OAUTH_STATE_AUDIENCE,
    expiresIn: "10m",
  });
}

export function verifyOauthState(token: string): OauthStatePayload {
  const secret = getOrCreateJwtSecret();
  const decoded = jwt.verify(token, secret, { audience: OAUTH_STATE_AUDIENCE }) as jwt.JwtPayload;
  if (
    typeof decoded.sub !== "string" ||
    typeof decoded.orgId !== "string" ||
    typeof decoded.provider !== "string"
  ) {
    throw new Error("invalid oauth state payload");
  }
  return { sub: decoded.sub, orgId: decoded.orgId, provider: decoded.provider };
}
