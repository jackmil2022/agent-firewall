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
        "runtime": "python",
        "executable": True,
        "health": "unchecked",
    }


def test_capability_inventory_marks_agent_with_missing_model_key(tmp_path: Path) -> None:
    write_default_config(tmp_path)
    config = load_config(workspace=tmp_path)
    inventory = list_capabilities(config)

    agent = next(item for item in inventory if item["kind"] == "agent")

    assert agent["health"] == "available"
    assert agent["health_issue"] is None


def test_capability_inventory_reports_disabled_and_uncredentialed_models(
    tmp_path: Path, monkeypatch
) -> None:
    write_default_config(tmp_path)
    from agent_firewall.store import AgentFirewallStore

    store = AgentFirewallStore(tmp_path)
    data = store.get_config()
    data["models"]["fake-echo"]["enabled"] = False
    store.save_config(data)

    disabled = next(
        item for item in list_capabilities(load_config(workspace=tmp_path)) if item["kind"] == "agent"
    )
    assert disabled["health_issue"] == "model_disabled"

    data["models"]["fake-echo"]["enabled"] = True
    data["models"]["fake-echo"]["api_key_env"] = "AGENT_FIREWALL_TEST_KEY"
    store.save_config(data)
    monkeypatch.delenv("AGENT_FIREWALL_TEST_KEY", raising=False)

    missing_key = next(
        item for item in list_capabilities(load_config(workspace=tmp_path)) if item["kind"] == "agent"
    )
    assert missing_key["health_issue"] == "model_api_key_missing"

    data["models"]["fake-echo"]["api_key"] = "stored-secret"
    store.save_config(data)
    available = next(
        item for item in list_capabilities(load_config(workspace=tmp_path)) if item["kind"] == "agent"
    )
    assert available["health"] == "available"
