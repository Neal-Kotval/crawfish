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

program.command("install-hooks").action(() => {
  installHooks(root());
});

program.command("uninstall-hooks").action(() => {
  uninstallHooks(root());
});

program.parseAsync();
