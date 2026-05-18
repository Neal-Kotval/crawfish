/**
 * Workspace-ensure helper.
 *
 * One user, one workspace (per the 2026-05-18 product brainstorm). On first
 * sign-in we auto-create an org for the user with the default agent set so
 * the platform UI never has to ask "which org?" — projects live under the
 * user's implicit workspace.
 *
 * Idempotent: if the user already has any OrgMember row, this is a no-op.
 * Cached in-process via a Set so we don't run the membership check on every
 * authenticated request.
 */
import { db } from "../index.js";

const DEFAULT_AGENTS = [
  { name: "eng-bot", role: "engineer", runtime: "claude-code" },
  { name: "designer-bot", role: "designer", runtime: "claude-api" },
  { name: "support-bot", role: "tier-1 support", runtime: "cma" },
  { name: "ops-bot", role: "operations", runtime: "claude-api" },
];

// Process-local cache. Reset on server restart, which is fine — first request
// after restart pays one extra DB round-trip per user. We also clear an entry
// if creation fails, so the next request retries.
const ensuredUsers = new Set<string>();

export function clearWorkspaceCache(userId?: string): void {
  if (userId) ensuredUsers.delete(userId);
  else ensuredUsers.clear();
}

/**
 * Sanitize an email-prefix into a valid org slug:
 *   - lowercase
 *   - replace non-[a-z0-9-] with '-'
 *   - collapse repeated dashes
 *   - trim leading/trailing dashes
 *   - cap at 32 chars
 *   - fall back to "workspace" if empty
 */
function sanitizeSlug(input: string): string {
  let s = input.toLowerCase();
  s = s.replace(/[^a-z0-9-]+/g, "-");
  s = s.replace(/-+/g, "-");
  s = s.replace(/^-+|-+$/g, "");
  if (s.length > 32) s = s.slice(0, 32).replace(/-+$/g, "");
  return s || "workspace";
}

/** Pick a unique org name starting from `base`, appending -2, -3, … on collision. */
async function uniqueOrgName(base: string): Promise<string> {
  for (let i = 0; i < 50; i++) {
    const candidate = i === 0 ? base : `${base}-${i + 1}`;
    const hit = await db.org.findUnique({ where: { name: candidate }, select: { id: true } });
    if (!hit) return candidate;
  }
  // Pathological: 50 collisions on the same slug. Append a timestamp to
  // guarantee uniqueness without infinite loop.
  return `${base}-${Date.now().toString(36)}`;
}

/**
 * If the user has no OrgMember rows, create a workspace org for them with
 * the default agent set. Return the workspace org id (existing or new).
 *
 * Safe to call on every authenticated request — the first call seeds, every
 * subsequent call is a process-local set lookup.
 */
export async function ensureUserHasWorkspace(
  userId: string,
  email: string | null,
): Promise<void> {
  if (ensuredUsers.has(userId)) return;

  try {
    const existing = await db.orgMember.findFirst({
      where: { userId },
      select: { id: true },
    });
    if (existing) {
      ensuredUsers.add(userId);
      return;
    }

    const emailPrefix = (email ?? "").split("@")[0] ?? "";
    const baseSlug = sanitizeSlug(emailPrefix);
    const name = await uniqueOrgName(baseSlug);

    await db.$transaction(async (tx) => {
      const org = await tx.org.create({
        data: {
          name,
          teamSize: "Just me",
          primaryClient: "Dash",
        },
      });
      await tx.orgMember.create({
        data: { orgId: org.id, userId, role: "founder" },
      });
      await tx.agentMeta.createMany({
        data: DEFAULT_AGENTS.map((a) => ({
          orgId: org.id,
          name: a.name,
          role: a.role,
          runtime: a.runtime,
        })),
      });
    });

    ensuredUsers.add(userId);
  } catch (err) {
    // Don't cache failures — the next request will retry. We deliberately
    // swallow here so an unrelated DB hiccup doesn't break a user's session;
    // if their workspace genuinely can't be created, downstream routes that
    // expect an org membership will surface the issue.
    // eslint-disable-next-line no-console
    console.warn(`ensureUserHasWorkspace failed for user=${userId}: ${String(err)}`);
  }
}
