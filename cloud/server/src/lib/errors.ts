/**
 * httpError — uniform error response shape used by every route.
 *
 * Body: { error: { code, message } }
 *   code:    short machine string (e.g. "name_taken", "forbidden")
 *   message: human-readable
 */
import type { Response } from "express";

export function httpError(
  res: Response,
  status: number,
  code: string,
  message: string,
): Response {
  return res.status(status).json({ error: { code, message } });
}
