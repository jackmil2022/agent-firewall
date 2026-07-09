from __future__ import annotations

import asyncio
import inspect
import json
import subprocess
import sys
from pathlib import Path
from typing import Any
from uuid import uuid4

from .config import APP_DIR, AgentFirewallConfig
from .engine import build_agent_sync
from .flow import FlowNode, FlowSpec, load_flow
from .handoff import Handoff, StepResult, TaskPacket
from .skills import _read_manifest
from .store import AgentFirewallStore


class RunnerError(RuntimeError):
    """Raised when a flow run cannot continue."""


def run_flow(
    config: AgentFirewallConfig,
    *,
    goal: str,
    flow_name: str = "default",
    flow_path: str | Path | None = None,
) -> dict[str, Any]:
    flow = load_flow(config.workspace, config, name=flow_name, path=flow_path)
    store = AgentFirewallStore(config.workspace)
    run_id = uuid4().hex
    store.create_run(run_id, goal, flow_name)
    store.log_event(run_id, "run_started", {"goal": goal, "flow_name": flow_name})

    incoming: dict[str, list[dict[str, Any]]] = {node.id: [] for node in flow.nodes}
    nodes = {node.id: node for node in flow.nodes}
    queue = [node.id for node in flow.start_nodes()]
    visits: dict[str, int] = {}
    step_count = 0
    final_summaries: list[str] = []
    status = "success"

    try:
        while queue and step_count < flow.max_steps:
            node_id = queue.pop(0)
            node = nodes[node_id]
            visits[node_id] = visits.get(node_id, 0) + 1
            if visits[node_id] > flow.max_loop_iterations:
                raise RunnerError(f"node exceeded max loop iterations: {node_id}")
            packet = TaskPacket(run_id=run_id, goal=goal, node_id=node_id, incoming=incoming[node_id])
            store.log_event(run_id, "node_started", {"node": _node_payload(node), "incoming": packet.incoming}, node_id)
            result = _run_node(config, node, packet)
            step_count += 1
            final_summaries.append(f"{node_id}: {result.summary}")
            store.log_event(run_id, "node_finished", result.to_mapping(), node_id)

            routed = False
            for edge in flow.outgoing(node_id, result.status):
                handoff = Handoff(
                    run_id=run_id,
                    goal=goal,
                    from_node=node_id,
                    to_node=edge.to_node,
                    summary=result.summary,
                    artifacts=result.artifacts,
                    next_input=str(result.handoff.get("next_input") or result.summary),
                    status=result.status,
                ).to_mapping()
                incoming[edge.to_node].append(_filter_handoff(handoff, edge.pass_fields))
                store.log_event(run_id, "handoff_created", handoff, node_id)
                if edge.to_node not in queue:
                    queue.append(edge.to_node)
                routed = True
            if result.status != "success" and not routed:
                status = result.status
                break
        if queue and step_count >= flow.max_steps:
            raise RunnerError(f"flow exceeded max steps: {flow.max_steps}")
    except Exception as exc:
        status = "failed"
        store.log_event(run_id, "run_failed", {"error": str(exc)})
        final_summaries.append(f"failed: {exc}")

    final_summary = "\n".join(final_summaries)
    store.finish_run(run_id, status, final_summary)
    store.log_event(run_id, "run_finished", {"status": status, "summary": final_summary})
    return {"run_id": run_id, "status": status, "summary": final_summary, "database": str(store.path)}


def _run_node(config: AgentFirewallConfig, node: FlowNode, packet: TaskPacket) -> StepResult:
    if node.type == "agent":
        return _run_agent_node(config, node, packet)
    if node.type == "skill":
        return _run_skill_node(config, node, packet)
    if node.type == "mcp":
        return _run_mcp_node(config, node)
    return StepResult(status="failed", summary=f"unknown node type: {node.type}")


def _run_agent_node(config: AgentFirewallConfig, node: FlowNode, packet: TaskPacket) -> StepResult:
    agent_name = node.ref or config.active_agent
    agent = build_agent_sync(config, agent_name)
    response = _invoke_agent(agent, packet.prompt())
    return StepResult(
        status="success",
        summary=_response_text(response),
        handoff={"next_input": _response_text(response)},
    )


def _invoke_agent(agent: Any, prompt: str) -> Any:
    payload = {"messages": [{"role": "user", "content": prompt}]}
    if hasattr(agent, "invoke"):
        result = agent.invoke(payload)
    elif callable(agent):
        result = agent(payload)
    else:
        return repr(agent)
    if inspect.isawaitable(result):
        raise RunnerError("async agent invocation is not supported by the sync runner yet")
    return result


