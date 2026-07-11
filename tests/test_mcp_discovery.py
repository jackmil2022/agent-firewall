from pathlib import Path

import pytest

from agent_firewall.capabilities import discover_mcp_tools, list_capabilities
from agent_firewall.config import load_config, write_default_config
from agent_firewall.policy import PolicyViolation
from agent_firewall.store import AgentFirewallStore


def test_discover_mcp_tools_returns_executable_schema_entries(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    write_default_config(tmp_path)
    store = AgentFirewallStore(tmp_path)
    data = store.get_config()
    data["agents"]["default"]["mcp_servers"] = {"local": {"transport": "stdio", "command": "demo"}}
    data["policy"]["allowed_commands"] = ["demo"]
    store.save_config(data)

    class Tool:
        name = "search"
        description = "Search documents"
        args_schema = {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}

    async def fake_load(_servers):
        return [Tool()]

    monkeypatch.setattr("agent_firewall.capabilities._load_mcp_tools", fake_load)

    tools = discover_mcp_tools(load_config(workspace=tmp_path), "default", "local")

    assert tools == [
        {
            "id": "mcp_tool:default:local:search",
            "kind": "mcp_tool",
            "name": "search",
            "description": "Search documents",
            "ref": "local",
            "agent": "default",
            "input_schema": Tool.args_schema,
            "executable": True,
            "health": "available",
        }
    ]
    cached = next(item for item in list_capabilities(load_config(workspace=tmp_path)) if item["kind"] == "mcp_tool")
    assert cached["id"] == "mcp_tool:default:local:search"
    assert cached["executable"] is True

    data = store.get_config()
    data["agents"]["default"]["mcp_servers"]["local"]["args"] = ["--changed"]
    store.save_config(data)
    stale = next(item for item in list_capabilities(load_config(workspace=tmp_path)) if item["kind"] == "mcp_tool")
    assert stale["executable"] is False
    assert stale["health_issue"] == "discovery_stale"


def test_discover_mcp_tools_rejects_disallowed_transport_before_connecting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_default_config(tmp_path)
    store = AgentFirewallStore(tmp_path)
    data = store.get_config()
    data["agents"]["default"]["mcp_servers"] = {
        "local": {"transport": "stdio", "command": "unsafe", "args": []}
    }
    store.save_config(data)

    async def should_not_connect(_servers):
        raise AssertionError("transport should be rejected before connection")

    monkeypatch.setattr("agent_firewall.capabilities._load_mcp_tools", should_not_connect)

    with pytest.raises(PolicyViolation, match="Command is not allowed"):
        discover_mcp_tools(load_config(workspace=tmp_path), "default", "local")
