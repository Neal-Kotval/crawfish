"""CRA-180 — craw install / capability consent + the grant manifest.

Capabilities are DECLARED in ``[capabilities]`` but, before this issue, never ENFORCED
at install. These tests prove the install gate:

  * install surfaces the DECLARED capabilities (secrets by REFERENCE, never value) and,
    on explicit approval, records a :class:`Grant`;
  * a DECLINE records NO grant — fail-closed (the broker denies any ungranted lease);
  * the recorded :class:`Grant` is exactly what the broker (CRA-178) consumes — a granted
    secret leases, an ungranted one is denied;
  * the grant manifest persists + round-trips through the :class:`Store` seam;
  * the consent surface shows references, not values;
  * a non-interactive install is fail-closed without an explicit approval.

Determinism: the consent decision is an injected fake decider (no real stdin prompt); a
fake transport + fake secret-value table (no live calls).
"""

from __future__ import annotations

import pytest

from crawfish.secrets import (
    AutoConsent,
    CallbackConsent,
    Capabilities,
    ConsentDeclined,
    ConsentRequest,
    DenyConsent,
    Grant,
    GrantManifest,
    LeaseDenied,
    Outbound,
    SecretBroker,
    SecretRequest,
    consent_install,
)
from crawfish.store import SqliteStore

REF = "ACME_API_KEY"
SECRET_VALUE = "sk-supersecret-value-0123456789"
DEST = "api.acme.com"
PACKAGE = "crawfish-acme"


def _caps() -> Capabilities:
    return Capabilities(secrets=[REF], egress=[DEST])


class FakeTransport:
    def __init__(self) -> None:
        self.sent: list[Outbound] = []

    def send(self, request: Outbound) -> object:
        self.sent.append(request)
        return {"status": "ok"}


# --- install surfaces declared capabilities + records a grant on approval ----------


def test_install_records_grant_on_approval() -> None:
    store = SqliteStore()
    grant = consent_install(PACKAGE, _caps(), store=store, decider=AutoConsent(), now=123.0)
    assert grant.package == PACKAGE
    assert grant.secrets == (REF,)
    assert grant.egress == (DEST,)
    assert grant.granted_at == 123.0
    # Persisted + queryable via the manifest (Store seam).
    assert GrantManifest(store).lookup(PACKAGE) == grant


def test_consent_request_surfaces_declared_capabilities() -> None:
    request = ConsentRequest.from_capabilities(PACKAGE, _caps())
    assert request.secrets == (REF,)
    assert request.egress == (DEST,)
    seen: list[ConsentRequest] = []
    consent_install(
        PACKAGE,
        _caps(),
        store=SqliteStore(),
        decider=CallbackConsent(lambda r: (seen.append(r), True)[1]),
    )
    assert seen and seen[0].secrets == (REF,) and seen[0].egress == (DEST,)


# --- decline records NO grant (fail-closed) ----------------------------------------


def test_decline_records_no_grant() -> None:
    store = SqliteStore()
    with pytest.raises(ConsentDeclined):
        consent_install(PACKAGE, _caps(), store=store, decider=DenyConsent())
    assert GrantManifest(store).lookup(PACKAGE) is None


def test_non_interactive_default_is_fail_closed() -> None:
    """No decider → DenyConsent default → declined, fail-closed, no grant."""
    store = SqliteStore()
    with pytest.raises(ConsentDeclined):
        consent_install(PACKAGE, _caps(), store=store)
    assert GrantManifest(store).lookup(PACKAGE) is None


# --- consent shows references, never values ----------------------------------------


def test_consent_surface_shows_references_not_values() -> None:
    request = ConsentRequest.from_capabilities(PACKAGE, _caps())
    summary = request.summary()
    assert REF in summary
    assert SECRET_VALUE not in summary
    # And the recorded grant carries the reference, never a value.
    grant = consent_install(PACKAGE, _caps(), store=SqliteStore(), decider=AutoConsent())
    assert REF in grant.secrets
    assert SECRET_VALUE not in grant.secrets


# --- the recorded grant is what the broker consumes --------------------------------


def test_granted_secret_leases_via_broker() -> None:
    store = SqliteStore()
    consent_install(PACKAGE, _caps(), store=store, decider=AutoConsent())
    # The broker consumes the consented grant directly.
    looked_up = GrantManifest(store).lookup(PACKAGE)
    assert looked_up is not None
    transport = FakeTransport()
    broker = SecretBroker(secret_values={REF: SECRET_VALUE}, transport=transport)
    handle = broker.lease(SecretRequest(node_id="sink", ref=REF, destination=DEST), looked_up)
    assert handle.ref == REF


