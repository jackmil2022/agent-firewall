from __future__ import annotations

import asyncio
import inspect
import os
import sqlite3
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlsplit

from .config import AgentFirewallConfig, AgentSpec, ConfigError
from .policy import (
    ExecutionPolicy,
    mcp_policy_interceptor,
    policy_from_config,
    prepare_mcp_connections,
    require_operation,
)
from .skills import normalize_skill_path
from .store import db_path
from .tools import BUILTIN_TOOLS, bind_builtin_tool


class EngineError(RuntimeError):
    """Raised when deepagents cannot be created or configured."""


async def build_agent(
    config: AgentFirewallConfig,
    agent_name: str | None = None,
    *,
    policy: ExecutionPolicy | None = None,
    approved: bool = False,
    approved_operation: str = "",
) -> Any:
    spec = config.agents[agent_name] if agent_name else config.active
    execution_policy = policy or policy_from_config(config)
    _check_agent_policy(
        config,
        spec,
        execution_policy,
        approved=approved or approved_operation == "agent",
    )
    tools = await _load_tools(
        config,
        spec,
        policy=execution_policy,
        approved=approved,
        approved_operation=approved_operation,
    )
    create_deep_agent, filesystem_backend = _load_deepagents()
    kwargs = _deepagent_kwargs(create_deep_agent, config, spec, tools, filesystem_backend)
    return create_deep_agent(**kwargs)


def build_agent_sync(
    config: AgentFirewallConfig,
    agent_name: str | None = None,
    *,
    policy: ExecutionPolicy | None = None,
    approved: bool = False,
    approved_operation: str = "",
) -> Any:
    return asyncio.run(
        build_agent(
            config,
            agent_name,
            policy=policy,
            approved=approved,
            approved_operation=approved_operation,
        )
    )


async def _load_tools(
    config: AgentFirewallConfig,
    spec: AgentSpec,
    *,
    policy: ExecutionPolicy | None = None,
    approved: bool = False,
    approved_operation: str = "",
) -> list[Callable[..., Any]]:
    tools: list[Callable[..., Any]] = []
    for name in spec.tools:
        try:
            BUILTIN_TOOLS[name]
        except KeyError as exc:
            raise EngineError(f"unknown builtin tool '{name}'") from exc
        tools.append(bind_builtin_tool(name, config.workspace))
    if spec.mcp_servers:
        tools.extend(
            await _load_mcp_tools(
                spec.mcp_servers,
                allowed_mcp_tools=spec.allowed_mcp_tools,
                policy=policy,
                approved=approved,
                approved_operation=approved_operation,
            )
        )
    return tools


async def _load_mcp_tools(
    mcp_servers: dict[str, dict[str, Any]],
    *,
    allowed_mcp_tools: dict[str, list[str]] | None = None,
    policy: ExecutionPolicy | None = None,
    approved: bool = False,
    approved_operation: str = "",
) -> list[Any]:
    try:
        from langchain_mcp_adapters.client import MultiServerMCPClient
    except ImportError as exc:
        raise EngineError(
            "MCP servers are configured, but langchain-mcp-adapters is not installed."
        ) from exc
    connection_approved = approved or approved_operation.startswith("mcp:")
    connections = (
        prepare_mcp_connections(policy, mcp_servers, approved=connection_approved) if policy else mcp_servers
    )
    interceptors = (
        [
            mcp_policy_interceptor(
                policy,
                approved=approved,
                approved_operation=approved_operation,
            )
        ]
        if policy
        else None
    )
    client = MultiServerMCPClient(connections, tool_interceptors=interceptors)
    tools = await client.get_tools()
    if not allowed_mcp_tools:
        return tools
    allowed = {name for names in allowed_mcp_tools.values() for name in names}
    return [tool for tool in tools if str(getattr(tool, "name", "")) in allowed]


def _check_agent_policy(
    config: AgentFirewallConfig,
    spec: AgentSpec,
    policy: ExecutionPolicy,
    *,
    approved: bool,
) -> None:
    preset = config.models.get(spec.model) or {}
    model_value = str(preset.get("model") or spec.model)
    api_key_env = str(preset.get("api_key_env") or "")
    api_key = str(preset.get("api_key") or "")
    network_host = _model_network_host(model_value, preset)
    require_operation(
        policy,
        kind="agent",
        network=bool(network_host),
        network_host=network_host,
        env_vars=[api_key_env] if api_key_env and not api_key else [],
        approved=approved,
    )


def _model_network_host(model_value: str, preset: dict[str, Any]) -> str | None:
    if model_value == "fake:echo":
        return None
    base_url = str(preset.get("base_url") or "")
    if base_url:
        host = urlsplit(base_url).hostname
        if not host:
            raise ConfigError(f"invalid model base_url: {base_url}")
        return host
    prefixed_provider, separator, _model_id = model_value.partition(":")
    provider = str(preset.get("provider") or (prefixed_provider if separator else "custom"))
    return "api.openai.com" if provider == "openai" else f"{provider}.provider-default"


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
        prefixed_provider, separator, prefixed_model_id = model_value.partition(":")
        provider = str(preset.get("provider") or (prefixed_provider if separator else ""))
        model_id = prefixed_model_id if separator else model_value
        if not provider:
            raise ConfigError(f"model preset '{model}' requires provider or a provider:model value")
        if separator and preset.get("provider") and prefixed_provider != provider:
            raise ConfigError(
                f"model preset '{model}' provider '{provider}' conflicts with model value '{model_value}'"
            )
        api_key = str(preset.get("api_key") or "")
        api_key_env = str(preset.get("api_key_env") or "")
        if not api_key and api_key_env:
            api_key = os.environ.get(api_key_env) or ""
        if api_key_env and not api_key:
            raise ConfigError(f"model preset '{model}' requires environment variable {api_key_env}")
        kwargs = dict(preset.get("params") or {})
        kwargs["model"] = model_id
        if preset.get("base_url"):
            kwargs["base_url"] = str(preset["base_url"])
        if api_key:
            kwargs["api_key"] = api_key
        if provider == "openai":
            from langchain_openai import ChatOpenAI

            return ChatOpenAI(**kwargs)
        from langchain.chat_models import init_chat_model

        return init_chat_model(model_provider=provider, **kwargs)
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
