# API reference

> Auto-generated from `crawfish.__all__` by `docs/guide/gen_api_reference.py`.
> Do not edit by hand — regenerate on each release:
> `uv run python docs/guide/gen_api_reference.py > docs/guide/api-reference.md`.

`crawfish` version: `0.1.0` — 195 public symbols.

Everything documented here is importable directly from the top-level package:

```python
from crawfish import Definition, Batch, MockRuntime  # etc.
```

## Symbols

| Symbol | Kind | Summary |
| --- | --- | --- |
| `JSONValue` | class | Special type indicating an unconstrained type. |
| `new_id` | function | A fresh opaque identifier for any framework object. |
| `Flow` | enum | Whether a parameter is set once per batch or varies per item. |
| `Parameter` | class | A typed parameter on an input/output boundary. |
| `NodeKind` | enum | str(object='') -> str |
| `Node` | class | Anything that can sit in a pipeline. |
| `PolicyKind` | enum | str(object='') -> str |
| `Policy` | class | Importable rule bundle: guardrails, model-routing, permissions. |
| `parameters_compatible` | function | True if an output ``out`` can wire into an input ``in_``. |
| `RunContext` | class | Per-run execution context handed to every node. |
| `CostBudget` | class | A token/dollar ceiling the orchestrator can hard-kill on. |
| `CancelToken` | class | Cooperative cancellation. Long loops call :meth:`raise_if_cancelled`. |
| `BudgetExceeded` | class | Raised when a run would exceed its cost ceiling. |
| `Cancelled` | class | Raised when a cancelled run cooperatively checks in. |
| `TypeDef` | class | A resolved type. Built by the registry; not authored directly. |
| `TypeKind` | enum | str(object='') -> str |
| `TypeRegistry` | class | Holds named types and answers structural compatibility. |
| `default_registry` | value | Holds named types and answers structural compatibility. |
| `Version` | class | A semver-ish version with an optional content sha and a frozen flag. |
| `FrozenError` | class | Raised on any attempt to mutate a frozen artifact. |
| `Freezable` | class | Mixin for any customizable artifact carrying a ``version``. |
| `Store` | class | Persistence contract: typed records, KV/memory, idempotency, telemetry. |
| `SqliteStore` | class | A ``Store`` backed by SQLite. Use ``:memory:`` for tests, a path for dev. |
| `Engine` | class | Runs a pipeline of steps under a single :class:`RunContext`. |
| `run_pipeline` | function | Convenience wrapper that builds a default :class:`Engine`. |
| `Output` | class | The unit of data flowing between nodes. Frozen once produced. |
| `output_satisfies_inputs` | function | True if ``output``'s schema can satisfy every *required* downstream input. |
| `check_wire` | function | Raise :class:`WireError` if ``output`` cannot wire into ``inputs``. |
| `WireError` | class | Raised when an upstream Output cannot wire into a downstream node's inputs. |
| `Definition` | class | The rigid, code-first agent-team package, compiled from a directory. |
| `AgentSpec` | class | One agent in a team. ``prompt`` is compiled from its markdown body. |
| `TeamSpec` | class | !!! abstract "Usage Documentation" |
| `Coordination` | enum | str(object='') -> str |
| `Prompt` | class | !!! abstract "Usage Documentation" |
| `DefinitionRef` | class | !!! abstract "Usage Documentation" |
| `DefinitionAssets` | class | !!! abstract "Usage Documentation" |
| `MarketplacePackage` | class | Export shape (stub — full hub package lands with the registry). |
| `MCPConnection` | class | An MCP server connection authored in ``mcp/*.py``. |
| `load_definition` | function |  |
| `DefinitionLoadError` | class | Raised when a directory cannot compile to a valid Definition. |
| `AgentRuntime` | class | Swappable agent-loop backend. |
| `CommandRuntime` | class | Swappable agent-loop backend. |
| `MockRuntime` | class | Swappable agent-loop backend. |
| `ClientRuntime` | class | Swappable agent-loop backend. |
| `ManagedRuntime` | class | Swappable agent-loop backend. |
| `RecordReplayRuntime` | class | Swappable agent-loop backend. |
| `RunRequest` | class | One agent's turn: a compiled Definition + the inputs bound for this run. |
| `RunResult` | class | !!! abstract "Usage Documentation" |
| `RuntimeEvent` | class | !!! abstract "Usage Documentation" |
| `get_runtime` | function | Instantiate the runtime named by a resolved profile. |
| `Source` | class | Pipeline ingress that fetches data and emits a typed Output. |
| `RepoSource` | class | Single source describing one repository (deterministic, network-free). |
| `PullRequestSource` | class | Multi source emitting a list of pull requests (deterministic, network-free). |
| `fan_out` | function | Split a multi-item Output into per-item Outputs that seed N Runs. |
| `Sink` | class | Base class for egress nodes. Subclasses implement :meth:`_write`. |
| `LinearSink` | class | Create a Linear issue/comment. Dry-run by default (network-free). |
| `GitHubPRSink` | class | Open a GitHub pull request. Dry-run by default (network-free). |
| `TargetMustBeStaticError` | class | Raised when a target parameter is ``Flow.FLUID``. |
| `ApprovalRequired` | class | Raised when an ``always_ask`` sink is asked to write without approval. |
| `Filter` | class | A pure, synchronous node that narrows a list Output by a predicate. |
| `title_contains` | function | Keep dict items whose ``"title"`` field contains ``needle``. |
| `field_equals` | function | Keep dict items whose ``field`` equals ``value``. |
| `field_matches` | function | Keep dict items whose ``field`` (as a string) matches ``pattern`` (regex search). |
| `limit` | function | Keep the first ``n`` items (a list slice, not a per-item test). |
| `Memory` | class | A ``Store``-backed KV/dedup handle scoped to ``(namespace, org_id)``. |
| `Run` | class | An agent team performing a single task. |
| `RunStatus` | enum | str(object='') -> str |
| `InputBindingError` | class | Raised when a required input slot is unbound before execution. |
| `RunSuspended` | class | Raised when a Run idles on an approval gate (state persisted, no compute spent). |
| `Batch` | class | A set of Runs executed under one Definition, wired from Sources/Outputs. |
| `Task` | class | !!! abstract "Usage Documentation" |
| `Anomaly` | class | !!! abstract "Usage Documentation" |
| `Aggregator` | class | A fan-in node: consumes a group of N Outputs and emits one Output. |
| `collect` | function | Gather the item values into a list (the identity fan-in). |
| `concat` | function | Concatenate the item values into one string (str-coerced, no separator). |
| `count` | function | Count the items. |
| `dedupe` | function | List the item values with duplicates removed, first-seen order preserved. |
| `definition_reducer` | function | A reducer that runs an agent team to reduce N item values into one. |
| `fan_in` | function | Barrier that waits for N concurrent runs and returns their successful Outputs. |
| `Router` | class | A node that routes an Output down one labelled branch chosen by a Classifier. |
| `Classifier` | class | Produces one typed label for an :class:`Output` from a closed label set. |
| `UnroutableLabelError` | class | Raised at assembly time when a classifier label has no matching branch. |
| `ArtifactRef` | class | A content-addressed pointer to artifact bytes held in an ``ArtifactStore``. |
| `ArtifactStore` | class | Blob persistence contract: content-addressed, tenant-scoped, GC-able. |
| `LocalArtifactStore` | class | An ``ArtifactStore`` backed by the local filesystem, addressed by sha256. |
| `offload_if_large` | function | Offload ``value`` to ``store`` if its JSON form exceeds ``threshold`` bytes. |
| `DependencyGraph` | class | Edges ``(blocker, blocked)``; ``topo_layers`` returns parallelizable layers. |
| `CycleError` | class | Raised when a dependency graph contains a cycle. |
| `Roadmap` | class | !!! abstract "Usage Documentation" |
| `ExecutionPlan` | class | !!! abstract "Usage Documentation" |
| `BatchExecutor` | class | Schedules + runs a Batch. Rule-based; leaves a seam for an agentic executor. |
| `BatchRunResult` | class | BatchRunResult(outputs: 'list[Output[JSONValue]]' = <factory>, items: 'list[ItemResult]' = <factory>, dead_letters: 'list[dict[str, JSONValue]]' = <factory>) |
| `ExecutionLedger` | class | Store-backed execution state for pipelines, runs, and fan-out items. |
| `ObserverEvent` | class | A structured finding emitted by an observer or a node. |
| `ObserverSurface` | class | Read/write facade over the run-info surface, scoped to one tenant. |
| `RunInfo` | class | Per-run summary the dashboard and ``craw manage`` read. |
| `Severity` | enum | How loudly an observer event should be surfaced. |
| `parse_since` | function | Resolve a ``since`` argument to an epoch-seconds threshold. |
| `DeployEntry` | class | A registry row describing one deployed pipeline. |
| `DeployRegistry` | class | Store-backed registry of deployed pipelines (read by deploy/manage/visualize). |
| `DeployStatus` | enum | str(object='') -> str |
| `Supervisor` | class | The always-on loop: schedule → fire → record, with ledger-backed resume. |
| `deploy` | function | Detach the project's pipeline as an always-on supervisor and register it. |
| `stop` | function | Stop a deployed pipeline: signal its process and clear its registry status. |
| `PipelineStatus` | class | A row in ``craw manage``: a deployed pipeline joined with its run state. |
| `manage_list` | function | Build the management view for every deployed pipeline. |
| `format_table` | function | Render the management view as a fixed-width table (``craw manage``). |
| `restart_target` | function | Stop then re-deploy ``name`` with its recorded dir + schedule. Returns success. |
| `Observer` | class | Watch one pipeline: run rules (and an optional LLM judge) on a poll interval. |
| `ObserverContext` | class | The window a rule judges: recent runs + events for one pipeline at ``now``. |
| `Rule` | class | A cheap, deterministic check over recent runs. Returns an event or ``None``. |
| `FailureRateAbove` | class | Fire when the fraction of failed runs in ``window`` exceeds ``threshold``. |
| `CostSpike` | class | Fire when total spend across runs in ``window`` reaches ``usd``. |
| `StuckRun` | class | Fire when a run has been ``running`` for longer than ``seconds``. |
| `dashboard_state` | function | Build the JSON the dashboard renders — pipelines, runs, cost, observer feed. |
| `serve_dashboard` | function | Create a loopback-bound dashboard server (caller runs ``serve_forever``). |
| `ClaudeCodeAgent` | class | A Claude Code subagent: YAML front-matter + a system-prompt body. |
| `ClaudeCodeSkill` | class | A Claude Code skill wrapper — a Definition as an invocable slash-command. |
| `definition_to_cc_agent` | function | Render a Definition into a :class:`ClaudeCodeAgent` (no secrets emitted). |
| `export_claude_code` | function | Write the CC subagent (and optional skill) under ``project_dir/.claude``. |
| `map_tools` | function | The subagent's ``tools`` allowlist: union of agent tools + MCP tool names. |
| `model_alias` | function | Map a Definition's pinned model to a CC alias (``opus``/``sonnet``/``haiku``). |
| `ExecState` | enum | str(object='') -> str |
| `RetryPolicy` | class | Exponential backoff: ``delay = min(base * factor**attempt, max_delay)``. |
| `ItemResult` | class | Partial-success unit surfaced in batch results. |
| `ItemStatus` | enum | str(object='') -> str |
| `Workflow` | class | A versioned pipeline of steps, run from a prompt and deployable as a unit. |
| `Metric` | class | A single scalar quality signal over one Output. |
| `Rubric` | class | A named collection of metrics scored together into one vector. |
| `Benchmark` | class | A rubric run over a fixed task set, aggregated to comparable scores. |
| `output_number` | function | Factory: a metric that extracts a numeric from the Output value. |
| `field_present` | function | Factory: a metric that checks a field is present in the Output value. |
| `is_nonempty` | function | Factory: a metric that checks the Output value (or a field) is non-empty. |
| `confidence_threshold` | function | Factory: a metric that checks a field's confidence clears ``threshold``. |
| `compare` | function | Per-metric deltas ``b - a`` (candidate minus baseline). |
| `is_regression` | function | True if ``candidate`` is worse than ``baseline`` on any metric. |
| `estimate_cost` | function | Predict the dollar cost of running ``definition`` over ``items`` items. |
| `CostEstimate` | class | A dry-run cost preview for a Definition. |
| `Budget` | class | A warn/stop spend policy. |
| `BudgetState` | enum | Where spend sits relative to a :class:`Budget`'s thresholds. |
| `CostMeter` | class | A live spend accumulator checked against a :class:`Budget`. |
| `spent_today` | function | Sum today's spend from the Store's run telemetry (UTC day). |
| `inspect_run` | function | Summarize a run from the Store's event ledger (``craw inspect <run>``). |
| `tail_events` | function | Return events after ``after_seq`` — the poll primitive for ``craw logs``. |
| `format_report` | function | Render a concise human-readable summary for ``craw inspect`` output. |
| `RunReport` | class | A summary of a single run, derived from the Store's event ledger. |
| `EvalCase` | class | A captured run made reusable: its inputs, the produced output, and an |
| `GoldenSet` | class | A named, versioned set of labeled cases, persisted through the ``Store``. |
| `LLMJudge` | class | A Definition-backed grader: an agent scores an output against criteria. |
| `capture_case` | function | Capture a real run (inputs + output [+ transcript]) as an eval case. |
| `grade_output` | function | Combine coded-metric scores and LLM-judge grades into one score dict. |
| `save_baseline` | function |  |
| `load_baseline` | function |  |
| `gate_against_baseline` | function | True if ``candidate`` passes (no regression vs the stored baseline). |
| `Registry` | class | Collects discovered units; first registration of a (kind, name) wins. |
| `UnitRef` | class | A discovered unit: its kind, name, and where it came from. |
| `ProfileConfig` | class | One named profile: which runtime backend, plus free-form settings. |
| `ProjectManifest` | class | Parsed ``crawfish.toml``. |
| `ProjectPaths` | class | Where each kind of unit lives, relative to the project root. |
| `load_manifest` | function | Load ``crawfish.toml`` from ``project_dir``; return defaults if absent. |
| `DoctorFinding` | class | One health observation. ``level`` is ``ok`` \| ``info`` \| ``warn`` \| ``error``. |
| `DoctorReport` | class | !!! abstract "Usage Documentation" |
| `diagnose` | function | Inspect ``project_dir`` and return a structured structure-health report. |
| `Cron` | class | A minimal 5-field cron evaluator (``m h dom mon dow``). |
| `CronSchedule` | class | A minimal 5-field cron evaluator (``m h dom mon dow``). |
| `scaffold_project` | function | Create a self-contained project directory and return its path. |
| `resolve_secret` | function | Resolve a secret reference (env-var name) to its value, or None if unset. |
| `load_env` | function | Parse a gitignored ``.env`` (KEY=VALUE lines). Values are never logged. |
| `SecretManager` | class | Maps nodes to the secrets they declare and resolves them least-privilege. |
| `ScrubbingStore` | class | A ``Store`` wrapper that redacts secrets/PII before any write. |
| `redact` | function | Replace known secret values and credential/PII patterns with a marker. |
| `read_capabilities` | function | Read a package's declared capabilities from ``crawfish.toml [capabilities]``. |
| `Capabilities` | class | What a package/unit declares it needs (the consent surface). |
| `snapshot_match` | function | Compare ``value`` against the snapshot at ``path``. |
| `assert_snapshot` | function | Like :func:`snapshot_match` but raise :class:`SnapshotMismatch` on a diff. |
| `run_fixtures` | function | Run every ``*.json`` fixture in ``fixtures_dir`` against ``definition``. |
| `assert_rubric` | function | Score ``output`` and assert each thresholded metric clears its floor. |
| `replaying` | function | Wrap ``inner_runtime`` so tests replay cassettes instead of calling live. |
| `generate_containerfile` | function | Generate deterministic Containerfile text for ``manifest``. |
| `plan_build` | function | Build a :class:`BuildPlan` from ``manifest``. |
| `write_containerfile` | function | Write the generated Containerfile to ``dest`` and return its path. |
| `BuildPlan` | class | Summary of what ``craw build`` will produce for a project. |
| `Trigger` | class | Base for anything that can fire a pipeline run. |
| `CronTrigger` | class | Fire a run on a cron ``schedule``. |
| `WebhookTrigger` | class | Fire a run from an inbound HTTP POST to ``path``. |
| `verify_webhook` | function | Verify an inbound webhook ``signature`` against ``payload``. |
| `Stability` | enum | The stability tier of a public API surface. |
| `stable` | function | Tag ``obj`` as :attr:`Stability.STABLE`. Behavior-preserving no-op otherwise. |
| `experimental` | function | Tag ``obj`` as :attr:`Stability.EXPERIMENTAL`. Behavior-preserving no-op. |
| `deprecated` | function | Mark a callable :attr:`Stability.DEPRECATED` and warn on every call. |
| `stability_of` | function | Read the stability tier tagged on ``obj``. |
| `is_breaking` | function | Return ``True`` when going from ``old`` to ``new`` is a major (breaking) bump. |
| `EgressBroker` | class | Mediates network egress against a capability allowlist (runtime enforcement). |
| `EgressDenied` | class | Raised when host-side code attempts egress to a non-allowlisted host. |
| `run_out_of_process` | function | Execute ``func`` in a separate process and return its result. |

### `JSONValue`

*class*

Special type indicating an unconstrained type.

- Any is compatible with every type.
- Any assumed to have all methods.
- All values assumed to be instances of Any.

Note that all the above statements are true from the point of view of
static type checkers. At runtime, Any should not be used with instance
checks.

### `new_id`

*function*

```python
new_id() -> 'str'
```

A fresh opaque identifier for any framework object.

### `Flow`

*class* — bases: `str`, `Enum`

Whether a parameter is set once per batch or varies per item.

``FLUID`` is also the prompt-injection boundary: fluid values reach the model
as session *data*, never concatenated into instructions (enforced in the
Definition compiler / runtime).

Members: `STATIC` = `'static'`, `FLUID` = `'fluid'`

### `Parameter`

*class* — bases: `BaseModel`

A typed parameter on an input/output boundary.

``type`` is a string name resolved against the type registry
(:mod:`crawfish.typesystem`); it is intentionally language-neutral so the
console and registry can read port shapes without importing Python.

### `NodeKind`

*class* — bases: `str`, `Enum`

str(object='') -> str
str(bytes_or_buffer[, encoding[, errors]]) -> str

Create a new string object from the given object. If encoding or
errors is specified, then the object must expose a data buffer
that will be decoded using the given encoding and error handler.
Otherwise, returns the result of object.__str__() (if defined)
or repr(object).
encoding defaults to 'utf-8'.
errors defaults to 'strict'.

Members: `SOURCE` = `'source'`, `BATCH` = `'batch'`, `SINK` = `'sink'`, `FILTER` = `'filter'`, `AGGREGATOR` = `'aggregator'`, `ROUTER` = `'router'`

### `Node`

*class* — bases: `ABC`

Anything that can sit in a pipeline.

Concrete nodes set ``id``/``name``/``kind`` in ``__init__``. This is an ABC
(not a Pydantic model) because nodes carry behaviour, not just data.

### `PolicyKind`

*class* — bases: `str`, `Enum`

str(object='') -> str
str(bytes_or_buffer[, encoding[, errors]]) -> str

Create a new string object from the given object. If encoding or
errors is specified, then the object must expose a data buffer
that will be decoded using the given encoding and error handler.
Otherwise, returns the result of object.__str__() (if defined)
or repr(object).
encoding defaults to 'utf-8'.
errors defaults to 'strict'.

Members: `GUARDRAIL` = `'guardrail'`, `ROUTING` = `'routing'`, `PERMISSION` = `'permission'`

### `Policy`

*class* — bases: `BaseModel`

Importable rule bundle: guardrails, model-routing, permissions.

### `parameters_compatible`

*function*

```python
parameters_compatible(out: 'Parameter', in_: 'Parameter', registry: 'TypeRegistry | None' = None) -> 'bool'
```

True if an output ``out`` can wire into an input ``in_``.

A value flows producer → consumer, so types are checked structurally in that
direction. An optional/defaulted input may go unfilled, but a *required*
input must receive a structurally compatible value.

### `RunContext`

*class*

Per-run execution context handed to every node.

```python
RunContext(store: 'Store', run_id: 'str' = <factory>, batch_id: 'str | None' = None, org_id: 'str' = 'local', cost_budget: 'CostBudget' = <factory>, cancel_token: 'CancelToken' = <factory>) -> None
```

**Methods**

- `emit(self, event: 'ObserverEvent') -> 'None'` — Append an observer event to the run-info surface.

### `CostBudget`

*class*

A token/dollar ceiling the orchestrator can hard-kill on.

``limit_usd`` of ``None`` means unbounded (local dev default).

```python
CostBudget(limit_usd: 'float | None' = None, spent_usd: 'float' = 0.0) -> None
```

**Methods**

- `charge(self, amount_usd: 'float') -> 'None'`

### `CancelToken`

*class*

Cooperative cancellation. Long loops call :meth:`raise_if_cancelled`.

```python
CancelToken(_event: 'threading.Event' = <factory>) -> None
```

**Methods**

- `cancel(self) -> 'None'`
- `raise_if_cancelled(self) -> 'None'`

### `BudgetExceeded`

*class* — bases: `RuntimeError`

Raised when a run would exceed its cost ceiling.

### `Cancelled`

*class* — bases: `RuntimeError`

Raised when a cancelled run cooperatively checks in.

### `TypeDef`

*class* — bases: `BaseModel`

A resolved type. Built by the registry; not authored directly.

### `TypeKind`

*class* — bases: `str`, `Enum`

str(object='') -> str
str(bytes_or_buffer[, encoding[, errors]]) -> str

Create a new string object from the given object. If encoding or
errors is specified, then the object must expose a data buffer
that will be decoded using the given encoding and error handler.
Otherwise, returns the result of object.__str__() (if defined)
or repr(object).
encoding defaults to 'utf-8'.
errors defaults to 'strict'.

Members: `PRIMITIVE` = `'primitive'`, `RECORD` = `'record'`, `LIST` = `'list'`, `OPTIONAL` = `'optional'`

### `TypeRegistry`

*class*

Holds named types and answers structural compatibility.

Unknown bare names resolve to *nominal* primitives (matched by name) so
authoring stays ergonomic; records are registered explicitly to unlock
field-subset rules.

```python
TypeRegistry() -> 'None'
```

**Methods**

- `explain(self, producer: 'str', consumer: 'str') -> 'str | None'` — ``None`` if compatible, else a structural reason string.
- `is_compatible(self, producer: 'str', consumer: 'str') -> 'bool'` — Can a value of ``producer`` type flow into a ``consumer`` port?
- `is_registered(self, name: 'str') -> 'bool'`
- `json_schema(self, type_str: 'str') -> 'dict[str, object]'`
- `register_primitive(self, name: 'str') -> 'None'`
- `register_record(self, name: 'str', fields: 'dict[str, str]') -> 'TypeDef'`
- `resolve(self, type_str: 'str') -> 'TypeDef'` — Parse a type string into a :class:`TypeDef`, recursing into generics.

### `default_registry`

*value* — `TypeRegistry`

`default_registry = <crawfish.typesystem.registry.TypeRegistry object at 0x102c19940>`

### `Version`

*class* — bases: `BaseModel`

A semver-ish version with an optional content sha and a frozen flag.

**Methods**

- `freeze(self) -> 'None'`

### `FrozenError`

*class* — bases: `RuntimeError`

Raised on any attempt to mutate a frozen artifact.

### `Freezable`

*class* — bases: `BaseModel`

Mixin for any customizable artifact carrying a ``version``.

Once ``version.frozen`` is set, attribute assignment is rejected — the
artifact is an immutable, reproducible unit (Definitions first, then
Source/Sink). Use :meth:`freeze` to seal.

**Methods**

- `freeze(self) -> 'None'`

### `Store`

*class* — bases: `Protocol`

Persistence contract: typed records, KV/memory, idempotency, telemetry.

```python
Store(*args, **kwargs)
```

**Methods**

- `append_event(self, run_id: 'str', event: 'dict[str, JSONValue]', *, org_id: 'str' = 'local') -> 'None'`
- `claim_idempotency(self, key: 'str', *, org_id: 'str' = 'local') -> 'bool'` — Atomically claim ``key``. Returns True iff this call won the claim
- `close(self) -> 'None'`
- `delete_record(self, kind: 'str', id: 'str', *, org_id: 'str' = 'local') -> 'None'`
- `events(self, run_id: 'str', *, org_id: 'str' = 'local') -> 'list[dict[str, JSONValue]]'`
- `get_record(self, kind: 'str', id: 'str', *, org_id: 'str' = 'local') -> 'dict[str, JSONValue] | None'`
- `kv_get(self, namespace: 'str', key: 'str', *, org_id: 'str' = 'local') -> 'JSONValue | None'`
- `kv_set(self, namespace: 'str', key: 'str', value: 'JSONValue', *, org_id: 'str' = 'local') -> 'None'`
- `list_records(self, kind: 'str', *, org_id: 'str' = 'local') -> 'list[dict[str, JSONValue]]'`
- `put_record(self, kind: 'str', id: 'str', data: 'dict[str, JSONValue]', *, org_id: 'str' = 'local') -> 'None'`

### `SqliteStore`

*class*

A ``Store`` backed by SQLite. Use ``:memory:`` for tests, a path for dev.

```python
SqliteStore(path: 'str | Path' = ':memory:') -> 'None'
```

**Methods**

- `append_event(self, run_id: 'str', event: 'dict[str, JSONValue]', *, org_id: 'str' = 'local') -> 'None'`
- `claim_idempotency(self, key: 'str', *, org_id: 'str' = 'local') -> 'bool'`
- `close(self) -> 'None'`
- `delete_record(self, kind: 'str', id: 'str', *, org_id: 'str' = 'local') -> 'None'`
- `events(self, run_id: 'str', *, org_id: 'str' = 'local') -> 'list[dict[str, JSONValue]]'`
- `get_record(self, kind: 'str', id: 'str', *, org_id: 'str' = 'local') -> 'dict[str, JSONValue] | None'`
- `kv_get(self, namespace: 'str', key: 'str', *, org_id: 'str' = 'local') -> 'JSONValue | None'`
- `kv_set(self, namespace: 'str', key: 'str', value: 'JSONValue', *, org_id: 'str' = 'local') -> 'None'`
- `list_records(self, kind: 'str', *, org_id: 'str' = 'local') -> 'list[dict[str, JSONValue]]'`
- `put_record(self, kind: 'str', id: 'str', data: 'dict[str, JSONValue]', *, org_id: 'str' = 'local') -> 'None'`

### `Engine`

*class*

Runs a pipeline of steps under a single :class:`RunContext`.

```python
Engine(store: 'Store | None' = None) -> 'None'
```

**Methods**

- `run_pipeline(self, steps: 'Sequence[Step]', *, ctx: 'RunContext | None' = None, seed: 'list[object] | None' = None) -> 'list[object]'`

### `run_pipeline`

*function*

```python
run_pipeline(steps: 'Sequence[Step]', **kwargs: 'object') -> 'list[object]'
```

Convenience wrapper that builds a default :class:`Engine`.

### `Output`

*class* — bases: `BaseModel`, `Generic`

The unit of data flowing between nodes. Frozen once produced.

**Methods**

- `derive(self, *, value: 'JSONValue', produced_by: 'str', output_schema: 'list[Parameter] | None' = None, tainted: 'bool | None' = None, lineage: 'str | None' = None) -> 'Output[JSONValue]'` — Create a fresh Output from this one (the immutable-derivation path).
- `persist(self, store: 'object', *, org_id: 'str' = 'local') -> 'None'` — Persist this Output through the ``Store`` seam.

### `output_satisfies_inputs`

*function*

```python
output_satisfies_inputs(output: 'Output[object]', inputs: 'list[Parameter]', *, registry: 'TypeRegistry | None' = None) -> 'bool'
```

True if ``output``'s schema can satisfy every *required* downstream input.

Each required input must be matched by name to a parameter in the output's
schema whose type is structurally compatible (producer → consumer).

### `check_wire`

*function*

```python
check_wire(output: 'Output[object]', inputs: 'list[Parameter]', *, registry: 'TypeRegistry | None' = None) -> 'None'
```

Raise :class:`WireError` if ``output`` cannot wire into ``inputs``.

### `WireError`

*class* — bases: `TypeError`

Raised when an upstream Output cannot wire into a downstream node's inputs.

### `Definition`

*class* — bases: `Freezable`

The rigid, code-first agent-team package, compiled from a directory.

Versioned and freezable (a frozen Definition is an immutable, reproducible
artifact). ``id`` is set deterministically by the canonical loader (ADR 0006)
so a directory and its installed package compile byte-identically.

**Methods**

- `agent(self, role: 'str') -> 'AgentSpec | None'`
- `export(self) -> 'MarketplacePackage'` — Export to a marketplace package shape.

### `AgentSpec`

*class* — bases: `BaseModel`

One agent in a team. ``prompt`` is compiled from its markdown body.

### `TeamSpec`

*class* — bases: `BaseModel`

!!! abstract "Usage Documentation"
    Models

A base class for creating Pydantic models.

Attributes:
    __class_vars__: The names of the class variables defined on the model.
    __private_attributes__: Metadata about the private attributes of the model.
    __signature__: The synthesized `__init__` [`Signature`][inspect.Signature] of the model.

    __pydantic_complete__: Whether model building is completed, or if there are still undefined fields.
    __pydantic_core_schema__: The core schema of the model.
    __pydantic_custom_init__: Whether the model has a custom `__init__` function.
    __pydantic_decorators__: Metadata containing the decorators defined on the model.
        This replaces `Model.__validators__` and `Model.__root_validators__` from Pydantic V1.
    __pydantic_generic_metadata__: A dictionary containing metadata about generic Pydantic models.
        The `origin` and `args` items map to the [`__origin__`][genericalias.__origin__]
        and [`__args__`][genericalias.__args__] attributes of [generic aliases][types-genericalias],
        and the `parameter` item maps to the `__parameter__` attribute of generic classes.
    __pydantic_parent_namespace__: Parent namespace of the model, used for automatic rebuilding of models.
    __pydantic_post_init__: The name of the post-init method for the model, if defined.
    __pydantic_root_model__: Whether the model is a [`RootModel`][pydantic.root_model.RootModel].
    __pydantic_serializer__: The `pydantic-core` `SchemaSerializer` used to dump instances of the model.
    __pydantic_validator__: The `pydantic-core` `SchemaValidator` used to validate instances of the model.

    __pydantic_fields__: A dictionary of field names and their corresponding [`FieldInfo`][pydantic.fields.FieldInfo] objects.
    __pydantic_computed_fields__: A dictionary of computed field names and their corresponding [`ComputedFieldInfo`][pydantic.fields.ComputedFieldInfo] objects.

    __pydantic_extra__: A dictionary containing extra values, if [`extra`][pydantic.config.ConfigDict.extra]
        is set to `'allow'`.
    __pydantic_fields_set__: The names of fields explicitly set during instantiation.
    __pydantic_private__: Values of private attributes set on the model instance.

### `Coordination`

*class* — bases: `str`, `Enum`

str(object='') -> str
str(bytes_or_buffer[, encoding[, errors]]) -> str

Create a new string object from the given object. If encoding or
errors is specified, then the object must expose a data buffer
that will be decoded using the given encoding and error handler.
Otherwise, returns the result of object.__str__() (if defined)
or repr(object).
encoding defaults to 'utf-8'.
errors defaults to 'strict'.

Members: `SINGLE` = `'single'`, `LEAD` = `'lead'`, `SEQUENTIAL` = `'sequential'`

### `Prompt`

*class* — bases: `BaseModel`

!!! abstract "Usage Documentation"
    Models

A base class for creating Pydantic models.

Attributes:
    __class_vars__: The names of the class variables defined on the model.
    __private_attributes__: Metadata about the private attributes of the model.
    __signature__: The synthesized `__init__` [`Signature`][inspect.Signature] of the model.

    __pydantic_complete__: Whether model building is completed, or if there are still undefined fields.
    __pydantic_core_schema__: The core schema of the model.
    __pydantic_custom_init__: Whether the model has a custom `__init__` function.
    __pydantic_decorators__: Metadata containing the decorators defined on the model.
        This replaces `Model.__validators__` and `Model.__root_validators__` from Pydantic V1.
    __pydantic_generic_metadata__: A dictionary containing metadata about generic Pydantic models.
        The `origin` and `args` items map to the [`__origin__`][genericalias.__origin__]
        and [`__args__`][genericalias.__args__] attributes of [generic aliases][types-genericalias],
        and the `parameter` item maps to the `__parameter__` attribute of generic classes.
    __pydantic_parent_namespace__: Parent namespace of the model, used for automatic rebuilding of models.
    __pydantic_post_init__: The name of the post-init method for the model, if defined.
    __pydantic_root_model__: Whether the model is a [`RootModel`][pydantic.root_model.RootModel].
    __pydantic_serializer__: The `pydantic-core` `SchemaSerializer` used to dump instances of the model.
    __pydantic_validator__: The `pydantic-core` `SchemaValidator` used to validate instances of the model.

    __pydantic_fields__: A dictionary of field names and their corresponding [`FieldInfo`][pydantic.fields.FieldInfo] objects.
    __pydantic_computed_fields__: A dictionary of computed field names and their corresponding [`ComputedFieldInfo`][pydantic.fields.ComputedFieldInfo] objects.

    __pydantic_extra__: A dictionary containing extra values, if [`extra`][pydantic.config.ConfigDict.extra]
        is set to `'allow'`.
    __pydantic_fields_set__: The names of fields explicitly set during instantiation.
    __pydantic_private__: Values of private attributes set on the model instance.

### `DefinitionRef`

*class* — bases: `BaseModel`

!!! abstract "Usage Documentation"
    Models

A base class for creating Pydantic models.

Attributes:
    __class_vars__: The names of the class variables defined on the model.
    __private_attributes__: Metadata about the private attributes of the model.
    __signature__: The synthesized `__init__` [`Signature`][inspect.Signature] of the model.

    __pydantic_complete__: Whether model building is completed, or if there are still undefined fields.
    __pydantic_core_schema__: The core schema of the model.
    __pydantic_custom_init__: Whether the model has a custom `__init__` function.
    __pydantic_decorators__: Metadata containing the decorators defined on the model.
        This replaces `Model.__validators__` and `Model.__root_validators__` from Pydantic V1.
    __pydantic_generic_metadata__: A dictionary containing metadata about generic Pydantic models.
        The `origin` and `args` items map to the [`__origin__`][genericalias.__origin__]
        and [`__args__`][genericalias.__args__] attributes of [generic aliases][types-genericalias],
        and the `parameter` item maps to the `__parameter__` attribute of generic classes.
    __pydantic_parent_namespace__: Parent namespace of the model, used for automatic rebuilding of models.
    __pydantic_post_init__: The name of the post-init method for the model, if defined.
    __pydantic_root_model__: Whether the model is a [`RootModel`][pydantic.root_model.RootModel].
    __pydantic_serializer__: The `pydantic-core` `SchemaSerializer` used to dump instances of the model.
    __pydantic_validator__: The `pydantic-core` `SchemaValidator` used to validate instances of the model.

    __pydantic_fields__: A dictionary of field names and their corresponding [`FieldInfo`][pydantic.fields.FieldInfo] objects.
    __pydantic_computed_fields__: A dictionary of computed field names and their corresponding [`ComputedFieldInfo`][pydantic.fields.ComputedFieldInfo] objects.

    __pydantic_extra__: A dictionary containing extra values, if [`extra`][pydantic.config.ConfigDict.extra]
        is set to `'allow'`.
    __pydantic_fields_set__: The names of fields explicitly set during instantiation.
    __pydantic_private__: Values of private attributes set on the model instance.

### `DefinitionAssets`

*class* — bases: `BaseModel`

!!! abstract "Usage Documentation"
    Models

A base class for creating Pydantic models.

Attributes:
    __class_vars__: The names of the class variables defined on the model.
    __private_attributes__: Metadata about the private attributes of the model.
    __signature__: The synthesized `__init__` [`Signature`][inspect.Signature] of the model.

    __pydantic_complete__: Whether model building is completed, or if there are still undefined fields.
    __pydantic_core_schema__: The core schema of the model.
    __pydantic_custom_init__: Whether the model has a custom `__init__` function.
    __pydantic_decorators__: Metadata containing the decorators defined on the model.
        This replaces `Model.__validators__` and `Model.__root_validators__` from Pydantic V1.
    __pydantic_generic_metadata__: A dictionary containing metadata about generic Pydantic models.
        The `origin` and `args` items map to the [`__origin__`][genericalias.__origin__]
        and [`__args__`][genericalias.__args__] attributes of [generic aliases][types-genericalias],
        and the `parameter` item maps to the `__parameter__` attribute of generic classes.
    __pydantic_parent_namespace__: Parent namespace of the model, used for automatic rebuilding of models.
    __pydantic_post_init__: The name of the post-init method for the model, if defined.
    __pydantic_root_model__: Whether the model is a [`RootModel`][pydantic.root_model.RootModel].
    __pydantic_serializer__: The `pydantic-core` `SchemaSerializer` used to dump instances of the model.
    __pydantic_validator__: The `pydantic-core` `SchemaValidator` used to validate instances of the model.

    __pydantic_fields__: A dictionary of field names and their corresponding [`FieldInfo`][pydantic.fields.FieldInfo] objects.
    __pydantic_computed_fields__: A dictionary of computed field names and their corresponding [`ComputedFieldInfo`][pydantic.fields.ComputedFieldInfo] objects.

    __pydantic_extra__: A dictionary containing extra values, if [`extra`][pydantic.config.ConfigDict.extra]
        is set to `'allow'`.
    __pydantic_fields_set__: The names of fields explicitly set during instantiation.
    __pydantic_private__: Values of private attributes set on the model instance.

### `MarketplacePackage`

*class* — bases: `BaseModel`

Export shape (stub — full hub package lands with the registry).

### `MCPConnection`

*class* — bases: `BaseModel`

An MCP server connection authored in ``mcp/*.py``.

``auth`` is a **secret reference** (an env-var name), never an inline credential —
resolved at run time and injected into the server env, never into the prompt.
``tools`` lists the tool names the connection exposes (so the per-agent allowlist
stays checkable).

### `load_definition`

*function*

```python
load_definition(path: 'str | Path') -> 'Definition'
```

### `DefinitionLoadError`

*class* — bases: `Exception`

Raised when a directory cannot compile to a valid Definition.

### `AgentRuntime`

*class* — bases: `ABC`

Swappable agent-loop backend.

**Methods**

- `run(self, request: 'RunRequest', ctx: 'RunContext') -> 'RunResult'` — Execute one agent turn to completion and return the typed result.
- `stream(self, request: 'RunRequest', ctx: 'RunContext') -> 'AsyncIterator[RuntimeEvent]'` — Stream events. Default: run to completion, then replay its events.

### `CommandRuntime`

*class* — bases: `AgentRuntime`

Swappable agent-loop backend.

```python
CommandRuntime(*, claude_bin: 'str' = 'claude', transport: 'Transport | None' = None, default_model: 'str' = 'claude-opus-4-8', permission_mode: 'str | None' = None) -> 'None'
```

**Methods**

- `run(self, request: 'RunRequest', ctx: 'RunContext') -> 'RunResult'` — Execute one agent turn to completion and return the typed result.

### `MockRuntime`

*class* — bases: `AgentRuntime`

Swappable agent-loop backend.

```python
MockRuntime(responder: 'Responder | None' = None) -> 'None'
```

**Methods**

- `run(self, request: 'RunRequest', ctx: 'RunContext') -> 'RunResult'` — Execute one agent turn to completion and return the typed result.

### `ClientRuntime`

*class* — bases: `AgentRuntime`

Swappable agent-loop backend.

```python
ClientRuntime(*, api_key: 'str | None' = None, model: 'str | None' = None) -> 'None'
```

**Methods**

- `run(self, request: 'RunRequest', ctx: 'RunContext') -> 'RunResult'` — Execute one agent turn to completion and return the typed result.

### `ManagedRuntime`

*class* — bases: `AgentRuntime`

Swappable agent-loop backend.

```python
ManagedRuntime(*, endpoint: 'str | None' = None) -> 'None'
```

**Methods**

- `run(self, request: 'RunRequest', ctx: 'RunContext') -> 'RunResult'` — Execute one agent turn to completion and return the typed result.

### `RecordReplayRuntime`

*class* — bases: `AgentRuntime`

Swappable agent-loop backend.

```python
RecordReplayRuntime(inner: 'AgentRuntime', cassette_dir: 'str | Path', *, record: 'bool' = False) -> 'None'
```

**Methods**

- `run(self, request: 'RunRequest', ctx: 'RunContext') -> 'RunResult'` — Execute one agent turn to completion and return the typed result.

### `RunRequest`

*class* — bases: `BaseModel`

One agent's turn: a compiled Definition + the inputs bound for this run.

### `RunResult`

*class* — bases: `BaseModel`

!!! abstract "Usage Documentation"
    Models

A base class for creating Pydantic models.

Attributes:
    __class_vars__: The names of the class variables defined on the model.
    __private_attributes__: Metadata about the private attributes of the model.
    __signature__: The synthesized `__init__` [`Signature`][inspect.Signature] of the model.

    __pydantic_complete__: Whether model building is completed, or if there are still undefined fields.
    __pydantic_core_schema__: The core schema of the model.
    __pydantic_custom_init__: Whether the model has a custom `__init__` function.
    __pydantic_decorators__: Metadata containing the decorators defined on the model.
        This replaces `Model.__validators__` and `Model.__root_validators__` from Pydantic V1.
    __pydantic_generic_metadata__: A dictionary containing metadata about generic Pydantic models.
        The `origin` and `args` items map to the [`__origin__`][genericalias.__origin__]
        and [`__args__`][genericalias.__args__] attributes of [generic aliases][types-genericalias],
        and the `parameter` item maps to the `__parameter__` attribute of generic classes.
    __pydantic_parent_namespace__: Parent namespace of the model, used for automatic rebuilding of models.
    __pydantic_post_init__: The name of the post-init method for the model, if defined.
    __pydantic_root_model__: Whether the model is a [`RootModel`][pydantic.root_model.RootModel].
    __pydantic_serializer__: The `pydantic-core` `SchemaSerializer` used to dump instances of the model.
    __pydantic_validator__: The `pydantic-core` `SchemaValidator` used to validate instances of the model.

    __pydantic_fields__: A dictionary of field names and their corresponding [`FieldInfo`][pydantic.fields.FieldInfo] objects.
    __pydantic_computed_fields__: A dictionary of computed field names and their corresponding [`ComputedFieldInfo`][pydantic.fields.ComputedFieldInfo] objects.

    __pydantic_extra__: A dictionary containing extra values, if [`extra`][pydantic.config.ConfigDict.extra]
        is set to `'allow'`.
    __pydantic_fields_set__: The names of fields explicitly set during instantiation.
    __pydantic_private__: Values of private attributes set on the model instance.

### `RuntimeEvent`

*class* — bases: `BaseModel`

!!! abstract "Usage Documentation"
    Models

A base class for creating Pydantic models.

Attributes:
    __class_vars__: The names of the class variables defined on the model.
    __private_attributes__: Metadata about the private attributes of the model.
    __signature__: The synthesized `__init__` [`Signature`][inspect.Signature] of the model.

    __pydantic_complete__: Whether model building is completed, or if there are still undefined fields.
    __pydantic_core_schema__: The core schema of the model.
    __pydantic_custom_init__: Whether the model has a custom `__init__` function.
    __pydantic_decorators__: Metadata containing the decorators defined on the model.
        This replaces `Model.__validators__` and `Model.__root_validators__` from Pydantic V1.
    __pydantic_generic_metadata__: A dictionary containing metadata about generic Pydantic models.
        The `origin` and `args` items map to the [`__origin__`][genericalias.__origin__]
        and [`__args__`][genericalias.__args__] attributes of [generic aliases][types-genericalias],
        and the `parameter` item maps to the `__parameter__` attribute of generic classes.
    __pydantic_parent_namespace__: Parent namespace of the model, used for automatic rebuilding of models.
    __pydantic_post_init__: The name of the post-init method for the model, if defined.
    __pydantic_root_model__: Whether the model is a [`RootModel`][pydantic.root_model.RootModel].
    __pydantic_serializer__: The `pydantic-core` `SchemaSerializer` used to dump instances of the model.
    __pydantic_validator__: The `pydantic-core` `SchemaValidator` used to validate instances of the model.

    __pydantic_fields__: A dictionary of field names and their corresponding [`FieldInfo`][pydantic.fields.FieldInfo] objects.
    __pydantic_computed_fields__: A dictionary of computed field names and their corresponding [`ComputedFieldInfo`][pydantic.fields.ComputedFieldInfo] objects.

    __pydantic_extra__: A dictionary containing extra values, if [`extra`][pydantic.config.ConfigDict.extra]
        is set to `'allow'`.
    __pydantic_fields_set__: The names of fields explicitly set during instantiation.
    __pydantic_private__: Values of private attributes set on the model instance.

### `get_runtime`

*function*

```python
get_runtime(profile: 'ProfileConfig') -> 'AgentRuntime'
```

Instantiate the runtime named by a resolved profile.

### `Source`

*class* — bases: `Node`, `ABC`, `Generic`

Pipeline ingress that fetches data and emits a typed Output.

Subclasses declare their per-item shape in :attr:`outputs` and implement
:meth:`fetch`. Set :attr:`multi` to ``True`` when :meth:`fetch` returns an
Output whose value is a list of items to fan out into independent Runs.

```python
Source(name: 'str', config: 'dict[str, JSONValue] | None' = None) -> 'None'
```

**Methods**

- `fan_out(self, output: 'Output[T]') -> 'list[Output[JSONValue]]'` — Explode a multi source's list Output into one Output per item.
- `fetch(self, ctx: 'RunContext') -> 'Output[T]'` — Fetch data and return a typed Output matching :attr:`outputs`.

### `RepoSource`

*class* — bases: `Source`

Single source describing one repository (deterministic, network-free).

``config`` keys:
    ``repo``: the static repository identifier (e.g. ``"owner/name"``).
    ``auth``: a secret *reference* — the env-var name holding the token.

**Methods**

- `fetch(self, ctx: 'RunContext') -> 'Output[dict[str, JSONValue]]'` — Fetch data and return a typed Output matching :attr:`outputs`.

### `PullRequestSource`

*class* — bases: `Source`

Multi source emitting a list of pull requests (deterministic, network-free).

``config`` keys:
    ``repo``: the static repository identifier.
    ``items``: a fixture list of PR dicts (each matching :attr:`outputs`).
    ``auth``: an optional secret *reference* (env-var name).

**Methods**

- `fetch(self, ctx: 'RunContext') -> 'Output[list[dict[str, JSONValue]]]'` — Fetch data and return a typed Output matching :attr:`outputs`.

### `fan_out`

*function*

```python
fan_out(output: 'Output[JSONValue]', *, multi: 'bool', item_schema: 'list[Parameter] | None' = None) -> 'list[Output[JSONValue]]'
```

Split a multi-item Output into per-item Outputs that seed N Runs.

When ``multi`` is ``False`` (or the value is not a list), the input Output is
returned as a single-element list. Otherwise each list item becomes its own
Output with ``value`` set to the item, ``produced_by`` preserved, and
``output_schema`` set to ``item_schema`` (the declared per-item shape).

### `Sink`

*class* — bases: `Node`, `ABC`, `Generic`

Base class for egress nodes. Subclasses implement :meth:`_write`.

The public :meth:`write` wraps the side effect with idempotency and the
optional approval gate; subclasses never reimplement those invariants.

```python
Sink(name: 'str', config: 'dict[str, JSONValue] | None' = None, *, always_ask: 'bool' = False, target_params: 'list[Parameter] | None' = None) -> 'None'
```

**Methods**

- `write(self, output: 'Output[T]', ctx: 'RunContext', *, approve: 'ApproveCallback | None' = None) -> 'bool'` — Write ``output`` to this sink's static target.

### `LinearSink`

*class* — bases: `Sink`

Create a Linear issue/comment. Dry-run by default (network-free).

In ``dry_run`` mode the would-be write is recorded into :attr:`writes`
instead of hitting the network, which keeps tests deterministic.

```python
LinearSink(name: 'str' = 'linear', config: 'dict[str, JSONValue] | None' = None, *, always_ask: 'bool' = False, target_params: 'list[Parameter] | None' = None, dry_run: 'bool' = True) -> 'None'
```

### `GitHubPRSink`

*class* — bases: `Sink`

Open a GitHub pull request. Dry-run by default (network-free).

In ``dry_run`` mode the would-be PR is recorded into :attr:`writes` instead
of calling GitHub, keeping tests deterministic and offline.

```python
GitHubPRSink(name: 'str' = 'github_pr', config: 'dict[str, JSONValue] | None' = None, *, always_ask: 'bool' = False, target_params: 'list[Parameter] | None' = None, dry_run: 'bool' = True) -> 'None'
```

### `TargetMustBeStaticError`

*class* — bases: `ValueError`

Raised when a target parameter is ``Flow.FLUID``.

Targets address *where* a write lands; allowing a fluid (per-item,
model-influenced) target would let upstream data redirect egress. Rejected
at construction so the guarantee holds at wire/compile time, not runtime.

### `ApprovalRequired`

*class* — bases: `RuntimeError`

Raised when an ``always_ask`` sink is asked to write without approval.

### `Filter`

*class* — bases: `Node`, `Generic`

A pure, synchronous node that narrows a list Output by a predicate.

The predicate is applied per item; matching items are kept in their original
order. The input Output is left unchanged (it is frozen); :meth:`apply`
returns a freshly derived Output with a new id.

```python
Filter(predicate: 'Callable[[T], bool]', name: 'str' = 'filter') -> 'None'
```

**Methods**

- `apply(self, inp: 'Output[list[T]]') -> 'Output[list[T]]'` — Return a fresh Output keeping only items that satisfy the predicate.

### `title_contains`

*function*

```python
title_contains(needle: 'str', name: 'str' = 'title_contains') -> 'Filter[JSONValue]'
```

Keep dict items whose ``"title"`` field contains ``needle``.

### `field_equals`

*function*

```python
field_equals(field: 'str', value: 'JSONValue', name: 'str' = 'field_equals') -> 'Filter[JSONValue]'
```

Keep dict items whose ``field`` equals ``value``.

### `field_matches`

*function*

```python
field_matches(field: 'str', pattern: 'str', name: 'str' = 'field_matches') -> 'Filter[JSONValue]'
```

Keep dict items whose ``field`` (as a string) matches ``pattern`` (regex search).

### `limit`

*function*

```python
limit(n: 'int', name: 'str' = 'limit') -> 'Filter[JSONValue]'
```

Keep the first ``n`` items (a list slice, not a per-item test).

### `Memory`

*class*

A ``Store``-backed KV/dedup handle scoped to ``(namespace, org_id)``.

```python
Memory(store: 'Store', namespace: 'str', *, org_id: 'str' = 'local') -> 'None'
```

**Methods**

- `already_processed(self, item_id: 'str') -> 'bool'` — True iff ``item_id`` was previously marked via :meth:`mark_processed`.
- `claim(self, item_id: 'str') -> 'bool'` — Atomically claim ``item_id``.
- `get(self, key: 'str') -> 'JSONValue | None'` — Return the value stored at ``key`` in this namespace, or ``None``.
- `mark_processed(self, item_id: 'str') -> 'None'` — Record ``item_id`` as processed (persists across runs).
- `set(self, key: 'str', value: 'JSONValue') -> 'None'` — Store ``value`` at ``key`` within this namespace.

### `Run`

*class*

An agent team performing a single task.

```python
Run(definition: 'Definition', inputs: 'dict[str, JSONValue] | None' = None, *, runtime: 'AgentRuntime | None' = None, requires_approval: 'bool' = False, id: 'str | None' = None) -> 'None'
```

**Methods**

- `execute(self, ctx: 'RunContext', runtime: 'AgentRuntime | None' = None, *, approve: 'bool | None' = None) -> 'Output[JSONValue]'` — Execute the Definition's team on the bound inputs → a typed Output.
- `validate(self) -> 'None'` — Fail fast if any required input slot is unbound (before any model call).

### `RunStatus`

*class* — bases: `str`, `Enum`

str(object='') -> str
str(bytes_or_buffer[, encoding[, errors]]) -> str

Create a new string object from the given object. If encoding or
errors is specified, then the object must expose a data buffer
that will be decoded using the given encoding and error handler.
Otherwise, returns the result of object.__str__() (if defined)
or repr(object).
encoding defaults to 'utf-8'.
errors defaults to 'strict'.

Members: `PENDING` = `'pending'`, `RUNNING` = `'running'`, `DONE` = `'done'`, `FAILED` = `'failed'`, `SUSPENDED` = `'suspended'`

### `InputBindingError`

*class* — bases: `ValueError`

Raised when a required input slot is unbound before execution.

### `RunSuspended`

*class* — bases: `RuntimeError`

Raised when a Run idles on an approval gate (state persisted, no compute spent).

### `Batch`

*class* — bases: `Node`

A set of Runs executed under one Definition, wired from Sources/Outputs.

```python
Batch(definition: 'Definition', name: 'str' = 'batch', *, runtime: 'AgentRuntime | None' = None, cost_budget: 'CostBudget | None' = None) -> 'None'
```

**Methods**

- `add_input(self, item: 'Source[JSONValue] | Output[JSONValue]') -> 'Batch'`
- `check_wiring(self) -> 'None'` — Reject a mistyped/missing wire at assembly (before run time).
- `detect_anomalies(self) -> 'list[Anomaly]'` — Surface failed runs as anomalies (richer rules arrive with Metrics).
- `run(self, ctx: 'RunContext', runtime: 'AgentRuntime | None' = None) -> 'list[Output[JSONValue]]'`

### `Task`

*class* — bases: `BaseModel`

!!! abstract "Usage Documentation"
    Models

A base class for creating Pydantic models.

Attributes:
    __class_vars__: The names of the class variables defined on the model.
    __private_attributes__: Metadata about the private attributes of the model.
    __signature__: The synthesized `__init__` [`Signature`][inspect.Signature] of the model.

    __pydantic_complete__: Whether model building is completed, or if there are still undefined fields.
    __pydantic_core_schema__: The core schema of the model.
    __pydantic_custom_init__: Whether the model has a custom `__init__` function.
    __pydantic_decorators__: Metadata containing the decorators defined on the model.
        This replaces `Model.__validators__` and `Model.__root_validators__` from Pydantic V1.
    __pydantic_generic_metadata__: A dictionary containing metadata about generic Pydantic models.
        The `origin` and `args` items map to the [`__origin__`][genericalias.__origin__]
        and [`__args__`][genericalias.__args__] attributes of [generic aliases][types-genericalias],
        and the `parameter` item maps to the `__parameter__` attribute of generic classes.
    __pydantic_parent_namespace__: Parent namespace of the model, used for automatic rebuilding of models.
    __pydantic_post_init__: The name of the post-init method for the model, if defined.
    __pydantic_root_model__: Whether the model is a [`RootModel`][pydantic.root_model.RootModel].
    __pydantic_serializer__: The `pydantic-core` `SchemaSerializer` used to dump instances of the model.
    __pydantic_validator__: The `pydantic-core` `SchemaValidator` used to validate instances of the model.

    __pydantic_fields__: A dictionary of field names and their corresponding [`FieldInfo`][pydantic.fields.FieldInfo] objects.
    __pydantic_computed_fields__: A dictionary of computed field names and their corresponding [`ComputedFieldInfo`][pydantic.fields.ComputedFieldInfo] objects.

    __pydantic_extra__: A dictionary containing extra values, if [`extra`][pydantic.config.ConfigDict.extra]
        is set to `'allow'`.
    __pydantic_fields_set__: The names of fields explicitly set during instantiation.
    __pydantic_private__: Values of private attributes set on the model instance.

### `Anomaly`

*class* — bases: `BaseModel`

!!! abstract "Usage Documentation"
    Models

A base class for creating Pydantic models.

Attributes:
    __class_vars__: The names of the class variables defined on the model.
    __private_attributes__: Metadata about the private attributes of the model.
    __signature__: The synthesized `__init__` [`Signature`][inspect.Signature] of the model.

    __pydantic_complete__: Whether model building is completed, or if there are still undefined fields.
    __pydantic_core_schema__: The core schema of the model.
    __pydantic_custom_init__: Whether the model has a custom `__init__` function.
    __pydantic_decorators__: Metadata containing the decorators defined on the model.
        This replaces `Model.__validators__` and `Model.__root_validators__` from Pydantic V1.
    __pydantic_generic_metadata__: A dictionary containing metadata about generic Pydantic models.
        The `origin` and `args` items map to the [`__origin__`][genericalias.__origin__]
        and [`__args__`][genericalias.__args__] attributes of [generic aliases][types-genericalias],
        and the `parameter` item maps to the `__parameter__` attribute of generic classes.
    __pydantic_parent_namespace__: Parent namespace of the model, used for automatic rebuilding of models.
    __pydantic_post_init__: The name of the post-init method for the model, if defined.
    __pydantic_root_model__: Whether the model is a [`RootModel`][pydantic.root_model.RootModel].
    __pydantic_serializer__: The `pydantic-core` `SchemaSerializer` used to dump instances of the model.
    __pydantic_validator__: The `pydantic-core` `SchemaValidator` used to validate instances of the model.

    __pydantic_fields__: A dictionary of field names and their corresponding [`FieldInfo`][pydantic.fields.FieldInfo] objects.
    __pydantic_computed_fields__: A dictionary of computed field names and their corresponding [`ComputedFieldInfo`][pydantic.fields.ComputedFieldInfo] objects.

    __pydantic_extra__: A dictionary containing extra values, if [`extra`][pydantic.config.ConfigDict.extra]
        is set to `'allow'`.
    __pydantic_fields_set__: The names of fields explicitly set during instantiation.
    __pydantic_private__: Values of private attributes set on the model instance.

### `Aggregator`

*class* — bases: `Node`

A fan-in node: consumes a group of N Outputs and emits one Output.

The ``reducer`` is any :class:`Reducer` (a built-in or
:func:`definition_reducer`). ``output_schema`` declares the shape of the reduced
value on the emitted Output (default: empty, i.e. undeclared).

```python
Aggregator(reducer: 'Reducer', *, output_schema: 'list[Parameter] | None' = None, name: 'str' = 'aggregator') -> 'None'
```

**Methods**

- `reduce(self, outputs: 'list[Output[JSONValue]]', ctx: 'RunContext') -> 'Output[JSONValue]'` — Apply the reducer to the N item Outputs and emit one fresh Output.

### `collect`

*function*

```python
collect(outputs: 'list[Output[JSONValue]]', ctx: 'RunContext') -> 'list[JSONValue]'
```

Gather the item values into a list (the identity fan-in).

### `concat`

*function*

```python
concat(outputs: 'list[Output[JSONValue]]', ctx: 'RunContext') -> 'str'
```

Concatenate the item values into one string (str-coerced, no separator).

### `count`

*function*

```python
count(outputs: 'list[Output[JSONValue]]', ctx: 'RunContext') -> 'int'
```

Count the items.

### `dedupe`

*function*

```python
dedupe(outputs: 'list[Output[JSONValue]]', ctx: 'RunContext') -> 'list[JSONValue]'
```

List the item values with duplicates removed, first-seen order preserved.

### `definition_reducer`

*function*

```python
definition_reducer(definition: 'Definition', runtime: 'AgentRuntime') -> 'Reducer'
```

A reducer that runs an agent team to reduce N item values into one.

The N item *values* are fed in as a single fluid input (``{"items": [...]}``), so
they reach the model as untrusted session data (never as instructions). The
reduced value is the agent team's text result.

### `fan_in`

*function*

```python
fan_in(runs_or_coros: 'list[Awaitable[Output[JSONValue] | None]]', *, quorum: 'int | None' = None) -> 'list[Output[JSONValue]]'
```

Barrier that waits for N concurrent runs and returns their successful Outputs.

Partial-success aware: results that raise or resolve to ``None`` are dropped, so a
single failed item never sinks the fan-in. Order is preserved (submission order).
If ``quorum`` is given, raise once fewer than ``quorum`` items succeed.

### `Router`

*class* — bases: `Node`

A node that routes an Output down one labelled branch chosen by a Classifier.

``branches`` maps every classifier label (including ``default``, the dead-letter
branch) to a downstream :class:`Node`. Construction fails with
:class:`UnroutableLabelError` if any classifier label is uncovered (assembly-time
check) — the routing graph is total before it ever runs.

```python
Router(branches: 'Mapping[str, Node]', classifier: 'Classifier', name: 'str' = 'router') -> 'None'
```

**Methods**

- `route(self, output: 'Output[JSONValue]') -> 'tuple[str, Node]'` — Classify ``output`` (pure path) and return the chosen ``(label, branch)``.
- `route_async(self, output: 'Output[JSONValue]', ctx: 'RunContext', runtime: 'AgentRuntime') -> 'tuple[str, Node]'` — Classify ``output`` via the agent team and return ``(label, branch)``.

### `Classifier`

*class*

Produces one typed label for an :class:`Output` from a closed label set.

Construct via :meth:`from_predicates` (pure/built-in) or :meth:`from_definition`
(agent-backed). ``labels`` is the explicit, closed set of possible labels and always
includes ``default``.

```python
Classifier(*, labels: 'list[str]', default: 'str', predicates: 'Mapping[str, Predicate] | None' = None, definition: 'Definition | None' = None, name: 'str' = 'classifier') -> 'None'
```

**Methods**

- `classify(self, output: 'Output[JSONValue]') -> 'str'` — Return the first predicate-matched label, or ``default`` (pure path).
- `classify_async(self, output: 'Output[JSONValue]', ctx: 'RunContext', runtime: 'AgentRuntime') -> 'str'` — Run the agent team on ``output`` and normalise its text to a label.

### `UnroutableLabelError`

*class* — bases: `ValueError`

Raised at assembly time when a classifier label has no matching branch.

### `ArtifactRef`

*class* — bases: `BaseModel`

A content-addressed pointer to artifact bytes held in an ``ArtifactStore``.

This is what an ``Output`` carries instead of inline bytes. ``uri`` and
``sha256`` both derive from the content hash, so identical content dedupes.

### `ArtifactStore`

*class* — bases: `Protocol`

Blob persistence contract: content-addressed, tenant-scoped, GC-able.

```python
ArtifactStore(*args, **kwargs)
```

**Methods**

- `delete(self, ref: 'ArtifactRef', *, org_id: 'str' = 'local') -> 'None'` — Delete ``ref``'s content for this ``org_id`` (no-op if absent).
- `exists(self, ref: 'ArtifactRef', *, org_id: 'str' = 'local') -> 'bool'` — True iff ``ref``'s content is stored under this ``org_id``.
- `gc(self, live_refs: 'set[str]', *, org_id: 'str' = 'local') -> 'int'` — Delete artifacts whose sha256 is not in ``live_refs``; return count.
- `get(self, ref: 'ArtifactRef', *, org_id: 'str' = 'local') -> 'bytes'` — Return the bytes for ``ref``. Raises if absent for this ``org_id``.
- `put(self, data: 'bytes', *, content_type: 'str' = 'application/octet-stream', org_id: 'str' = 'local') -> 'ArtifactRef'` — Store ``data`` and return a content-addressed :class:`ArtifactRef`.

### `LocalArtifactStore`

*class*

An ``ArtifactStore`` backed by the local filesystem, addressed by sha256.

```python
LocalArtifactStore(root: 'str | Path') -> 'None'
```

**Methods**

- `delete(self, ref: 'ArtifactRef', *, org_id: 'str' = 'local') -> 'None'`
- `exists(self, ref: 'ArtifactRef', *, org_id: 'str' = 'local') -> 'bool'`
- `gc(self, live_refs: 'set[str]', *, org_id: 'str' = 'local') -> 'int'`
- `get(self, ref: 'ArtifactRef', *, org_id: 'str' = 'local') -> 'bytes'`
- `put(self, data: 'bytes', *, content_type: 'str' = 'application/octet-stream', org_id: 'str' = 'local') -> 'ArtifactRef'`

### `offload_if_large`

*function*

```python
offload_if_large(value: 'JSONValue', store: 'ArtifactStore', *, threshold: 'int' = 65536, org_id: 'str' = 'local') -> 'JSONValue | ArtifactRef'
```

Offload ``value`` to ``store`` if its JSON form exceeds ``threshold`` bytes.

Returns an :class:`ArtifactRef` (content_type ``application/json``) when the
serialized value is larger than ``threshold``; otherwise returns ``value``
unchanged. This is how an Output keeps large payloads out of the record.

### `DependencyGraph`

*class*

Edges ``(blocker, blocked)``; ``topo_layers`` returns parallelizable layers.

```python
DependencyGraph() -> 'None'
```

**Methods**

- `add_edge(self, blocker: 'str', blocked: 'str') -> 'None'`
- `add_node(self, node: 'str') -> 'None'`
- `topo_layers(self) -> 'list[list[str]]'`

### `CycleError`

*class* — bases: `ValueError`

Raised when a dependency graph contains a cycle.

### `Roadmap`

*class* — bases: `BaseModel`

!!! abstract "Usage Documentation"
    Models

A base class for creating Pydantic models.

Attributes:
    __class_vars__: The names of the class variables defined on the model.
    __private_attributes__: Metadata about the private attributes of the model.
    __signature__: The synthesized `__init__` [`Signature`][inspect.Signature] of the model.

    __pydantic_complete__: Whether model building is completed, or if there are still undefined fields.
    __pydantic_core_schema__: The core schema of the model.
    __pydantic_custom_init__: Whether the model has a custom `__init__` function.
    __pydantic_decorators__: Metadata containing the decorators defined on the model.
        This replaces `Model.__validators__` and `Model.__root_validators__` from Pydantic V1.
    __pydantic_generic_metadata__: A dictionary containing metadata about generic Pydantic models.
        The `origin` and `args` items map to the [`__origin__`][genericalias.__origin__]
        and [`__args__`][genericalias.__args__] attributes of [generic aliases][types-genericalias],
        and the `parameter` item maps to the `__parameter__` attribute of generic classes.
    __pydantic_parent_namespace__: Parent namespace of the model, used for automatic rebuilding of models.
    __pydantic_post_init__: The name of the post-init method for the model, if defined.
    __pydantic_root_model__: Whether the model is a [`RootModel`][pydantic.root_model.RootModel].
    __pydantic_serializer__: The `pydantic-core` `SchemaSerializer` used to dump instances of the model.
    __pydantic_validator__: The `pydantic-core` `SchemaValidator` used to validate instances of the model.

    __pydantic_fields__: A dictionary of field names and their corresponding [`FieldInfo`][pydantic.fields.FieldInfo] objects.
    __pydantic_computed_fields__: A dictionary of computed field names and their corresponding [`ComputedFieldInfo`][pydantic.fields.ComputedFieldInfo] objects.

    __pydantic_extra__: A dictionary containing extra values, if [`extra`][pydantic.config.ConfigDict.extra]
        is set to `'allow'`.
    __pydantic_fields_set__: The names of fields explicitly set during instantiation.
    __pydantic_private__: Values of private attributes set on the model instance.

### `ExecutionPlan`

*class* — bases: `BaseModel`

!!! abstract "Usage Documentation"
    Models

A base class for creating Pydantic models.

Attributes:
    __class_vars__: The names of the class variables defined on the model.
    __private_attributes__: Metadata about the private attributes of the model.
    __signature__: The synthesized `__init__` [`Signature`][inspect.Signature] of the model.

    __pydantic_complete__: Whether model building is completed, or if there are still undefined fields.
    __pydantic_core_schema__: The core schema of the model.
    __pydantic_custom_init__: Whether the model has a custom `__init__` function.
    __pydantic_decorators__: Metadata containing the decorators defined on the model.
        This replaces `Model.__validators__` and `Model.__root_validators__` from Pydantic V1.
    __pydantic_generic_metadata__: A dictionary containing metadata about generic Pydantic models.
        The `origin` and `args` items map to the [`__origin__`][genericalias.__origin__]
        and [`__args__`][genericalias.__args__] attributes of [generic aliases][types-genericalias],
        and the `parameter` item maps to the `__parameter__` attribute of generic classes.
    __pydantic_parent_namespace__: Parent namespace of the model, used for automatic rebuilding of models.
    __pydantic_post_init__: The name of the post-init method for the model, if defined.
    __pydantic_root_model__: Whether the model is a [`RootModel`][pydantic.root_model.RootModel].
    __pydantic_serializer__: The `pydantic-core` `SchemaSerializer` used to dump instances of the model.
    __pydantic_validator__: The `pydantic-core` `SchemaValidator` used to validate instances of the model.

    __pydantic_fields__: A dictionary of field names and their corresponding [`FieldInfo`][pydantic.fields.FieldInfo] objects.
    __pydantic_computed_fields__: A dictionary of computed field names and their corresponding [`ComputedFieldInfo`][pydantic.fields.ComputedFieldInfo] objects.

    __pydantic_extra__: A dictionary containing extra values, if [`extra`][pydantic.config.ConfigDict.extra]
        is set to `'allow'`.
    __pydantic_fields_set__: The names of fields explicitly set during instantiation.
    __pydantic_private__: Values of private attributes set on the model instance.

### `BatchExecutor`

*class*

Schedules + runs a Batch. Rule-based; leaves a seam for an agentic executor.

```python
BatchExecutor(definition: 'Definition', *, max_concurrency: 'int' = 8, retry_policy: 'RetryPolicy | None' = None, runtime: 'AgentRuntime | None' = None) -> 'None'
```

**Methods**

- `replay(self, batch: 'Batch', ctx: 'RunContext', runtime: 'AgentRuntime | None' = None) -> 'BatchRunResult'` — Re-run only dead-lettered items (idempotency makes this safe).
- `run(self, batch: 'Batch', ctx: 'RunContext', runtime: 'AgentRuntime | None' = None, *, only_items: 'set[str] | None' = None) -> 'BatchRunResult'`
- `schedule(self, tasks: 'list[Task]') -> 'ExecutionPlan'`

### `BatchRunResult`

*class*

BatchRunResult(outputs: 'list[Output[JSONValue]]' = <factory>, items: 'list[ItemResult]' = <factory>, dead_letters: 'list[dict[str, JSONValue]]' = <factory>)

```python
BatchRunResult(outputs: 'list[Output[JSONValue]]' = <factory>, items: 'list[ItemResult]' = <factory>, dead_letters: 'list[dict[str, JSONValue]]' = <factory>) -> None
```

### `ExecutionLedger`

*class*

Store-backed execution state for pipelines, runs, and fan-out items.

```python
ExecutionLedger(store: 'Store', *, org_id: 'str' = 'local') -> 'None'
```

**Methods**

- `checkpoint_step(self, pipeline_id: 'str', step_index: 'int') -> 'None'`
- `completed_items(self, pipeline_id: 'str') -> 'set[str]'`
- `completed_steps(self, pipeline_id: 'str') -> 'set[int]'`
- `finish_pipeline(self, pipeline_id: 'str', status: 'ExecState' = <ExecState.DONE: 'done'>) -> 'None'`
- `mark_item(self, pipeline_id: 'str', item_id: 'str', status: 'ExecState') -> 'None'`
- `pinned_version(self, pipeline_id: 'str') -> 'str | None'` — The version this pipeline started on — unchanged by any redeploy.
- `reconcile(self) -> 'dict[str, list[str]]'` — Reconcile orphaned state after an engine restart.
- `record_run(self, run_id: 'str', *, backend: 'str', status: 'ExecState', version: 'str') -> 'None'`
- `start_pipeline(self, pipeline_id: 'str', version: 'str', *, total_items: 'int' = 0) -> 'None'`

### `ObserverEvent`

*class* — bases: `BaseModel`

A structured finding emitted by an observer or a node.

``pipeline`` and ``kind`` are stable, static identifiers (safe to render and
filter on); ``detail``/``data`` are free-form and are scrubbed on write when the
surface is backed by a :class:`~crawfish.secrets.ScrubbingStore`.

### `ObserverSurface`

*class*

Read/write facade over the run-info surface, scoped to one tenant.

Persists through whatever :class:`~crawfish.store.base.Store` it is handed — pass
a :class:`~crawfish.secrets.ScrubbingStore` to redact secrets before the write.

```python
ObserverSurface(store: 'Store', *, org_id: 'str' = 'local') -> 'None'
```

**Methods**

- `emit(self, event: 'ObserverEvent') -> 'None'` — Append an observer event to the ``pipeline``'s ordered stream.
- `events(self, pipeline: 'str', *, since: 'str | float | int | None' = None, kind: 'str | None' = None, now: 'float | None' = None) -> 'list[ObserverEvent]'` — Observer events for ``pipeline``, oldest first, filtered by time/kind.
- `get_run_info(self, run_id: 'str') -> 'RunInfo | None'`
- `put_run_info(self, info: 'RunInfo') -> 'None'` — Upsert a run's info record (idempotent on ``run_id``).
- `run_info(self, pipeline: 'str | None' = None, *, since: 'str | float | int | None' = None, now: 'float | None' = None) -> 'list[RunInfo]'` — Run-info records, newest first, optionally scoped to one pipeline/window.

### `RunInfo`

*class* — bases: `BaseModel`

Per-run summary the dashboard and ``craw manage`` read.

### `Severity`

*class* — bases: `str`, `Enum`

How loudly an observer event should be surfaced.

Members: `INFO` = `'info'`, `WARN` = `'warn'`, `CRITICAL` = `'critical'`

### `parse_since`

*function*

```python
parse_since(since: 'str | float | int | None' = None, *, now: 'float | None' = None) -> 'float'
```

Resolve a ``since`` argument to an epoch-seconds threshold.

Accepts ``None`` (epoch 0 — everything), an absolute epoch ``float``/``int``, or a
relative string like ``"-1h"`` / ``"-30m"`` / ``"-15s"`` / ``"-2d"``.

### `DeployEntry`

*class* — bases: `BaseModel`

A registry row describing one deployed pipeline.

### `DeployRegistry`

*class*

Store-backed registry of deployed pipelines (read by deploy/manage/visualize).

```python
DeployRegistry(store: 'Store', *, org_id: 'str' = 'local') -> 'None'
```

**Methods**

- `entries(self) -> 'list[DeployEntry]'`
- `get(self, name: 'str') -> 'DeployEntry | None'`
- `reconcile_liveness(self) -> 'list[str]'` — Mark registry rows whose PID is gone as ``DEAD``; return their names.
- `register(self, entry: 'DeployEntry') -> 'None'`
- `remove(self, name: 'str') -> 'None'`
- `set_status(self, name: 'str', status: 'DeployStatus') -> 'None'`

### `DeployStatus`

*class* — bases: `str`, `Enum`

str(object='') -> str
str(bytes_or_buffer[, encoding[, errors]]) -> str

Create a new string object from the given object. If encoding or
errors is specified, then the object must expose a data buffer
that will be decoded using the given encoding and error handler.
Otherwise, returns the result of object.__str__() (if defined)
or repr(object).
encoding defaults to 'utf-8'.
errors defaults to 'strict'.

Members: `RUNNING` = `'running'`, `STOPPED` = `'stopped'`, `DEAD` = `'dead'`

### `Supervisor`

*class*

The always-on loop: schedule → fire → record, with ledger-backed resume.

Construct with the pipeline ``name``, a :class:`~crawfish.store.base.Store`, the
cycle ``run_fn``, and an optional cron ``schedule``. :meth:`serve` blocks; tests
drive :meth:`run_cycle` / :meth:`due` directly with an injected clock.

```python
Supervisor(name: 'str', store: 'Store', run_fn: 'RunFn', *, schedule: 'str | None' = None, org_id: 'str' = 'local', version: 'str' = '0.1.0', backend: 'str' = 'command', secrets: 'Sequence[str]' = ()) -> 'None'
```

**Methods**

- `due(self, now: 'datetime') -> 'bool'` — Whether a cycle should fire at ``now`` (always, if no schedule).
- `process_items(self, items: 'Sequence[str]', handler: 'Callable[[str], None]') -> 'list[str]'` — Process fan-out ``items`` exactly once across restarts (ledger resume).
- `reconcile(self) -> 'dict[str, list[str]]'` — On (re)start, resume/retry orphaned runs via the ledger.
- `run_cycle(self, now: 'datetime | None' = None) -> 'str'` — Execute one pipeline cycle, recording RunInfo + ledger state.
- `serve(self, *, max_cycles: 'int | None' = None, now_fn: 'Callable[[], datetime] | None' = None, sleep_fn: 'Callable[[float], None] | None' = None, stop_flag: 'Callable[[], bool] | None' = None) -> 'int'` — Block in the always-on loop. Returns the number of cycles fired.

### `deploy`

*function*

```python
deploy(project_dir: 'str | Path', *, name: 'str', store: 'Store', schedule: 'str | None' = None, backend: 'str' = 'daemon', spawn: 'Spawner | None' = None, org_id: 'str' = 'local') -> 'DeployEntry'
```

Detach the project's pipeline as an always-on supervisor and register it.

Validates the schedule up front, spawns the detached ``craw _supervise`` child
(argv carries only the pipeline name + dir — never a secret), and writes the
deploy-registry entry ``craw manage`` reads.

When ``schedule`` is omitted, the project's own declared trigger (a module-level
``TRIGGER``/``SCHEDULE`` in its ``pipeline.py``) is used — so cadence lives in the
project, not the command line.

### `stop`

*function*

```python
stop(name: 'str', *, store: 'Store', org_id: 'str' = 'local', kill: 'Callable[[int], None] | None' = None) -> 'bool'
```

Stop a deployed pipeline: signal its process and clear its registry status.

Returns True if an entry was found. ``kill`` is injectable for tests.

### `PipelineStatus`

*class* — bases: `BaseModel`

A row in ``craw manage``: a deployed pipeline joined with its run state.

### `manage_list`

*function*

```python
manage_list(store: 'Store', *, org_id: 'str' = 'local', now: 'datetime | None' = None) -> 'list[PipelineStatus]'
```

Build the management view for every deployed pipeline.

Reconciles liveness first (marks dead PIDs), then joins each registry entry with
its run-info history for uptime, last run, next fire, and today's spend.

### `format_table`

*function*

```python
format_table(rows: 'list[PipelineStatus]', *, show_dir: 'bool' = False) -> 'str'
```

Render the management view as a fixed-width table (``craw manage``).

``show_dir`` appends a DIR column — useful for the global view, where pipelines come
from different project directories.

### `restart_target`

*function*

```python
restart_target(name: 'str', *, store: 'Store', org_id: 'str' = 'local', spawn: 'Spawner | None' = None) -> 'bool'
```

Stop then re-deploy ``name`` with its recorded dir + schedule. Returns success.

### `Observer`

*class*

Watch one pipeline: run rules (and an optional LLM judge) on a poll interval.

```python
Observer(watch: 'str', *, poll: 'str | CronSchedule | None' = None, rules: 'Sequence[Rule]' = (), judge: 'Definition | None' = None, judge_runtime: 'AgentRuntime | None' = None, judge_cost_cap_usd: 'float' = 0.5, judge_flag: 'JudgeFlagFn' = <function _default_judge_flag at 0x104379a80>, org_id: 'str' = 'local', lookback: 'str' = '-24h') -> 'None'
```

**Methods**

- `evaluate(self, store: 'Store', *, now: 'datetime | None' = None, run_judge: 'bool' = True) -> 'list[ObserverEvent]'` — Run every rule (and the judge, if configured) once; emit + return findings.
- `poll_due(self, now: 'datetime') -> 'bool'` — Whether the poll schedule fires at ``now`` (always, if no schedule).
- `watch_loop(self, store: 'Store', *, max_polls: 'int | None' = None, now_fn: 'Callable[[], datetime] | None' = None, sleep_fn: 'Callable[[float], None] | None' = None, stop_flag: 'Callable[[], bool] | None' = None) -> 'int'` — Block, evaluating on each poll tick. Returns the number of evaluations.

### `ObserverContext`

*class*

The window a rule judges: recent runs + events for one pipeline at ``now``.

``events`` (the pipeline's recent observer events) is provided as a hook for custom
user rules — the built-in rules judge ``runs`` only, but a rule can read prior
findings (e.g. to debounce or escalate repeats).

```python
ObserverContext(pipeline: 'str', runs: 'list[RunInfo]', events: 'list[ObserverEvent]', now: 'datetime') -> None
```

**Methods**

- `runs_since(self, window: 'str') -> 'list[RunInfo]'`

### `Rule`

*class* — bases: `ABC`

A cheap, deterministic check over recent runs. Returns an event or ``None``.

**Methods**

- `evaluate(self, octx: 'ObserverContext') -> 'ObserverEvent | None'`

### `FailureRateAbove`

*class* — bases: `Rule`

Fire when the fraction of failed runs in ``window`` exceeds ``threshold``.

```python
FailureRateAbove(threshold: 'float', *, window: 'str' = '-1h') -> 'None'
```

**Methods**

- `evaluate(self, octx: 'ObserverContext') -> 'ObserverEvent | None'`

### `CostSpike`

*class* — bases: `Rule`

Fire when total spend across runs in ``window`` reaches ``usd``.

```python
CostSpike(usd: 'float', *, window: 'str' = '-5m') -> 'None'
```

**Methods**

- `evaluate(self, octx: 'ObserverContext') -> 'ObserverEvent | None'`

### `StuckRun`

*class* — bases: `Rule`

Fire when a run has been ``running`` for longer than ``seconds``.

```python
StuckRun(seconds: 'float') -> 'None'
```

**Methods**

- `evaluate(self, octx: 'ObserverContext') -> 'ObserverEvent | None'`

### `dashboard_state`

*function*

```python
dashboard_state(store: 'Store', *, org_id: 'str' = 'local', now: 'datetime | None' = None, event_window: 'str' = '-24h') -> 'dict[str, JSONValue]'
```

Build the JSON the dashboard renders — pipelines, runs, cost, observer feed.

Every value comes from the scrubbed Store surface; nothing here reaches outside
the persisted, redacted records.

### `serve_dashboard`

*function*

```python
serve_dashboard(store: 'Store', *, org_id: 'str' = 'local', port: 'int' = 7878) -> 'ThreadingHTTPServer'
```

Create a loopback-bound dashboard server (caller runs ``serve_forever``).

Always binds :data:`LOOPBACK` — the dashboard is never reachable off-host.

### `ClaudeCodeAgent`

*class* — bases: `BaseModel`

A Claude Code subagent: YAML front-matter + a system-prompt body.

**Methods**

- `to_markdown(self) -> 'str'` — Render the ``.claude/agents/<name>.md`` file (front-matter + body).

### `ClaudeCodeSkill`

*class* — bases: `BaseModel`

A Claude Code skill wrapper — a Definition as an invocable slash-command.

**Methods**

- `to_markdown(self) -> 'str'` — Render the ``.claude/skills/<name>/SKILL.md`` file.

### `definition_to_cc_agent`

*function*

```python
definition_to_cc_agent(definition: 'Definition') -> 'ClaudeCodeAgent'
```

Render a Definition into a :class:`ClaudeCodeAgent` (no secrets emitted).

### `export_claude_code`

*function*

```python
export_claude_code(definition: 'Definition', project_dir: 'Path', *, skill: 'bool' = False) -> 'list[Path]'
```

Write the CC subagent (and optional skill) under ``project_dir/.claude``.

Returns the written paths. Always writes ``.claude/agents/<name>.md``; with
``skill=True`` also writes ``.claude/skills/<name>/SKILL.md``. Carries no secrets.

### `map_tools`

*function*

```python
map_tools(definition: 'Definition') -> 'list[str]'
```

The subagent's ``tools`` allowlist: union of agent tools + MCP tool names.

MCP-exposed tools render as ``mcp__<server>__<tool>`` (CC's MCP tool naming). The
result is sorted and de-duplicated for a deterministic file. **No ``auth`` /secret
reference is ever emitted** — only tool names.

### `model_alias`

*function*

```python
model_alias(model: 'str | list[str] | None') -> 'str'
```

Map a Definition's pinned model to a CC alias (``opus``/``sonnet``/``haiku``).

A list (model-universal with preferences) resolves on its first entry; ``mock``,
an unrecognised id, or ``None`` resolves to ``inherit`` (the platform picks).

### `ExecState`

*class* — bases: `str`, `Enum`

str(object='') -> str
str(bytes_or_buffer[, encoding[, errors]]) -> str

Create a new string object from the given object. If encoding or
errors is specified, then the object must expose a data buffer
that will be decoded using the given encoding and error handler.
Otherwise, returns the result of object.__str__() (if defined)
or repr(object).
encoding defaults to 'utf-8'.
errors defaults to 'strict'.

Members: `RUNNING` = `'running'`, `DONE` = `'done'`, `FAILED` = `'failed'`, `NEEDS_RETRY` = `'needs_retry'`

### `RetryPolicy`

*class*

Exponential backoff: ``delay = min(base * factor**attempt, max_delay)``.

```python
RetryPolicy(max_attempts: 'int' = 3, base_delay: 'float' = 0.0, factor: 'float' = 2.0, max_delay: 'float' = 30.0) -> None
```

**Methods**

- `delay_for(self, attempt: 'int') -> 'float'`

### `ItemResult`

*class*

Partial-success unit surfaced in batch results.

```python
ItemResult(item_id: 'str', status: 'ItemStatus', value: 'JSONValue' = None, error: 'str | None' = None, attempts: 'int' = 0) -> None
```

### `ItemStatus`

*class* — bases: `str`, `Enum`

str(object='') -> str
str(bytes_or_buffer[, encoding[, errors]]) -> str

Create a new string object from the given object. If encoding or
errors is specified, then the object must expose a data buffer
that will be decoded using the given encoding and error handler.
Otherwise, returns the result of object.__str__() (if defined)
or repr(object).
encoding defaults to 'utf-8'.
errors defaults to 'strict'.

Members: `OK` = `'ok'`, `DEAD` = `'dead'`

### `Workflow`

*class*

A versioned pipeline of steps, run from a prompt and deployable as a unit.

```python
Workflow(prompt: 'str' = '', steps: 'list[Node] | None' = None, *, name: 'str' = 'workflow', runtime: 'AgentRuntime | None' = None, version: 'str' = '0.1') -> 'None'
```

**Methods**

- `check_types(self) -> 'None'` — Reject a type-incompatible adjacency at assembly.
- `run(self, prompt: 'str | None' = None, *, ctx: 'RunContext | None' = None, runtime: 'AgentRuntime | None' = None, resume: 'bool' = False) -> 'list[Output[JSONValue]]'`

### `Metric`

*class* — bases: `ABC`

A single scalar quality signal over one Output.

``name`` keys the metric in a :class:`Rubric` score vector; ``evaluate``
returns a float (convention: higher is better; presence/format metrics use
``1.0``/``0.0`` as a pass/fail).

**Methods**

- `evaluate(self, output: 'Output[JSONValue]') -> 'float'` — Score ``output`` to a float.

### `Rubric`

*class*

A named collection of metrics scored together into one vector.

```python
Rubric(metrics: 'Sequence[Metric]', *, name: 'str' = 'rubric')
```

**Methods**

- `score(self, output: 'Output[JSONValue]') -> 'dict[str, float]'` — Score ``output`` with every metric -> ``{metric.name: float}``.

### `Benchmark`

*class*

A rubric run over a fixed task set, aggregated to comparable scores.

Each task drives one :class:`~crawfish.run.Run` of the Definition; the rubric
scores each resulting Output; per-metric scores are aggregated (mean) into a
single comparable vector. Deterministic under ``MockRuntime``.

```python
Benchmark(rubric: 'Rubric', tasks: 'Sequence[Task]', *, name: 'str' = 'benchmark', inputs_for: 'Callable[[Task], dict[str, JSONValue]] | None' = None)
```

**Methods**

- `run(self, definition: 'Definition', ctx: 'RunContext', runtime: 'AgentRuntime') -> 'dict[str, float]'` — Execute ``definition`` on every task, aggregate rubric scores (mean).

### `output_number`

*function*

```python
output_number(*, field: 'str | None' = None, default: 'float' = 0.0) -> 'OutputNumber'
```

Factory: a metric that extracts a numeric from the Output value.

### `field_present`

*function*

```python
field_present(field: 'str') -> 'FieldPresent'
```

Factory: a metric that checks a field is present in the Output value.

### `is_nonempty`

*function*

```python
is_nonempty(*, field: 'str | None' = None) -> 'IsNonempty'
```

Factory: a metric that checks the Output value (or a field) is non-empty.

### `confidence_threshold`

*function*

```python
confidence_threshold(field: 'str', threshold: 'float') -> 'ConfidenceThreshold'
```

Factory: a metric that checks a field's confidence clears ``threshold``.

### `compare`

*function*

```python
compare(scores_a: 'dict[str, float]', scores_b: 'dict[str, float]') -> 'dict[str, float]'
```

Per-metric deltas ``b - a`` (candidate minus baseline).

Positive means the candidate improved on that metric; negative is a drop.
Metrics absent from a side are treated as ``0.0`` so vectors need not align.

### `is_regression`

*function*

```python
is_regression(baseline: 'dict[str, float]', candidate: 'dict[str, float]', *, tolerance: 'float' = 0.0) -> 'bool'
```

True if ``candidate`` is worse than ``baseline`` on any metric.

A metric regresses when its delta drops below ``-tolerance`` (so a small
``tolerance`` absorbs noise). Higher-is-better is assumed for every metric.

### `estimate_cost`

*function*

```python
estimate_cost(definition: 'Definition', *, items: 'int' = 1, model_prices: 'dict[str, float] | None' = None) -> 'CostEstimate'
```

Predict the dollar cost of running ``definition`` over ``items`` items.

Heuristic (deterministic, approximate): charge one run per agent per item,
priced from ``model_prices`` (defaults to :data:`DEFAULT_MODEL_PRICES`) by
each agent's resolved model id. Unknown model ids are treated as free so a
missing price never silently inflates the estimate — pass a fuller table for
sharper numbers.

### `CostEstimate`

*class* — bases: `BaseModel`

A dry-run cost preview for a Definition.

All figures are USD and approximate. ``per_item_usd`` is the predicted spend
for a single item across the whole team; ``total_usd`` scales that by the
item count. ``per_model`` breaks the total down by resolved model id so a
caller can see which model dominates the bill.

### `Budget`

*class*

A warn/stop spend policy.

``stop_usd`` is the hard ceiling; ``warn_usd`` (default 80% of stop) is the
soft line where callers should surface a warning. ``None`` for ``stop_usd``
means unbounded — every check is :attr:`BudgetState.OK`. Use :meth:`check`
for the soft signal and :meth:`as_cost_budget` to hand the orchestrator the
matching hard ceiling.

```python
Budget(stop_usd: 'float | None' = None, warn_usd: 'float | None' = None) -> None
```

**Methods**

- `as_cost_budget(self, *, spent_usd: 'float' = 0.0) -> 'CostBudget'` — Project the hard ceiling onto a :class:`CostBudget` for the runtime.
- `check(self, spent_usd: 'float') -> 'BudgetState'` — Classify ``spent_usd`` as ok / warn / stopped.

### `BudgetState`

*class* — bases: `str`, `Enum`

Where spend sits relative to a :class:`Budget`'s thresholds.

Members: `OK` = `'ok'`, `WARN` = `'warn'`, `STOPPED` = `'stopped'`

### `CostMeter`

*class*

A live spend accumulator checked against a :class:`Budget`.

Call :meth:`charge` as runs complete; :attr:`total_usd` is running spend,
:attr:`remaining_usd` is headroom to the hard stop, and :meth:`state`
reports the current :class:`BudgetState`.

```python
CostMeter(budget: 'Budget' = <factory>, total_usd: 'float' = 0.0) -> None
```

**Methods**

- `charge(self, amount_usd: 'float') -> 'BudgetState'` — Add ``amount_usd`` to running spend and return the resulting state.
- `state(self) -> 'BudgetState'`

### `spent_today`

*function*

```python
spent_today(store: 'Store', *, org_id: 'str' = 'local', run_ids: 'list[str] | None' = None, today: 'date | None' = None, now: 'datetime | None' = None) -> 'float'
```

Sum today's spend from the Store's run telemetry (UTC day).

Reads ``runtime.run`` / ``run.finish`` events that carry a cost field and a
``ts`` timestamp, keeping only those dated to ``today`` (defaults to the
current UTC date). ``run_ids`` narrows the scan; if omitted, the caller is
responsible for passing the runs to total (the Store seam is per-run, so
there is no cheap cross-run scan). Events without a usable timestamp are
counted, so a meter never silently undercounts.

### `inspect_run`

*function*

```python
inspect_run(store: 'Store', run_id: 'str', *, org_id: 'str' = 'local') -> 'RunReport'
```

Summarize a run from the Store's event ledger (``craw inspect <run>``).

Derives status / total cost / latency from the ``span`` events Run emits
(``run.start`` / ``run.finish``), accumulates cost from ``runtime.run``
telemetry, and builds an ordered transcript + tool-call list. Performs no
live model call — pure read over append-only events.

### `tail_events`

*function*

```python
tail_events(store: 'Store', run_id: 'str', *, after_seq: 'int' = 0, org_id: 'str' = 'local') -> 'list[dict[str, JSONValue]]'
```

Return events after ``after_seq`` — the poll primitive for ``craw logs``.

The Store's ledger is append-only and ordered, so a caller polls with the
sequence index of the last event it saw and gets only what is new. ``seq`` is
a 0-based positional index into the ordered ledger; ``after_seq=0`` skips the
first event. Pass ``after_seq=-1`` (or any negative value) to get everything.

### `format_report`

*function*

```python
format_report(report: 'RunReport') -> 'str'
```

Render a concise human-readable summary for ``craw inspect`` output.

### `RunReport`

*class* — bases: `BaseModel`

A summary of a single run, derived from the Store's event ledger.

``found`` is ``False`` for an unknown run (no events) — callers get a clearly
empty report rather than a crash.

### `EvalCase`

*class* — bases: `BaseModel`

A captured run made reusable: its inputs, the produced output, and an
optional human label (expected output / judgment).

### `GoldenSet`

*class*

A named, versioned set of labeled cases, persisted through the ``Store``.

```python
GoldenSet(store: 'Store', name: 'str', *, org_id: 'str' = 'local', version: 'str' = '0.1') -> 'None'
```

**Methods**

- `add(self, case: 'EvalCase') -> 'None'`
- `cases(self) -> 'list[EvalCase]'`
- `get(self, case_id: 'str') -> 'EvalCase | None'`
- `label(self, case_id: 'str', label: 'JSONValue') -> 'None'`

### `LLMJudge`

*class*

A Definition-backed grader: an agent scores an output against criteria.

Complements coded ``Metric``s. Deterministic under a mock/replay runtime.

```python
LLMJudge(definition: 'Definition', runtime: 'AgentRuntime', *, name: 'str' = 'llm_judge') -> 'None'
```

**Methods**

- `grade(self, output: 'Output[JSONValue]', ctx: 'RunContext', *, criteria: 'str' = 'quality') -> 'float'`

### `capture_case`

*function*

```python
capture_case(*, inputs: 'dict[str, JSONValue]', output: 'Output[JSONValue]', transcript: 'list[JSONValue] | None' = None, label: 'JSONValue' = None) -> 'EvalCase'
```

Capture a real run (inputs + output [+ transcript]) as an eval case.

### `grade_output`

*function*

```python
grade_output(output: 'Output[JSONValue]', ctx: 'RunContext', *, rubric: 'Rubric | None' = None, judges: 'list[LLMJudge] | None' = None) -> 'dict[str, float]'
```

Combine coded-metric scores and LLM-judge grades into one score dict.

### `save_baseline`

*function*

```python
save_baseline(store: 'Store', name: 'str', scores: 'dict[str, float]', *, org_id: 'str' = 'local') -> 'None'
```

### `load_baseline`

*function*

```python
load_baseline(store: 'Store', name: 'str', *, org_id: 'str' = 'local') -> 'dict[str, float] | None'
```

### `gate_against_baseline`

*function*

```python
gate_against_baseline(store: 'Store', name: 'str', candidate: 'dict[str, float]', *, tolerance: 'float' = 0.0, org_id: 'str' = 'local') -> 'bool'
```

True if ``candidate`` passes (no regression vs the stored baseline).

### `Registry`

*class*

Collects discovered units; first registration of a (kind, name) wins.

```python
Registry(units: 'dict[tuple[str, str], UnitRef]' = <factory>) -> None
```

**Methods**

- `discover_entry_points(self) -> 'None'`
- `discover_local(self, project_dir: 'str | Path', paths: 'dict[str, str] | None' = None) -> 'None'`
- `get(self, kind: 'str', name: 'str') -> 'UnitRef | None'`
- `of_kind(self, kind: 'str') -> 'list[UnitRef]'`
- `register(self, ref: 'UnitRef') -> 'bool'`

### `UnitRef`

*class*

A discovered unit: its kind, name, and where it came from.

```python
UnitRef(kind: 'str', name: 'str', origin: 'str', target: 'str') -> None
```

### `ProfileConfig`

*class* — bases: `BaseModel`

One named profile: which runtime backend, plus free-form settings.

### `ProjectManifest`

*class* — bases: `BaseModel`

Parsed ``crawfish.toml``.

**Methods**

- `resolve_profile(self, name: 'str | None' = None) -> 'ProfileConfig'` — Resolve a profile by name, falling back to the manifest default and

### `ProjectPaths`

*class* — bases: `BaseModel`

Where each kind of unit lives, relative to the project root.

Defaults are the canonical layout; a project may relocate any folder via
``crawfish.toml [project.paths]`` and discovery follows the override.

**Methods**

- `as_discovery_map(self) -> 'dict[str, str]'` — ``{unit-kind: subdir}`` for the registry's local folder scan.

### `load_manifest`

*function*

```python
load_manifest(project_dir: 'str | Path' = '.') -> 'ProjectManifest'
```

Load ``crawfish.toml`` from ``project_dir``; return defaults if absent.

### `DoctorFinding`

*class* — bases: `BaseModel`

One health observation. ``level`` is ``ok`` | ``info`` | ``warn`` | ``error``.

### `DoctorReport`

*class* — bases: `BaseModel`

!!! abstract "Usage Documentation"
    Models

A base class for creating Pydantic models.

Attributes:
    __class_vars__: The names of the class variables defined on the model.
    __private_attributes__: Metadata about the private attributes of the model.
    __signature__: The synthesized `__init__` [`Signature`][inspect.Signature] of the model.

    __pydantic_complete__: Whether model building is completed, or if there are still undefined fields.
    __pydantic_core_schema__: The core schema of the model.
    __pydantic_custom_init__: Whether the model has a custom `__init__` function.
    __pydantic_decorators__: Metadata containing the decorators defined on the model.
        This replaces `Model.__validators__` and `Model.__root_validators__` from Pydantic V1.
    __pydantic_generic_metadata__: A dictionary containing metadata about generic Pydantic models.
        The `origin` and `args` items map to the [`__origin__`][genericalias.__origin__]
        and [`__args__`][genericalias.__args__] attributes of [generic aliases][types-genericalias],
        and the `parameter` item maps to the `__parameter__` attribute of generic classes.
    __pydantic_parent_namespace__: Parent namespace of the model, used for automatic rebuilding of models.
    __pydantic_post_init__: The name of the post-init method for the model, if defined.
    __pydantic_root_model__: Whether the model is a [`RootModel`][pydantic.root_model.RootModel].
    __pydantic_serializer__: The `pydantic-core` `SchemaSerializer` used to dump instances of the model.
    __pydantic_validator__: The `pydantic-core` `SchemaValidator` used to validate instances of the model.

    __pydantic_fields__: A dictionary of field names and their corresponding [`FieldInfo`][pydantic.fields.FieldInfo] objects.
    __pydantic_computed_fields__: A dictionary of computed field names and their corresponding [`ComputedFieldInfo`][pydantic.fields.ComputedFieldInfo] objects.

    __pydantic_extra__: A dictionary containing extra values, if [`extra`][pydantic.config.ConfigDict.extra]
        is set to `'allow'`.
    __pydantic_fields_set__: The names of fields explicitly set during instantiation.
    __pydantic_private__: Values of private attributes set on the model instance.

**Methods**

- `add(self, level: 'str', message: 'str') -> 'None'`
- `text(self) -> 'str'`

### `diagnose`

*function*

```python
diagnose(project_dir: 'str | Path' = '.') -> 'DoctorReport'
```

Inspect ``project_dir`` and return a structured structure-health report.

### `Cron`

*class*

A minimal 5-field cron evaluator (``m h dom mon dow``).

Supports ``*``, ``*/n`` steps, ``a,b`` lists, ``a-b`` ranges, and exact values
— enough for the deploy/observer polling cases (``0 8 * * *``, ``*/5 * * * *``).
Day-of-week is ``0-6`` with Sunday = 0. When both day-of-month and day-of-week
are restricted, a tick matches if *either* matches (standard cron semantics).
Evaluation is at minute resolution.

