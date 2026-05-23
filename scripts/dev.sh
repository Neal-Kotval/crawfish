#!/usr/bin/env bash
# scripts/dev.sh — one command to launch the whole stack.
#
# Starts (default = everything):
#   CLOUD (canonical tier — ADR-003):
#     - server   on :7882 (cloud/server — Express + Prisma API)
#     - platform on :5174 (cloud/platform — Vite web app)  ← opens here by default
#   DESKTOP:
#     - lens     on :7878 (built bundle, serves API + transcript reader)
#     - dash     on :7880 (built bundle, proxied to by Vite)
#     - vite     on :7881 (HMR for desktop/dash web)
#
# Ctrl-C once to stop everything.
#
# Flags:
#   --cloud-only    only the cloud tier (server + platform)
#   --desktop-only  only the desktop tier (lens + dash + vite)
#   --rebuild       run `npm run build` first (needed if you changed lens/dash src/)
#   --no-open       don't auto-open the browser
#   --lens-only     desktop: skip Vite (just lens + dash)
#   --vite-only     desktop: skip lens+dash (assume something else is on :7880)

set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="$(pwd)"

REBUILD=false
OPEN=true
RUN_CLOUD=true
RUN_API=true        # desktop lens + dash
RUN_VITE=true       # desktop dash HMR

for arg in "$@"; do
  case "$arg" in
    --cloud-only)   RUN_API=false; RUN_VITE=false ;;
    --desktop-only) RUN_CLOUD=false ;;
    --rebuild)      REBUILD=true ;;
    --no-open)      OPEN=false ;;
    --lens-only)    RUN_VITE=false ;;
    --vite-only)    RUN_API=false ;;
    -h|--help)
      sed -n '2,26p' "$0" | sed 's/^# \{0,1\}//'
      exit 0 ;;
    *)
      echo "unknown flag: $arg (try --help)" >&2; exit 1 ;;
  esac
done

# ─── cleanup ─────────────────────────────────────────────────────────────
PIDS=()
ALL_PORTS=(7882 5174 7878 7880 7881)
cleanup() {
  echo
  echo "crawfish-dev: stopping…"
  for pid in "${PIDS[@]:-}"; do
    [[ -n "${pid:-}" ]] && kill "$pid" 2>/dev/null || true
  done
  # belt-and-suspenders: free every port we might own
  for port in "${ALL_PORTS[@]}"; do
    pid="$(lsof -ti ":$port" 2>/dev/null || true)"
    [[ -n "$pid" ]] && kill "$pid" 2>/dev/null || true
  done
  exit 0
}
trap cleanup INT TERM

# ─── port preflight ──────────────────────────────────────────────────────
PORTS=()
[[ "$RUN_CLOUD" == true ]] && PORTS+=(7882 5174)
[[ "$RUN_API"   == true ]] && PORTS+=(7878 7880)
[[ "$RUN_VITE"  == true ]] && PORTS+=(7881)
for port in "${PORTS[@]:-}"; do
  if pid="$(lsof -ti ":$port" 2>/dev/null)"; then
    echo "crawfish-dev: killing existing process on :$port (pid $pid)"
    kill "$pid" 2>/dev/null || true
    sleep 0.3
  fi
done

# ─── rebuild (optional, desktop bundles) ─────────────────────────────────
if [[ "$REBUILD" == true ]]; then
  echo "crawfish-dev: rebuilding lens + dash…"
  npm run build
fi

# Desktop needs built dist bundles. If they're missing and we're not
# rebuilding, skip the desktop tier instead of aborting — cloud still comes up.
if [[ "$RUN_API" == true ]]; then
  for p in desktop/lens/dist/index.js desktop/dash/dist/index.js; do
    if [[ ! -f "$ROOT/$p" ]]; then
      echo "crawfish-dev: $p missing — skipping desktop tier (run with --rebuild to include it)"
      RUN_API=false
      RUN_VITE=false
      break
    fi
  done
fi

# ─── boot cloud server (:7882) ───────────────────────────────────────────
if [[ "$RUN_CLOUD" == true ]]; then
  echo "crawfish-dev: starting cloud server (:7882)…"
  ( cd cloud/server && npm run dev ) &
  PIDS+=($!)
  for _ in $(seq 1 40); do
    if curl -sf -o /dev/null http://127.0.0.1:7882/api/health; then break; fi
    sleep 0.5
  done
fi

# ─── boot cloud platform (:5174) ─────────────────────────────────────────
if [[ "$RUN_CLOUD" == true ]]; then
  echo "crawfish-dev: starting cloud platform (:5174)…"
  ( cd cloud/platform && npm run dev ) &
  PIDS+=($!)
  for _ in $(seq 1 40); do
    if curl -sf -o /dev/null http://127.0.0.1:5174/; then break; fi
    sleep 0.5
  done
fi

# ─── boot desktop API (lens + dash) ──────────────────────────────────────
if [[ "$RUN_API" == true ]]; then
  echo "crawfish-dev: starting lens (:7878) + dash (:7880)…"
  npm start --silent -- --no-open &
  PIDS+=($!)
  for _ in $(seq 1 40); do
    if curl -sf -o /dev/null http://127.0.0.1:7880/; then break; fi
    sleep 0.5
  done
fi

# ─── boot Vite HMR for the desktop dash UI (:7881) ───────────────────────
if [[ "$RUN_VITE" == true ]]; then
  echo "crawfish-dev: starting Vite HMR (:7881)…"
  ( cd desktop/dash && npm run web:dev --silent ) &
  PIDS+=($!)
  for _ in $(seq 1 40); do
    if curl -sf -o /dev/null http://127.0.0.1:7881/; then break; fi
    sleep 0.5
  done
fi

# Open the canonical surface (cloud platform) by default; fall back to the
# desktop Vite HMR url when running --desktop-only.
if [[ "$RUN_CLOUD" == true ]]; then
  URL="http://127.0.0.1:5174"
elif [[ "$RUN_VITE" == true ]]; then
  URL="http://127.0.0.1:7881"
else
  URL="http://127.0.0.1:7880"
fi

echo
echo "  crawfish-dev ready"
[[ "$RUN_CLOUD" == true ]] && echo "    server:   http://127.0.0.1:7882  (cloud API)"
[[ "$RUN_CLOUD" == true ]] && echo "    platform: http://127.0.0.1:5174  (cloud web app — canonical)"
[[ "$RUN_API"   == true ]] && echo "    lens:     http://127.0.0.1:7878"
[[ "$RUN_API"   == true ]] && echo "    dash:     http://127.0.0.1:7880  (built bundle)"
[[ "$RUN_VITE"  == true ]] && echo "    vite:     http://127.0.0.1:7881  (desktop HMR)"
echo
echo "  Opening $URL"
echo "  Ctrl-C to stop."

if [[ "$OPEN" == true ]] && command -v open >/dev/null 2>&1; then
  open "$URL"
fi

# Park on the first started process so Ctrl-C reaches the trap.
wait "${PIDS[0]}"
