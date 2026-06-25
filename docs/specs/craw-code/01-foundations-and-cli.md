# craw code — Implementation Spec: Foundations & CLI (M0, M1)

This spec elaborates the M0 ("Trust & test foundations") and M1 ("CLI legibility +
schema reflection") halves of [`docs/rfcs/0001-craw-code.md`](../../rfcs/0001-craw-code.md),
folding in the §12 Hardening gap review. `craw code` puts an LLM in the author's chair,
which collapses the framework's old "the author is a trusted human" assumption
(`docs/reference/definition.md`: "Compiling imports `definition.py` … this is
authoring-time trusted code"). Everything here is *wiring existing seams* — the
[`Jail`](../../../packages/crawfish/src/crawfish/jail.py) (ADR 0016),
[`provenance.py`](../../../packages/crawfish/src/crawfish/provenance.py),
[`assert_build_safe`](../../../packages/crawfish/src/crawfish/build.py),
[`ScrubbingStore`](../../../packages/crawfish/src/crawfish/secrets.py),
[`ObserverSurface`](../../../packages/crawfish/src/crawfish/observe.py),
[`estimate_cost`](../../../packages/crawfish/src/crawfish/cost.py),
[`RecordReplayRuntime`](../../../packages/crawfish/src/crawfish/runtime/replay.py) — into
the new authoring path, never a second execution path. The Definition of Done is the
repo bar: `ruff` + `mypy --strict` clean, `pytest` green and deterministic (no live model
calls — `MockRuntime` / cassettes), the security spine upheld, security sign-off before
`Done`, and the demo (`demo/triage-bot/`) exercising it end to end.

## Build & dependency order

This cluster has one keystone and a short critical path. Build in this order:

1. **CRA-266** (provenance + taint) — *keystone.* It defines the per-file provenance row
   and the `authored_by` / `source_tainted` identity that every later gate keys on. It
   extends the existing [`Provenance`](../../../packages/crawfish/src/crawfish/provenance.py)
   record from per-Definition to per-file. Nothing else in M0/M1 lands first.
2. **CRA-267** (jailed compile) — depends on CRA-266 for the taint label it propagates out
   of the jail into the provenance row.
3. **CRA-268** (record/replay harness) — depends on CRA-266 + CRA-267 so the golden
   authoring session can assert provenance + jail outcomes deterministically.
4. **M1 contracts first, verbs second.** CRA-269 (schema negotiation) and CRA-270 (error
   envelope) are the parsing/recovery substrate every other verb emits through; build them
   before the verbs. Then CRA-243 (audit existing `--json`), then CRA-244 (`describe`),
   then its dependents CRA-271 (redaction), CRA-274 (bounded reflection). CRA-272
   (assembly gate in `run`/`sync`), CRA-273 (`estimate`), and CRA-275 (org_id threading)
   layer on top and depend on CRA-269 + CRA-270 for their envelopes.

Dependency sketch:

```text
CRA-266 ──▶ CRA-267 ──▶ CRA-268
   │
   └─(taint feeds)─▶ CRA-271 redaction, CRA-272 gate

CRA-269 ─┐
CRA-270 ─┼─▶ CRA-243 ─▶ CRA-244 ─▶ CRA-271
         │                     └─▶ CRA-274
         ├─▶ CRA-272
         ├─▶ CRA-273
         └─▶ CRA-275  (threads through every verb above)
```

---

## M0 — Trust & test foundations

### CRA-266 — Stamp authorship provenance on every component and carry it as taint
**Milestone:** M0 · **Priority:** Urgent (KEYSTONE) · **Depends on:** none
**Context** — The framework records provenance per *generated Definition* today
([`Provenance`](../../../packages/crawfish/src/crawfish/provenance.py): `artifact_sha`,
`generated_by`, `source_tainted`, persisted via `ProvenanceLedger` on the `Store` seam).
But `craw code` authors at *file* granularity — a single edit to `tools/notify.py` or
`policies/guard.py` — and nothing distinguishes a human-written file from an
agent-written one, nor records whether the authoring agent was steered by fluid
(untrusted) data it had read. Without this, no later gate (CRA-267 jail, CRA-271
redaction, CRA-272 assembly gate, the M6 promotion gate) can fail closed on
agent-authored-under-injection code, because it cannot tell what authored a file.

**Design** — Add a **per-file provenance row** keyed by `(component_path, content_sha)`,
written through the `Store` protocol (never a concrete backend), carrying `authored_by`
(`"human"` | `"craw-code"` | other loop id), `source_tainted: bool`, and the
`TaintSet` (`crawfish.jail.TaintSet`, the `frozenset[str]` taint-label set; the canonical
label is `crawfish.jail.FLUID_TAINT == "fluid"`). Reuse the existing
`PROVENANCE_RECORD_KIND` ledger plumbing but add a new record kind
`FILE_PROVENANCE_RECORD_KIND = "file_provenance"` so per-Definition provenance is
untouched. Fold `authored_by` into **content identity** by recording it alongside the
file's content sha (the same sha `load_definition` computes over directory files, with
`.crawfish`/`.claude`/`uv.lock`/etc. excluded — see `docs/reference/definition.md`); the
provenance row is *adjacent to* identity, not mixed into the sha itself (the sha stays a
pure content hash so a directory and its installed copy still compile byte-identical).
When the authoring loop writes a file while holding fluid context, the row is stamped
`source_tainted=True` and carries `FLUID_TAINT` — this is **taint rule 9** (aggregate
taint is the union, monotonic, dropped only by an audited `declassify`): a file authored
under fluid context stays tainted across every later boundary. Emit a `METRIC` emission
(`metric="file.authored"`, `tainted=source_tainted`) so the dashboard and ledger see the
authoring event, exactly as `record_provenance` does today.

**Interface**

```python
# crawfish/provenance.py  (extends existing module)
FILE_PROVENANCE_RECORD_KIND = "file_provenance"

@dataclass(frozen=True)
class FileProvenance:
    component_path: str        # repo-relative, e.g. "tools/notify.py"
    content_sha: str           # sha of the file bytes (identity-adjacent)
    authored_by: str           # "human" | "craw-code" | <loop id>
    source_tainted: bool = False
    taint: frozenset[str] = frozenset()   # crawfish.jail.TaintSet
    provenance_id: str = field(default_factory=new_id)

def record_file_provenance(
    path: str, content_sha: str, *, store: Store, authored_by: str,
    source_tainted: bool = False, taint: frozenset[str] = frozenset(),
    org_id: str = "local", emit_event: bool = True,
) -> FileProvenance: ...

def file_provenance(path: str, content_sha: str, *, store: Store,
                    org_id: str = "local") -> FileProvenance | None: ...

def component_tainted(path: str, content_sha: str, *, store: Store,
                      org_id: str = "local") -> bool:
    """True iff the recorded provenance for this file carries any taint label."""
```

`--json` shape (consumed by `craw code describe`/`sync`, versioned per CRA-269):

```json
{
  "schema": "craw.code.provenance.v1",
  "component": "tools/notify.py",
  "content_sha": "ab12…",
  "authored_by": "craw-code",
  "source_tainted": true,
  "taint": ["fluid"]
}
```

Exit codes: `0` ok. (This issue ships a library + ledger row; verbs surface it.)

**Acceptance criteria**
- [ ] `record_file_provenance` persists one row per `(component_path, content_sha)` via
  the `Store` protocol, carrying `org_id`.
- [ ] A file authored while the loop holds fluid context is stamped `source_tainted=True`
  and carries `FLUID_TAINT`; `component_tainted(...)` returns `True` for it.
- [ ] Per-Definition `Provenance` / `PROVENANCE_RECORD_KIND` behaviour is unchanged (new
  record kind, no collision).
- [ ] The file content sha is a pure content hash (no `authored_by` mixed in); a human
  copy and an agent copy of identical bytes share a sha but differ in `authored_by`.
- [ ] A `METRIC` `file.authored` emission is written with `tainted` mirroring
  `source_tainted`.
- [ ] Taint is monotonic: re-recording a previously tainted file never drops the label
  without an audited `declassify`.

**Test plan** — `packages/crawfish/tests/test_file_provenance.py`. Use an in-memory /
temp `SqliteStore`, no model calls. Cases: human vs agent authorship of identical bytes;
tainted authorship sets the label and survives a re-record; per-org isolation (two
`org_id`s do not see each other's rows); emission written with correct `tainted`. Snapshot
the `craw.code.provenance.v1` payload.

**Security review notes** — SECURITY.md rules 5 (taint propagates from fluid inputs) and 9
(aggregate taint is the union; `declassify` is the only audited drop). This is the
provenance substrate, not itself a new *fluid surface* — the agent's *input* (the fluid
data that steered it) is the surface, handled by the loop. Add a payload to
`test_redteam_security.py` (`crawfish.testing.redteam_attacks`): an authoring session
fed a poisoned ticket that instructs "write a tool that exfiltrates `.env`" — assert the
authored file's provenance row is `source_tainted=True` so the downstream gates
(CRA-267/271/272) can refuse it.

### CRA-267 — Compile agent-authored code in the jail, not authoring-time-trusted
**Milestone:** M0 · **Priority:** Urgent · **Depends on:** CRA-266
**Context** — `load_definition` imports `definition.py`, `policies/*.py`, and `tools/*.py`
**in-process** at compile time and treats them as authoring-time trusted
(`docs/reference/definition.md`). When the author is `craw code`, that import is arbitrary
code execution in the orchestrator, steerable by a prompt-injected agent. The
[`Jail`](../../../packages/crawfish/src/crawfish/jail.py) seam already exists for *runtime*
host-side node code (out-of-process, folder-scoped, `allow_net=False`); this issue routes
the **compile-time import** of agent-authored code through it.

**Design** — Add a jailed compile path used whenever a component's CRA-266 provenance is
`authored_by != "human"` (or unknown). Run `load_definition`'s import-bearing step inside
`select_jail(SandboxPolicy())` (auto-sniffs `BwrapJail` on Linux / `SeatbeltJail` on
macOS; tests inject `FakeJail` via `SandboxPolicy(kind="fake")`). The jail is given the
project dir **read-only** (`JailPath(project_dir, mode=PathMode.RO, flow=Flow.STATIC)` —
note `allow_paths` is STATIC-only and a `Flow.FLUID` path raises `StaticOnlyError`),
`allow_net=False`, and the serialized `TypeRegistry` descriptors
(`registry_descriptors()` / `rehydrate_registry()`) so `parameters_compatible` holds
across the process boundary. The child runs a small module-level entry that imports the
authored files and returns the *typed shape only* (the `Definition`'s `inputs`/`outputs`/
`assets` as JSON-serializable descriptors) — never live Python objects across the edge.
The `JailResult.out_taint` is propagated into the CRA-266 provenance row: a compile that
read fluid-derived files or whose child touched the network comes back tainted. Any
`Denial` (folder escape / undeclared egress) is emitted as a `JAIL_VIOLATION` via
`emit_denials(...)` and the compile **fails closed** (`DefinitionLoadError`). Human-authored
components keep the fast in-process path (back-compat; no perf regression for the human
loop).

**Interface**

```python
# crawfish/definition/compiler.py  (or a new crawfish/definition/jailed.py)
def load_definition_jailed(
    path: str | Path, *, store: Store, org_id: str = "local",
    policy: SandboxPolicy | None = None,
) -> Definition:
    """Compile a project whose components may be agent-authored, importing the
    authored Python inside select_jail(). Fails closed (DefinitionLoadError) on any
    jail Denial. Propagates JailResult.out_taint into the file provenance row."""
```

`craw code run`/`sync` select the jailed path automatically when any component is
non-human-authored. CLI surfaces a jail violation through the `craw.error.v1` envelope
(CRA-270) with `code="jail_violation"`, `retryable=false`.

Exit codes: `0` ok; `2` compile/jail failure (a `DefinitionLoadError` or any `Denial`).

**Acceptance criteria**
- [ ] An agent-authored `tools/*.py` is imported inside `select_jail()`, project dir
  bound read-only, `allow_net=False`.
- [ ] A tool that tries to read outside the project (`/etc/shadow`) or open a socket
  produces a `Denial`, a `JAIL_VIOLATION` emission, and a fail-closed `DefinitionLoadError`.
- [ ] `JailResult.out_taint` is recorded onto the file's CRA-266 provenance row.
- [ ] Human-authored components still compile in-process (the existing path is untouched).
- [ ] `parameters_compatible` holds across the boundary (registry rehydrated), so type
  wiring checks behave identically to in-process compile.
- [ ] A FLUID-tagged `allow_paths` entry raises `StaticOnlyError` before any spawn.

**Test plan** — `packages/crawfish/tests/test_jailed_compile.py`, using
`SandboxPolicy(kind="fake")` and `FakeJail`'s `_Probe` program to simulate a child that
reads/writes/connects out of scope — no real process, no model call. Cases: clean
agent-authored compile returns the typed shape and records taint; folder-escape probe →
`Denial` + `JAIL_VIOLATION` + `DefinitionLoadError`; egress probe under `allow_net=False`
→ same; human-authored path unchanged; registry rehydration round-trip. Reuse the
existing jail conformance fixtures where present (`test_harness_conformance.py`).

**Security review notes** — SECURITY.md rule 5 (host-side code out-of-process, taint
propagates) and the §12.2 "agent-authored code compiled as trusted = arbitrary code
execution" gap. This is the central M0 enforcement. Add a `test_redteam_security.py`
payload: a poisoned-ticket authoring session that writes a `tools/*.py` whose import-time
top-level code shells out / opens a socket — assert it is jailed, denied, audited, and the
compile fails closed (it never executes in the orchestrator).

### CRA-268 — Deterministic record/replay harness for the authoring loop
**Milestone:** M0 · **Priority:** High · **Depends on:** CRA-266, CRA-267
**Context** — The agent-driven authoring loop calls a live model (`claude -p`), so it is
untestable under the repo's "no live model calls" bar without a record/replay layer.
Claude Code has file checkpointing but **no comprehensive built-in record/replay
test-doubles stdlib**, so the harness must build on the framework's own cassette infra
([`RecordReplayRuntime`](../../../packages/crawfish/src/crawfish/runtime/replay.py),
`CassetteMiss`, the execution-coordinate cassette key) plus `MockRuntime`. *(Verify /
build: there is no existing transcript-replay harness for the **authoring** loop — only
the per-run cassette layer; this issue builds the authoring-session layer on top.)*

**Design** — A golden **authoring-session fixture**: a recorded transcript of the agent's
tool calls (Read/Write/Edit on the seven component folders, and `Bash: craw … --json`
invocations) plus the model turns, replayed deterministically. Two doubles cooperate:
(1) the model turns replay through `RecordReplayRuntime` wrapping `MockRuntime` (the
existing cassette key already folds `org_id`, decode seed, and execution coordinate, so
replays are byte-stable); (2) the **tool-call transcript** replays through a new
`AuthoringSession` driver that, in replay mode, feeds recorded tool inputs/outputs in
order and asserts the agent's writes land in the right folders. For CI determinism, the
headless harness invokes `claude -p "<prompt>" --allowedTools …` with `--bare` (ignores
local `~/.claude` and project `.mcp.json`), or — preferably — drives the **Agent SDK**
(Python) collecting all messages at once, so the whole session is one deterministic
fixture. Record mode (developer-only, gated behind `--live`) captures a new golden;
replay mode is the default and never calls a live model. The harness asserts CRA-266
provenance rows and CRA-267 jail outcomes for each authored file, closing the loop.

**Interface**

```python
# crawfish/testing.py  (extends) or crawfish/authoring/session.py
class AuthoringSession:
    """Replays a recorded authoring transcript deterministically.

    mode="replay" (default): feed recorded tool I/O + model turns; no live call.
    mode="record" (dev-only, --live): capture a fresh golden transcript.
    """
    def __init__(self, transcript_path: str, *, runtime: AgentRuntime,
                 store: Store, org_id: str = "local",
                 mode: str = "replay") -> None: ...
    def run(self) -> "AuthoringResult": ...

@dataclass(frozen=True)
class AuthoringResult:
    files_written: tuple[str, ...]
    provenance: tuple[FileProvenance, ...]   # one per file (CRA-266)
    jail_denials: tuple[Denial, ...]         # any CRA-267 violations
```

Golden transcripts live under `packages/crawfish/tests/fixtures/authoring/<name>.json`.

**Acceptance criteria**
- [ ] A recorded authoring session replays byte-identically with no live model call.
- [ ] Model turns route through `RecordReplayRuntime` + `MockRuntime`; a missing cassette
  raises `CassetteMiss` (replay never silently hits the network).
- [ ] The harness asserts each authored file's CRA-266 provenance row and any CRA-267
  jail `Denial`.
- [ ] Record mode is reachable only under an explicit `--live` flag and is never invoked
  in the default test run.
- [ ] `--bare` (or the Agent SDK collect-all path) is used so CI ignores local
  `~/.claude` / `.mcp.json`. *(Verify: confirm the chosen path in CI config.)*

**Test plan** — `packages/crawfish/tests/test_authoring_harness.py`. One golden fixture
(`fixtures/authoring/triage_new_tool.json`) drives the agent authoring a new `tool`;
assert deterministic file set, provenance, and a clean (no-denial) jail outcome. A second
fixture replays a poisoned session and asserts the tainted provenance + denial path
(shared with CRA-267). All replay; zero live calls.

**Security review notes** — SECURITY.md "Review gate" (deterministic, offline behavioural
gate). This harness is the vehicle the red-team payloads run in — it must itself never
admit a live call in replay mode (fail closed to `CassetteMiss`). No new fluid surface of
its own, but it *exercises* CRA-266/267 payloads, so the poisoned golden fixture doubles
as the behavioural-gate driver for the M0 cluster.

---

## M1 — CLI legibility + schema reflection

### CRA-243 — Audit `craw` --json coverage and exit codes for agent use
**Milestone:** M1 · **Priority:** High · **Depends on:** CRA-269, CRA-270
**Context** — `craw code` drives the project by parsing `craw … --json` over Bash, so
every verb the agent calls must emit a versioned, snapshot-tested `--json` payload and a
**meaningful exit code**. Today `--json` exists on the optimization plane
(`_opt_print` emits `{"schema": "craw.<cmd>.v1", …}` via `_opt_schema`/`JSON_SCHEMA_VERSION`
in [`cli.py`](../../../packages/crawfish/src/crawfish/cli.py)) but coverage is uneven —
`run`, `dev`, `list`, `doctor`, `install` print human one-liners, and exit-code semantics
are ad hoc.

**Design** — Audit every `craw` verb the agent calls and bring each to a uniform contract:
(1) a `--json` mode emitting `{"schema": "craw.<cmd>.v<N>", …}` through a single shared
emitter (generalize `_opt_print` into a top-level `emit_json(command, payload)` that all
verbs use, not just the optimization plane); (2) a documented, stable **exit-code table**;
(3) errors emitted as the `craw.error.v1` envelope (CRA-270) on stderr, not a stray
traceback. Produce a coverage matrix (verb × has-`--json` × exit codes) as the deliverable
and close every gap. No behaviour change to the human one-liner mode — `--json` is purely
additive, as today.

**Interface**

```text
Exit-code table (uniform across craw verbs):
  0  success
  1  expected failure (regression gate tripped, consent declined, goal not met)
  2  usage / compile error (bad args, DefinitionLoadError, jail Denial)
  3  budget exceeded (a --budget ceiling halted the run)
  4  security rejection (assembly gate, fluid-to-static-sink, signing required) — non-retryable
```

```python
# crawfish/cli.py
def emit_json(command: str, payload: dict[str, object], *,
              seed: int = 0, org: str = "local") -> None:
    """The single --json emitter. Wraps payload in {"schema": craw.<cmd>.v<N>, …},
    sort_keys=True. Generalizes _opt_print's envelope to every verb."""
```

**Acceptance criteria**
- [ ] Every agent-facing verb (`run`, `dev`, `list`, `doctor`, `install`, plus the
  optimization plane and the new `craw code` verbs) emits a `craw.<cmd>.v<N>` payload under
  `--json`.
- [ ] Exit codes follow the table above and are asserted per verb.
- [ ] On error, `--json` mode emits a `craw.error.v1` envelope (CRA-270) on stderr, never
  a raw traceback.
- [ ] A coverage matrix is checked into the docs and snapshot-tested.
- [ ] Human one-liner mode is unchanged when `--json` is absent.

**Test plan** — `packages/crawfish/tests/test_cli_json_coverage.py`. For each verb, run it
under `--json` against the demo project on the `MockRuntime`, snapshot the payload, assert
the `schema` key and the exit code. Extend the existing `test_cli.py` / `test_cli_optimize.py`
rather than duplicating. No live calls.

**Security review notes** — SECURITY.md rule 4 (secrets never logged / in payloads): the
audit must confirm no `--json` payload carries a secret value or a destination — route any
borderline field through `ScrubbingStore` (this overlaps CRA-271). No new fluid surface;
the surface is the *output* legibility, but a stray secret in a payload is a leak, so the
snapshot tests double as a no-secret assertion.

### CRA-244 — Implement `craw code describe <component>` (typed IO reflection)
**Milestone:** M1 · **Priority:** High · **Depends on:** CRA-269, CRA-270, CRA-271, CRA-274
**Context** — The RFC's load-bearing addition: `describe` recovers the one genuine
ergonomic advantage a per-app MCP had (typed schemas surfaced to the model) while staying
filesystem-fresh, because it reflects the component **at call time** rather than caching a
registry. *(Honest note: the per-app-MCP-goes-stale argument is weaker than the RFC
implied — MCP supports `list_changed` and deferred tool-def loading, so a registry can
refresh mid-session. The CLI-first decision still holds on trust/transparency/
one-execution-path grounds, not on staleness alone.)*

**Design** — `craw code describe <component>` compiles the component (via the CRA-267
jailed path when agent-authored) and projects its **typed inputs/outputs only** as JSON,
resolved through `crawfish.typesystem`'s structural `TypeRegistry` (JSON-Schema export —
ADR 0002, structural not string equality). Each `Parameter` surfaces `name`, `type`
(resolved structural shape), and `flow` (`static`/`fluid`) — the latter is what lets the
agent honor the security spine (never wire a fluid input toward a static-only sink slot).
The projection is **typed-shape-only** (CRA-271 forbids secret refs / egress hosts / sink
destinations leaking into context) and is **bounded/cached by content sha** (CRA-274). The
payload is `craw.code.describe.v1` (CRA-269 negotiated, snapshot-tested).

