from pathlib import Path

from agent_firewall.config import load_config, write_default_config
from agent_firewall.skills import install_bundled_skills
from agent_firewall.store import AgentFirewallStore
from agent_firewall.workbench import run_test_case


def test_test_case_can_resume_after_policy_approval(tmp_path: Path) -> None:
    write_default_config(tmp_path)
    install_bundled_skills(tmp_path)
    store = AgentFirewallStore(tmp_path)
    data = store.get_config()
    data["policy"]["require_approval"] = ["script"]
    store.save_config(data)
    case = store.save_test_case(
        {
            "name": "approved script",
            "target_type": "script_action",
            "target_ref": ".agent-firewall/skills/skill-creator",
            "goal": "run after approval",
            "input_json": {"script": "scripts/workbench_echo.py"},
            "assertions_json": [{"kind": "output_equals", "path": "ok", "expected": True}],
        }
    )
    config = load_config(workspace=tmp_path)

    paused = run_test_case(config, case["id"])
    approved = run_test_case(config, case["id"], approved=True)

    assert paused["status"] == "needs_input"
    assert paused["diagnosis"]["layer"] == "policy"
    assert approved["status"] == "success"
