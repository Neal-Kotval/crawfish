# Visualize runs on a localhost dashboard

`craw visualize` serves a dashboard over the run-info surface: running pipelines, recent
runs and their status, what you have spent today, and observer events. It is plain HTML and
JavaScript, with no build step and no framework, and it binds to loopback only, so only
your machine can reach it.

## Run the command

```bash
craw visualize [--port <port>]
# dashboard on http://127.0.0.1:7878  (loopback only)
```

The server binds `127.0.0.1` only, so no other host can reach it. The default port is
`7878`. Open the URL in a browser. The page reads the same Store-backed run-info surface
that [observers](observers.md) write and [`craw manage`](manage.md) queries, so it shows
deployed pipelines live.

!!! warning "Loopback only, by design"
    The dashboard binds `127.0.0.1`, never `0.0.0.0`. There is no auth layer because there
    is no network surface to authenticate. Do not put it behind a reverse proxy to expose
    it off the machine. That breaks the security model.

## What the dashboard shows

- Running pipelines: name, status, uptime, next fire (from the deploy registry).
- Recent runs: per-run status, backend, version, cost, item count (from `RunInfo`).
- $ today: spend rolled up from the cost meter.
- Observer events: the `ObserverEvent` stream, newest first, with severity.

The dashboard is a read-only mirror. It never triggers a run or changes state. The page
renders the scrubbed run-info surface, so no secret value reaches the UI. For control
actions like deploy, stop, and restart, use [`craw manage`](manage.md).

## Open the dashboard for the triage bot

With the triage bot [deployed](deploy.md) and an [observer](observers.md) attached:

```bash
craw deploy demo/triage-bot --schedule "0 8 * * *"
craw visualize
# dashboard on http://127.0.0.1:7878
```

Open `http://127.0.0.1:7878`. You see `crawfish/triage-bot` under Running pipelines. Each
08:00 cycle shows up under Recent runs as it completes, the running $ today total updates,
and any `cost.spike` or `quality.flag` events the observer emitted land in the Observer
events panel.

To free the default port, or to run two dashboards at once, pick another:

```bash
craw visualize --port 9000
# dashboard on http://127.0.0.1:9000
```

## Why the dashboard is safe

The dashboard is small and closed by design.

- Loopback only. It binds `127.0.0.1`, so nothing off the machine can reach it. There is no
  auth layer because there is no network surface to authenticate.
- Scrubbed surface only. It renders the same scrubbed run-info surface as the rest of the
  observe layer. Events and run-info are scrubbed before the Store write, so no secret
  value can appear in the UI.
- Read-only. It has no control actions. Deploy, stop, and restart live in
  [`craw manage`](manage.md).

## Next steps

- [Observe a running pipeline](observers.md) emits the events the dashboard shows.
- [Manage deployed pipelines](manage.md) covers control actions and CLI queries.
- [Deploy a pipeline](deploy.md) schedules the pipelines you watch here.
- [SECURITY.md](../architecture/SECURITY.md) covers the full security spine.
