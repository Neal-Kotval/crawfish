"""Tests for the artifact store seam (CRA-137)."""

from __future__ import annotations

import hashlib
from pathlib import Path

from crawfish.artifacts import (
    ArtifactRef,
    ArtifactStore,
    LocalArtifactStore,
    offload_if_large,
)


def test_large_blob_round_trips(tmp_path: Path) -> None:
    store = LocalArtifactStore(tmp_path)
    blob = b"\xde\xad\xbe\xef" * (5 * 1024 * 1024 // 4)  # 5 MiB
    ref = store.put(blob)
    assert ref.size == len(blob)
    assert ref.sha256 == hashlib.sha256(blob).hexdigest()
    assert store.get(ref) == blob


def test_content_addressing_dedupes(tmp_path: Path) -> None:
    store = LocalArtifactStore(tmp_path)
    data = b"identical content"
    ref1 = store.put(data)
    ref2 = store.put(data)
    assert ref1.sha256 == ref2.sha256
    assert ref1.uri == ref2.uri


def test_offload_large_json(tmp_path: Path) -> None:
    store = LocalArtifactStore(tmp_path)
    big = {"items": ["x" * 100 for _ in range(2000)]}
    result = offload_if_large(big, store, threshold=1024)
    assert isinstance(result, ArtifactRef)
    assert result.content_type == "application/json"
    assert store.exists(result)


def test_offload_small_json_passes_through(tmp_path: Path) -> None:
    store = LocalArtifactStore(tmp_path)
    small = {"hello": "world"}
    result = offload_if_large(small, store, threshold=1024)
    assert result == small
    assert not isinstance(result, ArtifactRef)


def test_tenancy_isolation(tmp_path: Path) -> None:
    store = LocalArtifactStore(tmp_path)
    ref = store.put(b"secret", org_id="acme")
    assert store.exists(ref, org_id="acme")
    assert not store.exists(ref)  # default org cannot see acme's artifact
    assert not store.exists(ref, org_id="local")


def test_gc_removes_unreferenced(tmp_path: Path) -> None:
    store = LocalArtifactStore(tmp_path)
    keep = store.put(b"keep me")
    drop = store.put(b"drop me")
    removed = store.gc({keep.sha256})
    assert removed == 1
    assert store.exists(keep)
    assert not store.exists(drop)


def test_runtime_checkable_protocol(tmp_path: Path) -> None:
    assert isinstance(LocalArtifactStore(tmp_path), ArtifactStore)
