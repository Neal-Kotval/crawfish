"""UNFILED-ADOPT acceptance: ``craw code explain <topic>`` — a thin doc reader (no model).

Deterministic: ``run_code``, no network/model. Each topic maps to a shipped doc whose body
is returned; an unknown topic fails with usage; the security-spine topic surfaces the spine.
"""

from __future__ import annotations

import json

import pytest

from crawfish.code.adopt import _EXPLAIN_TOPICS, _docs_root
from crawfish.code.cli import run_code


@pytest.mark.parametrize("topic", sorted(_EXPLAIN_TOPICS))
def test_each_topic_resolves_to_a_shipped_doc(topic: str) -> None:
    """Every advertised topic maps to a doc that actually ships in this checkout."""
    doc = _docs_root() / _EXPLAIN_TOPICS[topic]
    assert doc.exists(), f"topic {topic!r} points at a missing doc {_EXPLAIN_TOPICS[topic]}"


def test_explain_returns_body_no_model(capsys: pytest.CaptureFixture[str]) -> None:
    rc = run_code(["explain", "security-spine", "--json"])
    out = capsys.readouterr().out.strip()
    assert rc == 0
    payload = json.loads(out.splitlines()[-1])
    assert payload["topic"] == "security-spine"
    # the body is the actual shipped doc — it names the prompt-injection boundary
    assert "prompt-injection boundary" in str(payload["body"])


def test_unknown_topic_is_usage_error(capsys: pytest.CaptureFixture[str]) -> None:
    rc = run_code(["explain", "no-such-topic", "--json"])
    cap = capsys.readouterr()
    text = cap.out.strip() or cap.err.strip()
    payload = json.loads(text.splitlines()[-1])
    assert rc == 2
    assert "topics" in payload["detail"]


def test_explain_human_prints_doc(capsys: pytest.CaptureFixture[str]) -> None:
    rc = run_code(["explain", "pipeline-model"])
    out = capsys.readouterr().out
    assert rc == 0
    assert out.strip()  # non-empty doc body printed
