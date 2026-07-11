from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable, Iterable
from urllib.parse import urlsplit


@dataclass(frozen=True)
class ExecutionPolicy:
    workspace: Path
    require_approval: list[str] = field(default_factory=list)
    allowed_commands: list[str] = field(default_factory=lambda: ["python"])
    allow_network: bool = False
    exposed_env: list[str] = field(default_factory=list)
    allowed_network_hosts: list[str] = field(default_factory=list)
    allowed_env_vars: list[str] = field(default_factory=list)

    @property
    def environment_names(self) -> set[str]:
        return {str(name) for name in [*self.exposed_env, *self.allowed_env_vars] if name}


class PolicyViolation(PermissionError):
    def __init__(self, decision: dict[str, Any], operation: str = "") -> None:
        super().__init__(str(decision["message"]))
        self.decision = decision
        self.operation = operation


def policy_from_config(config: Any, overrides: dict[str, Any] | None = None) -> ExecutionPolicy:
    if overrides is None:
        spec = config.policy
        data = {
            "require_approval": getattr(spec, "require_approval", []),
            "allowed_commands": getattr(spec, "allowed_commands", ["python"]),
            "allow_network": getattr(spec, "allow_network", False),
            "allowed_network_hosts": getattr(spec, "allowed_network_hosts", []),
            "allowed_env_vars": getattr(spec, "allowed_env_vars", []),
            "exposed_env": getattr(spec, "exposed_env", []),
        }
    else:
        data = overrides
    return ExecutionPolicy(
        workspace=Path(config.workspace).resolve(),
        require_approval=[str(item) for item in data.get("require_approval", [])],
        allowed_commands=[str(item) for item in data.get("allowed_commands", ["python"])],
        allow_network=bool(data.get("allow_network", False)),
        allowed_network_hosts=[str(item) for item in data.get("allowed_network_hosts", [])],
        allowed_env_vars=[str(item) for item in data.get("allowed_env_vars", [])],
        exposed_env=[str(item) for item in data.get("exposed_env", [])],
    )


def check_operation(
    policy: ExecutionPolicy,
    *,
    kind: str,
    path: str | Path | None = None,
    command: str | None = None,
    network: bool = False,
    network_host: str | None = None,
    env_vars: Iterable[str] = (),
    approved: bool = False,
) -> dict[str, Any]:
    if path is not None:
        try:
            Path(path).resolve().relative_to(policy.workspace.resolve())
        except ValueError:
            return _decision(False, "path_outside_workspace", f"Path is outside workspace: {path}")
    if command:
        command_name = Path(command).name
        if command not in policy.allowed_commands and command_name not in policy.allowed_commands:
            return _decision(False, "command_denied", f"Command is not allowed: {command}")
    denied_env = sorted({str(name) for name in env_vars if str(name)} - policy.environment_names)
    if denied_env:
        return _decision(
            False,
            "environment_denied",
            f"Environment variable is not allowed: {', '.join(denied_env)}",
        )
    if network or network_host:
        if not policy.allow_network:
            return _decision(False, "network_denied", "Network access is disabled")
        if network_host and policy.allowed_network_hosts and not _host_allowed(
            network_host, policy.allowed_network_hosts
        ):
            return _decision(False, "network_host_denied", f"Network host is not allowed: {network_host}")
    requires_approval = kind in policy.require_approval or (
        kind.startswith("mcp:") and "mcp:*" in policy.require_approval
    )
    if requires_approval and not approved:
        return _decision(False, "approval_required", f"Approval required for {kind}")
    return _decision(True, "allowed", "Operation allowed")


def require_operation(policy: ExecutionPolicy, **operation: Any) -> None:
    decision = check_operation(policy, **operation)
    if not decision["allowed"]:
        raise PolicyViolation(decision, str(operation.get("kind") or ""))


def subprocess_environment(
    policy: ExecutionPolicy,
    configured: dict[str, Any] | None = None,
) -> dict[str, str]:
    configured = configured or {}
    require_operation(policy, kind="environment", env_vars=configured)
    allowed_names = policy.environment_names | _essential_environment_names()
    environment = {name: value for name, value in os.environ.items() if name in allowed_names}
    environment.update({name: str(value) for name, value in configured.items() if name in allowed_names})
    return environment


