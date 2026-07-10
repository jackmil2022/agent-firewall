from pathlib import Path

from agent_firewall.config import load_config, write_default_config
from agent_firewall.revisions import apply_revision, create_revision, revert_revision
from agent_firewall.store import AgentFirewallStore


def test_agent_revision_requires_review_and_can_revert(tmp_path: Path) -> None:
    write_default_config(tmp_path)
    store = AgentFirewallStore(tmp_path)
    before = store.get_config()["agents"]["default"]["system_prompt"]

    revision = create_revision(
        load_config(workspace=tmp_path),
        target_type="agent",
        target_ref="default",
        after={"system_prompt": "Use only verified tools."},
        reason="prevent unverified tool selection",
    )

    assert revision["status"] == "draft"
    assert '-  "system_prompt": "You are Agent Firewall' in revision["diff"]
    assert '+  "system_prompt": "Use only verified tools."' in revision["diff"]
    assert store.get_config()["agents"]["default"]["system_prompt"] == before

    applied = apply_revision(load_config(workspace=tmp_path), revision["id"])
    assert applied["status"] == "applied"
    assert store.get_config()["agents"]["default"]["system_prompt"] == "Use only verified tools."

    reverted = revert_revision(load_config(workspace=tmp_path), revision["id"])
    assert reverted["status"] == "reverted"
    assert store.get_config()["agents"]["default"]["system_prompt"] == before
