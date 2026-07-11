from __future__ import annotations

import asyncio
import copy
import difflib
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from .config import AgentFirewallConfig
from .flow import FlowSpec
from .store import AgentFirewallStore, snapshot_hash


def create_revision(
    config: AgentFirewallConfig,
    *,
    target_type: str,
    target_ref: str,
    after: dict[str, Any],
    reason: str,
    test_case_id: int | None = None,
    baseline_run_id: str | None = None,
) -> dict[str, Any]:
    store = AgentFirewallStore(config.workspace)
    case = _revision_case(store, test_case_id, target_type, target_ref)
    baseline = _revision_baseline(store, baseline_run_id, case) if case else None
    if (test_case_id is None) != (baseline_run_id is None):
        raise ValueError("revision evidence requires both test_case_id and baseline_run_id")

    before = target_snapshot_value(config, target_type, target_ref, test_case=case)
    normalized_after = _normalize_after(config, target_type, target_ref, before, after)
    before_hash = target_evidence_hash(target_type, target_ref, before)
    after_hash = target_evidence_hash(target_type, target_ref, normalized_after)
    if baseline and baseline.get("target_snapshot_hash") != before_hash:
        raise ValueError("baseline target snapshot does not match the current revision target")

    revision = store.create_revision(
        {
            "target_type": target_type,
            "target_ref": target_ref,
            "before_json": before,
            "after_json": normalized_after,
            "reason": reason,
            "test_case_id": test_case_id,
            "snapshot_hash": case.get("snapshot_hash") if case else None,
            "baseline_run_id": baseline_run_id,
            "before_hash": before_hash,
            "after_hash": after_hash,
        }
    )
    return _with_diff(revision)


def review_revision(config: AgentFirewallConfig, revision_id: int, comparison_id: int) -> dict[str, Any]:
    store = AgentFirewallStore(config.workspace)
    revision = _revision(store, revision_id)
    _validate_review_evidence(store, revision, comparison_id)
    return _with_diff(
        store.mark_revision_reviewed(revision_id, comparison_id, str(revision["candidate_run_id"]))
    )


def apply_revision(config: AgentFirewallConfig, revision_id: int) -> dict[str, Any]:
    store = AgentFirewallStore(config.workspace)
    revision = _revision(store, revision_id)
    if revision["status"] != "draft":
        raise ValueError(f"revision is not reviewable: {revision_id} ({revision['status']})")
    if not revision.get("reviewed_at") or not revision.get("comparison_id"):
        raise ValueError("revision requires explicit review after a passing regression comparison")
    _validate_review_evidence(store, revision, int(revision["comparison_id"]))
    _assert_current_snapshot(config, revision, "before_hash")
    _validate_target_value(config, revision["target_type"], revision["target_ref"], revision["after_json"])

    try:
        _write_target(config, revision["target_type"], revision["target_ref"], revision["after_json"])
        result = store.transition_revision_status(revision_id, "draft", "applied")
    except Exception:
        _write_target(config, revision["target_type"], revision["target_ref"], revision["before_json"])
        raise
    return _with_diff(result)


def revert_revision(config: AgentFirewallConfig, revision_id: int) -> dict[str, Any]:
    store = AgentFirewallStore(config.workspace)
    revision = _revision(store, revision_id)
    if revision["status"] != "applied":
        raise ValueError(f"revision is not applied: {revision_id} ({revision['status']})")
    _assert_current_snapshot(config, revision, "after_hash")
    _validate_target_value(config, revision["target_type"], revision["target_ref"], revision["before_json"])

    try:
        _write_target(config, revision["target_type"], revision["target_ref"], revision["before_json"])
        result = store.transition_revision_status(revision_id, "applied", "reverted")
    except Exception:
        _write_target(config, revision["target_type"], revision["target_ref"], revision["after_json"])
        raise
    return _with_diff(result)


def target_evidence(target_type: str, target_ref: str, value: dict[str, Any]) -> dict[str, Any]:
    return {"target_type": target_type, "target_ref": target_ref, "value": value}


