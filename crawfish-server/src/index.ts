import express from "express";
import cors from "cors";
import { PrismaClient } from "@prisma/client";
import { fileURLToPath } from "node:url";

export const app = express();
const port = Number(process.env.PORT ?? 7882);
export const db = new PrismaClient();

app.use(cors({
  origin: [/^http:\/\/localhost:(5173|5174|7881)$/, /^http:\/\/127\.0\.0\.1:(5173|5174|7881)$/],
  credentials: true,
}));
app.use(express.json({ limit: "1mb" }));

// Dev-mode auth shim: trust X-User-Id header from any request when CLERK_SECRET_KEY
// is unset. Real Clerk JWT verification lands in a follow-up task.
import { authMiddleware } from "./middleware/auth.js";
import { healthRouter } from "./routes/health.js";
import { orgsRouter, meRouter } from "./routes/orgs.js";
import { deviceLinkRouter } from "./routes/deviceLink.js";
import { invitesRouter, publicInvitesRouter } from "./routes/invites.js";

app.use(authMiddleware);

app.use("/api/health", healthRouter);
app.use("/api/orgs/:orgId/invites", invitesRouter);
app.use("/api/orgs", orgsRouter);
app.use("/api/me", meRouter);
app.use("/api/device-link", deviceLinkRouter);
app.use("/api/invites", publicInvitesRouter);

// Only start the HTTP listener when this file is executed directly
// (i.e., not when imported by tests).
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
