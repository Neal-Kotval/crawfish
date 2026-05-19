import { describe, it } from "node:test";
import assert from "node:assert/strict";
import {
  TRIAGE_TOOL_DEFS,
  dispatchTriage,
  normalizeInbound,
} from "../src/triage.js";

describe("TRIAGE_TOOL_DEFS", () => {
  it("exposes triage_normalize", () => {
    assert.equal(TRIAGE_TOOL_DEFS.length, 1);
    assert.equal(TRIAGE_TOOL_DEFS[0].name, "triage_normalize");
  });

  it("description is substantial", () => {
    assert.ok((TRIAGE_TOOL_DEFS[0].description?.length ?? 0) > 80);
  });

  it("requires title", () => {
    const schema = TRIAGE_TOOL_DEFS[0].inputSchema as Record<string, unknown>;
    assert.deepEqual(schema.required, ["title"]);
  });
});

describe("normalizeInbound heuristics", () => {
  it("bumps to high+bug on crash keyword", () => {
    const out = normalizeInbound({ title: "x", body: "the app crashes on startup" });
    assert.equal(out.priority, "high");
    assert.deepEqual(out.labels, ["bug"]);
    assert.equal(out.triage_confidence, 0.8);
  });

  it("bumps to high+bug on broken keyword", () => {
    const out = normalizeInbound({ title: "x", body: "feature is broken in prod" });
    assert.equal(out.priority, "high");
    assert.deepEqual(out.labels, ["bug"]);
  });

  it("bumps to high+bug on regression keyword", () => {
    const out = normalizeInbound({ title: "x", body: "regression vs last release" });
    assert.equal(out.priority, "high");
    assert.deepEqual(out.labels, ["bug"]);
  });

  it("low+feature on feature keyword", () => {
    const out = normalizeInbound({ title: "x", body: "feature request: dark mode" });
    assert.equal(out.priority, "low");
    assert.deepEqual(out.labels, ["feature"]);
    assert.equal(out.triage_confidence, 0.8);
  });

  it("low+feature on 'would be nice'", () => {
    const out = normalizeInbound({ title: "x", body: "would be nice to have CSV export" });
    assert.equal(out.priority, "low");
    assert.deepEqual(out.labels, ["feature"]);
  });

  it("defaults to med+task with conf 0.5 when no keyword fires", () => {
    const out = normalizeInbound({ title: "x", body: "please look at this" });
    assert.equal(out.priority, "med");
    assert.deepEqual(out.labels, ["task"]);
    assert.equal(out.triage_confidence, 0.5);
  });

  it("confidence 0.3 when body is empty", () => {
    const out = normalizeInbound({ title: "x" });
    assert.equal(out.triage_confidence, 0.3);
    assert.equal(out.priority, "med");
  });

  it("returns empty criteria", () => {
    const out = normalizeInbound({ title: "x", body: "anything" });
    assert.deepEqual(out.criteria, []);
  });

  it("matches keyword in title as well as body", () => {
    const out = normalizeInbound({ title: "Crash on login", body: "" });
    assert.equal(out.priority, "high");
    // body empty, but keyword in title — conf should reflect empty body
    assert.equal(out.triage_confidence, 0.3);
  });

  it("trims title", () => {
    const out = normalizeInbound({ title: "   hello   " });
    assert.equal(out.title, "hello");
  });
});

describe("dispatchTriage", () => {
  it("returns ok envelope on valid input", async () => {
    const res = await dispatchTriage("triage_normalize", { title: "hi", body: "crash" });
    assert.equal(res.tokens_used, 0);
    assert.ok("ok" in res && res.ok);
    if ("ok" in res) {
      assert.equal(res.result.priority, "high");
    }
  });

  it("returns invalid_argument when title missing", async () => {
    const res = await dispatchTriage("triage_normalize", { body: "x" });
    assert.ok("error" in res);
    if ("error" in res) {
      assert.equal(res.error.code, "invalid_argument");
    }
  });

  it("returns invalid_argument when title is whitespace", async () => {
    const res = await dispatchTriage("triage_normalize", { title: "   " });
    assert.ok("error" in res);
  });

  it("returns unknown_tool for other names", async () => {
    const res = await dispatchTriage("bogus", { title: "x" });
    assert.ok("error" in res);
    if ("error" in res) {
      assert.equal(res.error.code, "unknown_tool");
    }
  });

  it("returns invalid_argument when args is not an object", async () => {
    const res = await dispatchTriage("triage_normalize", null);
    assert.ok("error" in res);
  });
});
