from __future__ import annotations

import asyncio
import inspect
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

from .config import APP_DIR, AgentFirewallConfig
from .engine import build_agent_sync
from .flow import FlowEdge, FlowNode, FlowSpec, load_flow, validate_flow
from .handoff import Handoff, StepResult, TaskPacket
from .policy import ExecutionPolicy, check_operation
from .skills import _read_manifest
from .store import AgentFirewallStore


class RunnerError(RuntimeError):
    """Raised when a flow run cannot continue."""


PAUSE_STATUSES = {"needs_input", "blocked"}
RESUMABLE_STATUSES = PAUSE_STATUSES | {"failed"}


def run_flow(
    config: AgentFirewallConfig,
    *,
    goal: str,
    flow_name: str = "default",
    flow_path: str | Path | None = None,
) -> dict[str, Any]:
    flow = load_flow(config.workspace, config, name=flow_name, path=flow_path)
    validate_flow(flow, config, check_resources=True)
    store = AgentFirewallStore(config.workspace)
    run_id = uuid4().hex
    store.create_run(run_id, goal, flow_name, flow.to_mapping())
    store.log_event(run_id, "run_started", {"goal": goal, "flow_name": flow_name})
    state = _new_state(flow)
    store.save_checkpoint(run_id, state)
    return _execute_flow(config, flow, store, run_id, goal, state)


def resume_flow(config: AgentFirewallConfig, run_id: str, *, correction: str = "") -> dict[str, Any]:
    store = AgentFirewallStore(config.workspace)
    run = store.get_run(run_id)
    if not run:
        raise RunnerError(f"run not found: {run_id}")
    if run["status"] not in RESUMABLE_STATUSES:
        raise RunnerError(f"run is not resumable: {run_id} ({run['status']})")
    if not run.get("flow_snapshot") or not run.get("state_json"):
        raise RunnerError(f"run has no resumable checkpoint: {run_id}")
    flow = FlowSpec.from_mapping(run["flow_snapshot"])
    validate_flow(flow, config, check_resources=True)
    state = dict(run["state_json"])
    paused_node = str(state.get("paused_node") or state.get("failed_node") or "")
    if not paused_node:
        raise RunnerError(f"run checkpoint has no resumable node: {run_id}")
    if run["status"] == "failed":
        reset_nodes = _descendants(flow, paused_node)
        state["completed"] = {
            key: value for key, value in (state.get("completed") or {}).items() if key not in reset_nodes
        }
        state["attempts"] = {
            key: value for key, value in (state.get("attempts") or {}).items() if key not in reset_nodes
        }
        state["summaries"] = [
            summary
            for summary in state.get("summaries") or []
            if not any(str(summary).startswith(f"{node_id}:") for node_id in reset_nodes)
        ]
    state["paused_node"] = ""
    state["failed_node"] = ""
    state.setdefault("corrections", {})[paused_node] = correction
    state.setdefault("correction_kinds", {})[paused_node] = str(
        (state.get("pause") or {}).get("kind") or "operator"
    )
    state.setdefault("attempts", {})[paused_node] = 0
    store.reopen_run(run_id)
    store.log_event(run_id, "run_resumed", {"node_id": paused_node, "correction": correction}, paused_node)
    return _execute_flow(config, flow, store, run_id, str(run["goal"]), state)


def _new_state(flow: FlowSpec) -> dict[str, Any]:
    return {
        "completed": {},
        "attempts": {},
        "summaries": [],
        "paused_node": "",
        "failed_node": "",
        "corrections": {},
        "correction_kinds": {},
        "max_steps": flow.max_steps,
    }


