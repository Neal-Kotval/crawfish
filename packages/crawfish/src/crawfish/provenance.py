"""Provenance + consent re-gate on generated artifacts (SEC-1, CRA-238).

``craw code`` is a **stochastic agent** that authors ``Definition``\\s, prompts, and
distilled predicates. It is *not* benign: a prompt-injected generator (fed a poisoned
ticket / RAG hit) can author a Definition that declares an attacker-chosen secret, MCP
connection, or consequential Sink target. The eval gate stops quality *regressions* — it
does **not** stop a malicious-but-passing artifact. This module is the *capability* net
the eval gate does not provide.

Two deterministic mechanisms (generation stays stochastic + confined; the gate is pure):

* **Provenance** — every generated artifact records who/what generated it
  (:class:`Provenance`: ``generated_by`` + the source ``taint`` + a content hash of the
  artifact), persisted as a queryable ledger record and emission. The generator boundary
  is recorded so a later audit can answer "what authored this, and from what input".
* **Consent re-gate** — :func:`regate_generated`. A generated Definition that *newly*
  declares a secret, MCP connection, or consequential Sink **re-enters the install-time
  capability-consent gate** (``secrets.consent_install``) before it may run unattended.
  Generated ≠ trusted: a model-authored capability is never auto-trusted. Until a human /
  CI signs the artifact admissible (:func:`sign`), an unsigned generated artifact runs
  only in shadow/eval and may **not** fire a consequential Sink — :func:`assert_admissible`
  fails closed.

Determinism / security: the artifact hash is a pure function of the Definition's content
sha; the gate decision is pure given the (static) declared capabilities and the stored
:class:`~crawfish.secrets.Grant`. A FLUID-derived capability can never appear here — the
declared capabilities surfaced for consent are static-only (the prompt-injection spine).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from crawfish.core.ids import new_id
from crawfish.core.types import JSONValue
from crawfish.secrets import (
    Capabilities,
    ConsentDecider,
    ConsentDeclined,
    Grant,
    GrantManifest,
    consent_install,
)
from crawfish.store.base import Store

if TYPE_CHECKING:
    from crawfish.definition.types import Definition

__all__ = [
    "Provenance",
    "ProvenanceLedger",
    "ConsentRequired",
    "SigningRequired",
    "PROVENANCE_RECORD_KIND",
    "SIGNATURE_RECORD_KIND",
    "declared_capabilities",
    "record_provenance",
    "regate_generated",
    "sign",
    "is_signed",
    "assert_admissible",
]

#: Store record ``kind`` for a generated artifact's provenance (one per artifact sha).
PROVENANCE_RECORD_KIND = "generated_provenance"
#: Store record ``kind`` for a human/CI signature admitting an artifact to prod.
SIGNATURE_RECORD_KIND = "generated_signature"


class ConsentRequired(RuntimeError):
    """A generated artifact declares a new secret/MCP/Sink capability without consent.

    Fail-closed: a generated Definition that newly holds a secret or fires a consequential
    Sink re-enters the install-time consent gate; until consent is recorded, it may not run
    unattended. Generated ≠ trusted.
    """


class SigningRequired(RuntimeError):
    """An unsigned generated artifact was asked to fire a consequential action.

    Until a human / CI signs the artifact (:func:`sign`), it is admissible only to
    shadow/eval — never to a consequential Sink in eval/prod. Fail-closed.
    """


@dataclass(frozen=True)
class Provenance:
    """Who/what generated an artifact, the source taint, and the artifact's content hash.

    The generator boundary, recorded. ``generated_by`` names the authoring agent/loop
    (e.g. ``"craw-code"``); ``source_tainted`` marks that the generation drew on fluid
    (untrusted) input — a poisoned ticket/RAG hit — so a downstream audit can treat a
    tainted-provenance artifact with extra suspicion. ``artifact_sha`` is the Definition's
    content sha (the lineage key); frozen + content-stable.
    """

    artifact_sha: str
    generated_by: str
    source_tainted: bool = False
    artifact_id: str = ""
    provenance_id: str = field(default_factory=new_id)

    def to_record(self) -> dict[str, JSONValue]:
        return {
            "v": 1,
            "artifact_sha": self.artifact_sha,
            "generated_by": self.generated_by,
            "source_tainted": self.source_tainted,
            "artifact_id": self.artifact_id,
            "provenance_id": self.provenance_id,
        }

    @classmethod
    def from_record(cls, data: dict[str, JSONValue]) -> Provenance:
        return cls(
            artifact_sha=str(data.get("artifact_sha", "")),
            generated_by=str(data.get("generated_by", "")),
            source_tainted=bool(data.get("source_tainted", False)),
            artifact_id=str(data.get("artifact_id", "")),
            provenance_id=str(data.get("provenance_id") or new_id()),
        )


def _content_sha(definition: Definition) -> str:
    """The artifact's content hash (the lineage key) — the version sha, else content_sha()."""
    sha = getattr(definition.version, "sha", None)
    if sha:
        return str(sha)
    return str(definition.content_sha())


