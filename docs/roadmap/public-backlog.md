# Public backlog

This is the contributor-facing backlog. **GitHub Issues are the source of truth
for contributor work** — the narrative roadmap lives in
[`README.md`](README.md), and the claimable, well-scoped tasks live as GitHub
Issues you can pick up today.

## How to claim an issue

1. Find an open issue — start with the
   [`good first issue`](https://github.com/Neal-Kotval/crawfish/labels/good%20first%20issue)
   and [`connector`](https://github.com/Neal-Kotval/crawfish/labels/connector)
   labels.
2. **Comment on it to claim it** — a maintainer will assign it to you. This keeps
   two people from doing the same work.
3. Open a PR that closes the issue. See the
   [PR template](https://github.com/Neal-Kotval/crawfish/blob/main/.github/PULL_REQUEST_TEMPLATE.md): tests, docs, `just check`
   green, and a **DCO `Signed-off-by`** on every commit (`git commit -s`).

Questions? Use
[Discussions](https://github.com/Neal-Kotval/crawfish/discussions) — not a new
issue.

## The canonical first contribution: a connector

A new **Source / Sink / Definition** is a small, self-contained PR: typed seams
plus entry-point discovery (the `crawfish.sources` / `crawfish.sinks` /
`crawfish.definitions` / `crawfish.types` groups). You add one file, register one
entry point, and it's discovered automatically — no core changes. See the
[connector guide](../guide/contributing-a-connector.md) and use the
**New connector** issue form.

## What's mirrored publicly

The public backlog mirrors the parts of the roadmap that are safe to open up —
small hardening tasks, new connectors, and documentation. Items are described by
their public title only. Seed issues (created by
[`scripts/seed-github-backlog.sh`](https://github.com/Neal-Kotval/crawfish/blob/main/scripts/seed-github-backlog.sh)) include:

### Good first issues (small, well-scoped)

- Add a `--json` flag to `craw doctor`
- Add a `--version`/env footer to `craw doctor` output
- Support `craw list --json` for machine-readable unit discovery
- Document the retry / dead-letter / replay policy
- Friendlier error when `craw dev` gets a missing Definition path
- Validate duplicate `-i key=value` inputs in `craw dev`
- Add a `--quiet` flag to `craw run`
- Expand the getting-started guide with a `craw doctor` + `craw list` walkthrough

### Connectors (new Source / Sink / Definition)

- Slack source (fan out over channel messages)
- Slack sink (post to a static channel)
- RSS/Atom source (no-auth feed — easiest first connector)
- Postgres source (fan out over query rows)
- Generic webhook sink (POST to a static URL)

More connectors are welcome beyond this list — Notion, Gmail, Jira, and others
all fit the same shape. Open a **New connector** issue to propose one.

## Maintaining the backlog

GitHub is the public source of truth for contributor-facing work. Maintainers
keep the internal roadmap and the GitHub backlog in rough sync by hand; there is
no automated mirror, and **no internal tracker IDs appear in public issues**. To
(re)seed labels and starter issues, run
[`scripts/seed-github-backlog.sh`](https://github.com/Neal-Kotval/crawfish/blob/main/scripts/seed-github-backlog.sh) — it is
idempotent.
