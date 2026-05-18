import { Router } from "express";
import { httpError } from "../lib/errors.js";
import {
  fetchRepoByName,
  getGithubToken,
  GithubNotConnected,
  GithubRepoNotFound,
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

githubRouter.get("/repos/:owner/:name/check", async (req, res) => {
  const userId = req.userId;
  if (!userId) return httpError(res, 401, "unauthenticated", "");

  const { owner, name } = req.params;

  let token: string;
  try {
    token = await getGithubToken(userId);
  } catch (err) {
    if (err instanceof GithubNotConnected)
      return httpError(res, 409, "github_disconnected", "");
    return httpError(res, 502, "github_error", String(err));
  }

  try {
    const repo = await fetchRepoByName(token, owner, name);
    return res.json(repo);
  } catch (err) {
    if (err instanceof GithubRepoNotFound)
      return httpError(res, 404, "repo_not_found", "");
    return httpError(res, 502, "github_error", String(err));
  }
});

/**
 * Dash-sync–only GitHub routes. Mounted under /api/dash/github behind
 * dashSyncMiddleware so only device-linked desktops (with a valid
 * X-Crawfish-Token JWT) can call them. The clone-token endpoint hands the
 * raw GitHub OAuth token to the desktop so it can `git clone` directly,
 * without proxying every clone through the server.
 */
export const dashGithubRouter = Router();

dashGithubRouter.get("/clone-token", async (req, res) => {
  const userId = req.userId;
  if (!userId) return httpError(res, 401, "unauthenticated", "");

  let token: string;
  try {
    token = await getGithubToken(userId);
  } catch (err) {
    if (err instanceof GithubNotConnected)
      return httpError(res, 409, "github_disconnected", "");
    return httpError(res, 502, "github_error", String(err));
  }

  return res.json({ token, expires_at: null });
});
