#!/usr/bin/env bash
# prod.sh — rebuild everything and run the full crawfish stack.
#
#   1. kill anything on ports 5174, 7880, 7882 (idempotent)
#   2. build cli/projectctl + symlink `craw` into ~/.local/bin
#   3. build cloud/server (tsc)
#   4. build desktop/lens (server only — web is wedged on a stale UI path)
#   5. build desktop/dash (server + web)
#   6. build cloud/platform (tsc + vite)
#   7. rebuild the Tauri desktop shell
#   8. boot cloud/server (7882) and cloud/platform (5174) in the background
#   9. open Crawfish.app — it spawns lens (7878) and dash (7880) itself
#
# Logs land in .prod-logs/. Tail them or run `./prod.sh stop` to kill the bg
# services.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$ROOT/.prod-logs"
mkdir -p "$LOG_DIR"

# ─── port helpers ───────────────────────────────────────────────────────────

kill_port() {
  local port="$1"
  local pids
  pids="$(lsof -ti tcp:"$port" 2>/dev/null || true)"
  if [[ -n "$pids" ]]; then
    echo "  ↪ killing pids on :$port — $pids"
    kill $pids 2>/dev/null || true
    sleep 0.3
    pids="$(lsof -ti tcp:"$port" 2>/dev/null || true)"
    [[ -n "$pids" ]] && kill -9 $pids 2>/dev/null || true
  fi
}

wait_for() {
  local url="$1"
  local label="$2"
  local tries=40 # 40 * 0.5s = 20s
  for ((i = 0; i < tries; i++)); do
    if curl -sSf -o /dev/null --max-time 1 "$url" 2>/dev/null; then
      echo "  ✓ $label up"
      return 0
    fi
    sleep 0.5
  done
  echo "  ✗ $label never responded at $url (see $LOG_DIR for details)"
  return 1
}

# ─── stop subcommand ───────────────────────────────────────────────────────

if [[ "${1:-}" == "stop" ]]; then
  echo "→ stopping crawfish stack"
  for p in 5174 7880 7882 7878; do kill_port "$p"; done
  # also kill the desktop app
  pkill -x crawfish_app 2>/dev/null || true
  pkill -f "Crawfish.app/Contents/MacOS" 2>/dev/null || true
  echo "done."
  exit 0
fi

# Always remove /Applications/Crawfish.app — we only want one copy of the app,
# which is the build artifact under desktop/app/src-tauri/target/release/bundle.
# If the user has dragged the DMG into Applications, that copy gets stale fast.
if [[ -d /Applications/Crawfish.app ]]; then
  echo "→ removing stale /Applications/Crawfish.app (build copy is canonical)"
  rm -rf /Applications/Crawfish.app
fi

# ─── prereqs ───────────────────────────────────────────────────────────────

echo "→ checking prereqs"
command -v node >/dev/null || { echo "node not on PATH"; exit 1; }
[[ -f "$HOME/.cargo/env" ]] && source "$HOME/.cargo/env"
command -v cargo >/dev/null || { echo "cargo not on PATH — run: curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh"; exit 1; }

# ─── stop anything already running ─────────────────────────────────────────

echo "→ freeing ports 5174 / 7880 / 7882 / 7878"
for p in 5174 7880 7882 7878; do kill_port "$p"; done
pkill -x crawfish_app 2>/dev/null || true
pkill -f "Crawfish.app/Contents/MacOS" 2>/dev/null || true

# ─── builds (sequential — never parallel; they share dist/) ─────────────────

echo "→ build: cli/projectctl"
( cd "$ROOT/cli/projectctl" && npm run build >"$LOG_DIR/build-projectctl.log" 2>&1 )

echo "→ build: cloud/server"
( cd "$ROOT/cloud/server" && npm run build >"$LOG_DIR/build-server.log" 2>&1 )

echo "→ build: desktop/lens (server only)"
( cd "$ROOT/desktop/lens" && npm run build:server >"$LOG_DIR/build-lens.log" 2>&1 )

echo "→ build: desktop/dash"
( cd "$ROOT/desktop/dash" && npm run build >"$LOG_DIR/build-dash.log" 2>&1 )

echo "→ build: cloud/platform"
( cd "$ROOT/cloud/platform" && npm run build >"$LOG_DIR/build-platform.log" 2>&1 )

echo "→ build: desktop/app (Tauri)"
( cd "$ROOT/desktop/app" && npm run build >"$LOG_DIR/build-app.log" 2>&1 )

# ─── legacy-name symlinks for the Tauri shell ───────────────────────────────
# The Rust shell still expects <umbrella>/crawfish-{lens,dash}/ paths.
ln -sfn desktop/lens "$ROOT/crawfish-lens"
ln -sfn desktop/dash "$ROOT/crawfish-dash"

# ─── install craw onto PATH ────────────────────────────────────────────────

echo "→ installing craw shim → ~/.local/bin/craw"
mkdir -p "$HOME/.local/bin"
chmod +x "$ROOT/bin/craw.js"
ln -sfn "$ROOT/bin/craw.js" "$HOME/.local/bin/craw"
if ! echo "$PATH" | tr ':' '\n' | grep -q "^$HOME/.local/bin$"; then
  echo "  ⚠️  ~/.local/bin is not on your PATH — add it to your shell rc:"
  echo "       export PATH=\"\$HOME/.local/bin:\$PATH\""
fi

# ─── boot servers ──────────────────────────────────────────────────────────

echo "→ starting cloud/server on :7882"
( cd "$ROOT/cloud/server" && nohup npm run dev >"$LOG_DIR/server.log" 2>&1 & )

echo "→ starting cloud/platform on :5174"
( cd "$ROOT/cloud/platform" && nohup npm run dev >"$LOG_DIR/platform.log" 2>&1 & )

wait_for http://localhost:7882/api/health "cloud/server"
wait_for http://localhost:5174           "cloud/platform"

# ─── launch desktop app ────────────────────────────────────────────────────

echo "→ opening Crawfish.app"
open "$ROOT/desktop/app/src-tauri/target/release/bundle/macos/Crawfish.app"

# Dash + lens are spawned by the Tauri shell — give them a moment, then probe.
sleep 3
wait_for http://127.0.0.1:7880 "desktop/dash" || true
wait_for http://127.0.0.1:7878 "desktop/lens" || true

cat <<EOF

────────────────────────────────────────────────────────────
  crawfish is up

    cloud/server     http://localhost:7882   (logs: $LOG_DIR/server.log)
    cloud/platform   http://localhost:5174   (logs: $LOG_DIR/platform.log)
    desktop/dash     http://127.0.0.1:7880   (inside Crawfish.app)
    desktop/lens     http://127.0.0.1:7878   (inside Crawfish.app)

  CLI:
    craw init        scaffold .crawfish/ in any folder
                     it'll surface in the app's Projects page

  Stop everything:   ./prod.sh stop
────────────────────────────────────────────────────────────
EOF
