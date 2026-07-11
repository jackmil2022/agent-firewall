from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from agent_firewall.config import load_config, write_default_config
from agent_firewall.handoff import StepResult
from agent_firewall.revisions import apply_revision, create_revision, review_revision, revert_revision
from agent_firewall.skills import install_bundled_skills
from agent_firewall.store import AgentFirewallStore, db_path, snapshot_hash
from agent_firewall.workbench import compare_test_runs, run_test_case, set_test_run_baseline


def _successful_result(*_args, **_kwargs) -> StepResult:
    return StepResult(status="success", summary="passed", output={"ok": True})


def _agent_case(store: AgentFirewallStore, assertions: list[object] | None = None) -> dict:
    return store.save_test_case(
        {
            "name": "agent regression",
            "target_type": "agent",
            "target_ref": "default",
            "goal": "verify agent",
            "input_json": {},
            "assertions_json": assertions or [{"kind": "status", "expected": "success"}],
        }
    )


def test_malformed_assertion_finalizes_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    write_default_config(tmp_path)
    store = AgentFirewallStore(tmp_path)
    case = _agent_case(store, [{"kind": "min_artifacts", "expected": "many"}, "not-an-object"])
    monkeypatch.setattr("agent_firewall.runner.run_capability_node", _successful_result)

    result = run_test_case(load_config(workspace=tmp_path), case["id"])

    run = store.get_run(result["run_id"])
    assert result["status"] == "failed"
    assert run is not None
    assert run["status"] == "failed"
    assert run["finished_at"] is not None
    assert result["assertions"]["results"][0]["message"].startswith("invalid assertion:")


def test_baseline_is_explicit_and_case_edit_clears_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_default_config(tmp_path)
    store = AgentFirewallStore(tmp_path)
    case = _agent_case(store)
    monkeypatch.setattr("agent_firewall.runner.run_capability_node", _successful_result)
    baseline = run_test_case(load_config(workspace=tmp_path), case["id"])

    with pytest.raises(ValueError, match="explicitly selected"):
        run_test_case(load_config(workspace=tmp_path), case["id"], baseline_run_id=baseline["run_id"])

    set_test_run_baseline(load_config(workspace=tmp_path), baseline["run_id"])
    selected = store.get_test_case(case["id"])
    assert selected is not None
    assert selected["baseline_run_id"] == baseline["run_id"]

    changed = store.save_test_case({**selected, "goal": "changed goal"})
    assert changed["snapshot_hash"] != case["snapshot_hash"]
    assert changed["baseline_run_id"] is None
    with pytest.raises(ValueError, match="explicitly selected"):
        run_test_case(load_config(workspace=tmp_path), case["id"], baseline_run_id=baseline["run_id"])


