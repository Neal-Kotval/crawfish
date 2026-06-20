"""Host-side code sandbox + egress broker (Phase-1 minimum).

Third-party Source/Sink/tool code runs **out-of-process** (:func:`run_out_of_process`)
so a compromised unit can't read the engine's in-process memory/credentials. The
:class:`EgressBroker` is the **allowlist primitive** host-side code checks before
network egress (``broker.guard(host)``); wiring it into a transparent network
interception layer (so undeclared egress is blocked even without a cooperative call),
plus full microVM/seccomp isolation, is tracked separately. This is the portable
Phase-1 floor, not the final enforcement boundary.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from concurrent.futures import ProcessPoolExecutor
from typing import TypeVar

__all__ = ["EgressDenied", "EgressBroker", "run_out_of_process"]

R = TypeVar("R")


class EgressDenied(RuntimeError):
    """Raised when host-side code attempts egress to a non-allowlisted host."""


class EgressBroker:
    """Mediates network egress against a capability allowlist (runtime enforcement)."""

    def __init__(self, allow: Iterable[str] = ()) -> None:
        self.allow = set(allow)

    def permitted(self, host: str) -> bool:
        return host in self.allow

    def guard(self, host: str) -> None:
        if not self.permitted(host):
            raise EgressDenied(f"egress to {host!r} is not in the capability allowlist")


def run_out_of_process(func: Callable[..., R], *args: object, timeout: float = 30.0) -> R:
    """Execute ``func`` in a separate process and return its result.

    The function must be importable (picklable). Host-side tool code runs here so it
    never shares the engine's process memory or credentials.
    """
    with ProcessPoolExecutor(max_workers=1) as pool:
        return pool.submit(func, *args).result(timeout=timeout)
