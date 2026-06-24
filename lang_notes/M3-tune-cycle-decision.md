# M3 — `Definition.tune` import-cycle decision (CRA-209 / AL-T1)

**Decision (Option A, approved by team-lead):** extract the light tune value-types into a new
low-layer module `crawfish/tune.py`; `crawfish.tuner` re-exports them; `Definition.tune` stays
**strongly typed** as `TuneSpec | None`.

## Problem

`Definition.tune` annotates `TuneSpec`. Pydantic must resolve that type when it builds
`Definition`'s schema, and `runtime/base.py:127` forces that build **eagerly at import** via
`RunRequest.model_rebuild()`. But `TuneSpec`'s original home, `crawfish.tuner`, sits behind a hard
cycle back to `definition.types`:

```
tuner → eval → metrics → batch → definition.types
```

and `batch.py` imports `definition.types` *before* it defines `Task`. So any import-time
`definition → tuner` edge deadlocks (`ImportError: cannot import name 'Task' ...`).

## Options considered

- **Forward-ref + lazy `model_rebuild()` in the compiler** (team-lead's first suggestion) —
  REJECTED. The eager `RunRequest.model_rebuild()` at import wins the race and resolves
  `Definition`'s schema *before* any compiler-time seam runs; Pydantic 2.13 then hard-fails with
  `PydanticUndefinedAnnotation` and does not tolerate a deferred/incomplete nested model. Verified
  empirically.
- **Store the serialized dict** `tune: dict[str, Any] | None` (team-lead's second suggestion) —
  works and removes the type from the schema, but loses the strong typing on `Definition.tune`.
  Superseded.
- **Light-module extraction (Option A)** — CHOSEN. Keeps `Definition.tune: TuneSpec | None`.

## Resolution

`crawfish/tune.py` is a new leaf module holding `KnobValue`, `KnobDomain`, `TuneSpec`,
`tune_spec_sha`, depending only on `pydantic`/`json`/`hashlib`/`tomllib` (NO imports of
`eval`/`metrics`/`batch`/`runtime`/`definition`). Because it has no crawfish imports it sits below
everything, so `definition.types` can `from crawfish.tune import TuneSpec` **eagerly at module
top** with no cycle — Pydantic resolves the annotation when the schema builds.

`crawfish.tuner` does `from crawfish.tune import KnobDomain, KnobValue, TuneSpec, tune_spec_sha`
(kept in `tuner.__all__`) — a **pure extract + re-export**, so they are the **same class objects**.
`from crawfish.tuner import TuneSpec` is unchanged; the package `__init__` re-export still works;
a `tuner.TuneSpec` instance is accepted by `Definition.tune` (same class). No tuner behavior changed.

## Final import edges

- `definition → tune`  (for the `TuneSpec` annotation)
- `tuner → tune`       (re-export)
- **No** `definition → tuner` import edge.

## Hashing rule (unchanged by this decision)

- Tune-less Definition (`tune is None` / no knobs) **omits** the `tune` key from `content_dict()`
  → byte-identical pre-change sha (hash-neutral). `tune_spec_sha({"knobs": []})` is a non-trivial
  constant, so we omit rather than fold-the-constant.
- Non-empty tune folds `tune_spec_sha(self.tune)` into `content_dict()` (versions the agent).
- `CONTENT_HASH_VERSION` stays `1` (hash-neutral addition, F-5 precedent).

## Verification (all green)

- `uv run python -c "import crawfish"` → OK; `crawfish.tune.TuneSpec is crawfish.tuner.TuneSpec`.
- Demo lock regenerates to `0.1-7113bfa78543` (unchanged) on clean demo source.
- `uv run pytest -q` → fully green (incl. `test_tuner`, `test_definition_tune`, learning/gate
  and demo tests).

## Files

- `packages/crawfish/src/crawfish/tune.py` (new — light home)
- `packages/crawfish/src/crawfish/tuner.py` (extract + re-export, behavior unchanged)
- `packages/crawfish/src/crawfish/definition/types.py` (`tune: TuneSpec | None`, content_dict fold)
- `packages/crawfish/src/crawfish/definition/compiler.py` (`tune.toml` → typed `TuneSpec`)
- `packages/crawfish/tests/test_definition_tune.py`
- `docs/_changelog/CRA-209-tune-wiring.md`
