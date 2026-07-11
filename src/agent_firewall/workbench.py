from __future__ import annotations

import copy
import shutil
import sys
import tempfile
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path
from typing import Any, Iterator
from uuid import uuid4

from .capabilities import list_capabilities
from .config import APP_DIR, AgentFirewallConfig
from .diagnostics import classify_failure, evaluate_assertions
from .flow import FlowNode
from .handoff import TaskPacket
from .policy import policy_from_config, redact_data
from .revisions import (
    config_with_revision,
    target_evidence,
    target_evidence_hash,
    target_snapshot_value,
)
from .store import AgentFirewallStore, snapshot_hash


def save_test_case(config: AgentFirewallConfig, value: dict[str, Any]) -> dict[str, Any]:
    input_json = value.get("input_json")
    assertions = value.get("assertions_json")
    if not isinstance(input_json, dict) or not isinstance(assertions, list):
        raise ValueError("test case input_json must be an object and assertions_json must be a list")
    target_type = str(value.get("target_type") or "")
    target_ref = str(value.get("target_ref") or "")
    capability = next(
        (
            item
            for item in list_capabilities(config)
            if item.get("executable")
            and item["kind"] == target_type
            and item["ref"] == target_ref
            and (target_type != "script_action" or item.get("script") == input_json.get("script"))
            and (target_type != "mcp_tool" or (
                item.get("agent") == input_json.get("agent", config.active_agent)
                and item.get("name") == input_json.get("tool")
                and item.get("ref") == input_json.get("server", target_ref)
            ))
            and (target_type != "skill_binding" or item.get("agent") == input_json.get("agent", config.active_agent))
        ),
        None,
    )
    if capability is None:
        raise ValueError("test target is not a discovered executable capability")
    normalized = dict(value)
    if target_type == "mcp_tool":
        normalized["input_json"] = {
            **{key: item for key, item in input_json.items() if key not in {"input_schema", "server_config_hash"}},
            "agent": capability["agent"],
            "server": capability["ref"],
            "tool": capability["name"],
        }
    if target_type == "skill_binding":
        normalized["input_json"] = {**input_json, "agent": capability["agent"]}
    return AgentFirewallStore(config.workspace).save_test_case(normalized)


