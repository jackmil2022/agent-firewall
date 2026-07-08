const state = {
  workspace: null,
  data: null,
  activeTab: "agents",
  selectedNodeId: null,
  linkMode: false,
  linkSource: null,
  drag: null
};

const els = {
  workspacePath: document.querySelector("#workspacePath"),
  inventoryCount: document.querySelector("#inventoryCount"),
  inventoryList: document.querySelector("#inventoryList"),
  flowCanvas: document.querySelector("#flowCanvas"),
  edgeLayer: document.querySelector("#edgeLayer"),
  flowStats: document.querySelector("#flowStats"),
  selectedType: document.querySelector("#selectedType"),
  detailsBody: document.querySelector("#detailsBody"),
  acpSummary: document.querySelector("#acpSummary"),
  chooseWorkspace: document.querySelector("#chooseWorkspace"),
  startFlow: document.querySelector("#startFlow"),
  saveFlow: document.querySelector("#saveFlow"),
  clearFlow: document.querySelector("#clearFlow"),
  linkMode: document.querySelector("#linkMode")
  ,
  runStatus: document.querySelector("#runStatus"),
  runOutput: document.querySelector("#runOutput")
};

window.addEventListener("DOMContentLoaded", async () => {
  wireEvents();
  await loadWorkspace();
});

function wireEvents() {
  document.querySelectorAll(".tab").forEach((button) => {
    button.addEventListener("click", () => {
      state.activeTab = button.dataset.tab;
      document.querySelectorAll(".tab").forEach((tab) => tab.classList.remove("active"));
      button.classList.add("active");
      renderInventory();
    });
  });

  els.chooseWorkspace.addEventListener("click", async () => {
    const result = await window.agentFirewall.chooseWorkspace();
    if (result) setWorkspaceData(result);
  });

  els.saveFlow.addEventListener("click", async () => {
    await saveFlow("manual");
  });

  els.startFlow.addEventListener("click", async () => {
    if (!state.workspace || !state.data) return;
    els.startFlow.disabled = true;
    els.runStatus.textContent = "启动中";
    els.runOutput.textContent = "正在保存编排并启动已配置的智能体...";
    try {
      const result = await window.agentFirewall.startFlow(state.workspace, currentFlow());
      els.runStatus.textContent = result.ok ? "已启动" : translateStatus(result.status);
      els.runOutput.textContent = formatRunResult(result);
      els.workspacePath.textContent = `${state.workspace} / 编排已保存`;
    } catch (error) {
      els.runStatus.textContent = "错误";
      els.runOutput.textContent = error.message;
    } finally {
      els.startFlow.disabled = false;
    }
  });

  els.clearFlow.addEventListener("click", () => {
    state.data.flow = { nodes: [], edges: [], updatedAt: new Date().toISOString() };
    state.selectedNodeId = null;
    renderCanvas();
    renderDetails();
    scheduleAutosave();
  });

  els.linkMode.addEventListener("click", () => {
    state.linkMode = !state.linkMode;
    state.linkSource = null;
    els.linkMode.classList.toggle("active", state.linkMode);
  });

  els.flowCanvas.addEventListener("dragover", (event) => event.preventDefault());
  els.flowCanvas.addEventListener("drop", (event) => {
    event.preventDefault();
    const raw = event.dataTransfer.getData("application/json");
    if (!raw) return;
    const asset = JSON.parse(raw);
    const rect = els.flowCanvas.getBoundingClientRect();
    addNode(asset, event.clientX - rect.left, event.clientY - rect.top);
  });

  window.addEventListener("mousemove", onMouseMove);
  window.addEventListener("mouseup", () => {
    state.drag = null;
  });
  window.addEventListener("resize", renderEdges);
}

async function loadWorkspace() {
  try {
    const result = await window.agentFirewall.loadWorkspace();
    setWorkspaceData(result);
  } catch (error) {
    els.workspacePath.textContent = error.message;
  }
}

function setWorkspaceData(data) {
  state.workspace = data.workspace;
  state.data = data;
  state.selectedNodeId = data.flow.nodes[0] ? data.flow.nodes[0].id : null;
  els.workspacePath.textContent = data.workspace;
  els.acpSummary.textContent = data.acp.enabled ? "已启用 / stdio" : "已禁用";
  renderInventory();
  renderCanvas();
  renderDetails();
  scheduleAutosave();
}

