"""API stability contract: tiers, tagging decorators, and a semver helper.

This module is the machine-readable half of the API-stability policy documented in
``docs/architecture/API-STABILITY.md``. It lets every public function or class declare
a stability tier (``STABLE`` / ``EXPERIMENTAL`` / ``DEPRECATED``) via a decorator, and
gives tooling a uniform way to read that tier back off any object.

The decorators are deliberately behavior-preserving: they attach a
``__crawfish_stability__`` attribute (and, for ``@deprecated``, emit a
``DeprecationWarning`` on call) but otherwise return the wrapped object unchanged, with
signature and metadata preserved via :func:`functools.wraps`.
"""

from __future__ import annotations

import functools
import warnings
from enum import Enum
from typing import TYPE_CHECKING, TypeVar

if TYPE_CHECKING:
    from collections.abc import Callable

__all__ = [
    "Stability",
    "deprecated",
    "experimental",
    "is_breaking",
    "migration_note",
    "stable",
    "stability_of",
]

#: Attribute name used to tag an object with its stability tier.
STABILITY_ATTR = "__crawfish_stability__"

T = TypeVar("T")


class Stability(str, Enum):
    """The stability tier of a public API surface.

    ``str`` mix-in so a tier round-trips through JSON and config without conversion.
    """

    STABLE = "stable"
    EXPERIMENTAL = "experimental"
    DEPRECATED = "deprecated"


def stable(obj: T) -> T:
    """Tag ``obj`` as :attr:`Stability.STABLE`. Behavior-preserving no-op otherwise."""
    obj.__crawfish_stability__ = Stability.STABLE  # type: ignore[attr-defined]
    return obj


def experimental(obj: T) -> T:
    """Tag ``obj`` as :attr:`Stability.EXPERIMENTAL`. Behavior-preserving no-op."""
    obj.__crawfish_stability__ = Stability.EXPERIMENTAL  # type: ignore[attr-defined]
    return obj


def deprecated(
    *,
    since: str,
    removed_in: str,
    use: str | None = None,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Mark a callable :attr:`Stability.DEPRECATED` and warn on every call.

    Args:
        since: Version in which the deprecation took effect (e.g. ``"0.4"``).
        removed_in: Version in which the callable is scheduled for removal.
        use: Optional name of the replacement API, surfaced in the warning message.

    The returned wrapper is behavior-preserving: it forwards all arguments to the
    wrapped callable and returns its result, preserving metadata via
    :func:`functools.wraps`. A :class:`DeprecationWarning` is emitted on each call.
    """

    def decorate(func: Callable[..., T]) -> Callable[..., T]:
        replacement = f" Use {use} instead." if use else ""
        message = (
            f"{func.__qualname__} is deprecated since {since} and is scheduled for "
            f"removal in {removed_in}.{replacement}"
        )

        @functools.wraps(func)
        def wrapper(*args: object, **kwargs: object) -> T:
            warnings.warn(message, DeprecationWarning, stacklevel=2)
            return func(*args, **kwargs)

        wrapper.__crawfish_stability__ = Stability.DEPRECATED  # type: ignore[attr-defined]
        return wrapper

    return decorate


def stability_of(obj: object) -> Stability:
    """Read the stability tier tagged on ``obj``.

    Untagged objects default to :attr:`Stability.EXPERIMENTAL`: nothing is stable until
    it is explicitly promoted with :func:`stable`.
    """
    tier = getattr(obj, STABILITY_ATTR, None)
    if isinstance(tier, Stability):
        return tier
    return Stability.EXPERIMENTAL


def _major(version: str) -> int:
    """Parse the major component of a ``MAJOR[.MINOR[.PATCH]]`` version string."""
    head = version.strip().lstrip("v").split(".", 1)[0]
    return int(head)


def is_breaking(old: str, new: str) -> bool:
    """Return ``True`` when going from ``old`` to ``new`` is a major (breaking) bump.

    Follows semver: a change is breaking when the major component increases. This is the
    coarse signal used by tooling to require a migration note.
    """
    return _major(new) > _major(old)


def migration_note(old: str, new: str) -> str:
    """A one-line human summary of the migration step from ``old`` to ``new``."""
    if is_breaking(old, new):
        return (
            f"{old} -> {new} is a breaking (major) change; a migration guide and "
            f"codemod are required before removal."
        )
    return f"{old} -> {new} is a non-breaking change; no migration guide required."