**Interface**

```bash
craw code describe definitions/triage-bot --json [--org ID]
```

```json
{
  "schema": "craw.code.describe.v1",
  "component": "definitions/triage-bot",
  "kind": "definition",
  "content_sha": "ab12…",
  "inputs":  [{"name": "ticket", "type": "str", "flow": "fluid"}],
  "outputs": [{"name": "label",  "type": "str", "flow": "static"}],
  "authored_by": "craw-code",
  "tainted": true
}
```

Exit codes: `0` ok; `2` component not found / compile error; `4` reflection cost ceiling
exceeded (CRA-274).

**Acceptance criteria**
- [ ] Reflects inputs/outputs with resolved structural `type` and `flow` per `Parameter`.
- [ ] Surfaces nothing but typed shape + identity (no secrets/egress/destinations — CRA-271).
- [ ] Reflects the on-disk component at call time (edit a file, re-run, see the change) —
  no stale registry.
- [ ] Emits `craw.code.describe.v1`, snapshot-tested, negotiated per CRA-269.
- [ ] Carries `authored_by` / `tainted` from CRA-266 so the agent knows the file's trust.

**Test plan** — `packages/crawfish/tests/test_describe.py`. Compile the demo `triage-bot`
on the `MockRuntime`; snapshot the payload; assert `flow` is correctly reported for a
fluid input; assert a re-run after an edit reflects the new shape; assert no
secret/destination field appears. No live calls.

