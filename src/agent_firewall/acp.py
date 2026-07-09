from __future__ import annotations

import asyncio
from typing import Any

from .config import AgentFirewallConfig
from .engine import build_agent
from .runner import run_flow


async def serve_acp(
    config: AgentFirewallConfig,
    agent_name: str | None = None,
    *,
    runner: bool = False,
    goal: str = "Run the configured Agent Firewall flow.",
) -> None:
    try:
        from deepagents_acp.server import AgentServerACP, run_acp_agent
    except ImportError as exc:
        raise RuntimeError("deepagents-acp is not installed. Run: pip install -e .") from exc

    agent = RunnerAcpAgent(config, goal) if runner else await build_agent(config, agent_name)
    server = AgentServerACP(agent=agent)
    await run_acp_agent(
        server,
        use_unstable_protocol=config.acp.use_unstable_protocol,
        stdio_buffer_limit_bytes=config.acp.stdio_buffer_limit_bytes,
    )


class RunnerAcpAgent:
    def __init__(self, config: AgentFirewallConfig, default_goal: str) -> None:
        self.config = config
        self.default_goal = default_goal

    def invoke(self, payload: Any) -> dict[str, Any]:
        return run_flow(self.config, goal=_goal_from_payload(payload) or self.default_goal)

    async def ainvoke(self, payload: Any) -> dict[str, Any]:
        return await asyncio.to_thread(self.invoke, payload)


def _goal_from_payload(payload: Any) -> str:
    if isinstance(payload, str):
        return payload
    if not isinstance(payload, dict):
        return ""
    messages = payload.get("messages")
    if isinstance(messages, list) and messages:
        last = messages[-1]
        if isinstance(last, dict):
            return str(last.get("content") or "")
        return str(getattr(last, "content", "") or "")
    return str(payload.get("goal") or payload.get("input") or "")
