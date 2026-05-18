#!/usr/bin/env node
import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { CallToolRequestSchema, ListToolsRequestSchema } from "@modelcontextprotocol/sdk/types.js";
import { readFileSync, existsSync } from "node:fs";
import { join } from "node:path";
import { init } from "../verbs/init.js";
import { refresh } from "../verbs/refresh.js";
import { status } from "../verbs/status.js";
import { decisionAdd } from "../verbs/decision-add.js";
import { memoryAppend } from "../verbs/memory-append.js";

const TOOLS = [
  { name: "project_init", description: "Scaffold .crawfish/ in the repo.", inputSchema: { type: "object", properties: { repo_root: { type: "string" } }, required: ["repo_root"] } },
  { name: "project_refresh", description: "Re-derive .crawfish/*.md from sources.", inputSchema: { type: "object", properties: { repo_root: { type: "string" }, files: { type: "array", items: { type: "string" } } }, required: ["repo_root"] } },
  { name: "project_status", description: "Report which .crawfish files are stale.", inputSchema: { type: "object", properties: { repo_root: { type: "string" } }, required: ["repo_root"] } },
  { name: "project_decision_add", description: "Append an ADR entry.", inputSchema: { type: "object", properties: { repo_root: { type: "string" }, title: { type: "string" }, body: { type: "string" } }, required: ["repo_root", "title", "body"] } },
  { name: "project_memory_append", description: "Append a deduped memory entry.", inputSchema: { type: "object", properties: { repo_root: { type: "string" }, text: { type: "string" } }, required: ["repo_root", "text"] } },
  { name: "project_read", description: "Read one .crawfish/*.md file.", inputSchema: { type: "object", properties: { repo_root: { type: "string" }, file: { type: "string" } }, required: ["repo_root", "file"] } },
];

export async function dispatch(name: string, args: Record<string, unknown>): Promise<any> {
  const root = String(args.repo_root);
  switch (name) {
    case "project_init":
      return { result: init(root) };
    case "project_refresh":
      return await refresh(root, { only: args.files as string[] | undefined });
    case "project_status":
      return await status(root);
    case "project_decision_add":
      decisionAdd(root, String(args.title), String(args.body));
      return { ok: true };
    case "project_memory_append":
      memoryAppend(root, String(args.text), []);
      return { ok: true };
    case "project_read": {
      const path = join(root, ".crawfish", String(args.file));
      if (!existsSync(path)) return { error: "file not found" };
      return { content: readFileSync(path, "utf8") };
    }
    default:
      throw new Error(`unknown tool: ${name}`);
  }
}

async function main(): Promise<void> {
  const server = new Server({ name: "crawfish-projectctl", version: "0.1.0" }, { capabilities: { tools: {} } });
  server.setRequestHandler(ListToolsRequestSchema, async () => ({ tools: TOOLS }));
  server.setRequestHandler(CallToolRequestSchema, async (req) => {
    const result = await dispatch(req.params.name, req.params.arguments ?? {});
    return { content: [{ type: "text", text: JSON.stringify(result) }] };
  });
  const transport = new StdioServerTransport();
  await server.connect(transport);
}

if (import.meta.url === `file://${process.argv[1]}`) {
  main().catch((e) => { console.error(e); process.exit(1); });
}