**Security review notes** — SECURITY.md rules 1 (static/fluid typing) and 4 (secrets by
reference, never surfaced). The `flow` field is the agent's safety signal; CRA-271 governs
redaction. Red-team payload (shared with CRA-271): a component whose `mcp/*.py` declares an
`auth` env-var ref and an egress host — assert `describe` surfaces neither, only the
capability *kind*.

### CRA-269 — Define --json schema-version negotiation between plugin and CLI
**Milestone:** M1 · **Priority:** Urgent · **Depends on:** none
**Context** — The plugin and the `craw` CLI upgrade independently (the plugin is pinned to
a `crawfish` version range, but a user can `pip install -U crawfish` out from under it).
Today there is a single `JSON_SCHEMA_VERSION = 1` integer and a `craw.<cmd>.v<N>` string
([`cli.py`](../../../packages/crawfish/src/crawfish/cli.py)) but no *negotiation* — a
plugin built for `v1` parsing a `v2` payload has no defined behaviour, inviting silent
schema skew.

**Design** — Split the monolithic integer into per-command **`schema_major.schema_minor`**
and define a forward-compatible contract: a **major** bump is breaking (field removed /
re-typed), a **minor** bump is additive (new field, old parsers ignore it). The plugin
declares the majors it understands; the CLI advertises what it emits. On a `--json` call,
the envelope carries both, and a mismatch surfaces a structured `schema_skew` error
(through the CRA-270 envelope) rather than a parse crash. Parsers are written
forward-compatible (subset check: the plugin requires its known fields are present, tolerates
extras). Add a `craw code schema [--json]` introspection verb that dumps the emitted
`{command: "major.minor"}` map so the plugin can do a one-shot compat check at session
start (and after an `--upgrade`).