def _run_skill_node(config: AgentFirewallConfig, node: FlowNode, packet: TaskPacket) -> StepResult:
    skill_dir = _resolve_path(config.workspace, node.ref or node.meta.get("path") or "")
    if not (skill_dir / "SKILL.md").exists():
        skill_dir = config.workspace / APP_DIR / "skills" / (node.ref or node.id.split(":", 1)[-1])
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        return StepResult(status="failed", summary=f"skill manifest not found: {skill_md}")
    manifest = _read_manifest(skill_md)
    script = node.params.get("script")
    if script:
        return _run_skill_script(skill_dir, str(script), packet)
    summary = f"loaded skill {manifest.name}: {manifest.description}"
    return StepResult(status="success", summary=summary, handoff={"next_input": packet.prompt()})


def _run_skill_script(skill_dir: Path, script: str, packet: TaskPacket) -> StepResult:
    script_path = (skill_dir / script).resolve()
    try:
        script_path.relative_to(skill_dir.resolve())
    except ValueError:
        return StepResult(status="failed", summary="skill script must stay inside the skill directory")
    if not script_path.exists():
        return StepResult(status="failed", summary=f"skill script not found: {script}")
    completed = subprocess.run(
        [sys.executable, str(script_path)],
        input=json.dumps({"goal": packet.goal, "incoming": packet.incoming}, ensure_ascii=False),
        text=True,
        capture_output=True,
        timeout=60,
        check=False,
    )
    summary = (completed.stdout or completed.stderr).strip()
    return StepResult(
        status="success" if completed.returncode == 0 else "failed",
        summary=summary or f"script exited with {completed.returncode}",
        handoff={"next_input": summary},
    )


def _run_mcp_node(config: AgentFirewallConfig, node: FlowNode) -> StepResult:
    tool_name = node.params.get("tool")
    if not tool_name:
        # ponytail: direct MCP calls need an explicit tool name and arguments; otherwise MCP is loaded through agent tools.
        return StepResult(
            status="success",
            summary=f"mcp server available for agent tool use: {node.ref}",
            handoff={"next_input": f"MCP server {node.ref} is available through the configured agent."},
        )
    return asyncio.run(_call_mcp_tool(config, node, str(tool_name), dict(node.params.get("args") or {})))


async def _call_mcp_tool(config: AgentFirewallConfig, node: FlowNode, tool_name: str, args: dict[str, Any]) -> StepResult:
    try:
        from langchain_mcp_adapters.client import MultiServerMCPClient
    except ImportError:
        return StepResult(status="failed", summary="langchain-mcp-adapters is not installed")

    server_key = str(node.params.get("server") or node.ref)
    agent_key = str(node.meta.get("agent") or config.active_agent)
    server_config = config.agents.get(agent_key, config.active).mcp_servers.get(server_key)
    if not server_config and isinstance(node.meta.get("config"), dict):
        server_config = node.meta["config"]
    if not server_config:
        return StepResult(status="failed", summary=f"mcp server not configured: {server_key}")

    tools = await MultiServerMCPClient({server_key: server_config}).get_tools()
    tool = next((item for item in tools if getattr(item, "name", "") == tool_name), None)
    if not tool:
        return StepResult(status="failed", summary=f"mcp tool not found: {tool_name}")
    if hasattr(tool, "ainvoke"):
        result = await tool.ainvoke(args)
    elif hasattr(tool, "invoke"):
        result = tool.invoke(args)
    else:
        result = tool(**args)
    summary = _response_text(result)
    return StepResult(
        status="success",
        summary=summary,
        handoff={"next_input": summary},
    )


def _resolve_path(workspace: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else (workspace / path)


def _response_text(response: Any) -> str:
    if isinstance(response, str):
        return response
    if isinstance(response, dict):
        messages = response.get("messages")
        if isinstance(messages, list) and messages:
            last = messages[-1]
            content = getattr(last, "content", None) or (last.get("content") if isinstance(last, dict) else None)
            if content:
                return str(content)
    content = getattr(response, "content", None)
    return str(content if content is not None else response)


def _node_payload(node: FlowNode) -> dict[str, Any]:
    return {"id": node.id, "type": node.type, "label": node.label, "ref": node.ref, "params": node.params}


def _filter_handoff(handoff: dict[str, Any], fields: list[str]) -> dict[str, Any]:
    if not fields:
        return handoff
    required = {"run_id", "goal", "from_node", "to_node", "status"}
    return {key: value for key, value in handoff.items() if key in required or key in fields}
