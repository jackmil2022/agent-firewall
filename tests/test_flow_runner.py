import sqlite3
from pathlib import Path

from agent_firewall.config import load_config, write_default_config
from agent_firewall.flow import load_flow, save_flow
from agent_firewall.runner import run_flow
from agent_firewall.skills import install_bundled_skills
from agent_firewall.store import AgentFirewallStore


def test_flow_saved_to_sqlite(tmp_path: Path) -> None:
    write_default_config(tmp_path)
    install_bundled_skills(tmp_path)
    config = load_config(workspace=tmp_path)
    flow = {
        "nodes": [{"id": "skill:creator", "type": "skill", "ref": ".agent-firewall/skills/skill-creator"}],
        "edges": [],
    }

    save_flow(tmp_path, flow)

    loaded = load_flow(tmp_path, config)
    assert loaded.nodes[0].id == "skill:creator"
    assert AgentFirewallStore(tmp_path).get_flow()["nodes"][0]["id"] == "skill:creator"


def test_runner_writes_run_and_events_to_sqlite(tmp_path: Path) -> None:
    write_default_config(tmp_path)
    install_bundled_skills(tmp_path)
    config = load_config(workspace=tmp_path)
    save_flow(
        tmp_path,
        {
            "nodes": [{"id": "skill:creator", "type": "skill", "ref": ".agent-firewall/skills/skill-creator"}],
            "edges": [],
        },
    )

    result = run_flow(config, goal="validate sqlite logs")

    assert result["status"] == "success"
    db = sqlite3.connect(AgentFirewallStore(tmp_path).path)
    try:
        run_count = db.execute("select count(*) from runs where run_id = ?", (result["run_id"],)).fetchone()[0]
        event_count = db.execute("select count(*) from run_events where run_id = ?", (result["run_id"],)).fetchone()[0]
    finally:
        db.close()
    assert run_count == 1
    assert event_count >= 3
