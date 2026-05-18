import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  getGithubToken,
  GithubNotConnected,
  _setClerkClientForTests,
} from "../../src/lib/github.js";

const getUserOauthAccessToken = vi.fn();

beforeEach(() => {
  getUserOauthAccessToken.mockReset();
  _setClerkClientForTests({
    // Only the surface we use is stubbed; cast to satisfy the ClerkClient type.
    users: { getUserOauthAccessToken },
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
  } as any);
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