```python
Cron(expr: 'str') -> 'None'
```

**Methods**

- `matches(self, dt: 'datetime') -> 'bool'` — True if ``dt`` (truncated to the minute) satisfies the schedule.
- `next_after(self, dt: 'datetime') -> 'datetime'` — The first minute strictly after ``dt`` that matches (searches ≤366d).

### `CronSchedule`

*class*

A minimal 5-field cron evaluator (``m h dom mon dow``).

Supports ``*``, ``*/n`` steps, ``a,b`` lists, ``a-b`` ranges, and exact values
— enough for the deploy/observer polling cases (``0 8 * * *``, ``*/5 * * * *``).
Day-of-week is ``0-6`` with Sunday = 0. When both day-of-month and day-of-week
are restricted, a tick matches if *either* matches (standard cron semantics).
Evaluation is at minute resolution.

```python
CronSchedule(expr: 'str') -> 'None'
```

**Methods**

- `matches(self, dt: 'datetime') -> 'bool'` — True if ``dt`` (truncated to the minute) satisfies the schedule.
- `next_after(self, dt: 'datetime') -> 'datetime'` — The first minute strictly after ``dt`` that matches (searches ≤366d).

### `scaffold_project`

*function*

```python
scaffold_project(name: 'str' = 'crawfish-app') -> 'Path'
```

