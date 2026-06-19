"""Generate ``api-reference.md`` from ``crawfish.__all__``.

This walks the *public* surface (only what ``crawfish/__init__.py`` re-exports) and
emits, for each symbol, its kind, signature, and docstring. Auto-generated beats a
hand-written reference that drifts: re-run on every release.

Usage::

    uv run python docs/guide/gen_api_reference.py > docs/guide/api-reference.md
"""

from __future__ import annotations

import inspect
import re
from collections.abc import Callable
from enum import Enum
from typing import Any

import crawfish

# Inherited docstrings (e.g. Pydantic's BaseModel) carry relative markdown links to
# *their* docs; flatten any non-HTTP link to plain text so the site builds --strict.
_REL_LINK = re.compile(r"\[([^\]]+)\]\((?!https?://)[^)]+\)")


def _strip_links(text: str) -> str:
    return _REL_LINK.sub(r"\1", text)


def _first_line(text: str | None) -> str:
    if not text:
        return ""
    for line in text.strip().splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return ""


def _signature(obj: Callable[..., Any]) -> str:
    try:
        return str(inspect.signature(obj))
    except (TypeError, ValueError):
        return "(...)"


def _kind(obj: object) -> str:
    if inspect.isclass(obj):
        if issubclass(obj, Enum):
            return "enum"
        return "class"
    if inspect.isfunction(obj) or inspect.isbuiltin(obj):
        return "function"
    return "value"


def _render_class(name: str, obj: type) -> list[str]:
    lines: list[str] = [f"### `{name}`", ""]
    bases = [b.__name__ for b in obj.__bases__ if b is not object]
    if bases:
        lines.append(f"*class* — bases: {', '.join(f'`{b}`' for b in bases)}")
    else:
        lines.append("*class*")
    lines.append("")
    doc = inspect.getdoc(obj)
    if doc:
        lines.extend([doc, ""])

    if issubclass(obj, Enum):
        members = ", ".join(f"`{m.name}` = `{m.value!r}`" for m in obj)
        lines.extend([f"Members: {members}", ""])
        return lines

    # __init__ signature (skip the pydantic/object default)
    init = obj.__dict__.get("__init__")
    if callable(init):
        lines.extend([f"```python\n{name}{_signature(obj)}\n```", ""])

    # public methods declared on the class
    methods = [
        (n, m)
        for n, m in inspect.getmembers(obj, predicate=inspect.isfunction)
        if not n.startswith("_") and n in obj.__dict__
    ]
    if methods:
        lines.append("**Methods**")
        lines.append("")
        for mname, meth in sorted(methods):
            summary = _first_line(inspect.getdoc(meth))
            suffix = f" — {summary}" if summary else ""
            lines.append(f"- `{mname}{_signature(meth)}`{suffix}")
        lines.append("")
    return lines


def _render_callable(name: str, obj: Callable[..., Any]) -> list[str]:
    lines = [f"### `{name}`", "", "*function*", "", f"```python\n{name}{_signature(obj)}\n```", ""]
    doc = inspect.getdoc(obj)
    if doc:
        lines.extend([doc, ""])
    return lines


def _render_value(name: str, obj: object) -> list[str]:
    return [f"### `{name}`", "", f"*value* — `{type(obj).__name__}`", "", f"`{name} = {obj!r}`", ""]


def main() -> None:
    names = [n for n in crawfish.__all__ if n != "__version__"]

    out: list[str] = [
        "# API reference",
        "",
        "> Auto-generated from `crawfish.__all__` by `docs/guide/gen_api_reference.py`.",
        "> Do not edit by hand — regenerate on each release:",
        "> `uv run python docs/guide/gen_api_reference.py > docs/guide/api-reference.md`.",
        "",
        f"`crawfish` version: `{crawfish.__version__}` — {len(names)} public symbols.",
        "",
        "Everything documented here is importable directly from the top-level package:",
        "",
        "```python",
        "from crawfish import Definition, Batch, MockRuntime  # etc.",
        "```",
        "",
        "## Symbols",
        "",
    ]

    # index
    out.append("| Symbol | Kind | Summary |")
    out.append("| --- | --- | --- |")
    for name in names:
        obj = getattr(crawfish, name)
        summary = _first_line(inspect.getdoc(obj)).replace("|", "\\|")
        out.append(f"| [`{name}`](#{name.lower()}) | {_kind(obj)} | {summary} |")
    out.append("")

    for name in names:
        obj = getattr(crawfish, name)
        if inspect.isclass(obj):
            out.extend(_render_class(name, obj))
        elif callable(obj):
            out.extend(_render_callable(name, obj))
        else:
            out.extend(_render_value(name, obj))

    print(_strip_links("\n".join(out)))


if __name__ == "__main__":
    main()