def target_evidence_hash(target_type: str, target_ref: str, value: dict[str, Any]) -> str:
    return snapshot_hash(target_evidence(target_type, target_ref, value))


def target_snapshot_value(
    config: AgentFirewallConfig,
    target_type: str,
    target_ref: str,
    *,
    test_case: dict[str, Any] | None = None,
) -> dict[str, Any]:
    store = AgentFirewallStore(config.workspace)
    if target_type == "agent":
        data = store.get_config() or {}
        try:
            agent = copy.deepcopy(data["agents"][target_ref])
            model_key = str(agent["model"])
            model_preset = copy.deepcopy(data["models"][model_key])
        except KeyError as exc:
            raise ValueError(f"agent not found: {target_ref}") from exc
        return {"agent": agent, "model_key": model_key, "model_preset": model_preset}
    if target_type == "flow":
        flow = store.get_flow(target_ref)
        if flow is None:
            raise ValueError(f"flow not found: {target_ref}")
        return flow
    if target_type == "script_action":
        path = _script_path(config.workspace, target_ref, test_case)
        content = path.read_text(encoding="utf-8")
        return {
            "path": path.relative_to(config.workspace).as_posix(),
            "content": content,
            "sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
        }
    if target_type == "skill_binding":
        path = _skill_manifest_path(config.workspace, target_ref)
        content = path.read_text(encoding="utf-8")
        value = {
            "path": path.relative_to(config.workspace).as_posix(),
            "content": content,
            "sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
        }
        if test_case:
            agent_key = str((test_case.get("input_json") or {}).get("agent") or config.active_agent)
            try:
                value["agent"] = agent_key
                value["skills"] = list((store.get_config() or {})["agents"][agent_key]["skills"])
            except KeyError as exc:
                raise ValueError(f"skill binding agent not found: {agent_key}") from exc
        return value
    if target_type == "mcp_tool":
        agent_key, server_key, tool_name = _mcp_identity(config, target_ref, test_case)
        data = store.get_config() or {}
        try:
            server_config = copy.deepcopy(data["agents"][agent_key]["mcp_servers"][server_key])
        except KeyError as exc:
            raise ValueError(f"mcp server not found: {agent_key}/{server_key}") from exc
        cached = store.get_discovered_mcp_tool(agent_key, server_key, tool_name) or {}
        current_server_hash = snapshot_hash(server_config)
        schema = cached.get("input_schema")
        schema_matches_server = cached.get("server_config_hash") == current_server_hash
        return {
            "agent": agent_key,
            "server": server_key,
            "tool": tool_name,
            "server_config": server_config,
            "input_schema": copy.deepcopy(schema) if isinstance(schema, dict) else None,
            "description": str(cached.get("description") or ""),
            "server_config_hash": current_server_hash,
            "discovered": bool(schema) and schema_matches_server,
        }
    raise ValueError(f"unsupported revision target: {target_type}")


def config_with_revision(config: AgentFirewallConfig, revision: dict[str, Any]) -> AgentFirewallConfig:
    target_type = str(revision["target_type"])
    if target_type not in {"agent", "mcp_tool"}:
        return config
    store = AgentFirewallStore(config.workspace)
    data = copy.deepcopy(store.get_config() or {})
    value = revision["after_json"]
    if target_type == "agent":
        data["agents"][revision["target_ref"]] = copy.deepcopy(value["agent"])
        data["models"][value["model_key"]] = copy.deepcopy(value["model_preset"])
    else:
        data["agents"][value["agent"]]["mcp_servers"][value["server"]] = copy.deepcopy(value["server_config"])
    return AgentFirewallConfig.from_mapping(data, config.workspace)


