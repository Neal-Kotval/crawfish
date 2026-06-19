# demo/ — Crawfish dogfood

A mini real project that depends on Crawfish and exercises every capability as it
lands. The framework's own self-test and the hero example for the guide (CRA-118).

## `triage-bot/` (grows per milestone)

The target shape, filled in as milestones complete:

- a **Source** (canned fixtures, no external creds),
- a **Definition** authored as a directory,
- a **Batch** with fan-out (one Run per item),
- an **Aggregator** (reduce N outputs → one digest),
- a **Router** (branch by classification),
- a **Sink** in `--dry-run` mode.

Run it after every milestone via `craw dev` (CommandRuntime / `claude -p`, zero API
key, fixtures + mock/cheap model). If the demo can't run a new feature end to end, the
milestone is not done.

> M0: the directory exists and the framework imports cleanly. Authoring lands in M1.
