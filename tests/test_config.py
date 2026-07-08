from pathlib import Path

from agent_firewall.config import load_config, write_default_config
from agent_firewall.skills import install_bundled_skills


def test_default_config_loads(tmp_path: Path) -> None:
    write_default_config(tmp_path)
    install_bundled_skills(tmp_path)

    config = load_config(workspace=tmp_path)

    assert config.active.name == "agent-firewall"
    assert config.active.subagents[0].name == "skill-builder"
    assert config.acp.enabled is True
    assert config.acp.stdio_buffer_limit_bytes == 52_428_800