**Interface**

```python
# crawfish/cli.py  (replaces the scalar JSON_SCHEMA_VERSION)
SCHEMA_VERSIONS: dict[str, tuple[int, int]] = {
    "code.describe": (1, 0),
    "code.estimate": (1, 0),
    "error":         (1, 0),
    # … per command
}
def schema_tag(command: str) -> str:           # "craw.code.describe.v1"  (major only)
def schema_version(command: str) -> dict[str, int]:  # {"major": 1, "minor": 0}
```

Every `--json` envelope gains:

```json
{ "schema": "craw.code.describe.v1",
  "schema_version": {"major": 1, "minor": 0} }
```

`schema_skew` error (CRA-270 envelope):

```json
{ "schema": "craw.error.v1",
  "code": "schema_skew", "retryable": false,
  "detail": {"command": "code.describe", "cli_major": 2, "plugin_major": 1},
  "remediation": "Upgrade the crawfish plugin to a build that understands major 2." }
```

Exit code: `4` on an unrecoverable skew (non-retryable).

**Acceptance criteria**
- [ ] Each `--json` payload carries `schema` (major tag) and `schema_version`
  (`major`,`minor`).
- [ ] A minor bump is additive; an existing parser ignoring the new field still passes.
- [ ] A major mismatch surfaces a `schema_skew` `craw.error.v1` envelope, never a crash.
- [ ] `craw code schema --json` dumps the full `{command: "major.minor"}` map.
- [ ] The subset/forward-compat parser contract is documented and snapshot-tested.

