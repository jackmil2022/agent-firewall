import json
from pathlib import Path

from agent_firewall.app import main
from agent_firewall.config import load_config, write_default_config
from agent_firewall.flow import preflight_flow
from agent_firewall.store import AgentFirewallStore
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


def test_preflight_rejects_missing_or_escaping_skill_script(tmp_path: Path) -> None:
    config = _config(tmp_path)
    base = {
        "nodes": [
            {"id": "start", "type": "start"},
            {
                "id": "script:creator",
                "type": "skill",
                "ref": ".agent-firewall/skills/skill-creator",
                "params": {"script": "scripts/missing.py"},
            },
            {"id": "end", "type": "end"},
        ],
        "edges": [
            {"from": "start", "to": "script:creator"},
            {"from": "script:creator", "to": "end"},
        ],
    }

    missing = preflight_flow(base, config)
    assert missing["valid"] is False
    assert "script not found" in missing["issues"][0]["message"]

    base["nodes"][1]["params"]["script"] = "../SKILL.md"
    escaping = preflight_flow(base, config)
    assert escaping["valid"] is False
    assert "inside the skill directory" in escaping["issues"][0]["message"]


def test_flow_save_cli_refuses_invalid_resources(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    config = _config(tmp_path)
    existing = AgentFirewallStore(tmp_path).get_flow("default")
    invalid = {
        "nodes": [
            {"id": "start", "type": "start"},
            {
                "id": "script:creator",
                "type": "skill",
                "ref": ".agent-firewall/skills/skill-creator",
                "params": {"script": "scripts/missing.py"},
            },
            {"id": "end", "type": "end"},
        ],
        "edges": [
            {"from": "start", "to": "script:creator"},
            {"from": "script:creator", "to": "end"},
        ],
    }
    monkeypatch.setattr("sys.stdin.read", lambda: json.dumps(invalid))

    assert main(["--workspace", str(config.workspace), "flow-save"]) == 1
    response = json.loads(capsys.readouterr().out)
    assert response["valid"] is False
    assert AgentFirewallStore(tmp_path).get_flow("default") == existing


def test_preflight_rejects_undeclared_script_runtime(tmp_path: Path) -> None:
    config = _config(tmp_path)
    skill = tmp_path / ".agent-firewall" / "skills" / "skill-creator"
    shell_script = skill / "scripts" / "action.sh"
    shell_script.write_text("#!/bin/sh\n", encoding="utf-8")
    flow = {
        "nodes": [
            {"id": "start", "type": "start"},
            {
                "id": "script:creator",
                "type": "skill",
                "ref": ".agent-firewall/skills/skill-creator",
                "params": {"script": "scripts/action.sh"},
            },
            {"id": "end", "type": "end"},
        ],
        "edges": [
            {"from": "start", "to": "script:creator"},
            {"from": "script:creator", "to": "end"},
        ],
    }

    result = preflight_flow(flow, config)

    assert result["valid"] is False
    assert "only supports Python" in result["issues"][0]["message"]


def test_preflight_requires_current_discovered_mcp_tool_and_valid_arguments(tmp_path: Path) -> None:
    config = _config(tmp_path)
    store = AgentFirewallStore(tmp_path)
    data = store.get_config()
    data["agents"]["default"]["mcp_servers"] = {"local": {"transport": "stdio", "command": "demo"}}
    store.save_config(data)
    config = load_config(workspace=tmp_path)
    store.replace_discovered_mcp_tools(
        "default",
        "local",
        [{"tool_name": "search", "input_schema": {"type": "object", "required": ["query"]}}],
    )
    flow = {
        "nodes": [
            {"id": "start", "type": "start"},
            {
                "id": "mcp:search",
                "type": "mcp",
                "ref": "local",
                "params": {"tool": "search", "args": {"query": "ok"}},
            },
            {"id": "end", "type": "end"},
        ],
        "edges": [{"from": "start", "to": "mcp:search"}, {"from": "mcp:search", "to": "end"}],
    }
    assert preflight_flow(flow, config) == {"valid": True, "issues": []}

    flow["nodes"][1]["params"]["args"] = {}
    assert "arguments do not match" in preflight_flow(flow, config)["issues"][0]["message"]

    flow["nodes"][1]["params"]["args"] = {"query": "ok"}
    data = store.get_config()
    data["agents"]["default"]["mcp_servers"]["local"]["args"] = ["--changed"]
    store.save_config(data)
    assert "discovery is stale" in preflight_flow(flow, load_config(workspace=tmp_path))["issues"][0]["message"]
