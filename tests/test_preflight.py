from pathlib import Path

from agent_firewall.config import load_config, write_default_config
from agent_firewall.flow import preflight_flow
from agent_firewall.skills import install_bundled_skills


def _config(tmp_path: Path):
    write_default_config(tmp_path)
    install_bundled_skills(tmp_path)
    return load_config(workspace=tmp_path)


def test_preflight_returns_actionable_issue_for_skill_binding_node(tmp_path: Path) -> None:
    config = _config(tmp_path)
    flow = {
        "nodes": [
            {"id": "start", "type": "start"},
            {
                "id": "skill:creator",
                "type": "skill",
                "ref": ".agent-firewall/skills/skill-creator",
            },
            {"id": "end", "type": "end"},
        ],
        "edges": [
            {"from": "start", "to": "skill:creator"},
            {"from": "skill:creator", "to": "end"},
        ],
    }

    result = preflight_flow(flow, config)

    assert result["valid"] is False
    assert result["issues"] == [
        {
            "node_id": "skill:creator",
            "field": "params.script",
            "code": "skill_script_required",
            "message": "Skill bindings are Agent resources. Select a script to create an executable Script action.",
        }
    ]


def test_preflight_accepts_explicit_skill_script_action(tmp_path: Path) -> None:
    config = _config(tmp_path)
    flow = {
        "nodes": [
            {"id": "start", "type": "start"},
            {
                "id": "script:creator",
                "type": "skill",
                "ref": ".agent-firewall/skills/skill-creator",
                "params": {"script": "scripts/init_skill.py"},
            },
            {"id": "end", "type": "end"},
        ],
        "edges": [
            {"from": "start", "to": "script:creator"},
            {"from": "script:creator", "to": "end"},
        ],
    }

    assert preflight_flow(flow, config) == {"valid": True, "issues": []}


def test_preflight_reports_invalid_graph_without_masking_parse_error(tmp_path: Path) -> None:
    config = _config(tmp_path)

    result = preflight_flow({"nodes": [{"id": "x", "type": "unknown"}], "edges": []}, config)

    assert result["valid"] is False
    assert result["issues"][0]["code"] == "invalid_flow"
