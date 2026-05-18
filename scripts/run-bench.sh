#!/usr/bin/env bash
# scripts/run-bench.sh — automate the vanilla vs. optimized bench.
#
# What it does:
#   1. Snapshots ~/.claude.json (the MCP config) so we can restore.
#   2. Removes crawfish-codebase from user-scope MCPs (vanilla baseline).
#   3. Runs the combined 3-task prompt via `claude -p`, captures session ID.
#   4. Re-installs crawfish-codebase, optionally with the policy hook.
#   5. Runs the same prompt again, captures the second session ID.
#   6. Restores the original MCP config.
#   7. Prints both UUIDs + the dash compare URL.
#
# Flags:
#   --with-policy   Also install the PreToolUse hook for the optimized side
#                   (force-routes wasteful tool calls). Without this, the
#                   optimizer is just available; agents may not use it.
#   --skip-restore  Leave the optimized config in place after the run
#                   (handy if you want to keep playing in dash).
#   --vanilla-only  Run only the vanilla side (e.g. to refresh a baseline).
#   --opt-only      Run only the optimized side (re-uses an existing baseline).
#
# Output: prints "VANILLA=<sid>" and "OPTIMIZED=<sid>" lines that you can
# paste straight into dash → Compare.

set -euo pipefail

# ─── locate everything ────────────────────────────────────────────────────
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OPT_BIN="$ROOT/desktop/opt-codebase/dist/index.js"
HOOK_BIN="$ROOT/desktop/dash/dist/policy/hook.js"
DASH_BIN="$ROOT/desktop/dash/dist/index.js"
SETTINGS_JSON="$HOME/.claude.json"
DASH_URL="${DASH_URL:-http://127.0.0.1:7880}"

WITH_POLICY=0
SKIP_RESTORE=0
RUN_VANILLA=1
RUN_OPTIMIZED=1
REPEAT=1

while [ $# -gt 0 ]; do
  case "$1" in
    --with-policy)  WITH_POLICY=1 ;;
    --skip-restore) SKIP_RESTORE=1 ;;
    --vanilla-only) RUN_OPTIMIZED=0 ;;
    --opt-only)     RUN_VANILLA=0 ;;
    --repeat)       REPEAT=$2; shift ;;
    --repeat=*)     REPEAT=${1#--repeat=} ;;
    -h|--help)
      grep -E '^#( |$)' "$0" | sed 's/^# \?//'
      exit 0
      ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
  shift
done

if ! [[ "$REPEAT" =~ ^[1-9][0-9]*$ ]]; then
  echo "error: --repeat must be a positive integer" >&2
  exit 2
fi

# ─── sanity checks ────────────────────────────────────────────────────────
need() { command -v "$1" >/dev/null 2>&1 || { echo "missing: $1" >&2; exit 1; }; }
need claude
need jq
need node

[ -f "$OPT_BIN"  ] || { echo "missing: $OPT_BIN. Run: cd desktop/opt-codebase && npm run build" >&2; exit 1; }
[ -f "$HOOK_BIN" ] || { echo "missing: $HOOK_BIN. Run: cd desktop/dash && npm run build" >&2; exit 1; }
[ -f "$SETTINGS_JSON" ] || { echo "no $SETTINGS_JSON yet — run claude once to create it" >&2; exit 1; }

# ─── combined prompt ──────────────────────────────────────────────────────
# Single prompt covering all three audits in one session, so we get one
# session ID per side. Subagents still fan out as before.
read -r -d '' COMBINED_PROMPT <<'PROMPT_EOF' || true
You will run three code-review tasks in sequence on this repo
(/Users/nealkotval/crawfish). Send each finding through to me when ready.

