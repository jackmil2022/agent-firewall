const state = {
  workspace: null,
  data: null,
  activeTab: "models",
  inventoryQuery: "",
  selectedNodeId: null,
  editor: null,
  renderingFlow: false,
  activeView: "flow",
  selectedModelKey: "",
  canvasPan: null,
  lastRun: null
};

const els = {
  flowView: document.querySelector("#flowView"),
  modelView: document.querySelector("#modelView"),
  workspacePath: document.querySelector("#workspacePath"),
  inventoryCount: document.querySelector("#inventoryCount"),
  inventorySearch: document.querySelector("#inventorySearch"),
  inventoryList: document.querySelector("#inventoryList"),
  flowCanvas: document.querySelector("#flowCanvas"),
  flowStats: document.querySelector("#flowStats"),
  selectedType: document.querySelector("#selectedType"),
  detailsBody: document.querySelector("#detailsBody"),
  acpSummary: document.querySelector("#acpSummary"),
  chooseWorkspace: document.querySelector("#chooseWorkspace"),
  startFlow: document.querySelector("#startFlow"),
  saveFlow: document.querySelector("#saveFlow"),
  saveConfig: document.querySelector("#saveConfig"),
  reloadConfig: document.querySelector("#reloadConfig"),
  clearFlow: document.querySelector("#clearFlow"),
  linkMode: document.querySelector("#linkMode"),
  zoomOut: document.querySelector("#zoomOut"),
  zoomReset: document.querySelector("#zoomReset"),
  zoomIn: document.querySelector("#zoomIn"),
  runStatus: document.querySelector("#runStatus"),
  runOutput: document.querySelector("#runOutput"),
  resumeFlow: document.querySelector("#resumeFlow"),
  activeAgentSelect: document.querySelector("#activeAgentSelect"),
  agentModelSelect: document.querySelector("#agentModelSelect"),
  agentNameInput: document.querySelector("#agentNameInput"),
  modelCount: document.querySelector("#modelCount"),
  modelList: document.querySelector("#modelList"),
  addModel: document.querySelector("#addModel"),
  deleteModel: document.querySelector("#deleteModel"),
  modelKeyInput: document.querySelector("#modelKeyInput"),
  modelDisplayNameInput: document.querySelector("#modelDisplayNameInput"),
  modelProviderInput: document.querySelector("#modelProviderInput"),
  modelValueInput: document.querySelector("#modelValueInput"),
  modelBaseUrlInput: document.querySelector("#modelBaseUrlInput"),
  modelApiKeyEnvInput: document.querySelector("#modelApiKeyEnvInput"),
  modelEnabledInput: document.querySelector("#modelEnabledInput"),
  modelTemperatureInput: document.querySelector("#modelTemperatureInput"),
  modelMaxTokensInput: document.querySelector("#modelMaxTokensInput"),
  systemPromptInput: document.querySelector("#systemPromptInput"),
  agentCheckpointInput: document.querySelector("#agentCheckpointInput"),
  agentInterruptInput: document.querySelector("#agentInterruptInput"),
  agentResponseFormatInput: document.querySelector("#agentResponseFormatInput"),
  acpEnabledInput: document.querySelector("#acpEnabledInput"),
  acpUnstableInput: document.querySelector("#acpUnstableInput"),
  acpBufferInput: document.querySelector("#acpBufferInput"),
  mcpServersInput: document.querySelector("#mcpServersInput"),
  modelStatus: document.querySelector("#modelStatus")
};

window.addEventListener("DOMContentLoaded", async () => {
  initFlowEditor();
  wireEvents();
  await loadWorkspace();
});

