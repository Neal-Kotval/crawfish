"""CRA-256 — the authoring spec is the single source of truth.

The file-by-file authoring playbook (``docs/specs/craw-code/authoring/``) is what both the
plugin skills (CRA-258..264) and the validation eval (CRA-265) derive from. These tests pin
its structure so teaching and checking can never drift:

* every Definition file kind from ``docs/reference/definition.md`` has a spec section;
* the machine-checkable form (``authoring-spec.toml``) is loadable and internally consistent
  (every ``[[file]]`` points at a real section, names a spine tag that exists, and the spine
  tags it requires actually appear inline in that section's prose);
* the structured ``golden`` path exists and is the project the golden tests load.

Pure filesystem + TOML reads — no model call, no compile.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[3]
_SPEC_DIR = _REPO / "docs" / "specs" / "craw-code" / "authoring"
_SPEC_TOML = _SPEC_DIR / "authoring-spec.toml"


def _load_spec() -> dict:
    return tomllib.loads(_SPEC_TOML.read_text())


def test_spec_dir_and_index_exist() -> None:
    """The authoring spec has a README index and a machine-checkable TOML form."""
    assert (_SPEC_DIR / "README.md").is_file()
    assert _SPEC_TOML.is_file()


def test_structured_form_loads() -> None:
    """``authoring-spec.toml`` parses and carries the expected top-level keys."""
    spec = _load_spec()
    assert spec["version"] == 1
    assert spec["golden"] == "demo/craw-code-golden"
    assert spec["file"], "expected at least one [[file]] entry"
    assert spec["spine"], "expected the [spine.*] rule table"


def test_every_definition_file_kind_has_a_section() -> None:
    """Each file kind the compile contract names is covered by a spec section.

    The kinds are the import-bearing + asset-bearing surfaces ``load_definition`` walks
    (``docs/reference/definition.md``): definition.py, instructions.md, agents/*.md,
    tools/*.py, mcp/*.py, policies/*.py, skills/*.md, plus knowledge and fixtures.
    """
    spec = _load_spec()
    covered = {entry["kind"] for entry in spec["file"]}
    required = {
        "definition.py",
        "instructions.md",
        "agents/*.md",
        "tools/*.py",
        "mcp/*.py",
        "policies/*.py",
        "skills/*.md",
        "knowledge",
        "fixtures",
    }
    missing = required - covered
    assert not missing, f"authoring spec is missing a section for: {sorted(missing)}"


def test_each_file_entry_points_at_a_real_section() -> None:
    """Every ``[[file]]`` names a section markdown file that exists on disk."""
    spec = _load_spec()
    for entry in spec["file"]:
        section = _SPEC_DIR / entry["section"]
        assert section.is_file(), f"{entry['kind']} → missing section {entry['section']}"


def test_required_spine_tags_exist_and_appear_inline() -> None:
    """The drift guard: a section that requires a spine rule states its phrase inline.

    This is what keeps the teaching surface from drifting away from the enforcement: if a
    file kind can touch a sink/secret/fluid value, its prose section must repeat the rule.
    """
    spec = _load_spec()
    spine = spec["spine"]
    for entry in spec["file"]:
        body = (_SPEC_DIR / entry["section"]).read_text().lower()
        for tag in entry.get("requires_spine", []):
            assert tag in spine, f"{entry['kind']} requires unknown spine tag {tag!r}"
            phrase = spine[tag]["phrase"].lower()
            assert phrase in body, (
                f"section {entry['section']} must state the {tag!r} spine rule inline "
                f"(phrase {phrase!r} not found)"
            )


def test_golden_path_exists() -> None:
    """The structured ``golden`` path is a real project directory the eval/tests load."""
    spec = _load_spec()
    golden = _REPO / spec["golden"]
    assert golden.is_dir(), f"golden project {spec['golden']} not found"
    assert (golden / "definition.py").is_file()


def test_readme_references_each_section() -> None:
    """The README index links every per-file section (no orphan section)."""
    readme = (_SPEC_DIR / "README.md").read_text()
    spec = _load_spec()
    for entry in spec["file"]:
        assert entry["section"] in readme, f"README does not link {entry['section']}"


@pytest.mark.parametrize(
    "tag",
    [
        "fluid-is-data",
        "consequential-static-only",
        "secrets-by-reference",
        "taint-propagates",
        "jailed-compile",
        "consent-regate",
        "knowledge-is-tainted",
        "pinned-by-hash",
        "determinism-mock-default",
    ],
)
def test_spine_table_is_complete(tag: str) -> None:
    """Every spine rule the sections reference is defined with a phrase + a rule string."""
    spine = _load_spec()["spine"]
    assert tag in spine
    assert spine[tag]["phrase"]
    assert spine[tag]["rule"]
