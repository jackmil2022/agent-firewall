from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .config import APP_DIR, AgentFirewallConfig
from .skills import list_skill_manifests
from .store import AgentFirewallStore

FLOW_FILE = "flow.json"


class FlowError(ValueError):
    """Raised when a flow cannot be loaded or executed."""


@dataclass(frozen=True)
class FlowNode:
    id: str
    type: str
    label: str = ""
    ref: str = ""
    x: float | int | None = None
    y: float | int | None = None
    params: dict[str, Any] = field(default_factory=dict)
    meta: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "FlowNode":
        node_id = str(data.get("id") or "")
        node_type = str(data.get("type") or node_id.split(":", 1)[0])
        if not node_id or not node_type:
            raise FlowError("flow node requires id and type")
        meta = dict(data.get("meta") or {})
        return cls(
            id=node_id,
            type=node_type,
            label=str(data.get("label") or node_id),
            ref=str(data.get("ref") or _legacy_ref(node_id, node_type, meta)),
            x=data.get("x"),
            y=data.get("y"),
            params=dict(data.get("params") or {}),
            meta=meta,
        )


@dataclass(frozen=True)
class FlowEdge:
    from_node: str
    to_node: str
    on: str = "success"
    pass_fields: list[str] = field(default_factory=list)

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "FlowEdge":
        from_node = str(data.get("from") or data.get("from_node") or "")
        to_node = str(data.get("to") or data.get("to_node") or "")
        if not from_node or not to_node:
            raise FlowError("flow edge requires from and to")
        return cls(
            from_node=from_node,
            to_node=to_node,
            on=str(data.get("on") or "success"),
            pass_fields=[str(item) for item in data.get("pass", [])],
        )


@dataclass(frozen=True)
class FlowSpec:
    nodes: list[FlowNode]
    edges: list[FlowEdge]
    max_steps: int = 20
    max_loop_iterations: int = 3

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "FlowSpec":
        nodes = [FlowNode.from_mapping(item) for item in data.get("nodes", [])]
        edges = [FlowEdge.from_mapping(item) for item in data.get("edges", [])]
        if not nodes:
            raise FlowError("flow requires at least one node")
        node_ids = {node.id for node in nodes}
        for edge in edges:
            if edge.from_node not in node_ids or edge.to_node not in node_ids:
                raise FlowError(f"flow edge references unknown node: {edge.from_node} -> {edge.to_node}")
        limits = dict(data.get("limits") or {})
        return cls(
            nodes=nodes,
            edges=edges,
            max_steps=int(limits.get("max_steps", data.get("max_steps", 20))),
            max_loop_iterations=int(limits.get("max_loop_iterations", data.get("max_loop_iterations", 3))),
        )

    def to_mapping(self) -> dict[str, Any]:
        return {
            "nodes": [
                {
                    "id": node.id,
                    "type": node.type,
                    "label": node.label,
                    "ref": node.ref,
                    "x": node.x,
                    "y": node.y,
                    "params": node.params,
                    "meta": node.meta,
                }
                for node in self.nodes
            ],
            "edges": [
                {
                    "from": edge.from_node,
                    "to": edge.to_node,
                    "on": edge.on,
                    "pass": edge.pass_fields,
                }
                for edge in self.edges
            ],
            "limits": {
                "max_steps": self.max_steps,
                "max_loop_iterations": self.max_loop_iterations,
            },
        }

    def outgoing(self, node_id: str, status: str) -> list[FlowEdge]:
        return [edge for edge in self.edges if edge.from_node == node_id and edge.on in (status, "always")]

    def start_nodes(self) -> list[FlowNode]:
        targets = {edge.to_node for edge in self.edges}
        starts = [node for node in self.nodes if node.id not in targets]
        return starts or self.nodes[:1]


def load_flow(
    workspace: str | Path,
    config: AgentFirewallConfig,
    *,
    name: str = "default",
    path: str | Path | None = None,
) -> FlowSpec:
    root = Path(workspace).resolve()
    if path:
        return FlowSpec.from_mapping(json.loads(Path(path).read_text(encoding="utf-8")))
    store = AgentFirewallStore(root)
    data = store.get_flow(name)
    if data:
        return FlowSpec.from_mapping(data)
    legacy = root / APP_DIR / FLOW_FILE
    if legacy.exists():
        data = json.loads(legacy.read_text(encoding="utf-8"))
        store.save_flow(data, name)
        return FlowSpec.from_mapping(data)
    data = default_flow(config)
    store.save_flow(data, name)
    return FlowSpec.from_mapping(data)


def save_flow(workspace: str | Path, flow: dict[str, Any], *, name: str = "default") -> Path:
    spec = FlowSpec.from_mapping(flow)
    store = AgentFirewallStore(workspace)
    store.save_flow(spec.to_mapping(), name)
    return store.path


def default_flow(config: AgentFirewallConfig) -> dict[str, Any]:
    skills_root = config.workspace / APP_DIR / "skills"
    nodes: list[dict[str, Any]] = [
        {
            "id": f"agent:{config.active_agent}",
            "type": "agent",
            "label": config.active.name,
            "ref": config.active_agent,
            "meta": {"model": config.active.model, "key": config.active_agent},
        }
    ]
    edges: list[dict[str, Any]] = []
    for manifest in list_skill_manifests(skills_root)[:4]:
        node_id = f"skill:{manifest.name}"
        nodes.append(
            {
                "id": node_id,
                "type": "skill",
                "label": manifest.name,
                "ref": str(manifest.path),
                "meta": {"path": str(manifest.path)},
            }
        )
        edges.append({"from": f"agent:{config.active_agent}", "to": node_id, "on": "success"})
    return {
        "nodes": nodes,
        "edges": edges,
        "limits": {"max_steps": 20, "max_loop_iterations": 3},
    }


def _legacy_ref(node_id: str, node_type: str, meta: dict[str, Any]) -> str:
    if node_type == "agent":
        return str(meta.get("key") or node_id.split(":", 1)[-1])
    if node_type == "skill":
        return str(meta.get("path") or node_id.split(":", 1)[-1])
    if node_type == "mcp":
        return str(meta.get("key") or node_id.split(":", 1)[-1])
    return str(meta.get("ref") or node_id)
