from pathlib import Path

from agent_firewall.config import load_config, write_default_config
from agent_firewall.store import AgentFirewallStore


def test_policy_configuration_is_normalized_and_loaded(tmp_path: Path) -> None:
    write_default_config(tmp_path)
    store = AgentFirewallStore(tmp_path)
    data = store.get_config()
    data["policy"] = {
        "require_approval": ["script", "mcp:delete"],
        "allowed_commands": ["python"],
        "allow_network": False,
        "exposed_env": ["WORK_API_KEY"],
    }
    store.save_config(data)

    config = load_config(workspace=tmp_path)

    assert config.policy.require_approval == ["script", "mcp:delete"]
    assert config.policy.allow_network is False
