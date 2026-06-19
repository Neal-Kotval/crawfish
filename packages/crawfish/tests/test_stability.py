"""Tests for the API stability contract (CRA-124)."""

from __future__ import annotations

import pytest

from crawfish.stability import (
    Stability,
    deprecated,
    experimental,
    is_breaking,
    migration_note,
    stability_of,
    stable,
)


def test_stable_tag_preserves_behavior() -> None:
    @stable
    def add(a: int, b: int) -> int:
        return a + b

    assert add(2, 3) == 5
    assert stability_of(add) is Stability.STABLE


def test_experimental_tag_preserves_behavior() -> None:
    @experimental
    def mul(a: int, b: int) -> int:
        return a * b

    assert mul(2, 3) == 6
    assert stability_of(mul) is Stability.EXPERIMENTAL


def test_stable_decorator_on_class() -> None:
    @stable
    class Widget:
        pass

    assert stability_of(Widget) is Stability.STABLE


def test_untagged_defaults_to_experimental() -> None:
    def plain() -> None:
        return None

    assert stability_of(plain) is Stability.EXPERIMENTAL
    assert stability_of(object()) is Stability.EXPERIMENTAL


def test_deprecated_tag_and_behavior() -> None:
    @deprecated(since="0.4", removed_in="1.0", use="new_fn")
    def old_fn(x: int) -> int:
        return x + 1

    assert stability_of(old_fn) is Stability.DEPRECATED
    assert old_fn.__name__ == "old_fn"

    with pytest.warns(DeprecationWarning, match="new_fn"):
        assert old_fn(41) == 42


def test_deprecated_without_replacement_still_warns() -> None:
    @deprecated(since="0.4", removed_in="1.0")
    def old_fn() -> str:
        return "ok"

    with pytest.warns(DeprecationWarning):
        assert old_fn() == "ok"


def test_is_breaking() -> None:
    assert is_breaking("1.2.0", "2.0.0") is True
    assert is_breaking("1.2.0", "1.3.0") is False
    assert is_breaking("0.4", "0.5") is False
    assert is_breaking("v1.0.0", "v2.0.0") is True


def test_migration_note() -> None:
    assert "breaking" in migration_note("1.2.0", "2.0.0")
    assert "non-breaking" in migration_note("1.2.0", "1.3.0")