def run_test_case(
    config: AgentFirewallConfig,
    test_case_id: int,
    *,
    baseline_run_id: str | None = None,
    revision_id: int | None = None,
    run_id: str | None = None,
    approved: bool = False,
) -> dict[str, Any]:
    store = AgentFirewallStore(config.workspace)
    case = store.get_test_case(test_case_id)
    if not case:
        raise ValueError(f"test case not found: {test_case_id}")
    revision = _candidate_revision(store, case, revision_id, baseline_run_id)
    if revision and baseline_run_id is None:
        baseline_run_id = str(revision["baseline_run_id"])
    if baseline_run_id:
        _require_current_baseline(store, case, baseline_run_id)

    actual_run_id = run_id or uuid4().hex
    if store.get_run(actual_run_id):
        raise ValueError(f"run already exists: {actual_run_id}")
    with _execution_context(config, case, revision) as (effective_config, node, target_value):
        evidence = target_evidence(case["target_type"], case["target_ref"], target_value)
        evidence_hash = target_evidence_hash(case["target_type"], case["target_ref"], target_value)
        if revision and evidence_hash != revision.get("after_hash"):
            raise ValueError("candidate overlay does not match the revision after snapshot")
        case_snapshot = _case_snapshot(case)
        execution_snapshot = _execution_snapshot(effective_config, node)
        execution_hash = snapshot_hash(execution_snapshot)
        redacted_case = _redact(effective_config, case_snapshot)
        redacted_evidence = _redact(effective_config, evidence)
        redacted_execution = _redact(effective_config, execution_snapshot)
        store.create_run(
            actual_run_id,
            str(_redact(effective_config, case["goal"])),
            f"test:{test_case_id}",
            {
                "test_case": redacted_case,
                "test_case_snapshot_hash": case["snapshot_hash"],
                "target_snapshot": redacted_evidence,
                "target_snapshot_hash": evidence_hash,
                "execution_snapshot": redacted_execution,
                "execution_snapshot_hash": execution_hash,
                "node": _redact(effective_config, _node_mapping(node)),
                "revision_id": revision_id,
            },
            parent_run_id=baseline_run_id,
            run_kind="test_case",
            test_case_id=test_case_id,
            snapshot_hash_value=case["snapshot_hash"],
            target_snapshot=redacted_evidence,
            target_snapshot_hash=evidence_hash,
            execution_snapshot=redacted_execution,
            execution_snapshot_hash=execution_hash,
            revision_id=revision_id,
        )
        _log_event(
            effective_config,
            store,
            actual_run_id,
            "run_started",
            {
                "test_case_id": test_case_id,
                "snapshot_hash": case["snapshot_hash"],
                "target_snapshot_hash": evidence_hash,
                "revision_id": revision_id,
                "goal": case["goal"],
            },
        )
        _log_event(effective_config, store, actual_run_id, "node_started", {"node": _node_mapping(node)}, node.id)
        validation_error = _mcp_validation_error(node, target_value) if case["target_type"] == "mcp_tool" else None
        if validation_error:
            step_mapping = validation_error
        else:
            step_mapping = _run_case_node(effective_config, node, case, actual_run_id, approved)

    _log_event(config, store, actual_run_id, "node_finished", step_mapping, node.id)
    try:
        assertions = evaluate_assertions(
            step_mapping,
            list(case["assertions_json"]),
            status=str(step_mapping["status"]),
        )
    except Exception as exc:
        assertions = {
            "passed": False,
            "results": [{"passed": False, "kind": "invalid", "message": f"invalid assertions: {exc}"}],
        }
    _log_event(config, store, actual_run_id, "assertions_evaluated", assertions, node.id)
    passed = step_mapping["status"] == "success" and assertions["passed"]
    diagnosis = None
    if not passed:
        error = step_mapping.get("error") or {
            "code": "validation_error",
            "message": next(
                (item["message"] for item in assertions["results"] if not item["passed"]),
                "assertion failed",
            ),
        }
        diagnosis = classify_failure(error)
        _log_event(config, store, actual_run_id, "diagnosis_created", diagnosis, node.id)
    status = (
        "success"
        if passed
        else str(step_mapping["status"] if step_mapping["status"] in {"needs_input", "blocked"} else "failed")
    )
    summary = str(step_mapping["summary"] if passed else diagnosis["message"])
    persisted_summary = str(_redact(config, summary))
    if store.finish_run(actual_run_id, status, persisted_summary):
        _log_event(config, store, actual_run_id, "run_finished", {"status": status, "summary": summary})
    else:
        cancelled = store.get_run(actual_run_id)
        status = "cancelled"
        summary = str((cancelled or {}).get("final_summary") or "cancelled by operator")
    if revision:
        store.bind_revision_candidate(revision["id"], actual_run_id)
    return {
        "run_id": actual_run_id,
        "test_case_id": test_case_id,
        "revision_id": revision_id,
        "status": status,
        "result": step_mapping,
        "assertions": assertions,
        "diagnosis": diagnosis,
        "events": store.list_events(actual_run_id),
    }


def set_test_run_baseline(config: AgentFirewallConfig, run_id: str) -> dict[str, Any]:
    store = AgentFirewallStore(config.workspace)
    run = store.get_run(run_id)
    if not run or run.get("test_case_id") is None:
        raise ValueError(f"test case run not found: {run_id}")
    case = store.get_test_case(int(run["test_case_id"]))
    if not case:
        raise ValueError(f"test case not found: {run['test_case_id']}")
    current = target_snapshot_value(config, case["target_type"], case["target_ref"], test_case=case)
    if run.get("target_snapshot_hash") != target_evidence_hash(
        case["target_type"], case["target_ref"], current
    ):
        raise ValueError("baseline run target does not match the current capability snapshot")
    return store.mark_run_baseline(run_id)


