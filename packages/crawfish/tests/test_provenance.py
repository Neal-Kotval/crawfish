"""SEC-1 (CRA-238) acceptance: provenance + consent re-gate on generated artifacts.

The generator boundary is a trust boundary: a model-authored Definition that newly
declares a secret/MCP/consequential-Sink re-enters the install-time consent gate, and an
unsigned generated artifact may not fire a consequential action. All deterministic — no
model call.
"""

from __future__ import annotations

import pytest

from crawfish.definition.types import (
    AgentSpec,
    Definition,
    DefinitionAssets,
    MCPConnection,
    TeamSpec,
)
from crawfish.provenance import (
    ConsentRequired,
    Provenance,
    ProvenanceLedger,
    SigningRequired,
    assert_admissible,
    declared_capabilities,
    is_signed,
    record_provenance,
    regate_generated,
    sign,
)
from crawfish.secrets import AutoConsent, DenyConsent, GrantManifest
from crawfish.store.sqlite import SqliteStore


def _plain_def() -> Definition:
    """A generated Definition that declares NO new capability."""
    return Definition(team=TeamSpec(agents=[AgentSpec(role="main")]))


def _capable_def() -> Definition:
    """A generated Definition that declares a secret + egress (a new capability)."""
    return Definition(
        team=TeamSpec(agents=[AgentSpec(role="main")]),
        assets=DefinitionAssets(
            mcp=[MCPConnection(name="github.com", auth="GITHUB_TOKEN", tools=["create_pr"])]
        ),
    )


def test_provenance_recorded_and_queryable() -> None:
    """A generated artifact records who/what generated it + source taint, queryable."""
    store = SqliteStore()
    d = _plain_def()
    prov = record_provenance(d, store=store, generated_by="craw-code", source_tainted=True)
    assert prov.generated_by == "craw-code"
    assert prov.source_tainted is True

    looked = ProvenanceLedger(store).lookup(prov.artifact_sha)
    assert looked is not None
    assert looked.generated_by == "craw-code"
    assert looked.source_tainted is True
    assert [p.artifact_sha for p in ProvenanceLedger(store).list()] == [prov.artifact_sha]


def test_declared_capabilities_are_static_references() -> None:
    """The consent surface reads the secret/egress by reference (name), never a value."""
    caps = declared_capabilities(_capable_def())
    assert "GITHUB_TOKEN" in caps.secrets
    assert "github.com" in caps.egress


def test_regate_raises_consent_required_when_declined() -> None:
    """A generated Definition declaring a NEW capability re-enters consent — fail-closed."""
    store = SqliteStore()
    with pytest.raises(ConsentRequired):
        regate_generated(
            _capable_def(),
            store=store,
            generated_by="craw-code",
            package="pkg",
            decider=DenyConsent(),
        )
    # Fail-closed: no grant was recorded.
    assert GrantManifest(store).lookup("pkg") is None


def test_regate_records_grant_on_explicit_consent() -> None:
    """On explicit approval the re-gate records the consented grant (generated→trusted)."""
    store = SqliteStore()
    regate_generated(
        _capable_def(),
        store=store,
        generated_by="craw-code",
        package="pkg",
        decider=AutoConsent(),
    )
    grant = GrantManifest(store).lookup("pkg")
    assert grant is not None
    assert "GITHUB_TOKEN" in grant.secrets


def test_regate_noop_when_no_new_capability() -> None:
    """A generated artifact declaring nothing new needs no new consent (no raise)."""
    store = SqliteStore()
    # DenyConsent would raise IF a re-gate were triggered; it must not be.
    prov = regate_generated(
        _plain_def(),
        store=store,
        generated_by="craw-code",
        package="pkg",
        decider=DenyConsent(),
    )
    assert ProvenanceLedger(store).lookup(prov.artifact_sha) is not None


def test_unsigned_generated_artifact_cannot_fire_consequential_action() -> None:
    """An unsigned generated artifact is inadmissible for a consequential action."""
    store = SqliteStore()
    d = _plain_def()
    record_provenance(d, store=store, generated_by="craw-code")
    assert not is_signed(d, store=store)
    with pytest.raises(SigningRequired):
        assert_admissible(d, store=store)

    # After a human/CI signature it is admissible.
    sign(d, store=store, signer="ci")
    assert is_signed(d, store=store)
    assert_admissible(d, store=store)  # no raise


def test_non_generated_artifact_is_outside_the_gate() -> None:
    """A Definition with no recorded provenance is not governed by the signing gate."""
    store = SqliteStore()
    # Never recorded provenance ⇒ not a generated artifact ⇒ no SigningRequired.
    assert_admissible(_plain_def(), store=store)


def test_provenance_is_org_scoped() -> None:
    """Provenance + signatures are tenant-isolated (every row carries org_id)."""
    store = SqliteStore()
    d = _plain_def()
    record_provenance(d, store=store, generated_by="craw-code", org_id="orgA")
    assert (
        ProvenanceLedger(store, org_id="orgB").lookup(
            Provenance(artifact_sha=str(d.content_sha()), generated_by="x").artifact_sha
        )
        is None
    )
