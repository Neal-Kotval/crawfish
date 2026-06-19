"""CRA-114 acceptance: .env, least-privilege secrets, scrubbing, capabilities, taint."""

from __future__ import annotations

from pathlib import Path

from crawfish.output import Output
from crawfish.secrets import (
    ScrubbingStore,
    SecretManager,
    load_env,
    read_capabilities,
    redact,
    resolve_secret,
)
from crawfish.store import SqliteStore


def test_load_env(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text('GITHUB_TOKEN=ghp_secretvalue123456789\n# comment\nFOO="bar"\n')
    env = load_env(tmp_path / ".env")
    assert env["GITHUB_TOKEN"] == "ghp_secretvalue123456789"
    assert env["FOO"] == "bar"


def test_secret_by_reference() -> None:
    assert resolve_secret("K", {"K": "v"}) == "v"
    assert resolve_secret(None) is None


def test_least_privilege_node_secrets() -> None:
    mgr = SecretManager(env={"A": "1", "B": "2", "C": "3"})
    mgr.declare("node1", ["A", "B"])
    got = mgr.for_node("node1")
    assert got == {"A": "1", "B": "2"}  # node only receives what it declared
    assert mgr.for_node("other") == {}


def test_redact_values_and_patterns() -> None:
    text = "token=ghp_abcdefghijklmnopqrstuv and key sk-ABCDEFGHIJKLMNOP and mine@x.com"
    out = redact(text, ["supersecret"])
    assert "ghp_" not in out
    assert "sk-" not in out
    assert "@x.com" not in out


def test_scrubbing_store_redacts_before_write() -> None:
    store = ScrubbingStore(SqliteStore(), secrets=["topsecret"])
    store.put_record("run", "r1", {"transcript": "the password is topsecret"})
    rec = store.get_record("run", "r1")
    assert rec is not None
    assert "topsecret" not in rec["transcript"]


def test_capabilities_consent_surface(tmp_path: Path) -> None:
    (tmp_path / "crawfish.toml").write_text(
        '[capabilities]\nsecrets = ["GITHUB_TOKEN"]\negress = ["api.github.com"]\n'
    )
    caps = read_capabilities(tmp_path)
    assert "GITHUB_TOKEN" in caps.summary()
    assert "api.github.com" in caps.summary()


def test_output_taint_propagates() -> None:
    tainted = Output(output_schema=[], value={"x": 1}, produced_by="s", tainted=True)
    derived = tainted.derive(value={"x": 2}, produced_by="f")
    assert derived.tainted is True  # taint flows through derivation
    clean = tainted.derive(value={"x": 3}, produced_by="f", tainted=False)
    assert clean.tainted is False
