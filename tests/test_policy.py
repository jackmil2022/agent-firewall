from pathlib import Path

from agent_firewall.policy import ExecutionPolicy, check_operation, redact_secrets


def test_policy_blocks_paths_outside_workspace_and_protected_operations(tmp_path: Path) -> None:
    policy = ExecutionPolicy(workspace=tmp_path, require_approval=["mcp:delete"])

    outside = check_operation(policy, kind="script", path=tmp_path.parent / "outside.py")
    protected = check_operation(policy, kind="mcp:delete")
    approved = check_operation(policy, kind="mcp:delete", approved=True)

    assert outside["allowed"] is False
    assert outside["code"] == "path_outside_workspace"
    assert protected == {"allowed": False, "code": "approval_required", "message": "Approval required for mcp:delete"}
    assert approved["allowed"] is True


def test_policy_redacts_configured_environment_secrets(monkeypatch) -> None:
    monkeypatch.setenv("WORK_API_KEY", "super-secret")

    assert redact_secrets("failed with super-secret", ["WORK_API_KEY"]) == "failed with [REDACTED]"


def test_policy_supports_mcp_wildcard_approval(tmp_path: Path) -> None:
    policy = ExecutionPolicy(workspace=tmp_path, require_approval=["mcp:*"])

    assert check_operation(policy, kind="mcp:create")["code"] == "approval_required"
