import { createClerkClient, type ClerkClient } from "@clerk/backend";

export class GithubNotConnected extends Error {
  constructor() {
    super("GitHub connection missing or revoked");
  }
}

let cached: ClerkClient | null = null;

export function getClerkClient(): ClerkClient {
  if (cached) return cached;
  cached = createClerkClient({ secretKey: process.env.CLERK_SECRET_KEY ?? "" });
  return cached;
}

/**
 * For tests: inject a stub client. Pass null to reset.
 */
export function _setClerkClientForTests(stub: ClerkClient | null): void {
  cached = stub;
}

export async function getGithubToken(userId: string): Promise<string> {
  const client = getClerkClient();
  const res = await client.users.getUserOauthAccessToken(userId, "oauth_github");
  const token = res.data?.[0]?.token;
  if (!token) throw new GithubNotConnected();
  return token;
}
