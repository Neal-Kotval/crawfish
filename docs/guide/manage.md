# Manage deployed pipelines

`craw manage` shows every [deployed](deploy.md) pipeline in one view. It reads three
things: the deploy registry (what is running), the execution ledger (run history), and the
cost meter (what you have spent). From there you stop, restart, or tail any pipeline by
name.

## Run the command

```bash
craw manage                       # list every deployed pipeline
craw manage stop    <name>        # stop the supervisor
craw manage restart <name>        # restart the supervisor (re-reads schedule)
craw manage logs    <name>        # tail the supervisor + run logs
```

Run `craw manage` with no arguments to list deployed pipelines. Each pipeline gets a row:
name, status, uptime, last run, next fire (for a cron deploy), and $ today.

`craw manage` only reads. It never re-runs a pipeline to answer a query. Every number
comes from a Store-backed surface.

## See and control a fleet by name

After deploying the triage bot (see [deploy](deploy.md)), list the fleet:

```bash
craw manage
# NAME                     STATUS    UPTIME    LAST RUN        NEXT FIRE   $ TODAY
# crawfish/triage-bot      running   06:14:02  08:00 (ok)      08:00       $0.42
# triage-drain             running   01:09:55  18:21 (ok)      —           $0.07
```

`$ TODAY` comes from the cost meter, so you watch spend add up per pipeline without opening
the dashboard. `NEXT FIRE` is blank for a continuous deploy.

Tail a pipeline to watch cycles fire and observer events land:

```bash
craw manage logs crawfish/triage-bot
# 08:00:01  cycle start  run=01HZ…  items=3
# 08:00:04  observer cost.spike  severity=warn  detail="run cost $0.31 > 2x median"
# 08:00:05  cycle ok     run=01HZ…  cost=$0.31
```

Stop a pipeline and the supervisor exits cleanly, leaving its registry row marked stopped.
Restart it to pick up a changed schedule:

```bash
craw manage stop    crawfish/triage-bot
craw manage restart crawfish/triage-bot
```

## Where the numbers come from

`craw manage` only reads. It pulls from three Store-backed sources and never re-runs a
pipeline to answer a query:

| Column              | Source                                                  |
| ------------------- | ------------------------------------------------------- |
| status, uptime      | deploy registry (the supervisor's PID entry)            |
| last run, next fire | execution ledger + the supervisor's schedule            |
| $ today             | cost meter (`CostMeter`, the live spend accumulator)    |

This is the same ledger that backs `craw inspect` and `craw logs`, so deployed and
foreground runs share one history.

## Why tailing logs is safe

`craw manage` reads scrubbed surfaces only. The registry, ledger, and cost meter hold no
secret values, because secrets resolve by reference at run time and are never stored.
`logs` tails the supervisor and run logs, which are already scrubbed. Every row is scoped
by `org_id`.

There is no secret value to leak through `craw manage logs`. Logs are scrubbed before they
are written, so tailing them is always safe.

## Next steps

- [Deploy a pipeline](deploy.md) starts the supervisors `craw manage` lists.
- [Run a pipeline in the background](operations.md) shows how manage fits with deploy,
  observers, and the dashboard.
- [SECURITY.md](../architecture/SECURITY.md) covers the full security spine.
