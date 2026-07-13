from pathlib import Path

import pytest

from agent_firewall.imports import import_local_skill


def _skill(path: Path, name: str = "local-check") -> None:
    (path / "scripts").mkdir(parents=True)
    (path / "SKILL.md").write_text(f"---\nname: {name}\ndescription: Test import\n---\n", encoding="utf-8")
    (path / "scripts" / "check.py").write_text("print('ok')\n", encoding="utf-8")


def test_import_local_skill_copies_a_managed_snapshot(tmp_path: Path) -> None:
    source = tmp_path / "source"
    _skill(source)

    result = import_local_skill(tmp_path / "workspace", source)

    assert result["name"] == "local-check"
    assert Path(result["managed_path"]).name == "local-check"
    assert (Path(result["managed_path"]) / "scripts" / "check.py").is_file()
    assert result["content_hash"].startswith("sha256:")


def test_import_local_skill_rejects_symlinks(tmp_path: Path) -> None:
    source = tmp_path / "source"
    _skill(source)
    (source / "linked.py").symlink_to(source / "scripts" / "check.py")

    with pytest.raises(ValueError, match="regular files"):
        import_local_skill(tmp_path / "workspace", source)


def test_import_local_skill_refuses_to_replace_a_different_skill_with_the_same_name(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    _skill(first)
    _skill(second)
    (second / "scripts" / "check.py").write_text("print('different')\n", encoding="utf-8")
    workspace = tmp_path / "workspace"
    import_local_skill(workspace, first)

    with pytest.raises(ValueError, match="already exists"):
        import_local_skill(workspace, second)
