from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .config import APP_DIR, AgentFirewallConfig
from .store import AgentFirewallStore, snapshot_hash

FLOW_FILE = "flow.json"
NODE_TYPES = {"start", "end", "agent", "skill", "mcp"}
EDGE_STATUSES = {"success", "failed", "needs_input", "blocked", "always"}


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
        on = str(data.get("on") or "success")
        if on not in EDGE_STATUSES:
            raise FlowError(f"unsupported edge status '{on}'")
        pass_fields = data.get("pass", [])
        if not isinstance(pass_fields, list):
            raise FlowError("flow edge pass must be a list")
        return cls(
            from_node=from_node,
            to_node=to_node,
            on=on,
            pass_fields=[str(item) for item in pass_fields],
        )


@dataclass(frozen=True)
class FlowSpec:
    nodes: list[FlowNode]
    edges: list[FlowEdge]
    max_steps: int = 20
    max_loop_iterations: int = 3

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "FlowSpec":
        if not isinstance(data, dict):
            raise FlowError("flow must be an object")
        data = ensure_boundary_nodes(data)
        nodes = [FlowNode.from_mapping(item) for item in data.get("nodes", [])]
        edges = [FlowEdge.from_mapping(item) for item in data.get("edges", [])]
        if not nodes:
            raise FlowError("flow requires at least one node")
        node_ids = [node.id for node in nodes]
        duplicates = sorted({node_id for node_id in node_ids if node_ids.count(node_id) > 1})
        if duplicates:
            raise FlowError(f"flow node ids must be unique: {', '.join(duplicates)}")
        unsupported = sorted({node.type for node in nodes if node.type not in NODE_TYPES})
        if unsupported:
            raise FlowError(f"unsupported flow node type(s): {', '.join(unsupported)}")
        node_ids = {node.id for node in nodes}
        for edge in edges:
            if edge.from_node not in node_ids or edge.to_node not in node_ids:
                raise FlowError(f"flow edge references unknown node: {edge.from_node} -> {edge.to_node}")
            if edge.from_node == edge.to_node:
                raise FlowError(f"flow edge cannot target itself: {edge.from_node}")
        limits = dict(data.get("limits") or {})
        spec = cls(
            nodes=nodes,
            edges=edges,
            max_steps=int(limits.get("max_steps", data.get("max_steps", 20))),
            max_loop_iterations=int(limits.get("max_loop_iterations", data.get("max_loop_iterations", 3))),
        )
        validate_flow(spec, require_connected=False)
        return spec

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
        return [node for node in self.nodes if node.type == "start"]

    def incoming(self, node_id: str) -> list[FlowEdge]:
        return [edge for edge in self.edges if edge.to_node == node_id]


def validate_flow(
    flow: FlowSpec,
    config: AgentFirewallConfig | None = None,
    *,
    check_resources: bool = False,
    require_connected: bool = True,
) -> None:
    if flow.max_steps < 1:
        raise FlowError("flow max_steps must be at least 1")
    if flow.max_loop_iterations < 1:
        raise FlowError("flow max_loop_iterations must be at least 1")
    starts = [node for node in flow.nodes if node.type == "start"]
    ends = [node for node in flow.nodes if node.type == "end"]
    if len(starts) != 1 or len(ends) != 1:
        raise FlowError("flow requires exactly one start node and one end node")
    start, end = starts[0], ends[0]
    if flow.incoming(start.id):
        raise FlowError("start node cannot have incoming edges")
    if flow.outgoing(end.id, "success") or any(edge.from_node == end.id for edge in flow.edges):
        raise FlowError("end node cannot have outgoing edges")

    adjacency = {node.id: [] for node in flow.nodes}
    reverse = {node.id: [] for node in flow.nodes}
    for edge in flow.edges:
        adjacency[edge.from_node].append(edge.to_node)
        reverse[edge.to_node].append(edge.from_node)
    if require_connected:
        reachable = _walk(start.id, adjacency)
        unreachable = sorted(set(adjacency) - reachable)
        if unreachable:
            raise FlowError(f"flow contains nodes unreachable from start: {', '.join(unreachable)}")
        can_finish = _walk(end.id, reverse)
        dead_ends = sorted(set(adjacency) - can_finish)
        if dead_ends:
            raise FlowError(f"flow contains nodes that cannot reach end: {', '.join(dead_ends)}")
    _assert_acyclic(adjacency)

    if check_resources:
        if config is None:
            raise FlowError("resource validation requires config")
        for node in flow.nodes:
            _validate_node_resource(node, config)