def _normalize_after(
    config: AgentFirewallConfig,
    target_type: str,
    target_ref: str,
    before: dict[str, Any],
    patch: dict[str, Any],
) -> dict[str, Any]:
    if not isinstance(patch, dict):
        raise ValueError("revision after value must be an object")
    if target_type == "agent":
        agent_patch = patch.get("agent") if set(patch) <= {"agent"} and isinstance(patch.get("agent"), dict) else patch
        extra = set(agent_patch) - set(before["agent"])
        if extra:
            raise ValueError(f"unsupported agent revision field(s): {', '.join(sorted(extra))}")
        agent = {**before["agent"], **copy.deepcopy(agent_patch)}
        data = AgentFirewallStore(config.workspace).get_config() or {}
        model_key = str(agent.get("model") or "")
        try:
            model_preset = copy.deepcopy(data["models"][model_key])
        except KeyError as exc:
            raise ValueError(f"model preset not found: {model_key}") from exc
        value = {"agent": agent, "model_key": model_key, "model_preset": model_preset}
    else:
        value = {**before, **copy.deepcopy(patch)}
    if target_type in {"script_action", "skill_binding"}:
        extra = set(value) - ({"path", "content", "sha256"} | ({"agent", "skills"} if target_type == "skill_binding" else set()))
        if extra:
            raise ValueError(f"unsupported {target_type} revision field(s): {', '.join(sorted(extra))}")
        if value.get("path") != before.get("path"):
            raise ValueError(f"{target_type} revision cannot change the target path")
        content = value.get("content")
        if not isinstance(content, str):
            raise ValueError(f"{target_type} revision content must be a string")
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        if "sha256" in patch and patch["sha256"] != digest:
            raise ValueError(f"{target_type} revision sha256 does not match content")
        value["sha256"] = digest
    elif target_type == "mcp_tool":
        forbidden_evidence = {"input_schema", "description", "server_config_hash", "discovered"} & set(patch)
        if forbidden_evidence:
            raise ValueError(
                "MCP revision evidence is discovered from the server, not supplied in the patch: "
                + ", ".join(sorted(forbidden_evidence))
            )
        extra = set(value) - {
            "agent",
            "server",
            "tool",
            "server_config",
            "input_schema",
            "description",
            "server_config_hash",
            "discovered",
        }
        if extra:
            raise ValueError(f"unsupported MCP revision field(s): {', '.join(sorted(extra))}")
        for key in ("agent", "server", "tool"):
            if value.get(key) != before.get(key):
                raise ValueError(f"MCP revision cannot change target identity field: {key}")
        server_hash = snapshot_hash(value.get("server_config"))
        if value.get("server_config") != before.get("server_config"):
            schema, description = _discover_mcp_target(config, value)
            value["input_schema"] = schema
            value["description"] = description
            value["server_config_hash"] = server_hash
            value["discovered"] = True
        if value.get("server_config_hash") != server_hash:
            raise ValueError("MCP revision server_config_hash does not match server_config")
    elif target_type == "flow":
        value = FlowSpec.from_mapping(value).to_mapping()
    _validate_target_value(config, target_type, target_ref, value)
    return value


