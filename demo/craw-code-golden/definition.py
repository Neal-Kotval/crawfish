"""Golden Definition — typed IO boundary (CRA-257).

The reference Definition authored exactly to the file-by-file playbook
(``docs/specs/craw-code/authoring/``). ``project`` is STATIC author config; ``ticket_body``
is FLUID, untrusted per-item data — the prompt-injection boundary.

The output is a typed ``Triage`` **record** ({category, severity, summary}). It is declared
``Flow.STATIC``: the team writes its decision into a consequential static slot, so ALG-3
(``assert_no_fluid_to_static_sink``) discharges it and the project is build-gate clean. A
FLUID output here would be treated as a suspected fluid-fed target slot and fail the gate.
The record type is registered on the process-wide ``default_registry`` at import so
``validate_output`` can walk it.
"""

from __future__ import annotations

from crawfish.core import Flow, Parameter
from crawfish.typesystem import default_registry

default_registry.register_record(
    "Triage",
    {"category": "str", "severity": "str", "summary": "str"},
)

inputs = [
    Parameter(name="project", type="str", flow=Flow.STATIC),  # set once at batch start
    Parameter(name="ticket_body", type="str"),  # default → FLUID (untrusted per-item data)
]
# STATIC consequential output: the triage decision is written into a static slot, so the
# assembly gate can prove it is non-consequential-fluid (the scaffold's build-clean idiom).
outputs = [Parameter(name="triage", type="Triage", flow=Flow.STATIC)]

lead = "lead"