def compare_test_runs(
    config: AgentFirewallConfig, baseline_run_id: str, candidate_run_id: str
) -> dict[str, Any]:
    store = AgentFirewallStore(config.workspace)
    baseline = store.get_run_details(baseline_run_id)
    candidate = store.get_run_details(candidate_run_id)
    if not baseline or not candidate:
        missing = baseline_run_id if not baseline else candidate_run_id
        raise ValueError(f"run not found: {missing}")
    if baseline["run_kind"] != "test_case" or candidate["run_kind"] != "test_case":
        raise ValueError("run comparison requires test case runs")
    case = store.get_test_case(int(baseline["test_case_id"]))
    if not case or case.get("baseline_run_id") != baseline_run_id:
        raise ValueError("baseline is not the current explicit baseline for this test case")
    if baseline["status"] != "success" or not baseline.get("is_baseline"):
        raise ValueError("baseline must be explicitly marked and successful")
    if baseline.get("test_case_id") != candidate.get("test_case_id"):
        raise ValueError("run comparison requires the same test case")
    if not baseline.get("snapshot_hash") or baseline.get("snapshot_hash") != candidate.get("snapshot_hash"):
        raise ValueError("run comparison requires the same immutable test case snapshot")
    if case.get("snapshot_hash") != baseline.get("snapshot_hash"):
        raise ValueError("test case changed after the baseline was recorded")
    if candidate.get("parent_run_id") != baseline_run_id:
        raise ValueError("candidate run is not linked to this baseline")
    if candidate["status"] in {"running", "needs_input"}:
        raise ValueError("candidate run is not finalized")
    baseline_execution = baseline.get("execution_snapshot") or {}
    candidate_execution = candidate.get("execution_snapshot") or {}
    if baseline_execution.get("policy") != candidate_execution.get("policy"):
        raise ValueError("run comparison requires the same execution policy snapshot")
    if baseline_execution.get("runtime") != candidate_execution.get("runtime"):
        raise ValueError("run comparison requires the same runtime snapshot")

    revision_id = candidate.get("revision_id")
    if revision_id is not None:
        revision = store.get_revision(int(revision_id))
        if not revision:
            raise ValueError(f"revision not found: {revision_id}")
        if baseline.get("target_snapshot_hash") != revision.get("before_hash"):
            raise ValueError("baseline did not execute the revision before snapshot")
        if candidate.get("target_snapshot_hash") != revision.get("after_hash"):
            raise ValueError("candidate did not execute the revision after snapshot")

    regressions: list[str] = []
    if candidate["status"] != "success":
        regressions.append("candidate no longer passes")
    result = {
        "passed": not regressions,
        "baseline_status": baseline["status"],
        "candidate_status": candidate["status"],
        "snapshot_hash": baseline["snapshot_hash"],
        "baseline_target_snapshot_hash": baseline.get("target_snapshot_hash"),
        "candidate_target_snapshot_hash": candidate.get("target_snapshot_hash"),
        "baseline_execution_snapshot_hash": baseline.get("execution_snapshot_hash"),
        "candidate_execution_snapshot_hash": candidate.get("execution_snapshot_hash"),
        "regressions": regressions,
    }
    return store.save_comparison(
        {
            "baseline_run_id": baseline_run_id,
            "candidate_run_id": candidate_run_id,
            "snapshot_hash": baseline["snapshot_hash"],
            "revision_id": revision_id,
            "result_json": result,
        }
    )


def _run_case_node(
    config: AgentFirewallConfig,
    node: FlowNode,
    case: dict[str, Any],
    run_id: str,
    approved: bool,
) -> dict[str, Any]:
    try:
        from .runner import run_capability_node

        step = run_capability_node(
            config,
            node,
            TaskPacket(run_id=run_id, goal=case["goal"], node_id=node.id, idempotency_key=f"{run_id}:{node.id}"),
            approved=approved,
        )
    except Exception as exc:
        return {
            "status": "failed",
            "summary": str(exc) or type(exc).__name__,
            "output": {},
            "error": {"code": "exception", "message": str(exc), "type": type(exc).__name__},
            "artifacts": [],
            "handoff": {},
        }
    return step.to_mapping()


