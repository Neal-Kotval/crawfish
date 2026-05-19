import { describe, it } from "node:test";
import assert from "node:assert/strict";
import {
  NOTION_PAGES_INBOUND_TOOL_DEFS,
  dispatchNotionPagesInbound,
  ingestNotionPage,
} from "../src/inbound/notion-pages.js";

describe("NOTION_PAGES_INBOUND_TOOL_DEFS", () => {
  it("exposes inbound_notion_ingest", () => {
    assert.equal(NOTION_PAGES_INBOUND_TOOL_DEFS.length, 1);
    assert.equal(NOTION_PAGES_INBOUND_TOOL_DEFS[0].name, "inbound_notion_ingest");
  });

  it("requires page_id", () => {
    const schema = NOTION_PAGES_INBOUND_TOOL_DEFS[0].inputSchema as Record<string, unknown>;
    assert.deepEqual((schema.required as string[]).slice(), ["page_id"]);
  });
});

describe("ingestNotionPage (stub)", () => {
  it("returns not_configured envelope", () => {
    const r = ingestNotionPage("abc-123");
    assert.equal(r.tokens_used, 0);
    assert.ok("error" in r);
    if ("error" in r) {
      assert.equal(r.error.code, "not_configured");
      assert.match(r.error.message, /Notion API token/);
    }
  });

  it("matches the github-issues envelope shape", () => {
    const r = ingestNotionPage("p");
    // Either ok+result or error — same discriminated-union shape as github.
    assert.ok("error" in r || "ok" in r);
  });
});

describe("dispatchNotionPagesInbound", () => {
  it("returns not_configured envelope on inbound_notion_ingest", async () => {
    const r = await dispatchNotionPagesInbound("inbound_notion_ingest", { page_id: "p" });
    assert.ok("error" in r);
    if ("error" in r) assert.equal(r.error.code, "not_configured");
  });

  it("returns unknown_tool on bogus name", async () => {
    const r = await dispatchNotionPagesInbound("bogus", {});
    assert.ok("error" in r);
    if ("error" in r) assert.equal(r.error.code, "unknown_tool");
  });
});
