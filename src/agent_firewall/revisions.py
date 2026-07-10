from __future__ import annotations

import difflib
from typing import Any

from .config import AgentFirewallConfig
from .store import AgentFirewallStore


def create_revision(
    config: AgentFirewallConfig,
    *,
    target_type: str,
    target_ref: str,
    after: dict[str, Any],
    reason: str,
) -> dict[str, Any]:
    before = _target_snapshot(config, target_type, target_ref)
    revision = AgentFirewallStore(config.workspace).create_revision(
        {
            "target_type": target_type,
            "target_ref": target_ref,
            "before_json": before,
            "after_json": {**before, **after},
            "reason": reason,
        }
    )
    return {**revision, "diff": _diff(revision["before_json"], revision["after_json"])}


def apply_revision(config: AgentFirewallConfig, revision_id: int) -> dict[str, Any]:
    store = AgentFirewallStore(config.workspace)
    revision = _revision(store, revision_id)
    if revision["status"] != "draft":
        raise ValueError(f"revision is not reviewable: {revision_id} ({revision['status']})")
    _write_target(store, revision["target_type"], revision["target_ref"], revision["after_json"])
    result = store.update_revision_status(revision_id, "applied")
    assert result is not None
    return {**result, "diff": _diff(result["before_json"], result["after_json"])}


def revert_revision(config: AgentFirewallConfig, revision_id: int) -> dict[str, Any]:
    store = AgentFirewallStore(config.workspace)
    revision = _revision(store, revision_id)
    if revision["status"] != "applied":
        raise ValueError(f"revision is not applied: {revision_id} ({revision['status']})")
    _write_target(store, revision["target_type"], revision["target_ref"], revision["before_json"])
    result = store.update_revision_status(revision_id, "reverted")
    assert result is not None
    return {**result, "diff": _diff(result["before_json"], result["after_json"])}


def _target_snapshot(config: AgentFirewallConfig, target_type: str, target_ref: str) -> dict[str, Any]:
    store = AgentFirewallStore(config.workspace)
    if target_type == "agent":
        data = store.get_config() or {}
        try:
            return dict(data["agents"][target_ref])
        except KeyError as exc:
            raise ValueError(f"agent not found: {target_ref}") from exc
    if target_type == "flow":
        flow = store.get_flow(target_ref)
        if flow is None:
            raise ValueError(f"flow not found: {target_ref}")
        return flow
    raise ValueError(f"unsupported revision target: {target_type}")


def _write_target(store: AgentFirewallStore, target_type: str, target_ref: str, value: dict[str, Any]) -> None:
    if target_type == "agent":
        data = store.get_config() or {}
        if target_ref not in (data.get("agents") or {}):
            raise ValueError(f"agent not found: {target_ref}")
        data["agents"][target_ref] = value
        store.save_config(data)
        return
    if target_type == "flow":
        store.save_flow(value, target_ref)
        return
    raise ValueError(f"unsupported revision target: {target_type}")


def _revision(store: AgentFirewallStore, revision_id: int) -> dict[str, Any]:
    revision = store.get_revision(revision_id)
    if not revision:
        raise ValueError(f"revision not found: {revision_id}")
    return revision


def _diff(before: dict[str, Any], after: dict[str, Any]) -> str:
    import json

    left = json.dumps(before, ensure_ascii=False, indent=2, sort_keys=True).splitlines()
    right = json.dumps(after, ensure_ascii=False, indent=2, sort_keys=True).splitlines()
    return "\n".join(difflib.unified_diff(left, right, fromfile="before", tofile="after", lineterm=""))
