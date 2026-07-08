from __future__ import annotations

import shutil
from dataclasses import dataclass
from importlib import resources
from pathlib import Path

from .config import APP_DIR


@dataclass(frozen=True)
class SkillManifest:
    name: str
    path: Path
    description: str


def bundled_skills_root() -> Path:
    return Path(str(resources.files("agent_firewall") / "resources" / "skills"))


def install_bundled_skills(workspace: str | Path, *, force: bool = False) -> Path:
    root = Path(workspace).resolve()
    target = root / APP_DIR / "skills"
    target.mkdir(parents=True, exist_ok=True)
    source = bundled_skills_root()
    for item in source.iterdir():
        destination = target / item.name
        if destination.exists() and force:
            shutil.rmtree(destination)
        if not destination.exists():
            shutil.copytree(item, destination)
    return target


def list_skill_manifests(skill_root: str | Path) -> list[SkillManifest]:
    root = Path(skill_root)
    if not root.exists():
        return []
    manifests: list[SkillManifest] = []
    for skill_md in sorted(root.glob("*/SKILL.md")):
        manifests.append(_read_manifest(skill_md))
    return manifests


def _read_manifest(path: Path) -> SkillManifest:
    text = path.read_text(encoding="utf-8")
    frontmatter = _frontmatter(text)
    return SkillManifest(
        name=frontmatter.get("name", path.parent.name),
        path=path.parent,
        description=frontmatter.get("description", ""),
    )


def _frontmatter(text: str) -> dict[str, str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    values: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if ":" in line:
            key, value = line.split(":", 1)
            values[key.strip()] = value.strip().strip('"')
    return values


def normalize_skill_path(path: str | Path, workspace: str | Path) -> str:
    root = Path(workspace).resolve()
    candidate = (root / path).resolve() if not Path(path).is_absolute() else Path(path).resolve()
    try:
        return candidate.relative_to(root).as_posix()
    except ValueError:
        return candidate.as_posix()
