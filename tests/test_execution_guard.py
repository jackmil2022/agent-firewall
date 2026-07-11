import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest

from agent_firewall import engine
from agent_firewall.config import load_config, write_default_config
from agent_firewall.policy import ExecutionPolicy, PolicyViolation
from agent_firewall.store import AgentFirewallStore


def test_mcp_stdio_connection_enforces_command_cwd_and_environment(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("MCP_TOKEN", "token")
    monkeypatch.setenv("UNRELATED_SECRET", "hidden")
    captured = {}

    class FakeClient:
        def __init__(self, connections, **kwargs):
            captured["connections"] = connections
            captured["interceptors"] = kwargs.get("tool_interceptors") or []

        async def get_tools(self):
            return []

    monkeypatch.setattr("langchain_mcp_adapters.client.MultiServerMCPClient", FakeClient)
    policy = ExecutionPolicy(
        workspace=tmp_path,
        allowed_commands=["python"],
        allowed_env_vars=["MCP_TOKEN"],
    )

    asyncio.run(
        engine._load_mcp_tools(
            {"local": {"transport": "stdio", "command": "python", "args": ["server.py"], "env": {"MCP_TOKEN": "token"}}},
            policy=policy,
        )
    )

    connection = captured["connections"]["local"]
    assert connection["cwd"] == str(tmp_path)
    assert connection["env"]["MCP_TOKEN"] == "token"
    assert "UNRELATED_SECRET" not in connection["env"]
    assert captured["interceptors"]


def test_agent_mcp_tool_call_requires_its_own_policy_approval(tmp_path: Path, monkeypatch) -> None:
    captured = {}

    class FakeClient:
        def __init__(self, _connections, **kwargs):
            captured["guard"] = kwargs["tool_interceptors"][0]

        async def get_tools(self):
            return []

    monkeypatch.setattr("langchain_mcp_adapters.client.MultiServerMCPClient", FakeClient)
    policy = ExecutionPolicy(
        workspace=tmp_path,
        require_approval=["mcp:delete"],
        allowed_commands=["python"],
    )
    asyncio.run(
        engine._load_mcp_tools(
            {"local": {"transport": "stdio", "command": "python", "args": []}},
            policy=policy,
        )
    )

    async def handler(_request):
        return "called"

    with pytest.raises(PolicyViolation) as denied:
        asyncio.run(captured["guard"](SimpleNamespace(name="delete"), handler))

    assert denied.value.decision["code"] == "approval_required"


def test_mcp_remote_connection_rejects_non_allowlisted_host(tmp_path: Path) -> None:
    policy = ExecutionPolicy(
        workspace=tmp_path,
        allow_network=True,
        allowed_network_hosts=["mcp.example.com"],
    )

    with pytest.raises(PolicyViolation, match="not allowed"):
        asyncio.run(
            engine._load_mcp_tools(
                {"remote": {"transport": "http", "url": "https://metadata.local/mcp"}},
                policy=policy,
            )
        )


def test_agent_builtin_file_tools_are_bound_to_workspace(tmp_path: Path) -> None:
    write_default_config(tmp_path)
    config = load_config(workspace=tmp_path)
    tools = asyncio.run(engine._load_tools(config, config.active))
    read_manifest = next(tool for tool in tools if tool.__name__ == "read_skill_manifest")

    with pytest.raises(ValueError, match="outside workspace"):
        read_manifest(str(tmp_path.parent / "SKILL.md"))


def test_agent_mcp_tool_allowlist_filters_loaded_tools(tmp_path: Path, monkeypatch) -> None:
    write_default_config(tmp_path)
    store = AgentFirewallStore(tmp_path)
    data = store.get_config()
    data["agents"]["default"]["mcp_servers"] = {"local": {"transport": "stdio", "command": "python"}}
    data["agents"]["default"]["allowed_mcp_tools"] = {"local": ["read"]}
    store.save_config(data)
    config = load_config(workspace=tmp_path)

    class FakeClient:
        def __init__(self, *_args, **_kwargs):
            pass

        async def get_tools(self):
            return [SimpleNamespace(name="read"), SimpleNamespace(name="write")]

    monkeypatch.setattr("langchain_mcp_adapters.client.MultiServerMCPClient", FakeClient)

    tools = asyncio.run(engine._load_tools(config, config.active))

    assert [tool.name for tool in tools if hasattr(tool, "name")] == ["read"]


def test_agent_model_network_and_key_require_policy_allowlists(tmp_path: Path, monkeypatch) -> None:
    write_default_config(tmp_path)
    store = AgentFirewallStore(tmp_path)
    data = store.get_config()
    data["models"]["work"] = {
        "model": "openai:gpt-5",
        "base_url": "https://models.example/v1",
        "api_key_env": "WORK_API_KEY",
        "enabled": True,
    }
    data["agents"]["default"]["model"] = "work"
    store.save_config(data)
    monkeypatch.setenv("WORK_API_KEY", "secret")
    config = load_config(workspace=tmp_path)

    with pytest.raises(PolicyViolation) as denied:
        asyncio.run(engine.build_agent(config))

    assert denied.value.decision["code"] in {"network_denied", "environment_denied"}
