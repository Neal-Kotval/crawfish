#!/usr/bin/env bash
# dev.sh — start every Crawfish dev surface at once.
#
# Brings up five processes:
#   • dash node server        http://127.0.0.1:7880   (REST: /api/orgs, /api/sessions, …)
#   • dash vite SPA           http://127.0.0.1:7881   (the dash UI; /api proxied to :7880)
#   • marketing vite          http://127.0.0.1:5173   (crawfish.dev front door)
#   • platform vite           http://127.0.0.1:5174   (signed-in collab skeleton)
#   • crawfish-server         http://127.0.0.1:7882   (Wave 2 cloud API: orgs, invites, link)
#
# Logs stream into ./dev-logs/. Ctrl-C kills all four cleanly.
#
# To also run the Tauri shell against the dash:
#   cd desktop/app && npm run dev      (in another terminal)
# That spawns its own dash node server, so don't start both at once.
#
# To install Dash so the `crawfish-dash://` URL scheme works in browsers:
#   ./build-app.sh --install
# (Slow — runs only when you change the Rust shell or tauri.conf.json.)

set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="$ROOT/dev-logs"
mkdir -p "$LOG_DIR"

PIDS=()

cleanup() {
  echo
  echo "▶ stopping dev servers…"
  for pid in "${PIDS[@]}"; do
    if kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
    fi
  done
  # belt-and-suspenders: also kill anything still on these ports
  for port in 7880 7881 7882 5173 5174; do
    lsof -ti tcp:"$port" 2>/dev/null | xargs -r kill 2>/dev/null || true
  done
  wait 2>/dev/null
  echo "▶ all dev servers stopped."
}
trap cleanup INT TERM EXIT

free_port() {
  local port=$1 name=$2
  if lsof -ti tcp:"$port" >/dev/null 2>&1; then
    echo "⚠ port $port (for $name) already in use — killing previous process"
    lsof -ti tcp:"$port" | xargs -r kill 2>/dev/null || true
    sleep 0.5
  fi
}

start() {
  local name=$1 dir=$2 cmd=$3 port=$4
  echo "▶ starting $name (port $port) — logs: $LOG_DIR/$name.log"
  free_port "$port" "$name"
  (
    cd "$ROOT/$dir"
    eval "$cmd"
  ) >"$LOG_DIR/$name.log" 2>&1 &
  PIDS+=("$!")
}

# Build the dash server once before launching (its tsx invocation reads source
# directly, but the templates / policy code expects no stale artifacts).
echo "▶ pre-flight: type-checking dash server…"
(cd "$ROOT/desktop/dash" && npx tsc --noEmit) || {
  echo "✗ dash server type-check failed — aborting"; exit 1; }

start dash-node     desktop/dash       "npm run serve"   7880
start cf-server     cloud/server       "npm run dev"     7882
# Give the node servers a moment so vite's first proxy call doesn't fail.
sleep 1
start dash-web      desktop/dash       "npm run web:dev" 7881
start marketing     web                "npm run dev"     5173
start platform      cloud/platform     "npm run dev"     5174

# Give Vite a moment to actually bind to 5174 before launching the browser.
PORTAL_URL="${PORTAL_URL:-http://localhost:5174}"
if [ "${NO_OPEN:-0}" != "1" ] && command -v open >/dev/null 2>&1; then
  ( sleep 3 && open "$PORTAL_URL" 2>/dev/null || true ) &
fi

cat <<EOF

────────────────────────────────────────────────────────────────────
  Crawfish dev — all four surfaces up
────────────────────────────────────────────────────────────────────
  marketing    →  http://localhost:5173
  platform     →  http://localhost:5174
  dash (web)   →  http://localhost:7881/canvas
  dash (api)   →  http://localhost:7880/api/orgs
  cf-server    →  http://localhost:7882/api/health
  Tauri shell  →  cd desktop/app && npm run dev   (separate terminal)

  Logs:       tail -f dev-logs/<name>.log
  Stop:       Ctrl-C
────────────────────────────────────────────────────────────────────

  Opening $PORTAL_URL in your browser. Set NO_OPEN=1 to skip.

EOF

# Wait on all background PIDs so Ctrl-C reaches us.
wait