def _execute_flow(
    config: AgentFirewallConfig,
    flow: FlowSpec,
    store: AgentFirewallStore,
    run_id: str,
    goal: str,
    state: dict[str, Any],
) -> dict[str, Any]:
    nodes = {node.id: node for node in flow.nodes}
    completed: dict[str, dict[str, Any]] = dict(state.get("completed") or {})
    attempts: dict[str, int] = {str(key): int(value) for key, value in (state.get("attempts") or {}).items()}
    summaries: list[str] = [str(item) for item in state.get("summaries") or []]
    corrections: dict[str, str] = {str(key): str(value) for key, value in (state.get("corrections") or {}).items()}
    correction_kinds: dict[str, str] = {
        str(key): str(value) for key, value in (state.get("correction_kinds") or {}).items()
    }

    while len(completed) < len(nodes):
        if len([result for result in completed.values() if result["status"] != "skipped"]) >= flow.max_steps:
            return _finish_failed(store, run_id, state, summaries, f"flow exceeded max steps: {flow.max_steps}")

        node = _next_ready_node(flow, completed)
        if node is None:
            return _finish_failed(store, run_id, state, summaries, "flow cannot make progress")

        incoming_edges = flow.incoming(node.id)
        active_edges = [edge for edge in incoming_edges if _edge_active(edge, completed)]
        if incoming_edges and not active_edges:
            result = StepResult(status="skipped", summary="no active incoming route")
            completed[node.id] = result.to_mapping()
            store.log_event(run_id, "node_skipped", result.to_mapping(), node.id)
            _save_state(store, run_id, state, completed, attempts, summaries, corrections)
            continue

        handoffs = [_handoff_for_edge(edge, completed) for edge in active_edges]
        packet = TaskPacket(
            run_id=run_id,
            goal=goal,
            node_id=node.id,
            incoming=handoffs,
            correction=corrections.pop(node.id, ""),
            correction_kind=correction_kinds.pop(node.id, ""),
            idempotency_key=f"{run_id}:{node.id}",
        )
        store.log_event(
            run_id,
            "node_started",
            {"node": _node_payload(node), "incoming": packet.incoming},
            node.id,
        )
        result, node_attempts = _run_with_policy(config, node, packet, attempts.get(node.id, 0), store)
        attempts[node.id] = node_attempts
        store.log_event(run_id, "node_finished", result.to_mapping(), node.id)

        matching_edges = flow.outgoing(node.id, result.status)
        if result.status in PAUSE_STATUSES and not matching_edges:
            state["paused_node"] = node.id
            state["pause"] = result.output.get("pause") or {}
            _save_state(
                store,
                run_id,
                state,
                completed,
                attempts,
                summaries,
                corrections,
                correction_kinds,
                status=result.status,
            )
            store.log_event(run_id, "run_paused", result.to_mapping(), node.id)
            return _run_result(store, run_id, result.status, summaries + [f"{node.id}: {result.summary}"])

        completed[node.id] = result.to_mapping()
        summaries.append(f"{node.id}: {result.summary}")
        for edge in matching_edges:
            store.log_event(
                run_id,
                "handoff_created",
                _create_handoff(run_id, goal, node.id, edge.to_node, result),
                node.id,
            )
        _save_state(store, run_id, state, completed, attempts, summaries, corrections, correction_kinds)

        if result.status == "failed" and not matching_edges:
            return _finish_failed(store, run_id, state, summaries, result.summary, failed_node=node.id)

    end = next(node for node in flow.nodes if node.type == "end")
    end_result = completed.get(end.id, {})
    if end_result.get("status") != "success":
        return _finish_failed(store, run_id, state, summaries, "flow did not reach end through an active route")
    summary = "\n".join(summaries)
    store.finish_run(run_id, "success", summary)
    store.log_event(run_id, "run_finished", {"status": "success", "summary": summary})
    return _run_result(store, run_id, "success", summaries)


def _next_ready_node(flow: FlowSpec, completed: dict[str, dict[str, Any]]) -> FlowNode | None:
    for node in flow.nodes:
        if node.id in completed:
            continue
        if all(edge.from_node in completed for edge in flow.incoming(node.id)):
            return node
    return None


def _descendants(flow: FlowSpec, node_id: str) -> set[str]:
    result: set[str] = set()
    pending = [node_id]
    while pending:
        current = pending.pop()
        if current in result:
            continue
        result.add(current)
        pending.extend(edge.to_node for edge in flow.edges if edge.from_node == current)
    return result


def _edge_active(edge: FlowEdge, completed: dict[str, dict[str, Any]]) -> bool:
    source_status = completed[edge.from_node]["status"]
    return source_status != "skipped" and edge.on in (source_status, "always")