**Test plan** — `packages/crawfish/tests/test_schema_negotiation.py`. Cases: minor-bump
back-compat (old parser, new field, still parses); simulated major mismatch produces the
`schema_skew` envelope + exit `4`; `craw code schema` snapshot. No live calls.

**Security review notes** — SECURITY.md: a schema-skew must **fail closed**, not degrade to
an unparsed/guessed payload that could mask a security field (e.g. a missing `flow` or
`tainted`). `retryable:false` on skew. No new fluid surface.

### CRA-270 — Structured recoverable error envelope (craw.error.v1)
**Milestone:** M1 · **Priority:** High · **Depends on:** none
**Context** — The agent loop needs a structured, recoverable error surface: today a failed
`craw` call surfaces a Python traceback or a bare non-zero exit, which the agent cannot
reliably classify (retry? fix the wiring? stop and ask a human?). §12.3 calls for a
`craw.error.v1` envelope with `code`, `retryable`, `remediation`, and **security
rejections marked non-retryable**.

**Design** — A single error envelope emitted on stderr in `--json` mode (and a clean
one-line message otherwise). `code` is a closed enum (`usage`, `not_found`,
`compile_error`, `jail_violation`, `budget_exceeded`, `schema_skew`,
`fluid_to_static_sink`, `signing_required`, `consent_required`, `tree_busy`, `internal`).
`retryable` is `false` for every **security** rejection (`jail_violation`,
`fluid_to_static_sink`, `signing_required`, `consent_required`, `schema_skew`) — fail
closed, an injected agent must not be able to "retry past" a security gate. `remediation`
is a static, non-fluid human string. The CLI maps each raised framework exception
(`DefinitionLoadError`, `FluidToStaticSinkError`, `SigningRequired`, `ConsentRequired`,
`CassetteMiss`, jail `Denial`, budget halt) to exactly one `code` + exit code (per the
CRA-243 table). Remediation strings are **static-only** — never echo fluid input back into
the envelope (a tainted ticket body must not round-trip through an error message).

