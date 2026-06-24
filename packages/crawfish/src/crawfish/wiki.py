"""Summonable knowledge objects — ``Wiki`` (now) and the ``Rag`` seam (deferred).

The Agent Language wants knowledge you *summon* into a feature loop —
``feature_loop(summon=[arch.readonly(), playbook.frozen()])``. The partial substrate
was :class:`~crawfish.memory.Memory` (a mutable KV handle) and the
:class:`~crawfish.runtime.context_artifact.Context` artifact (threaded between agents),
but neither is a **versioned, summonable, narrowable** unit. This module adds the unit.

A :class:`Wiki` is

* **Freezable** (CRA-199): it carries a :class:`~crawfish.versioning.Version` and a
  content hash, so a frozen Wiki is an immutable, reproducible artifact and any edit is
  copy-on-write to a *new* sha. Mutating a frozen Wiki raises
  :class:`~crawfish.versioning.FrozenError`.
* **Summonable**: it hands out a :class:`SummonRef` — a small, pinned-by-version
  reference. A summon enters a run's identity *by hash*, never by body (the body does not
  appear in :meth:`export`'s checksum payload, only the pinned sha).
* **Mode-aware**: ``.readonly()`` returns a frozen view that cannot write;
  ``.mutable()`` is the train-mode edit handle and is **rejected in eval mode** (a frozen
  Wiki), mirroring ``train()``/``eval()`` (CRA-209) — eval mode == frozen.

Storage rides the **Store / ArtifactStore seams** (the protocols, never a concrete
backend): a Wiki persists through :class:`~crawfish.store.base.Store` (so a
``ScrubbingStore`` redacts secrets on the write) and a large page body offloads to an
:class:`~crawfish.artifacts.base.ArtifactStore`. Every operation carries an ``org_id``
tenancy key (defaulted ``"local"``), so a Wiki in org ``"a"`` is invisible to org ``"b"``.

Security (the load-bearing rule, SECURITY.md). Summoned knowledge reaches the model as
**data, never instructions**: :meth:`Wiki.consult` materialises a
:class:`~crawfish.runtime.context_artifact.Context` whose entries are **tainted
(fluid) by default**, so they flow through the fluid-data block and can never reach an
instruction slot or a static-only Sink target. A page that was authored tainted *stays*
tainted across a copy-on-write edit. Pages also carry a **trust tier** (gap S6):
retrieval/consult from a low-trust corpus (e.g. ``customer-tickets``) is a stored-injection
surface and must never be treated as more trusted than a high-trust one (``repo/src``).

``Rag`` (retrieval over a content-hashed corpus snapshot) is the larger half and is
**deferred** to a follow-on. This module ships the *seam* only — a documented
:class:`RagSeam` protocol and a :class:`RagDeferred` marker — so the summon surface,
the trust-tier provenance, and the secret-scrubbing routing are designed in now and the
retrieval implementation drops in later without reshaping callers. No retrieval,
embedding, or indexing is implemented here.
"""

from __future__ import annotations

import hashlib
import json
from enum import Enum
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from pydantic import BaseModel, Field

from crawfish.core.ids import new_id
from crawfish.runtime.context_artifact import Context, ContextEntry
from crawfish.versioning.version import Freezable, FrozenError, Version

if TYPE_CHECKING:
    from crawfish.core.types import JSONValue, Parameter
    from crawfish.store.base import Store

__all__ = [
    "TrustTier",
    "WikiPage",
    "SummonRef",
    "Wiki",
    "RagSeam",
    "RagDeferred",
    "WIKI_RECORD_KIND",
]

#: The Store record ``kind`` a Wiki persists under. One record per (org_id, wiki id).
WIKI_RECORD_KIND = "wiki"


class TrustTier(str, Enum):
    """Source provenance / trust tier of a knowledge page (gap S6).

    A corpus is a persistent stored-injection surface and binary taint is not enough:
    a Wiki built over ``repo/src`` is more trustworthy than one over ``customer-tickets``.
    The tier is carried on every page so a consumer can refuse to let low-trust content
    influence a high-trust decision. It NEVER lowers taint — even ``TRUSTED`` content is
    summoned tainted (data, not instructions); the tier only ever raises suspicion.
    """

    TRUSTED = "trusted"  # first-party, curated (e.g. the repo's own docs)
    COMMUNITY = "community"  # semi-trusted (e.g. a shared playbook)
    UNTRUSTED = "untrusted"  # third-party / user-supplied (e.g. customer tickets)