def _walk(start: str, graph: dict[str, list[str]]) -> set[str]:
    seen: set[str] = set()
    pending = [start]
    while pending:
        node_id = pending.pop()
        if node_id in seen:
            continue
        seen.add(node_id)
        pending.extend(graph[node_id])
    return seen


def _assert_acyclic(graph: dict[str, list[str]]) -> None:
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node_id: str) -> None:
        if node_id in visiting:
            raise FlowError(f"flow cycles are not supported; cycle includes {node_id}")
        if node_id in visited:
            return
        visiting.add(node_id)
        for target in graph[node_id]:
            visit(target)
        visiting.remove(node_id)
        visited.add(node_id)

    for node_id in graph:
        visit(node_id)


def _validate_node_resource(node: FlowNode, config: AgentFirewallConfig) -> None:
    if node.type == "agent":
        agent_key = node.ref or config.active_agent
        if agent_key not in config.agents:
            raise FlowError(f"agent node '{node.id}' references unknown agent '{agent_key}'")
    elif node.type == "skill":
        value = node.ref or str(node.meta.get("path") or "")
        skill_dir = _resolve_resource_path(config.workspace, value).resolve()
        if not (skill_dir / "SKILL.md").is_file():
            fallback = config.workspace / APP_DIR / "skills" / (value or node.id.split(":", 1)[-1])
            if not (fallback / "SKILL.md").is_file():
                raise FlowError(f"skill node '{node.id}' manifest not found")
            skill_dir = fallback.resolve()
        script = node.params.get("script")
        if not script:
            raise FlowError(f"skill node '{node.id}' requires params.script")
        if not isinstance(script, str):
            raise FlowError(f"skill node '{node.id}' script must be a string")
        script_path = (skill_dir / script).resolve()
        if not script_path.is_relative_to(skill_dir):
            raise FlowError(f"skill node '{node.id}' script must stay inside the skill directory")
        if script_path.suffix.lower() != ".py":
            raise FlowError(f"skill node '{node.id}' only supports Python Script Actions")
        if not script_path.is_file():
            raise FlowError(f"skill node '{node.id}' script not found: {script}")
    elif node.type == "mcp":
        server_key = str(node.params.get("server") or node.ref)
        agent_key = str(node.meta.get("agent") or config.active_agent)
        agent = config.agents.get(agent_key)
        if not agent:
            raise FlowError(f"mcp node '{node.id}' references unknown agent '{agent_key}'")
        if isinstance(node.meta.get("config"), dict):
            raise FlowError(f"mcp node '{node.id}' cannot use inline server config")
        if server_key not in agent.mcp_servers:
            raise FlowError(f"mcp node '{node.id}' references unknown server '{server_key}'")
        tool_name = str(node.params.get("tool") or "")
        if not tool_name:
            raise FlowError(f"mcp node '{node.id}' requires params.tool")
        if not isinstance(node.params.get("args", {}), dict):
            raise FlowError(f"mcp node '{node.id}' params.args must be an object")
        discovered = AgentFirewallStore(config.workspace).get_discovered_mcp_tool(
            agent_key, server_key, tool_name
        )
        if not discovered:
            raise FlowError(f"mcp node '{node.id}' tool was not discovered: {tool_name}")
        if discovered.get("server_config_hash") != snapshot_hash(agent.mcp_servers[server_key]):
            raise FlowError(f"mcp node '{node.id}' tool discovery is stale: {tool_name}")
        schema = discovered.get("input_schema")
        if not schema:
            raise FlowError(f"mcp node '{node.id}' tool has no discovered input schema: {tool_name}")
        args = _mcp_node_args(node)
        try:
            from jsonschema import SchemaError, ValidationError, validate

            validate(instance=args, schema=schema)
        except (SchemaError, ValidationError) as exc:
            raise FlowError(f"mcp node '{node.id}' arguments do not match discovered schema: {exc.message}") from exc
    retry = dict(node.params.get("retry") or {})
    if int(retry.get("max_attempts", 1)) > 1 and not node.params.get("idempotent"):
        raise FlowError(f"node '{node.id}' must set params.idempotent=true before enabling retries")