def _handoff_for_edge(edge: FlowEdge, completed: dict[str, dict[str, Any]]) -> dict[str, Any]:
    result = completed[edge.from_node]
    handoff = dict(result.get("handoff") or {})
    handoff.setdefault("from_node", edge.from_node)
    handoff.setdefault("to_node", edge.to_node)
    handoff.setdefault("status", result["status"])
    handoff.setdefault("summary", result.get("summary", ""))
    handoff.setdefault("output", result.get("output", {}))
    return _filter_handoff(handoff, edge.pass_fields)


def _run_with_policy(
    config: AgentFirewallConfig,
    node: FlowNode,
    packet: TaskPacket,
    previous_attempts: int,
    store: AgentFirewallStore,
) -> tuple[StepResult, int]:
    retry = dict(node.params.get("retry") or {})
    max_attempts = max(1, int(retry.get("max_attempts", 1)))
    delay_seconds = max(0.0, float(retry.get("delay_seconds", 0)))
    attempt = previous_attempts
    while attempt < max_attempts:
        attempt += 1
        try:
            result = _run_node(config, node, packet)
        except Exception as exc:
            result = _exception_result(exc)
        result = _validate_result(node, result)
        if result.status != "failed" or not result.error.get("retryable") or attempt >= max_attempts:
            return result, attempt
        store.log_event(
            packet.run_id,
            "node_retrying",
            {"attempt": attempt, "max_attempts": max_attempts, "error": result.error},
            node.id,
        )
        if delay_seconds:
            time.sleep(delay_seconds)
    raise RunnerError(f"node retry loop ended unexpectedly: {node.id}")


def _exception_result(exc: Exception) -> StepResult:
    code = "timeout" if isinstance(exc, (TimeoutError, subprocess.TimeoutExpired, asyncio.TimeoutError)) else "exception"
    return StepResult(
        status="failed",
        summary=str(exc) or type(exc).__name__,
        error={
            "code": code,
            "message": str(exc) or type(exc).__name__,
            "retryable": code == "timeout",
            "type": type(exc).__name__,
        },
    )


def _validate_result(node: FlowNode, result: StepResult) -> StepResult:
    if result.status != "success":
        return result
    rules = dict(node.params.get("validate") or {})
    failures: list[str] = []
    for key in rules.get("required", []):
        if key not in result.output or result.output[key] in (None, ""):
            failures.append(f"missing output field: {key}")
    for key, expected in dict(rules.get("equals") or {}).items():
        if result.output.get(key) != expected:
            failures.append(f"output field {key} must equal {expected!r}")
    summary_contains = rules.get("summary_contains")
    if summary_contains and str(summary_contains) not in result.summary:
        failures.append(f"summary must contain: {summary_contains}")
    min_artifacts = int(rules.get("min_artifacts", 0))
    if len(result.artifacts) < min_artifacts:
        failures.append(f"expected at least {min_artifacts} artifact(s)")
    if not failures:
        return result
    message = "; ".join(failures)
    return StepResult(
        status="failed",
        summary=f"output validation failed: {message}",
        output=result.output,
        error={"code": "validation_error", "message": message, "retryable": True},
        artifacts=result.artifacts,
        handoff=result.handoff,
    )


def _save_state(
    store: AgentFirewallStore,
    run_id: str,
    state: dict[str, Any],
    completed: dict[str, dict[str, Any]],
    attempts: dict[str, int],
    summaries: list[str],
    corrections: dict[str, str],
    correction_kinds: dict[str, str] | None = None,
    *,
    status: str = "running",
) -> None:
    state.update(
        {
            "completed": completed,
            "attempts": attempts,
            "summaries": summaries,
            "corrections": corrections,
            "correction_kinds": correction_kinds or {},
        }
    )
    store.save_checkpoint(run_id, state, status=status)


def _finish_failed(
    store: AgentFirewallStore,
    run_id: str,
    state: dict[str, Any],
    summaries: list[str],
    error: str,
    *,
    failed_node: str = "",
) -> dict[str, Any]:
    final_summaries = summaries + [f"failed: {error}"]
    summary = "\n".join(final_summaries)
    state["failed_node"] = failed_node
    store.save_checkpoint(run_id, state, status="failed")
    store.log_event(run_id, "run_failed", {"error": error})
    store.finish_run(run_id, "failed", summary)
    store.log_event(run_id, "run_finished", {"status": "failed", "summary": summary})
    return _run_result(store, run_id, "failed", final_summaries)


