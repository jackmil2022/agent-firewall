from __future__ import annotations

import asyncio
import inspect
import os
import sqlite3
from pathlib import Path
from typing import Any, Callable

from .config import AgentFirewallConfig, AgentSpec, ConfigError
from .skills import normalize_skill_path
from .store import db_path
from .tools import BUILTIN_TOOLS


class EngineError(RuntimeError):
    """Raised when deepagents cannot be created or configured."""


async def build_agent(config: AgentFirewallConfig, agent_name: str | None = None) -> Any:
    spec = config.agents[agent_name] if agent_name else config.active
    tools = await _load_tools(spec)
    create_deep_agent, filesystem_backend = _load_deepagents()
    kwargs = _deepagent_kwargs(create_deep_agent, config, spec, tools, filesystem_backend)
    return create_deep_agent(**kwargs)


def build_agent_sync(config: AgentFirewallConfig, agent_name: str | None = None) -> Any:
    return asyncio.run(build_agent(config, agent_name))


async def _load_tools(spec: AgentSpec) -> list[Callable[..., Any]]:
    tools: list[Callable[..., Any]] = []
    for name in spec.tools:
        try:
            tools.append(BUILTIN_TOOLS[name])
        except KeyError as exc:
            raise EngineError(f"unknown builtin tool '{name}'") from exc
    if spec.mcp_servers:
        tools.extend(await _load_mcp_tools(spec.mcp_servers))
    return tools


async def _load_mcp_tools(mcp_servers: dict[str, dict[str, Any]]) -> list[Any]:
    try:
        from langchain_mcp_adapters.client import MultiServerMCPClient
    except ImportError as exc:
        raise EngineError(
            "MCP servers are configured, but langchain-mcp-adapters is not installed."
        ) from exc
    client = MultiServerMCPClient(mcp_servers)
    return await client.get_tools()


def _load_deepagents() -> tuple[Callable[..., Any], Any]:
    try:
        from deepagents import create_deep_agent
    except ImportError as exc:
        raise EngineError("deepagents is not installed. Run: pip install -e .") from exc
    try:
        from deepagents.backends import FilesystemBackend
    except ImportError:
        FilesystemBackend = None
    return create_deep_agent, FilesystemBackend


def _deepagent_kwargs(
    create_deep_agent: Callable[..., Any],
    config: AgentFirewallConfig,
    spec: AgentSpec,
    tools: list[Any],
    filesystem_backend: Any,
) -> dict[str, Any]:
    params = set(inspect.signature(create_deep_agent).parameters)
    kwargs: dict[str, Any] = {
        "tools": tools,
        "model": _resolve_model(spec.model, config),
        "subagents": [item.to_deepagents() for item in spec.subagents],
    }
    if "system_prompt" in params:
        kwargs["system_prompt"] = spec.system_prompt
    elif "instructions" in params:
        kwargs["instructions"] = spec.system_prompt
    else:
        kwargs["prompt"] = spec.system_prompt

    skill_paths = [normalize_skill_path(path, config.workspace) for path in spec.skills]
    if "skills" in params:
        kwargs["skills"] = skill_paths

    if filesystem_backend and "backend" in params:
        kwargs["backend"] = filesystem_backend(root_dir=Path(config.workspace), virtual_mode=True)
    if spec.interrupt_on and "interrupt_on" in params:
        kwargs["interrupt_on"] = spec.interrupt_on
    if spec.response_format and "response_format" in params:
        kwargs["response_format"] = spec.response_format
    if spec.checkpoint and "checkpointer" in params:
        kwargs["checkpointer"] = _sqlite_checkpointer(config.workspace)
    return {key: value for key, value in kwargs.items() if key in params}


def _resolve_model(model: str, config: AgentFirewallConfig | None = None) -> Any:
    preset = (config.models.get(model) or {}) if config else {}
    model_value = str(preset.get("model") or model)
    if model_value == "fake:echo":
        from .fake_model import EchoChatModel

        return EchoChatModel()
    if preset:
        if preset.get("enabled", True) is False:
            raise ConfigError(f"model preset '{model}' is disabled")
        provider, separator, model_id = model_value.partition(":")
        needs_client = bool(preset.get("base_url") or preset.get("api_key_env") or preset.get("params"))
        if provider == "openai" and separator and needs_client:
            from langchain_openai import ChatOpenAI

            api_key_env = str(preset.get("api_key_env") or "")
            api_key = os.environ.get(api_key_env) if api_key_env else None
            if api_key_env and not api_key:
                raise ConfigError(f"model preset '{model}' requires environment variable {api_key_env}")
            kwargs = dict(preset.get("params") or {})
            kwargs["model"] = model_id
            if preset.get("base_url"):
                kwargs["base_url"] = str(preset["base_url"])
            if api_key:
                kwargs["api_key"] = api_key
            return ChatOpenAI(**kwargs)
    return model_value


def _sqlite_checkpointer(workspace: Path) -> Any:
    try:
        from langgraph.checkpoint.sqlite import SqliteSaver
    except ImportError as exc:
        raise EngineError(
            "Agent checkpointing requires langgraph-checkpoint-sqlite. Run: pip install -e ."
        ) from exc
    connection = sqlite3.connect(db_path(workspace), check_same_thread=False)
    return SqliteSaver(connection)