**Interface**

```json
{ "schema": "craw.error.v1",
  "schema_version": {"major": 1, "minor": 0},
  "code": "fluid_to_static_sink",
  "retryable": false,
  "detail": {"component": "pipelines/triage", "slot": "sink.target"},
  "remediation": "A sink target is static-only; bind it from static config, not a fluid input." }
```

```python
# crawfish/cli.py
def emit_error(code: str, *, retryable: bool, remediation: str,
               detail: dict[str, object] | None = None) -> int:
    """Print the craw.error.v1 envelope to stderr (--json) and return the exit code."""
```

Exit codes follow CRA-243 (`2` compile, `3` budget, `4` security).

**Acceptance criteria**
- [ ] `code` is a closed enum; every agent-facing failure maps to exactly one.
- [ ] Every security rejection is `retryable:false`.
- [ ] `remediation` is static; no fluid/tainted input is echoed into the envelope.
- [ ] The envelope is emitted on stderr; the exit code matches CRA-243.
- [ ] `DefinitionLoadError`, `FluidToStaticSinkError`, `SigningRequired`,
  `ConsentRequired`, `CassetteMiss`, jail `Denial`, and budget halt each produce the right
  `code`.

**Test plan** — `packages/crawfish/tests/test_error_envelope.py`. Trigger each mapped
exception against the demo project on the mock and snapshot the envelope + exit code.
Assert `retryable` is `false` for the five security codes. Include a case where a tainted
input is present and assert it does **not** appear in the envelope. No live calls.

**Security review notes** — SECURITY.md rules 1/4/9. The non-fluid-remediation rule is a
fluid-surface boundary: the error message is an output the agent reads, so echoing a
tainted ticket body would re-introduce injected text into the agent's instruction stream.
Red-team payload: a `fluid_to_static_sink` rejection triggered by a poisoned input —
assert the input string never appears in the envelope and `retryable` is `false`.

### CRA-271 — Redact secret refs & consequential config from `craw code describe`
**Milestone:** M1 · **Priority:** High · **Depends on:** CRA-244
**Context** — `describe` projects a component into the agent's context. If it surfaced
secret references, egress hosts, or sink destinations, it would leak the consequential
configuration the security spine keeps away from the model (SECURITY.md rule 4: secrets by
reference, never in-prompt; rule 2: sink targets static-only). §12.2 routes this through
the existing `ScrubbingStore` redaction and surfaces capability *kind*, not destination.

**Design** — `describe`'s projection is **typed-shape-only** and passes through the
`ScrubbingStore` redaction layer before emission. For capabilities it surfaces the
**kind** (`"has_mcp_connection"`, `"declares_secret_ref"`, `"writes_to_sink"`) but never
the destination, the env-var name, or any auth reference. The `MCPConnection.auth` field
(an env-var name by reference — `docs/reference/definition.md`) is dropped; the egress
host (`MCPConnection.url` / `command`) and any sink target are dropped. The
`craw.code.describe.v1` snapshot test asserts the absence of these fields, so a regression
that re-introduces a leak fails CI.

**Interface** — `describe`'s payload (CRA-244) gains a redacted `capabilities` block,
destination-free:

```json
{ "schema": "craw.code.describe.v1",
  "capabilities": [
    {"kind": "declares_secret_ref"},
    {"kind": "has_mcp_connection"},
    {"kind": "writes_to_sink"}
  ] }
```

No `auth`, `url`, `command`, or sink `target` field ever appears. Exit codes per CRA-244.

**Acceptance criteria**
- [ ] `describe` surfaces capability *kind* only — never a secret ref, egress host, or
  sink destination.
- [ ] The projection passes through `ScrubbingStore` redaction before emission.
- [ ] `MCPConnection.auth` / `url` / `command` and sink targets are absent from the payload.
- [ ] The `craw.code.describe.v1` snapshot asserts the absence (regression fails CI).

**Test plan** — `packages/crawfish/tests/test_describe_redaction.py`. A demo component
declaring an `MCPConnection` with `auth="SLACK_TOKEN"`, a `url`, and a sink target; assert
`describe --json` shows `{"kind": …}` entries only and none of the three values. Negative
test: grep the serialized payload for the secret name / host and assert absence. No live
calls.

**Security review notes** — SECURITY.md rules 2 and 4 directly. `describe` is a
context-feeding surface, so a leak here is a direct injection-amplifier (the agent could be
steered to exfiltrate a surfaced destination). Red-team payload (shared with CRA-244):
poisoned component declaring a secret + egress host — assert neither reaches the payload.

### CRA-272 — Run the assembly gate (assert_build_safe) inside `craw code run`/`sync`
**Milestone:** M1 · **Priority:** High · **Depends on:** CRA-269, CRA-270
**Context** — [`assert_build_safe`](../../../packages/crawfish/src/crawfish/build.py)
runs `crawfish.alg3.assert_no_fluid_to_static_sink` over a project's definitions and fails
closed before any image is produced — but today it fires at **build** time, not in the
edit→run loop where `craw code` actually iterates. §12.2: invoke the assembly gate as a
**precondition** of `craw code run`/`sync`, the exact moment an agent-authored wiring would
otherwise slip a fluid value toward a static-only sink slot.

