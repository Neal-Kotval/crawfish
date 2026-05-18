#!/usr/bin/env bash
# build-app.sh — build the Tauri shell once and (optionally) install it.
#
# Run this when you've changed any of:
#   - crawfish-app/src-tauri/**          (Rust shell / deep-link handler)
#   - crawfish-app/src-tauri/tauri.conf.json
#   - the deep-link scheme registration
#
# Full bundle: ~2-5 min cold, ~30-90s warm. dev.sh deliberately does NOT
# do this every restart — that would cost minutes per iteration.
#
# Usage:
#   ./build-app.sh              # build the bundle into target/release/bundle/
#   ./build-app.sh --install    # build, then drag to /Applications via cp -R
#   ./build-app.sh --open       # build and open the resulting DMG (macOS)

set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
APP_DIR="$ROOT/crawfish-app"

# rustup toolchain isn't always on PATH in fresh shells.
for p in "$HOME/.cargo/bin" "$HOME/.rustup/toolchains/stable-aarch64-apple-darwin/bin"; do
  [ -d "$p" ] && PATH="$p:$PATH"
done
export PATH

if ! command -v cargo >/dev/null 2>&1; then
  echo "✗ cargo not found on PATH. Install rustup from https://rustup.rs/"
  exit 1
fi

cd "$APP_DIR"

echo "▶ building Tauri bundle (this takes a minute…)"
npm run tauri build

case "${1:-}" in
  --install)
    DMG="$(find src-tauri/target/release/bundle/dmg -name 'Crawfish_*.dmg' 2>/dev/null | head -1)"
    APP="$(find src-tauri/target/release/bundle/macos -name 'Crawfish.app' 2>/dev/null | head -1)"
    if [ -n "$APP" ]; then
      echo "▶ installing $APP → /Applications/Crawfish.app"
      rm -rf "/Applications/Crawfish.app"
      cp -R "$APP" /Applications/
      echo "▶ registering crawfish-dash:// URL scheme with launchd"
      /System/Library/Frameworks/CoreServices.framework/Versions/A/Frameworks/LaunchServices.framework/Versions/A/Support/lsregister \
        -f "/Applications/Crawfish.app" 2>/dev/null || true
      echo "✓ installed. Launch once so macOS confirms the URL handler:"
      echo "  open /Applications/Crawfish.app"
    else
      echo "✗ no .app produced; check the build log above."
      exit 1
    fi
    ;;
  --open)
    DMG="$(find src-tauri/target/release/bundle/dmg -name 'Crawfish_*.dmg' 2>/dev/null | head -1)"
    [ -n "$DMG" ] && open "$DMG"
    ;;
  "")
    echo
    echo "✓ build done. Bundle at:"
    find src-tauri/target/release/bundle -name 'Crawfish*.{dmg,app}' -maxdepth 3 2>/dev/null | sed 's|^|  |'
    echo
    echo "Next steps:"
    echo "  ./build-app.sh --install    # install to /Applications and register the URL scheme"
    echo "  ./build-app.sh --open       # open the DMG to drag manually"
    ;;
  *)
    echo "Unknown arg: $1"
    echo "Usage: $0 [--install|--open]"
    exit 1
    ;;
esac
