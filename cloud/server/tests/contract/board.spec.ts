import { describe, it, expect, beforeEach } from "vitest";
import request from "supertest";
import { app, db } from "../../src/index.js";
import { publishBoard, subscribeBoard } from "../../src/lib/events.js";

// Exercises the canonical board (ADR-003): tasks/cycles/epics/activity,
// the role write-gate, and activity emission. No provider/fetch involved.

let orgId: string;
let projectId: string;

beforeEach(async () => {
  await db.activity.deleteMany({});
  await db.task.deleteMany({});
  await db.cycle.deleteMany({});
  await db.epic.deleteMany({});
  await db.project.deleteMany({});
  await db.orgMember.deleteMany({});
  await db.org.deleteMany({ where: { name: "board1" } });

  const founder = await db.user.upsert({
    where: { email: "board1-founder@local" },
    update: {},
    create: { email: "board1-founder@local", name: "board1-founder" },
  });
  const viewer = await db.user.upsert({
    where: { email: "board1-viewer@local" },
    update: {},
    create: { email: "board1-viewer@local", name: "board1-viewer" },
  });
  const org = await db.org.create({ data: { name: "board1" } });
  orgId = org.id;
  await db.orgMember.create({ data: { orgId, userId: founder.id, role: "founder" } }); // → owner
  await db.orgMember.create({ data: { orgId, userId: viewer.id, role: "viewer" } });
  const project = await db.project.create({
    data: { orgId, name: "p", githubRepo: "octo/p", createdById: founder.id },
  });
  projectId = project.id;
});

const base = () => `/api/orgs/${orgId}/projects/${projectId}`;
const asFounder = (m: "get" | "post" | "patch", path: string) =>
  request(app)[m](path).set("X-User-Id", "board1-founder");

describe("canonical board — tasks", () => {
  it("a member creates a task (default status triage) and it appears in the list", async () => {
    const res = await asFounder("post", `${base()}/tasks`).send({ title: "Fix the thing" });
    expect(res.status).toBe(201);
    expect(res.body).toMatchObject({ title: "Fix the thing", status: "triage", escalated: false });

    const list = await asFounder("get", `${base()}/tasks`);
    expect(list.status).toBe(200);
    expect(list.body).toHaveLength(1);
    expect(list.body[0].id).toBe(res.body.id);
  });

  it("task creation emits a task_created activity", async () => {
    await asFounder("post", `${base()}/tasks`).send({ title: "T" });
    const feed = await asFounder("get", `${base()}/activity`);
    expect(feed.status).toBe(200);
    expect(feed.body.some((a: { kind: string }) => a.kind === "task_created")).toBe(true);
  });

  it("status change updates the task and emits status_changed (from→to)", async () => {
    const created = await asFounder("post", `${base()}/tasks`).send({ title: "T" });
    const patch = await asFounder("patch", `${base()}/tasks/${created.body.id}`).send({
      status: "in_progress",
    });
    expect(patch.status).toBe(200);
    expect(patch.body.status).toBe("in_progress");
    const feed = await asFounder("get", `${base()}/activity`);
    const sc = feed.body.find((a: { kind: string }) => a.kind === "status_changed");
    expect(sc).toBeTruthy();
    expect(sc.payload).toMatchObject({ from: "triage", to: "in_progress" });
  });

  it("escalated is an orthogonal flag set via PATCH without changing status", async () => {
    const created = await asFounder("post", `${base()}/tasks`).send({ title: "T" });
    const patch = await asFounder("patch", `${base()}/tasks/${created.body.id}`).send({
      escalated: true,
    });
    expect(patch.status).toBe(200);
    expect(patch.body).toMatchObject({ escalated: true, status: "triage" });
  });

  it("rejects an invalid status with 400", async () => {
    const res = await asFounder("post", `${base()}/tasks`).send({ title: "T", status: "bogus" });
    expect(res.status).toBe(400);
    expect(res.body.error.code).toBe("invalid_body");
  });
});

