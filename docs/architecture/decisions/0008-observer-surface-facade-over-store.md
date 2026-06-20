# ADR 0008 — Observer/run-info surface as a facade over the Store, not new protocol methods

**Status:** Accepted · **Date:** 2026-06-19 · **Milestone:** Phase 1 Hardening

## Context

The operate/observe layer needs a queryable place for **observer events** and **per-run info** to land,
read by `craw visualize`, `craw manage`, and alerting. The worked example shows
`ctx.emit(ObserverEvent(...))` and `store.run_info("triage-bot", since="-1h")`. The
obvious reading — add `emit` / `run_info` / `observer_events` methods to the `Store`
**protocol** — would force every future backend (Postgres, cloud) to grow and keep
those methods in lockstep, and would put more bespoke SQL behind the seam.

Two constraints pull against that: the architecture rule that persistence goes through
the `Store` seam with **no new SQL outside a Store impl**, and the security rule that
observer events are **scrubbed before the write** by reusing `ScrubbingStore`.

## Decision

Persist the surface through the **existing** `Store` primitives and expose it as a thin
**`ObserverSurface` facade**, not as new protocol methods:

- **Observer events** ride the append-only event ledger under a synthetic stream id
  `observer:<pipeline>`, reusing `Store.append_event` / `Store.events` (already
  ordered, poll-friendly, tenant-scoped).
- **RunInfo** is a `run_info` record keyed by `run_id`, via `put_record` /
  `list_records` (full-record upsert).
- `ObserverSurface(store, org_id=…)` provides `emit` / `events` / `put_run_info` /
  `run_info`, filtering by pipeline / time-window / kind in Python over the scrubbed
  rows. `RunContext.emit(event)` is the one-liner that routes through the run's store.

Because writes go through whatever `Store` the surface wraps, handing it a
`ScrubbingStore` redacts secrets/PII automatically — scrubbing is reused, not
reimplemented, and is impossible to forget on a new event type.

## Alternatives rejected

- **New `Store` protocol methods** (`emit`, `run_info`, `observer_events`) — bloats the
  seam, adds SQL to every backend, and re-implements time/kind filtering per driver.
- **A separate observer database/file** — a second persistence path outside the seam,
  breaking tenancy + the single-scrubbing-point guarantee.

## Consequences

Adding the surface required **zero schema or protocol change**; Postgres/cloud get it
for free the day they implement the existing protocol. Time-window queries filter in
Python (fine at local-dev scale; a future indexed `observer_events` table is a Store-impl
optimization, not an API change). `store.run_info(...)` from the issue example is
realized as `ObserverSurface(store).run_info(...)` — the documented stable API.