function wireEvents() {
  document.querySelectorAll(".view-toggle").forEach((button) => {
    button.addEventListener("click", () => {
      setActiveView(button.dataset.view, button);
      if (button.dataset.tab) setActiveTab(button.dataset.tab);
    });
  });

  document.querySelectorAll(".tab").forEach((button) => {
    button.addEventListener("click", () => {
      setActiveTab(button.dataset.tab);
    });
  });

  els.chooseWorkspace.addEventListener("click", async () => {
    const result = await window.agentFirewall.chooseWorkspace();
    if (result) setWorkspaceData(result);
  });

  els.saveFlow.addEventListener("click", async () => {
    await saveFlow("manual");
  });

  els.inventorySearch.addEventListener("input", () => {
    state.inventoryQuery = els.inventorySearch.value.trim().toLowerCase();
    renderInventory();
  });

  els.reloadConfig.addEventListener("click", async () => {
    await loadWorkspace();
    els.modelStatus.textContent = "已重新加载。";
  });

  els.saveConfig.addEventListener("click", async () => {
    await saveModelConfig();
  });

  els.activeAgentSelect.addEventListener("change", () => renderModelForm());
  els.addModel.addEventListener("click", () => addModelConfig());
  els.deleteModel.addEventListener("click", () => deleteModelConfig());

  els.startFlow.addEventListener("click", async () => {
    if (!state.workspace || !state.data) return;
    els.startFlow.disabled = true;
    els.runStatus.textContent = "启动中";
    els.runOutput.textContent = "正在保存并运行当前编排...";
    try {
      const result = await window.agentFirewall.startFlow(state.workspace, currentFlow());
      state.lastRun = result.run;
      els.runStatus.textContent = translateStatus(result.status);
      els.runOutput.textContent = formatRunResult(result);
      els.resumeFlow.disabled = !["needs_input", "blocked", "failed"].includes(result.status);
      els.workspacePath.textContent = `${state.workspace} / 编排已保存`;
    } catch (error) {
      els.runStatus.textContent = "错误";
      els.runOutput.textContent = error.message;
    } finally {
      els.startFlow.disabled = false;
    }
  });

  els.resumeFlow.addEventListener("click", async () => {
    if (!state.workspace || !state.lastRun?.run_id) return;
    const correction = window.prompt("输入修正内容或审批 decisions JSON。", "");
    if (correction === null) return;
    els.resumeFlow.disabled = true;
    els.runStatus.textContent = "继续中";
    try {
      const result = await window.agentFirewall.resumeFlow(
        state.workspace,
        state.lastRun.run_id,
        correction
      );
      state.lastRun = result.run;
      els.runStatus.textContent = translateStatus(result.status);
      els.runOutput.textContent = formatRunResult(result);
      els.resumeFlow.disabled = !["needs_input", "blocked", "failed"].includes(result.status);
    } catch (error) {
      els.runStatus.textContent = "错误";
      els.runOutput.textContent = error.message;
    }
  });

  els.clearFlow.addEventListener("click", () => {
    if (!window.confirm("重置画布会清空当前编排并保留开始/结束节点。继续吗？")) return;
    state.data.flow = {
      nodes: [
        { id: "start", type: "start", label: "开始", x: 120, y: 220 },
        { id: "end", type: "end", label: "结束", x: 560, y: 220 }
      ],
      edges: [{ from: "start", to: "end", on: "success" }],
      updatedAt: new Date().toISOString()
    };
    state.selectedNodeId = "start";
    renderCanvas({ fit: true });
    renderDetails();
    scheduleAutosave();
  });

  els.linkMode.addEventListener("click", () => {
    fitEditorView();
  });

  els.zoomOut.addEventListener("click", () => state.editor?.zoom_out());
  els.zoomReset.addEventListener("click", () => setEditorView(0, 0, 1));
  els.zoomIn.addEventListener("click", () => state.editor?.zoom_in());

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

function setActiveTab(tabName) {
  state.activeTab = tabName;
  document.querySelectorAll(".tab").forEach((tab) => {
    tab.classList.toggle("active", tab.dataset.tab === tabName);
  });
  renderInventory();
}

function setActiveView(view, activeButton = null) {
  state.activeView = view;
  els.flowView.classList.toggle("hidden", view !== "flow");
  els.modelView.classList.toggle("hidden", view !== "model");
  const target = activeButton || document.querySelector(`.view-toggle[data-view="${view}"]`);
  document.querySelectorAll(".view-toggle").forEach((button) => {
    button.classList.toggle("active", button === target);
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
  wireCanvasPan();
}

function wireCanvasPan() {
  els.flowCanvas.addEventListener("mousedown", (event) => {
    if (event.button !== 0 || isCanvasControlTarget(event.target)) return;
    const editor = state.editor;
    if (!editor) return;
    state.canvasPan = {
      x: event.clientX,
      y: event.clientY,
      canvasX: editor.canvas_x,
      canvasY: editor.canvas_y
    };
    editor.editor_selected = false;
    els.flowCanvas.classList.add("panning");
    event.preventDefault();
  });
  window.addEventListener("mousemove", (event) => {
    if (!state.canvasPan || !state.editor) return;
    const dx = event.clientX - state.canvasPan.x;
    const dy = event.clientY - state.canvasPan.y;
    setEditorView(state.canvasPan.canvasX + dx, state.canvasPan.canvasY + dy, state.editor.zoom);
  });
  window.addEventListener("mouseup", () => {
    if (!state.canvasPan) return;
    state.canvasPan = null;
    els.flowCanvas.classList.remove("panning");
  });
}

function isCanvasControlTarget(target) {
  return Boolean(target.closest(".drawflow-node, .input, .output, .main-path, .point, .drawflow-delete, .canvas-actionbar"));
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
  renderModelForm();
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
  if (state.activeTab === "models") {
    const config = state.data.config || {};
    ensureModels(config);
    return Object.entries(config.models || {}).map(([key, model]) => ({
      id: key,
      type: "model",
      label: model.display_name || key,
      subtitle: model.model || "",
      description: `${model.provider || "custom"} / ${model.enabled === false ? "禁用" : "启用"}`,
      meta: { key, ...model },
      draggable: false
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
  const items = filterInventoryItems(inventoryItems());
  els.inventoryCount.textContent = String(items.length);
  els.inventoryList.innerHTML = "";
  if (items.length === 0) {
    els.inventoryList.innerHTML = '<div class="asset-card"><p>当前没有配置项目。</p></div>';
    return;
  }
  items.forEach((item) => {
    const card = document.createElement("article");
    card.className = `asset-card${item.draggable === false ? " static" : ""}`;
    card.draggable = item.draggable !== false;
    card.innerHTML = `
      <div class="asset-top">
        <h2>${escapeHtml(item.label)}</h2>
        <span class="pill ${item.type}">${translateType(item.type)}</span>
      </div>
      <p>${escapeHtml(item.subtitle || item.description || "")}</p>
    `;
    if (item.draggable !== false) {
      card.addEventListener("dragstart", (event) => {
        event.dataTransfer.setData("application/json", JSON.stringify(item));
      });
      card.addEventListener("dblclick", () => addAssetNode(item, 420, 160 + state.data.flow.nodes.length * 24));
    }
    els.inventoryList.appendChild(card);
  });
}

function filterInventoryItems(items) {
  if (!state.inventoryQuery) return items;
  return items.filter((item) =>
    [item.label, item.subtitle, item.description, item.id]
      .filter(Boolean)
      .some((value) => String(value).toLowerCase().includes(state.inventoryQuery))
  );
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
  const ports = nodePorts(node.type);
  editor.addNode(
    node.type,
    ports.inputs,
    ports.outputs,
    Math.max(12, Number(node.x) || 12),
    Math.max(12, Number(node.y) || 12),
    node.type,
    {
      flowId: node.id,
      type: node.type,
      label: node.label,
      ref: node.ref,
      params: node.params || {},
      meta: node.meta || {}
    },
    nodeHtml(node)
  );
  return Object.keys(editor.drawflow.drawflow.Home.data).find((id) => !before.has(id)) || null;
}

function nodePorts(type) {
  if (type === "start") return { inputs: 0, outputs: 1 };
  if (type === "end") return { inputs: 1, outputs: 0 };
  return { inputs: 1, outputs: 1 };
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
    ref: node.data.ref,
    x: node.pos_x,
    y: node.pos_y,
    params: node.data.params || {},
    meta: node.data.meta || {}
  }));
  const edgeKeys = new Set();
  const existingEdges = new Map(
    (state.data.flow.edges || []).map((edge) => [`${edge.from}->${edge.to}`, edge])
  );
  const edges = [];
  entries.forEach((node) => {
    Object.values(node.outputs || {}).forEach((output) => {
      (output.connections || []).forEach((connection) => {
        const from = drawflowToFlow.get(String(node.id));
        const to = drawflowToFlow.get(String(connection.node));
        const key = `${from}->${to}`;
        if (from && to && from !== to && !edgeKeys.has(key)) {
          edgeKeys.add(key);
          const existing = existingEdges.get(key) || {};
          edges.push({
            from,
            to,
            on: existing.on || "success",
            pass: Array.isArray(existing.pass) ? existing.pass : []
          });
        }
      });
    });
  });
  return {
    nodes,
    edges,
    limits: state.data.flow.limits || { max_steps: 20, max_loop_iterations: 3 },
    updatedAt: new Date().toISOString()
  };
}

function nodeHtml(node) {
  if (node.type === "start" || node.type === "end") {
    return `
      <div class="flow-node-card boundary-node-card">
        <span class="pill ${node.type}">${translateType(node.type)}</span>
        <h3>${escapeHtml(node.label)}</h3>
      </div>
    `;
  }
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
  const outgoing = state.data.flow.edges.filter((edge) => edge.from === node.id);
  els.detailsBody.innerHTML = `
    <h2>${escapeHtml(node.label)}</h2>
    <p>${escapeHtml(node.id)}</p>
    <div class="kv">
      <div><span>位置</span><code>${Math.round(node.x)}, ${Math.round(node.y)}</code></div>
      <div><span>出站连线</span><code>${state.data.flow.edges.filter((edge) => edge.from === node.id).length}</code></div>
      <div><span>入站连线</span><code>${state.data.flow.edges.filter((edge) => edge.to === node.id).length}</code></div>
    </div>
    ${nodePolicyHtml(node)}
    ${outgoingEdgesHtml(outgoing)}
    <pre>${escapeHtml(JSON.stringify(node.meta || {}, null, 2))}</pre>
  `;
  wireNodePolicy(node);
  wireOutgoingEdges(outgoing);
}

function nodePolicyHtml(node) {
  if (node.type === "start" || node.type === "end") return "";
  const params = node.params || {};
  const retry = params.retry || {};
  const validation = JSON.stringify(params.validate || {}, null, 2);
  const typeFields = [];
  if (node.type === "skill") {
    typeFields.push(`
      <label>脚本<input id="nodeScript" type="text" value="${escapeHtml(params.script || "")}" /></label>
    `);
  }
  if (node.type === "mcp") {
    typeFields.push(`
      <label>工具<input id="nodeTool" type="text" value="${escapeHtml(params.tool || "")}" /></label>
      <label>参数 JSON<textarea id="nodeArgs" rows="5">${escapeHtml(JSON.stringify(params.args || {}, null, 2))}</textarea></label>
      <label>幂等参数<input id="nodeIdempotencyArg" type="text" value="${escapeHtml(params.idempotency_arg || "")}" /></label>
    `);
  }
  if (node.type === "agent") {
    typeFields.push(`
      <label class="detail-check"><input id="nodeRequiresApproval" type="checkbox" ${params.requires_approval ? "checked" : ""} />运行前审批</label>
    `);
  }
  return `
    <div class="node-policy">
      <label>超时秒数<input id="nodeTimeout" type="number" min="1" value="${Number(params.timeout_seconds) || 60}" /></label>
      <label>最大尝试<input id="nodeAttempts" type="number" min="1" value="${Number(retry.max_attempts) || 1}" /></label>
      <label>重试间隔<input id="nodeRetryDelay" type="number" min="0" step="0.1" value="${Number(retry.delay_seconds) || 0}" /></label>
      <label class="detail-check"><input id="nodeIdempotent" type="checkbox" ${params.idempotent ? "checked" : ""} />节点可幂等重试</label>
      ${typeFields.join("")}
      <label>结果校验 JSON<textarea id="nodeValidation" rows="6">${escapeHtml(validation)}</textarea></label>
      <button id="applyNodePolicy" type="button">应用节点策略</button>
    </div>
  `;
}

function outgoingEdgesHtml(edges) {
  if (!edges.length) return "";
  return `
    <div class="edge-policies">
      ${edges.map((edge, index) => `
        <div class="edge-policy">
          <code>${escapeHtml(edge.to)}</code>
          <select data-edge-status="${index}">
            ${["success", "failed", "needs_input", "blocked", "always"]
              .map((status) => `<option value="${status}" ${edge.on === status ? "selected" : ""}>${translateStatus(status)}</option>`)
              .join("")}
          </select>
          <input data-edge-pass="${index}" type="text" value="${escapeHtml((edge.pass || []).join(", "))}" placeholder="传递字段" />
        </div>
      `).join("")}
    </div>
  `;
}

function wireNodePolicy(node) {
  const button = document.querySelector("#applyNodePolicy");
  if (!button) return;
  button.addEventListener("click", () => {
    let validation;
    let args;
    try {
      validation = JSON.parse(document.querySelector("#nodeValidation")?.value || "{}");
      args = JSON.parse(document.querySelector("#nodeArgs")?.value || "{}");
    } catch (error) {
      els.runStatus.textContent = "配置错误";
      els.runOutput.textContent = error.message;
      return;
    }
    node.params = {
      ...(node.params || {}),
      timeout_seconds: Number(document.querySelector("#nodeTimeout")?.value) || 60,
      retry: {
        max_attempts: Number(document.querySelector("#nodeAttempts")?.value) || 1,
        delay_seconds: Number(document.querySelector("#nodeRetryDelay")?.value) || 0
      },
      idempotent: Boolean(document.querySelector("#nodeIdempotent")?.checked),
      validate: validation
    };
    if (node.type === "skill") node.params.script = document.querySelector("#nodeScript")?.value.trim() || "";
    if (node.type === "mcp") {
      node.params.tool = document.querySelector("#nodeTool")?.value.trim() || "";
      node.params.args = args;
      node.params.idempotency_arg = document.querySelector("#nodeIdempotencyArg")?.value.trim() || "";
    }
    if (node.type === "agent") {
      node.params.requires_approval = Boolean(document.querySelector("#nodeRequiresApproval")?.checked);
    }
    updateEditorNodeData(node);
    scheduleAutosave();
    renderDetails();
  });
}

function wireOutgoingEdges(edges) {
  edges.forEach((edge, index) => {
    document.querySelector(`[data-edge-status="${index}"]`)?.addEventListener("change", (event) => {
      edge.on = event.target.value;
      scheduleAutosave();
    });
    document.querySelector(`[data-edge-pass="${index}"]`)?.addEventListener("change", (event) => {
      edge.pass = event.target.value.split(",").map((value) => value.trim()).filter(Boolean);
      scheduleAutosave();
    });
  });
}

function updateEditorNodeData(node) {
  if (!state.editor) return;
  const drawflowNode = Object.values(state.editor.drawflow.drawflow.Home.data)
    .find((item) => item.data?.flowId === node.id);
  if (!drawflowNode) return;
  drawflowNode.data.params = node.params || {};
}

function currentFlow() {
  syncFlowFromEditor(false);
  return {
    nodes: state.data.flow.nodes,
    edges: state.data.flow.edges,
    limits: state.data.flow.limits,
    updatedAt: new Date().toISOString()
  };
}

async function saveFlow(reason) {
  if (!state.workspace || !state.data) return null;
  const result = await window.agentFirewall.saveFlow(state.workspace, currentFlow());
  els.workspacePath.textContent = `${state.workspace} / ${reason === "manual" ? "手动保存" : "已自动保存"}`;
  return result;
}

function renderModelForm() {
  if (!state.data?.config) return;
  const config = state.data.config;
  ensureModels(config);
  const modelKeys = Object.keys(config.models || {});
  if (!modelKeys.includes(state.selectedModelKey)) {
    state.selectedModelKey = modelKeys[0] || "";
  }
  renderModelList(config);
  const model = config.models?.[state.selectedModelKey] || {};
  const params = model.params || {};
  els.modelKeyInput.value = state.selectedModelKey || "";
  els.modelDisplayNameInput.value = model.display_name || "";
  els.modelProviderInput.value = model.provider || "";
  els.modelValueInput.value = model.model || "";
  els.modelBaseUrlInput.value = model.base_url || "";
  els.modelApiKeyEnvInput.value = model.api_key_env || "";
  els.modelEnabledInput.checked = Boolean(model.enabled ?? true);
  els.modelTemperatureInput.value = params.temperature ?? "";
  els.modelMaxTokensInput.value = params.max_tokens ?? "";

  const agentKeys = Object.keys(config.agents || {});
  const activeKey = els.activeAgentSelect.value || config.active_agent || agentKeys[0] || "";
  els.activeAgentSelect.innerHTML = agentKeys
    .map((key) => `<option value="${escapeHtml(key)}">${escapeHtml(key)}</option>`)
    .join("");
  els.activeAgentSelect.value = agentKeys.includes(activeKey) ? activeKey : agentKeys[0] || "";

  const agent = config.agents?.[els.activeAgentSelect.value] || {};
  els.agentNameInput.value = agent.name || "";
  els.agentModelSelect.innerHTML = modelKeys
    .map((key) => `<option value="${escapeHtml(key)}">${escapeHtml(key)}</option>`)
    .join("");
  els.agentModelSelect.value = modelKeys.includes(agent.model) ? agent.model : modelKeys[0] || "";
  els.systemPromptInput.value = agent.system_prompt || "";
  els.agentCheckpointInput.checked = Boolean(agent.checkpoint ?? true);
  els.agentInterruptInput.value = JSON.stringify(agent.interrupt_on || {}, null, 2);
  els.agentResponseFormatInput.value = agent.response_format
    ? JSON.stringify(agent.response_format, null, 2)
    : "";
  els.mcpServersInput.value = JSON.stringify(agent.mcp_servers || {}, null, 2);
  els.acpEnabledInput.checked = Boolean(config.acp?.enabled ?? true);
  els.acpUnstableInput.checked = Boolean(config.acp?.use_unstable_protocol);
  els.acpBufferInput.value = String(config.acp?.stdio_buffer_limit_bytes || 52428800);
}

function renderModelList(config) {
  const keys = Object.keys(config.models || {});
  els.modelCount.textContent = String(keys.length);
  els.modelList.innerHTML = "";
  keys.forEach((key) => {
    const model = config.models[key] || {};
    const usedBy = agentsUsingModel(config, key);
    const button = document.createElement("button");
    button.type = "button";
    button.className = `model-list-item${key === state.selectedModelKey ? " active" : ""}`;
    button.innerHTML = `
      <strong>${escapeHtml(model.display_name || key)}</strong>
      <span>${escapeHtml(key)}</span>
      <span>${escapeHtml(model.provider || "-")} / ${escapeHtml(model.model || "-")}</span>
      <div class="model-list-meta">
        <span class="model-badge ${model.enabled === false ? "" : "enabled"}">${model.enabled === false ? "禁用" : "启用"}</span>
        <span class="model-badge">${escapeHtml(usedBy.length ? usedBy.join(", ") : "未绑定")}</span>
      </div>
    `;
    button.addEventListener("click", () => {
      state.selectedModelKey = key;
      renderModelForm();
    });
    els.modelList.appendChild(button);
  });
}

async function saveModelConfig() {
  if (!state.workspace || !state.data?.config) return;
  const config = structuredClone(state.data.config);
  ensureModels(config);
  const agentKey = els.activeAgentSelect.value;
  if (!agentKey || !config.agents?.[agentKey]) return;

  const oldModelKey = state.selectedModelKey;
  const newModelKey = els.modelKeyInput.value.trim();
  if (!newModelKey) {
    els.modelStatus.textContent = "模型名字不能为空。";
    return;
  }
  if (oldModelKey !== newModelKey && config.models[newModelKey]) {
    els.modelStatus.textContent = "模型名字已存在。";
    return;
  }
  if (!els.modelProviderInput.value.trim()) {
    els.modelStatus.textContent = "Provider 不能为空。";
    return;
  }
  if (!els.modelValueInput.value.trim()) {
    els.modelStatus.textContent = "模型 ID 不能为空。";
    return;
  }

  let mcpServers;
  let interruptOn;
  let responseFormat;
  try {
    mcpServers = JSON.parse(els.mcpServersInput.value || "{}");
    interruptOn = JSON.parse(els.agentInterruptInput.value || "{}");
    responseFormat = els.agentResponseFormatInput.value.trim()
      ? JSON.parse(els.agentResponseFormatInput.value)
      : null;
  } catch (error) {
    els.modelStatus.textContent = `JSON 无效: ${error.message}`;
    return;
  }

  if (oldModelKey && oldModelKey !== newModelKey) {
    config.models[newModelKey] = config.models[oldModelKey] || {};
    delete config.models[oldModelKey];
    Object.values(config.agents || {}).forEach((agent) => {
      if (agent.model === oldModelKey) agent.model = newModelKey;
    });
  }
  config.models[newModelKey] = {
    ...(config.models[newModelKey] || {}),
    display_name: els.modelDisplayNameInput.value.trim(),
    provider: els.modelProviderInput.value.trim(),
    model: els.modelValueInput.value.trim(),
    base_url: els.modelBaseUrlInput.value.trim(),
    api_key_env: els.modelApiKeyEnvInput.value.trim(),
    enabled: els.modelEnabledInput.checked,
    params: compactModelParams()
  };

  config.active_agent = agentKey;
  const selectedAgentModel = els.agentModelSelect.value === oldModelKey ? newModelKey : els.agentModelSelect.value;
  config.agents[agentKey] = {
    ...config.agents[agentKey],
    name: els.agentNameInput.value.trim() || agentKey,
    model: selectedAgentModel || newModelKey,
    system_prompt: els.systemPromptInput.value,
    mcp_servers: mcpServers,
    interrupt_on: interruptOn,
    response_format: responseFormat,
    checkpoint: els.agentCheckpointInput.checked
  };
  config.acp = {
    ...(config.acp || {}),
    enabled: els.acpEnabledInput.checked,
    use_unstable_protocol: els.acpUnstableInput.checked,
    stdio_buffer_limit_bytes: Number(els.acpBufferInput.value) || 52428800
  };

  els.saveConfig.disabled = true;
  els.modelStatus.textContent = "正在保存...";
  try {
    const result = await window.agentFirewall.saveConfig(state.workspace, config);
    const reloaded = await window.agentFirewall.loadWorkspace(state.workspace);
    state.selectedModelKey = newModelKey;
    setWorkspaceData(reloaded);
    setActiveView("model");
    els.modelStatus.textContent = `已保存到 ${result.database}`;
  } catch (error) {
    els.modelStatus.textContent = error.message;
  } finally {
    els.saveConfig.disabled = false;
  }
}

function ensureModels(config) {
  config.models = config.models && typeof config.models === "object" ? config.models : {};
  Object.values(config.agents || {}).forEach((agent) => {
    const model = agent.model || "fake:echo";
    if (!config.models[model]) {
      config.models[model] = {
        display_name: model,
        provider: model.includes(":") ? model.split(":", 1)[0] : "",
        model,
        base_url: "",
        api_key_env: "",
        enabled: true,
        params: {}
      };
    }
  });
}

function agentsUsingModel(config, modelKey) {
  return Object.entries(config.agents || {})
    .filter(([, agent]) => agent.model === modelKey)
    .map(([key]) => key);
}

function compactModelParams() {
  const params = {};
  const temperature = els.modelTemperatureInput.value;
  const maxTokens = els.modelMaxTokensInput.value;
  if (temperature !== "") params.temperature = Number(temperature);
  if (maxTokens !== "") params.max_tokens = Number(maxTokens);
  return params;
}

function addModelConfig() {
  if (!state.data?.config) return;
  const config = state.data.config;
  ensureModels(config);
  let index = Object.keys(config.models).length + 1;
  let key = `model-${index}`;
  while (config.models[key]) {
    index += 1;
    key = `model-${index}`;
  }
  config.models[key] = {
    display_name: "",
    provider: "openai",
    model: "openai:gpt-5",
    base_url: "",
    api_key_env: "OPENAI_API_KEY",
    enabled: true,
    params: { temperature: 0.2, max_tokens: 4096 }
  };
  state.selectedModelKey = key;
  renderModelForm();
}

function deleteModelConfig() {
  if (!state.data?.config) return;
  const config = state.data.config;
  ensureModels(config);
  const key = state.selectedModelKey;
  const modelKeys = Object.keys(config.models);
  if (!key || modelKeys.length <= 1) {
    els.modelStatus.textContent = "至少保留一个模型配置。";
    return;
  }
  const usedBy = agentsUsingModel(config, key);
  if (usedBy.length) {
    els.modelStatus.textContent = `模型正在被使用，先切换这些智能体: ${usedBy.join(", ")}`;
    return;
  }
  delete config.models[key];
  state.selectedModelKey = Object.keys(config.models)[0] || "";
  renderModelForm();
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
  if (result.run) {
    const events = (result.run.events || [])
      .filter((event) => ["node_started", "node_finished", "node_retrying", "run_paused", "run_resumed"].includes(event.event_type))
      .map((event) => formatRunEvent(event));
    return [
      `运行: ${result.run.run_id}`,
      `状态: ${translateStatus(result.run.status)}`,
      "",
      ...events,
      "",
      result.run.summary || ""
    ].join("\n");
  }
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

function formatRunEvent(event) {
  const node = event.node_id ? ` ${event.node_id}` : "";
  if (event.event_type === "node_finished") {
    return `[${translateStatus(event.payload.status)}]${node} ${event.payload.summary || ""}`;
  }
  if (event.event_type === "node_retrying") {
    return `[重试]${node} ${event.payload.attempt}/${event.payload.max_attempts}`;
  }
  if (event.event_type === "run_paused") return `[暂停]${node} ${event.payload.summary || ""}`;
  if (event.event_type === "run_resumed") return `[继续]${node}`;
  return `[开始]${node}`;
}

function translateStatus(status) {
  const map = {
    idle: "空闲",
    starting: "启动中",
    started: "已启动",
    success: "成功",
    failed: "失败",
    needs_input: "等待输入",
    blocked: "已阻塞",
    always: "始终",
    error: "错误",
    timeout: "超时"
  };
  return map[status] || status || "未知";
}

function translateType(type) {
  const map = {
    agent: "智能体",
    start: "开始",
    end: "结束",
    skill: "技能",
    model: "模型",
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
