# Contributing to Crawfish

Thanks for helping build Crawfish — an open-source framework for **agents that do bulk
work over your data** (`Source → Batch → Aggregator → Router → Sink`, authored as
directories and run locally via `claude -p`). This guide gets you from a fresh clone to
a merged PR.

By participating you agree to our [Code of Conduct](CODE_OF_CONDUCT.md). To report a
security issue, follow the [Security Policy](SECURITY.md) — please don't open a public
issue for vulnerabilities.

## The fastest first contribution: a connector

The most welcome — and most self-contained — first PR is a **connector** (a Source or
Sink that wires Crawfish to a new system). It's a vertical slice you can build and test
without touching the core seams. Start here:
[`docs/guide/contributing-a-connector.md`](../docs/guide/contributing-a-connector.md).

## Dev setup

Crawfish is a [`uv`](https://docs.astral.sh/uv/) workspace and uses
[`just`](https://github.com/casey/just) as its task runner. Run `just` to list every
recipe.

```bash
just deps        # install the workspace + dev deps (editable) — runs `uv sync`
just demo        # run the demo end to end (zero key, mock runtime)
just check       # the full gate: lint + typecheck + tests
```

No `just`? Every recipe is a thin wrapper — `just deps` is `uv sync`, `just check` runs
the commands below directly.

## The gate (run before every push)

`just check` must be green. It runs:

```bash
uv run ruff check .                  # lint
uv run ruff format --check .         # format check
uv run mypy packages/crawfish/src    # typecheck (strict)
uv run pytest -q                     # tests
```

Auto-fix formatting and lint with `just fmt`. If you touched docs, also confirm the docs
site builds strict (CI runs this too):

```bash
uv run --group docs mkdocs build --strict
```

## Code style

- **`ruff` + `mypy --strict` clean** — no `# type: ignore` without a reason, no
  suppressed lints without a comment explaining why.
- **Pydantic for data shapes, ABCs for behavioural nodes.** Data carriers (parameters,
  config, records) are Pydantic models; nodes that *do* something are abstract base
  classes with typed methods.
- **Enums are `(str, Enum)`.** `ruff`'s `UP042` is intentionally disabled — keep enums
  string-valued (see ADR 0004).
- **Respect the seams.** The product model imports the *protocols* `AgentRuntime`,
  `Store`, and `ArtifactStore` — never a concrete backend. No SDK import in nodes; no raw
  SQL outside a `Store` implementation. Type compatibility is structural via
  `crawfish.typesystem`, never string equality (ADR 0002).
- **Honour the security spine.** `Flow.FLUID` inputs are untrusted session data — they
  reach the model as data, never instructions; Sink targets and idempotency keys are
  static-only; secrets resolve by reference and are never logged or in-prompt. See
  [`docs/architecture/SECURITY.md`](../docs/architecture/SECURITY.md).

Match the style of the code around you. When an architectural or security fork comes up,
record an ADR in `docs/architecture/decisions/` rather than deciding silently.

## Branch & PR flow

1. Fork the repo and create a topic branch off `main`
   (`git switch -c feat/my-connector`).
2. Make focused commits — one concern per commit, present-tense summary lines.
3. **Sign off every commit** (see DCO below).
4. Push and open a PR against `main`. Describe *what* changed and *why*; link any related
   issue.
5. CI runs the gate, the docs build, and the DCO check. A maintainer reviews under lazy
   consensus (see [GOVERNANCE.md](GOVERNANCE.md)).

`main` is branch-protected: required CI + review, no direct pushes.

## Developer Certificate of Origin (DCO)

Crawfish uses the [Developer Certificate of Origin](https://developercertificate.org/)
— **not a CLA**. The DCO is a lightweight statement that you wrote the patch, or
otherwise have the right to submit it under the project's Apache-2.0 license.

You certify it by signing off your commits:

```bash
git commit -s -m "feat(source): add Notion connector"
```

The `-s` flag appends a `Signed-off-by: Your Name <you@example.com>` trailer using your
git `user.name` / `user.email`. **CI enforces this** — every commit in a PR must carry a
matching sign-off, or the check fails. To fix an existing branch:

```bash
git rebase --signoff main   # sign off every commit on the branch
git push --force-with-lease
```

## Definition of Done

A PR is ready to merge when:

- [ ] **Tests** — new behaviour is covered; `uv run pytest -q` is green and deterministic
      (no live model calls — use fixtures / record-replay).
- [ ] **Docs** — user-facing changes update the relevant page under `docs/`, and
      `mkdocs build --strict` passes.
- [ ] **Green CI** — `just check` clean: `ruff`, `ruff format --check`, `mypy --strict`,
      `pytest`.
- [ ] **DCO** — every commit is signed off.
- [ ] **Spine upheld** — no new path lets a fluid input reach the model as an
      instruction, redirect a Sink, or leak a secret.

Questions are welcome — open a discussion or a draft PR early. Welcome aboard.