Create a self-contained project directory and return its path.

### `resolve_secret`

*function*

```python
resolve_secret(ref: 'str | None', env: 'Mapping[str, str] | None' = None) -> 'str | None'
```

Resolve a secret reference (env-var name) to its value, or None if unset.

### `load_env`

*function*

```python
load_env(path: 'str | Path' = '.env') -> 'dict[str, str]'
```

Parse a gitignored ``.env`` (KEY=VALUE lines). Values are never logged.

### `SecretManager`

*class*

Maps nodes to the secrets they declare and resolves them least-privilege.

```python
SecretManager(env: 'Mapping[str, str] | None' = None) -> 'None'
```

**Methods**

- `declare(self, node_id: 'str', refs: 'Iterable[str]') -> 'None'`
- `for_node(self, node_id: 'str') -> 'dict[str, str]'` — Return only the secrets this node declared (and that exist).

### `ScrubbingStore`

*class*

A ``Store`` wrapper that redacts secrets/PII before any write.

Wrap a backing Store so transcripts, outputs, and telemetry are redacted on the
way in — the persisted ledger never contains a raw credential.

```python
ScrubbingStore(inner: 'Store', secrets: 'Iterable[str]' = ()) -> 'None'
```

**Methods**

- `append_event(self, run_id: 'str', event: 'dict[str, JSONValue]', *, org_id: 'str' = 'local') -> 'None'`
- `claim_idempotency(self, key: 'str', *, org_id: 'str' = 'local') -> 'bool'`
- `close(self) -> 'None'`
- `delete_record(self, kind: 'str', id: 'str', *, org_id: 'str' = 'local') -> 'None'`
- `events(self, run_id: 'str', *, org_id: 'str' = 'local') -> 'list[dict[str, JSONValue]]'`
- `get_record(self, kind: 'str', id: 'str', *, org_id: 'str' = 'local') -> 'dict[str, JSONValue] | None'`
- `kv_get(self, namespace: 'str', key: 'str', *, org_id: 'str' = 'local') -> 'JSONValue | None'`
- `kv_set(self, namespace: 'str', key: 'str', value: 'JSONValue', *, org_id: 'str' = 'local') -> 'None'`
- `list_records(self, kind: 'str', *, org_id: 'str' = 'local') -> 'list[dict[str, JSONValue]]'`
- `put_record(self, kind: 'str', id: 'str', data: 'dict[str, JSONValue]', *, org_id: 'str' = 'local') -> 'None'`

