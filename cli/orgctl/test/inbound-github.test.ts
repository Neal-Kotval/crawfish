import { describe, it } from "node:test";
import assert from "node:assert/strict";
import {
  GITHUB_INBOUND_TOOL_DEFS,
  dispatchGithubInbound,
  ingestGithubIssue,
  mirrorStatusToGithub,
} from "../src/inbound/github-issues.js";
import { ingestEmail, dispatchEmailInbound } from "../src/inbound/email.js";
import { ingestNotionForm, dispatchNotionFormInbound } from "../src/inbound/notion-form.js";
import {
  ingestSlackHandoff,
  dispatchSlackHandoffInbound,
} from "../src/inbound/slack-handoff.js";

describe("GITHUB_INBOUND_TOOL_DEFS", () => {
  it("exposes inbound_github_ingest and inbound_github_mirror", () => {
    assert.equal(GITHUB_INBOUND_TOOL_DEFS.length, 2);
    const names = GITHUB_INBOUND_TOOL_DEFS.map((d) => d.name).slice().sort();
    assert.deepEqual(names, ["inbound_github_ingest", "inbound_github_mirror"]);
  });

  it("ingest requires owner, repo, number", () => {
    const def = GITHUB_INBOUND_TOOL_DEFS.find((d) => d.name === "inbound_github_ingest");
    assert.ok(def);
    const schema = def!.inputSchema as Record<string, unknown>;
    assert.deepEqual(
      (schema.required as string[]).slice().sort(),
      ["number", "owner", "repo"],
    );
  });

  it("mirror requires external_ref and transition", () => {
    const def = GITHUB_INBOUND_TOOL_DEFS.find((d) => d.name === "inbound_github_mirror");
    assert.ok(def);
    const schema = def!.inputSchema as Record<string, unknown>;
    assert.deepEqual(
      (schema.required as string[]).slice().sort(),
      ["external_ref", "transition"],
    );
  });
});

describe("mirrorStatusToGithub", () => {
  const ref = {
    kind: "github_issue" as const,
    id: 42,
    url: "https://github.com/o/r/issues/42",
  };

  it("closes the issue on transition to done", () => {
    const calls: string[][] = [];
    const runGh = (args: string[]) => {
      calls.push(args);
      return "";
    };
    const res = mirrorStatusToGithub(
      ref,
      { from: "doing", to: "done" },
      { runGh, taskId: "T-123" },
    );
    assert.ok("ok" in res && res.ok);
    if ("ok" in res) assert.equal(res.action, "closed");
    assert.equal(calls.length, 1);
    const args = calls[0];
    assert.equal(args[0], "issue");
    assert.equal(args[1], "close");
    assert.equal(args[2], "42");
    assert.deepEqual(args.slice(3, 5), ["--repo", "o/r"]);
    assert.equal(args[5], "--comment");
    assert.match(args[6], /T-123/);
  });

  it("comments on transition todo -> doing without reopening", () => {
    const calls: string[][] = [];
    const runGh = (args: string[]) => {
      calls.push(args);
      return "";
    };
    const res = mirrorStatusToGithub(
      ref,
      { from: "todo", to: "doing" },
      { runGh, assignee: "agent-a" },
    );
    assert.ok("ok" in res && res.ok);
    if ("ok" in res) assert.equal(res.action, "commented");
    assert.equal(calls.length, 1);
    assert.equal(calls[0][1], "comment");
    assert.match(calls[0][6], /picked up by agent-a/);
  });

  it("comments on triage -> doing", () => {
    const calls: string[][] = [];
    const runGh = (args: string[]) => {
      calls.push(args);
      return "";
    };
    const res = mirrorStatusToGithub(ref, { from: "triage", to: "doing" }, { runGh });
    assert.ok("ok" in res && res.ok);
    if ("ok" in res) assert.equal(res.action, "commented");
  });

  it("reopens when leaving done", () => {
    const calls: string[][] = [];
    const runGh = (args: string[]) => {
      calls.push(args);
      return "";
    };
    const res = mirrorStatusToGithub(ref, { from: "done", to: "doing" }, { runGh });
    assert.ok("ok" in res && res.ok);
    if ("ok" in res) assert.equal(res.action, "reopened");
    assert.equal(calls.length, 1);
    assert.equal(calls[0][1], "reopen");
  });

  it("noops on transitions that don't map to a gh action", () => {
    let called = 0;
    const runGh = () => {
      called += 1;
      return "";
    };
    const res = mirrorStatusToGithub(ref, { from: "doing", to: "doing" }, { runGh });
    assert.ok("ok" in res && res.ok);
    if ("ok" in res) assert.equal(res.action, "noop");
    assert.equal(called, 0);
  });

  it("rejects non github_issue refs", () => {
    const res = mirrorStatusToGithub(
      { kind: "notion_page" as unknown as "github_issue", id: 1, url: "u" },
      { to: "done" },
      { runGh: () => "" },
    );
    assert.ok("error" in res);
    if ("error" in res) {
      assert.equal(res.error.code, "invalid_external_ref");
      assert.match(res.error.message, /expected github_issue/);
    }
  });

  it("rejects malformed URLs", () => {
    const res = mirrorStatusToGithub(
      { kind: "github_issue", id: 1, url: "not-a-url" },
      { to: "done" },
      { runGh: () => "" },
    );
    assert.ok("error" in res);
    if ("error" in res) assert.equal(res.error.code, "invalid_external_ref");
  });

  it("wraps gh failures as upstream_error", () => {
    const runGh = () => {
      throw new Error("gh: not authenticated");
    };
    const res = mirrorStatusToGithub(ref, { from: "doing", to: "done" }, { runGh });
    assert.ok("error" in res);
    if ("error" in res) {
      assert.equal(res.error.code, "upstream_error");
      assert.match(res.error.message, /not authenticated/);
    }
  });
});

describe("dispatchGithubInbound — mirror", () => {
  const ref = {
    kind: "github_issue",
    id: 7,
    url: "https://github.com/o/r/issues/7",
  };

  it("dispatches inbound_github_mirror end-to-end", async () => {
    const runGh = () => "";
    const res = await dispatchGithubInbound(
      "inbound_github_mirror",
      { external_ref: ref, transition: { from: "doing", to: "done" }, task_id: "T-9" },
      { runGh },
    );
    assert.ok("ok" in res && res.ok);
    if ("ok" in res && "action" in res) assert.equal(res.action, "closed");
  });

  it("returns invalid_argument when external_ref is missing", async () => {
    const res = await dispatchGithubInbound(
      "inbound_github_mirror",
      { transition: { to: "done" } },
      { runGh: () => "" },
    );
    assert.ok("error" in res);
    if ("error" in res) assert.equal(res.error.code, "invalid_argument");
  });

  it("returns invalid_argument when transition.to is missing", async () => {
    const res = await dispatchGithubInbound(
      "inbound_github_mirror",
      { external_ref: ref, transition: {} },
      { runGh: () => "" },
    );
    assert.ok("error" in res);
    if ("error" in res) assert.equal(res.error.code, "invalid_argument");
  });

  it("propagates upstream_error from gh", async () => {
    const runGh = () => {
      throw new Error("gh exploded");
    };
    const res = await dispatchGithubInbound(
      "inbound_github_mirror",
      { external_ref: ref, transition: { to: "done" } },
      { runGh },
    );
    assert.ok("error" in res);
    if ("error" in res) assert.equal(res.error.code, "upstream_error");
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
    if ("ok" in res && "result" in res) {
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
