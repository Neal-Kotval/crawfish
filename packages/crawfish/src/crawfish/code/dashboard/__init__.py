"""``craw code dashboard`` — the loopback fleet dashboard over the ``.crawfish/`` ledger (M4).

This subpackage is the *operate / observe* surface of ``craw code``: a server-rendered, **read
only**, loopback dashboard over the ledger (runs in flight, fan-out progress, cost burn, and an
org-scoped cost-vs-ceiling gauge). It self-registers a ``dashboard`` verb via the ``craw code``
``pkgutil`` registry — ``discover_verbs`` finds this package's :func:`register`, so no shared
dispatcher is edited (architectural decision #2).

The seam (ADR 0011): the dashboard reads **only** through the
:class:`~crawfish.observe.ObserverSurface` / :class:`~crawfish.store.base.Store` protocols and
the :class:`~crawfish.deploy.DeployRegistry` — it resolves the project's configured Store via
:func:`crawfish.manage.store_for_dir` (the one factory that knows the backend), wraps it in a
:class:`~crawfish.secrets.ScrubbingStore`, and hands the *interface* to the data layer. No
concrete backend or raw query ever appears here, and the dashboard never reaches past the
scrubbed surface. Tainted ledger text is output-encoded + CSP'd at render (UNFILED-XSS).
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import TYPE_CHECKING

from crawfish.code import EXIT_OK, ErrorCode, emit_error, emit_json
from crawfish.code.dashboard.data import COST_SCHEMA, DASHBOARD_SCHEMA, RUNS_SCHEMA, DashboardData
from crawfish.code.dashboard.encoding import (
    CSP,
    SECURITY_HEADERS,
    Encoding,
    encode_field,
    safe_url,
)
from crawfish.code.dashboard.server import (
    DEFAULT_PORT,
    LOOPBACK,
    make_handler,
    render_snapshot,
    serve_dashboard,
)
from crawfish.code.dashboard.views import render_page

if TYPE_CHECKING:
    from crawfish.store.base import Store

VERB_NAME = "dashboard"

__all__ = [
    "VERB_NAME",
    "register",
    "build_data",
    # re-exports so callers/tests have one import surface
    "DashboardData",
    "render_snapshot",
    "render_page",
    "make_handler",
    "serve_dashboard",
    "encode_field",
    "safe_url",
    "Encoding",
    "CSP",
    "SECURITY_HEADERS",
    "LOOPBACK",
    "DEFAULT_PORT",
    "DASHBOARD_SCHEMA",
    "RUNS_SCHEMA",
    "COST_SCHEMA",
]


def register(subparsers: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    """Register ``craw code dashboard`` on the ``code`` subparser group (self-registering)."""
    from crawfish.code.cli import add_common_args

    p = subparsers.add_parser(
        VERB_NAME, help="loopback fleet dashboard over the .crawfish/ ledger (M4)"
    )
    p.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help="loopback port (binds 127.0.0.1 only)",
    )
    p.add_argument(
        "--project",
        default=".",
        help="project directory holding .crawfish/ (default: cwd)",
    )
    p.add_argument(
        "--open",
        action="store_true",
        dest="open_browser",
        help="launch a browser tab at the loopback URL",
    )
    add_common_args(p)
    p.set_defaults(func=_cmd_dashboard)


def build_data(
    project_dir: str | Path,
    *,
    org_id: str = "local",
    store: Store | None = None,
) -> DashboardData:
    """Build the scrubbed, org-scoped :class:`DashboardData` for a project (the seam).

    Resolves the project's Store via :func:`crawfish.manage.store_for_dir` (the only place
    that names the concrete backend), wraps it in a :class:`~crawfish.secrets.ScrubbingStore`
    (so the dashboard can never read past the redaction layer — ADR 0011), and constructs the
    :class:`~crawfish.observe.ObserverSurface` / :class:`~crawfish.deploy.DeployRegistry` over
    it. ``store`` may be injected (tests pass a non-Sqlite ``Store`` to prove the swap); it is
    still wrapped in scrubbing.
    """
    from crawfish.config import load_budget
    from crawfish.deploy import DeployRegistry
    from crawfish.manage import store_for_dir
    from crawfish.observe import ObserverSurface
    from crawfish.secrets import ScrubbingStore, SecretManager

    raw: Store = store if store is not None else store_for_dir(str(project_dir))
    scrubbed: Store = ScrubbingStore(raw, secrets=SecretManager(env=None).values)
    surface = ObserverSurface(scrubbed, org_id=org_id)
    registry = DeployRegistry(scrubbed, org_id=org_id)
    budget = load_budget(project_dir)
    return DashboardData(surface, registry, store=scrubbed, org_id=org_id, budget=budget)


def _cmd_dashboard(args: argparse.Namespace) -> int:
    """``craw code dashboard [--port] [--project] [--org] [--json] [--open]``.

    ``--json`` emits the ``craw.code.dashboard.v1`` snapshot (no server); otherwise the
    loopback HTTP server is started and blocks in ``serve_forever``. A missing ``.crawfish/``
    ledger is a ``not_found`` envelope (exit 2), never a stack trace.
    """
    org = getattr(args, "org", "local")
    as_json = getattr(args, "as_json", False)
    project = Path(getattr(args, "project", "."))
    if not (project / ".crawfish").is_dir():
        return emit_error(
            ErrorCode.NOT_FOUND,
            remediation=(
                "No .crawfish/ ledger was found; run the pipeline (or `craw code init`) first, "
                "or pass --project to point at the project directory."
            ),
            detail={"project": str(project)},
            as_json=as_json,
        )
    data = build_data(project, org_id=org)
    try:
        if as_json:
            emit_json("code.dashboard", render_snapshot(data), org=org)
            return EXIT_OK
        return _serve(
            data,
            port=int(getattr(args, "port", DEFAULT_PORT)),
            open_browser=bool(getattr(args, "open_browser", False)),
        )
    finally:
        # The data layer owns a scrubbed wrapper over the project store; close the inner store.
        store = getattr(data, "_store", None)
        close = getattr(store, "close", None)
        if callable(close):
            close()


def _serve(data: DashboardData, *, port: int, open_browser: bool) -> int:
    """Start the loopback server and block (extracted so the JSON path stays import-light)."""
    server = serve_dashboard(data, port=port)
    url = f"http://{LOOPBACK}:{server.server_address[1]}/"
    print(f"craw code dashboard → {url} (loopback only; Ctrl-C to stop)")
    if open_browser:
        import webbrowser

        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()
    return EXIT_OK
