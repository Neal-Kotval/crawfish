"""Project manifest + profile resolution.

A Crawfish project is self-contained: ``crawfish.toml`` is the manifest, ``.env``
holds secrets (gitignored, never logged), and ``.crawfish/`` is generated state.
Profiles select the runtime: ``dev`` → CommandRuntime (``claude -p``, zero key),
``prod`` → ManagedRuntime (CMA). This module resolves *which* profile and
*which* runtime name is requested.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

from pydantic import BaseModel, Field

__all__ = [
    "ProfileConfig",
    "ProjectPaths",
    "ProjectManifest",
    "load_manifest",
    "DEFAULT_PROFILES",
]

# Built-in profile → runtime mapping. Projects may override in crawfish.toml.
DEFAULT_PROFILES: dict[str, str] = {
    "dev": "command",  # CommandRuntime: `claude -p`, zero API key
    "prod": "managed",  # ManagedRuntime: CMA
}


class ProfileConfig(BaseModel):
    """One named profile: which runtime backend, plus free-form settings."""

    runtime: str = "command"
    settings: dict[str, object] = Field(default_factory=dict)


class ProjectPaths(BaseModel):
    """Where each kind of unit lives, relative to the project root.

    Defaults are the canonical layout; a project may relocate any folder via
    ``crawfish.toml [project.paths]`` and discovery follows the override.
    """

    sources: str = "sources"
    sinks: str = "sinks"
    definitions: str = "definitions"
    pipelines: str = "pipelines"
    observers: str = "observers"
    tools: str = "tools"
    policies: str = "policies"

    def as_discovery_map(self) -> dict[str, str]:
        """``{unit-kind: subdir}`` for the registry's local folder scan."""
        return {
            "source": self.sources,
            "sink": self.sinks,
            "definition": self.definitions,
            "observer": self.observers,
            "tool": self.tools,
            "policy": self.policies,
        }


class ProjectManifest(BaseModel):
    """Parsed ``crawfish.toml``."""

    name: str = "crawfish-project"
    version: str = "0.1.0"
    default_profile: str = "dev"
    paths: ProjectPaths = Field(default_factory=ProjectPaths)
    profiles: dict[str, ProfileConfig] = Field(default_factory=dict)

    def resolve_profile(self, name: str | None = None) -> ProfileConfig:
        """Resolve a profile by name, falling back to the manifest default and
        then to the built-in dev/prod mapping."""
        chosen = name or self.default_profile
        if chosen in self.profiles:
            return self.profiles[chosen]
        if chosen in DEFAULT_PROFILES:
            return ProfileConfig(runtime=DEFAULT_PROFILES[chosen])
        raise KeyError(f"unknown profile {chosen!r}")


def load_manifest(project_dir: str | Path = ".") -> ProjectManifest:
    """Load ``crawfish.toml`` from ``project_dir``; return defaults if absent."""
    path = Path(project_dir) / "crawfish.toml"
    if not path.exists():
        return ProjectManifest()
    raw = tomllib.loads(path.read_text())
    project = raw.get("project", {})
    profiles = {
        name: ProfileConfig.model_validate(cfg) for name, cfg in raw.get("profiles", {}).items()
    }
    return ProjectManifest(
        name=project.get("name", "crawfish-project"),
        version=project.get("version", "0.1.0"),
        default_profile=project.get("default_profile", "dev"),
        paths=ProjectPaths.model_validate(project.get("paths", {})),
        profiles=profiles,
    )
