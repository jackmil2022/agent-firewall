from pathlib import Path

from agent_firewall.skills import install_bundled_skills, list_skill_manifests, normalize_skill_path


def test_install_bundled_skills(tmp_path: Path) -> None:
    skills_root = install_bundled_skills(tmp_path)
    manifests = list_skill_manifests(skills_root)

    assert {item.name for item in manifests} == {"browser-control", "skill-creator"}


def test_normalize_skill_path_relative_to_workspace(tmp_path: Path) -> None:
    skill_path = tmp_path / ".agent-firewall" / "skills"
    skill_path.mkdir(parents=True)

    assert normalize_skill_path(skill_path, tmp_path) == ".agent-firewall/skills"
