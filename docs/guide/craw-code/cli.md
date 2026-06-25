# The craw code CLI

The CLI is the one execution path for `craw code`. Every action an agent or a human takes —
scaffolding a component, reflecting its types, pricing a run, deploying it, approving a change
— is a `craw code` verb. Each verb reads the project at the moment you invoke it (so it is
never stale), takes `--json` to emit a versioned, snapshot-tested envelope, and returns a
small, closed set of exit codes. This page is the map of that surface.

!!! note "You will learn:"
    - Every `craw code` verb, what it does, and its key flags
    - The `--json` envelope and the `craw.error.v1` error contract
    - The closed exit-code table, and the granular codes carried in `detail.exit`
    - How schema-version negotiation keeps an old parser from crashing on new output

## The verbs

The thirteen verbs below ship today. The nine [operate and HITL verbs](operate.md) —
`optimize`, `deploy`, `fleet`, `cancel`, `resume`, `propose`, `apply`, `review`, `diagnose` —
are documented on the [operate](operate.md) and [review](review-and-approve.md) pages; they
are part of the operate/HITL plane and may not all be registered in your build yet.

Every verb accepts `--json` (emit the versioned `craw.<cmd>.v1` envelope) and `--org ORG`
(thread a tenancy `org_id` through every Store read and write). Those two are omitted from the
"key flags" column below.

| Verb | What it does | Key flags | `--json` schema | Exit codes |
| --- | --- | --- | --- | --- |
| `init [dir]` | Scaffold the seven folders + `crawfish.toml`, install the plugin, start the ledger. Idempotent (reconcile, never clobber). | `--name`, `--no-plugin`, `--upgrade` | `craw.code.init.v1` | `0`, `2`, `4` |
| `new <kind> <name>` | Author a component from a template into its canonical folder; post-write secret-shape lint. | `--dir`, `--force` | `craw.code.new.v1` | `0`, `4` |
| `describe <component>` | Compile (jailed if agent-authored) and project typed inputs/outputs + capability *kind* only. | — | `craw.code.describe.v1` | `0`, `2`, `4` |
| `estimate <component>` | Cost preview via `estimate_cost` — no model call; honest band; threads the project budget ceiling. | `--items` | `craw.code.estimate.v1` | `0`, `3` |
| `sync` | Reconcile the tree with discovery + doctor, then run the assembly gate as a precondition. | `--dir` | `craw.code.sync.v1` | `0`, `2`, `4` |
| `map` | Emit the project's component/wiring graph: flow-tagged IO, topology, consequential sinks (kind only), lineage. | `--dir`, `--format {json,dot}` | `craw.code.map.v1` | `0`, `2`, `4` |
| `lint` | The standalone secret-shaped scan (fail closed). | `--dir` | `craw.code.lint.v1` | `0`, `4` |
| `schema` | Dump the `{command: "major.minor"}` version map for plugin/CLI compatibility. | — | `craw.code.schema.v1` | `0` |
| `grant <component>` | Human consent re-entry for an agent-added MCP/secret capability (references only, never a value). | `--yes` | `craw.code.grant.v1` | `0`, `1`, `4` |
| `explain [topic]` | Print a shipped doc for a topic — no model call. | — | `craw.code.explain.v1` | `0`, `4` |
| `adopt [dir]` | Bring an existing project into the loop; composes `craw export --claude-code`. | `--no-export` | `craw.code.adopt.v1` | `0`, `2`, `4` |
| `dashboard` | Serve the loopback fleet view over the ledger (binds `127.0.0.1` only). | `--port`, `--project`, `--open` | `craw.code.dashboard.v1` | `0`, `2` |
| `validate-authoring` | Validate the authoring playbook against the golden + red-team corpus. | `--spec`, `--repo-root` | `craw.code.validate.v1` | `0`, `1` |

To see the live version map for your build:

```bash
craw code schema --json
```

```json
{
  "schema": "craw.code.schema.v1",
  "schema_version": {"major": 1, "minor": 0},
  "versions": {
    "code.describe": "1.0", "code.estimate": "1.0", "code.init": "1.0",
    "code.map": "1.0", "code.new": "1.0", "error": "1.0"
  }
}
```

## The `--json` envelope

Every `--json` payload is emitted through a single encoder with `sort_keys=True`, so the
output is byte-stable and snapshot-testable. Each envelope carries its `schema` tag, a
`schema_version`, and the `org` it ran under:

```json
{
  "schema": "craw.code.estimate.v1",
  "schema_version": {"major": 1, "minor": 0},
  "org": "local",
  "items": 5,
  "total_usd": 4.5,
  "within_budget": true
}
```

The cost band uses the source-of-truth field names from `crawfish/cost.py`: `total_usd` is the
**lower bound**, `worst_case_usd` the upper bound, and `expected_usd` a measured-rate band
between them (it equals `worst_case_usd` until measured rates are supplied, so the band never
undercounts).

## The error contract

In `--json` mode, errors are emitted on **stderr** as a `craw.error.v1` envelope rather than a
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

`code` is a closed enum: `usage`, `not_found`, `compile_error`, `jail_violation`,
`budget_exceeded`, `schema_skew`, `fluid_to_static_sink`, `signing_required`,
`consent_required`, `tree_busy`, `internal`.

!!! warning "Security rejections are non-retryable"
    Every security rejection — `jail_violation`, `fluid_to_static_sink`, `signing_required`,
    `consent_required`, `schema_skew` — carries `retryable: false`. An injected agent must not
    be able to retry its way past a gate. The `remediation` string is static-only; tainted
    input never round-trips back into it.

## Exit codes

The top-level exit code is a closed 0–4 table. Verbs that need finer distinctions carry a
granular code in `detail.exit` of the envelope, but the process exit stays inside this table:

| Code | Name | Meaning |
| --- | --- | --- |
| `0` | ok | Success. |
| `1` | expected_failure | A regression gate tripped, consent was declined, or a goal was not met. |
| `2` | usage | Usage or compile error — bad args, a `DefinitionLoadError`, a jail `Denial` at parse. |
| `3` | budget_exceeded | A `--budget` or project `[budget]` ceiling halted the run. |
| `4` | security_rejection | Assembly gate, fluid→static-sink, or a signing/consent requirement — non-retryable. |

The granular `detail.exit` codes extend this for verb-specific outcomes: `5` (exists /
no-baseline), `6` (lint failed / cancel raced), `7` (assembly-gate rejected / no approval),
`8` (tree busy / ceiling reached), `9` (not a project).

## Schema negotiation

Each command carries its own `schema_major.schema_minor`. A **major** bump is breaking; a
**minor** bump is additive — old parsers ignore the new fields. If a plugin built against an
older major calls a newer CLI, the mismatch surfaces as a structured `schema_skew` error (exit
`4`, `retryable: false`) rather than a silent misparse. A parser should read `schema_version`
first and bail cleanly on a major mismatch; the full negotiation map lives in the
[JSON contracts reference](../../reference/craw-code-json-contracts.md).

## See also

- [Operate & optimize](operate.md) — the run/deploy/optimize verbs
- [Review & approve (HITL)](review-and-approve.md) — the propose → approve → apply gate
- [craw code JSON contracts](../../reference/craw-code-json-contracts.md) — the error schema, version map, and exit codes, exhaustively
- [Security model](security.md) — why each rejection is non-retryable
