const state = {
  workspace: null,
  data: null,
  activeTab: "agents",
  selectedNodeId: null,
  editor: null,
  renderingFlow: false
};

const els = {
  workspacePath: document.querySelector("#workspacePath"),
  inventoryCount: document.querySelector("#inventoryCount"),
  inventoryList: document.querySelector("#inventoryList"),
  flowCanvas: document.querySelector("#flowCanvas"),
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
  initFlowEditor();
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
    renderCanvas({ fit: true });
    renderDetails();
    scheduleAutosave();
  });

  els.linkMode.addEventListener("click", () => {
    fitEditorView();
  });

  els.flowCanvas.addEventListener("dragover", (event) => event.preventDefault());
  els.flowCanvas.addEventListener("drop", (event) => {
    event.preventDefault();
    const raw = event.dataTransfer.getData("application/json");
    if (!raw) return;
    const asset = JSON.parse(raw);
    const point = canvasPointFromEvent(event);
    addAssetNode(asset, point.x, point.y);
  });
}

function initFlowEditor() {
  if (!window.Drawflow) {
    els.flowCanvas.textContent = "Drawflow 加载失败。";
    return;
  }
  const editor = new Drawflow(els.flowCanvas);
  editor.reroute = true;
  editor.reroute_fix_curvature = true;
  editor.curvature = 0.42;
  editor.reroute_curvature = 0.42;
  editor.line_path = 4;
  editor.zoom_min = 0.45;
  editor.zoom_max = 1.7;
  editor.zoom_value = 0.08;
  editor.start();
  state.editor = editor;

  editor.on("nodeSelected", (drawflowId) => {
    const node = editor.getNodeFromId(drawflowId);
    state.selectedNodeId = node?.data?.flowId || null;
    renderDetails();
  });
  editor.on("nodeUnselected", () => renderDetails());
  ["nodeMoved", "nodeRemoved", "connectionRemoved", "addReroute", "removeReroute", "rerouteMoved"].forEach((eventName) => {
    editor.on(eventName, () => syncFlowFromEditor(true));
  });
  editor.on("connectionCreated", () => {
    if (state.renderingFlow) return;
    syncFlowFromEditor(true);
    renderCanvas();
  });
}

function canvasPointFromEvent(event) {
  const rect = els.flowCanvas.getBoundingClientRect();
  const editor = state.editor;
  if (!editor) return { x: event.clientX - rect.left, y: event.clientY - rect.top };
  return {
    x: (event.clientX - rect.left - editor.canvas_x) / editor.zoom,
    y: (event.clientY - rect.top - editor.canvas_y) / editor.zoom
  };
}

function resetEditorView() {
  const editor = state.editor;
  if (!editor) return;
  editor.canvas_x = 0;
  editor.canvas_y = 0;
  editor.zoom = 1;
  editor.zoom_last_value = 1;
  editor.precanvas.style.transform = "";
}

function setEditorView(x, y, zoom) {
  const editor = state.editor;
  if (!editor) return;
  editor.canvas_x = x;
  editor.canvas_y = y;
  editor.zoom = zoom;
  editor.zoom_last_value = zoom;
  editor.precanvas.style.transform = `translate(${x}px, ${y}px) scale(${zoom})`;
}

function fitEditorView() {
  const editor = state.editor;
  if (!editor) return;
  const nodes = Object.values(editor.drawflow.drawflow.Home.data);
  if (nodes.length === 0) {
    resetEditorView();
    return;
  }
  const boxes = nodes.map((node) => ({
    x: node.pos_x,
    y: node.pos_y,
    width: els.flowCanvas.querySelector(`#node-${cssEscape(String(node.id))}`)?.offsetWidth || 216,
    height: els.flowCanvas.querySelector(`#node-${cssEscape(String(node.id))}`)?.offsetHeight || 120
  }));
  const minX = Math.min(...boxes.map((box) => box.x));
  const minY = Math.min(...boxes.map((box) => box.y));
  const maxX = Math.max(...boxes.map((box) => box.x + box.width));
  const maxY = Math.max(...boxes.map((box) => box.y + box.height));
  const padding = 48;
  const width = Math.max(1, maxX - minX);
  const height = Math.max(1, maxY - minY);
  const zoom = clamp(
    Math.min((els.flowCanvas.clientWidth - padding * 2) / width, (els.flowCanvas.clientHeight - padding * 2) / height, 1),
    editor.zoom_min,
    editor.zoom_max
  );
  const x = (els.flowCanvas.clientWidth - width * zoom) / 2 - minX * zoom;
  const y = (els.flowCanvas.clientHeight - height * zoom) / 2 - minY * zoom;
  setEditorView(x, y, zoom);
}