def _validate_target_value(
    config: AgentFirewallConfig, target_type: str, target_ref: str, value: dict[str, Any]
) -> None:
    store = AgentFirewallStore(config.workspace)
    if target_type == "agent":
        data = copy.deepcopy(store.get_config() or {})
        if target_ref not in (data.get("agents") or {}):
            raise ValueError(f"agent not found: {target_ref}")
        if not isinstance(value.get("agent"), dict) or not isinstance(value.get("model_preset"), dict):
            raise ValueError("agent revision requires agent and model_preset snapshots")
        model_key = str(value.get("model_key") or "")
        if value["agent"].get("model") != model_key:
            raise ValueError("agent revision model identity does not match its preset")
        if data.get("models", {}).get(model_key) != value["model_preset"]:
            raise ValueError("agent revision model preset changed since the snapshot")
        data["agents"][target_ref] = copy.deepcopy(value["agent"])
        AgentFirewallConfig.from_mapping(data, config.workspace)
        return
    if target_type == "flow":
        FlowSpec.from_mapping(value)
        return
    if target_type == "script_action":
        if not isinstance(value.get("content"), str):
            raise ValueError("script revision content must be a string")
        path = _workspace_path(config.workspace, str(value.get("path") or ""))
        if path.suffix.lower() != ".py":
            raise ValueError("script revision target must be a Python file")
        digest = hashlib.sha256(value["content"].encode("utf-8")).hexdigest()
        if value.get("sha256") != digest:
            raise ValueError("script revision sha256 does not match content")
        compile(value["content"], str(path), "exec")
        return
    if target_type == "skill_binding":
        if not isinstance(value.get("content"), str):
            raise ValueError("skill binding revision content must be a string")
        path = _workspace_path(config.workspace, str(value.get("path") or ""))
        if path.name != "SKILL.md":
            raise ValueError("skill binding revision target must be SKILL.md")
        digest = hashlib.sha256(value["content"].encode("utf-8")).hexdigest()
        if value.get("sha256") != digest:
            raise ValueError("skill binding revision sha256 does not match content")
        if "agent" in value or "skills" in value:
            if not isinstance(value.get("agent"), str) or not isinstance(value.get("skills"), list):
                raise ValueError("skill binding revision requires an agent and skills snapshot")
            data = store.get_config() or {}
            if data.get("agents", {}).get(value["agent"], {}).get("skills") != value["skills"]:
                raise ValueError("skill binding changed since the snapshot")
        return
    if target_type == "mcp_tool":
        if not all(isinstance(value.get(key), str) and value[key] for key in ("agent", "server", "tool")):
            raise ValueError("MCP revision requires agent, server, and tool identity")
        if not isinstance(value.get("server_config"), dict):
            raise ValueError("MCP revision server_config must be an object")
        if not isinstance(value.get("input_schema"), dict):
            raise ValueError("MCP revision input_schema must be an object")
        if not value.get("discovered") or not value["input_schema"]:
            raise ValueError("MCP tool must be discovered with a non-empty input schema")
        if value.get("server_config_hash") != snapshot_hash(value["server_config"]):
            raise ValueError("MCP tool schema was discovered for a different server configuration")
        from jsonschema import Draft202012Validator, SchemaError

        try:
            Draft202012Validator.check_schema(value["input_schema"])
        except SchemaError as exc:
            raise ValueError(f"invalid MCP input schema: {exc.message}") from exc
        data = copy.deepcopy(store.get_config() or {})
        try:
            data["agents"][value["agent"]]["mcp_servers"][value["server"]] = copy.deepcopy(value["server_config"])
        except KeyError as exc:
            raise ValueError(f"mcp server not found: {value['agent']}/{value['server']}") from exc
        AgentFirewallConfig.from_mapping(data, config.workspace)
        return
    raise ValueError(f"unsupported revision target: {target_type}")


def _assert_current_snapshot(config: AgentFirewallConfig, revision: dict[str, Any], expected_field: str) -> None:
    case = AgentFirewallStore(config.workspace).get_test_case(revision["test_case_id"]) if revision.get("test_case_id") else None
    current = target_snapshot_value(
        config,
        revision["target_type"],
        revision["target_ref"],
        test_case=case,
    )
    actual_hash = target_evidence_hash(revision["target_type"], revision["target_ref"], current)
    if actual_hash != revision.get(expected_field):
        raise ValueError("revision target changed since its evidence snapshot; create a new revision")


