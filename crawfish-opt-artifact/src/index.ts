#!/usr/bin/env node
/**
 * crawfish-opt-artifact MCP server entrypoint.
 *
 * Tools:
 *   artifact_put     — store a large payload, return {id, summary, next_action}
 *   artifact_read    — fetch a byte slice of a stored artifact
 *   artifact_grep    — pattern-match across a stored artifact
 *   artifact_stats   — current store size (count + bytes)
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
import { putArtifact, readArtifact, grepArtifact, artifactStats } from "./store.js";
import { approxTokens } from "./tokens.js";

const PutArgs = z.object({
  text: z.string(),
  mime: z.string().optional(),
  source_tool: z.string().optional(),
  summary: z.string().optional(),
});
const ReadArgs = z.object({
  id: z.string(),
  offset: z.number().int().min(0).optional(),
  length: z.number().int().positive().optional(),
});
const GrepArgs = z.object({
  id: z.string(),
  pattern: z.string(),
  n: z.number().int().positive().optional(),
});

const server = new Server(
  { name: "crawfish-opt-artifact", version: "0.1.0" },
  { capabilities: { tools: {} } },
);

server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: [
    {
      name: "artifact_put",
      description:
        "Store a large payload on disk. Returns a tiny envelope (id + heuristic summary + next-action hint) so the model doesn't carry the whole result in context.",
      inputSchema: {
        type: "object",
        properties: {
          text: { type: "string", description: "The payload to store." },
          mime: { type: "string" },
          source_tool: { type: "string", description: "Name of the upstream tool whose result this is." },
          summary: { type: "string", description: "Override the heuristic summary." },
        },
        required: ["text"],
      },
    },
    {
      name: "artifact_read",
      description: "Read a byte slice from a stored artifact.",
      inputSchema: {
        type: "object",
        properties: {
          id: { type: "string" },
          offset: { type: "number", description: "Default 0." },
          length: { type: "number", description: "Default 4096." },
        },
        required: ["id"],
      },
    },
    {
      name: "artifact_grep",
      description: "Grep a stored artifact for a pattern. Returns first N matches.",
      inputSchema: {
        type: "object",
        properties: {
          id: { type: "string" },
          pattern: { type: "string" },
          n: { type: "number", description: "Match cap. Default 20." },
        },
        required: ["id", "pattern"],
      },
    },
    {
      name: "artifact_stats",
      description: "Return current artifact store size (count + bytes).",
      inputSchema: { type: "object", properties: {} },
    },
  ],
}));

server.setRequestHandler(CallToolRequestSchema, async (req) => {
  const { name, arguments: args } = req.params;
  if (name === "artifact_put") {
    const a = PutArgs.parse(args);
    const out = putArtifact(a.text, {
      mime: a.mime,
      source_tool: a.source_tool,
      summary: a.summary,
    });
    const payload = JSON.stringify(out);
    return {
      content: [{ type: "text" as const, text: payload }],
      tokens_used: approxTokens(payload),
    };
  }
  if (name === "artifact_read") {
    const a = ReadArgs.parse(args);
    const out = readArtifact(a.id, a.offset, a.length);
    const payload = JSON.stringify(out);
    return {
      content: [{ type: "text" as const, text: payload }],
      tokens_used: approxTokens(payload),
    };
  }
  if (name === "artifact_grep") {
    const a = GrepArgs.parse(args);
    const out = grepArtifact(a.id, a.pattern, a.n);
    const payload = JSON.stringify(out);
    return {
      content: [{ type: "text" as const, text: payload }],
      tokens_used: approxTokens(payload),
    };
  }
  if (name === "artifact_stats") {
    const out = artifactStats();
    const payload = JSON.stringify(out);
    return {
      content: [{ type: "text" as const, text: payload }],
      tokens_used: approxTokens(payload),
    };
  }
  throw new Error(`unknown tool: ${name}`);
});

const transport = new StdioServerTransport();
await server.connect(transport);
