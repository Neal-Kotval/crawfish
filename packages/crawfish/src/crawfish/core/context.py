"""RunContext and its cost/cancellation hooks (CRA-99).

The handle a node receives while executing: identity, store access, the cost
ceiling the orchestrator can hard-kill on, and a cooperative cancel token for
runaway kills. ``Store`` is a protocol (see :mod:`crawfish.store`); imported
under TYPE_CHECKING to keep this module dependency-light and cycle-free.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from crawfish.core.ids import new_id

if TYPE_CHECKING:
    from crawfish.store.base import Store

__all__ = ["CostBudget", "BudgetExceeded", "CancelToken", "Cancelled", "RunContext"]


class BudgetExceeded(RuntimeError):
    """Raised when a run would exceed its cost ceiling."""


class Cancelled(RuntimeError):
    """Raised when a cancelled run cooperatively checks in."""


@dataclass
class CostBudget:
    """A token/dollar ceiling the orchestrator can hard-kill on.

    ``limit_usd`` of ``None`` means unbounded (local dev default).
    """

    limit_usd: float | None = None
    spent_usd: float = 0.0

    def charge(self, amount_usd: float) -> None:
        self.spent_usd += amount_usd
        if self.limit_usd is not None and self.spent_usd > self.limit_usd:
            raise BudgetExceeded(
                f"cost budget exceeded: spent ${self.spent_usd:.4f} > ${self.limit_usd:.4f}"
            )

    @property
    def remaining_usd(self) -> float | None:
        if self.limit_usd is None:
            return None
        return max(0.0, self.limit_usd - self.spent_usd)


@dataclass
class CancelToken:
    """Cooperative cancellation. Long loops call :meth:`raise_if_cancelled`."""

    _event: threading.Event = field(default_factory=threading.Event)

    def cancel(self) -> None:
        self._event.set()

    @property
    def cancelled(self) -> bool:
        return self._event.is_set()

    def raise_if_cancelled(self) -> None:
        if self._event.is_set():
            raise Cancelled("run was cancelled")


@dataclass
class RunContext:
    """Per-run execution context handed to every node."""

    store: Store
    run_id: str = field(default_factory=new_id)
    batch_id: str | None = None
    org_id: str = "local"  # tenancy key, defaulted locally (CRA-99 gap review)
    cost_budget: CostBudget = field(default_factory=CostBudget)
    cancel_token: CancelToken = field(default_factory=CancelToken)
