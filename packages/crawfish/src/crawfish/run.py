"""Run — one durable execution of a Definition against one input set.

A Run drives execution through the :class:`AgentRuntime` seam (the product model
never imports the SDK), binding fluid inputs as **session data** — never into the
instruction/system prompt (the boundary is enforced by the prompt compiler). It emits
OTel-shaped spans (run = trace, model/tool calls = spans) into the ``Store``, validates
every input slot before executing, idles durably on an approval gate without burning
compute, and is hard-killed at the cost cap (telemetry captured either way).
"""

from __future__ import annotations

import time
from enum import Enum

from crawfish.core.context import BudgetExceeded, RunContext
from crawfish.core.ids import new_id
from crawfish.core.types import JSONValue
from crawfish.definition.types import Definition
from crawfish.emission import Emission, EmissionKind, emit
from crawfish.output import Output
from crawfish.runtime.base import AgentRuntime
from crawfish.runtime.team import run_team
from crawfish.store.base import Store

__all__ = ["RunStatus", "Run", "InputBindingError", "RunSuspended"]


class RunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    SUSPENDED = "suspended"  # idling on an approval gate, state held durably


class InputBindingError(ValueError):
    """Raised when a required input slot is unbound before execution."""


class RunSuspended(RuntimeError):
    """Raised when a Run idles on an approval gate (state persisted, no compute spent)."""


class Run:
    """An agent team performing a single task."""

    def __init__(
        self,
        definition: Definition,
        inputs: dict[str, JSONValue] | None = None,
        *,
        runtime: AgentRuntime | None = None,
        requires_approval: bool = False,
        id: str | None = None,
    ) -> None:
        self.id = id or new_id()
        self.definition = definition
        self.inputs: dict[str, JSONValue] = dict(inputs or {})
        self.runtime = runtime
        self.requires_approval = requires_approval
        self.status = RunStatus.PENDING
        self.output: Output[JSONValue] | None = None

    # -- validation ---------------------------------------------------------
    def validate(self) -> None:
        """Fail fast if any required input slot is unbound (before any model call)."""
        provided = set(self.inputs)
        missing = [
            p.name
            for p in self.definition.inputs
            if p.required and p.default is None and p.name not in provided
        ]
        if missing:
            raise InputBindingError(f"missing required input(s): {missing}")

    # -- persistence / telemetry -------------------------------------------
    def _persist(self, ctx: RunContext) -> None:
        ctx.store.put_record(
            "run",
            self.id,
            {
                "id": self.id,
                "definition": self.definition.id,
                "version": str(self.definition.version),
                "status": self.status.value,
            },
            org_id=ctx.org_id,
        )

    def _emit_start(self, ctx: RunContext, runtime_name: str, **attrs: JSONValue) -> None:
        """Emit a typed RUN_START onto the ledger (replaces the loose run.start span)."""
        emit(
            ctx.store,
            Emission(
                kind=EmissionKind.RUN_START,
                run_id=ctx.run_id,
                org_id=ctx.org_id,
                node_id=self.id,
                attrs={"runtime": runtime_name, **attrs},
            ),
            org_id=ctx.org_id,
        )

    def _emit_finish(
        self, ctx: RunContext, status: str, *, tainted: bool = False, **attrs: JSONValue
    ) -> None:
        """Emit a typed RUN_FINISH onto the ledger (replaces the loose run.finish span).

        ``tainted`` propagates the producing ``Output.tainted`` marker across the
        emission boundary where the run handled an Output.
        """
        emit(
            ctx.store,
            Emission(
                kind=EmissionKind.RUN_FINISH,
                run_id=ctx.run_id,
                org_id=ctx.org_id,
                node_id=self.id,
                attrs={"status": status, **attrs},
                tainted=tainted,
            ),
            org_id=ctx.org_id,
        )

    # -- execution ----------------------------------------------------------
    async def execute(
        self,
        ctx: RunContext,
        runtime: AgentRuntime | None = None,
        *,
        approve: bool | None = None,
    ) -> Output[JSONValue]:
        """Execute the Definition's team on the bound inputs → a typed Output.

        ``approve`` gates a ``requires_approval`` Run: ``None`` (or ``False``) idles the
        run durably (``RunSuspended``) without spending compute; ``True`` proceeds.
        """
        rt = runtime or self.runtime
        if rt is None:
            raise ValueError("Run.execute requires an AgentRuntime")

        self.validate()

        # Approval gate: idle durably before burning any compute.
        if self.requires_approval and not approve:
            self.status = RunStatus.SUSPENDED
            self._persist(ctx)
            self._emit_finish(ctx, "suspended", reason="awaiting_approval")
            raise RunSuspended(f"run {self.id} awaiting approval")

        self.status = RunStatus.RUNNING
        self._persist(ctx)
        start = time.perf_counter()
        self._emit_start(ctx, rt.name, definition=self.definition.id)

        try:
            result = await run_team(self.definition, self.inputs, ctx, rt)
        except BudgetExceeded as exc:
            self.status = RunStatus.FAILED
            self._persist(ctx)
            self._emit_finish(
                ctx,
                "failed",
                reason="budget_exceeded",
                detail=str(exc),
                latency_ms=(time.perf_counter() - start) * 1000,
            )
            raise
        except Exception as exc:
            self.status = RunStatus.FAILED
            self._persist(ctx)
            self._emit_finish(
                ctx,
                "failed",
                detail=str(exc),
                latency_ms=(time.perf_counter() - start) * 1000,
            )
            raise

        # Output schema derives from the Definition's declared outputs. The result
        # is tainted if any input was fluid (untrusted) — taint originates here and
        # propagates downstream.
        from crawfish.runtime.prompt import split_inputs

        _static, fluid = split_inputs(self.definition, self.inputs)
        out: Output[JSONValue] = Output(
            output_schema=list(self.definition.outputs),
            value=result.text,
            produced_by=self.id,
            tainted=bool(fluid),
        )
        out.persist(ctx.store, org_id=ctx.org_id)
        self.output = out
        self.status = RunStatus.DONE
        self._persist(ctx)
        # Taint propagates from the produced Output across the emission boundary.
        self._emit_finish(
            ctx,
            "done",
            tainted=out.tainted,
            cost_usd=result.cost_usd,
            latency_ms=(time.perf_counter() - start) * 1000,
        )
        return out

    # -- durability / recovery ---------------------------------------------
    @classmethod
    def restore(
        cls,
        store: Store,
        run_id: str,
        definition: Definition,
        *,
        runtime: AgentRuntime | None = None,
        org_id: str = "local",
    ) -> Run:
        """Rebuild a Run from its persisted record (restart recovery)."""
        record = store.get_record("run", run_id, org_id=org_id)
        if record is None:
            raise KeyError(f"no persisted run {run_id!r}")
        run = cls(definition, runtime=runtime, id=run_id)
        run.status = RunStatus(str(record["status"]))
        return run