## Task 1 — crawfish-lens code quality
Audit the crawfish-lens TypeScript codebase for code quality issues.
Spawn 3 Explore subagents in parallel:
  1. server layer: src/server/index.ts, src/server/api.ts, src/server/graph.ts,
     src/server/tail.ts, src/server/sse.ts, src/server/static.ts
  2. data layer: src/transcript.ts, src/stats.ts, src/topology.ts,
     src/savings.ts, src/diagnoses/
  3. React frontend: web/src/App.tsx, web/src/routes/*, web/src/components/*
Each subagent reports findings with file:line references.

## Task 2 — dash policy enforcement security
Audit crawfish-dash policy enforcement for security and edge-case gaps.
Spawn 2 Explore subagents in parallel:
  1. crawfish-dash/src/policy/* — schema, evaluator, store, hook, install
  2. crawfish-dash/web/src/routes/policies.tsx + AgentEditor.tsx
Quote vulnerable code with file:line.

## Task 3 — Benchmarks tab end-to-end review
Review crawfish-dash Benchmarks. Spawn 2 Explore subagents in parallel:
  1. crawfish-dash/src/bench/runner.ts methodology
  2. crawfish-dash/web/src/routes/benchmarks.tsx visualization choices

After all three tasks, produce a single ranked list of the top 5 most
impactful improvements across all the audits.
PROMPT_EOF

# ─── helpers ──────────────────────────────────────────────────────────────
backup_settings() {
  local ts; ts=$(date +%Y%m%d-%H%M%S)
  cp "$SETTINGS_JSON" "$SETTINGS_JSON.bench-$ts.bak"
  echo "$SETTINGS_JSON.bench-$ts.bak"
}

uninstall_codebase() {
  claude mcp remove -s user crawfish-codebase >/dev/null 2>&1 || true
}

install_codebase() {
  # Idempotent — if it's already added, that's fine. Tolerate non-zero exit.
  claude mcp add -s user crawfish-codebase -- node "$OPT_BIN" >/dev/null 2>&1 || true
}

install_hook() {
  node "$DASH_BIN" install-hooks --command "$HOOK_BIN" --yes >/dev/null
}

uninstall_hook() {
  node "$DASH_BIN" uninstall-hooks --command "$HOOK_BIN" >/dev/null 2>&1 || true
}

# Run claude with the combined prompt; capture session id from JSON output.
# Stderr is preserved so the user sees progress.
run_side() {
  local label="$1"
  echo "─── Running $label side ───" >&2
  cd "$ROOT"

  local out
  out=$(claude -p "$COMBINED_PROMPT" --output-format json 2>/dev/null) || {
    echo "FAILED: claude -p exited non-zero on $label side" >&2
    return 1
  }

  local sid
  sid=$(echo "$out" | jq -r '.session_id // .sessionId // empty')
  if [ -z "$sid" ]; then
    echo "WARN: couldn't extract session ID from claude output. Falling back to mtime." >&2
    sid=$(ls -t ~/.claude/projects/-Users-nealkotval-crawfish/*.jsonl 2>/dev/null | head -1 | xargs -I{} basename {} .jsonl)
  fi
  echo "$sid"
}

# ─── plan ─────────────────────────────────────────────────────────────────
echo
echo "Bench plan:"
[ $RUN_VANILLA -eq 1 ]   && echo "  • vanilla baseline (no crawfish MCPs)"
[ $RUN_OPTIMIZED -eq 1 ] && echo "  • optimized (crawfish-codebase installed$([ $WITH_POLICY -eq 1 ] && echo ' + policy hook'))"
[ $SKIP_RESTORE -eq 1 ]  && echo "  • leaving optimized config in place after run"
echo

# ─── execute ──────────────────────────────────────────────────────────────
BAK=$(backup_settings)
echo "MCP config backed up to: $BAK"
echo

VANILLA_SIDS=()
OPTIMIZED_SIDS=()

if [ $RUN_VANILLA -eq 1 ]; then
  uninstall_codebase
  uninstall_hook
  echo "(crawfish-codebase removed; policy hook removed)" >&2
  for ((i=1; i<=REPEAT; i++)); do
    SID=$(run_side "VANILLA $i/$REPEAT")
    VANILLA_SIDS+=("$SID")
    echo "VANILLA[$i]=$SID"
  done
fi

if [ $RUN_OPTIMIZED -eq 1 ]; then
  install_codebase
  echo "(crawfish-codebase installed)" >&2
  if [ $WITH_POLICY -eq 1 ]; then
    install_hook
    echo "(policy hook installed)" >&2
  fi
  for ((i=1; i<=REPEAT; i++)); do
    SID=$(run_side "OPTIMIZED $i/$REPEAT")
    OPTIMIZED_SIDS+=("$SID")
    echo "OPTIMIZED[$i]=$SID"
  done
fi

# ─── restore ──────────────────────────────────────────────────────────────
if [ $SKIP_RESTORE -eq 0 ]; then
  uninstall_hook 2>/dev/null || true
  echo "Restoring $SETTINGS_JSON from $BAK" >&2
  cp "$BAK" "$SETTINGS_JSON"
fi

# ─── manifest ─────────────────────────────────────────────────────────────
MANIFEST=~/.crawfish/bench-runs.jsonl
mkdir -p ~/.crawfish
{
  echo -n '{"ts":"'"$(date -u +%Y-%m-%dT%H:%M:%SZ)"'","repeat":'"$REPEAT"',"withPolicy":'$WITH_POLICY','
  echo -n '"vanilla":['
  if [ ${#VANILLA_SIDS[@]} -gt 0 ]; then
    printf '"%s"' "${VANILLA_SIDS[0]}"
    for sid in "${VANILLA_SIDS[@]:1}"; do printf ',"%s"' "$sid"; done
  fi
  echo -n '],'
  echo -n '"optimized":['
  if [ ${#OPTIMIZED_SIDS[@]} -gt 0 ]; then
    printf '"%s"' "${OPTIMIZED_SIDS[0]}"
    for sid in "${OPTIMIZED_SIDS[@]:1}"; do printf ',"%s"' "$sid"; done
  fi
  echo -n ']}'
  echo
} >> "$MANIFEST"
echo "Appended manifest entry to $MANIFEST"

echo
echo "Done — $REPEAT repeat$([ $REPEAT -gt 1 ] && echo 's') per side."
[ ${#VANILLA_SIDS[@]} -gt 0 ]   && echo "  vanilla:   ${VANILLA_SIDS[*]}"
[ ${#OPTIMIZED_SIDS[@]} -gt 0 ] && echo "  optimized: ${OPTIMIZED_SIDS[*]}"
echo
echo "Run analysis:  ./scripts/analyze-bench.sh"
echo "Or open dash:  $DASH_URL/compare"