def prepare_mcp_connections(
    policy: ExecutionPolicy,
    connections: dict[str, dict[str, Any]],
    *,
    approved: bool = False,
) -> dict[str, dict[str, Any]]:
    return {
        name: prepare_mcp_connection(policy, connection, approved=approved)
        for name, connection in connections.items()
    }


def prepare_mcp_connection(
    policy: ExecutionPolicy,
    connection: dict[str, Any],
    *,
    approved: bool = False,
) -> dict[str, Any]:
    prepared = dict(connection)
    transport = str(prepared.get("transport") or "").replace("-", "_").lower()
    require_operation(policy, kind="mcp:connect", approved=approved)
    if transport == "stdio":
        command = str(prepared.get("command") or "")
        if not command:
            raise PolicyViolation(
                _decision(False, "invalid_mcp_config", "MCP stdio command is required"), "mcp:connect"
            )
        cwd = Path(prepared.get("cwd") or policy.workspace)
        if not cwd.is_absolute():
            cwd = policy.workspace / cwd
        require_operation(policy, kind="mcp:connect", command=command, path=cwd, approved=approved)
        prepared["cwd"] = str(cwd.resolve())
        prepared["env"] = subprocess_environment(policy, dict(prepared.get("env") or {}))
        prepared.setdefault("args", [])
        return prepared
    if transport in {"sse", "http", "streamable_http", "websocket"}:
        url = str(prepared.get("url") or "")
        host = urlsplit(url).hostname
        if not host:
            raise PolicyViolation(
                _decision(False, "invalid_mcp_config", "MCP network URL is required"), "mcp:connect"
            )
        require_operation(
            policy,
            kind="mcp:connect",
            network=True,
            network_host=host,
            approved=approved,
        )
        return prepared
    raise PolicyViolation(
        _decision(False, "invalid_mcp_transport", f"Unsupported MCP transport: {transport or 'missing'}"),
        "mcp:connect",
    )


def mcp_policy_interceptor(
    policy: ExecutionPolicy,
    *,
    approved: bool = False,
    approved_operation: str = "",
) -> Callable[[Any, Callable[[Any], Awaitable[Any]]], Awaitable[Any]]:
    async def guard(request: Any, handler: Callable[[Any], Awaitable[Any]]) -> Any:
        operation = f"mcp:{request.name}"
        require_operation(
            policy,
            kind=operation,
            approved=approved or approved_operation in {operation, "mcp:*"},
        )
        return await handler(request)

    return guard


def redact_secrets(
    text: str,
    environment_names: Iterable[str],
    *,
    secret_values: Iterable[str] = (),
) -> str:
    result = text
    values = [os.environ.get(name) for name in environment_names]
    values.extend(str(value) for value in secret_values)
    for value in sorted({value for value in values if value}, key=len, reverse=True):
        result = result.replace(value, "[REDACTED]")
    return result


def redact_data(
    value: Any,
    environment_names: Iterable[str],
    *,
    secret_values: Iterable[str] = (),
) -> Any:
    if isinstance(value, str):
        return redact_secrets(value, environment_names, secret_values=secret_values)
    if isinstance(value, dict):
        return {
            key: (
                "[REDACTED]"
                if _sensitive_key(str(key))
                else redact_data(item, environment_names, secret_values=secret_values)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_data(item, environment_names, secret_values=secret_values) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_data(item, environment_names, secret_values=secret_values) for item in value)
    return value


def _decision(allowed: bool, code: str, message: str) -> dict[str, Any]:
    return {"allowed": allowed, "code": code, "message": message}


def _host_allowed(host: str, patterns: Iterable[str]) -> bool:
    host = host.rstrip(".").lower()
    for pattern in patterns:
        candidate = str(pattern).rstrip(".").lower()
        if candidate == "*" or candidate == host:
            return True
        if candidate.startswith("*.") and host.endswith(candidate[1:]) and host != candidate[2:]:
            return True
    return False


def _essential_environment_names() -> set[str]:
    return {
        "COMSPEC",
        "HOME",
        "LANG",
        "LC_ALL",
        "PATH",
        "PATHEXT",
        "SYSTEMROOT",
        "TEMP",
        "TMP",
        "TMPDIR",
        "USERPROFILE",
        "WINDIR",
    }


def _sensitive_key(key: str) -> bool:
    normalized = key.lower().replace("-", "_")
    return any(part in normalized for part in ("api_key", "authorization", "password", "secret", "token"))
