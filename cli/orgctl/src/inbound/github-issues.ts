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

// ---------- Mirror (outbound — round-trip) ----------

export interface GithubExternalRef {
  kind: "github_issue";
  id: number;
  url: string;
}

export interface MirrorTransition {
  from?: string;
  to: string;
}

export interface MirrorOptions extends GithubIngestOptions {
  /** Optional assignee name surfaced in the "picked up" comment body. */
  assignee?: string;
  /** Optional crawfish task id surfaced in the close comment. */
  taskId?: string;
}

export type MirrorResult =
  | { ok: true; action: "closed" | "commented" | "reopened" | "noop"; gh_output: string }
  | { error: { code: string; message: string } };

export type MirrorEnvelope =
  | { tokens_used: 0; ok: true; action: "closed" | "commented" | "reopened" | "noop"; gh_output: string }
  | { tokens_used: 0; error: { code: string; message: string } };

/**
 * Parse `owner/repo` from an issue URL like
 *   https://github.com/<owner>/<repo>/issues/<n>
 * Returns null if the URL is not in that shape.
 */
function parseRepoFromUrl(url: string): string | null {
  const m = /^https?:\/\/github\.com\/([^/]+)\/([^/]+)\/issues\/\d+/.exec(url);
  if (!m) return null;
  return `${m[1]}/${m[2]}`;
}

/**
 * Mirror a Crawfish task status transition back to its source GitHub issue.
 *
 * Crawfish is authoritative — this is best-effort one-way replication.
 * - to === "done": close with a comment referencing the task id.
 * - to === "doing" (from "todo" | "triage"): post a "picked up" comment. Do NOT reopen.
 * - from === "done" && to !== "done": reopen the issue.
 * - anything else: noop.
 */
export function mirrorStatusToGithub(
  externalRef: { kind: string; id: number; url: string },
  transition: MirrorTransition,
  opts: MirrorOptions = {},
): MirrorResult {
  if (externalRef == null || typeof externalRef !== "object") {
    return { error: { code: "invalid_external_ref", message: "external_ref is required" } };
  }
  if (externalRef.kind !== "github_issue") {
    return {
      error: {
        code: "invalid_external_ref",
        message: `expected github_issue, got ${String(externalRef.kind)}`,
      },
    };
  }
  if (!Number.isInteger(externalRef.id) || externalRef.id <= 0) {
    return {
      error: { code: "invalid_external_ref", message: "external_ref.id must be a positive integer" },
    };
  }
  if (typeof externalRef.url !== "string" || externalRef.url.length === 0) {
    return { error: { code: "invalid_external_ref", message: "external_ref.url is required" } };
  }
  const slug = parseRepoFromUrl(externalRef.url);
  if (slug == null) {
    return {
      error: {
        code: "invalid_external_ref",
        message: `external_ref.url is not a GitHub issue URL: ${externalRef.url}`,
      },
    };
  }
  if (transition == null || typeof transition !== "object" || typeof transition.to !== "string") {
    return { error: { code: "invalid_argument", message: "transition.to is required" } };
  }

  const runGh = opts.runGh ?? defaultRunGh;
  const number = String(externalRef.id);
  const taskRef = opts.taskId ? ` task ${opts.taskId}` : " task";
  const assignee = opts.assignee && opts.assignee.length > 0 ? opts.assignee : "an agent";

  try {
    if (transition.to === "done") {
      const out = runGh([
        "issue",
        "close",
        number,
        "--repo",
        slug,
        "--comment",
        `Closed via Crawfish${taskRef}`,
      ]);
      return { ok: true, action: "closed", gh_output: out };
    }
    if (transition.to === "doing" && (transition.from === "todo" || transition.from === "triage")) {
      const out = runGh([
        "issue",
        "comment",
        number,
        "--repo",
        slug,
        "--body",
        `Crawfish${taskRef} picked up by ${assignee}`,
      ]);
      return { ok: true, action: "commented", gh_output: out };
    }
    if (transition.from === "done" && transition.to !== "done") {
      const out = runGh(["issue", "reopen", number, "--repo", slug]);
      return { ok: true, action: "reopened", gh_output: out };
    }
    return { ok: true, action: "noop", gh_output: "" };
  } catch (err) {
    return {
      error: {
        code: "upstream_error",
        message: err instanceof Error ? err.message : String(err),
      },
    };
  }
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
  {
    name: "inbound_github_mirror",
    description:
      "Use `inbound_github_mirror` to round-trip a Crawfish task status change back to its source GitHub issue. Crawfish is authoritative; this is best-effort one-way replication. On `to: 'done'` the issue is closed with a comment. On `to: 'doing'` from `todo`/`triage` a 'picked up' comment is posted (no reopen). On `from: 'done'` to anything else the issue is reopened. Other transitions are no-ops. Returns `{ error: { code: 'upstream_error' } }` if `gh` fails.",
    inputSchema: {
      type: "object",
      properties: {
        external_ref: {
          type: "object",
          description: "External reference carried on the task.",
          properties: {
            kind: { type: "string", enum: ["github_issue"] },
            id: { type: "integer", description: "Issue number." },
            url: { type: "string", description: "Canonical issue URL." },
          },
          required: ["kind", "id", "url"],
        },
        transition: {
          type: "object",
          properties: {
            from: { type: "string", description: "Prior status (optional)." },
            to: { type: "string", description: "New status." },
          },
          required: ["to"],
        },
        assignee: { type: "string", description: "Optional agent name for the 'picked up' comment." },
        task_id: { type: "string", description: "Optional Crawfish task id for the close comment." },
      },
      required: ["external_ref", "transition"],
    },
  },
] as const;

// ---------- Dispatcher ----------

export async function dispatchGithubInbound(
  name: string,
  args: unknown,
  opts: GithubIngestOptions = {},
): Promise<GithubIngestEnvelope | MirrorEnvelope> {
  if (name === "inbound_github_mirror") {
    const a = (args ?? {}) as {
      external_ref?: { kind?: string; id?: number; url?: string };
      transition?: { from?: string; to?: string };
      assignee?: string;
      task_id?: string;
    };
    if (a.external_ref == null || typeof a.external_ref !== "object") {
      return {
        tokens_used: 0,
        error: { code: "invalid_argument", message: "external_ref is required" },
      };
    }
    if (a.transition == null || typeof a.transition.to !== "string") {
      return {
        tokens_used: 0,
        error: { code: "invalid_argument", message: "transition.to is required" },
      };
    }
    const ext = a.external_ref;
    const res = mirrorStatusToGithub(
      {
        kind: typeof ext.kind === "string" ? ext.kind : "",
        id: typeof ext.id === "number" ? ext.id : -1,
        url: typeof ext.url === "string" ? ext.url : "",
      },
      { from: a.transition.from, to: a.transition.to },
      { ...opts, assignee: a.assignee, taskId: a.task_id },
    );
    if ("error" in res) {
      return { tokens_used: 0, error: res.error };
    }
    return { tokens_used: 0, ok: true, action: res.action, gh_output: res.gh_output };
  }

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
