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
    interrupt_on: dict[str, bool | dict[str, Any]] = field(default_factory=dict)
    response_format: dict[str, Any] | None = None
    checkpoint: bool = True

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
            interrupt_on=dict(data.get("interrupt_on", {})),
            response_format=dict(data["response_format"]) if isinstance(data.get("response_format"), dict) else None,
            checkpoint=bool(data.get("checkpoint", True)),
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
class PolicySpec:
    require_approval: list[str] = field(default_factory=list)
    allowed_commands: list[str] = field(default_factory=lambda: ["python"])
    allow_network: bool = False
    exposed_env: list[str] = field(default_factory=list)

    @classmethod
    def from_mapping(cls, data: dict[str, Any] | None) -> "PolicySpec":
        data = data or {}
        return cls(
            require_approval=[str(item) for item in data.get("require_approval", [])],
            allowed_commands=[str(item) for item in data.get("allowed_commands", ["python"])],
            allow_network=bool(data.get("allow_network", False)),
            exposed_env=[str(item) for item in data.get("exposed_env", [])],
        )


@dataclass(frozen=True)
class AgentFirewallConfig:
    workspace: Path
    active_agent: str
    agents: dict[str, AgentSpec]
    models: dict[str, dict[str, Any]] = field(default_factory=dict)
    acp: AcpSpec = field(default_factory=AcpSpec)
    policy: PolicySpec = field(default_factory=PolicySpec)

    @property
    def active(self) -> AgentSpec:
        try:
            return self.agents[self.active_agent]
        except KeyError as exc:
            raise ConfigError(f"active_agent '{self.active_agent}' is not configured") from exc

    @classmethod
    def from_mapping(cls, data: dict[str, Any], workspace: Path) -> "AgentFirewallConfig":
        data = normalize_config_mapping(data)
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
            models=_models_from_mapping(data),
            acp=AcpSpec.from_mapping(data.get("acp")),
            policy=PolicySpec.from_mapping(data.get("policy")),
        )


def default_config(workspace: Path) -> dict[str, Any]:
    skill_root = f"{APP_DIR}/skills"
    return {
        "active_agent": "default",
        "models": {
            "fake-echo": {
                "display_name": "Fake Echo",
                "model": "fake:echo",
                "provider": "fake",
                "base_url": "",
                "api_key_env": "",
                "enabled": True,
                "params": {"temperature": 0.2, "max_tokens": 4096},
            }
        },
        "agents": {
            "default": {
                "name": "agent-firewall",
                "model": "fake-echo",
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
                "interrupt_on": {},
                "response_format": None,
                "checkpoint": True,
            }
        },
        "acp": {
            "enabled": True,
            "use_unstable_protocol": False,
            "stdio_buffer_limit_bytes": 52_428_800,
        },
        "policy": {
            "require_approval": [],
            "allowed_commands": ["python"],
            "allow_network": False,
            "exposed_env": [],
        },
    }


def _models_from_mapping(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    raw = data.get("models") or {}
    if not isinstance(raw, dict):
        raise ConfigError("config field 'models' must be an object")
    models = {str(name): dict(value) for name, value in raw.items() if isinstance(value, dict)}
    for spec in (data.get("agents") or {}).values():
        model = str(spec.get("model") or "")
        if model and model not in models and ":" in model:
            models.setdefault(
                model,
                {
                    "display_name": model,
                    "model": model,
                    "provider": model.split(":", 1)[0],
                    "base_url": "",
                    "api_key_env": "",
                    "enabled": True,
                    "params": {},
                },
            )
    return models


def config_path(workspace: Path) -> Path:
    return workspace / APP_DIR / CONFIG_FILE


def load_config(path: str | Path | None = None, *, workspace: str | Path | None = None) -> AgentFirewallConfig:
    root = Path(workspace or Path.cwd()).resolve()
    if path:
        cfg_path = Path(path).resolve()
        if not cfg_path.exists():
            raise ConfigError(f"config not found: {cfg_path}")
        data = json.loads(cfg_path.read_text(encoding="utf-8"))
        return AgentFirewallConfig.from_mapping(data, root)
    data = load_config_mapping(root)
    return AgentFirewallConfig.from_mapping(data, root)


def load_config_mapping(workspace: str | Path) -> dict[str, Any]:
    root = Path(workspace).resolve()
    from .store import AgentFirewallStore

    store = AgentFirewallStore(root)
    data = store.get_config()
    if data:
        normalized = normalize_config_mapping(data)
        if normalized != data:
            store.save_config(normalized)
        return normalized
    cfg_path = config_path(root)
    if not cfg_path.exists():
        raise ConfigError(f"config not found in sqlite or json: {store.path}")
    data = json.loads(cfg_path.read_text(encoding="utf-8"))
    data = normalize_config_mapping(data)
    store.save_config(data)
    return data


def write_default_config(workspace: str | Path, *, force: bool = False) -> Path:
    root = Path(workspace).resolve()
    from .store import AgentFirewallStore

    store = AgentFirewallStore(root)
    if store.get_config() and not force:
        return store.path
    store.save_config(default_config(root))
    return store.path


def normalize_config_mapping(data: dict[str, Any]) -> dict[str, Any]:
    result = dict(data)
    agents = result.get("agents")
    if not isinstance(agents, dict) or not agents:
        raise ConfigError("config requires a non-empty 'agents' object")
    result["models"] = _models_from_mapping(result)
    for key, spec in agents.items():
        if not isinstance(spec, dict):
            raise ConfigError(f"agent '{key}' must be an object")
        model_name = str(spec.get("model") or "")
        if not model_name:
            raise ConfigError(f"agent '{key}' requires model")
        if model_name not in result["models"]:
            result["models"][model_name] = {
                "display_name": model_name,
                "model": model_name,
                "provider": model_name.split(":", 1)[0] if ":" in model_name else "",
                "base_url": "",
                "api_key_env": "",
                "enabled": True,
                "params": {},
            }
        model_spec = result["models"][model_name]
        if not model_spec.get("model"):
            raise ConfigError(f"model '{model_name}' requires model id")
    for name, model_spec in result["models"].items():
        if not str(model_spec.get("model") or "").strip():
            raise ConfigError(f"model '{name}' requires model id")
        model_spec.setdefault("display_name", name)
        if not str(model_spec.get("provider") or "").strip():
            model_spec["provider"] = str(model_spec["model"]).split(":", 1)[0] if ":" in str(model_spec["model"]) else "custom"
        model_spec.setdefault("base_url", "")
        model_spec.setdefault("api_key_env", "")
        model_spec.setdefault("enabled", True)
        model_spec.setdefault("params", {})
    return result
