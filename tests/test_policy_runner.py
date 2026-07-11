import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from agent_firewall.config import load_config, write_default_config
from agent_firewall.handoff import TaskPacket
from agent_firewall.runner import run_capability_node
from agent_firewall.skills import install_bundled_skills
from agent_firewall.flow import FlowNode
from agent_firewall.runner import RunnerError, resume_flow, run_flow
from agent_firewall.flow import save_flow
from agent_firewall.store import AgentFirewallStore
from agent_firewall import runner


def test_script_execution_routes_through_policy_gate(tmp_path: Path) -> None:
    write_default_config(tmp_path)
    install_bundled_skills(tmp_path)
    config = load_config(workspace=tmp_path)
    node = FlowNode(
        id="script",
        type="skill",
        ref=".agent-firewall/skills/skill-creator",
        params={"script": "scripts/workbench_echo.py"},
    )
    packet = TaskPacket(run_id="run", goal="policy", node_id="script")

    blocked = run_capability_node(config, node, packet, policy={"require_approval": ["script"]})
    approved = run_capability_node(config, node, packet, policy={"require_approval": ["script"]}, approved=True)

    assert blocked.status == "needs_input"
    assert blocked.error["code"] == "approval_required"
    assert approved.status == "success"


def test_script_receives_node_input_and_only_allowlisted_environment(tmp_path: Path, monkeypatch) -> None:
    write_default_config(tmp_path)
    skill = tmp_path / ".agent-firewall" / "skills" / "probe"
    (skill / "scripts").mkdir(parents=True)
    (skill / "SKILL.md").write_text("---\nname: probe\ndescription: probe\n---\n", encoding="utf-8")
    (skill / "scripts" / "probe.py").write_text(
        """from __future__ import annotations
import json
import os
import sys
from pathlib import Path

payload = json.load(sys.stdin)
print(json.dumps({
    "payload": payload,
    "cwd": str(Path.cwd()),
    "allowed": os.environ.get("ALLOWED_VALUE"),
    "denied": os.environ.get("DENIED_VALUE"),
}))
""",
        encoding="utf-8",
    )
    store = AgentFirewallStore(tmp_path)
    data = store.get_config()
    data["policy"]["exposed_env"] = ["ALLOWED_VALUE"]
    store.save_config(data)
    monkeypatch.setenv("ALLOWED_VALUE", "visible")
    monkeypatch.setenv("DENIED_VALUE", "hidden")
    config = load_config(workspace=tmp_path)
    node = FlowNode(
        id="probe",
        type="skill",
        ref=".agent-firewall/skills/probe",
        params={"script": "scripts/probe.py", "input": {"query": "hello"}, "custom": 7},
    )

    result = run_capability_node(config, node, TaskPacket(run_id="run", goal="inspect", node_id="probe"))

    assert result.status == "success"
    assert result.output["payload"]["params"]["input"] == {"query": "hello"}
    assert result.output["payload"]["params"]["custom"] == 7
    assert result.output["cwd"] == str(tmp_path)
    assert result.output["allowed"] == "[REDACTED]"
    assert result.output["denied"] is None


def test_agent_receives_complete_capability_input(tmp_path: Path, monkeypatch) -> None:
    write_default_config(tmp_path)
    config = load_config(workspace=tmp_path)
    captured = {}

    class FakeAgent:
        def invoke(self, payload, config=None):
            captured["payload"] = payload
            return {"messages": [{"content": "ok"}]}

    monkeypatch.setattr(runner, "build_agent_sync", lambda *_args, **_kwargs: FakeAgent())
    node = FlowNode(
        id="agent",
        type="agent",
        ref="default",
        params={"input": {"query": "hello"}, "messages": [{"role": "user", "content": "original"}]},
    )

    result = run_capability_node(config, node, TaskPacket(run_id="run", goal="inspect", node_id="agent"))

    assert result.status == "success"
    content = captured["payload"]["messages"][0]["content"]
    assert '"query": "hello"' in content
    assert '"content": "original"' in content


def test_mcp_receives_input_and_explicit_args(tmp_path: Path, monkeypatch) -> None:
    write_default_config(tmp_path)
    store = AgentFirewallStore(tmp_path)
    data = store.get_config()
    data["agents"]["default"]["mcp_servers"] = {
        "local": {"transport": "stdio", "command": "python", "args": ["server.py"]}
    }
    store.save_config(data)
    config = load_config(workspace=tmp_path)
    captured = {}

    class FakeTool:
        name = "search"

        async def ainvoke(self, args):
            captured.update(args)
            return {"ok": True}

    async def fake_load(_servers, **_kwargs):
        return [FakeTool()]

    monkeypatch.setattr(runner, "_load_mcp_tools", fake_load)
    node = FlowNode(
        id="mcp",
        type="mcp",
        ref="local",
        params={"tool": "search", "input": {"query": "hello"}, "args": {"limit": 3}},
    )

    result = run_capability_node(config, node, TaskPacket(run_id="run", goal="inspect", node_id="mcp"))

    assert result.status == "success"
    assert captured == {"query": "hello", "limit": 3}


