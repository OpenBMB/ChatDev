"""Agent Skills discovery and loading helpers."""

from dataclasses import dataclass
from html import escape
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Mapping, Sequence

import yaml

from entity.tool_spec import ToolSpec


REPO_ROOT = Path(__file__).resolve().parents[4]
WORKSPACE_SKILLS_ROOT = (REPO_ROOT / "skills").resolve()
BUNDLED_SKILLS_ROOT = (REPO_ROOT / ".agents" / "skills").resolve()
DEFAULT_SKILLS_ROOTS = (
    WORKSPACE_SKILLS_ROOT,
    BUNDLED_SKILLS_ROOT,
)
MAX_SKILL_FILE_BYTES = 128 * 1024


class SkillValidationError(ValueError):
    """Raised when a skill directory or SKILL.md file is invalid."""


@dataclass(frozen=True)
class SkillMetadata:
    name: str
    description: str
    skill_dir: Path
    skill_file: Path
    frontmatter: Mapping[str, object]
    allowed_tools: tuple[str, ...]
    compatibility: Mapping[str, object]


def parse_skill_file(skill_file: str | Path) -> SkillMetadata:
    path = Path(skill_file).resolve()
    text = path.read_text(encoding="utf-8")
    frontmatter = _parse_frontmatter(text, path)

    raw_name = frontmatter.get("name")
    raw_description = frontmatter.get("description")
    if not isinstance(raw_name, str) or not raw_name.strip():
        raise SkillValidationError(f"{path}: skill frontmatter must define a non-empty name")
    if not isinstance(raw_description, str) or not raw_description.strip():
        raise SkillValidationError(f"{path}: skill frontmatter must define a non-empty description")

    name = raw_name.strip()
    description = raw_description.strip()
    if path.parent.name != name:
        raise SkillValidationError(
            f"{path}: skill name '{name}' must match directory name '{path.parent.name}'"
        )

    allowed_tools = _parse_optional_str_list(frontmatter.get("allowed-tools"), path, "allowed-tools")
    compatibility = _parse_optional_mapping(frontmatter.get("compatibility"), path, "compatibility")

    return SkillMetadata(
        name=name,
        description=description,
        skill_dir=path.parent,
        skill_file=path,
        frontmatter=dict(frontmatter),
        allowed_tools=tuple(allowed_tools),
        compatibility=dict(compatibility),
    )


def _parse_frontmatter(text: str, path: Path) -> Mapping[str, object]:
    if not text.startswith("---"):
        raise SkillValidationError(f"{path}: SKILL.md must start with YAML frontmatter")

    lines = text.splitlines()
    end_idx = None
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            end_idx = idx
            break
    if end_idx is None:
        raise SkillValidationError(f"{path}: closing frontmatter delimiter not found")

    payload = "\n".join(lines[1:end_idx])
    try:
        data = yaml.safe_load(payload) or {}
    except yaml.YAMLError as exc:
        raise SkillValidationError(f"{path}: invalid YAML frontmatter: {exc}") from exc
    if not isinstance(data, Mapping):
        raise SkillValidationError(f"{path}: skill frontmatter must be a mapping")
    return data


def _parse_optional_str_list(value: object, path: Path, field_name: str) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [item for item in value.split() if item]
    if not isinstance(value, list):
        raise SkillValidationError(f"{path}: {field_name} must be a list of strings")

    result: List[str] = []
    for idx, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            raise SkillValidationError(f"{path}: {field_name}[{idx}] must be a non-empty string")
        result.append(item.strip())
    return result


def _parse_optional_mapping(value: object, path: Path, field_name: str) -> Mapping[str, object]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise SkillValidationError(f"{path}: {field_name} must be a mapping")
    return {str(key): value[key] for key in value}


