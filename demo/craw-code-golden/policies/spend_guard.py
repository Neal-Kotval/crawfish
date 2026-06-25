"""spend_guard — a guardrail Policy (consequential, static-only config).

A Policy is consequential static config (a per-batch spend cap here); it is never derived
from a fluid or model-derived value.
"""

from __future__ import annotations

from crawfish.core import Policy, PolicyKind

spend_guard = Policy(
    name="spend_guard",
    kind=PolicyKind.GUARDRAIL,
    rules={"max_usd_per_batch": 5.0},
)