function inventoryItems() {
  if (!state.data) return [];
  if (state.activeTab === "agents") {
    return state.data.agents.map((agent) => ({
      id: agent.key,
      type: "agent",
      label: agent.name,
      subtitle: agent.model,
      description: agent.systemPrompt,
      meta: agent
    }));
  }
  if (state.activeTab === "skills") {
    return state.data.skills.map((skill) => ({
      id: skill.id,
      type: "skill",
      label: skill.name,
      subtitle: skill.path,
      description: skill.description,
      meta: skill
    }));
  }
  return state.data.mcpServers.map((server) => ({
    id: server.id,
    type: "mcp",
    label: server.key,
    subtitle: server.agent,
    description: JSON.stringify(server.config),
    meta: server
  }));
}

function renderInventory() {
  const items = inventoryItems();
  els.inventoryCount.textContent = String(items.length);
  els.inventoryList.innerHTML = "";
  if (items.length === 0) {
    els.inventoryList.innerHTML = '<div class="asset-card"><p>当前没有配置项目。</p></div>';
    return;
  }
  items.forEach((item) => {
    const card = document.createElement("article");
    card.className = "asset-card";
    card.draggable = true;
    card.innerHTML = `
      <div class="asset-top">
        <h2>${escapeHtml(item.label)}</h2>
        <span class="pill ${item.type}">${translateType(item.type)}</span>
      </div>
      <p>${escapeHtml(item.subtitle || item.description || "")}</p>
    `;
    card.addEventListener("dragstart", (event) => {
      event.dataTransfer.setData("application/json", JSON.stringify(item));
    });
    card.addEventListener("dblclick", () => addNode(item, 420, 160 + state.data.flow.nodes.length * 24));
    els.inventoryList.appendChild(card);
  });
}

function addNode(asset, x, y) {
  const baseId = `${asset.type}:${asset.id}`;
  const existing = state.data.flow.nodes.filter((node) => node.id.startsWith(baseId)).length;
  const id = existing ? `${baseId}:${existing + 1}` : baseId;
  state.data.flow.nodes = [
    ...state.data.flow.nodes,
    {
      id,
      type: asset.type,
      label: asset.label,
      x: clamp(x - 99, 12, Math.max(12, els.flowCanvas.clientWidth - 220)),
      y: clamp(y - 42, 12, Math.max(12, els.flowCanvas.clientHeight - 110)),
      meta: asset.meta
    }
  ];
  state.selectedNodeId = id;
  renderCanvas();
  renderDetails();
}

function renderCanvas() {
  els.flowCanvas.querySelectorAll(".flow-node").forEach((node) => node.remove());
  state.data.flow.nodes.forEach((node) => {
    const el = document.createElement("article");
    el.className = `flow-node ${node.type}${node.id === state.selectedNodeId ? " selected" : ""}`;
    el.style.left = `${node.x}px`;
    el.style.top = `${node.y}px`;
    el.dataset.nodeId = node.id;
    el.innerHTML = `
      <span class="pill ${node.type}">${translateType(node.type)}</span>
      <h3>${escapeHtml(node.label)}</h3>
      <code>${escapeHtml(node.meta?.model || node.meta?.path || node.meta?.agent || node.id)}</code>
    `;
    el.addEventListener("mousedown", (event) => startNodeDrag(event, node.id));
    el.addEventListener("click", (event) => {
      event.stopPropagation();
      handleNodeClick(node.id);
    });
    els.flowCanvas.appendChild(el);
  });
  renderEdges();
  els.flowStats.textContent = `${state.data.flow.nodes.length} 个节点 / ${state.data.flow.edges.length} 条连线`;
}

function handleNodeClick(nodeId) {
  if (state.linkMode) {
    if (!state.linkSource) {
      state.linkSource = nodeId;
      state.selectedNodeId = nodeId;
    } else if (state.linkSource !== nodeId) {
      const edge = { from: state.linkSource, to: nodeId };
      const exists = state.data.flow.edges.some((item) => item.from === edge.from && item.to === edge.to);
      if (!exists) state.data.flow.edges = [...state.data.flow.edges, edge];
      state.linkSource = null;
      scheduleAutosave();
    }
  } else {
    state.selectedNodeId = nodeId;
  }
  renderCanvas();
  renderDetails();
}

function startNodeDrag(event, nodeId) {
  const node = state.data.flow.nodes.find((item) => item.id === nodeId);
  if (!node) return;
  state.selectedNodeId = nodeId;
  state.drag = {
    nodeId,
    offsetX: event.clientX - node.x,
    offsetY: event.clientY - node.y
  };
  renderCanvas();
  renderDetails();
}

