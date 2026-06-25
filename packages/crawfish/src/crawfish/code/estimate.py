"""``craw code estimate <component> [--items N]`` — cost preview + budget threading (CRA-273).

An agent firing ``--live`` runs across a project with no preview and no aggregate ceiling is
the plan's single largest risk (§12.5). ``craw dev --estimate`` already previews a single
Definition via :func:`crawfish.cost.estimate_cost` (a pure function — **no model call ever**),
and the :class:`~crawfish.cost.CostEstimate` carries the honest band
(``total_usd`` ≤ ``expected_usd`` ≤ ``worst_case_usd``). This verb lifts that to a
project-level preview and threads a project-wide ``[budget]`` ceiling (read from
``crawfish.toml`` via :func:`crawfish.config.load_budget`) that halts an agent ``--live`` call
**before the call** when its ``worst_case_usd`` exceeds the remaining ceiling.

The ``worst_case`` halt is the responsibility gate that stops a prompt-injected agent from
burning spend via ``--live``; it is ``retryable=false`` (an injected agent must not loop past
it). ``estimate`` itself is pure: it previews, it does not run.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import TYPE_CHECKING

from crawfish.code import EXIT_OK, ErrorCode, emit_error, emit_json

if TYPE_CHECKING:
    from crawfish.cost import CostEstimate
    from crawfish.store.base import Store

VERB_NAME = "estimate"


def register(subparsers: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    """Register ``craw code estimate`` on the ``code`` subparser group (self-registering)."""
    from crawfish.code.cli import add_common_args

    p = subparsers.add_parser(
        VERB_NAME, help="preview the cost band of a component over N items (CRA-273)"
    )
    p.add_argument(
        "component", help="path to the component directory (e.g. definitions/triage-bot)"
    )
    p.add_argument(
        "--items", type=int, default=1, help="number of items to price the run over (default 1)"
    )
    add_common_args(p)
    p.set_defaults(func=_cmd_estimate)


def estimate_payload(
    estimate: CostEstimate,
    *,
    component: str,
    ceiling_usd: float | None,
    remaining_usd: float | None,
) -> dict[str, object]:
    """Build the ``craw.code.estimate.v1`` body (CRA-273).

    Carries the honest three-number band (``total`` ≤ ``expected`` ≤ ``worst_case``) plus the
    project ceiling and remaining headroom. ``within_budget`` is the precondition a ``--live``
    run checks: ``worst_case_usd`` must not exceed ``remaining_usd``. With no ``[budget]``
    ceiling the run is unbounded (``within_budget`` is always true, ceiling/remaining ``None``).
    Uses ``total_usd`` (the lower bound), never a non-existent ``lower_usd``.
    """
    within = True
    if remaining_usd is not None:
        within = estimate.worst_case_usd <= remaining_usd + 1e-9
    return {
        "component": component,
        "items": estimate.items,
        "total_usd": estimate.total_usd,
        "expected_usd": estimate.expected_usd,
        "worst_case_usd": estimate.worst_case_usd,
        "project_ceiling_usd": ceiling_usd,
        "remaining_usd": remaining_usd,
        "within_budget": within,
    }


def estimate_component(
    component: str,
    *,
    items: int = 1,
    store: Store | None = None,
    org_id: str = "local",
) -> tuple[CostEstimate, float | None]:
    """Compile a component and preview its cost over ``items`` (no model call) + read the ceiling.

    Compiles through the jailed path (CRA-267) so the preview reflects the on-disk component,
    then runs the pure :func:`crawfish.cost.estimate_cost` over the resolved team. Returns the
    estimate and the project ``[budget] ceiling_usd`` (``None`` when unset). Pure: no model
    call, no run.
    """
    from crawfish.config import load_budget, load_models_config
    from crawfish.cost import estimate_cost
    from crawfish.definition.jailed import load_definition_jailed
    from crawfish.jail import SandboxPolicy
    from crawfish.store import SqliteStore

    project_dir = Path(component)
    if not project_dir.is_dir():
        raise FileNotFoundError(component)

    owns_store = store is None
    backing = store if store is not None else SqliteStore()
    try:
        compiled = load_definition_jailed(
            project_dir, store=backing, org_id=org_id, policy=SandboxPolicy(kind="fake")
        )
    finally:
        if owns_store:
            backing.close()

    config = load_models_config(project_dir)
    estimate = estimate_cost(compiled.definition, items=items, config=config)
    ceiling = load_budget(project_dir).ceiling_usd
    return estimate, ceiling


def assert_within_budget(
    estimate: CostEstimate, *, ceiling_usd: float | None, spent_usd: float = 0.0
) -> None:
    """Fail closed if a ``--live`` run's worst case exceeds the remaining ceiling (CRA-273).

    The responsibility gate: a ``craw code run --live`` whose ``worst_case_usd`` exceeds the
    remaining headroom (``ceiling_usd − spent_usd``) **halts before the call**. Raises
    :class:`BudgetCeilingExceeded` (the CLI surfaces it as a non-retryable ``budget_exceeded``
    envelope, exit ``3``). With no ceiling the run is unbounded — never halts.
    """
    if ceiling_usd is None:
        return
    remaining = max(0.0, ceiling_usd - spent_usd)
    if estimate.worst_case_usd > remaining + 1e-9:
        raise BudgetCeilingExceeded(
            f"worst-case ${estimate.worst_case_usd:.2f} exceeds the remaining project ceiling "
            f"${remaining:.2f} (ceiling ${ceiling_usd:.2f}, spent ${spent_usd:.2f})"
        )


class BudgetCeilingExceeded(RuntimeError):
    """A ``--live`` run's worst-case cost exceeds the remaining project ceiling (fail closed)."""