def test_agent_revision_requires_candidate_overlay_review_and_stale_checks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_default_config(tmp_path)
    store = AgentFirewallStore(tmp_path)
    case = _agent_case(store)
    observed_prompts: list[str] = []

    def run_agent(config, *_args, **_kwargs) -> StepResult:
        observed_prompts.append(config.agents["default"].system_prompt)
        return _successful_result()

    monkeypatch.setattr("agent_firewall.runner.run_capability_node", run_agent)
    config = load_config(workspace=tmp_path)
    baseline = run_test_case(config, case["id"])
    set_test_run_baseline(config, baseline["run_id"])
    original = store.get_config()["agents"]["default"]["system_prompt"]
    proposed = "Use only regression-tested tools."
    revision = create_revision(
        config,
        target_type="agent",
        target_ref="default",
        after={"system_prompt": proposed},
        reason="repair tool selection",
        test_case_id=case["id"],
        baseline_run_id=baseline["run_id"],
    )

    with pytest.raises(ValueError, match="explicit review"):
        apply_revision(config, revision["id"])

    ordinary_candidate = run_test_case(
        config, case["id"], baseline_run_id=baseline["run_id"]
    )
    ordinary_comparison = compare_test_runs(
        config, baseline["run_id"], ordinary_candidate["run_id"]
    )
    with pytest.raises(ValueError, match="not bound"):
        review_revision(config, revision["id"], ordinary_comparison["id"])

    candidate = run_test_case(config, case["id"], revision_id=revision["id"])
    with pytest.raises(ValueError, match="current capability snapshot"):
        set_test_run_baseline(config, candidate["run_id"])
    comparison = compare_test_runs(config, baseline["run_id"], candidate["run_id"])
    reviewed = review_revision(config, revision["id"], comparison["id"])
    assert reviewed["reviewed_at"] is not None
    assert observed_prompts == [original, original, proposed]
    assert store.get_config()["agents"]["default"]["system_prompt"] == original

    data = store.get_config()
    data["agents"]["default"]["system_prompt"] = "concurrent edit"
    store.save_config(data)
    with pytest.raises(ValueError, match="changed since"):
        apply_revision(config, revision["id"])

    data["agents"]["default"]["system_prompt"] = original
    store.save_config(data)
    transition = AgentFirewallStore.transition_revision_status

    def fail_transition(*_args, **_kwargs):
        raise RuntimeError("simulated status failure")

    monkeypatch.setattr(AgentFirewallStore, "transition_revision_status", fail_transition)
    with pytest.raises(RuntimeError, match="simulated status failure"):
        apply_revision(config, revision["id"])
    assert store.get_config()["agents"]["default"]["system_prompt"] == original
    monkeypatch.setattr(AgentFirewallStore, "transition_revision_status", transition)
    applied = apply_revision(config, revision["id"])
    assert applied["status"] == "applied"
    assert store.get_config()["agents"]["default"]["system_prompt"] == proposed

    data = store.get_config()
    data["agents"]["default"]["system_prompt"] = "post-apply edit"
    store.save_config(data)
    with pytest.raises(ValueError, match="changed since"):
        revert_revision(config, revision["id"])
    data["agents"]["default"]["system_prompt"] = proposed
    store.save_config(data)
    assert revert_revision(config, revision["id"])["status"] == "reverted"
    assert store.get_config()["agents"]["default"]["system_prompt"] == original