### `redact`

*function*

```python
redact(text: 'str', secrets: 'Iterable[str]' = ()) -> 'str'
```

Replace known secret values and credential/PII patterns with a marker.

### `read_capabilities`

*function*

```python
read_capabilities(project_dir: 'str | Path') -> 'Capabilities'
```

Read a package's declared capabilities from ``crawfish.toml [capabilities]``.

### `Capabilities`

*class*

What a package/unit declares it needs (the consent surface).

```python
Capabilities(*, secrets: 'list[str] | None' = None, egress: 'list[str] | None' = None) -> 'None'
```

**Methods**

- `summary(self) -> 'str'`

### `snapshot_match`

*function*

```python
snapshot_match(path: 'str | Path', value: 'JSONValue', *, update: 'bool' = False) -> 'bool'
```

Compare ``value`` against the snapshot at ``path``.

Writes the snapshot and returns ``True`` when it is missing or ``update`` is
set (the accept-new-baseline path). Otherwise returns ``True`` on a match and
``False`` on a diff — the caller decides how to surface a regression.

### `assert_snapshot`

*function*

```python
assert_snapshot(path: 'str | Path', value: 'JSONValue', *, update: 'bool' = False) -> 'None'
```

Like :func:`snapshot_match` but raise :class:`SnapshotMismatch` on a diff.

