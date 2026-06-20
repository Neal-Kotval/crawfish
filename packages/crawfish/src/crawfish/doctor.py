"""``craw doctor`` — project structure health.

Explains where things belong, flags misplaced/ambiguous files, and verifies the
split between **authored** code (the unit folders at the project root) and
**generated** state (``.crawfish/``). Reads the canonical layout, applying any
``crawfish.toml [project.paths]`` overrides so the report matches the real project.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from crawfish.config import ProjectPaths, load_manifest

__all__ = ["DoctorFinding", "DoctorReport", "diagnose", "CANONICAL_LAYOUT", "GENERATED_DIR"]

GENERATED_DIR = ".crawfish"

# The canonical project layout (folder -> what it holds). Authored at the root;
# generated state is isolated under ``.crawfish/``.
CANONICAL_LAYOUT: dict[str, str] = {
    "sources": "Source units — pull data in",
    "sinks": "Sink units — push results out",
    "definitions": "Definition packages — the agent teams",
    "pipelines": "Pipeline wiring — Source → Batch → Sink",
    "observers": "Observer units — watch running pipelines",
    "tools": "Custom tool functions",
    "policies": "Reusable policies",
}


class DoctorFinding(BaseModel):
    """One health observation. ``level`` is ``ok`` | ``info`` | ``warn`` | ``error``."""

    level: str
    message: str


class DoctorReport(BaseModel):
    findings: list[DoctorFinding] = Field(default_factory=list)

    @property
    def ok(self) -> bool:
        """True when nothing rose above ``info``."""
        return not any(f.level in {"warn", "error"} for f in self.findings)

    def add(self, level: str, message: str) -> None:
        self.findings.append(DoctorFinding(level=level, message=message))

    def text(self) -> str:
        glyph = {"ok": "✓", "info": "·", "warn": "!", "error": "✗"}
        lines = [f"  {glyph.get(f.level, '?')} {f.message}" for f in self.findings]
        verdict = "structure healthy" if self.ok else "structure needs attention"
        return "\n".join([*lines, f"\n{verdict}"])


def _looks_like_definition(d: Path) -> bool:
    return (d / "instructions.md").exists() or (d / "definition.py").exists()


def diagnose(project_dir: str | Path = ".") -> DoctorReport:
    """Inspect ``project_dir`` and return a structured structure-health report."""
    root = Path(project_dir)
    report = DoctorReport()

    manifest_path = root / "crawfish.toml"
    if manifest_path.exists():
        report.add("ok", "crawfish.toml present")
        paths = load_manifest(root).paths
    else:
        report.add("info", "no crawfish.toml — using the default layout")
        paths = ProjectPaths()

    path_map = paths.model_dump()
    defaults = ProjectPaths()
    for field, subdir in path_map.items():
        d = root / subdir
        default_sub = getattr(defaults, field)
        relocated = "" if subdir == default_sub else f" (relocated from {default_sub}/)"
        if d.is_dir():
            report.add("ok", f"{field}: {subdir}/{relocated}")
        elif relocated:
            # an explicit override that points nowhere is a real misconfiguration
            report.add("warn", f"{field}: configured {subdir}/ does not exist{relocated}")
        else:
            report.add("info", f"{field}: {subdir}/ not present (optional)")

    # Misplacement: a Definition-shaped directory sitting under a non-definition root.
    for field, subdir in path_map.items():
        if field in {"definitions", "observers"}:
            continue
        d = root / subdir
        if not d.is_dir():
            continue
        for child in sorted(d.iterdir()):
            if child.is_dir() and _looks_like_definition(child):
                report.add(
                    "warn",
                    f"{child} looks like a Definition but sits in {subdir}/ — "
                    f"move it to {paths.definitions}/",
                )

    # Generated-vs-authored separation.
    gen = root / GENERATED_DIR
    if gen.is_dir():
        report.add("ok", f"{GENERATED_DIR}/ holds generated state")
        gitignore = root / ".gitignore"
        ignored = gitignore.exists() and GENERATED_DIR in gitignore.read_text()
        if not ignored:
            report.add("warn", f"{GENERATED_DIR}/ should be gitignored (it is generated state)")
        # authored unit files must not hide inside generated state
        for sub in path_map.values():
            if (gen / sub).exists():
                report.add("error", f"authored {sub}/ found inside {GENERATED_DIR}/ — move it out")

    return report
