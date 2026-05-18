#!/usr/bin/env bash
# scripts/gen-icon.sh — regenerate the Crawfish.app icon from the 🦞 emoji.
#
# Uses macOS's Apple Color Emoji font via Swift to produce a 1024x1024 PNG,
# then runs `cargo tauri icon` to regenerate every icon size + format.
#
# Re-run any time the icon needs refreshing (e.g., if Apple updates the emoji).

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_DIR="$ROOT/desktop/app"
OUT_PNG="$APP_DIR/src-tauri/icons/icon-source.png"

export PATH="$HOME/.cargo/bin:/opt/homebrew/opt/rustup/bin:$PATH"

command -v swift >/dev/null 2>&1 || { echo "swift not found (Xcode CLT required)" >&2; exit 1; }
command -v cargo >/dev/null 2>&1 || { echo "cargo not found (run scripts/build-dmg.sh prereqs)" >&2; exit 1; }

SWIFT_SCRIPT=$(mktemp).swift
cat > "$SWIFT_SCRIPT" <<'SWIFT'
import Cocoa

let emoji = "🦞"
let size: CGFloat = 1024
let image = NSImage(size: NSSize(width: size, height: size))
image.lockFocus()
NSColor.clear.set()
NSRect(x: 0, y: 0, width: size, height: size).fill()

let font = NSFont(name: "Apple Color Emoji", size: 820)!
let attrs: [NSAttributedString.Key: Any] = [.font: font]
let str = NSAttributedString(string: emoji, attributes: attrs)
let measured = str.size()
let x = (size - measured.width) / 2
let y = (size - measured.height) / 2 - 30
str.draw(at: NSPoint(x: x, y: y))

image.unlockFocus()

guard let tiff = image.tiffRepresentation,
      let bitmap = NSBitmapImageRep(data: tiff),
      let png = bitmap.representation(using: .png, properties: [:]) else {
    print("failed to encode PNG")
    exit(1)
}
let outPath = CommandLine.arguments.count > 1 ? CommandLine.arguments[1] : "icon-source.png"
try png.write(to: URL(fileURLWithPath: outPath))
print("wrote \(outPath)")
SWIFT

swift "$SWIFT_SCRIPT" "$OUT_PNG"
rm "$SWIFT_SCRIPT"

echo "▸ regenerating tauri icons…"
( cd "$APP_DIR" && cargo tauri icon "$OUT_PNG" )

echo
echo "✓ icons updated. Next: ./scripts/build-dmg.sh"
