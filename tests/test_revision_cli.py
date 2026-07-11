import json
from pathlib import Path

from agent_firewall.app import main
from agent_firewall.store import AgentFirewallStore


def test_revision_cli_requires_passing_review_before_apply(tmp_path: Path, capsys, monkeypatch) -> None:
    assert main(["--workspace", str(tmp_path), "init"]) == 0
    capsys.readouterr()
    payload = {
        "name": "script regression",
        "target_type": "script_action",
        "target_ref": ".agent-firewall/skills/skill-creator",
        "goal": "verify script",
        "input_json": {"script": "scripts/workbench_echo.py"},
        "assertions_json": [{"kind": "output_equals", "path": "ok", "expected": True}],
    }
    monkeypatch.setattr("sys.stdin.read", lambda: json.dumps(payload))
    assert main(["--workspace", str(tmp_path), "test-case-save"]) == 0
    case = json.loads(capsys.readouterr().out)

    assert main([
        "--workspace", str(tmp_path), "test-case-run", "--id", str(case["id"]), "--run-id", "baseline"
    ]) == 0
    capsys.readouterr()
    assert main([
        "--workspace", str(tmp_path), "test-case-baseline-set", "--id", str(case["id"]), "--run-id", "baseline"
    ]) == 0
    capsys.readouterr()

    script = tmp_path / case["target_ref"] / case["input_json"]["script"]
    original = script.read_text(encoding="utf-8")
    payload = {
        "target_type": "script_action",
        "target_ref": case["target_ref"],
        "after": {"content": original + "\n# reviewed candidate\n"},
        "reason": "prove the repair workflow",
        "test_case_id": case["id"],
        "baseline_run_id": "baseline",
    }
    assert main(["--workspace", str(tmp_path), "revision-create"]) == 0
    revision = json.loads(capsys.readouterr().out)

    assert main(["--workspace", str(tmp_path), "revision-apply", "--id", str(revision["id"])]) == 2
    assert "requires explicit review" in capsys.readouterr().err
    assert main([
        "--workspace", str(tmp_path), "test-case-run", "--id", str(case["id"]),
        "--revision-id", str(revision["id"]), "--run-id", "candidate"
    ]) == 0
    capsys.readouterr()
    assert main([
        "--workspace", str(tmp_path), "run-compare", "--baseline", "baseline", "--candidate", "candidate"
    ]) == 0
    comparison = json.loads(capsys.readouterr().out)
    assert main([
        "--workspace", str(tmp_path), "revision-review", "--id", str(revision["id"]),
        "--comparison-id", str(comparison["id"])
    ]) == 0
    capsys.readouterr()
    assert main(["--workspace", str(tmp_path), "revision-apply", "--id", str(revision["id"])]) == 0
    capsys.readouterr()
    assert "reviewed candidate" in script.read_text(encoding="utf-8")
    assert main(["--workspace", str(tmp_path), "revision-revert", "--id", str(revision["id"])]) == 0
    capsys.readouterr()
    assert script.read_text(encoding="utf-8") == original


def test_run_cancel_cli_finalizes_known_run(tmp_path: Path, capsys) -> None:
    store = AgentFirewallStore(tmp_path)
    store.create_run("cancel-me", "goal", "default", {})

    assert main(["--workspace", str(tmp_path), "run-cancel", "--run-id", "cancel-me"]) == 0

    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "cancelled"
