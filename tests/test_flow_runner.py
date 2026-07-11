import sqlite3
from pathlib import Path

import pytest

from agent_firewall.config import load_config, write_default_config
from agent_firewall.flow import FlowError, FlowSpec, load_flow, save_flow
from agent_firewall.handoff import StepResult
from agent_firewall.runner import resume_flow, run_flow
from agent_firewall.skills import install_bundled_skills
from agent_firewall.store import AgentFirewallStore
import agent_firewall.runner as runner


def test_flow_saved_to_sqlite(tmp_path: Path) -> None:
    write_default_config(tmp_path)
    install_bundled_skills(tmp_path)
    config = load_config(workspace=tmp_path)
    flow = {
        "nodes": [{"id": "skill:creator", "type": "skill", "ref": ".agent-firewall/skills/skill-creator"}],
        "edges": [],
    }

    save_flow(tmp_path, flow)

    loaded = load_flow(tmp_path, config)
    assert loaded.nodes[0].id == "start"
    assert any(node.id == "skill:creator" for node in loaded.nodes)
    assert AgentFirewallStore(tmp_path).get_flow()["nodes"][0]["id"] == "start"


def test_runner_writes_run_and_events_to_sqlite(tmp_path: Path) -> None:
    write_default_config(tmp_path)
    install_bundled_skills(tmp_path)
    config = load_config(workspace=tmp_path)
    save_flow(
        tmp_path,
        {
            "nodes": [{"id": "agent:default", "type": "agent", "ref": "default"}],
            "edges": [],
        },
    )

    result = run_flow(config, goal="validate sqlite logs")

    assert result["status"] == "success"
    db = sqlite3.connect(AgentFirewallStore(tmp_path).path)
    try:
        run_count = db.execute("select count(*) from runs where run_id = ?", (result["run_id"],)).fetchone()[0]
        event_count = db.execute("select count(*) from run_events where run_id = ?", (result["run_id"],)).fetchone()[0]
    finally:
        db.close()
    assert run_count == 1
    assert event_count >= 3


def test_flow_adds_start_and_end_nodes() -> None:
    flow = FlowSpec.from_mapping(
        {
            "nodes": [
                {"id": "agent:default", "type": "agent"},
                {"id": "skill:creator", "type": "skill"},
            ],
            "edges": [{"from": "agent:default", "to": "skill:creator"}],
        }
    )

    assert [node.id for node in flow.nodes][0] == "start"
    assert [node.id for node in flow.nodes][-1] == "end"
    assert any(edge.from_node == "start" and edge.to_node == "agent:default" for edge in flow.edges)
    assert any(edge.from_node == "skill:creator" and edge.to_node == "end" for edge in flow.edges)


@pytest.mark.parametrize(
    "flow",
    [
        {
            "nodes": [{"id": "x", "type": "skill"}, {"id": "x", "type": "skill"}],
            "edges": [],
        },
        {
            "nodes": [{"id": "x", "type": "unknown"}],
            "edges": [],
        },
        {
            "nodes": [{"id": "x", "type": "skill"}],
            "edges": [{"from": "x", "to": "x", "on": "typo"}],
        },
        {
            "nodes": [{"id": "x", "type": "skill"}],
            "edges": [],
            "limits": {"max_steps": 0},
        },
    ],
)
def test_flow_rejects_invalid_graphs(flow: dict) -> None:
    with pytest.raises(FlowError):
        FlowSpec.from_mapping(flow)


