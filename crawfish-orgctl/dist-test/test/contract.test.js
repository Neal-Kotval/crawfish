/**
 * Contract tests for crawfish-orgctl. Verify, against the optimizer
 * contract v1.0 + spec §6:
 *   - every tool response includes tokens_used
 *   - board_create_task round-trips through board_list_tasks
 *   - board_update_task is idempotent
 *   - org_fs_write / org_fs_read round-trip
 *   - path-escape attempts are rejected
 *   - >1 MiB writes are rejected with too_large
 */
import { test } from "node:test";
import assert from "node:assert/strict";
import * as fs from "node:fs";
import * as fsp from "node:fs/promises";
import * as os from "node:os";
import * as path from "node:path";
// Set CRAWFISH_HOME BEFORE importing the server so orgs.ts picks it up.
const TMP = fs.mkdtempSync(path.join(os.tmpdir(), "crawfish-orgctl-test-"));
process.env.CRAWFISH_HOME = TMP;
const ORG_ID = "test-org-01";
fs.mkdirSync(path.join(TMP, "orgs", ORG_ID, "files"), { recursive: true });
const { runTool } = await import("../src/index.js");
function assertTokens(r) {
    assert.equal(typeof r.tokens_used, "number", `tokens_used missing on ${JSON.stringify(r)}`);
    if ("error" in r) {
        assert.equal(r.tokens_used, 0, "error responses must have tokens_used=0");
    }
    else {
        assert.ok(r.tokens_used > 0, "success responses must have tokens_used > 0");
    }
}
test("every tool returns tokens_used", async () => {
    const r1 = await runTool("board_list_tasks", { org_id: ORG_ID });
    assertTokens(r1);
    const r2 = await runTool("org_fs_list", { org_id: ORG_ID });
    assertTokens(r2);
});
test("board_create_task round-trips through board_list_tasks", async () => {
    const created = await runTool("board_create_task", {
        org_id: ORG_ID,
        title: "First task",
        description: "demo",
        assignee: "founder",
        by: "founder",
    });
    assertTokens(created);
    assert.equal(typeof created.task_id, "string");
    assert.equal(created.task_id.length, 26);
    const listed = await runTool("board_list_tasks", { org_id: ORG_ID });
    assertTokens(listed);
    const found = listed.tasks.find((t) => t.id === created.task_id);
    assert.ok(found, "created task should appear in list");
    assert.equal(found.title, "First task");
    assert.equal(found.status, "backlog");
    assert.equal(found.assignee, "founder");
});
test("board_update_task is idempotent on retry", async () => {
    const created = await runTool("board_create_task", {
        org_id: ORG_ID,
        title: "Update me",
        description: "",
        by: "founder",
    });
    const patch = { status: "in_progress" };
    const r1 = await runTool("board_update_task", {
        org_id: ORG_ID,
        task_id: created.task_id,
        by: "founder",
        patch,
    });
    assertTokens(r1);
    assert.equal(r1.ok, true);
    // Apply same patch again — should not error.
    const r2 = await runTool("board_update_task", {
        org_id: ORG_ID,
        task_id: created.task_id,
        by: "founder",
        patch,
    });
    assertTokens(r2);
    assert.equal(r2.ok, true);
    const listed = await runTool("board_list_tasks", {
        org_id: ORG_ID,
        status: "in_progress",
    });
    const found = listed.tasks.find((t) => t.id === created.task_id);
    assert.ok(found);
    assert.equal(found.status, "in_progress");
});
test("board_comment appends and shows up in folded task", async () => {
    const created = await runTool("board_create_task", {
        org_id: ORG_ID,
        title: "Comment target",
        description: "",
        by: "founder",
    });
    const r = await runTool("board_comment", {
        org_id: ORG_ID,
        task_id: created.task_id,
        by: "eng",
        body: "hello",
    });
    assertTokens(r);
    const listed = await runTool("board_list_tasks", { org_id: ORG_ID });
    const t = listed.tasks.find((t) => t.id === created.task_id);
    assert.equal(t.comments.length, 1);
    assert.equal(t.comments[0].body, "hello");
});
test("org_fs_write + org_fs_read round-trip", async () => {
    const w = await runTool("org_fs_write", {
        org_id: ORG_ID,
        path: "notes/hello.md",
        content: "# Hello\n",
    });
    assertTokens(w);
    assert.equal(w.size, 8);
    const r = await runTool("org_fs_read", {
        org_id: ORG_ID,
        path: "notes/hello.md",
    });
    assertTokens(r);
    assert.equal(r.content, "# Hello\n");
    // Idempotent re-write
    const w2 = await runTool("org_fs_write", {
        org_id: ORG_ID,
        path: "notes/hello.md",
        content: "# Hello\n",
    });
    assertTokens(w2);
    assert.equal(w2.size, 8);
    const list = await runTool("org_fs_list", { org_id: ORG_ID });
    assertTokens(list);
    assert.ok(list.entries.find((e) => e.path === "notes/hello.md"));
});
test("path escape is rejected", async () => {
    const r = await runTool("org_fs_read", {
        org_id: ORG_ID,
        path: "../../../etc/passwd",
    });
    assert.equal(r.tokens_used, 0);
    assert.equal(r.error.code, "path_escape");
    const r2 = await runTool("org_fs_write", {
        org_id: ORG_ID,
        path: "/etc/passwd",
        content: "x",
    });
    assert.equal(r2.error.code, "path_escape");
    const r3 = await runTool("org_fs_write", {
        org_id: ORG_ID,
        path: "foo\0bar",
        content: "x",
    });
    assert.equal(r3.error.code, "path_escape");
});
test("oversize write rejected as too_large", async () => {
    const big = "x".repeat(1024 * 1024 + 1);
    const r = await runTool("org_fs_write", {
        org_id: ORG_ID,
        path: "big.bin",
        content: big,
    });
    assert.equal(r.error.code, "too_large");
});
test("missing org returns not_found", async () => {
    const r = await runTool("board_list_tasks", { org_id: "does-not-exist" });
    assert.equal(r.error.code, "not_found");
});
test("invalid status rejected", async () => {
    const r = await runTool("board_list_tasks", {
        org_id: ORG_ID,
        status: "weird",
    });
    assert.equal(r.error.code, "invalid_status");
});
test.after(async () => {
    await fsp.rm(TMP, { recursive: true, force: true });
});
