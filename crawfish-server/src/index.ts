import express from "express";
import cors from "cors";
import { PrismaClient } from "@prisma/client";
import { fileURLToPath } from "node:url";

export const app = express();
const port = Number(process.env.PORT ?? 7882);
export const db = new PrismaClient();

const IS_PROD = process.env.NODE_ENV === "production";
const DEV_ORIGIN_REGEX = [
  /^http:\/\/localhost:(5173|5174|7881)$/,
  /^http:\/\/127\.0\.0\.1:(5173|5174|7881)$/,
];
const prodOrigins = (process.env.ALLOWED_ORIGINS ?? "")
  .split(",")
  .map((s) => s.trim())
  .filter(Boolean);
if (IS_PROD && prodOrigins.length === 0) {
  throw new Error("ALLOWED_ORIGINS is required in production (comma-separated origin allowlist).");
}
app.use(
  cors({
    origin: IS_PROD ? prodOrigins : DEV_ORIGIN_REGEX,
    credentials: true,
  }),
);
app.use(express.json({ limit: "1mb" }));

import { authMiddleware, dashSyncMiddleware } from "./middleware/auth.js";
import { healthRouter } from "./routes/health.js";
import { orgsRouter, meRouter, dashAgentsRouter } from "./routes/orgs.js";
import { deviceLinkRouter } from "./routes/deviceLink.js";
import { invitesRouter, publicInvitesRouter } from "./routes/invites.js";
import { projectsRouter } from "./routes/projects.js";

// Public routes (no user auth required) — mounted before authMiddleware.
app.use("/api/health", healthRouter);
app.use("/api/device-link", deviceLinkRouter); // POST is anon; GET poll is anon; POST /:code/redeem requires user auth (handled in-route).
app.use("/api/invites", publicInvitesRouter);

// Dash-sync route: accepts X-Crawfish-Token (aud-scoped JWT). Mounted as its
// own sub-app so the dash-sync middleware only fires here, not on user routes.
app.use("/api/dash", dashSyncMiddleware, dashAgentsRouter);
app.use("/api/dash/orgs/:orgId/projects", dashSyncMiddleware, projectsRouter);

// All remaining /api routes require user auth (Clerk in prod; dev shim
// otherwise).
app.use("/api", authMiddleware);

app.use("/api/orgs/:orgId/invites", invitesRouter);
app.use("/api/orgs/:orgId/projects", projectsRouter);
app.use("/api/orgs", orgsRouter);
app.use("/api/me", meRouter);

const isMain = (() => {
  try {
    return process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1];
  } catch {
    return false;
  }
})();

if (isMain) {
  app.listen(port, "127.0.0.1", () => {
    console.log(`crawfish-server: http://127.0.0.1:${port}`);
  });
}