def test_script_revision_candidate_runs_temporary_content(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_default_config(tmp_path)
    install_bundled_skills(tmp_path)
    store = AgentFirewallStore(tmp_path)
    case = store.save_test_case(
        {
            "name": "script regression",
            "target_type": "script_action",
            "target_ref": ".agent-firewall/skills/skill-creator",
            "goal": "verify script",
            "input_json": {"script": "scripts/workbench_echo.py"},
            "assertions_json": [{"kind": "status", "expected": "success"}],
        }
    )
    script_path = tmp_path / case["target_ref"] / case["input_json"]["script"]
    original = script_path.read_text(encoding="utf-8")
    proposed = original + "\n# regression-tested revision\n"
    observed: list[str] = []

    def run_script(_config, node, *_args, **_kwargs) -> StepResult:
        observed.append((Path(node.ref) / node.params["script"]).read_text(encoding="utf-8"))
        return _successful_result()

    monkeypatch.setattr("agent_firewall.runner.run_capability_node", run_script)
    config = load_config(workspace=tmp_path)
    baseline = run_test_case(config, case["id"])
    set_test_run_baseline(config, baseline["run_id"])
    revision = create_revision(
        config,
        target_type="script_action",
        target_ref=case["target_ref"],
        after={"content": proposed},
        reason="repair script",
        test_case_id=case["id"],
        baseline_run_id=baseline["run_id"],
    )
    candidate = run_test_case(config, case["id"], revision_id=revision["id"])
    comparison = compare_test_runs(config, baseline["run_id"], candidate["run_id"])
    review_revision(config, revision["id"], comparison["id"])

    assert observed == [original, proposed]
    assert script_path.read_text(encoding="utf-8") == original
    apply_revision(config, revision["id"])
    assert script_path.read_text(encoding="utf-8") == proposed
    revert_revision(config, revision["id"])
    assert script_path.read_text(encoding="utf-8") == original


def test_mcp_revision_uses_cached_identity_schema_and_candidate_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_default_config(tmp_path)
    store = AgentFirewallStore(tmp_path)
    data = store.get_config()
    data["agents"]["default"]["mcp_servers"] = {
        "local": {"transport": "stdio", "command": "old-server"}
    }
    store.save_config(data)
    schema = {
        "type": "object",
        "properties": {"query": {"type": "string"}},
        "required": ["query"],
    }
    store.replace_discovered_mcp_tools(
        "default",
        "local",
        [{"tool_name": "search", "input_schema": schema, "description": "Search"}],
    )
    assert store.get_discovered_mcp_tool("default", "local", "search")["server_config_hash"]
    case = store.save_test_case(
        {
            "name": "MCP regression",
            "target_type": "mcp_tool",
            "target_ref": "local",
            "goal": "verify search",
            "input_json": {"agent": "default", "server": "local", "tool": "search", "args": {"query": "x"}},
            "assertions_json": [{"kind": "status", "expected": "success"}],
        }
    )
    observed_commands: list[str] = []

    def run_mcp(config, *_args, **_kwargs) -> StepResult:
        observed_commands.append(config.agents["default"].mcp_servers["local"]["command"])
        return _successful_result()

    monkeypatch.setattr("agent_firewall.runner.run_capability_node", run_mcp)
    def discover(_config, value, *, persist=False):
        if persist:
            AgentFirewallStore(_config.workspace).replace_discovered_mcp_tools(
                value["agent"],
                value["server"],
                [{"tool_name": value["tool"], "input_schema": schema, "description": "Search"}],
                server_config_hash=snapshot_hash(value["server_config"]),
            )
        return schema, "Search"

    monkeypatch.setattr("agent_firewall.revisions._discover_mcp_target", discover)
    config = load_config(workspace=tmp_path)
    baseline = run_test_case(config, case["id"])
    set_test_run_baseline(config, baseline["run_id"])
    revision = create_revision(
        config,
        target_type="mcp_tool",
        target_ref="local",
        after={"server_config": {"transport": "stdio", "command": "new-server"}},
        reason="repair MCP connection",
        test_case_id=case["id"],
        baseline_run_id=baseline["run_id"],
    )
    candidate = run_test_case(config, case["id"], revision_id=revision["id"])
    comparison = compare_test_runs(config, baseline["run_id"], candidate["run_id"])
    review_revision(config, revision["id"], comparison["id"])
    apply_revision(config, revision["id"])

    assert observed_commands == ["old-server", "new-server"]
    assert revision["before_json"]["input_schema"] == schema
    assert store.get_config()["agents"]["default"]["mcp_servers"]["local"]["command"] == "new-server"
    revert_revision(config, revision["id"])
    assert store.get_config()["agents"]["default"]["mcp_servers"]["local"]["command"] == "old-server"


def test_mcp_revision_rejects_caller_supplied_schema(tmp_path: Path) -> None:
    write_default_config(tmp_path)
    store = AgentFirewallStore(tmp_path)
    data = store.get_config()
    data["agents"]["default"]["mcp_servers"] = {"local": {"transport": "stdio", "command": "demo"}}
    store.save_config(data)
    store.replace_discovered_mcp_tools(
        "default", "local", [{"tool_name": "search", "input_schema": {"type": "object"}}]
    )

    with pytest.raises(ValueError, match="evidence is discovered"):
        create_revision(
            load_config(workspace=tmp_path),
            target_type="mcp_tool",
            target_ref="default:local:search",
            after={"input_schema": {"type": "object", "properties": {"forged": {}}}},
            reason="forged schema",
        )


def test_mcp_arguments_are_validated_before_execution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_default_config(tmp_path)
    store = AgentFirewallStore(tmp_path)
    data = store.get_config()
    data["agents"]["default"]["mcp_servers"] = {"local": {"transport": "stdio", "command": "demo"}}
    store.save_config(data)
    store.replace_discovered_mcp_tools(
        "default",
        "local",
        [
            {
                "tool_name": "search",
                "input_schema": {"type": "object", "required": ["query"]},
                "description": "Search",
            }
        ],
    )
    case = store.save_test_case(
        {
            "name": "invalid MCP arguments",
            "target_type": "mcp_tool",
            "target_ref": "local",
            "goal": "reject invalid arguments",
            "input_json": {"server": "local", "tool": "search", "args": {}},
            "assertions_json": [],
        }
    )
    called = False

    def should_not_run(*_args, **_kwargs):
        nonlocal called
        called = True
        return _successful_result()

    monkeypatch.setattr("agent_firewall.runner.run_capability_node", should_not_run)
    result = run_test_case(load_config(workspace=tmp_path), case["id"])

    assert result["status"] == "failed"
    assert result["result"]["error"]["code"] == "invalid_arguments"
    assert result["diagnosis"]["layer"] == "argument"
    assert called is False


def test_store_caches_mcp_tools_and_cancels_active_run(tmp_path: Path) -> None:
    store = AgentFirewallStore(tmp_path)
    cached = store.replace_discovered_mcp_tools(
        "agent",
        "server",
        [{"tool_name": "lookup", "input_schema": {"type": "object"}, "description": "Lookup"}],
    )
    assert cached[0]["tool_name"] == "lookup"
    assert store.get_discovered_mcp_tool("agent", "server", "lookup")["input_schema"] == {"type": "object"}

    store.create_run("cancel-me", "goal", "default", {})
    cancelled = store.cancel_run("cancel-me", "operator stopped it")
    assert cancelled["status"] == "cancelled"
    assert [event["event_type"] for event in cancelled["events"]] == ["run_cancelled", "run_finished"]
    assert store.finish_run("cancel-me", "success", "late result") is False
    store.log_event("cancel-me", "node_finished", {"late": True}, "node")
    assert store.get_run("cancel-me")["status"] == "cancelled"
    assert [event["event_type"] for event in store.list_events("cancel-me")] == [
        "run_cancelled",
        "run_finished",
    ]


def test_run_evidence_is_redacted_without_mutating_execution_input(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_default_config(tmp_path)
    store = AgentFirewallStore(tmp_path)
    data = store.get_config()
    data["policy"]["allowed_env_vars"] = ["WORKBENCH_SECRET"]
    store.save_config(data)
    monkeypatch.setenv("WORKBENCH_SECRET", "environment-secret")
    case = store.save_test_case(
        {
            "name": "secret evidence",
            "target_type": "agent",
            "target_ref": "default",
            "goal": "use environment-secret",
            "input_json": {"api_key": "literal-secret", "prompt": "environment-secret"},
            "assertions_json": [],
        }
    )
    observed_params: list[dict] = []

    def run_agent(_config, node, *_args, **_kwargs) -> StepResult:
        observed_params.append(node.params)
        return StepResult(
            status="success",
            summary="environment-secret",
            output={"token": "literal-secret", "text": "environment-secret"},
        )

    monkeypatch.setattr("agent_firewall.runner.run_capability_node", run_agent)
    result = run_test_case(load_config(workspace=tmp_path), case["id"])
    persisted = store.get_run_details(result["run_id"])
    serialized = json.dumps(persisted, ensure_ascii=False)

    assert observed_params == [case["input_json"]]
    assert "literal-secret" not in serialized
    assert "environment-secret" not in serialized
    assert "[REDACTED]" in serialized


def test_agent_model_preset_drift_invalidates_baseline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_default_config(tmp_path)
    store = AgentFirewallStore(tmp_path)
    case = _agent_case(store)
    monkeypatch.setattr("agent_firewall.runner.run_capability_node", _successful_result)
    config = load_config(workspace=tmp_path)
    baseline = run_test_case(config, case["id"])
    set_test_run_baseline(config, baseline["run_id"])
    data = store.get_config()
    data["models"]["fake-echo"]["params"]["temperature"] = 0.9
    store.save_config(data)

    with pytest.raises(ValueError, match="baseline target snapshot"):
        create_revision(
            load_config(workspace=tmp_path),
            target_type="agent",
            target_ref="default",
            after={"system_prompt": "new prompt"},
            reason="model drift check",
            test_case_id=case["id"],
            baseline_run_id=baseline["run_id"],
        )


def test_comparison_rejects_execution_policy_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_default_config(tmp_path)
    store = AgentFirewallStore(tmp_path)
    case = _agent_case(store)
    monkeypatch.setattr("agent_firewall.runner.run_capability_node", _successful_result)
    config = load_config(workspace=tmp_path)
    baseline = run_test_case(config, case["id"])
    set_test_run_baseline(config, baseline["run_id"])
    data = store.get_config()
    data["policy"]["allow_network"] = True
    store.save_config(data)
    candidate = run_test_case(
        load_config(workspace=tmp_path),
        case["id"],
        baseline_run_id=baseline["run_id"],
    )

    with pytest.raises(ValueError, match="execution policy"):
        compare_test_runs(load_config(workspace=tmp_path), baseline["run_id"], candidate["run_id"])


def test_stale_mcp_discovery_cache_blocks_execution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_default_config(tmp_path)
    store = AgentFirewallStore(tmp_path)
    data = store.get_config()
    data["agents"]["default"]["mcp_servers"] = {"local": {"transport": "stdio", "command": "old"}}
    store.save_config(data)
    store.replace_discovered_mcp_tools(
        "default",
        "local",
        [{"tool_name": "search", "input_schema": {"type": "object"}, "description": "Search"}],
    )
    data = store.get_config()
    data["agents"]["default"]["mcp_servers"]["local"]["command"] = "new"
    store.save_config(data)
    case = store.save_test_case(
        {
            "name": "stale MCP cache",
            "target_type": "mcp_tool",
            "target_ref": "local",
            "goal": "do not run stale schema",
            "input_json": {"server": "local", "tool": "search", "args": {}},
            "assertions_json": [],
        }
    )
    called = False

    def should_not_run(*_args, **_kwargs):
        nonlocal called
        called = True
        return _successful_result()

    monkeypatch.setattr("agent_firewall.runner.run_capability_node", should_not_run)
    result = run_test_case(load_config(workspace=tmp_path), case["id"], run_id="known-run-id")

    assert result["run_id"] == "known-run-id"
    assert result["result"]["error"]["code"] == "mcp_tool_not_discovered"
    assert result["diagnosis"]["layer"] == "discovery"
    assert called is False
    with pytest.raises(ValueError, match="already exists"):
        run_test_case(load_config(workspace=tmp_path), case["id"], run_id="known-run-id")


def test_additive_migration_keeps_old_workspace_readable(tmp_path: Path) -> None:
    path = db_path(tmp_path)
    path.parent.mkdir(parents=True)
    with sqlite3.connect(path) as db:
        db.executescript(
            """
            create table test_cases (
              id integer primary key autoincrement,
              name text not null,
              target_type text not null,
              target_ref text not null,
              goal text not null,
              input_json text not null,
              assertions_json text not null,
              created_at text not null,
              updated_at text not null
            );
            create table runs (
              run_id text primary key,
              goal text not null,
              flow_name text not null,
              status text not null,
              started_at text not null,
              finished_at text,
              final_summary text,
              flow_snapshot text,
              state_json text,
              parent_run_id text
            );
            create table revisions (
              id integer primary key autoincrement,
              target_type text not null,
              target_ref text not null,
              before_json text not null,
              after_json text not null,
              reason text not null,
              status text not null,
              created_at text not null,
              applied_at text
            );
            create table run_comparisons (
              id integer primary key autoincrement,
              baseline_run_id text not null,
              candidate_run_id text not null,
              result_json text not null,
              created_at text not null
            );
            """
        )
        db.execute(
            """
            insert into test_cases(
              name, target_type, target_ref, goal, input_json, assertions_json, created_at, updated_at
            ) values('old', 'agent', 'default', 'goal', '{}', '[]', 'then', 'then')
            """
        )
        db.execute(
            """
            insert into runs(run_id, goal, flow_name, status, started_at)
            values('old-run', 'goal', 'default', 'success', 'then')
            """
        )

    store = AgentFirewallStore(tmp_path)
    case = store.get_test_case(1)
    run = store.get_run("old-run")
    assert case is not None and case["snapshot_hash"]
    assert case["baseline_run_id"] is None
    assert run is not None
    assert run["run_kind"] == "flow"
    assert run["is_baseline"] is False


def test_store_connections_enable_wal_busy_timeout_and_foreign_keys(tmp_path: Path) -> None:
    store = AgentFirewallStore(tmp_path)
    with store._connect() as db:
        assert db.execute("pragma journal_mode").fetchone()[0] == "wal"
        assert db.execute("pragma busy_timeout").fetchone()[0] == 5000
        assert db.execute("pragma foreign_keys").fetchone()[0] == 1
