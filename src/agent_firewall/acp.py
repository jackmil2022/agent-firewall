from __future__ import annotations

import asyncio
from typing import Any

from .config import AgentFirewallConfig
from .engine import build_agent
from .policy import PolicyViolation, check_operation, policy_from_config
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

    agent = RunnerAcpAgent(config, goal) if runner else GuardedAcpAgent(config, agent_name)
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


class GuardedAcpAgent:
    def __init__(self, config: AgentFirewallConfig, agent_name: str | None = None) -> None:
        self.config = config
        self.agent_name = agent_name

    def invoke(self, payload: Any) -> Any:
        return asyncio.run(self.ainvoke(payload))

    async def ainvoke(self, payload: Any) -> Any:
        approved = False
        policy = policy_from_config(self.config)
        decision = check_operation(policy, kind="agent", approved=approved)
        if not decision["allowed"]:
            return _policy_response(decision, "agent")
        try:
            agent = await build_agent(
                self.config,
                self.agent_name,
                policy=policy,
                approved=approved,
                approved_operation="agent" if approved else "",
            )
        except PolicyViolation as exc:
            return _policy_response(exc.decision, exc.operation or "agent")
        forwarded = dict(payload) if isinstance(payload, dict) else payload
        if isinstance(forwarded, dict):
            forwarded.pop("approved", None)
        if hasattr(agent, "ainvoke"):
            return await agent.ainvoke(forwarded)
        return await asyncio.to_thread(agent.invoke, forwarded)


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


def _policy_response(decision: dict[str, Any], operation: str) -> dict[str, Any]:
    approval = decision["code"] == "approval_required"
    return {
        "status": "needs_input" if approval else "blocked",
        "summary": decision["message"],
        "output": {
            "pause": {
                "kind": f"policy_approval:{operation}" if approval else "policy_block",
                "operation": operation,
            }
        },
        "error": {
            "code": decision["code"],
            "message": decision["message"],
            "retryable": False,
        },
    }
