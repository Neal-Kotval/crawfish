# Governance

This document describes how decisions get made in Crawfish, who makes them, and
how someone becomes a maintainer. It is intentionally lightweight — enough
structure to be predictable, not so much that it gets in the way.

## Roles

- **Contributors** — anyone who opens an issue, a PR, a discussion, or otherwise
  helps. No commitment required.
- **Maintainers** — a small group with merge rights and release responsibility.
  They review PRs, steward the architecture, cut releases, and uphold the
  security spine. Current maintainers are listed in
  [`MAINTAINERS.md`](MAINTAINERS.md).

## How decisions are made

Day-to-day changes move by **lazy consensus**: a PR that satisfies the
[Definition of Done](CONTRIBUTING.md#definition-of-done), passes CI, and is
approved by a maintainer can be merged. Anyone can review; a maintainer's
approval is required to merge.

- **Code owners.** Changes to the load-bearing seams require review from the
  relevant owner (see [`CODEOWNERS`](CODEOWNERS)) — the runtime, store, and
  artifact protocols, the core type system, and the security-critical paths
  (sink egress, secrets, sandboxing).
- **Architectural / security forks.** When a change reaches an architectural or
  security decision point, the contributor records an ADR in
  `docs/architecture/decisions/` with rationale and rejected alternatives. The
  ADR is reviewed like any other change.
- **Disagreement.** Discuss it in the PR or a GitHub Discussion. If maintainers
  can't reach consensus, the matter is decided by a simple majority of
  maintainers; a tie defers to the status quo (no change). We aim for consensus
  first and votes rarely.

## Becoming a maintainer

Maintainership is earned through sustained, high-quality contribution — not a
one-time grant. The typical path:

1. Land several non-trivial PRs that respect the gate and the security spine.
2. Review others' PRs constructively and help in issues/discussions.
3. An existing maintainer nominates you; the maintainer group agrees by consensus.
4. You're added to [`MAINTAINERS.md`](MAINTAINERS.md) and `CODEOWNERS`, and given
   the corresponding repository access.

Maintainers who become inactive may move to emeritus status (recorded in
`MAINTAINERS.md`) to keep the active reviewer set accurate. This is not a
judgment — life happens — and returning is always welcome.

## Releases

Maintainers cut releases following [`RELEASING.md`](RELEASING.md): version bump,
`CHANGELOG.md` update, tag, and an automated publish via PyPI trusted publishing.

## Branch protection

`main` is protected: required status checks (CI + DCO), at least one maintainer
review, and no direct pushes. All changes land through pull requests.

## Code of Conduct

Participation is governed by our [Code of Conduct](CODE_OF_CONDUCT.md).
Maintainers are responsible for its fair enforcement.