def _resolve_resource_path(workspace: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else workspace / path


def _mcp_node_args(node: FlowNode) -> dict[str, Any]:
    input_value = node.params.get("input")
    args = dict(input_value) if isinstance(input_value, dict) else {}
    if input_value is not None and not isinstance(input_value, dict):
        args["input"] = input_value
    args.update(node.params.get("args") or {})
    return args


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


def preflight_flow(data: dict[str, Any], config: AgentFirewallConfig) -> dict[str, Any]:
    skill_issue = next(
        (
            FlowNode.from_mapping(raw_node)
            for raw_node in data.get("nodes", [])
            if str(raw_node.get("type") or "") == "skill"
            and not dict(raw_node.get("params") or {}).get("script")
        ),
        None,
    )
    if skill_issue:
        return {
            "valid": False,
            "issues": [
                {
                    "node_id": skill_issue.id,
                    "field": "params.script",
                    "code": "skill_script_required",
                    "message": (
                        "Skill bindings are Agent resources. Select a script to create an executable "
                        "Script action."
                    ),
                }
            ],
        }
    try:
        flow = FlowSpec.from_mapping(data)
        validate_flow(flow, config, check_resources=True)
    except FlowError as exc:
        return {
            "valid": False,
            "issues": [{"node_id": "", "field": "", "code": "invalid_flow", "message": str(exc)}],
        }
    return {"valid": True, "issues": []}


def default_flow(config: AgentFirewallConfig) -> dict[str, Any]:
    nodes: list[dict[str, Any]] = [
        {
            "id": f"agent:{config.active_agent}",
            "type": "agent",
            "label": config.active.name,
            "ref": config.active_agent,
            "meta": {"model": config.active.model, "key": config.active_agent},
        }
    ]
    return ensure_boundary_nodes({
        "nodes": nodes,
        "edges": [],
        "limits": {"max_steps": 20, "max_loop_iterations": 3},
    })


def ensure_boundary_nodes(data: dict[str, Any]) -> dict[str, Any]:
    nodes = [dict(item) for item in data.get("nodes", [])]
    edges = [dict(item) for item in data.get("edges", [])]
    node_ids = {str(node.get("id")) for node in nodes}
    if not nodes:
        return data

    if "start" not in node_ids:
        starts = _flow_start_ids(nodes, edges)
        start_x, start_y = _boundary_position(nodes, starts, side="start")
        nodes.insert(0, {"id": "start", "type": "start", "label": "开始", "x": start_x, "y": start_y})
        edges.extend({"from": "start", "to": node_id, "on": "success"} for node_id in starts)
        node_ids.add("start")

    if "end" not in node_ids:
        leaves = _flow_leaf_ids(nodes, edges)
        end_x, end_y = _boundary_position(nodes, leaves, side="end")
        nodes.append({"id": "end", "type": "end", "label": "结束", "x": end_x, "y": end_y})
        edges.extend({"from": node_id, "to": "end", "on": "success"} for node_id in leaves if node_id != "start")

    return {**data, "nodes": nodes, "edges": _dedupe_edges(edges)}


def _flow_start_ids(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> list[str]:
    targets = {str(edge.get("to") or edge.get("to_node")) for edge in edges}
    return [str(node["id"]) for node in nodes if str(node.get("id")) not in targets and str(node.get("id")) != "end"]


def _flow_leaf_ids(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> list[str]:
    sources = {str(edge.get("from") or edge.get("from_node")) for edge in edges}
    return [str(node["id"]) for node in nodes if str(node.get("id")) not in sources and str(node.get("id")) != "end"]


def _dedupe_edges(edges: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for edge in edges:
        key = (str(edge.get("from") or edge.get("from_node")), str(edge.get("to") or edge.get("to_node")), str(edge.get("on") or "success"))
        if key not in seen:
            seen.add(key)
            result.append(edge)
    return result


def _boundary_position(nodes: list[dict[str, Any]], anchor_ids: list[str], *, side: str) -> tuple[int, int]:
    anchors = [node for node in nodes if str(node.get("id")) in set(anchor_ids)] or nodes
    xs = [int(node.get("x") or 360) for node in nodes]
    ys = [int(node.get("y") or 220) for node in anchors]
    y = int(sum(ys) / len(ys)) if ys else 220
    if side == "start":
        return max(40, min(xs) - 320), y
    return max(xs) + 340, y


def _legacy_ref(node_id: str, node_type: str, meta: dict[str, Any]) -> str:
    if node_type == "agent":
        return str(meta.get("key") or node_id.split(":", 1)[-1])
    if node_type == "skill":
        return str(meta.get("path") or node_id.split(":", 1)[-1])
    if node_type == "mcp":
        return str(meta.get("key") or node_id.split(":", 1)[-1])
    return str(meta.get("ref") or node_id)
