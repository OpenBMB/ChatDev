"""Agent skill configuration models."""

from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Dict, List, Mapping

import yaml

from entity.configs.base import (
    BaseConfig,
    ConfigError,
    ConfigFieldSpec,
    EnumOption,
    optional_bool,
    extend_path,
    require_mapping,
)


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_SKILLS_ROOT = (REPO_ROOT / ".agents" / "skills").resolve()
def _discover_default_skills() -> List[tuple[str, str]]:
    if not DEFAULT_SKILLS_ROOT.exists() or not DEFAULT_SKILLS_ROOT.is_dir():
        return []

    discovered: List[tuple[str, str]] = []
    for candidate in sorted(DEFAULT_SKILLS_ROOT.iterdir()):
        if not candidate.is_dir():
            continue
        skill_file = candidate / "SKILL.md"
        if not skill_file.is_file():
            continue
        try:
            frontmatter = _parse_frontmatter(skill_file)
        except Exception:
            continue
        raw_name = frontmatter.get("name")
        raw_description = frontmatter.get("description")
        if not isinstance(raw_name, str) or not raw_name.strip():
            continue
        if not isinstance(raw_description, str) or not raw_description.strip():
            continue
        discovered.append((raw_name.strip(), raw_description.strip()))
    return discovered


def _parse_frontmatter(skill_file: Path) -> Mapping[str, object]:
    text = skill_file.read_text(encoding="utf-8")
    if not text.startswith("---"):
        raise ValueError("missing frontmatter")
    lines = text.splitlines()
    end_idx = None
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            end_idx = idx
            break
    if end_idx is None:
        raise ValueError("missing closing delimiter")
    payload = "\n".join(lines[1:end_idx])
    data = yaml.safe_load(payload) or {}
    if not isinstance(data, Mapping):
        raise ValueError("frontmatter must be a mapping")
    return data


@dataclass
class AgentSkillSelectionConfig(BaseConfig):
    name: str

    FIELD_SPECS = {
        "name": ConfigFieldSpec(
            name="name",
            display_name="Skill Name",
            type_hint="str",
            required=True,
            description="Discovered skill name from the default repo-level skills directory.",
        ),
    }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any], *, path: str) -> "AgentSkillSelectionConfig":
        mapping = require_mapping(data, path)
        name = mapping.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ConfigError("skill name is required", extend_path(path, "name"))
        return cls(name=name.strip(), path=path)

    @classmethod
    def field_specs(cls) -> Dict[str, ConfigFieldSpec]:
        specs = super().field_specs()
        name_spec = specs.get("name")
        if name_spec is None:
            return specs

        discovered = _discover_default_skills()
        enum_values = [name for name, _ in discovered] or None
        enum_options = [
            EnumOption(value=name, label=name, description=description)
            for name, description in discovered
        ] or None
        description = name_spec.description or "Skill name"
        if not discovered:
            description = (
                f"{description} (no skills found in {DEFAULT_SKILLS_ROOT})"
            )
        else:
            description = (
                f"{description} Picker options come from {DEFAULT_SKILLS_ROOT}."
            )
        specs["name"] = replace(
            name_spec,
            enum=enum_values,
            enum_options=enum_options,
            description=description,
        )
        return specs


@dataclass
class AgentSkillsConfig(BaseConfig):
    enabled: bool = False
    allow: List[str] = field(default_factory=list)

    FIELD_SPECS = {
        "enabled": ConfigFieldSpec(
            name="enabled",
            display_name="Enable Skills",
            type_hint="bool",
            required=False,
            default=False,
            description="Enable Agent Skills discovery and the built-in skill tools for this agent.",
            advance=True,
        ),
        "allow": ConfigFieldSpec(
            name="allow",
            display_name="Allowed Skills",
            type_hint="list[AgentSkillSelectionConfig]",
            required=False,
            description="Optional allowlist of discovered skill names. Leave empty to expose every discovered skill.",
            child=AgentSkillSelectionConfig,
            advance=True,
        ),
    }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any], *, path: str) -> "AgentSkillsConfig":
        mapping = require_mapping(data, path)
        enabled = optional_bool(mapping, "enabled", path, default=False)
        if enabled is None:
            enabled = False

        allow = cls._coerce_allow_entries(mapping.get("allow"), field_path=extend_path(path, "allow"))

        return cls(enabled=enabled, allow=allow, path=path)

    @staticmethod
    def _coerce_allow_entries(value: Any, *, field_path: str) -> List[str]:
        if value is None:
            return []
        if not isinstance(value, list):
            raise ConfigError("expected list of skill entries", field_path)

        result: List[str] = []
        for idx, item in enumerate(value):
            item_path = f"{field_path}[{idx}]"
            if isinstance(item, str):
                normalized = item.strip()
                if normalized:
                    result.append(normalized)
                continue
            if isinstance(item, Mapping):
                entry = AgentSkillSelectionConfig.from_dict(item, path=item_path)
                result.append(entry.name)
                continue
            raise ConfigError("expected skill entry mapping or string", item_path)
        return result
