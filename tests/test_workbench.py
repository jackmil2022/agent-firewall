from pathlib import Path

from agent_firewall.config import load_config, write_default_config
from agent_firewall.skills import install_bundled_skills
from agent_firewall.store import AgentFirewallStore
from agent_firewall.workbench import run_test_case


def test_script_action_case_records_assertions_and_diagnosis(tmp_path: Path) -> None:
    write_default_config(tmp_path)
    install_bundled_skills(tmp_path)
    store = AgentFirewallStore(tmp_path)
    case = store.save_test_case(
        {
            "name": "deterministic smoke",
            "target_type": "script_action",
            "target_ref": ".agent-firewall/skills/skill-creator",
            "goal": "verify workbench",
            "input_json": {"script": "scripts/workbench_echo.py"},
            "assertions_json": [
                {"kind": "status", "expected": "success"},
                {"kind": "output_equals", "path": "ok", "expected": True},
            ],
        }
    )

    result = run_test_case(load_config(workspace=tmp_path), case["id"])

    assert result["status"] == "success"
    assert result["assertions"]["passed"] is True
    assert result["diagnosis"] is None
    details = store.get_run_details(result["run_id"])
    assert details is not None
    assert any(event["event_type"] == "assertions_evaluated" for event in details["events"])


def test_failing_assertion_becomes_output_diagnosis(tmp_path: Path) -> None:
    write_default_config(tmp_path)
    install_bundled_skills(tmp_path)
    store = AgentFirewallStore(tmp_path)
    case = store.save_test_case(
        {
            "name": "bad expectation",
            "target_type": "script_action",
            "target_ref": ".agent-firewall/skills/skill-creator",
            "goal": "verify workbench",
            "input_json": {"script": "scripts/workbench_echo.py"},
            "assertions_json": [{"kind": "output_equals", "path": "ok", "expected": False}],
        }
    )

    result = run_test_case(load_config(workspace=tmp_path), case["id"])

    assert result["status"] == "failed"
    assert result["diagnosis"]["layer"] == "output"