The error carries a readable line-by-line diff (expected snapshot vs actual).

### `run_fixtures`

*function*

```python
run_fixtures(fixtures_dir: 'str | Path', definition: 'Definition', runtime: 'AgentRuntime', *, ctx_factory: 'Callable[[], RunContext] | None' = None) -> 'list[FixtureResult]'
```

Run every ``*.json`` fixture in ``fixtures_dir`` against ``definition``.

Each fixture is ``{"inputs": {...}, "expected": <optional>}``. The Definition
runs once per fixture (via :class:`~crawfish.run.Run`); a fixture passes when
it executes cleanly and — if ``expected`` is given — the Output value matches.
Fixtures are processed in sorted filename order for stable reporting.

``ctx_factory`` is an optional zero-arg callable returning a fresh
:class:`~crawfish.core.context.RunContext` per fixture (defaults to an
in-memory SQLite-backed context).

### `assert_rubric`

*function*

```python
assert_rubric(output: 'Output[JSONValue]', rubric: 'Rubric', thresholds: 'dict[str, float]') -> 'None'
```

Score ``output`` and assert each thresholded metric clears its floor.

A :class:`~crawfish.metrics.Rubric` threshold becomes a CI assertion: keys in
``thresholds`` name metrics (by ``Metric.name``) that must score ``>=`` their
value. Raise :class:`RubricThresholdError` listing every metric that fell
short (or a threshold naming a metric absent from the rubric).

