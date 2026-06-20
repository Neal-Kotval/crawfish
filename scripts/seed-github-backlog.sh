#!/usr/bin/env bash
#
# seed-github-backlog.sh — create/refresh Crawfish's public labels and seed the
# claimable GitHub issue backlog.
#
# WHAT IT DOES
#   1. Creates (or updates) every label in the public label set.
#   2. Opens 13 seed issues derived from real, small tasks in this repo. A solid
#      set are labeled `good first issue`; several propose new `connector`s.
#
# IT IS IDEMPOTENT: re-running it edits existing labels instead of failing, and
# skips any seed issue whose exact title already exists. Safe to run repeatedly.
#
# PREREQUISITES
#   - GitHub CLI installed:            https://cli.github.com
#   - Authenticated:                   gh auth login
#   - A repo to target. Either run this from inside the cloned repo (gh infers
#     it) or set REPO explicitly:      REPO=TODO-maintainer/crawfish ./scripts/seed-github-backlog.sh
#
#   This script contains NO tokens or secrets — it relies entirely on your
#   `gh auth` session.
#
# USAGE
#   ./scripts/seed-github-backlog.sh                 # uses the current repo
#   REPO=owner/name ./scripts/seed-github-backlog.sh # explicit target
#   DRY_RUN=1 ./scripts/seed-github-backlog.sh        # print actions, change nothing
#
set -euo pipefail

# --------------------------------------------------------------------------- setup
REPO="${REPO:-}"          # empty => gh uses the repo of the current directory
DRY_RUN="${DRY_RUN:-0}"

if ! command -v gh >/dev/null 2>&1; then
  echo "error: the GitHub CLI (gh) is not installed — see https://cli.github.com" >&2
  exit 1
fi
if ! gh auth status >/dev/null 2>&1; then
  echo "error: not authenticated — run 'gh auth login' first" >&2
  exit 1
fi

# Pass -R only when REPO is set, so the no-arg form works from inside the repo.
repo_args=()
if [[ -n "$REPO" ]]; then
  repo_args=(-R "$REPO")
fi

run() {
  if [[ "$DRY_RUN" == "1" ]]; then
    printf 'DRY_RUN:'; printf ' %q' "$@"; printf '\n'
  else
    "$@"
  fi
}

# --------------------------------------------------------------------------- labels
# name|color|description  (keep in sync with .github/labels.yml)
LABELS=(
  "good first issue|7057ff|Small, well-scoped, has acceptance criteria — a great place to start."
  "help wanted|008672|Maintainers would welcome a contributor picking this up."
  "connector|1d76db|A new Source / Sink / Definition connector to an external service."
  "type: bug|d73a4a|Something is broken or behaves unexpectedly."
  "type: feature|0e8a16|A new capability or improvement."
  "type: docs|0075ca|Documentation changes only."
  "area: core|c5def5|Typed-IO atoms: Flow, Parameter, Node, Policy, RunContext."
  "area: runtime|c5def5|AgentRuntime / claude -p loop and backends."
  "area: store|c5def5|Persistence: Store, ledger, idempotency, artifact store."
  "area: sink|c5def5|Egress boundary: sinks, approval gates, idempotency keys."
  "area: docs|c5def5|Guides, cookbook, API reference, roadmap."
  "priority: high|b60205|Should be addressed soon."
  "priority: medium|fbca04|Normal priority."
  "priority: low|fef2c0|Nice to have; no urgency."
  "status: blocked|e11d21|Blocked on another issue or an external dependency."
)

echo "==> Ensuring labels…"
for spec in "${LABELS[@]}"; do
  IFS='|' read -r name color desc <<<"$spec"
  # create, or edit if it already exists (idempotent)
  if run gh label create "$name" --color "$color" --description "$desc" "${repo_args[@]}" 2>/dev/null; then
    echo "    created: $name"
  else
    run gh label edit "$name" --color "$color" --description "$desc" "${repo_args[@]}" >/dev/null 2>&1 || true
    echo "    updated: $name"
  fi
done

