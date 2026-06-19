"""Team coordination — executing a TeamSpec topology (CRA-135).

Decision (locked): lean on Claude's **hierarchical subagent model**, not a bespoke
peer-to-peer message bus. Communication is **delegation-in / typed-result-out** — a
lead dispatches subagents and combines their typed results; there is no free-form
channel, which preserves typing and the prompt-injection boundary (a subagent's result
re-enters the lead as fluid data, never as instructions).

The coordinator is runtime-agnostic (works with any :class:`AgentRuntime`, incl. the
mock — so tests are deterministic). For backends with native hierarchical subagents
(CommandRuntime/CMA) this same topology can later collapse into one native multiagent
call; the explicit coordinator is the portable default (ADR 0007).
"""

from __future__ import annotations

from crawfish.core.context import RunContext
from crawfish.core.types import JSONValue
from crawfish.definition.types import Coordination, Definition
from crawfish.runtime.base import AgentRuntime, RunRequest, RunResult
from crawfish.runtime.prompt import pick_agent

__all__ = ["run_team"]


async def run_team(
    definition: Definition,
    inputs: dict[str, JSONValue],
    ctx: RunContext,
    runtime: AgentRuntime,
) -> RunResult:
    """Execute a Definition's team per its coordination topology, return one result."""
    topology = definition.team.coordination
    if topology is Coordination.SEQUENTIAL:
        return await _run_sequential(definition, inputs, ctx, runtime)
    if topology is Coordination.LEAD:
        return await _run_lead(definition, inputs, ctx, runtime)
    return await _run_single(definition, inputs, ctx, runtime)


async def _run_single(
    definition: Definition,
    inputs: dict[str, JSONValue],
    ctx: RunContext,
    runtime: AgentRuntime,
) -> RunResult:
    agent = pick_agent(definition, None)
    return await runtime.run(RunRequest(definition=definition, role=agent.role, inputs=inputs), ctx)


async def _run_sequential(
    definition: Definition,
    inputs: dict[str, JSONValue],
    ctx: RunContext,
    runtime: AgentRuntime,
) -> RunResult:
    """Agents run in declared order; each result threads into the next as fluid data."""
    threaded: dict[str, JSONValue] = dict(inputs)
    last: RunResult | None = None
    total_cost = 0.0
    for agent in definition.team.agents:
        ctx.cancel_token.raise_if_cancelled()
        last = await runtime.run(
            RunRequest(definition=definition, role=agent.role, inputs=threaded), ctx
        )
        total_cost += last.cost_usd
        threaded["prior_result"] = last.text  # typed-result-out -> delegation-in
    if last is None:
        raise ValueError("sequential team has no agents")
    return last.model_copy(update={"cost_usd": total_cost})


async def _run_lead(
    definition: Definition,
    inputs: dict[str, JSONValue],
    ctx: RunContext,
    runtime: AgentRuntime,
) -> RunResult:
    """Lead dispatches its delegates, then combines their typed results."""
    lead = pick_agent(definition, definition.team.lead)
    total_cost = 0.0
    delegated: dict[str, JSONValue] = dict(inputs)

    for role in lead.delegates_to:
        ctx.cancel_token.raise_if_cancelled()
        sub = await runtime.run(RunRequest(definition=definition, role=role, inputs=inputs), ctx)
        total_cost += sub.cost_usd
        delegated[f"{role}_result"] = sub.text  # typed result re-enters as fluid data

    result = await runtime.run(
        RunRequest(definition=definition, role=lead.role, inputs=delegated), ctx
    )
    total_cost += result.cost_usd
    return result.model_copy(update={"cost_usd": total_cost})