### `replaying`

*function*

```python
replaying(inner_runtime: 'AgentRuntime', cassette_dir: 'str | Path', *, record: 'bool' = False) -> 'RecordReplayRuntime'
```

Wrap ``inner_runtime`` so tests replay cassettes instead of calling live.

With ``record=False`` (the CI default) a cache miss raises
:class:`~crawfish.runtime.replay.CassetteMiss`, guaranteeing no live model
call. Set ``record=True`` once to capture cassettes from ``inner_runtime``.

### `generate_containerfile`

*function*

```python
generate_containerfile(manifest: 'ProjectManifest', *, python_version: 'str' = '3.11', lock_present: 'bool' = True) -> 'str'
```

Generate deterministic Containerfile text for ``manifest``.

The output installs dependencies (``pip install`` of the project, plus the
pinned ``crawfish.lock`` when ``lock_present``), copies the project tree, and
sets the entrypoint to ``craw run``. The string is stable for a given input
so builds are reproducible.

### `plan_build`

*function*

```python
plan_build(manifest: 'ProjectManifest', *, python_version: 'str' = '3.11', lock_present: 'bool' = True) -> 'BuildPlan'
```

Build a :class:`BuildPlan` from ``manifest``.

The image name/tag is derived as ``name:version`` from the manifest.

