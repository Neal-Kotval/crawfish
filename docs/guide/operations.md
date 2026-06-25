# Run a pipeline in the background

`craw dev` runs a pipeline once against the mock. To keep one running, you deploy it as a
background process, watch it for failures, see it on a localhost dashboard, and control it
from the CLI. This page shows how the four commands fit together.

You use four commands:

| Stage     | Command or API                       | What it does |
| --------- | ------------------------------------ | ------------ |
| deploy    | [`craw deploy`](deploy.md)           | Starts a background process (a supervisor) on a cron schedule or continuously. Restarts failed cycles and resumes runs left in flight. |
| observe   | [`crawfish.observe`](observers.md)   | Polls the event stream and raises an alert on failures, cost, latency, or an LLM judge. |
| visualize | [`craw visualize`](visualize.md)     | Serves a dashboard over the run-info surface, on loopback only. |
| manage    | [`craw manage`](manage.md)           | Lists, stops, restarts, and tails deployed pipelines by name. |

All four read and write one place: the *run-info surface*, an `ObserverSurface` handle
backed by the `Store`. Each cycle, the supervisor writes a `RunInfo` record, observers
emit `ObserverEvent`s, and the dashboard and `craw manage` read both. Every write is
scrubbed (secret values stripped) and scoped by `org_id`. An alert an observer raises
shows up in the dashboard and in `craw manage logs` at once, with no secret value anywhere
in the path.

## Take the triage bot from one run to always on

This walkthrough takes `demo/triage-bot` from a one-shot run to a supervised, observed,
dashboarded pipeline.

### 1. Deploy it

```bash
craw deploy demo/triage-bot --schedule "0 8 * * *"
# deployed: crawfish/triage-bot (schedule: 0 8 * * *) — supervisor pid 48213
```

The supervisor detaches, registers in the deploy registry, and fires at 08:00 daily. It
survives the shell closing. If it crashes mid-cycle, it resumes from the execution ledger.

### 2. Add an observer

Attach a watcher that warns on cost spikes and runs a quality judge. Both run under the
normal cost cap and the prompt-injection boundary, so untrusted run data reaches the model
as data, never as instructions:

```python
from crawfish.observe import Observer, ObserverSurface, Severity
from crawfish import Definition, SqliteStore

surface = ObserverSurface(SqliteStore(), org_id="local")
watch = Observer(
    pipeline="triage-bot",
    interval="*/5 * * * *",
    rules=[Observer.cost_spike(factor=2.0, severity=Severity.warn)],
    judge=Definition.from_package("observers/quality"),
)
await watch.run(surface)
```

### 3. Watch the dashboard

```bash
craw visualize
# dashboard on http://127.0.0.1:7878
```

Open `http://127.0.0.1:7878`. You see `crawfish/triage-bot` under Running pipelines, each
08:00 cycle under Recent runs, the day's spend under $ today, and any `cost.spike` or
`quality.flag` events the observer emitted.

!!! warning "The dashboard is loopback only"
    `craw visualize` binds `127.0.0.1`, so nothing off the machine can reach it. Do not
    expose it on a public interface. The surface it serves is not built to be reachable
    from the network.

### 4. Manage it

```bash
craw manage
# NAME                  STATUS   UPTIME    LAST RUN     NEXT FIRE   $ TODAY
# crawfish/triage-bot   running  06:14:02  08:00 (ok)   08:00       $0.42

craw manage logs    crawfish/triage-bot      # tail cycles + observer events
craw manage restart crawfish/triage-bot      # pick up a changed schedule
craw manage stop    crawfish/triage-bot      # clean shutdown
```

That is the full loop: deploy to keep it running, observe to know when it misbehaves,
visualize to see it, manage to control it.

## Where each command finds your components

Each command discovers components through the project layout: `definitions/`,
`pipelines/`, `observers/`, and the generated `.crawfish/` (registry and ledger). If
deploy or an observer cannot find a pipeline, run [`craw doctor`](project-structure.md). It
checks the structure and the split between what you authored and what Crawfish generated.

## How the layer handles secrets and run data

The whole layer holds one rule: operate without leaking secrets, and never let run data
become instructions. In practice:

- Scrubbed observer events and run-info, written through `ScrubbingStore`. No secret value
  reaches an event, the dashboard, or a log.
- Loopback-only dashboard. `craw visualize` binds `127.0.0.1`, so nothing off the machine
  can reach it.
- No-secret detached processes. The deploy supervisor keeps secrets by reference. No
  credential lands in the command line, the session name, the environment, the registry,
  or logs.
- Cost-capped LLM observers. A Definition-backed judge runs under the same `CostBudget`
  and `CostMeter` and the same prompt-injection boundary as any run, and its spend is
  metered. There is no unbounded background LLM cost.
- Tenancy everywhere. Every registry, ledger, and run-info row carries `org_id`.

!!! warning "Secrets stay by reference, run data stays data"
    Two rules hold the layer. Secret values never reach an event, the dashboard, or a log.
    They resolve by reference at the egress boundary. And untrusted (*fluid*) run data
    reaches an LLM observer as data, never as instructions. Do not route a secret or a
    fluid value around either path.

See [SECURITY.md](../architecture/SECURITY.md#the-operate-and-observe-layer) for the canonical
statement.

## Next steps

- [Deploy a pipeline](deploy.md) detaches a supervisor on a cron schedule or continuously.
- [Observe a running pipeline](observers.md) polls the event stream and raises alerts.
- [Visualize runs](visualize.md) is the loopback-only dashboard over the run-info surface.
- [Manage deployed pipelines](manage.md) lists, stops, restarts, and tails by name.
