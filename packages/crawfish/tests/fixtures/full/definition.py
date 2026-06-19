"""The typed IO boundary + manifest-in-code for the full fixture."""

from __future__ import annotations

from crawfish.core import Flow, Parameter

inputs = [
    Parameter(name="repo", type="str", flow=Flow.STATIC),
    Parameter(name="pr_body", type="str"),  # fluid (per-item)
]
outputs = [Parameter(name="review", type="str")]

lead = "lead"