**Design** — Make `assert_build_safe(definitions)` a precondition of `craw code run` and
`craw code sync`: compile the project (jailed per CRA-267 when agent-authored), then run
the assembly gate (`assert_no_fluid_to_static_sink`) over the compiled definitions before
any run. A `FluidToStaticSinkError` fails closed, surfaced as the CRA-270 envelope
`code="fluid_to_static_sink"`, `retryable:false`, exit `4`. This is **defense in depth**
atop the runtime `StaticOnlyError` / `TargetMustBeStaticError` (SECURITY.md invariant 8),
moved early so the agent sees the rejection before spending a run. `craw code sync` runs the
same gate across the whole authored tree as the agent's "where am I / is my wiring safe"
call.

**Interface**

```bash
craw code run definitions/triage-bot --json      # gate runs before any execution
craw code sync --json                            # gate runs across the whole tree
```

On rejection, the CRA-270 envelope:

```json
{ "schema": "craw.error.v1", "code": "fluid_to_static_sink",
  "retryable": false, "detail": {"component": "pipelines/triage"},
  "remediation": "A fluid value reaches a static-only sink slot; rebind from static config." }
```

Exit codes: `0` ok; `4` assembly-gate rejection.

**Acceptance criteria**
- [ ] `craw code run` runs `assert_build_safe` over the compiled definitions before any run.
- [ ] `craw code sync` runs the gate across the authored tree.
- [ ] A fluid-to-static-sink wiring fails closed with `code="fluid_to_static_sink"`,
  `retryable:false`, exit `4`, before any model call.
- [ ] The gate is additive to (never a replacement for) the runtime `StaticOnlyError` /
  `TargetMustBeStaticError`.

**Test plan** — `packages/crawfish/tests/test_run_assembly_gate.py`. A demo pipeline
wiring a fluid input toward a sink target; assert `craw code run` rejects it with the
envelope + exit `4` and that **no** run/model call fires (assert on the mock that it was
never invoked). A safe pipeline passes. No live calls.

**Security review notes** — SECURITY.md invariant 8 (fluid-to-static-sink rejected at
assembly, fails closed) and 2 (sink targets static-only). This is the precise enforcement
the §12.1 trust collapse demands — the gate fires in the loop, not only at build. Red-team
payload: an agent-authored pipeline that wires a poisoned ticket's body toward a sink
target — assert rejection before any run.

### CRA-273 — `craw code estimate` (cost preview) + project budget threading
**Milestone:** M1 · **Priority:** Urgent · **Depends on:** CRA-269, CRA-270
**Context** — An agent firing `--live` runs across a project with no preview and no
aggregate ceiling is the plan's single largest risk (§12.5). `craw dev --estimate` already
previews a single Definition via
[`estimate_cost`](../../../packages/crawfish/src/crawfish/cost.py) (no live call), and the
`CostEstimate` carries the honest band (`total_usd` ≤ `expected_usd` ≤ `worst_case_usd`).
This issue lifts that to a **project-level** preview verb and threads a project `[budget]`
ceiling that halts agent `--live` calls.

**Design** — `craw code estimate <component|project>` runs `estimate_cost` (no model call)
and emits the band. Add a `[budget]` section to `crawfish.toml` (a project-wide ceiling)
read via `crawfish.config`; the `--budget` flag already projects onto a `CostBudget` via
`Budget(stop_usd=…).as_cost_budget()` (`_opt_ctx` in `cli.py`). Thread the project ceiling
so a `craw code run --live` whose estimate's `worst_case_usd` exceeds the remaining ceiling
**halts before the call** with the CRA-270 envelope `code="budget_exceeded"`,
`retryable:false`, exit `3`. The dashboard (M4) renders actuals against this ceiling; this
issue ships the preview + the halt, deterministically.

**Interface**

```bash
craw code estimate definitions/triage-bot --items 100 --json
```

```json
{ "schema": "craw.code.estimate.v1",
  "component": "definitions/triage-bot", "items": 100,
  "total_usd": 0.12, "expected_usd": 0.31, "worst_case_usd": 4.80,
  "project_ceiling_usd": 5.00, "remaining_usd": 5.00, "within_budget": true }
```

```toml
# crawfish.toml
[budget]
ceiling_usd = 5.00     # halts agent --live calls whose worst_case exceeds remaining
```

Exit codes: `0` ok; `3` `budget_exceeded` when a `--live` run's worst case exceeds the
remaining ceiling.

**Acceptance criteria**
- [ ] `craw code estimate` previews `total`/`expected`/`worst_case` with **no** model call.
- [ ] A `[budget] ceiling_usd` in `crawfish.toml` is read and threaded.
- [ ] A `--live` run whose `worst_case_usd` exceeds the remaining ceiling halts before the
  call with `code="budget_exceeded"`, exit `3`.
- [ ] The estimate band honors the invariant `total ≤ expected ≤ worst_case`.
- [ ] `craw.code.estimate.v1` is snapshot-tested and CRA-269-negotiated.

**Test plan** — `packages/crawfish/tests/test_code_estimate.py`. Snapshot the estimate
payload for the demo Definition; assert no model call fires (mock never invoked); assert a
ceiling below `worst_case_usd` halts a simulated `--live` run with the budget envelope +
exit `3`; assert the band invariant. No live calls.

**Security review notes** — Not a fluid surface, but a **responsibility gate**: the
`worst_case` halt is what stops a prompt-injected agent from burning spend via `--live`.
SECURITY.md "LLM observers are cost-capped" generalizes here. The halt must be
`retryable:false` so an injected agent can't loop past it. No red-team payload required,
but note the budget halt in the §12.5 risk register.

