from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ExecutionPolicy:
    workspace: Path
    require_approval: list[str] = field(default_factory=list)
    allowed_commands: list[str] = field(default_factory=lambda: ["python"])
    allow_network: bool = False
    exposed_env: list[str] = field(default_factory=list)


def check_operation(
    policy: ExecutionPolicy,
    *,
    kind: str,
    path: str | Path | None = None,
    command: str | None = None,
    network: bool = False,
    approved: bool = False,
) -> dict[str, Any]:
    if path is not None:
        try:
            Path(path).resolve().relative_to(policy.workspace.resolve())
        except ValueError:
            return {"allowed": False, "code": "path_outside_workspace", "message": f"Path is outside workspace: {path}"}
    if command and Path(command).name not in policy.allowed_commands:
        return {"allowed": False, "code": "command_denied", "message": f"Command is not allowed: {command}"}
    if network and not policy.allow_network:
        return {"allowed": False, "code": "network_denied", "message": "Network access is disabled"}
    requires_approval = kind in policy.require_approval or (
        kind.startswith("mcp:") and "mcp:*" in policy.require_approval
    )
    if requires_approval and not approved:
        return {"allowed": False, "code": "approval_required", "message": f"Approval required for {kind}"}
    return {"allowed": True, "code": "allowed", "message": "Operation allowed"}


def redact_secrets(text: str, environment_names: list[str]) -> str:
    result = text
    for name in environment_names:
        value = os.environ.get(name)
        if value:
            result = result.replace(value, "[REDACTED]")
    return result
