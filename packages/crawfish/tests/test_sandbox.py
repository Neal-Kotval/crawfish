"""CRA-114 acceptance: out-of-process host-side execution + egress broker."""

from __future__ import annotations

import os

import pytest

from crawfish.sandbox import EgressBroker, EgressDenied, run_out_of_process


def _double(x: int) -> int:
    return x * 2


def _pid() -> int:
    return os.getpid()


def test_runs_in_a_separate_process() -> None:
    assert run_out_of_process(_double, 21) == 42
    assert run_out_of_process(_pid) != os.getpid()  # genuinely out-of-process


def test_egress_broker_allows_and_denies() -> None:
    broker = EgressBroker(allow=["api.github.com"])
    assert broker.permitted("api.github.com")
    broker.guard("api.github.com")  # no raise
    assert not broker.permitted("evil.example.com")
    with pytest.raises(EgressDenied):
        broker.guard("evil.example.com")