def _write_target(config: AgentFirewallConfig, target_type: str, target_ref: str, value: dict[str, Any]) -> None:
    store = AgentFirewallStore(config.workspace)
    if target_type == "agent":
        data = copy.deepcopy(store.get_config() or {})
        data["agents"][target_ref] = copy.deepcopy(value["agent"])
        store.save_config(data)
        return
    if target_type == "flow":
        store.save_flow(value, target_ref)
        return
    if target_type == "script_action":
        _atomic_write(_workspace_path(config.workspace, value["path"]), value["content"])
        return
    if target_type == "skill_binding":
        _atomic_write(_workspace_path(config.workspace, value["path"]), value["content"])
        return
    if target_type == "mcp_tool":
        data = copy.deepcopy(store.get_config() or {})
        data["agents"][value["agent"]]["mcp_servers"][value["server"]] = copy.deepcopy(value["server_config"])
        store.save_config(data)
        discovered_config = AgentFirewallConfig.from_mapping(data, config.workspace)
        schema, _description = _discover_mcp_target(discovered_config, value, persist=True)
        if schema != value["input_schema"]:
            raise ValueError("MCP tool schema changed since revision evidence; rediscover and create a new revision")
        return
    raise ValueError(f"unsupported revision target: {target_type}")


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = path.stat().st_mode if path.exists() else None
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        handle.write(content)
        temp_path = Path(handle.name)
    try:
        if mode is not None:
            os.chmod(temp_path, mode)
        os.replace(temp_path, path)
    finally:
        temp_path.unlink(missing_ok=True)


def _validate_review_evidence(
    store: AgentFirewallStore, revision: dict[str, Any], comparison_id: int
) -> None:
    comparison = store.get_comparison(comparison_id)
    if not comparison:
        raise ValueError(f"comparison not found: {comparison_id}")
    if comparison.get("revision_id") != revision["id"]:
        raise ValueError("comparison is not bound to this revision")
    if comparison["result_json"].get("passed") is not True:
        raise ValueError("revision review requires a passing comparison")
    if comparison.get("snapshot_hash") != revision.get("snapshot_hash"):
        raise ValueError("comparison test case snapshot does not match the revision")
    if comparison["baseline_run_id"] != revision.get("baseline_run_id"):
        raise ValueError("comparison baseline does not match the revision")
    if comparison["candidate_run_id"] != revision.get("candidate_run_id"):
        raise ValueError("comparison candidate does not match the revision")

    baseline = store.get_run(comparison["baseline_run_id"])
    candidate = store.get_run(comparison["candidate_run_id"])
    if not baseline or not candidate:
        raise ValueError("revision comparison run evidence is missing")
    if baseline["status"] != "success" or not baseline.get("is_baseline"):
        raise ValueError("revision baseline is not an explicit successful baseline")
    if candidate["status"] != "success" or candidate.get("revision_id") != revision["id"]:
        raise ValueError("revision candidate is not a successful revision run")
    if baseline.get("target_snapshot_hash") != revision.get("before_hash"):
        raise ValueError("revision baseline did not execute the before snapshot")
    if candidate.get("target_snapshot_hash") != revision.get("after_hash"):
        raise ValueError("revision candidate did not execute the proposed after snapshot")
    case = store.get_test_case(int(revision["test_case_id"])) if revision.get("test_case_id") else None
    if (
        not case
        or case.get("snapshot_hash") != revision.get("snapshot_hash")
        or case.get("baseline_run_id") != revision.get("baseline_run_id")
    ):
        raise ValueError("revision test case or current baseline changed after regression evidence")


def _revision_case(
    store: AgentFirewallStore,
    test_case_id: int | None,
    target_type: str,
    target_ref: str,
) -> dict[str, Any] | None:
    if test_case_id is None:
        return None
    case = store.get_test_case(test_case_id)
    if not case:
        raise ValueError(f"test case not found: {test_case_id}")
    if case["target_type"] != target_type or case["target_ref"] != target_ref:
        raise ValueError("revision target does not match the test case target")
    return case


def _revision_baseline(
    store: AgentFirewallStore, baseline_run_id: str | None, case: dict[str, Any]
) -> dict[str, Any]:
    if not baseline_run_id:
        raise ValueError("revision requires an explicit baseline run")
    baseline = store.get_run(baseline_run_id)
    if not baseline:
        raise ValueError(f"run not found: {baseline_run_id}")
    if baseline["status"] != "success" or not baseline.get("is_baseline"):
        raise ValueError("revision baseline must be explicitly marked and successful")
    if case.get("baseline_run_id") != baseline_run_id:
        raise ValueError("revision baseline is not the current test case baseline")
    if baseline.get("test_case_id") != case["id"] or baseline.get("snapshot_hash") != case.get("snapshot_hash"):
        raise ValueError("revision baseline does not match the current test case snapshot")
    return baseline


