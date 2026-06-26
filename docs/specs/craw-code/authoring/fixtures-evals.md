# `fixtures/` & evals

> Feeds `crawfish-authoring-fixtures-evals` (CRA-264). Golden:
> [`demo/craw-code-golden/fixtures/`](../../../../demo/craw-code-golden/fixtures).

`fixtures/` feeds `craw test` (eval-as-test): each `fixtures/*.json` is one input set the
Definition runs against. Evals gate against a saved baseline (`craw eval --baseline`).

## The fixture shape

```json
{"inputs": {"project": "acme", "ticket_body": "the login button does nothing"}}
```

A fixture is `{"inputs": {...}, "expected": <optional>}`. `inputs` maps each declared
`Parameter` name to a value (static and fluid alike — a fixture is the *trusted* test harness,
so it may supply both). With no `expected`, a fixture passes when the run executes cleanly;
with `expected`, the Output value must match. `run_fixtures` runs every `*.json` in sorted
order through a `Run`.

```bash
craw test definitions/<name> --fixtures fixtures
```

## Determinism: mock-by-default, randomness in `--seed`

Fixtures run **mock-by-default** — on the `MockRuntime` / the `command` profile's recorded
transport, never a live model — so the suite is deterministic and free. All randomness is
carried in `--seed`; the same seed replays byte-identically. Promote to `--live` only
deliberately and always **under `--budget`**.

## The eval baseline gate

`craw eval --baseline <ref>` compares the current run's per-metric scores against a saved
baseline within a `--tolerance`, and reports the deltas plus the cost band
(`total_usd` / `expected_usd` / `worst_case_usd`). Sinks fire **only in eval mode** (rule 7);
an optimize/search run never fires a consequential action. Read `retryable` on a
`craw.error.v1` to decide retry-vs-stop — a security rejection is `retryable:false`.

Fixtures never carry secrets. Reference credentials by name in `.env.example`
(`# GITHUB_TOKEN=...`), never inline.
