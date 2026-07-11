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
    interrupt_on=None,
    response_format=None,
    checkpointer=None,
):
    return {
        "model": model,
        "tools": tools,
        "system_prompt": system_prompt,
        "subagents": subagents,
        "skills": skills,
        "backend": backend,
        "interrupt_on": interrupt_on,
        "response_format": response_format,
        "checkpointer": checkpointer,
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
    assert kwargs["checkpointer"].__class__.__name__ == "SqliteSaver"


def test_deepagent_kwargs_resolve_named_model(tmp_path: Path, monkeypatch) -> None:
    write_default_config(tmp_path)
    install_bundled_skills(tmp_path)
    from agent_firewall.store import AgentFirewallStore

    data = AgentFirewallStore(tmp_path).get_config()
    data["models"]["work"] = {"model": "openai:gpt-5", "provider": "openai"}
    data["agents"]["default"]["model"] = "work"
    AgentFirewallStore(tmp_path).save_config(data)
    config = load_config(workspace=tmp_path)

    class FakeChatModel:
        pass

    monkeypatch.setattr("langchain_openai.ChatOpenAI", lambda **_kwargs: FakeChatModel())

    kwargs = _deepagent_kwargs(
        fake_create_deep_agent,
        config,
        config.active,
        [agent_policy_check],
        FakeFilesystemBackend,
    )

    assert isinstance(kwargs["model"], FakeChatModel)


def test_deepagent_kwargs_include_recovery_config(tmp_path: Path) -> None:
    write_default_config(tmp_path)
    install_bundled_skills(tmp_path)
    from agent_firewall.store import AgentFirewallStore

    data = AgentFirewallStore(tmp_path).get_config()
    data["agents"]["default"]["interrupt_on"] = {"read_skill_manifest": True}
    data["agents"]["default"]["response_format"] = {
        "type": "object",
        "properties": {"ok": {"type": "boolean"}},
        "required": ["ok"],
    }
    AgentFirewallStore(tmp_path).save_config(data)
    config = load_config(workspace=tmp_path)

    kwargs = _deepagent_kwargs(
        fake_create_deep_agent,
        config,
        config.active,
        [agent_policy_check],
        FakeFilesystemBackend,
    )

    assert kwargs["interrupt_on"] == {"read_skill_manifest": True}
    assert kwargs["response_format"]["required"] == ["ok"]
