from pathlib import Path

from agent_firewall.config import load_config, write_default_config
from agent_firewall.skills import install_bundled_skills
from agent_firewall.store import AgentFirewallStore
from agent_firewall.workbench import compare_test_runs, run_test_case, set_test_run_baseline


def test_same_test_case_can_save_baseline_and_compare_candidate(tmp_path: Path) -> None:
    write_default_config(tmp_path)
    install_bundled_skills(tmp_path)
    store = AgentFirewallStore(tmp_path)
    case = store.save_test_case(
        {
            "name": "echo regression",
            "target_type": "script_action",
            "target_ref": ".agent-firewall/skills/skill-creator",
            "goal": "stable result",
            "input_json": {"script": "scripts/workbench_echo.py"},
            "assertions_json": [{"kind": "output_equals", "path": "ok", "expected": True}],
        }
    )
    config = load_config(workspace=tmp_path)
    baseline = run_test_case(config, case["id"])
    set_test_run_baseline(config, baseline["run_id"])
    candidate = run_test_case(config, case["id"], baseline_run_id=baseline["run_id"])

    comparison = compare_test_runs(config, baseline["run_id"], candidate["run_id"])

    assert comparison["result_json"]["passed"] is True
    assert comparison["result_json"]["regressions"] == []
    assert store.list_comparisons()[0] == comparison
