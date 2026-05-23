/**
 * Issue sync engine.
 *
 * Pulls issues from a project's connected provider and upserts them into the
 * Issue table, keyed on the (projectId, provider, externalId) compound unique
 * so re-syncing is idempotent — a second sync updates rows in place rather
 * than inserting duplicates.
 *
 * GitHub ships here (Wave 2); Linear is wired in a later wave behind the
 * Integration OAuth store. Provider selection is by what the project is bound
 * to: a `githubRepo` → GitHub; a `linearTeamId` → Linear (not yet implemented).
 */
import type { PrismaClient, Project } from "@prisma/client";
import { getGithubToken, listRepoIssues, type GithubIssue } from "./github.js";

const GITHUB_MAX_PAGES = 10; // safety cap: 100/page → up to 1000 issues/sync

export class NothingToSync extends Error {
  constructor() {
    super("Project is not bound to a syncable provider");
  }
}

export interface SyncResult {
  provider: "github" | "linear";
  synced: number;
}

function labelNames(labels: GithubIssue["labels"]): string[] {
  return labels
    .map((l) => (typeof l === "string" ? l : (l.name ?? "")))
    .filter((n) => n.length > 0);
}

/**
 * Sync one GitHub-bound project's issues into the Issue table. Paginates until
 * a short page is returned (or the safety cap). Returns the number of issues
 * upserted this run.
 */
export async function syncGithubProject(
  db: PrismaClient,
  project: Project,
  userId: string,
): Promise<SyncResult> {
  if (!project.githubRepo) throw new NothingToSync();
  const token = await getGithubToken(userId);

  let synced = 0;
  const now = new Date();
  for (let page = 1; page <= GITHUB_MAX_PAGES; page++) {
    const issues = await listRepoIssues(token, project.githubRepo, page);
    for (const i of issues) {
      await db.issue.upsert({
        where: {
          projectId_provider_externalId: {
            projectId: project.id,
            provider: "github",
            externalId: i.node_id,
          },
        },
        create: {
          projectId: project.id,
          provider: "github",
          externalId: i.node_id,
          externalKey: `#${i.number}`,
          number: i.number,
          title: i.title,
          body: i.body ?? null,
          state: i.state === "closed" ? "closed" : "open",
          url: i.html_url,
          labels: JSON.stringify(labelNames(i.labels)),
          assigneeExternal: i.assignee?.login ?? null,
          externalUpdatedAt: i.updated_at ? new Date(i.updated_at) : null,
          syncedAt: now,
        },
        update: {
          externalKey: `#${i.number}`,
          number: i.number,
          title: i.title,
          body: i.body ?? null,
          state: i.state === "closed" ? "closed" : "open",
          url: i.html_url,
          labels: JSON.stringify(labelNames(i.labels)),
          assigneeExternal: i.assignee?.login ?? null,
          externalUpdatedAt: i.updated_at ? new Date(i.updated_at) : null,
          syncedAt: now,
        },
      });
      synced++;
    }
    if (issues.length < 100) break;
  }
  return { provider: "github", synced };
}

/**
 * Dispatch to the right provider sync for a project. GitHub is implemented;
 * Linear throws NothingToSync until its wave lands.
 */
export async function syncProjectIssues(
  db: PrismaClient,
  project: Project,
  userId: string,
): Promise<SyncResult> {
  if (project.githubRepo) return syncGithubProject(db, project, userId);
  throw new NothingToSync();
}