def test_join_waits_for_all_predecessors_and_runs_once(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = _configured_workspace(tmp_path)
    save_flow(
        tmp_path,
        {
            "nodes": [
                _skill_node("a"),
                _skill_node("b"),
                _skill_node("c"),
                _skill_node("join"),
            ],
            "edges": [
                {"from": "a", "to": "join"},
                {"from": "b", "to": "c"},
                {"from": "c", "to": "join"},
            ],
        },
    )
    seen: list[tuple[str, int]] = []

    def fake_run_node(config, node, packet):
        seen.append((node.id, len(packet.incoming)))
        return StepResult(status="success", summary=node.id)

    monkeypatch.setattr(runner, "_run_node", fake_run_node)

    result = run_flow(config, goal="join")

    assert result["status"] == "success"
    assert seen.count(("join", 2)) == 1
    assert [node for node, _ in seen].count("end") == 1


def test_exception_routes_through_failed_edge(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = _configured_workspace(tmp_path)
    save_flow(
        tmp_path,
        {
            "nodes": [
                _skill_node("work"),
                _skill_node("recover"),
            ],
            "edges": [{"from": "work", "to": "recover", "on": "failed"}],
        },
    )
    seen: list[str] = []

    def fake_run_node(config, node, packet):
        seen.append(node.id)
        if node.id == "work":
            raise TimeoutError("temporary")
        return StepResult(status="success", summary=node.id)

    monkeypatch.setattr(runner, "_run_node", fake_run_node)

    result = run_flow(config, goal="recover")

    assert result["status"] == "success"
    assert seen == ["start", "work", "recover", "end"]
    failed = next(event for event in result["events"] if event["event_type"] == "node_finished" and event["node_id"] == "work")
    assert failed["payload"]["error"]["code"] == "timeout"


def test_validation_failure_retries_then_recovers(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = _configured_workspace(tmp_path)
    save_flow(
        tmp_path,
        {
            "nodes": [
                {
                    "id": "work",
                    "type": "skill",
                    "ref": ".agent-firewall/skills/skill-creator",
                    "params": {
                        "script": "scripts/init_skill.py",
                        "idempotent": True,
                        "retry": {"max_attempts": 2},
                        "validate": {"required": ["ok"], "equals": {"ok": True}},
                    },
                }
            ],
            "edges": [],
        },
    )
    calls = 0

    def fake_run_node(config, node, packet):
        nonlocal calls
        if node.id == "work":
            calls += 1
            return StepResult(status="success", summary="work", output={"ok": calls == 2})
        return StepResult(status="success", summary=node.id)

    monkeypatch.setattr(runner, "_run_node", fake_run_node)

    result = run_flow(config, goal="validate")

    assert result["status"] == "success"
    assert calls == 2
    assert any(event["event_type"] == "node_retrying" for event in result["events"])


def test_paused_run_resumes_same_checkpoint(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = _configured_workspace(tmp_path)
    save_flow(
        tmp_path,
        {
            "nodes": [
                {
                    "id": "approval",
                    "type": "agent",
                    "ref": "default",
                    "params": {"requires_approval": True},
                }
            ],
            "edges": [],
        },
    )
    monkeypatch.setattr(
        runner,
        "build_agent_sync",
        lambda config, name, **_kwargs: lambda payload: {"messages": [{"content": "approved"}]},
    )

    paused = run_flow(config, goal="approve")
    resumed = resume_flow(config, paused["run_id"], correction="approved")

    assert paused["status"] == "needs_input"
    assert resumed["status"] == "success"
    assert paused["run_id"] == resumed["run_id"]
    assert any(event["event_type"] == "run_resumed" for event in resumed["events"])


def test_failed_run_resumes_from_failed_node(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = _configured_workspace(tmp_path)
    save_flow(
        tmp_path,
        {
            "nodes": [_skill_node("prepare"), _skill_node("work")],
            "edges": [{"from": "prepare", "to": "work"}],
        },
    )
    calls: list[str] = []
    fixed = False

    def fake_run_node(config, node, packet):
        nonlocal fixed
        calls.append(node.id)
        if node.id == "work" and not fixed:
            return StepResult(
                status="failed",
                summary="bad output",
                error={"code": "validation_error", "message": "bad output", "retryable": False},
            )
        if node.id == "work" and packet.correction == "fixed":
            fixed = True
        return StepResult(status="success", summary=node.id)

    monkeypatch.setattr(runner, "_run_node", fake_run_node)

    failed = run_flow(config, goal="repair")
    fixed = True
    resumed = resume_flow(config, failed["run_id"], correction="fixed")

    assert failed["status"] == "failed"
    assert resumed["status"] == "success"
    assert calls.count("prepare") == 1
    assert calls.count("work") == 2


def test_retries_require_idempotent_node(tmp_path: Path) -> None:
    config = _configured_workspace(tmp_path)
    save_flow(
        tmp_path,
        {
            "nodes": [
                {
                    **_skill_node("work"),
                    "params": {
                        "script": "scripts/init_skill.py",
                        "retry": {"max_attempts": 2},
                    },
                }
            ],
            "edges": [],
        },
    )

    with pytest.raises(FlowError, match="idempotent"):
        run_flow(config, goal="unsafe retry")


def _configured_workspace(tmp_path: Path):
    write_default_config(tmp_path)
    install_bundled_skills(tmp_path)
    return load_config(workspace=tmp_path)


def _skill_node(node_id: str) -> dict:
    return {
        "id": node_id,
        "type": "skill",
        "ref": ".agent-firewall/skills/skill-creator",
        "params": {"script": "scripts/init_skill.py"},
    }