class WikiPage(BaseModel):
    """One typed page of a :class:`Wiki`. Frozen; taint + trust tier propagate.

    Reuses the :class:`~crawfish.runtime.context_artifact.ContextEntry` value model (typed
    value, schema, taint, lineage) and adds a stable ``title`` (how a page is addressed)
    and a :class:`TrustTier`. Frozen, so a page is content-stable: editing it is a
    copy-on-write that mints a new page (and, in turn, a new Wiki sha).
    """

    title: str
    entry: ContextEntry
    trust: TrustTier = TrustTier.UNTRUSTED

    model_config = {"frozen": True}

    @property
    def tainted(self) -> bool:
        """True iff this page's value is fluid/untrusted (the injection boundary)."""
        return self.entry.tainted

    def page_sha(self) -> str:
        """A deterministic content hash over this page (the Merkle leaf).

        Hashing per-page is what lets a corpus snapshot's hash be a **Merkle over
        pages**: a Wiki re-hashes only changed leaves, never the whole body (the
        resolved-open item on CRA-227). Stable under key ordering.
        """
        blob = json.dumps(
            {
                "title": self.title,
                "trust": self.trust.value,
                "entry": self.entry.model_dump(mode="json"),
            },
            sort_keys=True,
            default=str,
        ).encode()
        return hashlib.sha256(blob).hexdigest()[:12]


class SummonRef(BaseModel):
    """A pinned-by-version reference to a summoned knowledge unit. Frozen.

    This is what ``summon=[wiki.readonly()]`` resolves to: a small reference carrying the
    unit's ``id`` and its **pinned content sha** (``version``), plus the read mode. A
    summon enters a run's identity by this hash — the body is NOT carried here, so two
    runs that summon the same frozen Wiki pin the same sha and replay identically. The
    ``readonly`` flag records that the summon may only read (never write back).
    """

    unit_id: str
    kind: str = "wiki"
    version: str  # the pinned content sha (str(Version)) — identity, not body
    readonly: bool = True

    model_config = {"frozen": True}

    def checksum(self) -> str:
        """The hash a summoner folds into its own identity — the PINNED SHA, not the body."""
        return self.version


