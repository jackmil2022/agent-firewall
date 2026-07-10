from pathlib import Path

import pytest

from agent_firewall.capabilities import discover_mcp_tools
from agent_firewall.config import load_config, write_default_config
from agent_firewall.store import AgentFirewallStore


def test_discover_mcp_tools_returns_executable_schema_entries(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    write_default_config(tmp_path)
    store = AgentFirewallStore(tmp_path)
    data = store.get_config()
    data["agents"]["default"]["mcp_servers"] = {"local": {"transport": "stdio", "command": "demo"}}
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
