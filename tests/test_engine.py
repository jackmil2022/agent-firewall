from pathlib import Path

from agent_firewall.config import load_config, write_default_config
from agent_firewall.engine import _deepagent_kwargs
from agent_firewall.fake_model import EchoChatModel
from agent_firewall.skills import install_bundled_skills
from agent_firewall.tools import agent_policy_check


def fake_create_deep_agent(
    model=None,
    tools=None,
    *,
    system_prompt=None,
    subagents=None,
    skills=None,
    backend=None,
):
    return {
        "model": model,
        "tools": tools,
        "system_prompt": system_prompt,
        "subagents": subagents,
        "skills": skills,
        "backend": backend,
    }


class FakeFilesystemBackend:
    def __init__(self, root_dir: Path, virtual_mode: bool = False) -> None:
        self.root_dir = root_dir
        self.virtual_mode = virtual_mode


def test_deepagent_kwargs_include_customization(tmp_path: Path) -> None:
    write_default_config(tmp_path)
    install_bundled_skills(tmp_path)
    config = load_config(workspace=tmp_path)

    kwargs = _deepagent_kwargs(
        fake_create_deep_agent,
        config,
        config.active,
        [agent_policy_check],
        FakeFilesystemBackend,
    )

    assert isinstance(kwargs["model"], EchoChatModel)
    assert kwargs["system_prompt"].startswith("You are Agent Firewall")
    assert kwargs["skills"] == [".agent-firewall/skills"]
    assert kwargs["subagents"][0]["name"] == "skill-builder"
    assert kwargs["backend"].root_dir == tmp_path
    assert kwargs["backend"].virtual_mode is True