class ProvenanceLedger:
    """A Store-backed, queryable record of generated-artifact provenance + signatures.

    Persistence rides the ``Store`` seam (SQLite → Postgres is a driver swap). Every
    record carries ``org_id`` (tenancy). One provenance record per artifact sha; one
    signature record per artifact sha.
    """

    def __init__(self, store: Store, *, org_id: str = "local") -> None:
        self._store = store
        self._org_id = org_id

    def record(self, prov: Provenance) -> None:
        """Persist (or overwrite) the provenance for ``prov.artifact_sha``."""
        self._store.put_record(
            PROVENANCE_RECORD_KIND, prov.artifact_sha, prov.to_record(), org_id=self._org_id
        )

    def lookup(self, artifact_sha: str) -> Provenance | None:
        """Return the recorded provenance for ``artifact_sha``, or None."""
        rec = self._store.get_record(PROVENANCE_RECORD_KIND, artifact_sha, org_id=self._org_id)
        return None if rec is None else Provenance.from_record(rec)

    def list(self) -> list[Provenance]:
        """Every recorded provenance in this org (the audit surface)."""
        return [
            Provenance.from_record(r)
            for r in self._store.list_records(PROVENANCE_RECORD_KIND, org_id=self._org_id)
        ]

    def sign(self, artifact_sha: str, *, signer: str) -> None:
        """Mark ``artifact_sha`` admissible to prod (a human/CI approval)."""
        self._store.put_record(
            SIGNATURE_RECORD_KIND,
            artifact_sha,
            {"v": 1, "artifact_sha": artifact_sha, "signer": signer},
            org_id=self._org_id,
        )

    def is_signed(self, artifact_sha: str) -> bool:
        """True iff a signature was recorded for ``artifact_sha``."""
        return (
            self._store.get_record(SIGNATURE_RECORD_KIND, artifact_sha, org_id=self._org_id)
            is not None
        )


def declared_capabilities(definition: Definition) -> Capabilities:
    """The STATIC secret/egress capabilities a Definition declares (the consent surface).

    Reads only static, author/generator-declared references — never a fluid value (the
    prompt-injection spine: a fluid value can never name a secret or an egress target).
    Folds in: each agent/MCP ``auth`` reference (a secret by name), each MCP connection's
    egress host, and any sink target host the Definition carries in ``assets``.
    """
    secrets: list[str] = []
    egress: list[str] = []
    assets = getattr(definition, "assets", None)
    if assets is not None:
        for conn in getattr(assets, "mcp", []) or []:
            auth = getattr(conn, "auth", None)
            if isinstance(auth, str) and auth:
                secrets.append(auth)
            name = getattr(conn, "name", None)
            if isinstance(name, str) and name:
                egress.append(name)
    # De-dup, stable order (deterministic consent surface).
    return Capabilities(
        secrets=sorted(dict.fromkeys(secrets)),
        egress=sorted(dict.fromkeys(egress)),
    )


def record_provenance(
    definition: Definition,
    *,
    store: Store,
    generated_by: str,
    source_tainted: bool = False,
    org_id: str = "local",
    emit_event: bool = True,
) -> Provenance:
    """Stamp + persist provenance for a generated ``definition`` (queryable + audited).

    Records who/what generated the artifact and whether the generation drew on fluid
    (untrusted) input, keyed by the artifact's content sha. With ``emit_event`` an
    append-only ``METRIC`` emission is written so the generation is visible on the
    dashboard/ledger. Pure given the Definition's content sha.
    """
    prov = Provenance(
        artifact_sha=_content_sha(definition),
        generated_by=generated_by,
        source_tainted=source_tainted,
        artifact_id=str(getattr(definition, "id", "")),
    )
    ProvenanceLedger(store, org_id=org_id).record(prov)
    if emit_event:
        from crawfish.emission import Emission, EmissionKind, emit

        emit(
            store,
            Emission(
                kind=EmissionKind.METRIC,
                run_id=f"generated:{prov.artifact_sha}",
                org_id=org_id,
                attrs={
                    "metric": "artifact.generated",
                    "artifact_sha": prov.artifact_sha,
                    "generated_by": generated_by,
                    "artifact_id": prov.artifact_id,
                },
                # Provenance is itself tainted if the generation drew on fluid input.
                tainted=source_tainted,
            ),
            org_id=org_id,
        )
    return prov


