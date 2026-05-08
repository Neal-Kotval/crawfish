#!/usr/bin/env bash
# scripts/build-dmg.sh — one-shot builder for a shareable Crawfish DMG.
#
# What it does:
#   1. Verifies prereqs (rust, cargo, tauri CLI, Node 20+).
#   2. Builds crawfish-lens + crawfish-dash (so the .app's spawned
#      children find their dist files at runtime).
#   3. Runs `cargo tauri build --bundles dmg` against crawfish-app.
#   4. Copies the resulting .dmg next to a versioned filename and
#      prints the paths + an instruction blurb to copy to Slack/email.
#
# Usage:
#   ./scripts/build-dmg.sh                  # builds dmg + prints share blurb
#   ./scripts/build-dmg.sh --open-finder    # also reveals the dmg in Finder
#   ./scripts/build-dmg.sh --skip-deps      # skip lens/dash rebuilds
#   ./scripts/build-dmg.sh --output ~/Desktop  # also copy to ~/Desktop

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_DIR="$ROOT/crawfish-app"
LENS_DIR="$ROOT/crawfish-lens"
DASH_DIR="$ROOT/crawfish-dash"

OPEN_FINDER=0
SKIP_DEPS=0
EXTRA_OUTPUT=""

while [ $# -gt 0 ]; do
  case "$1" in
    --open-finder) OPEN_FINDER=1 ;;
    --skip-deps)   SKIP_DEPS=1 ;;
    --output)      EXTRA_OUTPUT="$2"; shift ;;
    --output=*)    EXTRA_OUTPUT="${1#--output=}" ;;
    -h|--help)
      sed -n '2,18p' "$0" | sed 's/^# \?//'
      exit 0
      ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
  shift
done

# ─── prereqs ──────────────────────────────────────────────────────────────
have() { command -v "$1" >/dev/null 2>&1; }
need() {
  if ! have "$1"; then
    echo "missing: $1 — install with: $2" >&2
    exit 1
  fi
}

# Pick up cargo from rustup install if not on PATH
export PATH="$HOME/.cargo/bin:/opt/homebrew/opt/rustup/bin:$PATH"

need node "brew install node"
need npm "(comes with node)"
need cargo "brew install rustup && rustup install stable"

if ! cargo tauri --version >/dev/null 2>&1; then
  echo "missing: tauri CLI — install with: cargo install tauri-cli --version '^2.0'" >&2
  exit 1
fi

NODE_MAJOR=$(node --version | sed 's/v\([0-9]*\).*/\1/')
if [ "$NODE_MAJOR" -lt 20 ]; then
  echo "node $NODE_MAJOR found; need ≥20" >&2
  exit 1
fi

# ─── build dependent submodules ───────────────────────────────────────────
if [ $SKIP_DEPS -eq 0 ]; then
  echo "▸ building crawfish-lens…"
  ( cd "$LENS_DIR" && npm install --silent && npm run build >/dev/null )
  echo "▸ building crawfish-dash…"
  ( cd "$DASH_DIR" && npm install --silent && npm run build >/dev/null )
else
  # Sanity: require existing dist files even if we're skipping the build.
  [ -f "$LENS_DIR/dist/index.js" ]      || { echo "missing $LENS_DIR/dist/index.js — drop --skip-deps" >&2; exit 1; }
  [ -f "$DASH_DIR/dist/index.js" ]      || { echo "missing $DASH_DIR/dist/index.js — drop --skip-deps" >&2; exit 1; }
fi

# ─── build the dmg ────────────────────────────────────────────────────────
# bundle_dmg.sh fails if a previous run left a Crawfish disk image mounted
# or a stale rw.*.dmg next to the bundle. Self-heal both before building.
DEV=$(hdiutil info | awk '/^\/dev\/disk[0-9]+/{dev=$1} /Crawfish/{print dev; exit}' || true)
if [ -n "$DEV" ]; then
  echo "▸ detaching stale mounted Crawfish image at $DEV"
  hdiutil detach "$DEV" -force >/dev/null 2>&1 || true
fi
rm -f "$APP_DIR"/src-tauri/target/release/bundle/macos/rw.*.dmg 2>/dev/null || true

echo "▸ building Crawfish.dmg…"
( cd "$APP_DIR" && cargo tauri build --bundles dmg )

DMG_DIR="$APP_DIR/src-tauri/target/release/bundle/dmg"
DMG=$(ls -t "$DMG_DIR"/Crawfish_*.dmg 2>/dev/null | head -1)

if [ -z "$DMG" ] || [ ! -f "$DMG" ]; then
  echo "build succeeded but no dmg found in $DMG_DIR" >&2
  exit 1
fi

DMG_NAME=$(basename "$DMG")
DMG_SIZE=$(du -h "$DMG" | cut -f1 | tr -d ' ')

# ─── optional copy ────────────────────────────────────────────────────────
if [ -n "$EXTRA_OUTPUT" ]; then
  EXTRA_OUTPUT="${EXTRA_OUTPUT/#\~/$HOME}"
  mkdir -p "$EXTRA_OUTPUT"
  cp "$DMG" "$EXTRA_OUTPUT/"
  echo "▸ copied to $EXTRA_OUTPUT/$DMG_NAME"
fi

# ─── share blurb ──────────────────────────────────────────────────────────
cat <<BLURB

──────────────────────────────────────────────────────────────────────
  Crawfish DMG built — $DMG_SIZE

  $DMG

  Share blurb (copy/paste to Slack / email):
──────────────────────────────────────────────────────────────────────
  Crawfish (local agent-token observability) — early build.
  Drag-install:

    1. Download the attached .dmg (~$DMG_SIZE)
    2. Open it, drag Crawfish.app to /Applications
    3. First launch: right-click → Open (this build is unsigned, so
       Gatekeeper will warn; one-time confirmation per machine)
    4. Crawfish needs Node 20+ on PATH (\`brew install node\` if missing)

  The app boots crawfish-lens + crawfish-dash locally; nothing
  leaves your machine.
──────────────────────────────────────────────────────────────────────

BLURB

if [ $OPEN_FINDER -eq 1 ]; then
  open -R "$DMG"
fi
