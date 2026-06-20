# ADR 0009 — `craw deploy` uses a detached session-leader daemon, not tmux

**Status:** Accepted · **Date:** 2026-06-19 · **Milestone:** Phase 1 Hardening

## Context

`craw deploy` must run a project's pipeline **always-on**: detached, surviving the
shell closing, auto-restarting on crash, firing on a cron trigger, and resuming via the
execution ledger. The issue describes it as "tmux-style." A literal tmux dependency
would give a nice attachable pane, but tmux is **not guaranteed installed** (especially
in CI / containers), adds an external process we don't control, and the pane name is a
classic place secrets leak into.

## Decision

Default to a **detached session-leader daemon**, with tmux as an optional backend label:

- `deploy()` spawns `python -m crawfish.cli _supervise <name> --dir <dir> [--schedule …]`
  via `subprocess.Popen(start_new_session=True, ...)` (a `setsid` child) so it outlives
  the shell, with stdout/stderr to `.crawfish/deploys/<name>.log`.
- A Store-backed **deploy registry** records the PID, session label `crawfish/<name>`,
  schedule, and status so `craw manage` / `craw visualize` can see and control it; PID
  liveness is checked with `os.kill(pid, 0)` and stale rows are reported `dead`.
- The **supervisor logic is separated from the spawn**: `Supervisor.run_cycle` /
  `due` / `serve` take injectable clock/sleep/stop seams, so scheduling, auto-restart,
  and ledger reconciliation are unit-tested deterministically without launching a
  daemon. The `spawn` callable is injectable for the same reason.

**Security:** the child's argv carries only the pipeline name + project dir — never a
secret. The session label is `crawfish/<name>` (no secret). The child resolves secrets
by reference exactly like a foreground run and wraps its Store in `ScrubbingStore`, so
the log/ledger never holds a raw credential. No env dump is ever written.

**Resume:** on (re)start the supervisor calls `ExecutionLedger.reconcile()` — orphaned
ephemeral-backend runs are marked `needs_retry`; completed fan-out items are not redone.

## Alternatives rejected

- **Hard tmux dependency** — not portable, external process, pane-name leak surface.
- **A full process supervisor (systemd/supervisord)** — heavyweight, OS-specific, wrong
  altitude for a local "runs always-on" command; cloud/container deploy is a later milestone.
- **Threads inside the CLI process** — dies with the shell; fails the survive-exit
  acceptance.

## Consequences

Deploy works with zero external dependencies on macOS/Linux. The tmux ergonomic (an
attachable pane) is deferred to an optional backend that reuses the same registry +
supervisor; switching backends never changes the supervisor logic or the security
properties. Windows support would need a different detach primitive (out of scope now).