# --------------------------------------------------------------------------- issues
# Open an issue only if no open OR closed issue with the exact title exists.
ensure_issue() {
  local title="$1" labels="$2" body="$3"
  local existing
  existing="$(gh issue list "${repo_args[@]}" --state all --search "in:title \"$title\"" \
    --json title --jq ".[] | select(.title == \"$title\") | .title" 2>/dev/null | head -n1 || true)"
  if [[ -n "$existing" ]]; then
    echo "    skip (exists): $title"
    return 0
  fi
  run gh issue create "${repo_args[@]}" --title "$title" --label "$labels" --body "$body"
  echo "    created: $title"
}

echo "==> Seeding issues…"

# 1 -------------------------------------------------------------------------
ensure_issue \
  "Add a --json flag to \`craw doctor\`" \
  "good first issue,type: feature,area: docs" \
  "\`craw doctor\` (\`packages/crawfish/src/crawfish/doctor.py\`) prints a human-readable
structure-health report via \`DoctorReport.text()\`. Add a \`--json\` flag to the
\`doctor\` subparser in \`packages/crawfish/src/crawfish/cli.py\` that emits the
\`DoctorReport\` as JSON instead, so the report is machine-consumable in CI.

**Acceptance criteria**
- \`craw doctor --json\` prints \`{\"ok\": bool, \"findings\": [{\"level\", \"message\"}, …]}\`.
- Exit code is unchanged (0 when \`report.ok\`, else 1).
- A test in \`packages/crawfish/tests/\` asserts the JSON shape for a healthy and an unhealthy project.

**Pointers:** \`cli.py:_cmd_doctor\`, \`doctor.py\` (\`DoctorReport\` is a Pydantic model — \`model_dump_json()\` is your friend)."

# 2 -------------------------------------------------------------------------
ensure_issue \
  "Add \`--version\`/env footer to \`craw doctor\` output" \
  "good first issue,area: docs" \
  "When a contributor pastes \`craw doctor\` output into a bug report, we also want the
Crawfish version and Python version inline. Add a single info-level finding (or a
footer line) to \`diagnose()\` output that includes \`crawfish <version>\` and the
Python version.

**Acceptance criteria**
- \`craw doctor\` output includes the Crawfish version (reuse \`cli._version()\`) and \`platform.python_version()\`.
- It appears as an \`info\` finding so it never flips \`report.ok\`.
- Covered by a test.

**Pointers:** \`doctor.py:diagnose\`, \`cli.py:_version\`."

# 3 -------------------------------------------------------------------------
ensure_issue \
  "Support \`craw list --json\` for machine-readable unit discovery" \
  "good first issue,area: core" \
  "\`craw list\` (\`cli.py:_cmd_list\`) prints discovered units as a fixed-width table.
Add \`--json\` so tooling can consume the registry. Each entry should include
\`kind\`, \`name\`, and \`origin\` (from \`discovery.UnitRef\`).

**Acceptance criteria**
- \`craw list --json\` prints a JSON array sorted by \`(kind, name)\`.
- The human table output is unchanged when \`--json\` is absent.
- Test covers a project with at least one local unit.

**Pointers:** \`discovery.py\` (\`Registry.discover\`, \`UnitRef\`), \`cli.py:_cmd_list\`."

# 4 -------------------------------------------------------------------------
ensure_issue \
  "Document the retry / dead-letter / replay policy" \
  "good first issue,type: docs,area: docs" \
  "The framework has retries, a dead-letter path, and replay (roadmap M3, implemented
in \`packages/crawfish/src/crawfish/retry.py\` and the ledger). There is no
contributor-facing doc explaining the policy, the backoff defaults, what lands in
the dead-letter, and how to replay a failed run.

**Acceptance criteria**
- A new \`docs/guide/retries-and-replay.md\` explains the retry policy, dead-letter semantics, and the replay path.
- It is linked from \`docs/guide/concepts.md\` (or the docs index).
- Claims are verified against \`retry.py\` and \`ledger.py\` (no invented behaviour).

**Pointers:** \`retry.py\`, \`ledger.py\`, \`docs/roadmap/README.md\`."

# 5 -------------------------------------------------------------------------
ensure_issue \
  "Friendlier error when \`craw dev\` gets a Definition path that doesn't exist" \
  "good first issue,type: bug,area: runtime" \
  "\`craw dev path/to/missing\` currently surfaces a raw exception from
\`Definition.from_package\`. Catch the missing-path case and print a clear,
actionable message (\"no Definition found at <path> — expected instructions.md or
definition.py\") with a non-zero exit code.

**Acceptance criteria**
- A missing/invalid Definition path prints a one-line, human-readable error (no traceback).
- Exit code is non-zero.
- Test asserts the message and exit code.

**Pointers:** \`cli.py:_cmd_dev\`, \`definition/\` (\`Definition.from_package\`)."

# 6 -------------------------------------------------------------------------
ensure_issue \
  "Validate duplicate \`-i key=value\` inputs in \`craw dev\`" \
  "good first issue,area: runtime" \
  "\`craw dev -i a=1 -i a=2\` silently keeps the last value (\`cli.py:_cmd_dev\` builds a
dict). Either warn on a duplicate key or error clearly, so a typo isn't swallowed.

**Acceptance criteria**
- A repeated input key produces a clear warning or error (pick one, document it in \`--help\`).
- Single inputs and distinct keys behave exactly as before.
- Test covers the duplicate-key path.

**Pointers:** \`cli.py:_cmd_dev\` (the \`args.input\` loop)."

# 7 -------------------------------------------------------------------------
ensure_issue \
  "Add a \`--quiet\` flag to \`craw run\`" \
  "good first issue,area: core" \
  "\`craw run\` always prints \`pipeline ok: N output(s)\`. Add \`--quiet\` to suppress the
success line (keeping the exit code) so it composes cleanly in scripts.

**Acceptance criteria**
- \`craw run --quiet\` prints nothing on success and still exits 0.
- Default behaviour is unchanged.
- Test covers both paths.

**Pointers:** \`cli.py:_cmd_run\`, \`engine.py:run_pipeline\`."

# 8 -------------------------------------------------------------------------
ensure_issue \
  "Expand getting-started guide with a \`craw doctor\` + \`craw list\` walkthrough" \
  "good first issue,type: docs,area: docs" \
  "\`docs/guide/getting-started.md\` walks through \`craw init\` and \`craw dev\` but
doesn't show \`craw doctor\` (structure health) or \`craw list\` (discovery). Add a
short section demonstrating both on the scaffolded project so newcomers learn to
self-diagnose.

**Acceptance criteria**
- Getting-started includes real, copy-pasteable \`craw doctor\` and \`craw list\` output from \`craw init\`.
- Commands and output match the current CLI (verify by running them).

**Pointers:** \`docs/guide/getting-started.md\`, \`cli.py\` (\`doctor\`, \`list\`), \`scaffold.py\`."

# 9 -------------------------------------------------------------------------
ensure_issue \
  "Connector: Slack source (fan out over channel messages)" \
  "connector,help wanted,type: feature" \
  "Add a \`SlackSource\` that reads messages from a channel and fans out one Run per
message, modeled on \`PullRequestSource\` in
\`packages/crawfish/src/crawfish/nodes/source.py\`.

**Design**
- Multi source (\`multi = True\`); per-item outputs e.g. \`ts: str\`, \`text: str\` (FLUID, tainted — untrusted user content), with the \`channel\` as a STATIC config target.
- Credential by reference: store the env-var **name** (e.g. \`SLACK_BOT_TOKEN\`) in config; resolve only at fetch time, never in config/Output/logs.
- Ship a deterministic dry-run / fixture path (a \`messages\` config list) so tests stay offline.

**Acceptance criteria**
- \`SlackSource\` discovered via the \`crawfish.sources\` entry-point group (or local \`sources/\`).
- Fixture-backed test fans out N messages into N Outputs, each \`tainted=True\`.
- Read the connector guide: \`docs/guide/contributing-a-connector.md\`.

**Pointers:** \`nodes/source.py\` (\`Source\`, \`fan_out\`, \`PullRequestSource\`), \`discovery.py:ENTRY_POINT_GROUPS\`."

# 10 ------------------------------------------------------------------------
ensure_issue \
  "Connector: Slack sink (post a message to a channel)" \
  "connector,help wanted,type: feature,area: sink" \
  "Add a \`SlackSink\` that posts a message to a **static** channel, modeled on
\`LinearSink\` / \`GitHubPRSink\` in \`packages/crawfish/src/crawfish/nodes/sink.py\`.

**Design**
- The target \`channel\` must be a \`Flow.STATIC\` \`target_param\` — a fluid target must be rejected at construction (this is the egress-redirection guard).
- Inherit idempotency + approval from \`Sink\`; do not reimplement them.
- Credential by reference (env-var name in config). Dry-run by default: record the would-be post into \`self.writes\`.

**Acceptance criteria**
- Constructing \`SlackSink\` with a FLUID \`channel\` target raises \`TargetMustBeStaticError\`.
- A re-run of the same batch/item is a no-op (idempotency key from static config only).
- Dry-run test asserts the recorded write; no network.

**Pointers:** \`nodes/sink.py\` (\`Sink\`, \`LinearSink\`, \`TargetMustBeStaticError\`)."

# 11 ------------------------------------------------------------------------
ensure_issue \
  "Connector: RSS/Atom source (no-auth feed fan-out)" \
  "connector,good first issue,type: feature" \
  "An RSS/Atom source is the simplest possible connector — no auth — which makes it
an ideal first connector contribution. Fan out one Run per feed entry.

**Design**
- Multi source; per-item outputs e.g. \`id: str\`, \`title: str\`, \`link: str\`, \`summary: str\` (FLUID, tainted).
- The feed \`url\` is STATIC config. No credentials.
- Provide a fixture (a saved feed XML or a \`entries\` config list) so tests are offline and deterministic.

**Acceptance criteria**
- \`RssSource\` fans out N entries into N tainted Outputs.
- Stable per-item lineage (use the entry \`id\`) so idempotency keys are stable across re-runs.
- Test runs without network.

**Pointers:** \`nodes/source.py\` (\`fan_out\` lineage rules), \`docs/guide/contributing-a-connector.md\`."

# 12 ------------------------------------------------------------------------
ensure_issue \
  "Connector: Postgres source (fan out over query rows)" \
  "connector,help wanted,type: feature,area: store" \
  "Add a \`PostgresSource\` that runs a **static** query and fans out one Run per row.

**Design**
- Multi source; per-item outputs are the selected columns (FLUID, tainted).
- The DSN/connection is a credential **by reference** (env-var name); the query is STATIC config — never built from fluid/model-derived data.
- Provide a fixture/dry-run path (an injected rows list) so the default test suite needs no live database.

**Acceptance criteria**
- Fixture-backed test fans out rows into tainted Outputs without a live DB.
- The query and connection target are static; document that fluid values must not reach the SQL.
- Optional live path is opt-in and skipped by default.

**Pointers:** \`nodes/source.py\`, \`store/\` (tenancy/\`org_id\` conventions), \`docs/guide/contributing-a-connector.md\`."

# 13 ------------------------------------------------------------------------
ensure_issue \
  "Connector: generic webhook sink (POST to a static URL)" \
  "connector,good first issue,type: feature,area: sink" \
  "Add a \`WebhookSink\` that POSTs the Output to a **static** URL — a generic egress
useful for Zapier/n8n/custom endpoints.

**Design**
- The destination \`url\` must be a \`Flow.STATIC\` \`target_param\`; reject a fluid URL at construction (\`TargetMustBeStaticError\`).
- Optional bearer token by reference (env-var name in config), resolved only at egress.
- Inherit idempotency + approval from \`Sink\`. Dry-run by default: record the request into \`self.writes\`.

**Acceptance criteria**
- Fluid \`url\` target raises \`TargetMustBeStaticError\`.
- Dry-run test asserts the recorded request (method, url, body) with no network.
- Re-running the same batch/item is a no-op.

**Pointers:** \`nodes/sink.py\` (\`Sink\`, \`GitHubPRSink\`), \`docs/architecture/SECURITY.md\` (egress invariants)."

echo "==> Done."
if [[ "$DRY_RUN" == "1" ]]; then
  echo "    (dry run — nothing was changed)"
fi
