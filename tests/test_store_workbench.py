from pathlib import Path

import pytest

from agent_firewall.store import AgentFirewallStore


def test_test_case_crud(tmp_path: Path) -> None:
    store = AgentFirewallStore(tmp_path)
    created = store.save_test_case(
        {
            "name": "prompt smoke test",
            "target_type": "agent",
            "target_ref": "default",
            "goal": "answer briefly",
            "input_json": {"prompt": "hello"},
            "assertions_json": [{"type": "contains", "value": "hello"}],
        }
    )

    assert created["id"] > 0
    assert created["input_json"] == {"prompt": "hello"}
    assert store.get_test_case(created["id"]) == created

    updated = store.save_test_case({**created, "name": "renamed smoke test"})

    assert updated["name"] == "renamed smoke test"
    assert updated["created_at"] == created["created_at"]
    assert store.list_test_cases() == [updated]
    assert store.delete_test_case(created["id"]) is True
    assert store.delete_test_case(created["id"]) is False
    assert store.get_test_case(created["id"]) is None


def test_revision_lifecycle(tmp_path: Path) -> None:
    store = AgentFirewallStore(tmp_path)
    revision = store.create_revision(
        {
            "target_type": "flow",
            "target_ref": "default",
            "before_json": {"nodes": []},
            "after_json": {"nodes": [{"id": "start"}]},
            "reason": "add boundary node",
        }
    )

    assert revision["status"] == "draft"
    assert revision["applied_at"] is None
    assert store.get_revision(revision["id"]) == revision
    assert store.list_revisions() == [revision]

    applied = store.update_revision_status(revision["id"], "applied")
    assert applied["status"] == "applied"
    assert applied["applied_at"] is not None

    reverted = store.update_revision_status(revision["id"], "reverted")
    assert reverted["status"] == "reverted"
    assert reverted["applied_at"] == applied["applied_at"]
    assert store.update_revision_status(999, "applied") is None
    with pytest.raises(ValueError, match="invalid revision status"):
        store.update_revision_status(revision["id"], "invalid")


def test_comparisons_and_run_details(tmp_path: Path) -> None:
    store = AgentFirewallStore(tmp_path)
    for run_id in ("baseline", "candidate"):
        store.create_run(run_id, f"goal {run_id}", "default", {"nodes": []})
    store.log_event("candidate", "run_started", {"goal": "goal candidate"})

    comparison = store.save_comparison(
        {
            "baseline_run_id": "baseline",
            "candidate_run_id": "candidate",
            "result_json": {"passed": True, "score_delta": 0.2},
        }
    )

    assert store.get_comparison(comparison["id"]) == comparison
    assert store.list_comparisons() == [comparison]
    assert store.list_runs(limit=1)[0]["run_id"] == "candidate"
    assert store.list_runs(limit=0) == []
    assert store.get_run_details("missing") is None
    details = store.get_run_details("candidate")
    assert details is not None
    assert details["flow_snapshot"] == {"nodes": []}
    assert details["events"][0]["payload"] == {"goal": "goal candidate"}
