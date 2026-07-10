from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from .config import APP_DIR, AgentFirewallConfig
from .skills import list_skill_manifests


def list_capabilities(config: AgentFirewallConfig) -> list[dict[str, Any]]:
    capabilities: list[dict[str, Any]] = []
    for key, agent in config.agents.items():
        capabilities.append(
            {
                "id": f"agent:{key}",
                "kind": "agent",
                "name": agent.name,
                "ref": key,
                "model": agent.model,
                "skills": list(agent.skills),
                "executable": True,
                "health": "available" if agent.model in config.models else "issue",
            }
        )

    skills_root = config.workspace / APP_DIR / "skills"
    for skill in list_skill_manifests(skills_root):
        ref = _workspace_ref(skill.path, config.workspace)
        capabilities.append(
            {
                "id": f"skill:{skill.name}",
                "kind": "skill",
                "name": skill.name,
                "ref": ref,
                "description": skill.description,
                "executable": False,
                "health": "unchecked",
            }
        )
        scripts_root = skill.path / "scripts"
        for script in sorted(scripts_root.glob("*")) if scripts_root.exists() else []:
            if not script.is_file():
                continue
            script_ref = script.relative_to(skill.path).as_posix()
            capabilities.append(
                {
                    "id": f"script:{skill.name}:{script_ref}",
                    "kind": "script_action",
                    "name": f"{skill.name} / {script.name}",
                    "ref": ref,
                    "script": script_ref,
                    "executable": True,
                    "health": "unchecked",
                }
            )

    for agent_key, agent in config.agents.items():
        for server_key, server in agent.mcp_servers.items():
            capabilities.append(
                {
                    "id": f"mcp_server:{agent_key}:{server_key}",
                    "kind": "mcp_server",
                    "name": server_key,
                    "ref": server_key,
                    "agent": agent_key,
                    "config": server,
                    "executable": False,
                    "health": "unchecked",
                }
            )
    return capabilities


def discover_mcp_tools(config: AgentFirewallConfig, agent_key: str, server_key: str) -> list[dict[str, Any]]:
    if agent_key not in config.agents:
        raise ValueError(f"agent not found: {agent_key}")
    server = config.agents[agent_key].mcp_servers.get(server_key)
    if not server:
        raise ValueError(f"mcp server not found: {server_key}")
    tools = asyncio.run(_load_mcp_tools({server_key: server}))
    return [
        {
            "id": f"mcp_tool:{agent_key}:{server_key}:{tool.name}",
            "kind": "mcp_tool",
            "name": str(tool.name),
            "description": str(getattr(tool, "description", "") or ""),
            "ref": server_key,
            "agent": agent_key,
            "input_schema": _tool_schema(tool),
            "executable": True,
            "health": "available",
        }
        for tool in tools
    ]


async def _load_mcp_tools(servers: dict[str, dict[str, Any]]) -> list[Any]:
    from langchain_mcp_adapters.client import MultiServerMCPClient

    return await MultiServerMCPClient(servers).get_tools()


def _tool_schema(tool: Any) -> dict[str, Any]:
    schema = getattr(tool, "args_schema", {})
    if isinstance(schema, dict):
        return schema
    if hasattr(schema, "model_json_schema"):
        return schema.model_json_schema()
    if hasattr(tool, "args") and isinstance(tool.args, dict):
        return tool.args
    return {}


def _workspace_ref(path: Path, workspace: Path) -> str:
    try:
        return path.relative_to(workspace).as_posix()
    except ValueError:
        return path.as_posix()