def _cmd_estimate(args: argparse.Namespace) -> int:
    """``craw code estimate <component> [--items N] [--json] [--org ID]`` — preview the band."""
    org = getattr(args, "org", "local")
    items = getattr(args, "items", 1)
    if items < 0:
        return emit_error(
            ErrorCode.USAGE,
            remediation="--items must be >= 0.",
            detail={"items": items},
            as_json=getattr(args, "as_json", False),
        )
    try:
        estimate, ceiling = estimate_component(args.component, items=items, org_id=org)
    except FileNotFoundError:
        return emit_error(
            ErrorCode.NOT_FOUND,
            remediation=(
                f"Component {args.component!r} was not found; pass a component directory path."
            ),
            detail={"component": args.component},
            as_json=getattr(args, "as_json", False),
        )
    except Exception:
        # A compile/jail failure is a usage-class compile error (exit 2). The remediation is
        # static — no fluid input is echoed back.
        import sys

        from crawfish.definition.compiler import DefinitionLoadError

        exc = sys.exc_info()[1]
        code = (
            ErrorCode.COMPILE_ERROR if isinstance(exc, DefinitionLoadError) else ErrorCode.INTERNAL
        )
        return emit_error(
            code,
            remediation=(
                f"Component {args.component!r} failed to compile; fix the directory and retry."
            ),
            detail={"component": args.component},
            as_json=getattr(args, "as_json", False),
        )

    remaining = ceiling if ceiling is not None else None
    body = estimate_payload(
        estimate, component=args.component, ceiling_usd=ceiling, remaining_usd=remaining
    )
    if getattr(args, "as_json", False):
        emit_json("code.estimate", body, org=org)
    else:
        _print_human(body)
    return EXIT_OK


def _print_human(body: dict[str, object]) -> None:
    """Human one-liner (unchanged behaviour when ``--json`` is absent)."""
    ceiling = body["project_ceiling_usd"]
    tail = f" (ceiling ${ceiling})" if ceiling is not None else ""
    print(
        f"{body['component']}: {body['items']} items — "
        f"${body['total_usd']:.4f} ≤ ${body['expected_usd']:.4f} ≤ "
        f"${body['worst_case_usd']:.4f}{tail}"
    )
