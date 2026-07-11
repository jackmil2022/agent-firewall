from pathlib import Path

from agent_firewall.policy import (
    ExecutionPolicy,
    check_operation,
    redact_data,
    redact_secrets,
    subprocess_environment,
)


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


def test_policy_enforces_network_host_and_environment_allowlists(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ALLOWED_VALUE", "visible")
    monkeypatch.setenv("DENIED_VALUE", "hidden")
    policy = ExecutionPolicy(
        workspace=tmp_path,
        allow_network=True,
        allowed_network_hosts=["api.example.com", "*.internal.example"],
        allowed_env_vars=["ALLOWED_VALUE"],
    )

    assert check_operation(policy, kind="mcp:search", network_host="api.example.com")["allowed"] is True
    assert check_operation(policy, kind="mcp:search", network_host="svc.internal.example")["allowed"] is True
    assert check_operation(policy, kind="mcp:search", network_host="metadata.local")["code"] == "network_host_denied"

    environment = subprocess_environment(policy)
    assert environment["ALLOWED_VALUE"] == "visible"
    assert "DENIED_VALUE" not in environment


def test_policy_redacts_nested_secret_values_and_sensitive_fields(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("WORK_API_KEY", "super-secret")

    assert redact_data(
        {"message": "failed with super-secret", "authorization": "Bearer literal", "items": ["super-secret"]},
        ["WORK_API_KEY"],
    ) == {
        "message": "failed with [REDACTED]",
        "authorization": "[REDACTED]",
        "items": ["[REDACTED]"],
    }
