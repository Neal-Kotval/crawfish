"""Module discovery + a self-registering unit registry (CRA-113).

Three feeds, one registry: (a) entry points of installed ``crawfish-*`` packages
(``crawfish.sources`` / ``crawfish.sinks`` / ``crawfish.definitions`` / ``crawfish.types``)
— zero wiring; (b) a directory scan of the local project (``sources/`` / ``sinks/`` /
``definitions/`` / ...), filename → unit name; (c) the registry both feed. Name
collisions are namespaced and resolved **first-wins + warn**.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from importlib.metadata import entry_points
from pathlib import Path

__all__ = ["UnitRef", "Registry", "ENTRY_POINT_GROUPS", "LOCAL_DIRS"]

ENTRY_POINT_GROUPS = {
    "source": "crawfish.sources",
    "sink": "crawfish.sinks",
    "definition": "crawfish.definitions",
    "type": "crawfish.types",
}

# Local project directories scanned for units (filename stem -> unit name).
LOCAL_DIRS = {
    "source": "sources",
    "sink": "sinks",
    "definition": "definitions",
    "tool": "tools",
    "policy": "policies",
}


@dataclass
class UnitRef:
    """A discovered unit: its kind, name, and where it came from."""

    kind: str
    name: str
    origin: str  # "entrypoint:<group>" or "local:<path>"
    target: str  # entry-point value or filesystem path


@dataclass
class Registry:
    """Collects discovered units; first registration of a (kind, name) wins."""

    units: dict[tuple[str, str], UnitRef] = field(default_factory=dict)

    def register(self, ref: UnitRef) -> bool:
        key = (ref.kind, ref.name)
        if key in self.units:
            existing = self.units[key]
            warnings.warn(
                f"name collision for {ref.kind} {ref.name!r}: keeping {existing.origin}, "
                f"ignoring {ref.origin} (first-wins)",
                stacklevel=2,
            )
            return False
        self.units[key] = ref
        return True

    def of_kind(self, kind: str) -> list[UnitRef]:
        return [r for k, r in self.units.items() if k[0] == kind]

    def get(self, kind: str, name: str) -> UnitRef | None:
        return self.units.get((kind, name))

    # -- feeds --------------------------------------------------------------
    def discover_entry_points(self) -> None:
        for kind, group in ENTRY_POINT_GROUPS.items():
            for ep in entry_points(group=group):
                self.register(
                    UnitRef(kind=kind, name=ep.name, origin=f"entrypoint:{group}", target=ep.value)
                )

    def discover_local(self, project_dir: str | Path) -> None:
        root = Path(project_dir)
        for kind, subdir in LOCAL_DIRS.items():
            d = root / subdir
            if not d.is_dir():
                continue
            if kind == "definition":
                # a definition is a directory (has instructions.md or definition.py)
                for child in sorted(d.iterdir()):
                    if child.is_dir() and (
                        (child / "instructions.md").exists() or (child / "definition.py").exists()
                    ):
                        self.register(UnitRef(kind, child.name, f"local:{child}", str(child)))
            else:
                for f in sorted(d.glob("*.py")):
                    if f.stem.startswith("_"):
                        continue
                    self.register(UnitRef(kind, f.stem, f"local:{f}", str(f)))

    @classmethod
    def discover(cls, project_dir: str | Path = ".") -> Registry:
        reg = cls()
        reg.discover_entry_points()  # installed packages first (they win ties)
        reg.discover_local(project_dir)
        return reg
