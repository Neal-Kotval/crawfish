# craw code JSON contracts

Look-up page for the machine surface of `craw code`: the `craw.error.v1` error envelope, the
`--json` schema-version negotiation, and the exit-code tables. Every `craw code` verb takes
`--json` and emits a versioned, sort-keyed envelope; this page documents the shared contracts
those envelopes obey. For the task-level walk-through, see [the CLI guide](../guide/craw-code/cli.md).

## The success envelope

Every `--json` payload is emitted through a single encoder with `sort_keys=True`. Each carries
its `schema` tag, a `schema_version`, and the `org` it ran under:

```json
{
  "schema": "craw.code.estimate.v1",
  "schema_version": {"major": 1, "minor": 0},
  "org": "local",
  "items": 5,
  "total_usd": 4.5,
  "expected_usd": 4.5,
  "worst_case_usd": 4.5,
  "within_budget": true
}
```

The cost fields follow `crawfish/cost.py`: `total_usd` is the **lower bound**, `worst_case_usd`
the **upper bound**, and `expected_usd` a measured-rate band between them that equals
`worst_case_usd` until measured rates are supplied (so the band never undercounts).

## The `craw.error.v1` envelope

In `--json` mode, errors are emitted on **stderr** as a structured envelope, never a
parse-breaking stack trace:

```json
{
  "schema": "craw.error.v1",
  "schema_version": {"major": 1, "minor": 0},
  "code": "fluid_to_static_sink",
  "retryable": false,
  "detail": {"component": "pipelines/triage", "slot": "sink.target"},
  "remediation": "A sink target is static-only; bind it from static config, not a fluid input."
}
```

| Field | Type | Notes |
| --- | --- | --- |
| `schema` | `str` | Always `"craw.error.v1"`. |
| `schema_version` | `{major, minor}` | The error-envelope version. |
| `code` | `str` (closed enum) | The error class — see the table below. |
| `retryable` | `bool` | `false` for every security rejection. An injected agent must not retry past a gate. |
| `detail` | `object` | Structured context (component, slot, and the granular `exit` code). |
| `remediation` | `str` | A **static-only** human-readable fix. Tainted input never round-trips into it. |

### The `code` enum

| `code` | `retryable` | Meaning |
| --- | --- | --- |
| `usage` | `true` | Bad arguments. |
| `not_found` | `true` | The named component or run does not exist. |
| `compile_error` | `true` | A `DefinitionLoadError` outside the jail path. |
| `jail_violation` | **`false`** | A `Denial` inside the jailed compile. Security rejection. |
| `budget_exceeded` | `true` | A `--budget` or project `[budget]` ceiling halted the run. |
| `schema_skew` | **`false`** | A major `--json` schema mismatch between caller and CLI. Security rejection. |
| `fluid_to_static_sink` | **`false`** | A fluid value reached a static sink target or idempotency key. Security rejection. |
| `signing_required` | **`false`** | A recorded artifact must be signed to fire. Security rejection. |
| `consent_required` | **`false`** | A declared capability needs `craw code grant`. Security rejection. |
| `tree_busy` | `true` | The project tree is locked by another writer. |
| `internal` | `true` | An unexpected internal error. |

!!! warning "Security rejections are non-retryable by contract"
    `jail_violation`, `fluid_to_static_sink`, `signing_required`, `consent_required`, and
    `schema_skew` all carry `retryable: false`. A consumer (human or agent) must treat these as
    terminal — there is no input that retries past them. Note `plugin_skew` is a *recoverable*
    compatibility finding (exit `1`, `retryable: true`), not a security rejection.

## Schema-version negotiation

Each command declares its own `schema_major.schema_minor`. A **major** bump is breaking; a
**minor** bump is additive (old parsers ignore the new fields). The full map is dumped by
`craw code schema --json`:

```json
{
  "schema": "craw.code.schema.v1",
  "schema_version": {"major": 1, "minor": 0},
  "versions": {
    "code.adopt": "1.0",
    "code.cost": "1.0",
    "code.dashboard": "1.0",
    "code.dashboard.optimize": "1.0",
    "code.dashboard.runs": "1.0",
    "code.describe": "1.0",
    "code.estimate": "1.0",
    "code.explain": "1.0",
    "code.grant": "1.0",
    "code.init": "1.0",
    "code.lint": "1.0",
    "code.map": "1.0",
    "code.new": "1.0",
    "code.provenance": "1.0",
    "code.run": "1.0",
    "code.schema": "1.0",
    "code.sync": "1.0",
    "code.validate": "1.0",
    "error": "1.0"
  }
}
```

A consumer should read `schema_version` first and bail cleanly on a **major** mismatch — at
which point the CLI emits a `schema_skew` error (exit `4`, non-retryable) rather than letting an
old parser misread a new payload.

## Exit codes

The process exit code is a closed 0–4 table. Verbs that need finer outcomes carry a granular
code in `detail.exit`, but the process exit stays inside this table.

| Code | Name | Meaning |
| --- | --- | --- |
| `0` | ok | Success. |
| `1` | expected_failure | A regression gate tripped, consent declined, or a goal not met. |
| `2` | usage | Usage or compile error — bad args, `DefinitionLoadError`, jail `Denial` at parse. |
| `3` | budget_exceeded | A `--budget` or project `[budget]` ceiling halted the run. |
| `4` | security_rejection | Assembly gate, fluid→static-sink, or signing/consent required — non-retryable. |

### Granular `detail.exit` codes

Verb-specific outcomes extend the table above through `detail.exit`:

| `detail.exit` | Used by | Meaning |
| --- | --- | --- |
| `5` | `new`, `optimize` | Path exists / no baseline to optimize against. |
| `6` | `lint`, `new`, `cancel` | Secret-shaped lint failed / cancel raced a finished run. |
| `7` | `sync`, `apply` | Assembly gate rejected / no recorded approval. |
| `8` | `sync`, `apply` | Tree busy / approval ceiling reached. |
| `9` | `adopt` | Not a Crawfish project. |

## See also

- [The craw code CLI](../guide/craw-code/cli.md) — the task-level guide to these contracts
- [craw code provenance](craw-code-provenance.md) — the provenance record and jailed-compile surface
- [Security model](../guide/craw-code/security.md) — why each security rejection is non-retryable
