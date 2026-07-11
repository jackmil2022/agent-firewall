from pathlib import Path

import pytest

from agent_firewall.config import load_config, write_default_config
from agent_firewall.revisions import apply_revision, create_revision
from agent_firewall.store import AgentFirewallStore


def test_agent_revision_cannot_apply_without_regression_review(tmp_path: Path) -> None:
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
    assert '-    "system_prompt": "You are Agent Firewall' in revision["diff"]
    assert '+    "system_prompt": "Use only verified tools."' in revision["diff"]
    assert store.get_config()["agents"]["default"]["system_prompt"] == before

    with pytest.raises(ValueError, match="explicit review"):
        apply_revision(load_config(workspace=tmp_path), revision["id"])
    assert store.get_config()["agents"]["default"]["system_prompt"] == before
