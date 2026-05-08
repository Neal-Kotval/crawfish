#!/usr/bin/env bash
# scripts/analyze-bench.sh — read the latest bench-runs manifest and compute
# medians + per-tool averages across all repeats. Prints a clean summary.

set -euo pipefail

MANIFEST=~/.crawfish/bench-runs.jsonl

if [ ! -f "$MANIFEST" ]; then
  echo "no manifest at $MANIFEST — run scripts/run-bench.sh first" >&2
  exit 1
fi

LATEST=$(tail -1 "$MANIFEST")

if [ -z "$LATEST" ]; then
  echo "manifest is empty" >&2
  exit 1
fi

LENS_URL="${LENS_URL:-http://127.0.0.1:7878}"

# Quick health check — analysis depends on lens being up.
if ! curl -sf "$LENS_URL/api/health" >/dev/null 2>&1; then
  echo "lens not reachable at $LENS_URL — start it with: node bin/crawfish.js" >&2
  exit 1
fi

python3 - "$LATEST" "$LENS_URL" <<'PY'
import json, sys, urllib.request, statistics

entry = json.loads(sys.argv[1])
lens = sys.argv[2]

vanilla_sids   = entry.get("vanilla",   [])
optimized_sids = entry.get("optimized", [])

def get(sid):
    return json.loads(
        urllib.request.urlopen(f"{lens}/api/sessions/{sid}/savings").read()
    )

def detail(sid):
    return json.loads(
        urllib.request.urlopen(f"{lens}/api/sessions/{sid}").read()
    )

def fmt(n):
    sign = "+" if n > 0 else ("−" if n < 0 else " ")
    n = abs(n)
    if n < 1000: return f"{sign}{int(n)}"
    if n < 1_000_000: return f"{sign}{n/1000:.1f}K"
    return f"{sign}{n/1_000_000:.2f}M"

def fmtu(n):
    if n < 1000: return str(int(n))
    if n < 1_000_000: return f"{n/1000:.1f}K"
    return f"{n/1_000_000:.2f}M"

def gather(sids, label):
    rows = []
    for sid in sids:
        s = get(sid)
        rows.append({
            "sid": sid,
            "tokens": s["totalTokens"],
            "subagents": s["subagentCount"],
            "savings": s["estimatedSavings"],
        })
    if not rows:
        return None
    print(f"\n  {label}:")
    print(f"    {'sid':<12} {'total':>13} {'subagents':>10}")
    for r in rows:
        print(f"    {r['sid'][:8]:<12} {r['tokens']:>13,} {r['subagents']:>10}")
    return rows

print(f"\nManifest: {entry['ts']}  repeat={entry['repeat']}  withPolicy={entry['withPolicy']}")

V = gather(vanilla_sids,   "VANILLA runs")
O = gather(optimized_sids, "OPTIMIZED runs")

if not V or not O:
    print("\nNeed at least one of each side for a comparison.")
    sys.exit(0)

vmed = statistics.median([r["tokens"] for r in V])
omed = statistics.median([r["tokens"] for r in O])
delta = omed - vmed
pct = delta / vmed * 100 if vmed else 0

vmin = min(r["tokens"] for r in V); vmax = max(r["tokens"] for r in V)
omin = min(r["tokens"] for r in O); omax = max(r["tokens"] for r in O)

print()
print("─── Median totals ───")
print(f"  vanilla   median: {int(vmed):>13,}    range {fmtu(vmin)}…{fmtu(vmax)}")
print(f"  optimized median: {int(omed):>13,}    range {fmtu(omin)}…{fmtu(omax)}")
print(f"  delta:            {fmt(delta):>13}     {pct:+.1f}%")
print()

# Aggregate per-tool across all subagent transcripts
import subprocess
def subagent_tools(sids):
    counts = {}
    for sid in sids:
        out = subprocess.run([
            "bash", "-c",
            f"for f in ~/.claude/projects/*/{sid}*/subagents/*.jsonl; do "
            f"  [ -f \"$f\" ] && jq -r 'select(.type==\"assistant\") | .message.content[]? | select(.type==\"tool_use\") | .name' \"$f\" 2>/dev/null; "
            f"done"
        ], capture_output=True, text=True)
        for line in out.stdout.strip().split("\n"):
            if not line.strip(): continue
            counts[line] = counts.get(line, 0) + 1
    return counts

V_tools = subagent_tools(vanilla_sids)
O_tools = subagent_tools(optimized_sids)

print("─── Subagent tool calls (totals across all repeats) ───")
all_tools = sorted(set(V_tools) | set(O_tools), key=lambda t: -(V_tools.get(t,0) + O_tools.get(t,0)))
print(f"  {'tool':<42} {'vanilla':>10} {'optimized':>10}")
print(f"  {'─'*42} {'─'*10} {'─'*10}")
for t in all_tools:
    print(f"  {t:<42} {V_tools.get(t,0):>10} {O_tools.get(t,0):>10}")
PY