def _mcp_validation_error(node: FlowNode, target_value: dict[str, Any]) -> dict[str, Any] | None:
    if not target_value.get("discovered") or not target_value.get("input_schema"):
        return {
            "status": "failed",
            "summary": "MCP tool has not been discovered with an input schema",
            "output": {},
            "error": {
                "code": "mcp_tool_not_discovered",
                "message": "MCP tool has not been discovered with an input schema",
                "retryable": False,
            },
            "artifacts": [],
            "handoff": {},
        }
    from jsonschema import SchemaError, ValidationError, validate

    try:
        validate(instance=dict(node.params.get("args") or {}), schema=target_value.get("input_schema") or {})
    except ValidationError as exc:
        message = exc.message
        code = "invalid_arguments"
    except SchemaError as exc:
        message = exc.message
        code = "invalid_schema"
    else:
        return None
    return {
        "status": "failed",
        "summary": message,
        "output": {},
        "error": {"code": code, "message": message, "retryable": False},
        "artifacts": [],
        "handoff": {},
    }


def _candidate_revision(
    store: AgentFirewallStore,
    case: dict[str, Any],
    revision_id: int | None,
    baseline_run_id: str | None,
) -> dict[str, Any] | None:
    if revision_id is None:
        return None
    revision = store.get_revision(revision_id)
    if not revision:
        raise ValueError(f"revision not found: {revision_id}")
    if revision["status"] != "draft":
        raise ValueError(f"revision is not a candidate: {revision_id} ({revision['status']})")
    if revision.get("test_case_id") != case["id"] or revision.get("snapshot_hash") != case.get("snapshot_hash"):
        raise ValueError("revision is not bound to the current test case snapshot")
    if baseline_run_id and revision.get("baseline_run_id") != baseline_run_id:
        raise ValueError("revision is bound to a different baseline")
    if revision["target_type"] != case["target_type"] or revision["target_ref"] != case["target_ref"]:
        raise ValueError("revision target does not match the test case")
    return revision


def _require_current_baseline(
    store: AgentFirewallStore, case: dict[str, Any], baseline_run_id: str
) -> dict[str, Any]:
    baseline = store.get_run(baseline_run_id)
    if not baseline:
        raise ValueError(f"run not found: {baseline_run_id}")
    if case.get("baseline_run_id") != baseline_run_id:
        raise ValueError("baseline must be explicitly selected for the current test case")
    if baseline["status"] != "success" or not baseline.get("is_baseline"):
        raise ValueError("baseline must be explicitly marked and successful")
    if baseline.get("test_case_id") != case["id"] or baseline.get("snapshot_hash") != case.get("snapshot_hash"):
        raise ValueError("baseline does not match the current immutable test case snapshot")
    return baseline


@contextmanager
def _execution_context(
    config: AgentFirewallConfig,
    case: dict[str, Any],
    revision: dict[str, Any] | None,
) -> Iterator[tuple[AgentFirewallConfig, FlowNode, dict[str, Any]]]:
    if not revision:
        yield config, _case_node(case), target_snapshot_value(
            config, case["target_type"], case["target_ref"], test_case=case
        )
        return
    target_value = copy.deepcopy(revision["after_json"])
    if case["target_type"] not in {"script_action", "skill_binding"}:
        yield config_with_revision(config, revision), _case_node(case), target_value
        return

    skill_dir = Path(case["target_ref"])
    if not skill_dir.is_absolute():
        skill_dir = config.workspace / skill_dir
    script = str((case.get("input_json") or {}).get("script") or "")
    target_file = skill_dir / (script if case["target_type"] == "script_action" else "SKILL.md")
    expected_path = target_file.resolve().relative_to(config.workspace).as_posix()
    if target_value.get("path") != expected_path:
        raise ValueError("candidate path does not match the test case")
    candidates_root = config.workspace / APP_DIR
    candidates_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="candidate-", dir=candidates_root) as temp_dir:
        if case["target_type"] == "script_action":
            candidate_skill = Path(temp_dir) / "skill"
            shutil.copytree(skill_dir, candidate_skill)
            candidate_file = candidate_skill / script
            candidate_file.parent.mkdir(parents=True, exist_ok=True)
            candidate_file.write_text(target_value["content"], encoding="utf-8")
            yield config, _case_node(case, target_ref=str(candidate_skill)), target_value
            return

        agent_key = str((case.get("input_json") or {}).get("agent") or config.active_agent)
        effective_config = _config_with_candidate_skill(config, agent_key, skill_dir.resolve(), Path(temp_dir), target_value["content"])
        yield effective_config, _case_node(case), target_value


