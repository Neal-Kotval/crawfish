"""Retries, backoff & dead-letter.

Production-grade partial-failure handling: a failing item retries with exponential
backoff, and on exhaustion lands in a **dead-letter** store rather than halting the
batch. ``BudgetExceeded`` / ``Cancelled`` are never retried (a runaway must die fast).
Replay re-runs only dead-lettered items; Sink idempotency makes that safe.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import Enum
from typing import TypeVar

from crawfish.core.context import BudgetExceeded, Cancelled, RunContext
from crawfish.core.types import JSONValue

__all__ = [
    "RetryPolicy",
    "ItemStatus",
    "ItemResult",
    "run_with_retry",
    "dead_letter",
    "list_dead_letters",
]

R = TypeVar("R")
Sleep = Callable[[float], Awaitable[None]]


@dataclass
class RetryPolicy:
    """Exponential backoff: ``delay = min(base * factor**attempt, max_delay)``."""

    max_attempts: int = 3
    base_delay: float = 0.0
    factor: float = 2.0
    max_delay: float = 30.0

    def delay_for(self, attempt: int) -> float:
        return min(self.base_delay * (self.factor**attempt), self.max_delay)


class ItemStatus(str, Enum):
    OK = "ok"
    DEAD = "dead"  # exhausted retries -> dead-lettered


@dataclass
class ItemResult:
    """Partial-success unit surfaced in batch results."""

    item_id: str
    status: ItemStatus
    value: JSONValue = None
    error: str | None = None
    attempts: int = 0


async def run_with_retry(
    factory: Callable[[], Awaitable[R]],
    policy: RetryPolicy,
    *,
    sleep: Sleep = asyncio.sleep,
) -> R:
    """Run ``factory()`` with retries/backoff. Never retries budget/cancel errors."""
    last: Exception | None = None
    for attempt in range(policy.max_attempts):
        try:
            return await factory()
        except (BudgetExceeded, Cancelled):
            raise  # fail fast — a runaway/cancel must not be retried
        except Exception as exc:  # noqa: BLE001 - retry any task failure
            last = exc
            if attempt + 1 < policy.max_attempts:
                await sleep(policy.delay_for(attempt))
    assert last is not None
    raise last


def dead_letter(
    ctx: RunContext,
    *,
    batch_id: str,
    item_id: str,
    error: str,
    payload: JSONValue = None,
    attempts: int = 0,
) -> None:
    """Record a permanently-failed item so the batch can continue (never halt)."""
    ctx.store.put_record(
        "dead_letter",
        f"{batch_id}:{item_id}",
        {
            "batch_id": batch_id,
            "item_id": item_id,
            "error": error,
            "payload": payload,
            "attempts": attempts,
        },
        org_id=ctx.org_id,
    )


def list_dead_letters(ctx: RunContext, batch_id: str) -> list[dict[str, JSONValue]]:
    """All dead-lettered items for a batch (the replay work-list)."""
    return [
        r
        for r in ctx.store.list_records("dead_letter", org_id=ctx.org_id)
        if r["batch_id"] == batch_id
    ]
