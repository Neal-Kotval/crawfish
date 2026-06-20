<!--
Thanks for contributing to Crawfish! Keep PRs small and focused — a new
Source/Sink/Definition is ideally one self-contained PR.
-->

## What & why

<!-- One or two sentences. What does this change and why? -->

Closes #<!-- issue number -->

## Checklist

- [ ] Tests added or updated (deterministic — no live model calls; fixtures / record-replay)
- [ ] Docs updated (guide / cookbook / API reference as relevant)
- [ ] `just check` is green (ruff + mypy --strict + pytest)
- [ ] Demo / connector runs end to end (e.g. `craw dev …` or the connector's dry-run path)
- [ ] Commits are **DCO signed off** — every commit has a `Signed-off-by:` line (`git commit -s`)
- [ ] Security spine upheld: secrets held by reference, fluid inputs stay data, sink targets/idempotency keys static-only

## Notes for reviewers

<!-- Anything that needs attention: tradeoffs, follow-ups, areas to scrutinize. -->
