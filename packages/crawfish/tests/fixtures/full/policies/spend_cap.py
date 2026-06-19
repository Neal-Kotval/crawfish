"""A policy: a module-level Policy instance is collected into the Definition."""

from __future__ import annotations

from crawfish.core import Policy, PolicyKind

spend_cap = Policy(name="spend_cap", kind=PolicyKind.GUARDRAIL, rules={"max_usd": 5})
