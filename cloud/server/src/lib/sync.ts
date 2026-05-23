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
import {
  listTeamIssues,
  refreshAccessToken,
  normalizeLinearState,
  LinearTokenExpired,
  type LinearIssueNode,
} from "./linear.js";

const GITHUB_MAX_PAGES = 10; // safety cap: 100/page → up to 1000 issues/sync
const LINEAR_MAX_PAGES = 40; // safety cap: 50/page → up to 2000 issues/sync

export class NothingToSync extends Error {
  constructor() {
    super("Project is not bound to a syncable provider");
  }
}

export class IntegrationNotConnected extends Error {
  constructor(provider: string) {
    super(`${provider} integration is not connected for this org`);
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

function linearLabels(node: LinearIssueNode): string[] {
  const labels = node.labels.nodes.map((l) => l.name);
  // CONTEXT decision: Linear project/cycle are carried as metadata on the
  // issue (NOT the mapping unit), folded into labels with a namespace prefix.
  if (node.project?.name) labels.push(`project:${node.project.name}`);
  if (node.cycle?.number != null) labels.push(`cycle:${node.cycle.number}`);
  return labels;
}

/**
 * Sync a Linear-bound project's issues. Reads the org's Linear Integration,
 * pages the bound team's issues, and upserts them. A GraphQL 401 triggers a
 * single token refresh + retry; the refreshed pair is persisted.
 */
export async function syncLinearProject(
  db: PrismaClient,
  project: Project,
): Promise<SyncResult> {
  if (!project.linearTeamId) throw new NothingToSync();
  const integration = await db.integration.findUnique({
    where: { orgId_provider: { orgId: project.orgId, provider: "linear" } },
  });
  if (!integration) throw new IntegrationNotConnected("linear");

  let accessToken = integration.accessToken;
  let refreshed = false;

  // Call listTeamIssues, refreshing the token once on a 401.
  const fetchPage = async (after?: string) => {
    try {
      return await listTeamIssues(accessToken, project.linearTeamId!, after);
    } catch (err) {
      if (err instanceof LinearTokenExpired && !refreshed && integration.refreshToken) {
        refreshed = true;
        const pair = await refreshAccessToken(integration.refreshToken);
        accessToken = pair.access_token;
        await db.integration.update({
          where: { id: integration.id },
          data: { accessToken: pair.access_token, refreshToken: pair.refresh_token },
        });
        return await listTeamIssues(accessToken, project.linearTeamId!, after);
      }
      throw err;
    }
  };

  let synced = 0;
  const now = new Date();
  let after: string | undefined;
  for (let page = 0; page < LINEAR_MAX_PAGES; page++) {
    const { nodes, pageInfo } = await fetchPage(after);
    for (const n of nodes) {
      const fields = {
        externalKey: n.identifier,
        title: n.title,
        body: n.description ?? null,
        state: normalizeLinearState(n.state.type),
        url: n.url,
        labels: JSON.stringify(linearLabels(n)),
        assigneeExternal: n.assignee?.displayName ?? null,
        externalUpdatedAt: n.updatedAt ? new Date(n.updatedAt) : null,
        syncedAt: now,
      };
      await db.issue.upsert({
        where: {
          projectId_provider_externalId: {
            projectId: project.id,
            provider: "linear",
            externalId: n.id,
          },
        },
        create: { projectId: project.id, provider: "linear", externalId: n.id, ...fields },
        update: fields,
      });
      synced++;
    }
    if (!pageInfo.hasNextPage || !pageInfo.endCursor) break;
    after = pageInfo.endCursor;
  }
  return { provider: "linear", synced };
}

/**
 * Dispatch to the right provider sync for a project. A Linear-team binding
 * takes precedence; otherwise a GitHub repo binding; otherwise nothing.
 */
export async function syncProjectIssues(
  db: PrismaClient,
  project: Project,
  userId: string,
): Promise<SyncResult> {
  if (project.linearTeamId) return syncLinearProject(db, project);
  if (project.githubRepo) return syncGithubProject(db, project, userId);
  throw new NothingToSync();
}