class Wiki(Freezable):
    """A versioned, summonable, narrowable knowledge unit. Freezable.

    Typed pages (reusing :class:`ContextEntry`), a content hash, and a
    :class:`~crawfish.versioning.Version`. :meth:`with_page` is **copy-on-write**: it
    returns a *new frozen* Wiki with a distinct sha and leaves the receiver unchanged; a
    tainted page stays tainted across the edit. Mutating a frozen Wiki raises
    :class:`FrozenError` (Freezable). ``readonly()``/``mutable()`` expose the read/edit
    modes; ``mutable()`` is rejected in eval mode (a frozen Wiki).
    """

    id: str = Field(default_factory=new_id)
    org_id: str = "local"
    pages: list[WikiPage] = Field(default_factory=list)

    # -- content identity ---------------------------------------------------
    def content_sha(self) -> str:
        """Deterministic content hash over the pages — a **Merkle over page leaves**.

        The root combines per-page :meth:`WikiPage.page_sha` leaves under a stable key
        ordering, so re-hashing only re-derives changed leaves (the resolved-open item).
        Identity, not body: ``id``/``org_id`` are excluded (a Wiki copied across orgs has
        the same knowledge content). Two structurally-identical Wikis collapse to one sha.
        """
        leaves = sorted((p.title, p.page_sha()) for p in self.pages)
        blob = json.dumps(leaves, sort_keys=True).encode()
        return hashlib.sha256(blob).hexdigest()[:12]

    def freeze(self) -> None:
        """Seal the Wiki at its content hash (the sha CARRIES the content identity)."""
        # Stamp the content sha onto the version *before* sealing, so a frozen Wiki's
        # ``str(version)`` pins its body. (``freeze`` is allowed to write ``version``.)
        object.__setattr__(self.version, "sha", self.content_sha())
        super().freeze()

    def frozen_copy(self) -> Wiki:
        """A frozen copy pinned at the current content sha (the eval-mode artifact)."""
        sealed = self.model_copy(deep=True)
        sealed.freeze()
        return sealed

    # -- copy-on-write edit (train-mode) ------------------------------------
    def with_page(
        self,
        title: str,
        value: JSONValue,
        *,
        value_schema: list[Parameter] | None = None,
        tainted: bool = True,
        trust: TrustTier = TrustTier.UNTRUSTED,
        lineage: str | None = None,
        role: str = "wiki",
    ) -> Wiki:
        """Return a NEW frozen Wiki with ``title`` added/replaced (copy-on-write).

        Never edits in place: the receiver is unchanged and the result is a fresh frozen
        Wiki with a distinct content sha. A page is **tainted by default** (untrusted
        knowledge — the injection boundary); a tainted page stays tainted. Replacing an
        existing title overwrites that page; the rest are preserved.
        """
        page = WikiPage(
            title=title,
            trust=trust,
            entry=ContextEntry(
                key=title,
                role=role,
                value=value,
                value_schema=list(value_schema or []),
                tainted=tainted,
                lineage=lineage,
            ),
        )
        kept = [p for p in self.pages if p.title != title]
        # Build the next unfrozen draft from the receiver's identity, then seal it. We
        # construct fresh (rather than model_copy) so a frozen receiver is never mutated.
        draft = Wiki(id=self.id, org_id=self.org_id, pages=[*kept, page])
        return draft.frozen_copy()

    # -- modes (read / edit) ------------------------------------------------
    def readonly(self) -> SummonRef:
        """Summon this Wiki read-only — a :class:`SummonRef` pinned at its content sha.

        The read-side summon: it pins the body by hash and forbids writing back. A Wiki
        must be frozen (eval mode) to be summoned by a stable reference, so an unfrozen
        Wiki is sealed first (its sha is its content hash, deterministically).
        """
        pinned = self if self.frozen else self.frozen_copy()
        return SummonRef(unit_id=pinned.id, kind="wiki", version=str(pinned.version), readonly=True)

    def mutable(self) -> Wiki:
        """Return a train-mode (unfrozen) edit handle — **rejected in eval mode**.

        Mirrors ``train()`` (CRA-209): a fresh unfrozen copy whose pages may change via
        copy-on-write. A frozen (eval-mode) Wiki cannot be made mutable in place — that
        would defeat the reproducibility guarantee — so this raises :class:`FrozenError`
        on a frozen Wiki (eval mode == frozen).
        """
        if self.frozen:
            raise FrozenError(
                "cannot take a mutable handle on a frozen (eval-mode) Wiki; "
                "knowledge edits are train-mode copy-on-write — start from an unfrozen Wiki"
            )
        return self.model_copy(update={"version": Version()}, deep=True)

    # -- consult: knowledge AS DATA (the security boundary) -----------------
    def page(self, title: str) -> WikiPage | None:
        """Return the page addressed by ``title``, or ``None``."""
        return next((p for p in self.pages if p.title == title), None)

    def consult(self, *, into: Context | None = None) -> Context:
        """Materialise the Wiki's pages as a :class:`Context` — **data, never instructions**.

        Each page enters the Context as a :class:`ContextEntry` that is **tainted
        (fluid)** unless the page itself was authored trusted-and-untainted; tainted
        entries flow through the fluid-data block and can never reach an instruction slot
        or a static-only Sink (SECURITY.md). This is how an agent "consults the Wiki":
        the knowledge arrives as carried context, addressable by page title, never as a
        prompt the agent obeys. Pure: ``(wiki) -> Context``, no model call.
        """
        ctx = into if into is not None else Context()
        for p in self.pages:
            ctx = ctx.add(p.entry)
        return ctx

    # -- summonable identity ------------------------------------------------
    def export(self) -> dict[str, JSONValue]:
        """The summon record: the PINNED SHA, never the body.

        A summoned unit's pinned sha appears in ``export()["checksum"]``; the page bodies
        do NOT (a summon enters identity by hash, so a run records the small reference,
        not the knowledge). Includes the page titles + per-page leaf shas (the Merkle
        leaves) for auditability, but no page value.
        """
        pinned = self if self.frozen else self.frozen_copy()
        leaves = [
            {"title": p.title, "sha": p.page_sha(), "trust": p.trust.value} for p in pinned.pages
        ]
        return {
            "id": pinned.id,
            "kind": "wiki",
            "version": str(pinned.version),
            "checksum": pinned.content_sha(),
            "leaves": leaves,
        }

    # -- persistence (Store seam — secrets scrubbed by the seam) ------------
    def persist(self, store: Store) -> None:
        """Persist this Wiki through the ``Store`` seam (a ScrubbingStore redacts secrets).

        Routes the whole body — including page values — through the Store, so a
        :class:`~crawfish.secrets.ScrubbingStore` redacts any secret before it lands in a
        record (the same routing the Context artifact and the Rag-embedding seam use, so
        no secret is ever stored unredacted). Tenancy-scoped by ``self.org_id``.
        """
        record: dict[str, JSONValue] = {
            "id": self.id,
            "org_id": self.org_id,
            "version": str(self.version),
            "pages": [p.model_dump(mode="json") for p in self.pages],
        }
        store.put_record(WIKI_RECORD_KIND, self.id, record, org_id=self.org_id)

    @classmethod
    def load(cls, store: Store, wiki_id: str, *, org_id: str = "local") -> Wiki | None:
        """Load a persisted Wiki by id for ``org_id``, or ``None`` if absent.

        Tenancy isolation is a security property: a load under org ``"b"`` never returns
        a Wiki persisted under org ``"a"`` (the Store scopes every read by ``org_id``).
        A loaded Wiki is frozen (it is a reproducible, pinned artifact).
        """
        rec = store.get_record(WIKI_RECORD_KIND, wiki_id, org_id=org_id)
        if rec is None:
            return None
        raw_pages = rec.get("pages")
        pages = (
            [WikiPage.model_validate(p) for p in raw_pages] if isinstance(raw_pages, list) else []
        )
        wiki = cls(
            id=str(rec.get("id", wiki_id)),
            org_id=str(rec.get("org_id", org_id)),
            pages=pages,
        )
        return wiki.frozen_copy()


