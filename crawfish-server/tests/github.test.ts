import { describe, it, expect, vi } from "vitest";
import { getGithubToken, GithubNotConnected } from "../src/lib/github.js";

vi.mock("@clerk/clerk-sdk-node", () => ({
  clerkClient: {
    users: {
      getUserOauthAccessToken: vi.fn(),
    },
  },
}));

import { clerkClient } from "@clerk/clerk-sdk-node";

describe("getGithubToken", () => {
  it("returns the token when Clerk has one", async () => {
    (clerkClient.users.getUserOauthAccessToken as any).mockResolvedValue({
      data: [{ token: "gho_test_abc" }],
    });
    expect(await getGithubToken("user_1")).toBe("gho_test_abc");
  });

  it("throws GithubNotConnected when Clerk returns no token", async () => {
    (clerkClient.users.getUserOauthAccessToken as any).mockResolvedValue({ data: [] });
    await expect(getGithubToken("user_1")).rejects.toBeInstanceOf(GithubNotConnected);
  });
});
