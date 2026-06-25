# Deploy a pipeline

`craw deploy` keeps a pipeline running instead of running it once. It starts a *detached
supervisor*, a background process that survives the shell closing. The supervisor fires
the pipeline on a schedule or continuously, restarts failed cycles, and picks up runs left
in flight after a restart by reading the execution ledger.

A deploy stays local and needs no key. The supervisor drives the same `claude -p` path a
foreground run does, with no hosted dependency. Moving from `craw dev` to `craw deploy`
changes how the pipeline runs, not the code.

## Run the command

```bash
craw deploy <pipeline> [--schedule "<cron>"] [--name <name>]
```

- `--schedule "<cron>"` fires on a 5-field cron expression. For example, `"0 8 * * *"` is
  08:00 daily. Omit it to run continuously: each cycle starts when the previous one
  finishes.
- `--name <name>` sets the registry name. It defaults to `crawfish/<pipeline>`.

The supervisor records its process ID in a Store-backed deploy registry, so
[`craw manage`](manage.md) and [`craw visualize`](visualize.md) can see it. It writes a
checkpoint for each fired run to the execution ledger. On restart, the supervisor resumes
runs that were in flight instead of dropping or duplicating them.

## Deploy the triage bot

Run the demo pipeline every morning at 08:00:

```bash
craw deploy demo/triage-bot --schedule "0 8 * * *"
# deployed: crawfish/triage-bot (schedule: 0 8 * * *) — supervisor pid 48213
```

The command returns right away, and the supervisor keeps running after you close the
terminal. Confirm it is registered:

```bash
craw manage
# NAME                     STATUS    UPTIME   LAST RUN   NEXT FIRE    $ TODAY
# crawfish/triage-bot      running   00:00:12 —          08:00        $0.00
```

To run continuously instead, drop `--schedule`. Each cycle begins when the last one ends,
which is useful for draining a queue:

```bash
craw deploy demo/triage-bot --name triage-drain
```

Stop, restart, or tail it with [`craw manage`](manage.md):

```bash
craw manage logs crawfish/triage-bot
craw manage stop crawfish/triage-bot
```

## How resume works across a crash

A deploy never drops or duplicates a run, even across a crash.

Each cycle's run is written to the execution ledger before it starts. If the supervisor
dies mid-cycle, from a crash or a reboot, and then restarts, it reads the ledger, finds the
runs that were in flight, and resumes them. This is the same checkpoint-and-resume
machinery that lets a foreground workflow survive a crash. A failed cycle restarts on its
own, and the schedule is never silently skipped.

## How a supervisor handles secrets

A detached supervisor outlives your shell, so it holds secrets as carefully as a
foreground run. It follows the secrets-by-reference rule:

- No secret values on the command line. The session name is `crawfish/<pipeline>`. No
  credential appears in argv, where `ps` could read it.
- No secret values in the environment, registry, or logs. The supervisor resolves secrets
  by reference (an env-var name) at the egress boundary, the same way a foreground run
  does. It never copies them into the detached process's environment, the deploy registry
  row, or the supervisor log.
- Tenancy. Every registry and ledger row carries `org_id` (defaulted `"local"`).

!!! warning "Secrets never enter argv"
    A secret value never reaches the command line, the detached process's environment, the
    registry row, or any log. The supervisor resolves secrets by reference at the egress
    boundary. Anyone with `ps` sees only `crawfish/<pipeline>`, never a credential.

## Next steps

- [Run a pipeline in the background](operations.md) shows how deploy fits with observers,
  the dashboard, and `craw manage`.
- [Manage deployed pipelines](manage.md) stops, restarts, and tails a supervisor.
- [SECURITY.md](../architecture/SECURITY.md) covers the full security spine.