# ---------------------------------------------------------------------------
# Rag — DEFERRED. The seam only; no retrieval/embedding/indexing here.
#
# Rag is retrieval over a content-hashed corpus snapshot. Its **index version** =
# corpus sha + embed-model id + chunker config is the content hash, so retrieval over a
# frozen Rag is replay-deterministic — the same ``(query, version)`` yields the same hits,
# and only re-indexing (a train-mode op) mints a new sha. The corpus snapshot's hash is a
# **Merkle over chunks**, so a re-index only re-hashes changed chunks.
#
# Two properties this seam locks in NOW (so the deferred impl can't regress them):
#   * Embeddings MUST route through the secret-scrubbing seam (``ScrubbingStore``,
#     ``secrets.py``) — no secret may land unredacted in an index.
#   * Retrieved content is FLUID/tainted by default and carries its page's
#     :class:`TrustTier` (gap S6 — stored-injection-via-retrieval), so it reaches the
#     model as data and a low-trust corpus is never silently trusted.
#
# The retrieval implementation (embedding, chunking, the Merkle index, ``retrieve``) is
# the larger half and is a documented follow-on. Calling it now raises ``RagDeferred``.
# ---------------------------------------------------------------------------


class RagDeferred(NotImplementedError):
    """Raised by the deferred :class:`RagSeam` surface — retrieval is a follow-on.

    The seam exists so callers and the summon/trust-tier/scrubbing design are fixed now;
    the embedding + Merkle-index + ``retrieve`` implementation lands later.
    """


@runtime_checkable
class RagSeam(Protocol):
    """The deferred retrieval contract (CRA-227 — ``Rag`` half, NOT implemented).

    A future ``Rag`` is :class:`Freezable` + summonable like :class:`Wiki`. Its identity
    is the **index version** (corpus-sha + embed-model id + chunker config). ``retrieve``
    over a frozen index is a pure ``(query, version) -> hits`` function — not a stochastic
    primitive — so it is replay-deterministic. Implementations MUST: route embeddings
    through the secret-scrubbing seam; return :class:`ContextEntry` hits that are tainted
    by default and carry the source page's :class:`TrustTier`; mint a new sha only on
    re-index. Until then every method raises :class:`RagDeferred`.
    """

    @property
    def version(self) -> Version:
        """The index version (corpus-sha + embed-model id + chunker config)."""
        ...

    def retrieve(self, query: str, *, k: int = 3, org_id: str = "local") -> list[ContextEntry]:
        """Return the top-``k`` tainted hits for ``query`` (DEFERRED — raises RagDeferred)."""
        ...
