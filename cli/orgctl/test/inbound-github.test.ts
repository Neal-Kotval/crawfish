import { describe, it } from "node:test";
import assert from "node:assert/strict";
import {
  GITHUB_INBOUND_TOOL_DEFS,
  dispatchGithubInbound,
  ingestGithubIssue,
} from "../src/inbound/github-issues.js";
import { ingestEmail, dispatchEmailInbound } from "../src/inbound/email.js";
import { ingestNotionForm, dispatchNotionFormInbound } from "../src/inbound/notion-form.js";
import {
  ingestSlackHandoff,
  dispatchSlackHandoffInbound,
} from "../src/inbound/slack-handoff.js";

describe("GITHUB_INBOUND_TOOL_DEFS", () => {
  it("exposes inbound_github_ingest", () => {
    assert.equal(GITHUB_INBOUND_TOOL_DEFS.length, 1);
    assert.equal(GITHUB_INBOUND_TOOL_DEFS[0].name, "inbound_github_ingest");
  });

  it("requires owner, repo, number", () => {
    const schema = GITHUB_INBOUND_TOOL_DEFS[0].inputSchema as Record<string, unknown>;
    assert.deepEqual(
      (schema.required as string[]).slice().sort(),
      ["number", "owner", "repo"],
    );
  });
});

describe("ingestGithubIssue", () => {
  it("invokes gh with correct args and parses JSON", () => {
    let calledArgs: string[] | null = null;
    const runGh = (args: string[]) => {
      calledArgs = args;
      return JSON.stringify({
        title: "It crashes",
        body: "stack trace ...",
        labels: [{ name: "bug" }, { name: "p0" }],
        url: "https://github.com/o/r/issues/42",
      });
    };
    const res = ingestGithubIssue("o", "r", 42, { runGh });
    assert.deepEqual(calledArgs, [
      "issue",
      "view",
      "42",
      "--repo",
      "o/r",
      "--json",
      "title,body,labels,url",
    ]);
    assert.equal(res.title, "It crashes");
    assert.equal(res.body, "stack trace ...");
    assert.deepEqual(res.labels, ["bug", "p0"]);
    assert.deepEqual(res.external_ref, {
      kind: "github_issue",
      id: 42,
      url: "https://github.com/o/r/issues/42",
    });
  });

  it("tolerates labels-as-strings", () => {
    const runGh = () =>
      JSON.stringify({ title: "t", body: "b", labels: ["a", "b"], url: "u" });
    const res = ingestGithubIssue("o", "r", 1, { runGh });
    assert.deepEqual(res.labels, ["a", "b"]);
  });

  it("falls back to constructed URL when missing", () => {
    const runGh = () => JSON.stringify({ title: "t", body: "b", labels: [] });
    const res = ingestGithubIssue("o", "r", 7, { runGh });
    assert.equal(res.external_ref.url, "https://github.com/o/r/issues/7");
  });

  it("throws on non-JSON output", () => {
    const runGh = () => "not json {{";
    assert.throws(() => ingestGithubIssue("o", "r", 1, { runGh }), /non-JSON/);
  });

  it("throws on empty owner / repo / bad number", () => {
    assert.throws(() => ingestGithubIssue("", "r", 1, { runGh: () => "{}" }));
    assert.throws(() => ingestGithubIssue("o", "", 1, { runGh: () => "{}" }));
    assert.throws(() => ingestGithubIssue("o", "r", 0, { runGh: () => "{}" }));
    assert.throws(() => ingestGithubIssue("o", "r", -1, { runGh: () => "{}" }));
  });

  it("propagates gh errors", () => {
    const runGh = () => {
      throw new Error("gh: not found");
    };
    assert.throws(() => ingestGithubIssue("o", "r", 1, { runGh }), /gh: not found/);
  });
});

describe("dispatchGithubInbound", () => {
  it("returns ok envelope on success", async () => {
    const runGh = () =>
      JSON.stringify({ title: "t", body: "b", labels: [], url: "u" });
    const res = await dispatchGithubInbound(
      "inbound_github_ingest",
      { owner: "o", repo: "r", number: 5 },
      { runGh },
    );
    assert.ok("ok" in res && res.ok);
    if ("ok" in res) {
      assert.equal(res.result.title, "t");
      assert.equal(res.tokens_used, 0);
    }
  });

  it("wraps gh errors as upstream_error", async () => {
    const runGh = () => {
      throw new Error("gh: auth required");
    };
    const res = await dispatchGithubInbound(
      "inbound_github_ingest",
      { owner: "o", repo: "r", number: 1 },
      { runGh },
    );
    assert.ok("error" in res);
    if ("error" in res) {
      assert.equal(res.error.code, "upstream_error");
      assert.match(res.error.message, /auth required/);
    }
  });

  it("returns invalid_argument on missing owner", async () => {
    const res = await dispatchGithubInbound("inbound_github_ingest", {
      repo: "r",
      number: 1,
    });
    assert.ok("error" in res);
    if ("error" in res) assert.equal(res.error.code, "invalid_argument");
  });

  it("returns invalid_argument on non-integer number", async () => {
    const res = await dispatchGithubInbound("inbound_github_ingest", {
      owner: "o",
      repo: "r",
      number: 1.5,
    });
    assert.ok("error" in res);
  });

  it("returns unknown_tool for other names", async () => {
    const res = await dispatchGithubInbound("nope", { owner: "o", repo: "r", number: 1 });
    assert.ok("error" in res);
    if ("error" in res) assert.equal(res.error.code, "unknown_tool");
  });
});

describe("inbound stubs", () => {
  it("email returns not_configured", () => {
    const r = ingestEmail("mid");
    assert.ok("error" in r);
    if ("error" in r) assert.equal(r.error.code, "not_configured");
  });

  it("notion-form returns not_configured", () => {
    const r = ingestNotionForm("page");
    assert.ok("error" in r);
    if ("error" in r) assert.equal(r.error.code, "not_configured");
  });

  it("slack-handoff returns not_configured", () => {
    const r = ingestSlackHandoff("c", "ts");
    assert.ok("error" in r);
    if ("error" in r) assert.equal(r.error.code, "not_configured");
  });

  it("email dispatcher returns not_configured envelope", async () => {
    const r = await dispatchEmailInbound("inbound_email_ingest", {});
    assert.ok("error" in r);
    if ("error" in r) assert.equal(r.error.code, "not_configured");
  });

  it("notion-form dispatcher returns not_configured envelope", async () => {
    const r = await dispatchNotionFormInbound("inbound_notion_form_ingest", {});
    assert.ok("error" in r);
  });

  it("slack-handoff dispatcher returns not_configured envelope", async () => {
    const r = await dispatchSlackHandoffInbound("inbound_slack_handoff_ingest", {});
    assert.ok("error" in r);
  });

  it("stub dispatchers return unknown_tool on wrong name", async () => {
    const r1 = await dispatchEmailInbound("bogus", {});
    const r2 = await dispatchNotionFormInbound("bogus", {});
    const r3 = await dispatchSlackHandoffInbound("bogus", {});
    for (const r of [r1, r2, r3]) {
      assert.ok("error" in r);
      if ("error" in r) assert.equal(r.error.code, "unknown_tool");
    }
  });
});
