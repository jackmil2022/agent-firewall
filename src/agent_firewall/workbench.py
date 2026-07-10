from __future__ import annotations

from typing import Any
from uuid import uuid4

from .config import AgentFirewallConfig
from .diagnostics import classify_failure, evaluate_assertions
from .flow import FlowNode
from .handoff import TaskPacket
from .runner import _run_node
from .store import AgentFirewallStore


def run_test_case(
    config: AgentFirewallConfig,
    test_case_id: int,
    *,
    baseline_run_id: str | None = None,
    approved: bool = False,
) -> dict[str, Any]:
    store = AgentFirewallStore(config.workspace)
    case = store.get_test_case(test_case_id)
    if not case:
        raise ValueError(f"test case not found: {test_case_id}")
    node = _case_node(case)
    run_id = uuid4().hex
    store.create_run(
        run_id,
        case["goal"],
        f"test:{test_case_id}",
        {"test_case": case, "node": _node_mapping(node)},
        parent_run_id=baseline_run_id,
    )
    store.log_event(run_id, "run_started", {"test_case_id": test_case_id, "goal": case["goal"]})
    store.log_event(run_id, "node_started", {"node": _node_mapping(node)}, node.id)
    try:
        from .runner import run_capability_node

        step = run_capability_node(
            config,
            node,
            TaskPacket(run_id=run_id, goal=case["goal"], node_id=node.id, idempotency_key=f"{run_id}:{node.id}"),
            approved=approved,
        )
    except Exception as exc:
        step_mapping = {
            "status": "failed",
            "summary": str(exc) or type(exc).__name__,
            "output": {},
            "error": {"code": "exception", "message": str(exc), "type": type(exc).__name__},
            "artifacts": [],
            "handoff": {},
        }
    else:
        step_mapping = step.to_mapping()
    store.log_event(run_id, "node_finished", step_mapping, node.id)
    assertions = evaluate_assertions(
        step_mapping,
        list(case["assertions_json"]),
        status=str(step_mapping["status"]),
    )
    store.log_event(run_id, "assertions_evaluated", assertions, node.id)
    passed = step_mapping["status"] == "success" and assertions["passed"]
    diagnosis = None
    if not passed:
        error = step_mapping.get("error") or {
            "code": "validation_error",
            "message": next((item["message"] for item in assertions["results"] if not item["passed"]), "assertion failed"),
        }
        diagnosis = classify_failure(error)
        store.log_event(run_id, "diagnosis_created", diagnosis, node.id)
    status = "success" if passed else str(step_mapping["status"] if step_mapping["status"] in {"needs_input", "blocked"} else "failed")
    summary = step_mapping["summary"] if passed else diagnosis["message"]
    store.finish_run(run_id, status, summary)
    store.log_event(run_id, "run_finished", {"status": status, "summary": summary})
    return {
        "run_id": run_id,
        "test_case_id": test_case_id,
        "status": status,
        "result": step_mapping,
        "assertions": assertions,
        "diagnosis": diagnosis,
        "events": store.list_events(run_id),
    }


def compare_test_runs(
    config: AgentFirewallConfig, baseline_run_id: str, candidate_run_id: str
) -> dict[str, Any]:
    store = AgentFirewallStore(config.workspace)
    baseline = store.get_run_details(baseline_run_id)
    candidate = store.get_run_details(candidate_run_id)
    if not baseline or not candidate:
        missing = baseline_run_id if not baseline else candidate_run_id
        raise ValueError(f"run not found: {missing}")
    baseline_case = (baseline.get("flow_snapshot") or {}).get("test_case", {})
    candidate_case = (candidate.get("flow_snapshot") or {}).get("test_case", {})
    if baseline_case.get("id") != candidate_case.get("id"):
        raise ValueError("run comparison requires the same test case")
    regressions: list[str] = []
    if baseline["status"] == "success" and candidate["status"] != "success":
        regressions.append("candidate no longer passes")
    result = {
        "passed": not regressions and candidate["status"] == "success",
        "baseline_status": baseline["status"],
        "candidate_status": candidate["status"],
        "regressions": regressions,
    }
    return store.save_comparison(
        {"baseline_run_id": baseline_run_id, "candidate_run_id": candidate_run_id, "result_json": result}
    )


def _case_node(case: dict[str, Any]) -> FlowNode:
    target_type = str(case["target_type"])
    payload = dict(case["input_json"])
    if target_type == "script_action":
        return FlowNode(
            id=f"test:{case['id']}",
            type="skill",
            label=str(case["name"]),
            ref=str(case["target_ref"]),
            params={"script": payload.pop("script"), **payload},
        )
    if target_type == "agent":
        return FlowNode(
            id=f"test:{case['id']}", type="agent", label=str(case["name"]), ref=str(case["target_ref"]), params=payload
        )
    if target_type == "mcp_tool":
        return FlowNode(
            id=f"test:{case['id']}",
            type="mcp",
            label=str(case["name"]),
            ref=str(payload.pop("server", case["target_ref"])),
            params=payload,
        )
    raise ValueError(f"unsupported test target: {target_type}")


def _node_mapping(node: FlowNode) -> dict[str, Any]:
    return {"id": node.id, "type": node.type, "label": node.label, "ref": node.ref, "params": node.params, "meta": node.meta}
