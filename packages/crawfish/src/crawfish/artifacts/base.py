"""The ``ArtifactStore`` seam — blob/file Outputs by reference.

Large payloads (files, blobs, big JSON) don't belong inline in an ``Output``.
Instead an Output carries a small, content-addressed :class:`ArtifactRef` (a dict
on ``Output.value``) and the bytes live in an :class:`ArtifactStore`. The product
model imports the *protocol*, never a concrete backend, so local-disk → S3/GCS is
a driver swap (mirrors the ``Store`` seam, ADR 0001/0003). Every operation carries
an ``org_id`` tenancy key (defaulted ``"local"``) so cloud multi-tenancy is a
driver swap, not a schema migration.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel

__all__ = ["ArtifactRef", "ArtifactStore"]


class ArtifactRef(BaseModel):
    """A content-addressed pointer to artifact bytes held in an ``ArtifactStore``.

    This is what an ``Output`` carries instead of inline bytes. ``uri`` and
    ``sha256`` both derive from the content hash, so identical content dedupes.
    """

    uri: str
    sha256: str
    size: int
    content_type: str = "application/octet-stream"


@runtime_checkable
class ArtifactStore(Protocol):
    """Blob persistence contract: content-addressed, tenant-scoped, GC-able."""

    def put(
        self,
        data: bytes,
        *,
        content_type: str = "application/octet-stream",
        org_id: str = "local",
    ) -> ArtifactRef:
        """Store ``data`` and return a content-addressed :class:`ArtifactRef`."""
        ...

    def get(self, ref: ArtifactRef, *, org_id: str = "local") -> bytes:
        """Return the bytes for ``ref``. Raises if absent for this ``org_id``."""
        ...

    def exists(self, ref: ArtifactRef, *, org_id: str = "local") -> bool:
        """True iff ``ref``'s content is stored under this ``org_id``."""
        ...

    def delete(self, ref: ArtifactRef, *, org_id: str = "local") -> None:
        """Delete ``ref``'s content for this ``org_id`` (no-op if absent)."""
        ...

    def gc(self, live_refs: set[str], *, org_id: str = "local") -> int:
        """Delete artifacts whose sha256 is not in ``live_refs``; return count."""
        ...
