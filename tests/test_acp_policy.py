import asyncio
from pathlib import Path

from agent_firewall import acp
from agent_firewall.config import load_config, write_default_config
from agent_firewall.store import AgentFirewallStore


def test_guarded_acp_agent_does_not_trust_caller_approval(tmp_path: Path, monkeypatch) -> None:
    write_default_config(tmp_path)
    store = AgentFirewallStore(tmp_path)
    data = store.get_config()
    data["policy"]["require_approval"] = ["agent"]
    store.save_config(data)
    config = load_config(workspace=tmp_path)
    captured = []

    async def fake_build_agent(_config, _name=None, **kwargs):
        captured.append(kwargs)
        raise AssertionError("ACP caller approval must not reach agent construction")

    monkeypatch.setattr(acp, "build_agent", fake_build_agent)
    guarded = acp.GuardedAcpAgent(config)

    denied = asyncio.run(guarded.ainvoke({"messages": [{"role": "user", "content": "run"}]}))
    caller_claims_approval = asyncio.run(
        guarded.ainvoke({"approved": True, "messages": [{"role": "user", "content": "run"}]})
    )

    assert denied["status"] == "needs_input"
    assert denied["error"]["code"] == "approval_required"
    assert caller_claims_approval["status"] == "needs_input"
    assert caller_claims_approval["error"]["code"] == "approval_required"
    assert captured == []