### CRA-274 — Bound `craw code describe` reflection cost + standalone CLI contract
**Milestone:** M1 · **Priority:** Medium · **Depends on:** CRA-244
**Context** — `describe` recompiles per call, an unbounded hot-path latency for a verb the
agent may call repeatedly; and its **standalone** usability (usable directly over Bash
without the plugin) is unstated (§12.3). The cassette/identity model already keys on
content sha, so a single-component reflection can be cached.

**Design** — Cache the `describe` projection by **content sha** under `.crawfish/` (the
generated-state dir — never hand-edited; `craw doctor` flags tampering). On a call, compute
the component's content sha (the same sha `load_definition` derives); on a cache hit, return
the stored `craw.code.describe.v1` projection with **zero recompile**; on a miss, compile
(jailed per CRA-267 when agent-authored), project, and store. Bound the per-call work with
a reflection cost ceiling (a static cap; exceeding it is a `code="budget_exceeded"`/
reflection-bound error, exit `4` or `3` as appropriate). Assert the **standalone contract**:
`craw code describe` is a plain CLI call that works over Bash with no plugin, no MCP, no
session — the RFC's "one execution path; humans and Claude hit the same code."

**Interface**

```bash
craw code describe definitions/triage-bot --json   # cached by content sha under .crawfish/
```

Cache location: `.crawfish/describe/<content_sha>.json` (generated state; gitignored).
A re-run after an edit (new sha) is a miss and recompiles; an unchanged component is a hit.

**Acceptance criteria**
- [ ] A repeated `describe` of an unchanged component is a cache hit (no recompile).
- [ ] An edited component (new content sha) is a cache miss and recompiles.
- [ ] The cache lives under `.crawfish/` and is never written into the authored tree.
- [ ] A reflection cost ceiling bounds per-call work and fails closed when exceeded.
- [ ] `craw code describe` runs standalone over Bash (no plugin/MCP/session) — asserted by
  a test that invokes it as a bare subprocess.

**Test plan** — `packages/crawfish/tests/test_describe_cache.py`. Cases: two calls on an
unchanged component → second is a hit (assert no recompile, e.g. via a compile counter);
edit → miss → recompile; cache file lands under `.crawfish/`; a bare-subprocess invocation
returns the same payload (standalone contract). No live calls.

**Security review notes** — SECURITY.md "Do not hand-edit `.crawfish/`": the cache is
generated state, so a tampered cache must not be trusted — key strictly on content sha so a
stale/forged entry can't shadow a changed component. No new fluid surface (the cached
payload is already CRA-271-redacted).

### CRA-275 — Thread org_id (tenancy) through all craw code verbs and the dashboard
**Milestone:** M1 · **Priority:** Medium · **Depends on:** CRA-269, CRA-270
**Context** — Every `Store` row carries an `org_id` (defaulted `"local"`; SECURITY.md
"Tenancy and run identity"), and the existing optimization plane already threads `--org` to
the `RunContext` and Store (`_opt_ctx`, `RunContext(org_id=args.org)` in `cli.py`). The new
`craw code` verbs and the dashboard must thread the same `org_id` or risk cross-tenant
leakage (§12.3). The `ObserverSurface` is already constructed per-org
(`ObserverSurface(store, org_id=…)` in
[`observe.py`](../../../packages/crawfish/src/crawfish/observe.py)).

**Design** — Add `--org ID` to every `craw code` verb (`describe`, `estimate`, `run`,
`sync`, `schema`, and the M2+ verbs as they land), defaulting to `"local"`, and thread it
to: the `RunContext`, every `Store` read/write (provenance rows from CRA-266, the
`describe` cache from CRA-274, the cost ledger), and the dashboard's `ObserverSurface`
construction (`ObserverSurface(store, org_id=org)`). The dashboard data path imports only
the `Store` protocol + `ObserverSurface` (never a concrete `SqliteStore` — ADR rule:
"product model imports protocols, never a backend"; M4 owns the dashboard wiring, this
issue threads the key). Aggregations run in Python over scrubbed, org-scoped rows. The
acceptance gate is a **two-org isolation test**: a verb run under `--org a` never reads or
writes `--org b`'s rows.

**Interface**

```bash
craw code describe … --org acme
craw code estimate … --org acme
craw code run     … --org acme
craw code sync    --org acme
```

Every `--json` envelope already carries `"org"` (from the shared `_opt_print`/`emit_json`
envelope); `craw code` verbs inherit it.

**Acceptance criteria**
- [ ] Every `craw code` verb accepts `--org` (default `"local"`) and threads it to the
  `RunContext` and every Store read/write.
- [ ] CRA-266 provenance rows, the CRA-274 describe cache, and cost/ledger rows are all
  org-scoped.
- [ ] The dashboard constructs `ObserverSurface(store, org_id=org)` and reads only
  org-scoped, scrubbed rows — importing the `Store` protocol, never `SqliteStore`.
- [ ] A two-org isolation test: a verb under `--org a` sees none of `--org b`'s rows.

**Test plan** — `packages/crawfish/tests/test_code_org_isolation.py`. Reuse the existing
cross-tenant helpers (`crawfish.testing.assert_cross_tenant_isolation` /
`assert_store_org_scoped`; see `test_cross_tenant_gate.py`). Run `describe`/`estimate`/
provenance under two orgs against a shared store; assert no cross-read/write. No live calls.

**Security review notes** — SECURITY.md "Tenancy and run identity" (org folds into cassette
key and every ledger row; a resume in one org never replays another's work) and the
architecture rule "product model imports protocols, never a backend." Not a new fluid
surface, but a cross-tenant leak is a data-isolation breach — the two-org test is the gate.
Reuse the registered cross-tenant isolation surface so any new keyed store inherits the
check.
