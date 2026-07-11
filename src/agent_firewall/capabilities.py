from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any

from .config import APP_DIR, AgentFirewallConfig
from .policy import policy_from_config, prepare_mcp_connections
from .skills import list_skill_manifests, normalize_skill_path
from .store import AgentFirewallStore, snapshot_hash


def list_capabilities(config: AgentFirewallConfig) -> list[dict[str, Any]]:
    capabilities: list[dict[str, Any]] = []
    for key, agent in config.agents.items():
        health, health_issue = _agent_health(config, agent.model)
        capabilities.append(
            {
                "id": f"agent:{key}",
                "kind": "agent",
                "name": agent.name,
                "ref": key,
                "model": agent.model,
                "skills": list(agent.skills),
                "allowed_mcp_tools": {key: list(value) for key, value in agent.allowed_mcp_tools.items()},
                "executable": True,
                "health": health,
                "health_issue": health_issue,
            }
        )

    skills_root = config.workspace / APP_DIR / "skills"
    skills = list_skill_manifests(skills_root)
    for skill in skills:
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
        for script in sorted(scripts_root.glob("*.py")) if scripts_root.exists() else []:
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
                    "runtime": "python",
                    "executable": True,
                    "health": "unchecked",
                }
            )

    # A Skill is not an executable node, but an Agent/Skill binding is a useful
    # test target: it runs the Agent with that instruction package mounted.
    for agent_key, agent in config.agents.items():
        bound_skills: set[Path] = set()
        for binding in agent.skills:
            normalized = Path(normalize_skill_path(binding, config.workspace))
            binding_path = (config.workspace / normalized).resolve() if not normalized.is_absolute() else normalized.resolve()
            for skill in skills:
                try:
                    skill.path.resolve().relative_to(binding_path)
                except ValueError:
                    continue
                bound_skills.add(skill.path.resolve())
        for skill in skills:
            if skill.path.resolve() not in bound_skills:
                continue
            ref = _workspace_ref(skill.path, config.workspace)
            capabilities.append(
                {
                    "id": f"skill_binding:{agent_key}:{ref}",
                    "kind": "skill_binding",
                    "name": f"{agent.name} / {skill.name}",
                    "description": skill.description,
                    "ref": ref,
                    "agent": agent_key,
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
                    "executable": False,
                    "health": "unchecked",
                }
            )
    store = AgentFirewallStore(config.workspace)
    for cached in store.list_discovered_mcp_tools():
        agent = config.agents.get(str(cached["agent_key"]))
        server = agent.mcp_servers.get(str(cached["server_key"])) if agent else None
        if server is None:
            continue
        stale = cached.get("server_config_hash") != snapshot_hash(server)
        capabilities.append(
            {
                "id": f"mcp_tool:{cached['agent_key']}:{cached['server_key']}:{cached['tool_name']}",
                "kind": "mcp_tool",
                "name": cached["tool_name"],
                "description": cached["description"],
                "ref": cached["server_key"],
                "agent": cached["agent_key"],
                "input_schema": cached["input_schema"],
                "discovered_at": cached["discovered_at"],
                "executable": not stale,
                "health": "issue" if stale else "available",
                "health_issue": "discovery_stale" if stale else None,
            }
        )
    return capabilities


def discover_mcp_tools(
    config: AgentFirewallConfig, agent_key: str, server_key: str, *, approved: bool = False
) -> list[dict[str, Any]]:
    if agent_key not in config.agents:
        raise ValueError(f"agent not found: {agent_key}")
    server = config.agents[agent_key].mcp_servers.get(server_key)
    if not server:
        raise ValueError(f"mcp server not found: {server_key}")
    servers = prepare_mcp_connections(policy_from_config(config), {server_key: server}, approved=approved)
    tools = asyncio.run(_load_mcp_tools(servers))
    result = [
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
    AgentFirewallStore(config.workspace).replace_discovered_mcp_tools(
        agent_key,
        server_key,
        result,
        server_config_hash=snapshot_hash(server),
    )
    return result


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


def _agent_health(config: AgentFirewallConfig, model_key: str) -> tuple[str, str | None]:
    model = config.models.get(model_key)
    if model is None:
        return "issue", "model_not_configured"
    if not bool(model.get("enabled", True)):
        return "issue", "model_disabled"
    api_key = str(model.get("api_key") or "")
    api_key_env = str(model.get("api_key_env") or "")
    if not api_key and api_key_env and not os.environ.get(api_key_env):
        return "issue", "model_api_key_missing"
    return "available", None
