# craw code provenance and jailed compile

Look-up page for the typed surface that contains agent-authored code: the per-file provenance
record (CRA-266) and the jailed compile that imports it (CRA-267,
[ADR 0010](../architecture/decisions/0010-jailed-compile-agent-authored-code.md)). For the
narrative treatment, see the [security model](../guide/craw-code/security.md); this page is the
field-by-field reference.

## The provenance record

Every authored file carries a provenance row, written through the `Store` protocol under the
kind `FILE_PROVENANCE_RECORD_KIND = "file_provenance"`, keyed `(component_path, content_sha)`.

| Field | Type | Notes |
| --- | --- | --- |
| `component_path` | `str` | Path to the authored file, relative to the project root. Part of the key. |
| `content_sha` | `str` | A **pure content hash** of the file. `authored_by` is *not* mixed in, so a directory and its installed copy hash identically. Part of the key. |
| `authored_by` | `str` | `"human"`, `"craw-code"`, or an optimization-loop id. Drives whether the compile is jailed. |
| `source_tainted` | `bool` | `True` if the file was authored under fluid (untrusted) context. |
| `taint` | `frozenset[str]` | Taint labels carried by the file. The canonical label is `FLUID_TAINT == "fluid"`. |

Authoring a file emits a `file.authored` `METRIC` event onto the ledger.

!!! warning "Taint is monotonic"
    A file authored under fluid context is `source_tainted=True` and stays tainted across every
    boundary. Taint is dropped only by an audited `declassify` — never silently. A downstream
    gate can therefore trust the label.

### The `--json` shape

`craw code describe --json` carries the provenance fields inline (`authored_by`, `tainted`);
the dedicated provenance projection uses the `craw.code.provenance.v1` envelope:

```json
{
  "schema": "craw.code.provenance.v1",
  "component": "tools/notify.py",
  "content_sha": "ab12cd34",
  "authored_by": "craw-code",
  "source_tainted": true,
  "taint": ["fluid"]
}
```

## Jailed compile

When a component's provenance is `authored_by != "human"` (or unknown), its import is routed
through `load_definition_jailed` instead of the in-process path. Human-authored components keep
the fast in-process import.

| Element | Behavior |
| --- | --- |
| `load_definition_jailed(...)` | Entry point. Selects a jail, runs the import inside it, returns only the typed shape. |
| `select_jail(SandboxPolicy())` | Auto-sniffs the backend: `BwrapJail` (Linux), `SeatbeltJail` (macOS). Tests use `FakeJail` via `kind="fake"`. |
| Project dir binding | Bound **read-only and `Flow.STATIC`**. `allow_paths` is static-only — a `Flow.FLUID` path raises `StaticOnlyError` *before* the sandbox spawns. |
| Network | `allow_net=False`. No network inside the jail. |
| Boundary crossing | Only the **typed shape** crosses back — never live Python objects. The `TypeRegistry` is rehydrated on the far side so `parameters_compatible` holds across the boundary. |
| `JailResult.out_taint` | Recorded onto the provenance row after the import. |
| On `Denial` | Emits a `JAIL_VIOLATION` event and raises a fail-closed `DefinitionLoadError` (`code="jail_violation"`, `retryable: false`, exit `2`). |

### What crosses the boundary

The jail returns the component's typed inputs and outputs — `name`, `type`, `flow` per slot,
plus capability *kinds* only — exactly the projection `craw code describe` emits. No imported
module object, no closure, no live handle is allowed across. This is why `describe` can compile
agent-authored code safely: the dangerous part (running the import) happens inside the sandbox,
and only inert typed data comes out.

## See also

- [Security model](../guide/craw-code/security.md) — the narrative on provenance and the jail
- [craw code JSON contracts](craw-code-json-contracts.md) — the `craw.error.v1` envelope and exit codes
- [ADR 0010](../architecture/decisions/0010-jailed-compile-agent-authored-code.md) — jailed compile of agent-authored code
- [Sandbox & jail](sandbox-and-jail.md) — the jail backends in detail