def _run_result(
    store: AgentFirewallStore,
    run_id: str,
    status: str,
    summaries: list[str],
) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "status": status,
        "summary": "\n".join(summaries),
        "database": str(store.path),
        "events": store.list_events(run_id),
    }


def _run_node(config: AgentFirewallConfig, node: FlowNode, packet: TaskPacket) -> StepResult:
    return run_capability_node(config, node, packet)


def run_capability_node(
    config: AgentFirewallConfig,
    node: FlowNode,
    packet: TaskPacket,
    *,
    policy: dict[str, Any] | None = None,
    approved: bool = False,
) -> StepResult:
    policy_data = policy or {}
    execution_policy = ExecutionPolicy(
        workspace=config.workspace,
        require_approval=[str(item) for item in policy_data.get("require_approval", [])],
        allowed_commands=[str(item) for item in policy_data.get("allowed_commands", ["python"])],
        allow_network=bool(policy_data.get("allow_network", False)),
        exposed_env=[str(item) for item in policy_data.get("exposed_env", [])],
    )
    operation = node.type
    target_path = None
    if node.type == "skill":
        operation = "script"
        skill_dir = _resolve_path(config.workspace, node.ref or str(node.meta.get("path") or ""))
        target_path = skill_dir / str(node.params.get("script") or "")
    elif node.type == "mcp":
        operation = f"mcp:{node.params.get('tool') or 'call'}"
    decision = check_operation(execution_policy, kind=operation, path=target_path, approved=approved)
    if not decision["allowed"]:
        status = "needs_input" if decision["code"] == "approval_required" else "blocked"
        return StepResult(
            status=status,
            summary=decision["message"],
            output={"pause": {"kind": "policy_approval", "operation": operation}},
            error={"code": decision["code"], "message": decision["message"], "retryable": False},
        )
    if node.type in ("start", "end"):
        return _run_boundary_node(node, packet)
    if node.type == "agent":
        return _run_agent_node(config, node, packet)
    if node.type == "skill":
        return _run_skill_node(config, node, packet)
    if node.type == "mcp":
        return _run_mcp_node(config, node, packet)
    return StepResult(
        status="failed",
        summary=f"unknown node type: {node.type}",
        error={"code": "unknown_node_type", "message": node.type, "retryable": False},
    )


def _run_boundary_node(node: FlowNode, packet: TaskPacket) -> StepResult:
    summary = "flow started" if node.type == "start" else "flow finished"
    return StepResult(
        status="success",
        summary=summary,
        output={"prompt": packet.prompt()},
        handoff={"next_input": packet.prompt()},
    )


def _run_agent_node(config: AgentFirewallConfig, node: FlowNode, packet: TaskPacket) -> StepResult:
    if node.params.get("requires_approval") and not packet.correction:
        return StepResult(
            status="needs_input",
            summary=str(node.params.get("approval_prompt") or f"approval required before running {node.label}"),
            output={"pause": {"kind": "node_approval"}},
            error={"code": "approval_required", "message": "operator approval required", "retryable": False},
        )
    agent_name = node.ref or config.active_agent
    agent = build_agent_sync(config, agent_name)
    response = _invoke_agent(
        agent,
        packet.prompt(),
        run_id=packet.run_id,
        node_id=node.id,
        correction=packet.correction,
        correction_kind=packet.correction_kind,
    )
    if isinstance(response, dict) and response.get("__interrupt__"):
        return StepResult(
            status="needs_input",
            summary="agent execution requires operator input",
            output={
                "interrupts": _jsonable(response["__interrupt__"]),
                "pause": {"kind": "agent_interrupt"},
            },
            error={"code": "agent_interrupted", "message": "agent interrupted", "retryable": False},
        )
    summary = _response_text(response)
    output = _response_output(response)
    return StepResult(
        status="success",
        summary=summary,
        output=output,
        handoff={"next_input": summary, "output": output},
    )


