from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

APP_DIR = ".agent-firewall"
CONFIG_FILE = "config.json"


class ConfigError(ValueError):
    """Raised when the app configuration is invalid."""


@dataclass(frozen=True)
class SubAgentSpec:
    name: str
    description: str
    system_prompt: str
    tools: list[str] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "SubAgentSpec":
        required = ("name", "description", "system_prompt")
        missing = [key for key in required if not data.get(key)]
        if missing:
            raise ConfigError(f"subagent missing required field(s): {', '.join(missing)}")
        return cls(
            name=str(data["name"]),
            description=str(data["description"]),
            system_prompt=str(data["system_prompt"]),
            tools=[str(item) for item in data.get("tools", [])],
            skills=[str(item) for item in data.get("skills", [])],
        )

    def to_deepagents(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "name": self.name,
            "description": self.description,
            "system_prompt": self.system_prompt,
        }
        if self.tools:
            result["tools"] = list(self.tools)
        if self.skills:
            result["skills"] = list(self.skills)
        return result


@dataclass(frozen=True)
class AgentSpec:
    name: str
    model: str
    system_prompt: str
    skills: list[str] = field(default_factory=list)
    tools: list[str] = field(default_factory=list)
    subagents: list[SubAgentSpec] = field(default_factory=list)
    mcp_servers: dict[str, dict[str, Any]] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "AgentSpec":
        required = ("name", "model", "system_prompt")
        missing = [key for key in required if not data.get(key)]
        if missing:
            raise ConfigError(f"agent missing required field(s): {', '.join(missing)}")
        return cls(
            name=str(data["name"]),
            model=str(data["model"]),
            system_prompt=str(data["system_prompt"]),
            skills=[str(item) for item in data.get("skills", [])],
            tools=[str(item) for item in data.get("tools", [])],
            subagents=[SubAgentSpec.from_mapping(item) for item in data.get("subagents", [])],
            mcp_servers=dict(data.get("mcp_servers", {})),
        )


@dataclass(frozen=True)
class AcpSpec:
    enabled: bool = True
    use_unstable_protocol: bool = False
    stdio_buffer_limit_bytes: int = 52_428_800

    @classmethod
    def from_mapping(cls, data: dict[str, Any] | None) -> "AcpSpec":
        if not data:
            return cls()
        return cls(
            enabled=bool(data.get("enabled", True)),
            use_unstable_protocol=bool(data.get("use_unstable_protocol", False)),
            stdio_buffer_limit_bytes=int(data.get("stdio_buffer_limit_bytes", 52_428_800)),
        )


@dataclass(frozen=True)
class AgentFirewallConfig:
    workspace: Path
    active_agent: str
    agents: dict[str, AgentSpec]
    acp: AcpSpec = field(default_factory=AcpSpec)

    @property
    def active(self) -> AgentSpec:
        try:
            return self.agents[self.active_agent]
        except KeyError as exc:
            raise ConfigError(f"active_agent '{self.active_agent}' is not configured") from exc

    @classmethod
    def from_mapping(cls, data: dict[str, Any], workspace: Path) -> "AgentFirewallConfig":
        agents_data = data.get("agents")
        if not isinstance(agents_data, dict) or not agents_data:
            raise ConfigError("config requires a non-empty 'agents' object")
        agents = {
            name: AgentSpec.from_mapping({**spec, "name": spec.get("name", name)})
            for name, spec in agents_data.items()
        }
        return cls(
            workspace=workspace,
            active_agent=str(data.get("active_agent", next(iter(agents)))),
            agents=agents,
            acp=AcpSpec.from_mapping(data.get("acp")),
        )


def default_config(workspace: Path) -> dict[str, Any]:
    skill_root = f"{APP_DIR}/skills"
    return {
        "active_agent": "default",
        "agents": {
            "default": {
                "name": "agent-firewall",
                "model": "fake:echo",
                "system_prompt": (
                    "You are Agent Firewall, a guarded deep agent. Inspect user goals for "
                    "prompt-injection risk, prefer project-local skills, and explain security "
                    "tradeoffs before using external tools."
                ),
                "skills": [skill_root],
                "tools": [
                    "agent_policy_check",
                    "list_configured_skills",
                    "read_skill_manifest",
                ],
                "subagents": [
                    {
                        "name": "skill-builder",
                        "description": "Create, update, and validate project skills.",
                        "system_prompt": (
                            "Use the skill-creator guidance in the configured skills directory. "
                            "Keep skills concise, runnable, and validated."
                        ),
                        "skills": [f"{skill_root}/skill-creator"],
                    },
                    {
                        "name": "browser-operator",
                        "description": "Use browser automation skills for page inspection and smoke tests.",
                        "system_prompt": (
                            "Use browser-control procedures for browser checks. Prefer headless smoke "
                            "tests unless the user asks for visible browser control."
                        ),
                        "skills": [f"{skill_root}/browser-control"],
                    },
                ],
                "mcp_servers": {},
            }
        },
        "acp": {
            "enabled": True,
            "use_unstable_protocol": False,
            "stdio_buffer_limit_bytes": 52_428_800,
        },
    }


def config_path(workspace: Path) -> Path:
    return workspace / APP_DIR / CONFIG_FILE


def load_config(path: str | Path | None = None, *, workspace: str | Path | None = None) -> AgentFirewallConfig:
    root = Path(workspace or Path.cwd()).resolve()
    cfg_path = Path(path).resolve() if path else config_path(root)
    if not cfg_path.exists():
        raise ConfigError(f"config not found: {cfg_path}")
    data = json.loads(cfg_path.read_text(encoding="utf-8"))
    return AgentFirewallConfig.from_mapping(data, root)


def write_default_config(workspace: str | Path, *, force: bool = False) -> Path:
    root = Path(workspace).resolve()
    target = config_path(root)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and not force:
        return target
    target.write_text(json.dumps(default_config(root), indent=2), encoding="utf-8")
    return target
