"""``craw code init [<dir>]`` — stand a ``craw code`` project up (CRA-245).

A bare ``craw init`` writes the authored tree but does nothing about the agent loop. RFC
§4.1: ``craw code init`` must do *more* — scaffold the canonical layout **and** open the
``.crawfish/`` ledger the dashboard reads, recording an init provenance row, and (when the
shipped plugin bundle is present) install it. It must **never** reach a live model or
resolve a secret.

Three composable steps behind one verb:

1. **Scaffold** — reuse :data:`crawfish.scaffold.FILES` to write the canonical folders +
   ``crawfish.toml`` + the secrets-by-reference ``.env.example``. Reconcile-friendly:
   **create only if absent**, recording skipped (existing) paths (the byte-for-byte
   re-entrancy guarantee is CRA-279, a later wave; this verb already never clobbers).
2. **Start the ledger** — create ``<dir>/.crawfish/`` and open the Store **through the
   protocol/factory only** (never importing a concrete backend), recording an init
   provenance row (``generated_by="craw-code-init"``, ``source_tainted=False``).
3. **Install the plugin** — copy the shipped ``crawfish/plugin/`` bundle into
   ``<dir>/.claude/plugins/crawfish/`` (disjoint from ``.claude/agents/`` that export
   owns) when it exists, and **pin** the bundle (UNFILED-PIN): record its ``bundle_sha256``
   + ``requires_crawfish`` range in ``crawfish.plugin.lock`` (:mod:`crawfish.code.plugin`)
   so a tampered or wrong-version bundle is detectable. Until the bundle ships this step is
   a clean no-op, so ``init`` is useful today and gains the install with zero change here.

A self-registering verb (``register(subparsers)``).
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

from crawfish.code import (
    EXIT_OK,
    SCHEMA_VERSIONS,
    ErrorCode,
    emit_error,
    emit_json,
)

if TYPE_CHECKING:
    from crawfish.store.base import Store

VERB_NAME = "init"

# This verb's --json schema, seeded here (not by editing the shared registry).
SCHEMA_VERSIONS.setdefault("code.init", (1, 0))  # type: ignore[attr-defined]


def register(subparsers: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    """Register ``craw code init`` on the ``code`` subparser group."""
    from crawfish.code.cli import add_common_args

    p = subparsers.add_parser(VERB_NAME, help="scaffold a craw code project + start the ledger")
    p.add_argument("dir", nargs="?", default=".", help="project directory (default: cwd)")
    p.add_argument("--name", default=None, help="project name (crawfish.toml [project].name)")
    p.add_argument(
        "--no-plugin", action="store_true", help="scaffold + ledger only, skip plugin install"
    )
    p.add_argument(
        "--upgrade",
        action="store_true",
        help="re-pin the plugin + reconcile new canonical folders (never rewrites authored files)",
    )
    add_common_args(p)
    p.set_defaults(func=_cmd_init)


def _plugin_source() -> Path | None:
    """The shipped plugin bundle dir, or None if it is not present in this distribution.

    The bundle is an M3 deliverable; until it ships, plugin install is a clean no-op so
    ``init`` is useful today and gains the install step with no change here.
    """
    candidate = Path(__file__).resolve().parent.parent / "plugin"
    return candidate if candidate.is_dir() else None


def _scaffold(root: Path, *, name: str | None) -> tuple[list[str], list[str]]:
    """Write the canonical tree, create-only-if-absent. Returns (created, skipped_existing)."""
    from crawfish.scaffold import FILES

    created: list[str] = []
    skipped: list[str] = []
    for rel, content in FILES.items():
        path = root / rel
        if path.exists():
            skipped.append(rel)
            continue
        if name is not None and rel == "crawfish.toml":
            content = content.replace('name = "crawfish-app"', f'name = "{name}"', 1)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        created.append(rel)
    return sorted(created), sorted(skipped)


def _install_plugin(root: Path, *, upgrade: bool = False) -> dict[str, object] | None:
    """Copy the shipped plugin bundle into ``.claude/plugins/crawfish/`` (if present).

    Disjoint from ``.claude/agents/`` (export's namespace, RFC O-4); the whole ``.claude``
    tree is already excluded from the Definition content sha, so this never perturbs
    content identity. ``--upgrade`` re-copies the bundle (the re-pin step, CRA-279). Returns
    the plugin descriptor for the --json payload, or None when no bundle ships.
    """
    source = _plugin_source()
    if source is None:
        return None
    dest = root / ".claude" / "plugins" / "crawfish"
    dest.parent.mkdir(parents=True, exist_ok=True)
    already = dest.exists()
    if already:
        # A re-install/upgrade always re-copies (idempotent: the bundle is generated state,
        # excluded from the sha) so a stale bundle is reconciled to the shipped one.
        shutil.rmtree(dest)
    shutil.copytree(source, dest)
    # Pin the bundle (UNFILED-PIN): compute bundle_sha256 + requires_crawfish range and
    # record them in the framework's plugin-pin file so a tampered/wrong-version bundle is
    # detectable (`craw doctor`) and a skewed range fails closed (`craw code sync`).
    from crawfish.code.plugin import compute_pin, write_pin

    pin = compute_pin(dest)
    write_pin(pin, root)
    descriptor: dict[str, object] = {
        "installed": True,
        "name": pin.name,
        "version": pin.version,
        "path": ".claude/plugins/crawfish/",
        "bundle_sha256": pin.bundle_sha256,
        "requires_crawfish": pin.requires_crawfish,
    }
    if upgrade and already:
        # CRA-279 --upgrade re-copies + re-pins the bundle without rewriting authored files.
        descriptor["upgraded"] = True
    return descriptor


def _is_dirty_init(root: Path) -> str | None:
    """Detect a tampered ``.crawfish/`` (CRA-279, the dirty_init fail-closed signal).

    An authored unit hiding inside the generated ``.crawfish/`` tree is the
    authored-vs-generated boundary breach :func:`crawfish.doctor.diagnose` flags at
    ``error`` level. Re-running init over a tampered ledger must refuse (exit 2) rather than
    silently reset the audit trail. Returns the breach message, or None when clean.
    """
    if not (root / ".crawfish").is_dir():
        return None  # nothing generated yet — a fresh init, never dirty
    from crawfish.doctor import diagnose

    for finding in diagnose(root).findings:
        if finding.level == "error":
            return finding.message
    return None


def _cmd_init(args: argparse.Namespace) -> int:
    """Scaffold + start the ledger (+ install the plugin when present). No model, no secret.

    Reconcile-first (CRA-279): every scaffold path is **create-only-if-absent**, so a re-run
    over an existing project creates nothing and lists ``skipped_existing`` — the ledger
    under ``.crawfish/`` is opened, never reset, and an authored file is never clobbered. A
    tampered ``.crawfish/`` fails closed with ``dirty_init`` (exit 2). ``--upgrade`` re-pins
    the plugin and reconciles newly-added canonical folders without rewriting authored files.
    """
    as_json: bool = getattr(args, "as_json", False)
    org: str = getattr(args, "org", "local")
    upgrade: bool = getattr(args, "upgrade", False)
    root = Path(args.dir)
    root.mkdir(parents=True, exist_ok=True)

    # Fail closed on a tampered ledger BEFORE any write (CRA-279) — refusing here prevents a
    # confused agent (or an attacker) resetting the audit trail by re-running init.
    breach = _is_dirty_init(root)
    if breach is not None:
        # dirty_init is the spec's exit 2 (a fail-closed refusal). We emit the structured
        # craw.error.v1 envelope (retryable:false) but force process exit 2 to match the
        # spec's documented code, rather than the JAIL_VIOLATION→4 default mapping.
        emit_error(
            ErrorCode.JAIL_VIOLATION,
            remediation="the .crawfish/ ledger looks tampered (an authored unit hides inside "
            "generated state); resolve it before re-running init",
            detail={"exit": 2, "reason": "dirty_init", "breach": breach},
            as_json=as_json,
        )
        return 2

    had_ledger = (root / ".crawfish").is_dir()
    created, skipped = _scaffold(root, name=args.name)

    # Open the ledger through the factory (never a concrete backend). On a re-run the Store is
    # *opened*, not reset; the provenance re-record is keyed by (path, content_sha) so an
    # unchanged toml writes a byte-identical row (idempotent). Skip it on a pure --upgrade so
    # an upgrade leaves existing ledger rows untouched.
    store = _open_store(root)
    try:
        if not upgrade or not had_ledger:
            _record_init_provenance(store, root, org=org)
    finally:
        _close_store(store)

    plugin: dict[str, object] = {"installed": False}
    if not args.no_plugin:
        installed = _install_plugin(root, upgrade=upgrade)
        if installed is not None:
            plugin = installed

    payload: dict[str, object] = {
        "project": args.name or _project_name(root),
        "dir": str(root.resolve()),
        "scaffolded": created,
        "skipped_existing": skipped,
        "plugin": plugin,
        # On a re-run the ledger is preserved, not freshly started (CRA-279 re-entrant field).
        "ledger": {"started": not had_ledger, "preserved": had_ledger, "path": ".crawfish/"},
        "next_steps": [
            "craw code new definition my-agent",
            "craw dev definitions/triage-bot -i project=acme -i ticket_body=…",
        ],
    }
    if as_json:
        emit_json("code.init", payload, org=org)
    else:
        what = f"{len(created)} created" + (f", {len(skipped)} kept" if skipped else "")
        verb = "upgraded" if upgrade else "initialized"
        state = "preserved" if had_ledger else "started"
        print(f"{verb} craw code project at {root} ({what}); ledger {state}")
    return EXIT_OK


def _project_name(root: Path) -> str:
    """Read the project name from crawfish.toml (best-effort), else the dir name."""
    from crawfish.config import load_manifest

    try:
        return load_manifest(root).name
    except Exception:  # pragma: no cover - defensive; a malformed toml shouldn't crash init
        return root.resolve().name


def _record_init_provenance(store: Store, root: Path, *, org: str) -> None:
    """Record one init provenance row (``authored_by="craw-code-init"``), idempotently.

    Keyed by the project's ``crawfish.toml`` content sha (its identity anchor); the init
    event is the audit marker "craw code init ran here", never a fluid value. CRA-279: if an
    identical row already exists (a re-run over unchanged content), recording is skipped so
    re-init writes no new event — the ledger is byte-for-byte preserved.
    """
    import hashlib

    from crawfish.provenance import file_provenance, record_file_provenance

    toml = root / "crawfish.toml"
    content = toml.read_text() if toml.exists() else ""
    sha = hashlib.sha256(content.encode()).hexdigest()[:12]
    if file_provenance("crawfish.toml", sha, store=store, org_id=org) is not None:
        return  # already recorded for this exact content — re-init is a no-op (idempotent)
    record_file_provenance(
        "crawfish.toml",
        sha,
        store=store,
        authored_by="craw-code-init",
        source_tainted=False,
        org_id=org,
    )


def _open_store(root: Path) -> Store:
    """Open the project's Store via the protocol/factory — never import a concrete backend."""
    from crawfish.manage import store_for_dir

    (root / ".crawfish").mkdir(parents=True, exist_ok=True)
    return store_for_dir(str(root))


def _close_store(store: Store) -> None:
    close = getattr(store, "close", None)
    if callable(close):
        close()
