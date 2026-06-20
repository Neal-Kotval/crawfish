"""Versioning — every customizable item is versioned and freezable.

A frozen ``Version`` marks its owning artifact as an immutable, reproducible
artifact: mutating a frozen artifact raises :class:`FrozenError`. ``str(Version)``
renders ``0.1-sha`` / ``0.2`` for lockfile pinning and ``DefinitionRef`` resolution.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

__all__ = ["Version", "FrozenError", "Freezable"]


class FrozenError(RuntimeError):
    """Raised on any attempt to mutate a frozen artifact."""


class Version(BaseModel):
    """A semver-ish version with an optional content sha and a frozen flag."""

    major: int = 0
    minor: int = 1
    sha: str | None = None
    frozen: bool = False

    def freeze(self) -> None:
        # Bypass our own frozen-guard: flipping the flag is the one allowed write.
        object.__setattr__(self, "frozen", True)

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}" + (f"-{self.sha}" if self.sha else "")

    def __setattr__(self, name: str, value: Any) -> None:
        if getattr(self, "frozen", False):
            raise FrozenError(f"cannot mutate frozen Version {self}")
        super().__setattr__(name, value)


class Freezable(BaseModel):
    """Mixin for any customizable artifact carrying a ``version``.

    Once ``version.frozen`` is set, attribute assignment is rejected — the
    artifact is an immutable, reproducible unit (Definitions first, then
    Source/Sink). Use :meth:`freeze` to seal.
    """

    version: Version = Version()

    def freeze(self) -> None:
        self.version.freeze()

    @property
    def frozen(self) -> bool:
        return self.version.frozen

    def __setattr__(self, name: str, value: Any) -> None:
        if name != "version" and getattr(self, "version", None) is not None and self.version.frozen:
            raise FrozenError(f"cannot mutate frozen artifact (version {self.version})")
        super().__setattr__(name, value)