def _invoke_agent(
    agent: Any,
    prompt: str,
    *,
    run_id: str,
    node_id: str,
    correction: str = "",
    correction_kind: str = "",
) -> Any:
    payload: Any = {"messages": [{"role": "user", "content": prompt}]}
    if correction and correction_kind == "agent_interrupt":
        try:
            decisions = json.loads(correction)
        except json.JSONDecodeError:
            decisions = None
        if isinstance(decisions, list):
            from langgraph.types import Command

            payload = Command(resume={"decisions": decisions})
    config = {"configurable": {"thread_id": f"{run_id}:{node_id}"}}
    if hasattr(agent, "invoke"):
        result = agent.invoke(payload, config=config)
    elif callable(agent):
        result = agent(payload)
    else:
        return repr(agent)
    if inspect.isawaitable(result):
        raise RunnerError("async agent invocation is not supported by the sync runner yet")
    return result


def _run_skill_node(config: AgentFirewallConfig, node: FlowNode, packet: TaskPacket) -> StepResult:
    skill_dir = _resolve_path(config.workspace, node.ref or str(node.meta.get("path") or ""))
    if not (skill_dir / "SKILL.md").exists():
        skill_dir = config.workspace / APP_DIR / "skills" / (node.ref or node.id.split(":", 1)[-1])
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        return StepResult(
            status="failed",
            summary=f"skill manifest not found: {skill_md}",
            error={"code": "skill_not_found", "message": str(skill_md), "retryable": False},
        )
    manifest = _read_manifest(skill_md)
    script = node.params.get("script")
    if script:
        return _run_skill_script(skill_dir, str(script), packet, node)
    return StepResult(
        status="success",
        summary=f"loaded skill {manifest.name}: {manifest.description}",
        output={"name": manifest.name, "description": manifest.description, "path": str(manifest.path)},
        handoff={"next_input": packet.prompt()},
    )


def _run_skill_script(skill_dir: Path, script: str, packet: TaskPacket, node: FlowNode) -> StepResult:
    script_path = (skill_dir / script).resolve()
    try:
        script_path.relative_to(skill_dir.resolve())
    except ValueError:
        return StepResult(
            status="failed",
            summary="skill script must stay inside the skill directory",
            error={"code": "invalid_script_path", "message": script, "retryable": False},
        )
    if not script_path.exists():
        return StepResult(
            status="failed",
            summary=f"skill script not found: {script}",
            error={"code": "script_not_found", "message": script, "retryable": False},
        )
    completed = subprocess.run(
        [sys.executable, str(script_path)],
        input=json.dumps(
            {
                "goal": packet.goal,
                "incoming": packet.incoming,
                "correction": packet.correction,
                "idempotency_key": packet.idempotency_key,
            },
            ensure_ascii=False,
        ),
        text=True,
        capture_output=True,
        timeout=float(node.params.get("timeout_seconds", 60)),
        check=False,
    )
    summary = (completed.stdout or completed.stderr).strip()
    output = _parse_json_object(completed.stdout)
    if completed.returncode != 0:
        return StepResult(
            status="failed",
            summary=summary or f"script exited with {completed.returncode}",
            output=output,
            error={
                "code": "script_failed",
                "message": summary or f"exit code {completed.returncode}",
                "retryable": bool(node.params.get("retry_script_failure", False)),
                "exit_code": completed.returncode,
            },
        )
    return StepResult(
        status="success",
        summary=summary or "skill script completed",
        output=output,
        handoff={"next_input": summary, "output": output},
    )


def _run_mcp_node(config: AgentFirewallConfig, node: FlowNode, packet: TaskPacket) -> StepResult:
    tool_name = str(node.params["tool"])
    args = dict(node.params.get("args") or {})
    idempotency_arg = node.params.get("idempotency_arg")
    if idempotency_arg:
        args[str(idempotency_arg)] = packet.idempotency_key
    timeout = float(node.params.get("timeout_seconds", 60))
    return asyncio.run(_call_mcp_tool(config, node, tool_name, args, timeout=timeout))