def test_ungranted_secret_is_denied_by_broker() -> None:
    """A package never granted a secret cannot lease it — fail-closed end to end."""
    store = SqliteStore()
    # Consent to NOTHING (empty capabilities) → grant covers nothing.
    grant = consent_install(PACKAGE, Capabilities(), store=store, decider=AutoConsent())
    transport = FakeTransport()
    broker = SecretBroker(secret_values={REF: SECRET_VALUE}, transport=transport)
    with pytest.raises(LeaseDenied):
        broker.lease(SecretRequest(node_id="sink", ref=REF, destination=DEST), grant)


def test_no_grant_means_no_lease() -> None:
    """When consent was declined there is no grant to consume → cannot lease."""
    store = SqliteStore()
    with pytest.raises(ConsentDeclined):
        consent_install(PACKAGE, _caps(), store=store, decider=DenyConsent())
    grant = GrantManifest(store).lookup(PACKAGE)
    assert grant is None
    # The broker has nothing to lease against; an empty grant denies.
    empty = Grant(package=PACKAGE)
    broker = SecretBroker(secret_values={REF: SECRET_VALUE}, transport=FakeTransport())
    with pytest.raises(LeaseDenied):
        broker.lease(SecretRequest(node_id="sink", ref=REF, destination=DEST), empty)


# --- manifest persists + round-trips through the Store -----------------------------


def test_manifest_round_trips_through_store() -> None:
    store = SqliteStore()
    manifest = GrantManifest(store)
    g = Grant(package=PACKAGE, secrets=(REF,), egress=(DEST,), granted_at=9.0)
    manifest.save(g)
    assert manifest.lookup(PACKAGE) == g
    assert manifest.list() == [g]
    manifest.revoke(PACKAGE)
    assert manifest.lookup(PACKAGE) is None


def test_manifest_overwrites_on_reconsent() -> None:
    store = SqliteStore()
    consent_install(PACKAGE, Capabilities(secrets=[REF]), store=store, decider=AutoConsent())
    consent_install(
        PACKAGE, Capabilities(secrets=[REF], egress=[DEST]), store=store, decider=AutoConsent()
    )
    grant = GrantManifest(store).lookup(PACKAGE)
    assert grant is not None and grant.egress == (DEST,)
    assert len(GrantManifest(store).list()) == 1


def test_manifest_is_org_scoped() -> None:
    store = SqliteStore()
    consent_install(PACKAGE, _caps(), store=store, decider=AutoConsent(), org_id="org-a")
    assert GrantManifest(store, org_id="org-b").lookup(PACKAGE) is None
    assert GrantManifest(store, org_id="org-a").lookup(PACKAGE) is not None


# --- upconverter registered on the CRA-191 read path -------------------------------


def test_grant_kind_has_upconverter_registered() -> None:
    from crawfish.secrets import GRANT_RECORD_KIND
    from crawfish.store.migrations import RECORD_UPCONVERTERS

    assert GRANT_RECORD_KIND in RECORD_UPCONVERTERS
    # A pre-versioning row (no "v") up-converts to v1 and still reads back.
    conv = RECORD_UPCONVERTERS[GRANT_RECORD_KIND]
    out = conv({"package": PACKAGE, "secrets": [REF], "egress": [DEST], "grant_id": "x"})
    assert out["v"] == 1


# --- CLI wiring --------------------------------------------------------------------


def test_cli_install_records_grant(tmp_path, capsys) -> None:  # type: ignore[no-untyped-def]
    (tmp_path / "crawfish.toml").write_text(
        "[project]\nname = 'cli-pkg'\n\n"
        "[capabilities]\nsecrets = ['ACME_API_KEY']\negress = ['api.acme.com']\n"
    )
    from crawfish.cli import main

    # Without --yes: fail-closed, no grant, non-zero exit.
    assert main(["install", str(tmp_path)]) == 1
    out = capsys.readouterr().out
    assert "ACME_API_KEY" in out  # reference surfaced
    assert "NOT consented" in out

    # With --yes: grant recorded.
    assert main(["install", str(tmp_path), "--yes"]) == 0
    out = capsys.readouterr().out
    assert "grant" in out.lower()

    store = SqliteStore(tmp_path / ".crawfish" / "crawfish.db")
    assert GrantManifest(store).lookup("cli-pkg") is not None
    store.close()
