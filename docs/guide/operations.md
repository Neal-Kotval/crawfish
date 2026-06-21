# Operate and observe

The operate layer keeps a working pipeline running. Where `craw dev` runs it once against
the mock, you now deploy it as an always-on background process (a *supervisor*), watch it
with observers, see it on a localhost dashboard, and control it from one CLI.

Four commands share one Store-backed spine:

| Stage     | Command / API                       | Role |
| --------- | ----------------------------------- | ---- |
| **deploy**    | [`craw deploy`](deploy.md)      | detach a supervisor; fire on a cron or continuously; auto-restart; resume orphans |
| **observe**   | [`crawfish.observe`](observers.md) | poll the event stream; emit `ObserverEvent`s on failure/cost/latency or an LLM judge |
| **visualize** | [`craw visualize`](visualize.md) | loopback-only dashboard over the run-info surface |
| **manage**    | [`craw manage`](manage.md)      | list/stop/restart/logs from the registry + ledger + cost meter |

They share one place to read and write status: the **run-info surface**
(`ObserverSurface`, backed by the `Store`). Each cycle the supervisor writes a `RunInfo`
record, observers emit `ObserverEvent`s, and the dashboard and `craw manage` read both.
Everything is scrubbed (secret values stripped) before the Store write and scoped by
`org_id`. So an alert an observer raises shows up in the dashboard and in
`craw manage logs` at once, with no secret value anywhere in the path.

## End-to-end walkthrough: the triage bot, always on

This takes `demo/triage-bot` from a one-shot run to a supervised, observed, dashboarded
pipeline.

### 1. Deploy it

```bash
craw deploy demo/triage-bot --schedule "0 8 * * *"
# deployed: crawfish/triage-bot (schedule: 0 8 * * *) — supervisor pid 48213
```

The supervisor detaches, registers in the deploy registry, and fires at 08:00 daily. It
survives the shell closing. If it crashes mid-cycle, it resumes from the execution
ledger.

### 2. Add an observer

Attach a watcher that warns on cost spikes and runs a quality judge. Both run under the
normal cost cap and the prompt-injection boundary (untrusted run data reaches the model
as data, never as instructions):

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

Open `http://127.0.0.1:7878`. You'll see `crawfish/triage-bot` under **Running
pipelines**, each 08:00 cycle under **Recent runs**, the day's **$ today**, and any
`cost.spike` or `quality.flag` events the observer emitted.

!!! warning "The dashboard is loopback-only"
    `craw visualize` binds `127.0.0.1`, so nothing off the machine can reach it. Don't
    try to expose it on a public interface — the surface it serves isn't built to be
    reachable from the network.

### 4. Manage it

```bash
craw manage
# NAME                  STATUS   UPTIME    LAST RUN     NEXT FIRE   $ TODAY
# crawfish/triage-bot   running  06:14:02  08:00 (ok)   08:00       $0.42

craw manage logs    crawfish/triage-bot      # tail cycles + observer events
craw manage restart crawfish/triage-bot      # pick up a changed schedule
craw manage stop    crawfish/triage-bot      # clean shutdown
```

That's the full loop: **deploy** to keep it running, **observe** to know when it
misbehaves, **visualize** to see it, **manage** to control it.

## Where structure fits

Each of these commands finds components through the project layout: `definitions/`,
`pipelines/`, `observers/`, and the generated `.crawfish/` (registry + ledger). If
deploy or an observer can't find a pipeline, run [`craw doctor`](project-structure.md).
It checks the structure and the split between what you authored and what Crawfish
generated.

## The operate-layer security spine

The whole layer holds one line: **operate without leaking secrets, and never let run
data become instructions.** In practice:

- **Scrubbed observer events and run-info** — written through `ScrubbingStore`. No secret
  value reaches an event, the dashboard, or a log.
- **Loopback-only dashboard** — `craw visualize` binds `127.0.0.1`, so nothing off the
  machine can reach it.
- **No-secret detached processes** — the deploy supervisor keeps secrets by reference. No
  credential lands in the command line, the session name, the environment, the registry,
  or logs.
- **Cost-capped LLM observers** — a Definition-backed judge runs under the same
  `CostBudget`/`CostMeter` and prompt-injection boundary as any run, and its spend is
  metered. There's no unbounded background LLM cost.
- **Tenancy everywhere** — every registry, ledger, and run-info row carries `org_id`.

!!! warning "Secrets stay by reference, run data stays data"
    Two rules hold the whole layer. Secret values never reach an event, the dashboard, or
    a log — they're resolved by reference at the egress boundary. And untrusted run data
    reaches an LLM observer as data, never as instructions (the prompt-injection
    boundary). Don't route a secret or a fluid value around either path.

See [SECURITY.md](../architecture/SECURITY.md#the-operateobserve-layer) for the
canonical statement.

## Next steps

- [Deploy — always-on pipelines](deploy.md) — detach a supervisor on a cron or
  continuously.
- [Observers](observers.md) — poll the event stream and raise alerts on cost, latency, or
  quality.
- [Visualize](visualize.md) — the loopback-only dashboard over the run-info surface.
- [Manage deployed pipelines](manage.md) — list, stop, restart, and tail by name.
- [Project structure](project-structure.md) — where deploy and observers find your
  components, and `craw doctor`.
