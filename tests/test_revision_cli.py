import json
from pathlib import Path

from agent_firewall.app import main
from agent_firewall.store import AgentFirewallStore


def test_revision_cli_creates_applies_and_reverts_agent_change(tmp_path: Path, capsys, monkeypatch) -> None:
    assert main(["--workspace", str(tmp_path), "init"]) == 0
    capsys.readouterr()
    before = AgentFirewallStore(tmp_path).get_config()["agents"]["default"]["system_prompt"]
    payload = {
        "target_type": "agent",
        "target_ref": "default",
        "after": {"system_prompt": "Use verified tools."},
        "reason": "repair tool selection",
    }
    monkeypatch.setattr("sys.stdin.read", lambda: json.dumps(payload))

    assert main(["--workspace", str(tmp_path), "revision-create"]) == 0
    revision = json.loads(capsys.readouterr().out)
    assert revision["status"] == "draft"
    assert main(["--workspace", str(tmp_path), "revision-apply", "--id", str(revision["id"])]) == 0
    capsys.readouterr()
    assert AgentFirewallStore(tmp_path).get_config()["agents"]["default"]["system_prompt"] == "Use verified tools."
    assert main(["--workspace", str(tmp_path), "revision-revert", "--id", str(revision["id"])]) == 0
    capsys.readouterr()
    assert AgentFirewallStore(tmp_path).get_config()["agents"]["default"]["system_prompt"] == before
