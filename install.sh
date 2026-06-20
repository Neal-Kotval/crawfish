#!/bin/sh
# Crawfish installer — bootstraps the `craw` CLI with no Python setup required.
#
#   curl -LsSf https://raw.githubusercontent.com/Neal-Kotval/crawfish/main/install.sh | sh
#
# This is a thin wrapper over standard Python tooling: it installs Crawfish as an
# isolated CLI, preferring uv, then pipx, then pip --user. It is NOT a separate
# distribution channel — the package always comes from PyPI.
#
# To build *with* the framework (import crawfish in your own code) instead of just
# running the CLI, use:  pip install crawfish   (or: uv add crawfish)
set -eu

PACKAGE="crawfish"

say() { printf '\033[1;36mcrawfish\033[0m %s\n' "$1"; }
die() { printf '\033[1;31mcrawfish\033[0m %s\n' "$1" >&2; exit 1; }
has() { command -v "$1" >/dev/null 2>&1; }

say "installing the craw CLI…"

if has uv; then
  say "using uv → uv tool install $PACKAGE"
  uv tool install --upgrade "$PACKAGE"
elif has pipx; then
  say "using pipx → pipx install $PACKAGE"
  pipx install "$PACKAGE"
elif has python3; then
  say "uv/pipx not found — bootstrapping uv (https://astral.sh/uv)…"
  curl -LsSf https://astral.sh/uv/install.sh | sh
  # uv lands in ~/.local/bin (or ~/.cargo/bin on older installers); make it visible now.
  export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
  if has uv; then
    uv tool install --upgrade "$PACKAGE"
  else
    say "uv unavailable in this shell — falling back to pip --user"
    python3 -m pip install --user --upgrade "$PACKAGE"
  fi
else
  die "no python3, uv, or pipx found. Install Python 3 (https://www.python.org/downloads/) and re-run."
fi

if has craw; then
  say "done — $(craw --version 2>/dev/null || echo installed)"
  say "next: craw run"
else
  say "installed, but 'craw' isn't on your PATH yet."
  say "add your tool bin dir to PATH (e.g. export PATH=\"\$HOME/.local/bin:\$PATH\"), then restart your shell."
fi