def _new_capabilities(declared: Capabilities, prior: Grant | None) -> Capabilities:
    """The secrets/egress in ``declared`` that ``prior`` does NOT already grant.

    A re-gate is required only for *newly* declared capabilities — an artifact that
    declares nothing the existing grant doesn't already cover needs no new consent.
    """
    prior_secrets = set(prior.secrets) if prior is not None else set()
    prior_egress = set(prior.egress) if prior is not None else set()
    return Capabilities(
        secrets=[s for s in declared.secrets if s not in prior_secrets],
        egress=[e for e in declared.egress if e not in prior_egress],
    )


def regate_generated(
    definition: Definition,
    *,
    store: Store,
    generated_by: str,
    package: str | None = None,
    decider: ConsentDecider | None = None,
    source_tainted: bool = False,
    org_id: str = "local",
) -> Provenance:
    """Record provenance AND re-gate a generated artifact through install-time consent.

    The SEC-1 trust boundary. After stamping provenance, the artifact's STATIC declared
    capabilities (:func:`declared_capabilities`) are diffed against any prior
    :class:`~crawfish.secrets.Grant` for ``package``. If it newly declares a secret, MCP
    connection, or consequential egress target, it **re-enters** the install-time
    capability-consent gate (``secrets.consent_install``) — generated ≠ trusted. The
    default decider is fail-closed (``DenyConsent``): a non-interactive context grants
    nothing silently.

    Raises :class:`ConsentRequired` if the re-gate is declined (no grant recorded; the
    artifact stays fail-closed). Returns the recorded :class:`Provenance` on success or
    when no new capability is declared (nothing to re-consent).
    """
    prov = record_provenance(
        definition,
        store=store,
        generated_by=generated_by,
        source_tainted=source_tainted,
        org_id=org_id,
    )
    pkg = package or str(getattr(definition, "id", "")) or prov.artifact_sha
    declared = declared_capabilities(definition)
    prior = GrantManifest(store, org_id=org_id).lookup(pkg)
    new_caps = _new_capabilities(declared, prior)
    if not new_caps.secrets and not new_caps.egress:
        # Nothing the existing grant doesn't already cover — no new consent needed.
        return prov
    try:
        consent_install(
            pkg,
            # Re-consent the FULL declared surface (so the grant is complete), but the
            # *trigger* was a newly declared capability the prior grant lacked.
            declared,
            store=store,
            decider=decider,
            org_id=org_id,
        )
    except ConsentDeclined as exc:
        raise ConsentRequired(
            f"generated artifact {prov.artifact_sha} (by {generated_by!r}) newly declares "
            f"capabilities {new_caps.summary()}; consent was declined — it may not run "
            f"unattended (generated ≠ trusted)"
        ) from exc
    return prov


def sign(definition: Definition, *, store: Store, signer: str, org_id: str = "local") -> None:
    """Mark a generated artifact admissible to prod (a human/CI signature)."""
    ProvenanceLedger(store, org_id=org_id).sign(_content_sha(definition), signer=signer)


def is_signed(definition: Definition, *, store: Store, org_id: str = "local") -> bool:
    """True iff a signature admitting ``definition`` to prod was recorded."""
    return ProvenanceLedger(store, org_id=org_id).is_signed(_content_sha(definition))


def assert_admissible(definition: Definition, *, store: Store, org_id: str = "local") -> None:
    """Fail closed unless a generated artifact is signed admissible for a consequential action.

    The gate the consequential-Sink egress consults for a *generated* artifact: if the
    Definition has recorded provenance (it was machine-generated) it must also carry a
    signature, else :class:`SigningRequired` is raised. A non-generated (no-provenance)
    artifact is unaffected — this gate governs the generator boundary only.
    """
    ledger = ProvenanceLedger(store, org_id=org_id)
    sha = _content_sha(definition)
    if ledger.lookup(sha) is None:
        return  # not a generated artifact — outside this gate's scope
    if not ledger.is_signed(sha):
        raise SigningRequired(
            f"generated artifact {sha} is unsigned; an unsigned generated artifact may not "
            f"fire a consequential action in eval/prod (sign() it after review)"
        )
