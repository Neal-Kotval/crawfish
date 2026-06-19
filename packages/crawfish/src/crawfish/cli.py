"""The ``craw`` CLI (CRA-113 + M4/M5 command wiring).

Command surface: ``init`` (scaffold a working project — the 5-minute wow, CRA-118),
``list`` (module discovery), ``install`` (capability consent, CRA-114), ``freeze``
(lockfile + integrity), ``publish`` (registry stub), ``run`` / ``dev`` (+ ``--estimate``
cost preview, CRA-121), ``test`` (CRA-119), ``build`` (Containerfile, CRA-115),
``inspect`` / ``logs`` (run inspector, CRA-120).
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
from importlib.metadata import version as _pkg_version
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from crawfish.store.base import Store


def _version() -> str:
    try:
        return _pkg_version("crawfish")
    except Exception:  # pragma: no cover - source checkout without install
        return "0.0.0+dev"


# --------------------------------------------------------------------------- run
def _cmd_run(_args: argparse.Namespace) -> int:
    from crawfish.engine import run_pipeline

    outputs = asyncio.run(run_pipeline([]))
    print(f"pipeline ok: {len(outputs)} output(s)")
    return 0


# --------------------------------------------------------------------------- dev
def _cmd_dev(args: argparse.Namespace) -> int:
    from crawfish.core.context import RunContext
    from crawfish.definition import Definition
    from crawfish.runtime import MockRuntime, run_team
    from crawfish.store import SqliteStore

    definition = Definition.from_package(args.path)
    inputs: dict[str, object] = {}
    for pair in args.input or []:
        key, _, value = pair.partition("=")
        inputs[key] = value

    if args.estimate:
        from crawfish.cost import estimate_cost

        est = estimate_cost(definition, items=args.items)
        print(
            f"estimated cost: ${est.total_usd:.4f} for {args.items} item(s) "
            f"(team of {est.team_size})"
        )
        return 0

    async def _go() -> str:
        ctx = RunContext(store=SqliteStore())
        result = await run_team(definition, inputs, ctx, MockRuntime())
        return result.text

    print(asyncio.run(_go()))
    return 0


# -------------------------------------------------------------------------- list
def _cmd_list(args: argparse.Namespace) -> int:
    from crawfish.discovery import Registry

    reg = Registry.discover(args.dir)
    if not reg.units:
        print("no units discovered")
        return 0
    for (kind, name), ref in sorted(reg.units.items()):
        print(f"{kind:11} {name:24} {ref.origin}")
    return 0


# ------------------------------------------------------------------------ install
def _cmd_install(args: argparse.Namespace) -> int:
    from crawfish.secrets import read_capabilities

    caps = read_capabilities(args.path)
    print(f"'{args.path}' requests — {caps.summary()}")
    if not args.yes:
        print("re-run with --yes to consent and enable this package.")
        return 1
    print("capabilities consented; package enabled.")
    return 0


# ------------------------------------------------------------------------- freeze
def _cmd_freeze(args: argparse.Namespace) -> int:
    from crawfish.discovery import Registry

    reg = Registry.discover(args.dir)
    pins: dict[str, dict[str, str]] = {}
    for (kind, name), ref in sorted(reg.units.items()):
        integrity = ""
        target = Path(ref.target)
        if target.exists():
            data = (
                b"".join(sorted(p.read_bytes() for p in target.rglob("*") if p.is_file()))
                if target.is_dir()
                else target.read_bytes()
            )
            integrity = "sha256:" + hashlib.sha256(data).hexdigest()  # full digest
        pins[f"{kind}:{name}"] = {"origin": ref.origin, "integrity": integrity}
    lock = Path(args.dir) / "crawfish.lock"
    lock.write_text(json.dumps({"units": pins}, indent=2, sort_keys=True) + "\n")
    print(f"wrote {lock} ({len(pins)} unit(s))")
    return 0


def _cmd_publish(_args: argparse.Namespace) -> int:
    print("publish: the registry is Phase 2 (CRA-125); nothing to publish yet.")
    return 0


# --------------------------------------------------------------------------- test
def _cmd_test(args: argparse.Namespace) -> int:
    from crawfish.core.context import RunContext
    from crawfish.definition import Definition
    from crawfish.runtime import MockRuntime
    from crawfish.store import SqliteStore
    from crawfish.testing import run_fixtures

    definition = Definition.from_package(args.path)
    results = asyncio.run(
        run_fixtures(
            args.fixtures,
            definition,
            MockRuntime(),
            ctx_factory=lambda: RunContext(store=SqliteStore()),
        )
    )
    passed = sum(1 for r in results if r.passed)
    for r in results:
        print(f"{'PASS' if r.passed else 'FAIL'}  {r.name}")
    print(f"{passed}/{len(results)} fixtures passed")
    return 0 if passed == len(results) else 1


# -------------------------------------------------------------------------- build
def _cmd_build(args: argparse.Namespace) -> int:
    from crawfish.build import plan_build, write_containerfile
    from crawfish.config import load_manifest

    manifest = load_manifest(args.dir)
    plan = plan_build(manifest, lock_present=(Path(args.dir) / "crawfish.lock").exists())
    dest = write_containerfile(manifest, Path(args.dir), lock_present=plan.lock_present)
    print(f"wrote {dest} → image {plan.image} (base {plan.base_image})")
    return 0


# ------------------------------------------------------------------ inspect / logs
def _open_store(project_dir: str) -> Store:
    from crawfish.store import SqliteStore

    db = Path(project_dir) / ".crawfish" / "crawfish.db"
    db.parent.mkdir(parents=True, exist_ok=True)
    return SqliteStore(db)


def _cmd_inspect(args: argparse.Namespace) -> int:
    from crawfish.inspector import format_report, inspect_run

    report = inspect_run(_open_store(args.dir), args.run_id)
    print(format_report(report))
    return 0 if report.found else 1


def _cmd_logs(args: argparse.Namespace) -> int:
    from crawfish.inspector import tail_events

    for event in tail_events(_open_store(args.dir), args.run_id, after_seq=args.after):
        print(json.dumps(event))
    return 0


# ------------------------------------------------------------------------- doctor
def _cmd_doctor(args: argparse.Namespace) -> int:
    from crawfish.doctor import diagnose

    report = diagnose(args.dir)
    print(report.text())
    return 0 if report.ok else 1


# --------------------------------------------------------------------------- init
def _cmd_init(args: argparse.Namespace) -> int:
    from crawfish.scaffold import scaffold_project

    root = scaffold_project(args.name)
    print(f"created project at {root}")
    print("next:")
    print(f"  cd {root}")
    print('  craw dev definitions/triage-bot -i project=acme -i "ticket_body=login is broken"')
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="craw", description="Crawfish CLI")
    parser.add_argument("--version", action="version", version=f"crawfish {_version()}")
    sub = parser.add_subparsers(dest="command")

    p = sub.add_parser("run", help="run the project's pipeline")
    p.set_defaults(func=_cmd_run)

    p = sub.add_parser("dev", help="compile + run a Definition on the mock runtime")
    p.add_argument("path", help="path to a Definition directory")
    p.add_argument("-i", "--input", action="append", help="input as name=value (repeatable)")
    p.add_argument("--estimate", action="store_true", help="preview cost instead of running")
    p.add_argument("--items", type=int, default=1, help="item count for --estimate")
    p.set_defaults(func=_cmd_dev)

    p = sub.add_parser("init", help="scaffold a new project with a working example")
    p.add_argument("name", nargs="?", default="crawfish-app", help="project directory name")
    p.set_defaults(func=_cmd_init)

    p = sub.add_parser("list", help="list discovered units")
    p.add_argument("--dir", default=".", help="project directory")
    p.set_defaults(func=_cmd_list)

    p = sub.add_parser("doctor", help="report project structure health")
    p.add_argument("--dir", default=".", help="project directory")
    p.set_defaults(func=_cmd_doctor)

    p = sub.add_parser("install", help="install a unit (surfaces capabilities for consent)")
    p.add_argument("path", help="path to the unit/package")
    p.add_argument("--yes", action="store_true", help="consent to the declared capabilities")
    p.set_defaults(func=_cmd_install)

    p = sub.add_parser("freeze", help="write crawfish.lock with integrity hashes")
    p.add_argument("--dir", default=".", help="project directory")
    p.set_defaults(func=_cmd_freeze)

    p = sub.add_parser("publish", help="publish to the registry (Phase 2 stub)")
    p.set_defaults(func=_cmd_publish)

    p = sub.add_parser("test", help="run fixtures against a Definition")
    p.add_argument("path", help="path to a Definition directory")
    p.add_argument("--fixtures", default="fixtures", help="fixtures directory")
    p.set_defaults(func=_cmd_test)

    p = sub.add_parser("build", help="generate a Containerfile from the manifest + lock")
    p.add_argument("--dir", default=".", help="project directory")
    p.set_defaults(func=_cmd_build)

    p = sub.add_parser("inspect", help="inspect a run from the Store")
    p.add_argument("run_id")
    p.add_argument("--dir", default=".", help="project directory")
    p.set_defaults(func=_cmd_inspect)

    p = sub.add_parser("logs", help="tail a run's events")
    p.add_argument("run_id")
    p.add_argument("--after", type=int, default=0, help="return events after this index")
    p.add_argument("--dir", default=".", help="project directory")
    p.set_defaults(func=_cmd_logs)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return 0
    result: int = args.func(args)
    return result


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
