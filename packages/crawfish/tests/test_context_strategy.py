"""CRA-138 acceptance: pluggable context strategies compact, preserve boundary, log."""

from __future__ import annotations

from crawfish.core.context import RunContext
from crawfish.runtime import (
    ConversationTurn,
    ExponentialCompact,
    LinearCompact,
    MaxTokens,
    Summarize,
    manage_context,
    resolve_strategy,
)
from crawfish.store import SqliteStore


def _turns(
    n: int, *, chars: int = 8000, fluid_at: set[int] | None = None
) -> list[ConversationTurn]:
    fluid_at = fluid_at or set()
    return [
        ConversationTurn(role="user", text="x" * chars, is_fluid_data=(i in fluid_at))
        for i in range(n)
    ]


def _ctx() -> RunContext:
    return RunContext(store=SqliteStore())


def test_max_tokens_prevents_overflow() -> None:
    strat = MaxTokens(limit=10_000, keep_recent=2)
    turns = _turns(20)  # ~40k tokens, way over
    result = strat.compact(turns)
    assert sum(t.tokens for t in result.turns) <= 10_000 or len(result.turns) == 2
    assert result.compacted


def test_linear_compact_summarizes_oldest() -> None:
    strat = LinearCompact(threshold=10_000, keep_recent=3)
    turns = _turns(10)
    assert strat.should_compact(turns)
    result = strat.compact(turns)
    assert result.turns[0].role == "system"  # summary turn at the front
    assert len(result.turns) == 4  # 1 summary + 3 recent
    assert result.reclaimed_tokens > 0


def test_compaction_preserves_injection_boundary() -> None:
    # an old fluid-data turn gets compacted; the summary must stay tainted as data
    strat = LinearCompact(threshold=1, keep_recent=1)
    turns = _turns(4, fluid_at={0})
    result = strat.compact(turns)
    assert result.turns[0].is_fluid_data is True


def test_no_taint_when_no_fluid_compacted() -> None:
    strat = LinearCompact(threshold=1, keep_recent=1)
    result = strat.compact(_turns(4))
    assert result.turns[0].is_fluid_data is False


def test_switching_strategy_changes_behavior() -> None:
    turns = _turns(12)
    linear = LinearCompact(threshold=1, keep_recent=6).compact(turns)
    summarize = Summarize(threshold=1).compact(turns)
    assert len(linear.turns) != len(summarize.turns)  # different shapes


def test_exponential_grows_each_pass() -> None:
    strat = ExponentialCompact(threshold=1, keep_recent=8)
    first = strat.compact(_turns(20))
    second = strat.compact(_turns(20))
    # second pass keeps fewer recent turns than the first
    assert len(second.turns) < len(first.turns)


def test_manage_context_emits_telemetry() -> None:
    ctx = _ctx()
    strat = LinearCompact(threshold=1, keep_recent=2)
    out = manage_context(_turns(8), strat, ctx)
    assert len(out) < 8
    events = [e["event"] for e in ctx.store.events(ctx.run_id)]
    assert "context.compaction" in events


def test_default_strategy_resolves() -> None:
    assert resolve_strategy(None).name == "linear_compact"
    assert resolve_strategy("max_tokens").name == "max_tokens"
