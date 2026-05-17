import { Router } from "express";
import { db } from "../index.js";

export const healthRouter = Router();

healthRouter.get("/", async (_req, res) => {
  try {
    await db.$queryRaw`SELECT 1`;
    res.json({ ok: true });
  } catch (e) {
    res.status(500).json({ ok: false, error: String(e) });
  }
});
