from __future__ import annotations

from .config import AgentFirewallConfig
from .engine import build_agent


async def serve_acp(config: AgentFirewallConfig, agent_name: str | None = None) -> None:
    try:
        from deepagents_acp.server import AgentServerACP, run_acp_agent
    except ImportError as exc:
        raise RuntimeError("deepagents-acp is not installed. Run: pip install -e .") from exc

    agent = await build_agent(config, agent_name)
    server = AgentServerACP(agent=agent)
    await run_acp_agent(
        server,
        use_unstable_protocol=config.acp.use_unstable_protocol,
        stdio_buffer_limit_bytes=config.acp.stdio_buffer_limit_bytes,
    )
