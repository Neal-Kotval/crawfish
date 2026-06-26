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

from crawfish.provider import ModelsConfig, ProviderPolicy

__all__ = [
    "ProfileConfig",
    "ProjectPaths",
    "ProjectManifest",
    "BudgetConfig",
    "load_manifest",
    "load_models_config",
    "load_budget",
    "ModelsConfigError",
    "BudgetConfigError",
    "DEFAULT_PROFILES",
]


class BudgetConfigError(ValueError):
    """A malformed ``[budget]`` section in ``crawfish.toml``.

    Raised at config-load time so a project fails fast with a clear message rather than
    threading an invalid ceiling into the run path (CRA-273).
    """


class ModelsConfigError(ValueError):
    """A malformed ``[models]`` section in ``crawfish.toml``.

    Raised at config-load time so a project fails fast with a clear message rather
    than surfacing a confusing resolution result at run time (notably an
    alias→alias chain, which the single-hop :func:`resolve_model` cannot expand).
    """


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


class BudgetConfig(BaseModel):
    """The project-wide cost ceiling (CRA-273) — the ``[budget]`` section of ``crawfish.toml``.

    Today the runtime only has a per-run ``--budget`` flag projecting onto a
    :class:`~crawfish.core.context.CostBudget`; ``[budget] ceiling_usd`` adds a **project-wide**
    ceiling that halts an agent ``--live`` call whose ``worst_case_usd`` exceeds the remaining
    headroom (``craw code estimate`` / ``craw code run``). ``None`` means unbounded — the
    no-config back-compat path (every run is within budget).
    """

    ceiling_usd: float | None = None


class ProjectManifest(BaseModel):
    """Parsed ``crawfish.toml``."""

    name: str = "crawfish-project"
    version: str = "0.1.0"
    default_profile: str = "dev"
    paths: ProjectPaths = Field(default_factory=ProjectPaths)
    profiles: dict[str, ProfileConfig] = Field(default_factory=dict)
    models: ModelsConfig = Field(default_factory=ModelsConfig)
    budget: BudgetConfig = Field(default_factory=BudgetConfig)

    def resolve_profile(self, name: str | None = None) -> ProfileConfig:
        """Resolve a profile by name, falling back to the manifest default and
        then to the built-in dev/prod mapping."""
        chosen = name or self.default_profile
        if chosen in self.profiles:
            return self.profiles[chosen]
        if chosen in DEFAULT_PROFILES:
            return ProfileConfig(runtime=DEFAULT_PROFILES[chosen])
        raise KeyError(f"unknown profile {chosen!r}")


def _models_config_from_raw(raw_models: dict[str, object]) -> ModelsConfig:
    """Build a frozen :class:`ModelsConfig` from a ``[models]`` table.

    Schema (all optional)::

        [models]
        default = "claude-opus-4-8"            # fallback for unpinned agents
        allowed_providers = ["anthropic"]      # → ProviderPolicy.allowed

        [models.aliases]
        fast = "claude-haiku-4-5"              # name → concrete provider:model id

    CRA-184 follow-up: an alias must map to a *concrete* model id, never to another
    alias — :func:`resolve_model` expands a single hop by contract. Such a chain is
    rejected here at load time with a :class:`ModelsConfigError`.
    """
    default = raw_models.get("default")
    if default is not None and not isinstance(default, str):
        raise ModelsConfigError("[models].default must be a string model id")

    raw_aliases = raw_models.get("aliases", {})
    if not isinstance(raw_aliases, dict):
        raise ModelsConfigError("[models.aliases] must be a table of name = model-id")
    aliases: dict[str, str] = {}
    for name, target in raw_aliases.items():
        if not isinstance(target, str):
            raise ModelsConfigError(f"alias {name!r} must map to a string model id")
        aliases[name] = target

    # Reject alias→alias chains: single-hop resolution can't expand them, so a config
    # that looks valid would silently resolve to an alias name, not a concrete model.
    for name, target in aliases.items():
        if target in aliases and target != name:
            raise ModelsConfigError(
                f"alias {name!r} -> {target!r} points at another alias; aliases must map "
                "to a concrete provider:model id (resolve_model expands one hop only)"
            )

    raw_allowed = raw_models.get("allowed_providers")
    if raw_allowed is None:
        policy = ProviderPolicy()
    elif isinstance(raw_allowed, (list, tuple)) and all(isinstance(p, str) for p in raw_allowed):
        policy = ProviderPolicy(allowed=tuple(raw_allowed))
    else:
        raise ModelsConfigError("[models].allowed_providers must be a list of provider names")

    return ModelsConfig(default=default, aliases=aliases, policy=policy)


def load_models_config(project_dir: str | Path = ".") -> ModelsConfig:
    """Load just the ``[models]`` section as a frozen :class:`ModelsConfig`.

    Returns an empty config (no default, no aliases, open policy) when the file or
    section is absent — the no-config back-compat path where the runtime's built-in
    Claude ``DEFAULT_MODEL`` fallback still applies.
    """
    path = Path(project_dir) / "crawfish.toml"
    if not path.exists():
        return ModelsConfig()
    raw = tomllib.loads(path.read_text())
    return _models_config_from_raw(raw.get("models", {}))


def _budget_config_from_raw(raw_budget: dict[str, object]) -> BudgetConfig:
    """Build a :class:`BudgetConfig` from a ``[budget]`` table (CRA-273).

    Schema (all optional)::

        [budget]
        ceiling_usd = 5.00     # halts agent --live calls whose worst_case exceeds remaining

    An absent section is an unbounded budget (``ceiling_usd = None``). A present but malformed
    value (non-numeric / negative) is a :class:`BudgetConfigError` so the project fails fast.
    """
    raw_ceiling = raw_budget.get("ceiling_usd")
    if raw_ceiling is None:
        return BudgetConfig()
    if isinstance(raw_ceiling, bool) or not isinstance(raw_ceiling, (int, float)):
        raise BudgetConfigError("[budget].ceiling_usd must be a number (USD)")
    if raw_ceiling < 0:
        raise BudgetConfigError("[budget].ceiling_usd must be >= 0")
    return BudgetConfig(ceiling_usd=float(raw_ceiling))


def load_budget(project_dir: str | Path = ".") -> BudgetConfig:
    """Load just the ``[budget]`` section as a :class:`BudgetConfig` (CRA-273).

    Returns an unbounded budget (``ceiling_usd = None``) when the file or section is absent —
    the no-config back-compat path where only the per-run ``--budget`` flag applies.
    """
    path = Path(project_dir) / "crawfish.toml"
    if not path.exists():
        return BudgetConfig()
    raw = tomllib.loads(path.read_text())
    return _budget_config_from_raw(raw.get("budget", {}))


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
        models=_models_config_from_raw(raw.get("models", {})),
        budget=_budget_config_from_raw(raw.get("budget", {})),
    )
