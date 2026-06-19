# Deploy — always-on pipelines

`craw deploy` takes a pipeline from **runs-once** to **always-on**. It detaches a
supervisor process that survives the shell closing, fires the pipeline on a schedule (or
continuously), auto-restarts failed cycles, and resumes orphaned runs via the execution
ledger after a restart.

A deploy is a local, key-free thing: the supervisor drives the same `claude -p` path a
foreground run does. There is no hosted dependency — switching from `craw dev` to
`craw deploy` is an operating-mode change, not a code change.

## Command

```bash
craw deploy <pipeline> [--schedule "<cron>"] [--name <name>]
```

- `--schedule "<cron>"` — fire on a 5-field cron expression (e.g. `"0 8 * * *"` =
  08:00 daily). Omit it to run **continuously**: each cycle starts when the previous one
  finishes.
- `--name <name>` — registry name. Defaults to `crawfish/<pipeline>`.

The supervisor registers a PID entry in a **Store-backed deploy registry**, so
[`craw manage`](manage.md) and [`craw visualize`](visualize.md) can see it. Each fired
run is checkpointed to the execution ledger, so a supervisor restart **resumes orphaned
runs** rather than dropping or duplicating them.

## Worked example — deploy the triage bot

Run the demo pipeline every morning at 08:00:

```bash
craw deploy demo/triage-bot --schedule "0 8 * * *"
# deployed: crawfish/triage-bot (schedule: 0 8 * * *) — supervisor pid 48213
```

The command returns immediately; the supervisor keeps running after you close the
terminal. Confirm it is registered:

```bash
craw manage
# NAME                     STATUS    UPTIME   LAST RUN   NEXT FIRE    $ TODAY
# crawfish/triage-bot      running   00:00:12 —          08:00        $0.00
```

To run continuously instead (each cycle begins when the last ends — useful for a queue
drain), drop `--schedule`:

```bash
craw deploy demo/triage-bot --name triage-drain
```

Stop, restart, or tail it with [`craw manage`](manage.md):

```bash
craw manage logs crawfish/triage-bot
craw manage stop crawfish/triage-bot
```

## Resume semantics

Each cycle's run is written to the execution ledger before it starts. If the supervisor
dies mid-cycle (crash, reboot) and is restarted, it reads the ledger, finds runs that
were in flight, and **resumes them** — the same checkpoint/resume machinery that lets a
foreground workflow survive a crash. A failed cycle is auto-restarted; the schedule is
never silently skipped.

## Security

The deploy supervisor upholds the framework's **secrets-by-reference** spine:

- **No secret values in argv.** The session name is `crawfish/<pipeline>`; no credential
  appears on the command line, where `ps` could read it.
- **No secret values in the environment, registry, or logs.** Secrets are resolved by
  *reference* (an env-var name) at the egress boundary, exactly as in a foreground run —
  never copied into the detached process's environment, the deploy registry row, or the
  supervisor log.
- **Tenancy.** Every registry and ledger row carries `org_id` (defaulted `"local"`).

See the [operations overview](operations.md) for how deploy fits together with observers,
the dashboard, and `craw manage`, and [SECURITY.md](../architecture/SECURITY.md) for the
full spine.
