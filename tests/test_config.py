from pathlib import Path

import pytest

from agent_firewall.config import ConfigError, load_config, normalize_config_mapping, write_default_config
from agent_firewall.skills import install_bundled_skills
from agent_firewall.store import DB_FILE


def test_default_config_loads(tmp_path: Path) -> None:
    write_default_config(tmp_path)
    install_bundled_skills(tmp_path)

    config = load_config(workspace=tmp_path)

    assert config.active.name == "agent-firewall"
    assert config.active.subagents[0].name == "skill-builder"
    assert config.acp.enabled is True
    assert config.acp.stdio_buffer_limit_bytes == 52_428_800
    assert (tmp_path / ".agent-firewall" / DB_FILE).exists()


def test_normalize_config_adds_global_model_defaults() -> None:
    data = normalize_config_mapping(
        {
            "active_agent": "default",
            "agents": {"default": {"name": "agent", "model": "openai:gpt-5", "system_prompt": "x"}},
        }
    )

    assert data["models"]["openai:gpt-5"]["provider"] == "openai"
    assert data["models"]["openai:gpt-5"]["enabled"] is True


def test_normalize_config_rejects_empty_model_id() -> None:
    with pytest.raises(ConfigError):
        normalize_config_mapping(
            {
                "active_agent": "default",
                "models": {"bad": {"model": ""}},
                "agents": {"default": {"name": "agent", "model": "bad", "system_prompt": "x"}},
            }
        )


def test_normalize_config_keeps_one_enabled_global_model_and_updates_agents() -> None:
    data = normalize_config_mapping(
        {
            "active_agent": "default",
            "models": {
                "primary": {"model": "openai:gpt-5", "enabled": True},
                "secondary": {"model": "anthropic:claude-sonnet-4-5", "enabled": True},
            },
            "agents": {
                "default": {"name": "default", "model": "primary", "system_prompt": "x"},
                "reviewer": {"name": "reviewer", "model": "secondary", "system_prompt": "y"},
            },
        }
    )

    assert [name for name, model in data["models"].items() if model["enabled"]] == ["primary"]
    assert {agent["model"] for agent in data["agents"].values()} == {"primary"}


def test_normalize_config_rejects_config_without_an_enabled_model() -> None:
    with pytest.raises(ConfigError, match="exactly one enabled global model"):
        normalize_config_mapping(
            {
                "models": {"disabled": {"model": "fake:echo", "enabled": False}},
                "agents": {"default": {"name": "agent", "model": "disabled", "system_prompt": "x"}},
            }
        )
