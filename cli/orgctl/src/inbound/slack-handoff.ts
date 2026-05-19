/**
 * Inbound adapter — Slack handoff (STUB).
 *
 * Drop-in placeholder for a Slack-based handoff flow (e.g. an emoji
 * reaction or slash command turns a thread into a task). Real
 * implementation needs the Slack bot token and the handoff trigger spec.
 * Spec TBD — see `docs/specs/inbound-contract.md`.
 */

import type { GithubIssueIngestResult } from "./github-issues.js";

export interface SlackHandoffIngestOptions {
  [k: string]: unknown;
}

export type SlackHandoffIngestEnvelope =
  | { tokens_used: 0; ok: true; result: GithubIssueIngestResult }
  | { tokens_used: 0; error: { code: string; message: string } };

export function ingestSlackHandoff(
  _channelId: string,
  _threadTs: string,
  _opts: SlackHandoffIngestOptions = {},
): SlackHandoffIngestEnvelope {
  return {
    tokens_used: 0,
    error: {
      code: "not_configured",
      message:
        "slack-handoff adapter requires credentials; see docs/specs/inbound-contract.md (TBD)",
    },
  };
}

export const SLACK_HANDOFF_INBOUND_TOOL_DEFS = [
  {
    name: "inbound_slack_handoff_ingest",
    description:
      "STUB. Use `inbound_slack_handoff_ingest` to convert a Slack thread into a task. Currently returns `{ error: { code: 'not_configured' } }` until the bot token and trigger spec are wired — see docs/specs/inbound-contract.md (TBD).",
    inputSchema: {
      type: "object",
      properties: {
        channel_id: { type: "string", description: "Slack channel id." },
        thread_ts: { type: "string", description: "Thread timestamp (the parent message ts)." },
      },
      required: ["channel_id", "thread_ts"],
    },
  },
] as const;

export async function dispatchSlackHandoffInbound(
  name: string,
  _args: unknown,
): Promise<SlackHandoffIngestEnvelope> {
  if (name !== "inbound_slack_handoff_ingest") {
    return {
      tokens_used: 0,
      error: { code: "unknown_tool", message: `slack-handoff cannot dispatch ${name}` },
    };
  }
  return ingestSlackHandoff("", "");
}
