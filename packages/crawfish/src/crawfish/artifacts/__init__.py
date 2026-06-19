"""Artifact store — blob/file Outputs carried by reference (CRA-137).

Public surface: the :class:`ArtifactRef` envelope, the :class:`ArtifactStore`
protocol seam, the local-disk reference impl, and the ``offload_if_large`` helper.
"""

from __future__ import annotations

from crawfish.artifacts.base import ArtifactRef, ArtifactStore
from crawfish.artifacts.local import LocalArtifactStore, offload_if_large

__all__ = ["ArtifactRef", "ArtifactStore", "LocalArtifactStore", "offload_if_large"]