class AgentSkillManager:
    """Discover and read Agent Skills from the fixed project-level skills directory."""

    def __init__(
        self,
        allow: Sequence[str] | None = None,
        available_tool_names: Sequence[str] | None = None,
        warning_reporter: Callable[[str], None] | None = None,
    ) -> None:
        self.roots = DEFAULT_SKILLS_ROOTS
        self.allow = {item.strip() for item in (allow or []) if item and item.strip()}
        self.available_tool_names = {item.strip() for item in (available_tool_names or []) if item and item.strip()}
        self.warning_reporter = warning_reporter
        self._skills_by_name: Dict[str, SkillMetadata] | None = None
        self._skill_content_cache: Dict[str, str] = {}
        self._activation_state: Dict[str, bool] = {}
        self._current_skill_name: str | None = None
        self._discovery_warnings: List[str] = []

    def discover(self) -> List[SkillMetadata]:
        if self._skills_by_name is None:
            discovered: Dict[str, SkillMetadata] = {}
            for root in self.roots:
                if not root.exists() or not root.is_dir():
                    continue
                for metadata in self._iter_root_skills(root):
                    if self.allow and metadata.name not in self.allow:
                        continue
                    if not self._is_skill_compatible(metadata):
                        continue
                    discovered.setdefault(metadata.name, metadata)
            self._skills_by_name = discovered
        return list(self._skills_by_name.values())

    def has_skills(self) -> bool:
        return bool(self.discover())

    def build_available_skills_xml(self) -> str:
        skills = self.discover()
        if not skills:
            return ""

        lines = ["<available_skills>"]
        for skill in skills:
            lines.extend(
                [
                    "  <skill>",
                    f"    <name>{escape(skill.name)}</name>",
                    f"    <description>{escape(skill.description)}</description>",
                    f"    <location>{escape(str(skill.skill_file))}</location>",
                ]
            )
            if skill.allowed_tools:
                lines.append("    <allowed_tools>")
                for tool_name in skill.allowed_tools:
                    lines.append(f"      <tool>{escape(tool_name)}</tool>")
                lines.append("    </allowed_tools>")
            lines.append("  </skill>")
        lines.append("</available_skills>")
        return "\n".join(lines)

    def activate_skill(self, skill_name: str) -> Dict[str, str | List[str]]:
        skill = self._get_skill(skill_name)
        cached = self._skill_content_cache.get(skill.name)
        if cached is None:
            cached = skill.skill_file.read_text(encoding="utf-8")
            self._skill_content_cache[skill.name] = cached
        self._activation_state[skill.name] = True
        self._current_skill_name = skill.name
        return {
            "skill_name": skill.name,
            "path": str(skill.skill_file),
            "instructions": cached,
            "allowed_tools": list(skill.allowed_tools),
        }

    def read_skill_file(self, skill_name: str, relative_path: str) -> Dict[str, str]:
        skill = self._get_skill(skill_name)
        if not self.is_activated(skill.name):
            raise ValueError(f"Skill '{skill.name}' must be activated before reading files")

        normalized = relative_path.strip()
        if not normalized:
            raise ValueError("relative_path is required")

        candidate = (skill.skill_dir / normalized).resolve()
        try:
            candidate.relative_to(skill.skill_dir)
        except ValueError as exc:
            raise ValueError("relative_path must stay within the skill directory") from exc

        if not candidate.exists() or not candidate.is_file():
            raise ValueError(f"Skill file '{normalized}' not found")
        if candidate.stat().st_size > MAX_SKILL_FILE_BYTES:
            raise ValueError(f"Skill file '{normalized}' exceeds the {MAX_SKILL_FILE_BYTES} byte limit")

        return {
            "skill_name": skill.name,
            "path": str(candidate),
            "relative_path": str(candidate.relative_to(skill.skill_dir)),
            "content": candidate.read_text(encoding="utf-8"),
        }

    def is_activated(self, skill_name: str) -> bool:
        return bool(self._activation_state.get(skill_name))

    def active_skill(self) -> SkillMetadata | None:
        if self._current_skill_name is None:
            return None
        skills = self._skills_by_name
        if skills is None:
            return None
        return skills.get(self._current_skill_name)

    def discovery_warnings(self) -> List[str]:
        self.discover()
        return list(self._discovery_warnings)

    def build_tool_specs(self) -> List[ToolSpec]:
        if not self.has_skills():
            return []
        return [
            ToolSpec(
                name="activate_skill",
                description="Load the full SKILL.md instructions for a discovered agent skill.",
                parameters={
                    "type": "object",
                    "properties": {
                        "skill_name": {
                            "type": "string",
                            "description": "Exact skill name from <available_skills>.",
                        }
                    },
                    "required": ["skill_name"],
                },
                metadata={"source": "agent_skill_internal"},
            ),
            ToolSpec(
                name="read_skill_file",
                description="Read a text file inside an activated skill directory, such as references or scripts.",
                parameters={
                    "type": "object",
                    "properties": {
                        "skill_name": {
                            "type": "string",
                            "description": "Exact activated skill name from <available_skills>.",
                        },
                        "relative_path": {
                            "type": "string",
                            "description": "Path relative to the skill directory, for example references/example.md.",
                        },
                    },
                    "required": ["skill_name", "relative_path"],
                },
                metadata={"source": "agent_skill_internal"},
            ),
        ]

    def _iter_root_skills(self, root: Path) -> Iterable[SkillMetadata]:
        for candidate in sorted(root.iterdir()):
            if not candidate.is_dir():
                continue
            skill_file = candidate / "SKILL.md"
            if not skill_file.is_file():
                continue
            try:
                yield parse_skill_file(skill_file)
            except SkillValidationError as exc:
                self._warn(str(exc))
                continue

    def _get_skill(self, skill_name: str) -> SkillMetadata:
        for skill in self.discover():
            if skill.name == skill_name:
                return skill
        raise ValueError(f"Skill '{skill_name}' not found")

    def _is_skill_compatible(self, skill: SkillMetadata) -> bool:
        if not skill.allowed_tools:
            return True
        if not self.available_tool_names:
            self._warn(
                f"Skipping skill '{skill.name}': skill declares allowed-tools "
                f"{list(skill.allowed_tools)} but this agent has no bound external tools."
            )
            return False
        if not any(tool_name in self.available_tool_names for tool_name in skill.allowed_tools):
            self._warn(
                f"Skipping skill '{skill.name}': none of its allowed-tools "
                f"{list(skill.allowed_tools)} are configured on this agent."
            )
            return False
        return True

    def _warn(self, message: str) -> None:
        self._discovery_warnings.append(message)
        if self.warning_reporter is not None:
            self.warning_reporter(message)
