import { Router } from "express";
import { httpError } from "../lib/errors.js";
import {
  getGithubToken,
  GithubNotConnected,
  listUserRepos,
} from "../lib/github.js";

export const githubRouter = Router();

githubRouter.get("/repos", async (req, res) => {
  const userId = req.userId;
  if (!userId) return httpError(res, 401, "unauthenticated", "");

  const q = typeof req.query.q === "string" ? req.query.q.toLowerCase() : "";
  const pageRaw = typeof req.query.page === "string" ? parseInt(req.query.page, 10) : 1;
  const page = Number.isFinite(pageRaw) && pageRaw > 0 ? pageRaw : 1;

  let token: string;
  try {
    token = await getGithubToken(userId);
  } catch (err) {
    if (err instanceof GithubNotConnected)
      return httpError(res, 409, "github_disconnected", "");
    return httpError(res, 502, "github_error", String(err));
  }

  let repos;
  try {
    repos = await listUserRepos(token, page);
  } catch (err) {
    return httpError(res, 502, "github_error", String(err));
  }

  const filtered = q ? repos.filter((r) => r.full_name.toLowerCase().includes(q)) : repos;
  return res.json(filtered);
});
