/**
 * Inbound adapter — Notion pages (STUB).
 *
 * Distinct from `notion-form.ts` (which targets a Notion *form* submission
 * webhook). This adapter is the eventual home for ingesting arbitrary
 * Notion *pages* (databases entries, freeform pages, etc.) as Crawfish
 * tasks. The real implementation needs a Notion API token + a workspace
 * mapping; both TBD.
 *
 * The shape mirrors `ingestGithubIssue` so the eventual implementation can
 * drop in without touching callers.
 */
import type { GithubIssueIngestResult } from "./github-issues.js";

export interface NotionPageIngestResult {
  title: string;
  body: string;
  labels: string[];
  external_ref: {
    kind: "notion_page";
    id: string;
    url: string;
  };
}

export interface NotionPageIngestOptions {
  // Future: notionToken, workspace, etc.
  [k: string]: unknown;
}

export type NotionPageIngestEnvelope =
  | { tokens_used: 0; ok: true; result: NotionPageIngestResult }
  | { tokens_used: 0; error: { code: string; message: string } };

// Re-export the shared canonical shape for callers that want a union type
// across all inbound adapters once Notion is wired.
export type AnyIngestResult = GithubIssueIngestResult | NotionPageIngestResult;

export function ingestNotionPage(
  _pageId: string,
  _opts: NotionPageIngestOptions = {},
): NotionPageIngestEnvelope {
  return {
    tokens_used: 0,
    error: {
      code: "not_configured",
      message:
        "Notion ingestion requires Notion API token; see docs/specs/inbound-contract.md (TBD)",
    },
  };
}

export const NOTION_PAGES_INBOUND_TOOL_DEFS = [
  {
    name: "inbound_notion_ingest",
    description:
      "STUB. Use `inbound_notion_ingest` to ingest a Notion *page* (distinct from `inbound_notion_form_ingest`, which handles form-submission webhooks). Currently returns `{ error: { code: 'not_configured' } }` until a Notion API token and workspace mapping are wired — see docs/specs/inbound-contract.md (TBD).",
    inputSchema: {
      type: "object",
      properties: {
        page_id: { type: "string", description: "Notion page id (UUID, dashed or undashed)." },
      },
      required: ["page_id"],
    },
  },
] as const;

export async function dispatchNotionPagesInbound(
  name: string,
  _args: unknown,
): Promise<NotionPageIngestEnvelope> {
  if (name !== "inbound_notion_ingest") {
    return {
      tokens_used: 0,
      error: { code: "unknown_tool", message: `notion-pages cannot dispatch ${name}` },
    };
  }
  return ingestNotionPage("");
}