async function loadWorkspace() {
  try {
    const result = await window.agentFirewall.loadWorkspace();
    setWorkspaceData(result);
  } catch (error) {
    console.error(error.stack || error);
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
  renderCanvas({ fit: true });
  renderDetails();
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
    card.addEventListener("dblclick", () => addAssetNode(item, 420, 160 + state.data.flow.nodes.length * 24));
    els.inventoryList.appendChild(card);
  });
}

function addAssetNode(asset, x, y) {
  const baseId = `${asset.type}:${asset.id}`;
  const existing = state.data.flow.nodes.filter((node) => node.id.startsWith(baseId)).length;
  const id = existing ? `${baseId}:${existing + 1}` : baseId;
  addEditorNode({
    id,
    type: asset.type,
    label: asset.label,
    x: Math.max(12, x - 99),
    y: Math.max(12, y - 42),
    meta: asset.meta
  });
  syncFlowFromEditor(true);
  state.selectedNodeId = id;
  renderDetails();
}

function renderCanvas({ fit = false } = {}) {
  const editor = state.editor;
  if (!editor || !state.data) return;
  state.renderingFlow = true;
  editor.clearModuleSelected();
  const idMap = new Map();
  state.data.flow.nodes.forEach((node) => {
    const drawflowId = addEditorNode(node);
    idMap.set(node.id, drawflowId);
  });
  state.data.flow.edges.forEach((edge) => {
    const from = idMap.get(edge.from);
    const to = idMap.get(edge.to);
    if (from && to) editor.addConnection(from, to, "output_1", "input_1");
  });
  state.renderingFlow = false;
  if (fit) fitEditorView();
  selectEditorNode(state.selectedNodeId);
  els.flowStats.textContent = `${state.data.flow.nodes.length} 个节点 / ${state.data.flow.edges.length} 条连线`;
}

function addEditorNode(node) {
  const editor = state.editor;
  if (!editor) return null;
  const before = new Set(Object.keys(editor.drawflow.drawflow.Home.data));
  editor.addNode(
    node.type,
    1,
    1,
    Math.max(12, Number(node.x) || 12),
    Math.max(12, Number(node.y) || 12),
    node.type,
    {
      flowId: node.id,
      type: node.type,
      label: node.label,
      meta: node.meta || {}
    },
    nodeHtml(node)
  );
  return Object.keys(editor.drawflow.drawflow.Home.data).find((id) => !before.has(id)) || null;
}

function selectEditorNode(flowId) {
  els.flowCanvas.querySelectorAll(".drawflow-node.selected").forEach((node) => node.classList.remove("selected"));
  if (!flowId || !state.editor) return;
  const drawflowId = Object.values(state.editor.drawflow.drawflow.Home.data)
    .find((node) => node.data?.flowId === flowId)?.id;
  if (!drawflowId) return;
  const element = els.flowCanvas.querySelector(`#node-${cssEscape(String(drawflowId))}`);
  if (element) element.classList.add("selected");
}

function syncFlowFromEditor(autosave) {
  if (state.renderingFlow || !state.data || !state.editor) return;
  state.data.flow = flowFromEditor();
  if (!state.data.flow.nodes.some((node) => node.id === state.selectedNodeId)) {
    state.selectedNodeId = state.data.flow.nodes[0]?.id || null;
  }
  els.flowStats.textContent = `${state.data.flow.nodes.length} 个节点 / ${state.data.flow.edges.length} 条连线`;
  renderDetails();
  if (autosave) scheduleAutosave();
}

function flowFromEditor() {
  const data = state.editor.export().drawflow.Home.data;
  const entries = Object.values(data);
  const drawflowToFlow = new Map(entries.map((node) => [String(node.id), node.data.flowId]));
  const nodes = entries.map((node) => ({
    id: node.data.flowId,
    type: node.data.type,
    label: node.data.label,
    x: node.pos_x,
    y: node.pos_y,
    meta: node.data.meta || {}
  }));
  const edgeKeys = new Set();
  const edges = [];
  entries.forEach((node) => {
    Object.values(node.outputs || {}).forEach((output) => {
      (output.connections || []).forEach((connection) => {
        const from = drawflowToFlow.get(String(node.id));
        const to = drawflowToFlow.get(String(connection.node));
        const key = `${from}->${to}`;
        if (from && to && from !== to && !edgeKeys.has(key)) {
          edgeKeys.add(key);
          edges.push({ from, to });
        }
      });
    });
  });
  return { nodes, edges, updatedAt: new Date().toISOString() };
}

function nodeHtml(node) {
  return `
    <div class="flow-node-card">
      <span class="pill ${node.type}">${translateType(node.type)}</span>
      <h3>${escapeHtml(node.label)}</h3>
      <code>${escapeHtml(node.meta?.model || node.meta?.path || node.meta?.agent || node.id)}</code>
    </div>
  `;
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
  syncFlowFromEditor(false);
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
