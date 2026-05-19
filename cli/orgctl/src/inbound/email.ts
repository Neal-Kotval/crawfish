/**
 * Inbound adapter — Email (STUB).
 *
 * Drop-in placeholder for IMAP / Postmark / SES ingestion. The real
 * implementation will need credentials and a mailbox spec, neither of
 * which are wired yet. Spec TBD — see `docs/specs/inbound-contract.md`.
 *
 * The function signature mirrors `ingestGithubIssue` so the eventual
 * implementation can replace this without touching callers.
 */

import type { GithubIssueIngestResult } from "./github-issues.js";

export interface EmailIngestOptions {
  // Future: imapConfig, mailbox, etc.
  [k: string]: unknown;
}

export type EmailIngestEnvelope =
  | { tokens_used: 0; ok: true; result: GithubIssueIngestResult }
  | { tokens_used: 0; error: { code: string; message: string } };

export function ingestEmail(
  _messageId: string,
  _opts: EmailIngestOptions = {},
): EmailIngestEnvelope {
  return {
    tokens_used: 0,
    error: {
      code: "not_configured",
      message: "email adapter requires credentials; see docs/specs/inbound-contract.md (TBD)",
    },
  };
}

export const EMAIL_INBOUND_TOOL_DEFS = [
  {
    name: "inbound_email_ingest",
    description:
      "STUB. Use `inbound_email_ingest` to ingest a message from an attached mailbox. Currently returns `{ error: { code: 'not_configured' } }` until credentials and mailbox spec are wired — see docs/specs/inbound-contract.md (TBD).",
    inputSchema: {
      type: "object",
      properties: {
        message_id: { type: "string", description: "RFC-5322 Message-ID of the email." },
      },
      required: ["message_id"],
    },
  },
] as const;

export async function dispatchEmailInbound(
  name: string,
  _args: unknown,
): Promise<EmailIngestEnvelope> {
  if (name !== "inbound_email_ingest") {
    return {
      tokens_used: 0,
      error: { code: "unknown_tool", message: `email cannot dispatch ${name}` },
    };
  }
  return ingestEmail("");
}
