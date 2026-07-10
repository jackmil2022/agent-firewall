from agent_firewall.diagnostics import classify_failure, evaluate_assertions


def test_assertions_report_structured_failures() -> None:
    result = evaluate_assertions(
        {"summary": "created item", "output": {"ok": True, "count": 2}, "artifacts": []},
        [
            {"kind": "status", "expected": "success"},
            {"kind": "output_equals", "path": "ok", "expected": True},
            {"kind": "output_equals", "path": "count", "expected": 3},
            {"kind": "summary_contains", "expected": "created"},
        ],
        status="success",
    )

    assert result["passed"] is False
    assert result["results"][2] == {
        "passed": False,
        "kind": "output_equals",
        "message": "output.count expected 3, got 2",
    }


def test_failure_classifier_covers_deterministic_layers() -> None:
    cases = [
        ({"code": "mcp_server_not_found"}, "connection"),
        ({"code": "skill_not_found"}, "discovery"),
        ({"code": "mcp_tool_not_found"}, "selection"),
        ({"code": "invalid_arguments"}, "argument"),
        ({"code": "timeout"}, "execution"),
        ({"code": "validation_error"}, "output"),
        ({"code": "approval_required"}, "policy"),
        ({"code": "regression"}, "regression"),
    ]

    for error, expected in cases:
        assert classify_failure(error)["layer"] == expected
