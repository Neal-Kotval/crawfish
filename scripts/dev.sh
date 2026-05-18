#!/usr/bin/env bash
# scripts/dev.sh — one-command UI iteration loop.
#
# Starts:
#   - lens   on :7878 (built bundle, serves API + transcript reader)
#   - dash   on :7880 (built bundle, proxied to by Vite)
#   - vite   on :7881 (HMR for crawfish-dash/web — save .tsx/.css, see it instantly)
#
# Open http://127.0.0.1:7881 in your browser. Ctrl-C once to stop everything.
#
# Flags:
#   --rebuild       run `npm run build` first (needed if you changed lens/dash src/)
#   --no-open       don't auto-open the browser
#   --lens-only     skip Vite (just run lens + dash)
#   --vite-only     skip lens+dash (assume something else is on :7880)

set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="$(pwd)"

REBUILD=false
OPEN=true
RUN_API=true
RUN_VITE=true

for arg in "$@"; do
  case "$arg" in
    --rebuild)    REBUILD=true ;;
    --no-open)    OPEN=false ;;
    --lens-only)  RUN_VITE=false ;;
    --vite-only)  RUN_API=false ;;
    -h|--help)
      sed -n '2,16p' "$0" | sed 's/^# \{0,1\}//'
      exit 0 ;;
    *)
      echo "unknown flag: $arg (try --help)" >&2; exit 1 ;;
  esac
done

# ─── cleanup ─────────────────────────────────────────────────────────────
PIDS=()
cleanup() {
  echo
  echo "crawfish-dev: stopping…"
  for pid in "${PIDS[@]:-}"; do
    [[ -n "${pid:-}" ]] && kill "$pid" 2>/dev/null || true
  done
  # belt-and-suspenders: free the ports
  for port in 7878 7880 7881; do
    pid="$(lsof -ti ":$port" 2>/dev/null || true)"
    [[ -n "$pid" ]] && kill "$pid" 2>/dev/null || true
  done
  exit 0
}
trap cleanup INT TERM

# ─── port preflight ──────────────────────────────────────────────────────
for port in 7878 7880 7881; do
  if pid="$(lsof -ti ":$port" 2>/dev/null)"; then
    echo "crawfish-dev: killing existing process on :$port (pid $pid)"
    kill "$pid" 2>/dev/null || true
    sleep 0.3
  fi
done

# ─── rebuild (optional) ──────────────────────────────────────────────────
if [[ "$REBUILD" == true ]]; then
  echo "crawfish-dev: rebuilding lens + dash…"
  npm run build
fi

# Verify dist exists if we're running the API
if [[ "$RUN_API" == true ]]; then
  for p in desktop/lens/dist/index.js desktop/dash/dist/index.js; do
    if [[ ! -f "$ROOT/$p" ]]; then
      echo "crawfish-dev: $p missing — run with --rebuild first"
      exit 1
    fi
  done
fi

# ─── boot API (lens + dash) ──────────────────────────────────────────────
if [[ "$RUN_API" == true ]]; then
  echo "crawfish-dev: starting lens (:7878) + dash (:7880)…"
  npm start --silent -- --no-open &
  PIDS+=($!)
  # wait until dash answers (max 20s)
  for _ in $(seq 1 40); do
    if curl -sf -o /dev/null http://127.0.0.1:7880/; then break; fi
    sleep 0.5
  done
fi

# ─── boot Vite HMR for the dash UI ───────────────────────────────────────
if [[ "$RUN_VITE" == true ]]; then
  echo "crawfish-dev: starting Vite HMR (:7881)…"
  ( cd desktop/dash && npm run web:dev --silent ) &
  PIDS+=($!)
  for _ in $(seq 1 40); do
    if curl -sf -o /dev/null http://127.0.0.1:7881/; then break; fi
    sleep 0.5
  done
fi

URL="http://127.0.0.1:$([[ "$RUN_VITE" == true ]] && echo 7881 || echo 7880)"
echo
echo "  crawfish-dev ready"
[[ "$RUN_API"  == true ]] && echo "    lens:    http://127.0.0.1:7878"
[[ "$RUN_API"  == true ]] && echo "    dash:    http://127.0.0.1:7880  (built bundle)"
[[ "$RUN_VITE" == true ]] && echo "    vite:    $URL  (HMR — edit .tsx/.css and see it instantly)"
echo
echo "  Ctrl-C to stop."

if [[ "$OPEN" == true ]] && command -v open >/dev/null 2>&1; then
  open "$URL"
fi

# Park on whichever process the user is most likely watching
wait "${PIDS[0]}"
