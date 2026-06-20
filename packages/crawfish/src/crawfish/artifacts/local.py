"""Local-filesystem reference implementation of the ``ArtifactStore`` seam.

Content-addressed storage under ``root/<org_id>/<sha[:2]>/<sha>``: identical bytes
dedupe to one file, and each ``org_id`` gets a separate subtree (tenancy is a path
prefix, not a schema change — mirrors the SQLite ``Store`` impl, ADR 0001/0003).
All filesystem layout lives here; call sites use the protocol.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from crawfish.artifacts.base import ArtifactRef, ArtifactStore
from crawfish.core.types import JSONValue

__all__ = ["LocalArtifactStore", "offload_if_large"]


class LocalArtifactStore:
    """An ``ArtifactStore`` backed by the local filesystem, addressed by sha256."""

    def __init__(self, root: str | Path) -> None:
        self._root = Path(root)
        self._root.mkdir(parents=True, exist_ok=True)

    def _path(self, sha256: str, org_id: str) -> Path:
        return self._root / org_id / sha256[:2] / sha256

    def put(
        self,
        data: bytes,
        *,
        content_type: str = "application/octet-stream",
        org_id: str = "local",
    ) -> ArtifactRef:
        sha256 = hashlib.sha256(data).hexdigest()
        dest = self._path(sha256, org_id)
        if not dest.exists():
            dest.parent.mkdir(parents=True, exist_ok=True)
            # Atomic write: stage to a temp file, then rename into place.
            tmp = dest.with_name(dest.name + ".tmp")
            tmp.write_bytes(data)
            tmp.replace(dest)
        return ArtifactRef(
            uri=dest.as_uri(),
            sha256=sha256,
            size=len(data),
            content_type=content_type,
        )

    def get(self, ref: ArtifactRef, *, org_id: str = "local") -> bytes:
        return self._path(ref.sha256, org_id).read_bytes()

    def exists(self, ref: ArtifactRef, *, org_id: str = "local") -> bool:
        return self._path(ref.sha256, org_id).is_file()

    def delete(self, ref: ArtifactRef, *, org_id: str = "local") -> None:
        self._path(ref.sha256, org_id).unlink(missing_ok=True)

    def gc(self, live_refs: set[str], *, org_id: str = "local") -> int:
        base = self._root / org_id
        if not base.is_dir():
            return 0
        removed = 0
        for shard in base.iterdir():
            if not shard.is_dir():
                continue
            for blob in shard.iterdir():
                if blob.is_file() and blob.name not in live_refs:
                    blob.unlink()
                    removed += 1
        return removed


def offload_if_large(
    value: JSONValue,
    store: ArtifactStore,
    *,
    threshold: int = 65536,
    org_id: str = "local",
) -> JSONValue | ArtifactRef:
    """Offload ``value`` to ``store`` if its JSON form exceeds ``threshold`` bytes.

    Returns an :class:`ArtifactRef` (content_type ``application/json``) when the
    serialized value is larger than ``threshold``; otherwise returns ``value``
    unchanged. This is how an Output keeps large payloads out of the record.
    """
    data = json.dumps(value).encode("utf-8")
    if len(data) <= threshold:
        return value
    return store.put(data, content_type="application/json", org_id=org_id)
