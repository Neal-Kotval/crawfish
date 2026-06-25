# ADR 0003 — SQLite (WAL) reference Store with tenancy + transactional idempotency

**Status:** Accepted · **Date:** 2026-06-19 · **Milestone:** M0

## Context

A 10k-item fan-out writes telemetry, outputs, and idempotency claims concurrently. The
local default must survive that without lock contention or idempotency races, and must
not bake in single-tenant assumptions that force a schema migration for cloud.

## Decision

The reference `Store` is SQLite with:

- **WAL mode** + a process `RLock` so concurrent readers don't block the writer.
- **Transactional idempotency**: claim is a single `INSERT OR IGNORE`; the winner is
  the row that inserted (`rowcount == 1`). Check-then-write cannot race.
- **Tenancy key on every row** (`org_id`, defaulted `"local"`), part of every primary
  key, so multi-tenancy is a driver swap, not a migration.
- An **append-only event ledger** (`events` table, monotonic `seq` per run) — the basis
  for telemetry and the execution-state ledger.

## Alternatives rejected

- **JSON files on disk** — no transactions, no concurrent-safe idempotency.
- **Require Postgres locally** — breaks the zero-dependency `pip install` + `claude -p`
  promise.
- **Add `org_id` later** — a retrofit is a breaking schema migration across every table.

## Consequences

Postgres becomes a parallel `Store` impl with the same protocol. The WAL file appears
under the project's `.crawfish/` (gitignored). In-memory (`:memory:`) is used for tests.
