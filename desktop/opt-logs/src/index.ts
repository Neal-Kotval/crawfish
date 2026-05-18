#!/usr/bin/env node
/**
 * crawfish-opt-logs MCP server entrypoint.
 *
 * Tools:
 *   logs_summarize  — turn an arbitrary log dump into errors + warnings +
 *                     head/tail of the info stream. Beats blind cat 10–100×
 *                     on typical npm / cargo / k8s output.
 *   logs_grep       — pattern match with context lines + cap. Faster +
 *                     thinner than asking the agent to grep itself.
 *   logs_tail_smart — last N lines, extended back so a stack trace isn't
 *                     truncated mid-frame.
 *
 * Every response includes `tokens_used` per the crawfish optimizer
 * contract (v1.0).
 */

import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";
import { z } from "zod";
import { summarize, grep, tailSmart } from "./logs.js";
import { approxTokens } from "./tokens.js";

const SummarizeArgs = z.object({
  text: z.string(),
  intent: z.string().optional(),
  info_window: z.number().int().positive().optional(),
  max_errors: z.number().int().positive().optional(),
});
const GrepArgs = z.object({
  text: z.string(),
  pattern: z.string(),
  n: z.number().int().positive().optional(),
  context: z.number().int().min(0).optional(),
});
const TailArgs = z.object({
  text: z.string(),
  n: z.number().int().positive().optional(),
});

const server = new Server(
  { name: "crawfish-opt-logs", version: "0.1.0" },
  { capabilities: { tools: {} } },
);

server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: [
    {
      name: "logs_summarize",
      description:
        "Summarize a log dump. Returns errors with context, warnings, and head/tail of the info stream. Use when an agent would otherwise cat or read the whole file.",
      inputSchema: {
        type: "object",
        properties: {
          text: { type: "string", description: "The full log text." },
          intent: { type: "string", description: "Optional one-line intent — currently advisory." },
          info_window: { type: "number", description: "Head/tail lines kept from info stream. Default 5." },
          max_errors: { type: "number", description: "Cap on error blocks. Default 20." },
        },
        required: ["text"],
      },
    },
    {
      name: "logs_grep",
      description:
        "Grep a log for a regex pattern. Returns first N matches + context. Cheaper than re-shelling.",
      inputSchema: {
        type: "object",
        properties: {
          text: { type: "string" },
          pattern: { type: "string" },
          n: { type: "number", description: "Match cap. Default 20." },
          context: { type: "number", description: "Context lines around each match. Default 0." },
        },
        required: ["text", "pattern"],
      },
    },
    {
      name: "logs_tail_smart",
      description:
        "Tail last N lines, extending back so stack traces aren't truncated mid-frame.",
      inputSchema: {
        type: "object",
        properties: {
          text: { type: "string" },
          n: { type: "number", description: "Default 50." },
        },
        required: ["text"],
      },
    },
  ],
}));

server.setRequestHandler(CallToolRequestSchema, async (req) => {
  const { name, arguments: args } = req.params;
  if (name === "logs_summarize") {
    const a = SummarizeArgs.parse(args);
    const out = summarize(a.text, {
      info_window: a.info_window,
      max_errors: a.max_errors,
    });
    const payload = JSON.stringify(out, null, 2);
    return {
      content: [{ type: "text" as const, text: payload }],
      tokens_used: approxTokens(payload),
    };
  }
  if (name === "logs_grep") {
    const a = GrepArgs.parse(args);
    const out = grep(a.text, a.pattern, { n: a.n, context: a.context });
    const payload = JSON.stringify(out, null, 2);
    return {
      content: [{ type: "text" as const, text: payload }],
      tokens_used: approxTokens(payload),
    };
  }
  if (name === "logs_tail_smart") {
    const a = TailArgs.parse(args);
    const out = tailSmart(a.text, a.n);
    const payload = JSON.stringify(out, null, 2);
    return {
      content: [{ type: "text" as const, text: payload }],
      tokens_used: approxTokens(payload),
    };
  }
  throw new Error(`unknown tool: ${name}`);
});

const transport = new StdioServerTransport();
await server.connect(transport);