def _script_path(
    workspace: Path, target_ref: str, test_case: dict[str, Any] | None
) -> Path:
    if test_case:
        script = str((test_case.get("input_json") or {}).get("script") or "")
        if not script:
            raise ValueError("script action test case requires input_json.script")
        skill_dir = Path(target_ref)
        if not skill_dir.is_absolute():
            skill_dir = workspace / skill_dir
        return _workspace_path(workspace, str((skill_dir / script).resolve()))
    return _workspace_path(workspace, target_ref)


def _skill_manifest_path(workspace: Path, target_ref: str) -> Path:
    path = _workspace_path(workspace, str(Path(target_ref) / "SKILL.md"))
    if not path.is_file():
        raise ValueError(f"skill binding manifest not found: {target_ref}")
    return path


def _workspace_path(workspace: Path, value: str) -> Path:
    path = Path(value)
    path = path.resolve() if path.is_absolute() else (workspace / path).resolve()
    try:
        path.relative_to(workspace.resolve())
    except ValueError as exc:
        raise ValueError("revision target must stay inside the workspace") from exc
    return path


def _mcp_identity(
    config: AgentFirewallConfig, target_ref: str, test_case: dict[str, Any] | None
) -> tuple[str, str, str]:
    if test_case:
        payload = test_case.get("input_json") or {}
        agent_key = str(payload.get("agent") or config.active_agent)
        server_key = str(payload.get("server") or target_ref)
        tool_name = str(payload.get("tool") or "")
    else:
        parts = target_ref.split(":")
        if parts and parts[0] == "mcp_tool":
            parts = parts[1:]
        if len(parts) != 3:
            raise ValueError("MCP revision target_ref must be agent:server:tool without a test case")
        agent_key, server_key, tool_name = parts
    if not agent_key or not server_key or not tool_name:
        raise ValueError("MCP target requires agent, server, and tool identity")
    return agent_key, server_key, tool_name


def _discover_mcp_target(
    config: AgentFirewallConfig, value: dict[str, Any], *, persist: bool = False
) -> tuple[dict[str, Any], str]:
    """Return evidence from a live MCP discovery without accepting caller schema."""
    from .capabilities import _load_mcp_tools, _tool_schema, discover_mcp_tools
    from .policy import policy_from_config, prepare_mcp_connections

    server_key = str(value["server"])
    if persist:
        tools = discover_mcp_tools(config, str(value["agent"]), server_key)
    else:
        connections = prepare_mcp_connections(
            policy_from_config(config), {server_key: value["server_config"]}
        )
        tools = asyncio.run(_load_mcp_tools(connections))
    for tool in tools:
        if str(getattr(tool, "name", "")) != value["tool"]:
            continue
        schema = tool.get("input_schema") if isinstance(tool, dict) else _tool_schema(tool)
        if not isinstance(schema, dict) or not schema:
            break
        description = tool.get("description") if isinstance(tool, dict) else getattr(tool, "description", "")
        return copy.deepcopy(schema), str(description or "")
    raise ValueError(f"MCP tool was not discovered with a non-empty input schema: {value['tool']}")


def _revision(store: AgentFirewallStore, revision_id: int) -> dict[str, Any]:
    revision = store.get_revision(revision_id)
    if not revision:
        raise ValueError(f"revision not found: {revision_id}")
    return revision


def _with_diff(revision: dict[str, Any]) -> dict[str, Any]:
    return {**revision, "diff": _diff(revision["before_json"], revision["after_json"])}


def _diff(before: dict[str, Any], after: dict[str, Any]) -> str:
    left = json.dumps(before, ensure_ascii=False, indent=2, sort_keys=True).splitlines()
    right = json.dumps(after, ensure_ascii=False, indent=2, sort_keys=True).splitlines()
    return "\n".join(difflib.unified_diff(left, right, fromfile="before", tofile="after", lineterm=""))