describe("canonical board — role write-gate (ADR-003)", () => {
  it("a viewer cannot create a task (403 forbidden)", async () => {
    const res = await request(app)
      .post(`${base()}/tasks`)
      .set("X-User-Id", "board1-viewer")
      .send({ title: "nope" });
    expect(res.status).toBe(403);
    expect(res.body.error.code).toBe("forbidden");
  });

  it("a viewer CAN read tasks (viewer+ read access)", async () => {
    await asFounder("post", `${base()}/tasks`).send({ title: "T" });
    const res = await request(app).get(`${base()}/tasks`).set("X-User-Id", "board1-viewer");
    expect(res.status).toBe(200);
    expect(res.body).toHaveLength(1);
  });

  it("a non-member gets 404 on the board", async () => {
    const res = await request(app).get(`${base()}/tasks`).set("X-User-Id", "board1-outsider");
    expect(res.status).toBe(404);
  });
});

describe("canonical board — cycles & epics", () => {
  it("creates a cycle and an epic", async () => {
    const cycle = await asFounder("post", `${base()}/cycles`).send({ name: "Sprint 1" });
    expect(cycle.status).toBe(201);
    expect(cycle.body).toMatchObject({ name: "Sprint 1", status: "upcoming" });

    const epic = await asFounder("post", `${base()}/epics`).send({ title: "Launch" });
    expect(epic.status).toBe(201);
    expect(epic.body).toMatchObject({ title: "Launch", status: "backlog" });
  });
});

describe("acceptance-criteria evidence guard (Phase 5)", () => {
  it("blocks done while a criterion is unmet, then allows it once met", async () => {
    const created = await asFounder("post", `${base()}/tasks`).send({ title: "Guarded" });
    const tid = created.body.id;
    const crit = await asFounder("post", `${base()}/tasks/${tid}/criteria`).send({
      kind: "test",
      description: "unit tests pass",
    });
    expect(crit.status).toBe(201);
    expect(crit.body).toMatchObject({ kind: "test", met: false });

    const blocked = await asFounder("patch", `${base()}/tasks/${tid}`).send({ status: "done" });
    expect(blocked.status).toBe(400);
    expect(blocked.body.error.code).toBe("criteria_missing_evidence");

    const met = await asFounder("patch", `${base()}/tasks/${tid}/criteria/${crit.body.id}`).send({
      met: true,
      evidence: JSON.stringify({ run: "vitest", exit: 0 }),
    });
    expect(met.status).toBe(200);
    expect(met.body.met).toBe(true);

    const ok = await asFounder("patch", `${base()}/tasks/${tid}`).send({ status: "done" });
    expect(ok.status).toBe(200);
    expect(ok.body.status).toBe("done");
  });

  it("allows done when a task has no criteria", async () => {
    const created = await asFounder("post", `${base()}/tasks`).send({ title: "Free" });
    const ok = await asFounder("patch", `${base()}/tasks/${created.body.id}`).send({ status: "done" });
    expect(ok.status).toBe(200);
  });
});

describe("board events hub (SSE fan-out)", () => {
  it("delivers events to project subscribers, scoped by project, and stops after unsubscribe", () => {
    const got: string[] = [];
    const unsub = subscribeBoard("proj-x", (ev) => got.push(ev.kind));
    publishBoard("proj-x", { kind: "task_created", at: new Date().toISOString() });
    publishBoard("proj-y", { kind: "status_changed", at: new Date().toISOString() }); // other channel
    unsub();
    publishBoard("proj-x", { kind: "status_changed", at: new Date().toISOString() }); // after unsub
    expect(got).toEqual(["task_created"]);
  });

  it("non-member gets 404 on the live stream", async () => {
    const res = await request(app).get(`${base()}/stream`).set("X-User-Id", "board1-outsider");
    expect(res.status).toBe(404);
  });
});
