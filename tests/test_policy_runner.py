from pathlib import Path

from agent_firewall.config import load_config, write_default_config
from agent_firewall.handoff import TaskPacket
from agent_firewall.runner import run_capability_node
from agent_firewall.skills import install_bundled_skills
from agent_firewall.flow import FlowNode


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
