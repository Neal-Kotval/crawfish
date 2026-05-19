/**
 * Inbound adapter — GitHub issues.
 *
 * Uses the `gh` CLI as the transport (no npm dep on octokit). The runGh
 * shim is injectable for tests; the default wires execFileSync against
 * the `gh` binary on $PATH.
 *
 * Emits a `TaskCreateInput`-shaped payload that the lens can materialise
 * into a board task. The external_ref carries the canonical pointer back
 * to the source issue so duplicate-ingest can be deduped upstream.
 */

import { execFileSync } from "node:child_process";

export interface GithubIssueIngestResult {
  title: string;
  body: string;
  labels: string[];
  external_ref: {
    kind: "github_issue";
    id: number;
    url: string;
  };
}

export interface GithubIngestOptions {
  /** Injected for tests. If undefined, uses execFileSync('gh', args). */
  runGh?: (args: string[]) => string;
}

export type GithubIngestEnvelope =
  | { tokens_used: 0; ok: true; result: GithubIssueIngestResult }
  | { tokens_used: 0; error: { code: string; message: string } };

function defaultRunGh(args: string[]): string {
  try {
    return execFileSync("gh", args, { encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] });
  } catch (err) {
    const stderr =
      err && typeof err === "object" && "stderr" in err && (err as { stderr?: unknown }).stderr
        ? String((err as { stderr: unknown }).stderr)
        : err instanceof Error
          ? err.message
          : String(err);
    throw new Error(stderr);
  }
}

/**
 * Fetch a github issue via `gh` and shape it into a TaskCreateInput.
 *
 * Errors are returned as `{ error }`-envelope rejections via the MCP tool
 * wrapper. This function itself throws on upstream failure so callers can
 * choose between throw and envelope conversion.
 */
export function ingestGithubIssue(
  owner: string,
  repo: string,
  number: number,
  opts: GithubIngestOptions = {},
): GithubIssueIngestResult {
  if (typeof owner !== "string" || owner.length === 0) {
    throw new Error("owner is required");
  }
  if (typeof repo !== "string" || repo.length === 0) {
    throw new Error("repo is required");
  }
  if (!Number.isInteger(number) || number <= 0) {
    throw new Error("number must be a positive integer");
  }

  const runGh = opts.runGh ?? defaultRunGh;
  const slug = `${owner}/${repo}`;
  const args = [
    "issue",
    "view",
    String(number),
    "--repo",
    slug,
    "--json",
    "title,body,labels,url",
  ];

  const raw = runGh(args);

  let parsed: {
    title?: string;
    body?: string;
    labels?: Array<{ name?: string } | string>;
    url?: string;
  };
  try {
    parsed = JSON.parse(raw);
  } catch (err) {
    throw new Error(
      `gh returned non-JSON output: ${err instanceof Error ? err.message : String(err)}`,
    );
  }

  const title = typeof parsed.title === "string" ? parsed.title : "";
  const body = typeof parsed.body === "string" ? parsed.body : "";
  const labelsRaw = Array.isArray(parsed.labels) ? parsed.labels : [];
  const labels = labelsRaw
    .map((l) => (typeof l === "string" ? l : typeof l?.name === "string" ? l.name : ""))
    .filter((s) => s.length > 0);
  const url = typeof parsed.url === "string" ? parsed.url : `https://github.com/${slug}/issues/${number}`;

  return {
    title,
    body,
    labels,
    external_ref: {
      kind: "github_issue",
      id: number,
      url,
    },
  };
}

// ---------- Tool definition ----------

export const GITHUB_INBOUND_TOOL_DEFS = [
  {
    name: "inbound_github_ingest",
    description:
      "Use `inbound_github_ingest` to fetch a GitHub issue via the local `gh` CLI and return a canonical TaskCreateInput payload `{ title, body, labels, external_ref: { kind: 'github_issue', id, url } }`. The host machine must have `gh` on $PATH and be authenticated; otherwise this returns `{ error: { code: 'upstream_error' } }`. The caller is expected to feed the result into `triage_normalize` before creating the task.",
    inputSchema: {
      type: "object",
      properties: {
        owner: { type: "string", description: "GitHub owner/org slug." },
        repo: { type: "string", description: "GitHub repo name." },
        number: { type: "integer", description: "Issue number (positive integer)." },
      },
      required: ["owner", "repo", "number"],
    },
  },
] as const;

// ---------- Dispatcher ----------

export async function dispatchGithubInbound(
  name: string,
  args: unknown,
  opts: GithubIngestOptions = {},
): Promise<GithubIngestEnvelope> {
  if (name !== "inbound_github_ingest") {
    return {
      tokens_used: 0,
      error: { code: "unknown_tool", message: `github-issues cannot dispatch ${name}` },
    };
  }
  const a = (args ?? {}) as { owner?: string; repo?: string; number?: number };
  if (typeof a.owner !== "string" || a.owner.length === 0) {
    return {
      tokens_used: 0,
      error: { code: "invalid_argument", message: "owner is required" },
    };
  }
  if (typeof a.repo !== "string" || a.repo.length === 0) {
    return {
      tokens_used: 0,
      error: { code: "invalid_argument", message: "repo is required" },
    };
  }
  if (!Number.isInteger(a.number) || (a.number as number) <= 0) {
    return {
      tokens_used: 0,
      error: { code: "invalid_argument", message: "number must be a positive integer" },
    };
  }

  try {
    const result = ingestGithubIssue(a.owner, a.repo, a.number as number, opts);
    return { tokens_used: 0, ok: true, result };
  } catch (err) {
    return {
      tokens_used: 0,
      error: {
        code: "upstream_error",
        message: err instanceof Error ? err.message : String(err),
      },
    };
  }
}
