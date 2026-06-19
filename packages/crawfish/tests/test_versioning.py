"""CRA-100 acceptance: Version string form + freeze rejects mutation."""

from __future__ import annotations

import pytest

from crawfish.versioning import Freezable, FrozenError, Version


def test_version_str_with_sha() -> None:
    assert str(Version(major=0, minor=1, sha="abc")) == "0.1-abc"


def test_version_str_without_sha() -> None:
    assert str(Version(major=0, minor=2)) == "0.2"


def test_mutating_frozen_version_raises() -> None:
    v = Version(major=0, minor=1)
    v.freeze()
    assert v.frozen
    with pytest.raises(FrozenError):
        v.minor = 2


class _Artifact(Freezable):
    name: str = "x"


def test_freezable_artifact_rejects_mutation() -> None:
    a = _Artifact(name="clarity")
    a.name = "still-mutable"  # ok before freeze
    a.freeze()
    with pytest.raises(FrozenError):
        a.name = "nope"