### `write_containerfile`

*function*

```python
write_containerfile(manifest: 'ProjectManifest', dest: 'str | Path', *, python_version: 'str' = '3.11', lock_present: 'bool' = True) -> 'Path'
```

Write the generated Containerfile to ``dest`` and return its path.

If ``dest`` is a directory, the file is written as ``dest/Containerfile``.

### `BuildPlan`

*class* — bases: `BaseModel`

Summary of what ``craw build`` will produce for a project.

### `Trigger`

*class* — bases: `ABC`

Base for anything that can fire a pipeline run.

**Methods**

- `describe(self) -> 'dict[str, JSONValue]'` — Return a JSON-serialisable description of this trigger.

### `CronTrigger`

*class* — bases: `Trigger`

Fire a run on a cron ``schedule``.

```python
CronTrigger(schedule: 'str') -> 'None'
```

**Methods**

- `describe(self) -> 'dict[str, JSONValue]'` — Round-trippable description: kind + schedule.

### `WebhookTrigger`

*class* — bases: `Trigger`

Fire a run from an inbound HTTP POST to ``path``.

``secret_ref`` is the *name* of an environment variable holding the shared
secret, never the secret value itself, so it is safe to serialise.

```python
WebhookTrigger(path: 'str', secret_ref: 'str | None' = None) -> 'None'
```

