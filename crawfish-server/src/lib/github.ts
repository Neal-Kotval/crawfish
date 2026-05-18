import { clerkClient } from "@clerk/clerk-sdk-node";

export class GithubNotConnected extends Error {
  constructor() {
    super("GitHub connection missing or revoked");
  }
}

export async function getGithubToken(userId: string): Promise<string> {
  const res = await clerkClient.users.getUserOauthAccessToken(userId, "oauth_github");
  const token = res.data?.[0]?.token;
  if (!token) throw new GithubNotConnected();
  return token;
}
