import json
from pathlib import Path

from agent_firewall.app import main


def test_cli_supports_case_crud_run_and_inspection(tmp_path: Path, capsys, monkeypatch) -> None:
    assert main(["--workspace", str(tmp_path), "init"]) == 0
    capsys.readouterr()
    payload = {
        "name": "CLI smoke",
        "target_type": "script_action",
        "target_ref": ".agent-firewall/skills/skill-creator",
        "goal": "cli works",
        "input_json": {"script": "scripts/workbench_echo.py"},
        "assertions_json": [{"kind": "output_equals", "path": "ok", "expected": True}],
    }
    monkeypatch.setattr("sys.stdin.read", lambda: json.dumps(payload))

    assert main(["--workspace", str(tmp_path), "test-case-save"]) == 0
    saved = json.loads(capsys.readouterr().out)
    assert main(["--workspace", str(tmp_path), "test-case-run", "--id", str(saved["id"])]) == 0
    run = json.loads(capsys.readouterr().out)
    assert run["status"] == "success"
    assert main(["--workspace", str(tmp_path), "workbench-json"]) == 0
    workspace = json.loads(capsys.readouterr().out)
    assert workspace["testCases"][0]["id"] == saved["id"]
    assert workspace["runs"][0]["run_id"] == run["run_id"]


def test_workspace_json_exposes_workbench_state(tmp_path: Path, capsys) -> None:
    assert main(["--workspace", str(tmp_path), "init"]) == 0
    capsys.readouterr()

    assert main(["--workspace", str(tmp_path), "workspace-json"]) == 0
    workspace = json.loads(capsys.readouterr().out)

    assert any(item["kind"] == "script_action" for item in workspace["capabilities"])
    assert workspace["testCases"] == []
    assert workspace["runs"] == []