def _case_snapshot(case: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": case["id"],
        "name": case["name"],
        "target_type": case["target_type"],
        "target_ref": case["target_ref"],
        "goal": case["goal"],
        "input_json": copy.deepcopy(case["input_json"]),
        "assertions_json": copy.deepcopy(case["assertions_json"]),
        "snapshot_hash": case["snapshot_hash"],
    }


def _case_node(case: dict[str, Any], *, target_ref: str | None = None) -> FlowNode:
    target_type = str(case["target_type"])
    payload = dict(case["input_json"])
    if target_type == "script_action":
        return FlowNode(
            id=f"test:{case['id']}",
            type="skill",
            label=str(case["name"]),
            ref=target_ref or str(case["target_ref"]),
            params={"script": payload.pop("script"), **payload},
        )
    if target_type == "agent":
        return FlowNode(
            id=f"test:{case['id']}",
            type="agent",
            label=str(case["name"]),
            ref=str(case["target_ref"]),
            params=payload,
        )
    if target_type == "skill_binding":
        agent_key = str(payload.pop("agent", ""))
        if not agent_key:
            raise ValueError("skill binding test case requires input_json.agent")
        return FlowNode(
            id=f"test:{case['id']}",
            type="agent",
            label=str(case["name"]),
            ref=agent_key,
            params=payload,
        )
    if target_type == "mcp_tool":
        agent_key = str(payload.pop("agent", ""))
        payload.pop("input_schema", None)
        payload.pop("server_config_hash", None)
        return FlowNode(
            id=f"test:{case['id']}",
            type="mcp",
            label=str(case["name"]),
            ref=str(payload.pop("server", case["target_ref"])),
            params=payload,
            meta={"agent": agent_key} if agent_key else {},
        )
    raise ValueError(f"unsupported test target: {target_type}")


def _config_with_candidate_skill(
    config: AgentFirewallConfig,
    agent_key: str,
    skill_dir: Path,
    candidate_root: Path,
    content: str,
) -> AgentFirewallConfig:
    store = AgentFirewallStore(config.workspace)
    data = copy.deepcopy(store.get_config() or {})
    try:
        configured = list(data["agents"][agent_key]["skills"])
    except KeyError as exc:
        raise ValueError(f"agent not found or has no skills: {agent_key}") from exc
    replacement = None
    for path in configured:
        root = (config.workspace / path).resolve() if not Path(path).is_absolute() else Path(path).resolve()
        try:
            skill_dir.relative_to(root)
        except ValueError:
            continue
        replacement = root
        break
    if replacement is None:
        raise ValueError("skill is not bound to the test agent")
    candidate_binding = candidate_root / "skills"
    shutil.copytree(replacement, candidate_binding)
    candidate_manifest = candidate_binding / skill_dir.relative_to(replacement) / "SKILL.md"
    candidate_manifest.write_text(content, encoding="utf-8")
    data["agents"][agent_key]["skills"] = [
        str(candidate_binding) if ((config.workspace / path).resolve() if not Path(path).is_absolute() else Path(path).resolve()) == replacement else path
        for path in configured
    ]
    return AgentFirewallConfig.from_mapping(data, config.workspace)


def _node_mapping(node: FlowNode) -> dict[str, Any]:
    return {
        "id": node.id,
        "type": node.type,
        "label": node.label,
        "ref": node.ref,
        "params": node.params,
        "meta": node.meta,
    }


def _execution_snapshot(config: AgentFirewallConfig, node: FlowNode) -> dict[str, Any]:
    model = None
    if node.type == "agent":
        agent_key = node.ref or config.active_agent
        agent = config.agents[agent_key]
        model = {"key": agent.model, "preset": copy.deepcopy(config.models[agent.model])}
    return {
        "policy": asdict(config.policy),
        "model": model,
        "runtime": {"python": ".".join(str(part) for part in sys.version_info[:3])},
    }


def _redact(config: AgentFirewallConfig, value: Any) -> Any:
    return redact_data(value, policy_from_config(config).environment_names)


def _log_event(
    config: AgentFirewallConfig,
    store: AgentFirewallStore,
    run_id: str,
    event_type: str,
    payload: dict[str, Any],
    node_id: str | None = None,
) -> None:
    store.log_event(run_id, event_type, _redact(config, payload), node_id)
