from __future__ import annotations

from typing import Any


FAILURE_LAYERS = {
    "mcp_server_not_found": "connection",
    "dependency_missing": "connection",
    "skill_not_found": "discovery",
    "script_not_found": "discovery",
    "mcp_tool_not_found": "selection",
    "mcp_tool_not_discovered": "discovery",
    "invalid_arguments": "argument",
    "invalid_schema": "discovery",
    "timeout": "execution",
    "script_failed": "execution",
    "exception": "execution",
    "validation_error": "output",
    "approval_required": "policy",
    "agent_interrupted": "policy",
    "regression": "regression",
}


def classify_failure(error: dict[str, Any]) -> dict[str, str]:
    code = str(error.get("code") or "unknown")
    return {"layer": FAILURE_LAYERS.get(code, "execution"), "code": code, "message": str(error.get("message") or "")}


def evaluate_assertions(
    result: dict[str, Any], assertions: list[dict[str, Any]], *, status: str
) -> dict[str, Any]:
    checks = [_evaluate_assertion(result, assertion, status) for assertion in assertions]
    return {"passed": all(check["passed"] for check in checks), "results": checks}


def _evaluate_assertion(result: dict[str, Any], assertion: dict[str, Any], status: str) -> dict[str, Any]:
    if not isinstance(assertion, dict):
        return {"passed": False, "kind": "invalid", "message": "assertion must be an object"}
    kind = str(assertion.get("kind") or "")
    expected = assertion.get("expected")
    try:
        if kind == "status":
            actual = status
            label = "status"
        elif kind == "output_equals":
            path = str(assertion.get("path") or "")
            actual = _read_path(result.get("output") or {}, path)
            label = f"output.{path}"
        elif kind == "summary_contains":
            actual = str(result.get("summary") or "")
            passed = str(expected) in actual
            return {
                "passed": passed,
                "kind": kind,
                "message": f"summary must contain {expected!r}" if not passed else "passed",
            }
        elif kind == "min_artifacts":
            actual = len(result.get("artifacts") or [])
            passed = actual >= int(expected)
            return {
                "passed": passed,
                "kind": kind,
                "message": f"artifacts expected at least {expected}, got {actual}" if not passed else "passed",
            }
        else:
            return {"passed": False, "kind": kind, "message": f"unsupported assertion kind: {kind}"}
    except (TypeError, ValueError) as exc:
        return {"passed": False, "kind": kind or "invalid", "message": f"invalid assertion: {exc}"}
    passed = actual == expected
    return {
        "passed": passed,
        "kind": kind,
        "message": "passed" if passed else f"{label} expected {expected!r}, got {actual!r}",
    }


def _read_path(value: Any, path: str) -> Any:
    current = value
    for part in path.split(".") if path else []:
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current
