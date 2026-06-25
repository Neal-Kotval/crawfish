# ADR 0014 — Store schema: versioned migrate-on-open

**Status:** Accepted · **Date:** 2026-06-21 · **Milestone:** Phase 2

*(ADR 0013 is the emission/output decision; ADR 0011 is reserved for the ruvLLM/rvagent
adopt-vs-build spike.)*

## Context

`SqliteStore` built its tables with `CREATE TABLE IF NOT EXISTS` and never migrated. That
was fine while the schema was frozen, but Phase 2 adds new persisted shapes (typed
outputs, the emission ledger, learning-agent lineage). An older `.crawfish` database on a
user's disk must upgrade cleanly when a newer Crawfish opens it — and, symmetrically, an
old binary must *not* silently run against a database written by a newer one.

All persistence goes through the `Store` protocol (`store/base.py`), and no raw SQL
appears at any call site. Whatever we add has to live entirely inside the SQLite impl, and
must not change the protocol or any frozen contract (Emission/Output/Provider).

## Decision

Track the schema version in SQLite's built-in **`PRAGMA user_version`** (an atomic integer
in the database header — no bookkeeping table) and **migrate on open** via an ordered list
of forward migrations in `crawfish.store.migrations`.

- `Migration` is a frozen dataclass: `version: int`, `description: str`, and an
  `apply(conn) -> None` callable. `MIGRATIONS` is ordered by ascending `version`;
  `CURRENT_SCHEMA_VERSION` equals the highest.
- **Migration 1 is the baseline** — byte-for-byte the original `_SCHEMA`, idempotent
  `CREATE TABLE IF NOT EXISTS`. A brand-new DB (`user_version=0`) and an existing
  pre-versioning DB (tables already present, `user_version=0`, because SQLite never set it)
  therefore converge: migration 1 creates tables on the fresh DB and is a no-op on the
  pre-versioning one.
- **Migration 2** (shipped with this ADR) adds an index on `events(org_id, run_id)`, the
  pair both `append_event` and `events` scan by — a real forward step that exercises the
  mechanism end to end.
- `SqliteStore.__init__` calls `apply_migrations` under its lock after connecting: read
  `user_version`; if it **exceeds** `CURRENT_SCHEMA_VERSION` raise `StoreMigrationError`
  (refuse the **downgrade**); otherwise apply each migration with `version > user_version`
  in order, each in its own transaction, then stamp `user_version`. Idempotent: a
  fully-migrated DB applies nothing. WAL/synchronous pragmas are unchanged.
- **Read-path up-conversion.** `RECORD_UPCONVERTERS: dict[str, Callable[[dict], dict]]`,
  keyed by record `kind`, is applied in `get_record` / `list_records` (identity when no
  converter is registered). This generalizes CRA-171's `Emission.from_event` shim from
  events to records: a migration fixes the *table*; an up-converter lifts a *row's* JSON
  envelope to the current shape lazily on read, so historical rows stay readable without a
  bulk rewrite. A new record kind ships its up-converter alongside its migration.

**Concurrency.** Migrations run under the existing store lock plus SQLite's file lock; a
second opener on the same file observes the bumped `user_version` and applies nothing.

**Scope.** This is the migration *mechanism* only. Emission retention/rotation and wiring
`max_per_run` were loosely routed here but are a separate concern; they are a documented
follow-up, kept out to keep this reviewable.

## Alternatives rejected

- **No versioning (keep `CREATE TABLE IF NOT EXISTS` only).** Cannot add columns/indexes
  or evolve shapes; provides no downgrade guard; the status quo this ADR replaces.
- **Destructive recreate (drop + rebuild on shape change).** Trivially "migrates" but
  destroys user data — unacceptable for a local-first store that holds run history.
- **An external migration tool (Alembic / sqlite-utils).** A heavy dependency and a second
  source of truth for a single-file embedded DB. `user_version` is built in, atomic, and
  zero-dependency; the ordered Python list keeps migrations co-located with the schema.
- **A bespoke `schema_migrations` table.** More moving parts than the header integer
  SQLite already maintains, with no added capability at our scale.

## Consequences

Schema evolution is now a routine, reviewable change: append a `Migration`, bump
`CURRENT_SCHEMA_VERSION`, and (if a record kind's envelope changed) register an
up-converter. Old databases upgrade on open; newer databases are refused by old binaries
instead of being silently corrupted. The cost is the discipline of the authoring contract
— additive, idempotent migration bodies and a per-kind up-converter for legacy rows —
documented in `store/migrations.py` and ARCHITECTURE.md.
