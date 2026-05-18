import { describe, it, expect, vi, beforeEach, afterAll } from "vitest";
import request from "supertest";
import { app } from "../../src/index.js";
import {
  getGithubToken,
  GithubNotConnected,
  _setClerkClientForTests,
} from "../../src/lib/github.js";
import { signOrgToken } from "../../src/lib/jwt.js";

const getUserOauthAccessToken = vi.fn();

const realFetch = globalThis.fetch;

afterAll(() => {
  _setClerkClientForTests(null);
  globalThis.fetch = realFetch;
});

beforeEach(() => {
  getUserOauthAccessToken.mockReset();
  _setClerkClientForTests({
    users: { getUserOauthAccessToken },
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
  } as any);
  globalThis.fetch = realFetch;
});

describe("getGithubToken", () => {
  it("returns the token when Clerk has one", async () => {
    getUserOauthAccessToken.mockResolvedValue({
      data: [{ token: "gho_test_abc" }],
    });
    expect(await getGithubToken("user_1")).toBe("gho_test_abc");
    expect(getUserOauthAccessToken).toHaveBeenCalledWith("user_1", "oauth_github");
  });

  it("throws GithubNotConnected when Clerk returns no token", async () => {
    getUserOauthAccessToken.mockResolvedValue({ data: [] });
    await expect(getGithubToken("user_1")).rejects.toBeInstanceOf(GithubNotConnected);
  });
});

describe("GET /api/github/repos", () => {
  const sampleRepos = [
    {
      id: 1,
      full_name: "octo/hello",
      default_branch: "main",
      private: false,
      updated_at: "2026-05-10T00:00:00Z",
    },
    {
      id: 2,
      full_name: "octo/world",
      default_branch: "main",
      private: true,
      updated_at: "2026-05-09T00:00:00Z",
    },
    {
      id: 3,
      full_name: "acme/widgets",
      default_branch: "master",
      private: false,
      updated_at: "2026-05-08T00:00:00Z",
    },
  ];

  function stubFetchOk(payload: unknown) {
    globalThis.fetch = (async () =>
      new Response(JSON.stringify(payload), {
        status: 200,
        headers: { "content-type": "application/json" },
      })) as typeof fetch;
  }

  it("returns the user's repos", async () => {
    getUserOauthAccessToken.mockResolvedValue({ data: [{ token: "gho_test" }] });
    stubFetchOk(sampleRepos);
    const res = await request(app).get("/api/github/repos").set("X-User-Id", "gh-user-a");
    expect(res.status).toBe(200);
    expect(res.body).toHaveLength(3);
    expect(res.body[0]).toMatchObject({
      id: 1,
      full_name: "octo/hello",
      default_branch: "main",
      private: false,
      updated_at: "2026-05-10T00:00:00Z",
    });
  });

  it("filters by q against full_name (case-insensitive)", async () => {
    getUserOauthAccessToken.mockResolvedValue({ data: [{ token: "gho_test" }] });
    stubFetchOk(sampleRepos);
    const res = await request(app)
      .get("/api/github/repos?q=ACME")
      .set("X-User-Id", "gh-user-b");
    expect(res.status).toBe(200);
    expect(res.body).toHaveLength(1);
    expect(res.body[0].full_name).toBe("acme/widgets");
  });

  it("returns 409 github_disconnected when Clerk has no token", async () => {
    getUserOauthAccessToken.mockResolvedValue({ data: [] });
    const res = await request(app).get("/api/github/repos").set("X-User-Id", "gh-user-c");
    expect(res.status).toBe(409);
    expect(res.body.error.code).toBe("github_disconnected");
  });
});

describe("GET /api/github/repos/:owner/:name/check", () => {
  const repoPayload = {
    id: 42,
    full_name: "octo/hello",
    default_branch: "main",
    private: false,
  };

  function stubFetchOk(payload: unknown) {
    globalThis.fetch = (async () =>
      new Response(JSON.stringify(payload), {
        status: 200,
        headers: { "content-type": "application/json" },
      })) as typeof fetch;
  }

  function stubFetchStatus(status: number) {
    globalThis.fetch = (async () =>
      new Response("{}", {
        status,
        headers: { "content-type": "application/json" },
      })) as typeof fetch;
  }

  it("returns repo metadata when the user has access", async () => {
    getUserOauthAccessToken.mockResolvedValue({ data: [{ token: "gho_test" }] });
    stubFetchOk(repoPayload);
    const res = await request(app)
      .get("/api/github/repos/octo/hello/check")
      .set("X-User-Id", "gh-user-d");
    expect(res.status).toBe(200);
    expect(res.body).toEqual(repoPayload);
  });

  it("returns 404 repo_not_found when GitHub 404s", async () => {
    getUserOauthAccessToken.mockResolvedValue({ data: [{ token: "gho_test" }] });
    stubFetchStatus(404);
    const res = await request(app)
      .get("/api/github/repos/octo/missing/check")
      .set("X-User-Id", "gh-user-e");
    expect(res.status).toBe(404);
    expect(res.body.error.code).toBe("repo_not_found");
  });

  it("returns 409 github_disconnected when Clerk has no token", async () => {
    getUserOauthAccessToken.mockResolvedValue({ data: [] });
    const res = await request(app)
      .get("/api/github/repos/octo/hello/check")
      .set("X-User-Id", "gh-user-f");
    expect(res.status).toBe(409);
    expect(res.body.error.code).toBe("github_disconnected");
  });
});

describe("GET /api/dash/github/clone-token", () => {
  it("returns the Clerk-stored GitHub token when called with a valid X-Crawfish-Token", async () => {
    getUserOauthAccessToken.mockResolvedValue({ data: [{ token: "gho_clone_xyz" }] });
    const jwt = signOrgToken("user_clone_1", "org_clone_1");
    const res = await request(app)
      .get("/api/dash/github/clone-token")
      .set("X-Crawfish-Token", jwt);
    expect(res.status).toBe(200);
    expect(res.body.token).toBe("gho_clone_xyz");
    expect(res.body.expires_at).toBeNull();
    expect(getUserOauthAccessToken).toHaveBeenCalledWith("user_clone_1", "oauth_github");
  });

  it("returns 401 when no X-Crawfish-Token is present (web auth headers ignored)", async () => {
    const res = await request(app)
      .get("/api/dash/github/clone-token")
      .set("X-User-Id", "gh-user-web");
    expect(res.status).toBe(401);
  });
});
