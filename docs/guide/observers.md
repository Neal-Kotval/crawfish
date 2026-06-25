# Observe a running pipeline

An *observer* watches a running pipeline and raises an alert when something looks wrong. It
polls the pipeline's event stream on a cron interval and emits an `ObserverEvent` on a
failure-rate spike, a cost spike, or a stuck or slow run. Add an LLM judge and it also
flags low-quality results, described in plain language. Observers write to the same
scrubbed run-info surface that the [dashboard](visualize.md) and [`craw manage`](manage.md)
read, so an alert shows up in every view at once.

Observers live in `crawfish.observe`, alongside the run-info surface described below.

## Read and write the run-info surface

Nodes, observers, and the deploy supervisor record what happened through `ObserverSurface`,
a Store-backed handle:

```python
from crawfish.observe import ObserverSurface, ObserverEvent, RunInfo, Severity

surface = ObserverSurface(store, org_id="local")

# emit an event (nodes call ctx.emit(...) with the same payload)
surface.emit(ObserverEvent(
    pipeline="triage-bot",
    kind="cost.spike",
    detail="run cost $0.31 > 2x median",
    severity=Severity.warn,
    observer="cost-watch",
    run_id="01HZ…",
))

# record a per-run rollup
surface.put_run_info(RunInfo(
    pipeline="triage-bot",
    run_id="01HZ…",
    status="ok",
    backend="command",
    version="0.3.1",
    cost_usd=0.31,
    items=3,
))

# read back
events = surface.events("triage-bot", since="-1h", kind="cost.spike")
runs   = surface.run_info("triage-bot", since="-1d")
```

The three types you write and read:

| Type            | Fields |
| --------------- | ------ |
| `ObserverEvent` | `pipeline, kind, detail, severity, observer, run_id, ts, data` |
| `RunInfo`       | `pipeline, run_id, status, backend, version, cost_usd, items, started_at, finished_at` |
| `Severity`      | `info` · `warn` · `critical` |

Every event and run-info row carries `org_id` (defaulted `"local"`) and is scrubbed before
the Store write. The surface wraps `ScrubbingStore`, so no secret value reaches an event,
the dashboard, or a log.

`since=` takes a relative window (`"-1h"`, `"-30m"`, `"-15s"`, `"-2d"`) or an epoch
timestamp. Inside a node or observer, you emit through the run context:

```python
ctx.emit(ObserverEvent(pipeline="triage-bot", kind="item.dropped",
                       detail="missing ticket_body", severity=Severity.info))
```

## Define an observer

An observer has two parts: rules and an optional judge. It polls a pipeline's event stream
on a cron interval and applies the rules. There are two kinds of check:

- Rule-based checks are pure and free: failure rate over a window, cost spike against the
  median, and latency or stuck-run detection.
- An LLM judge is optional. A Definition reads recent run data and flags low-quality runs
  in plain language.

```python
from crawfish.observe import Observer, Severity
from crawfish import Definition

watch = Observer(
    pipeline="triage-bot",
    interval="*/5 * * * *",                 # poll every 5 minutes
    rules=[
        Observer.failure_rate(threshold=0.2, window="-15m", severity=Severity.warn),
        Observer.cost_spike(factor=2.0, severity=Severity.warn),
        Observer.stuck(after="-10m", severity=Severity.critical),
    ],
    judge=Definition.from_package("observers/quality"),   # optional language judge
)
```

When a rule trips, the observer emits an `ObserverEvent` onto the same surface. From there,
`craw manage logs`, the dashboard, and any downstream alert sink pick it up.

## Guard the deployed triage bot

Deploy the pipeline, then attach an observer that warns on cost spikes and runs a quality
judge:

```bash
craw deploy demo/triage-bot --schedule "0 8 * * *"
```

```python
from crawfish.observe import Observer, ObserverSurface, Severity
from crawfish import Definition, SqliteStore

surface = ObserverSurface(SqliteStore(), org_id="local")

watch = Observer(
    pipeline="triage-bot",
    interval="*/5 * * * *",
    rules=[
        Observer.cost_spike(factor=2.0, severity=Severity.warn),
        Observer.failure_rate(threshold=0.25, window="-30m", severity=Severity.critical),
    ],
    judge=Definition.from_package("observers/quality"),
)
await watch.run(surface)                    # polls; emits events as rules trip
```

Watch the events arrive:

```bash
craw manage logs crawfish/triage-bot
# 08:00:05  observer cost.spike     severity=warn      detail="run cost $0.31 > 2x median"
# 08:05:00  observer quality.flag   severity=warn      detail="summary omits the root cause"
```

Or query them directly:

```python
events = surface.events("triage-bot", since="-1h", kind="quality.flag")
```

## How an LLM judge stays safe

An LLM judge runs under the same boundary as any Definition.

!!! warning "The judge reads untrusted data"
    Run data the judge reads is *fluid* (untrusted) data. It reaches the model inside a
    labelled data block, never as instructions. A malicious ticket body that surfaces in a
    run cannot turn the observer into an attacker's agent.

- Cost-capped and metered. The judge spends under the same `CostBudget` and `CostMeter` as
  a normal run. Its spend is metered and shows up in `$ today`. There is no unbounded
  background LLM cost.
- Scrubbed surface and tenancy. Events and run-info are scrubbed before the Store write.
  The surface wraps `ScrubbingStore`, and every row carries `org_id`. No secret value
  reaches an event, the dashboard, or a log.

## Next steps

- [Visualize runs](visualize.md) shows observer events in the localhost dashboard.
- [Manage deployed pipelines](manage.md) queries the same events from the CLI.
- [Run a pipeline in the background](operations.md) shows how observe fits the deploy loop.
- [SECURITY.md](../architecture/SECURITY.md) covers the fluid-data boundary in full.
