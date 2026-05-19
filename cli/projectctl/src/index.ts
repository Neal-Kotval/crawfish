#!/usr/bin/env node
import { Command } from "commander";
import { init } from "./verbs/init.js";
import { refresh } from "./verbs/refresh.js";
import { status } from "./verbs/status.js";
import { doctor } from "./verbs/doctor.js";
import { decisionAdd } from "./verbs/decision-add.js";
import { activityRecord } from "./verbs/activity-record.js";
import { memoryAppend } from "./verbs/memory-append.js";
import { installHooks, uninstallHooks } from "./verbs/install-hooks.js";
import { boardRebuild } from "./verbs/board-rebuild.js";
import { createTask, updateTask, deleteTask, type TaskStatus } from "./tasks.js";
import { createCycle, listCycles, computeRollup } from "./cycles.js";
import { createEpic, listEpics, updateEpic, computeEpicRollup } from "./epics.js";

const program = new Command();
program.name("crawfish-projectctl").version("0.1.0");
program.option("--cwd <dir>", "repo root", process.cwd());

function root(): string {
  return (program.opts() as { cwd: string }).cwd;
}

program.command("init").description("scaffold .crawfish/").action(async () => {
  console.log(await init(root()));
});

program.command("refresh [files...]")
  .option("--debounce <ms>", "skip if last refresh within window", "0")
  .action(async (files: string[], opts: { debounce: string }) => {
    const r = await refresh(root(), {
      debounceMs: Number(opts.debounce),
      only: files.length > 0 ? files : undefined,
    });
    console.log(JSON.stringify(r, null, 2));
  });

program.command("status").action(async () => {
  console.log(JSON.stringify(await status(root()), null, 2));
});

program.command("doctor").action(() => {
  const d = doctor(root());
  console.log(JSON.stringify(d, null, 2));
  if (d.errors.length > 0) process.exit(1);
});

program.command("decision add <title> <body>").action((title: string, body: string) => {
  decisionAdd(root(), title, body);
});

program.command("activity record [summary]").action((summary?: string) => {
  const text = summary ?? "(no summary)";
  activityRecord(root(), text);
});

program.command("memory append <text>").action((text: string) => {
  memoryAppend(root(), text, []);
});

program.command("board:rebuild")
  .description("Rebuild .crawfish/board.jsonl from current task and cycle files")
  .action(() => {
    const r = boardRebuild(root());
    console.log(JSON.stringify(r, null, 2));
  });

program.command("task:create <slug> <title>")
  .option("--status <s>", "todo|doing|done|blocked", "todo")
  .option("--phase <p>", "now|next|later")
  .option("--estimate <n>", "token estimate", (v) => Number(v))
  .option("--cycle <id>", "cycle ULID")
  .option("--epic <id>", "epic ULID")
  .action((slug: string, title: string, opts: Record<string, unknown>) => {
    const path = createTask(root(), {
      slug,
      title,
      status: opts.status as TaskStatus,
      phase: opts.phase as "now" | "next" | "later" | undefined,
      estimate: typeof opts.estimate === "number" ? opts.estimate : undefined,
      cycle: opts.cycle as string | undefined,
      epic: opts.epic as string | undefined,
    });
    console.log(path);
  });

program.command("task:update <slug>")
  .option("--status <s>", "todo|doing|done|blocked")
  .option("--phase <p>", "now|next|later")
  .option("--title <t>", "new title")
  .option("--estimate <n>", "token estimate", (v) => Number(v))
  .option("--cycle <id>", "cycle ULID (or 'null' to clear)")
  .option("--epic <id>", "epic ULID (or 'null' to clear)")
  .action((slug: string, opts: Record<string, unknown>) => {
    updateTask(root(), slug, {
      status: opts.status as TaskStatus | undefined,
      phase: opts.phase as "now" | "next" | "later" | undefined,
      title: opts.title as string | undefined,
      estimate: typeof opts.estimate === "number" ? opts.estimate : undefined,
      cycle: opts.cycle === "null" ? null : (opts.cycle as string | undefined),
      epic: opts.epic === "null" ? null : (opts.epic as string | undefined),
    });
  });

program.command("task:delete <slug>").action((slug: string) => {
  deleteTask(root(), slug);
});

program.command("cycle:create <id> <name>")
  .requiredOption("--start <date>", "ISO start date (YYYY-MM-DD)")
  .requiredOption("--end <date>", "ISO end date (YYYY-MM-DD)")
  .requiredOption("--budget <tokens>", "token budget", (v) => Number(v))
  .action((id: string, name: string, opts: { start: string; end: string; budget: number }) => {
    const c = createCycle(root(), { id, name, start: opts.start, end: opts.end, token_budget: opts.budget });
    console.log(JSON.stringify(c, null, 2));
  });

program.command("cycle:list").action(() => {
  console.log(JSON.stringify(listCycles(root()), null, 2));
});

program.command("cycle:rollup <id>").action((id: string) => {
  const r = computeRollup(root(), id);
  if (!r) {
    console.error(`cycle not found: ${id}`);
    process.exit(1);
  }
  console.log(JSON.stringify(r, null, 2));
});

program.command("epic:create <id> <title>")
  .option("--parent-cycle <id>", "cycle ULID this epic rolls up under")
  .option("--body <text>", "markdown body")
  .action((id: string, title: string, opts: { parentCycle?: string; body?: string }) => {
    const path = createEpic(root(), { id, title, parent_cycle: opts.parentCycle, body: opts.body });
    console.log(path);
  });

program.command("epic:list").action(() => {
  console.log(JSON.stringify(listEpics(root()), null, 2));
});

program.command("epic:close <id>").action((id: string) => {
  updateEpic(root(), id, { status: "closed" });
});

program.command("epic:rollup <id>").action((id: string) => {
  const r = computeEpicRollup(root(), id);
  if (!r) {
    console.error(`epic not found: ${id}`);
    process.exit(1);
  }
  console.log(JSON.stringify(r, null, 2));
});

program.command("install-hooks").action(() => {
  installHooks(root());
});

program.command("uninstall-hooks").action(() => {
  uninstallHooks(root());
});

program.parseAsync();
