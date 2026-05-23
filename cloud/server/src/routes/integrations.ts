/**
 * Integration routes — connect GitHub/Linear to an org and bind Linear teams
 * to projects.
 *
 *   integrationsRouter      (gated)  mounted at /api/orgs/:orgId/integrations
 *   linearCallbackRouter    (public) mounted BEFORE authMiddleware
 *
 * The Linear OAuth callback is intentionally public — the browser redirect
 * from linear.app carries no platform session — but it recovers identity ONLY
 * from the signed `state` (audience "oauth-state"), so it performs no action
 * without a valid state. Tokens are exchanged server-side and never returned
 * to any client.
 */
import { Router } from "express";
import { z } from "zod";
import { db } from "../index.js";
import { httpError } from "../lib/errors.js";
import { requireMember } from "../lib/rbac.js";
import { getGithubToken } from "../lib/github.js";
import { signOauthState, verifyOauthState } from "../lib/jwt.js";
import {
  buildAuthorizeUrl,
  exchangeCode,
  listTeams,
  refreshAccessToken,
  LinearTokenExpired,
} from "../lib/linear.js";

export const integrationsRouter = Router({ mergeParams: true });
export const linearCallbackRouter = Router();

// GET /api/orgs/:orgId/integrations — provider connection status. Never
// returns tokens (T-20-07).
integrationsRouter.get("/", async (req, res) => {
  const ctx = await requireMember(req, (req.params as { orgId: string }).orgId);
  if (!ctx.ok) return httpError(res, ctx.status, ctx.code, "");

  // GitHub "connected" derives from the presence of a Clerk OAuth token.
  let githubConnected = false;
  try {
    await getGithubToken(ctx.userId);
    githubConnected = true;
  } catch {
    githubConnected = false;
  }

  const linear = await db.integration.findUnique({
    where: { orgId_provider: { orgId: ctx.orgId, provider: "linear" } },
    select: { externalWorkspaceName: true },
  });

  return res.json([
    { provider: "github", connected: githubConnected, externalWorkspaceName: null },
    {
      provider: "linear",
      connected: linear !== null,
      externalWorkspaceName: linear?.externalWorkspaceName ?? null,
    },
  ]);
});

// POST /api/orgs/:orgId/integrations/linear/connect — return the authorize URL
// with a signed CSRF state encoding userId+orgId.
integrationsRouter.post("/linear/connect", async (req, res) => {
  const ctx = await requireMember(req, (req.params as { orgId: string }).orgId);
  if (!ctx.ok) return httpError(res, ctx.status, ctx.code, "");
  try {
    const state = signOauthState(ctx.userId, ctx.orgId, "linear");
    return res.json({ authorizeUrl: buildAuthorizeUrl(state) });
  } catch (err) {
    return httpError(res, 500, "linear_not_configured", String(err));
  }
});

// GET /api/orgs/:orgId/integrations/linear/teams — the team list for the
// project picker. Refreshes the access token once on a 401.
integrationsRouter.get("/linear/teams", async (req, res) => {
  const ctx = await requireMember(req, (req.params as { orgId: string }).orgId);
  if (!ctx.ok) return httpError(res, ctx.status, ctx.code, "");

  const integration = await db.integration.findUnique({
    where: { orgId_provider: { orgId: ctx.orgId, provider: "linear" } },
  });
  if (!integration) return httpError(res, 409, "linear_not_connected", "");

  try {
    let teams;
    try {
      teams = await listTeams(integration.accessToken);
    } catch (err) {
      if (err instanceof LinearTokenExpired && integration.refreshToken) {
        const pair = await refreshAccessToken(integration.refreshToken);
        await db.integration.update({
          where: { id: integration.id },
          data: { accessToken: pair.access_token, refreshToken: pair.refresh_token },
        });
        teams = await listTeams(pair.access_token);
      } else {
        throw err;
      }
    }
    return res.json(teams);
  } catch (err) {
    return httpError(res, 502, "linear_error", String(err));
  }
});

const SelectTeamBody = z.object({
  projectId: z.string().min(1),
  teamId: z.string().min(1),
  teamKey: z.string().min(1).max(32),
});

// POST /api/orgs/:orgId/integrations/linear/select-team — bind a Linear team
// to one of the org's projects.
integrationsRouter.post("/linear/select-team", async (req, res) => {
  const ctx = await requireMember(req, (req.params as { orgId: string }).orgId);
  if (!ctx.ok) return httpError(res, ctx.status, ctx.code, "");

  const parsed = SelectTeamBody.safeParse(req.body);
  if (!parsed.success) return httpError(res, 400, "invalid_body", parsed.error.message);

  const integration = await db.integration.findUnique({
    where: { orgId_provider: { orgId: ctx.orgId, provider: "linear" } },
    select: { id: true },
  });
  if (!integration) return httpError(res, 409, "linear_not_connected", "");

  const project = await db.project.findFirst({
    where: { id: parsed.data.projectId, orgId: ctx.orgId },
    select: { id: true },
  });
  if (!project) return httpError(res, 404, "not_found", "");

  const updated = await db.project.update({
    where: { id: project.id },
    data: { linearTeamId: parsed.data.teamId, linearTeamKey: parsed.data.teamKey },
  });
  return res.json(updated);
});

// GET /api/integrations/linear/callback — PUBLIC. Validates the signed state
// (CSRF gate, T-20-02), exchanges the code server-side, stores the Integration
// with refresh token, then redirects to the platform connections page.
const PLATFORM_URL = process.env.PLATFORM_URL ?? "http://localhost:5174";

linearCallbackRouter.get("/", async (req, res) => {
  const code = typeof req.query.code === "string" ? req.query.code : "";
  const stateRaw = typeof req.query.state === "string" ? req.query.state : "";
  if (!code || !stateRaw) return httpError(res, 400, "invalid_state", "");

  let state: { sub: string; orgId: string; provider: string };
  try {
    state = verifyOauthState(stateRaw);
  } catch {
    // Tampered/expired/wrong-audience state → reject before any token exchange.
    return httpError(res, 400, "invalid_state", "");
  }
  if (state.provider !== "linear") return httpError(res, 400, "invalid_state", "");

  let tokens;
  try {
    tokens = await exchangeCode(code);
  } catch (err) {
    return httpError(res, 502, "linear_exchange_failed", String(err));
  }

  await db.integration.upsert({
    where: { orgId_provider: { orgId: state.orgId, provider: "linear" } },
    create: {
      orgId: state.orgId,
      provider: "linear",
      accessToken: tokens.access_token,
      refreshToken: tokens.refresh_token,
    },
    update: {
      accessToken: tokens.access_token,
      refreshToken: tokens.refresh_token,
    },
  });

  // Fixed app URL — never a request-supplied redirect target (T-20-08).
  return res.redirect(`${PLATFORM_URL}/?linear=connected`);
});
