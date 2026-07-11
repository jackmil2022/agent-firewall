from pathlib import Path

from agent_firewall.config import load_config, write_default_config
from agent_firewall.handoff import StepResult
from agent_firewall.revisions import apply_revision, create_revision, revert_revision, review_revision
from agent_firewall.skills import install_bundled_skills
from agent_firewall.store import AgentFirewallStore
from agent_firewall.workbench import compare_test_runs, run_test_case, save_test_case, set_test_run_baseline


def test_skill_binding_revision_runs_candidate_manifest_and_can_revert(tmp_path, monkeypatch) -> None:
    write_default_config(tmp_path)
    install_bundled_skills(tmp_path)
    config = load_config(workspace=tmp_path)
    store = AgentFirewallStore(tmp_path)
    skill_ref = ".agent-firewall/skills/skill-creator"
    manifest = tmp_path / skill_ref / "SKILL.md"
    before = manifest.read_text(encoding="utf-8")
    after = before + "\nCandidate instruction.\n"
    case = save_test_case(config, {
        "name": "skill instruction regression", "target_type": "skill_binding", "target_ref": skill_ref,
        "goal": "use the bound skill", "input_json": {"agent": "default"},
        "assertions_json": [{"kind": "status", "expected": "success"}],
    })
    observed = []

    def run_node(effective, node, *_args, **_kwargs):
        path = Path(effective.agents[node.ref].skills[0]) / "skill-creator" / "SKILL.md"
        observed.append(path.read_text(encoding="utf-8"))
        return StepResult(status="success", summary="ok", output={})

    monkeypatch.setattr("agent_firewall.runner.run_capability_node", run_node)
    baseline = run_test_case(config, case["id"])
    set_test_run_baseline(config, baseline["run_id"])
    revision = create_revision(config, target_type="skill_binding", target_ref=skill_ref, after={"content": after}, reason="repair instruction", test_case_id=case["id"], baseline_run_id=baseline["run_id"])
    candidate = run_test_case(config, case["id"], revision_id=revision["id"])
    comparison = compare_test_runs(config, baseline["run_id"], candidate["run_id"])
    review_revision(config, revision["id"], comparison["id"])

    assert observed == [before, after]
    assert manifest.read_text(encoding="utf-8") == before
    apply_revision(config, revision["id"])
    assert manifest.read_text(encoding="utf-8") == after
    revert_revision(config, revision["id"])
    assert manifest.read_text(encoding="utf-8") == before