function onMouseMove(event) {
  if (!state.drag || !state.data) return;
  const node = state.data.flow.nodes.find((item) => item.id === state.drag.nodeId);
  if (!node) return;
  const rect = els.flowCanvas.getBoundingClientRect();
  node.x = clamp(event.clientX - rect.left - state.drag.offsetX, 12, Math.max(12, rect.width - 220));
  node.y = clamp(event.clientY - rect.top - state.drag.offsetY, 12, Math.max(12, rect.height - 110));
  const element = els.flowCanvas.querySelector(`[data-node-id="${cssEscape(node.id)}"]`);
  if (element) {
    element.style.left = `${node.x}px`;
    element.style.top = `${node.y}px`;
  }
  renderEdges();
  scheduleAutosave();
}

function renderEdges() {
  if (!state.data) return;
  const rect = els.flowCanvas.getBoundingClientRect();
  els.edgeLayer.setAttribute("viewBox", `0 0 ${rect.width} ${rect.height}`);
  els.edgeLayer.innerHTML = "";
  state.data.flow.edges.forEach((edge) => {
    const from = state.data.flow.nodes.find((node) => node.id === edge.from);
    const to = state.data.flow.nodes.find((node) => node.id === edge.to);
    if (!from || !to) return;
    const x1 = from.x + 198;
    const y1 = from.y + 42;
    const x2 = to.x;
    const y2 = to.y + 42;
    const mid = Math.max(40, Math.abs(x2 - x1) / 2);
    const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
    path.setAttribute("d", `M ${x1} ${y1} C ${x1 + mid} ${y1}, ${x2 - mid} ${y2}, ${x2} ${y2}`);
    path.setAttribute("stroke", "rgba(214,255,92,0.72)");
    path.setAttribute("stroke-width", "2");
    path.setAttribute("fill", "none");
    els.edgeLayer.appendChild(path);
  });
}

function renderDetails() {
  if (!state.data) return;
  const node = state.data.flow.nodes.find((item) => item.id === state.selectedNodeId);
  if (!node) {
    els.selectedType.textContent = "未选择";
    els.detailsBody.innerHTML = "<p>请选择画布上的节点。</p>";
    return;
  }
  els.selectedType.textContent = translateType(node.type);
  els.detailsBody.innerHTML = `
    <h2>${escapeHtml(node.label)}</h2>
    <p>${escapeHtml(node.id)}</p>
    <div class="kv">
      <div><span>位置</span><code>${Math.round(node.x)}, ${Math.round(node.y)}</code></div>
      <div><span>出站连线</span><code>${state.data.flow.edges.filter((edge) => edge.from === node.id).length}</code></div>
      <div><span>入站连线</span><code>${state.data.flow.edges.filter((edge) => edge.to === node.id).length}</code></div>
    </div>
    <pre>${escapeHtml(JSON.stringify(node.meta || {}, null, 2))}</pre>
  `;
}

function currentFlow() {
  return {
    nodes: state.data.flow.nodes,
    edges: state.data.flow.edges,
    updatedAt: new Date().toISOString()
  };
}

async function saveFlow(reason) {
  if (!state.workspace || !state.data) return null;
  const result = await window.agentFirewall.saveFlow(state.workspace, currentFlow());
  els.workspacePath.textContent = `${state.workspace} / ${reason === "manual" ? "手动保存" : "已自动保存"}`;
  return result;
}

let autosaveTimer = null;

function scheduleAutosave() {
  if (!state.workspace || !state.data) return;
  clearTimeout(autosaveTimer);
  autosaveTimer = setTimeout(async () => {
    try {
      await saveFlow("automatically");
    } catch (error) {
      els.runStatus.textContent = "保存错误";
      els.runOutput.textContent = error.message;
    }
  }, 450);
}

function formatRunResult(result) {
  const lines = [
    `状态: ${translateStatus(result.status)}`,
    `命令: ${result.command}`,
    `启动时间: ${result.startedAt}`,
    result.finishedAt ? `结束时间: ${result.finishedAt}` : "",
    "",
    "标准输出:",
    result.stdout || "（空）",
    "",
    "错误输出:",
    result.stderr || "（空）"
  ];
  return lines.filter((line) => line !== "").join("\n");
}

function translateStatus(status) {
  const map = {
    idle: "空闲",
    starting: "启动中",
    started: "已启动",
    failed: "失败",
    error: "错误",
    timeout: "超时"
  };
  return map[status] || status || "未知";
}

function translateType(type) {
  const map = {
    agent: "智能体",
    skill: "技能",
    mcp: "MCP"
  };
  return map[type] || type;
}

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function cssEscape(value) {
  if (window.CSS && window.CSS.escape) return window.CSS.escape(value);
  return value.replace(/"/g, '\\"');
}