def test_empty_command_allowlist_blocks_script(tmp_path: Path) -> None:
    write_default_config(tmp_path)
    install_bundled_skills(tmp_path)
    config = load_config(workspace=tmp_path)
    node = FlowNode(
        id="script",
        type="skill",
        ref=".agent-firewall/skills/skill-creator",
        params={"script": "scripts/workbench_echo.py"},
    )

    result = run_capability_node(
        config,
        node,
        TaskPacket(run_id="run", goal="policy", node_id="script"),
        policy={"allowed_commands": []},
    )

    assert result.status == "blocked"
    assert result.error["code"] == "command_denied"


def test_non_python_skill_script_is_rejected_explicitly(tmp_path: Path) -> None:
    write_default_config(tmp_path)
    skill = tmp_path / ".agent-firewall" / "skills" / "shell"
    (skill / "scripts").mkdir(parents=True)
    (skill / "SKILL.md").write_text("---\nname: shell\ndescription: shell\n---\n", encoding="utf-8")
    (skill / "scripts" / "run.sh").write_text("echo unsafe\n", encoding="utf-8")
    config = load_config(workspace=tmp_path)
    node = FlowNode(
        id="shell",
        type="skill",
        ref=".agent-firewall/skills/shell",
        params={"script": "scripts/run.sh"},
    )

    result = run_capability_node(config, node, TaskPacket(run_id="run", goal="policy", node_id="shell"))

    assert result.status == "blocked"
    assert result.error["code"] == "unsupported_script_runtime"


def test_policy_approval_resume_is_consumed_once(tmp_path: Path) -> None:
    write_default_config(tmp_path)
    install_bundled_skills(tmp_path)
    store = AgentFirewallStore(tmp_path)
    data = store.get_config()
    data["policy"]["require_approval"] = ["script"]
    store.save_config(data)
    save_flow(
        tmp_path,
        {
            "nodes": [
                {
                    "id": "script",
                    "type": "skill",
                    "ref": ".agent-firewall/skills/skill-creator",
                    "params": {"script": "scripts/workbench_echo.py"},
                }
            ],
            "edges": [],
        },
    )
    config = load_config(workspace=tmp_path)

    paused = run_flow(config, goal="approve")
    resumed = resume_flow(config, paused["run_id"])

    assert paused["status"] == "needs_input"
    policy_event = next(
        event
        for event in paused["events"]
        if event["event_type"] == "policy_checked" and event["payload"]["operation"] == "script"
    )
    assert policy_event["payload"] == {
        "operation": "script",
        "code": "approval_required",
        "allowed": False,
        "approval": False,
    }
    assert resumed["status"] == "success"


def test_runner_redacts_secret_from_results_and_events(tmp_path: Path, monkeypatch) -> None:
    write_default_config(tmp_path)
    skill = tmp_path / ".agent-firewall" / "skills" / "leak"
    (skill / "scripts").mkdir(parents=True)
    (skill / "SKILL.md").write_text("---\nname: leak\ndescription: leak\n---\n", encoding="utf-8")
    (skill / "scripts" / "leak.py").write_text(
        "import json, os\nprint(json.dumps({'message': os.environ['WORK_API_KEY']}))\n",
        encoding="utf-8",
    )
    store = AgentFirewallStore(tmp_path)
    data = store.get_config()
    data["policy"]["exposed_env"] = ["WORK_API_KEY"]
    store.save_config(data)
    monkeypatch.setenv("WORK_API_KEY", "super-secret")
    save_flow(
        tmp_path,
        {
            "nodes": [
                {
                    "id": "leak",
                    "type": "skill",
                    "ref": ".agent-firewall/skills/leak",
                    "params": {"script": "scripts/leak.py"},
                }
            ],
            "edges": [],
        },
    )

    result = run_flow(load_config(workspace=tmp_path), goal="redact")

    assert "super-secret" not in json.dumps(result, ensure_ascii=False)
    assert "[REDACTED]" in json.dumps(result, ensure_ascii=False)


def test_run_flow_accepts_external_run_id_and_rejects_duplicates(tmp_path: Path) -> None:
    write_default_config(tmp_path)
    config = load_config(workspace=tmp_path)

    first = run_flow(config, goal="tracked", run_id="operation-123")

    assert first["run_id"] == "operation-123"
    with pytest.raises(RunnerError, match="already exists"):
        run_flow(config, goal="duplicate", run_id="operation-123")
