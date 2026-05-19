/**
 * Inbound adapter — Notion form submission (STUB).
 *
 * Drop-in placeholder for the Notion form-webhook path. Real implementation
 * needs the Notion integration token and the form's database id. Spec TBD —
 * see `docs/specs/inbound-contract.md`.
 */

import type { GithubIssueIngestResult } from "./github-issues.js";

export interface NotionFormIngestOptions {
  [k: string]: unknown;
}

export type NotionFormIngestEnvelope =
  | { tokens_used: 0; ok: true; result: GithubIssueIngestResult }
  | { tokens_used: 0; error: { code: string; message: string } };

export function ingestNotionForm(
  _pageId: string,
  _opts: NotionFormIngestOptions = {},
): NotionFormIngestEnvelope {
  return {
    tokens_used: 0,
    error: {
      code: "not_configured",
      message:
        "notion-form adapter requires credentials; see docs/specs/inbound-contract.md (TBD)",
    },
  };
}

export const NOTION_FORM_INBOUND_TOOL_DEFS = [
  {
    name: "inbound_notion_form_ingest",
    description:
      "STUB. Use `inbound_notion_form_ingest` to ingest a Notion form submission. Currently returns `{ error: { code: 'not_configured' } }` until the integration token and database id are wired — see docs/specs/inbound-contract.md (TBD).",
    inputSchema: {
      type: "object",
      properties: {
        page_id: { type: "string", description: "Notion page id of the form submission row." },
      },
      required: ["page_id"],
    },
  },
] as const;

export async function dispatchNotionFormInbound(
  name: string,
  _args: unknown,
): Promise<NotionFormIngestEnvelope> {
  if (name !== "inbound_notion_form_ingest") {
    return {
      tokens_used: 0,
      error: { code: "unknown_tool", message: `notion-form cannot dispatch ${name}` },
    };
  }
  return ingestNotionForm("");
}