async def _call_mcp_tool(
    config: AgentFirewallConfig,
    node: FlowNode,
    tool_name: str,
    args: dict[str, Any],
    *,
    timeout: float,
) -> StepResult:
    try:
        from langchain_mcp_adapters.client import MultiServerMCPClient
    except ImportError:
        return StepResult(
            status="failed",
            summary="langchain-mcp-adapters is not installed",
            error={"code": "dependency_missing", "message": "langchain-mcp-adapters", "retryable": False},
        )

    server_key = str(node.params.get("server") or node.ref)
    agent_key = str(node.meta.get("agent") or config.active_agent)
    server_config = config.agents.get(agent_key, config.active).mcp_servers.get(server_key)
    if not server_config and isinstance(node.meta.get("config"), dict):
        server_config = node.meta["config"]
    if not server_config:
        return StepResult(
            status="failed",
            summary=f"mcp server not configured: {server_key}",
            error={"code": "mcp_server_not_found", "message": server_key, "retryable": False},
        )

    tools = await asyncio.wait_for(
        MultiServerMCPClient({server_key: server_config}).get_tools(),
        timeout=timeout,
    )
    tool = next((item for item in tools if getattr(item, "name", "") == tool_name), None)
    if not tool:
        return StepResult(
            status="failed",
            summary=f"mcp tool not found: {tool_name}",
            error={"code": "mcp_tool_not_found", "message": tool_name, "retryable": False},
        )
    if hasattr(tool, "ainvoke"):
        result = await asyncio.wait_for(tool.ainvoke(args), timeout=timeout)
    elif hasattr(tool, "invoke"):
        result = await asyncio.wait_for(asyncio.to_thread(tool.invoke, args), timeout=timeout)
    else:
        result = await asyncio.wait_for(asyncio.to_thread(tool, **args), timeout=timeout)
    summary = _response_text(result)
    output = _response_output(result)
    is_error = bool(getattr(result, "isError", False)) or bool(output.get("isError"))
    if is_error:
        return StepResult(
            status="failed",
            summary=summary,
            output=output,
            error={"code": "mcp_tool_error", "message": summary, "retryable": False},
        )
    return StepResult(
        status="success",
        summary=summary,
        output=output,
        handoff={"next_input": summary, "output": output},
    )


def _resolve_path(workspace: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else workspace / path


def _response_text(response: Any) -> str:
    if isinstance(response, str):
        return response
    if isinstance(response, dict):
        structured = response.get("structured_response")
        if structured is not None:
            return json.dumps(structured, ensure_ascii=False)
        messages = response.get("messages")
        if isinstance(messages, list) and messages:
            last = messages[-1]
            content = getattr(last, "content", None) or (last.get("content") if isinstance(last, dict) else None)
            if content:
                return str(content)
    content = getattr(response, "content", None)
    return str(content if content is not None else response)


def _response_output(response: Any) -> dict[str, Any]:
    if isinstance(response, dict):
        structured = response.get("structured_response")
        if isinstance(structured, dict):
            return structured
        if "isError" in response:
            return dict(response)
    content = getattr(response, "content", None)
    if isinstance(content, dict):
        return content
    return _parse_json_object(_response_text(response))


def _parse_json_object(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    try:
        parsed = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {"value": parsed}


def _jsonable(value: Any) -> Any:
    try:
        json.dumps(value)
        return value
    except TypeError:
        if isinstance(value, (list, tuple)):
            return [_jsonable(item) for item in value]
        if isinstance(value, dict):
            return {str(key): _jsonable(item) for key, item in value.items()}
        if hasattr(value, "value"):
            return _jsonable(value.value)
        return repr(value)


def _node_payload(node: FlowNode) -> dict[str, Any]:
    return {
        "id": node.id,
        "type": node.type,
        "label": node.label,
        "ref": node.ref,
        "params": node.params,
    }


def _create_handoff(
    run_id: str,
    goal: str,
    from_node: str,
    to_node: str,
    result: StepResult,
) -> dict[str, Any]:
    return Handoff(
        run_id=run_id,
        goal=goal,
        from_node=from_node,
        to_node=to_node,
        summary=result.summary,
        artifacts=result.artifacts,
        next_input=str(result.handoff.get("next_input") or result.summary),
        status=result.status,
    ).to_mapping() | {"output": result.output, "error": result.error}


def _filter_handoff(handoff: dict[str, Any], fields: list[str]) -> dict[str, Any]:
    if not fields:
        return handoff
    required = {"run_id", "goal", "from_node", "to_node", "status"}
    return {key: value for key, value in handoff.items() if key in required or key in fields}