**Methods**

- `describe(self) -> 'dict[str, JSONValue]'` — Round-trippable description; carries the secret *reference* only.

### `verify_webhook`

*function*

```python
verify_webhook(secret: 'str', payload: 'bytes', signature: 'str') -> 'bool'
```

Verify an inbound webhook ``signature`` against ``payload``.

Computes ``HMAC-SHA256(secret, payload)`` as lowercase hex and compares it to
``signature`` in constant time to avoid timing oracles. The caller resolves
``secret`` from the trigger's ``secret_ref`` environment variable.

### `Stability`

*class* — bases: `str`, `Enum`

The stability tier of a public API surface.

``str`` mix-in so a tier round-trips through JSON and config without conversion.

Members: `STABLE` = `'stable'`, `EXPERIMENTAL` = `'experimental'`, `DEPRECATED` = `'deprecated'`

### `stable`

*function*

```python
stable(obj: 'T') -> 'T'
```

Tag ``obj`` as :attr:`Stability.STABLE`. Behavior-preserving no-op otherwise.

### `experimental`

*function*

```python
experimental(obj: 'T') -> 'T'
```

Tag ``obj`` as :attr:`Stability.EXPERIMENTAL`. Behavior-preserving no-op.

### `deprecated`

*function*

```python
deprecated(*, since: 'str', removed_in: 'str', use: 'str | None' = None) -> 'Callable[[Callable[..., T]], Callable[..., T]]'
```

Mark a callable :attr:`Stability.DEPRECATED` and warn on every call.

Args:
    since: Version in which the deprecation took effect (e.g. ``"0.4"``).
    removed_in: Version in which the callable is scheduled for removal.
    use: Optional name of the replacement API, surfaced in the warning message.

The returned wrapper is behavior-preserving: it forwards all arguments to the
wrapped callable and returns its result, preserving metadata via
:func:`functools.wraps`. A :class:`DeprecationWarning` is emitted on each call.

### `stability_of`

*function*

```python
stability_of(obj: 'object') -> 'Stability'
```

Read the stability tier tagged on ``obj``.

Untagged objects default to :attr:`Stability.EXPERIMENTAL`: nothing is stable until
it is explicitly promoted with :func:`stable`.

### `is_breaking`

*function*

```python
is_breaking(old: 'str', new: 'str') -> 'bool'
```

Return ``True`` when going from ``old`` to ``new`` is a major (breaking) bump.

Follows semver: a change is breaking when the major component increases. This is the
coarse signal used by tooling to require a migration note.

### `EgressBroker`

*class*

Mediates network egress against a capability allowlist (runtime enforcement).

```python
EgressBroker(allow: 'Iterable[str]' = ()) -> 'None'
```

**Methods**

- `guard(self, host: 'str') -> 'None'`
- `permitted(self, host: 'str') -> 'bool'`

### `EgressDenied`

*class* — bases: `RuntimeError`

Raised when host-side code attempts egress to a non-allowlisted host.

### `run_out_of_process`

*function*

```python
run_out_of_process(func: 'Callable[..., R]', *args: 'object', timeout: 'float' = 30.0) -> 'R'
```

Execute ``func`` in a separate process and return its result.

The function must be importable (picklable). Host-side tool code runs here so it
never shares the engine's process memory or credentials.

