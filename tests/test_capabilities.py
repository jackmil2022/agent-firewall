from pathlib import Path

from agent_firewall.capabilities import list_capabilities
from agent_firewall.config import load_config, write_default_config
from agent_firewall.skills import install_bundled_skills


def test_capability_inventory_separates_skill_bindings_and_script_actions(tmp_path: Path) -> None:
    write_default_config(tmp_path)
    install_bundled_skills(tmp_path)
    inventory = list_capabilities(load_config(workspace=tmp_path))

    skill = next(item for item in inventory if item["kind"] == "skill" and item["ref"].endswith("skill-creator"))
    script = next(item for item in inventory if item["id"] == "script:skill-creator:scripts/init_skill.py")

    assert skill["executable"] is False
    assert skill["health"] == "unchecked"
    assert script == {
        "id": "script:skill-creator:scripts/init_skill.py",
        "kind": "script_action",
        "name": "skill-creator / init_skill.py",
        "ref": ".agent-firewall/skills/skill-creator",
        "script": "scripts/init_skill.py",
        "executable": True,
        "health": "unchecked",
    }


def test_capability_inventory_marks_agent_with_missing_model_key(tmp_path: Path) -> None:
    write_default_config(tmp_path)
    config = load_config(workspace=tmp_path)
    inventory = list_capabilities(config)

    agent = next(item for item in inventory if item["kind"] == "agent")

    assert agent["health"] == "available"
