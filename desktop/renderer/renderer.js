const state = {
  workspace: null,
  data: null,
  activeTab: "models",
  inventoryQuery: "",
  selectedNodeId: null,
  editor: null,
  renderingFlow: false,
  activeView: "workbench",
  selectedModelKey: "",
  canvasPan: null,
  lastRun: null,
  layoutAdjusted: false,
  selectedTestCaseId: null,
  selectedRevisionId: null,
  pendingRevisionId: null,
  lastTestResult: null,
  activeTestOperationId: null,
  activeFlowOperationId: null,
  testStartedAt: null,
  testPollTimer: null,
  testPollBusy: false,
  flowPollTimer: null,
  flowPollBusy: false,
  runStatusFilter: "",
  capabilityQuery: "",
  capabilityKind: "",
  mcpDiscoveryStatus: {}
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
  modelApiKeyInput: document.querySelector("#modelApiKeyInput"),
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
  allowedMcpToolsInput: document.querySelector("#allowedMcpToolsInput"),
  modelStatus: document.querySelector("#modelStatus")
  ,workbenchView: document.querySelector("#workbenchView")
  ,capabilityView: document.querySelector("#capabilityView")
  ,runsView: document.querySelector("#runsView")
  ,policyView: document.querySelector("#policyView")
  ,settingsView: document.querySelector("#settingsView")
  ,advancedFlowView: document.querySelector("#advancedFlowView")
  ,testCaseList: document.querySelector("#testCaseList")
  ,testNameInput: document.querySelector("#testNameInput")
  ,testTargetSelect: document.querySelector("#testTargetSelect")
  ,testGoalInput: document.querySelector("#testGoalInput")
  ,testInputJson: document.querySelector("#testInputJson")
  ,testAssertionsJson: document.querySelector("#testAssertionsJson")
  ,saveTestCase: document.querySelector("#saveTestCase")
  ,newTestCase: document.querySelector("#newTestCase")
  ,runTestCase: document.querySelector("#runTestCase")
  ,rerunTestCase: document.querySelector("#rerunTestCase")
  ,traceList: document.querySelector("#traceList")
  ,diagnosisPanel: document.querySelector("#diagnosisPanel")
  ,evidenceSection: document.querySelector(".evidence-section")
  ,capabilityList: document.querySelector("#capabilityList")
  ,capabilitySearch: document.querySelector("#capabilitySearch")
  ,configureCapability: document.querySelector("#configureCapability")
  ,runHistoryList: document.querySelector("#runHistoryList")
  ,runStatusFilter: document.querySelector("#runStatusFilter")
  ,refreshRuns: document.querySelector("#refreshRuns")
  ,policyWorkspace: document.querySelector("#policyWorkspace")
  ,savePolicy: document.querySelector("#savePolicy")
  ,runPolicyCheck: document.querySelector("#runPolicyCheck")
  ,policyAgentApproval: document.querySelector("#policyAgentApproval")
  ,policyScriptApproval: document.querySelector("#policyScriptApproval")
  ,policyMcpApproval: document.querySelector("#policyMcpApproval")
  ,policyAllowNetwork: document.querySelector("#policyAllowNetwork")
  ,policyNetworkHosts: document.querySelector("#policyNetworkHosts")
  ,policyCommands: document.querySelector("#policyCommands")
  ,policyExposedEnv: document.querySelector("#policyExposedEnv")
  ,approveOperation: document.querySelector("#approveOperation")
  ,setBaseline: document.querySelector("#setBaseline")
  ,baselineStatus: document.querySelector("#baselineStatus")
  ,baselineRunId: document.querySelector("#baselineRunId")
  ,cancelTestRun: document.querySelector("#cancelTestRun")
  ,workbenchStatusDot: document.querySelector("#workbenchStatusDot")
  ,workbenchStatusText: document.querySelector("#workbenchStatusText")
  ,traceStatus: document.querySelector("#traceStatus")
  ,traceEventCount: document.querySelector("#traceEventCount")
  ,traceDuration: document.querySelector("#traceDuration")
  ,revisionSelect: document.querySelector("#revisionSelect")
  ,revisionState: document.querySelector("#revisionState")
  ,revisionDiff: document.querySelector("#revisionDiff")
  ,revisionTarget: document.querySelector("#revisionTarget")
  ,revisionReason: document.querySelector("#revisionReason")
  ,revisionAfterJson: document.querySelector("#revisionAfterJson")
  ,createRevision: document.querySelector("#createRevision")
  ,applyRevision: document.querySelector("#applyRevision")
  ,revertRevision: document.querySelector("#revertRevision")
  ,runRevisionCandidate: document.querySelector("#runRevisionCandidate")
  ,reviewRevision: document.querySelector("#reviewRevision")
  ,cancelFlow: document.querySelector("#cancelFlow")
};

window.addEventListener("DOMContentLoaded", async () => {
  initFlowEditor();
  wireEvents();
  await loadWorkspace();
});

window.addEventListener("unhandledrejection", (event) => {
  event.preventDefault();
  showActionError(event.reason);
});

function showActionError(error) {
  const message = error instanceof Error ? error.message : String(error || "未知错误");
  els.workspacePath.textContent = `操作失败：${message}`;
  if (state.activeView === "workbench") setWorkbenchError(message);
  if (state.activeView === "advanced") {
    els.runStatus.textContent = "错误";
    els.runOutput.textContent = message;
  }
  if (state.activeView === "settings") els.modelStatus.textContent = `操作失败：${message}`;
  if (state.activeView === "policy") {
    const status = document.querySelector("#policyStatus strong");
    const detail = document.querySelector("#policyStatus small");
    if (status) status.textContent = "操作失败";
    if (detail) detail.textContent = message;
  }
}

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
  els.saveTestCase?.addEventListener("click", () => saveWorkbenchCase());
  els.newTestCase?.addEventListener("click", () => newWorkbenchCase());
  els.runTestCase?.addEventListener("click", () => executeWorkbenchCase());
  els.rerunTestCase?.addEventListener("click", () => executeWorkbenchCase());
  els.testTargetSelect?.addEventListener("change", () => applyTargetDefaults());
  els.savePolicy?.addEventListener("click", () => savePolicyConfig());
  els.runPolicyCheck?.addEventListener("click", () => runPolicyCheck());
  els.approveOperation?.addEventListener("click", () => executeWorkbenchCase(true, state.pendingRevisionId));
  els.setBaseline?.addEventListener("click", () => setCurrentRunAsBaseline());
  els.cancelTestRun?.addEventListener("click", () => cancelActiveTestRun());
  els.runStatusFilter?.addEventListener("change", () => {
    state.runStatusFilter = els.runStatusFilter.value;
    renderRunHistory(state.data?.runs || []);
  });
  els.refreshRuns?.addEventListener("click", async () => {
    try {
      await refreshWorkspaceData();
    } catch (error) {
      els.workspacePath.textContent = error.message;
    }
  });
  els.capabilitySearch?.addEventListener("input", () => {
    state.capabilityQuery = els.capabilitySearch.value.trim().toLowerCase();
    renderCapabilityList(state.data?.capabilities || []);
  });
  document.querySelectorAll("[data-capability-kind]").forEach((button) => {
    button.addEventListener("click", () => {
      state.capabilityKind = button.dataset.capabilityKind;
      document.querySelectorAll("[data-capability-kind]").forEach((item) => item.classList.toggle("active", item === button));
      renderCapabilityList(state.data?.capabilities || []);
    });
  });
  els.configureCapability?.addEventListener("click", () => setActiveView("settings"));
  els.revisionSelect?.addEventListener("change", () => selectRevision(Number(els.revisionSelect.value) || null));
  els.createRevision?.addEventListener("click", () => createWorkbenchRevision());
  els.runRevisionCandidate?.addEventListener("click", () => executeWorkbenchCase(false, state.selectedRevisionId));
  els.reviewRevision?.addEventListener("click", () => reviewSelectedRevision());
  els.applyRevision?.addEventListener("click", () => applySelectedRevision());
  els.revertRevision?.addEventListener("click", () => revertSelectedRevision());
  els.cancelFlow?.addEventListener("click", () => cancelActiveFlowRun());

  els.startFlow.addEventListener("click", async () => {
    if (!state.workspace || !state.data) return;
    const operationId = crypto.randomUUID();
    state.activeFlowOperationId = operationId;
    startFlowRunPolling(operationId);
    els.startFlow.disabled = true;
    els.cancelFlow.disabled = false;
    els.runStatus.textContent = "运行中";
    els.runOutput.textContent = "本地后端进程运行中，正在从 SQLite 增量载入事件。";
    try {
      const result = await window.agentFirewall.startFlow(state.workspace, currentFlow(), operationId);
      state.lastRun = result.run;
      els.runStatus.textContent = translateStatus(result.status);
      els.runOutput.textContent = formatRunResult(result);
      els.resumeFlow.disabled = !["needs_input", "blocked", "failed"].includes(result.status);
      els.workspacePath.textContent = `${state.workspace} / 编排已保存`;
    } catch (error) {
      els.runStatus.textContent = "错误";
      els.runOutput.textContent = error.message;
    } finally {
      stopFlowRunPolling();
      if (state.activeFlowOperationId === operationId) state.activeFlowOperationId = null;
      els.startFlow.disabled = false;
      els.cancelFlow.disabled = true;
    }
  });

  els.resumeFlow.addEventListener("click", async () => {
    if (!state.workspace || !state.lastRun?.run_id) return;
    const correction = window.prompt("输入修正内容或审批 decisions JSON。", "");
    if (correction === null) return;
    const operationId = state.lastRun.run_id;
    state.activeFlowOperationId = operationId;
    startFlowRunPolling(operationId);
    els.resumeFlow.disabled = true;
    els.cancelFlow.disabled = false;
    els.runStatus.textContent = "恢复中";
    try {
      const result = await window.agentFirewall.resumeFlow(
        state.workspace,
        state.lastRun.run_id,
        correction,
        operationId
      );
      state.lastRun = result.run;
      els.runStatus.textContent = translateStatus(result.status);
      els.runOutput.textContent = formatRunResult(result);
      els.resumeFlow.disabled = !["needs_input", "blocked", "failed"].includes(result.status);
    } catch (error) {
      els.runStatus.textContent = "错误";
      els.runOutput.textContent = error.message;
    } finally {
      stopFlowRunPolling();
      if (state.activeFlowOperationId === operationId) state.activeFlowOperationId = null;
      els.cancelFlow.disabled = true;
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
  const views = {
    workbench: els.workbenchView,
    capability: els.capabilityView,
    runs: els.runsView,
    policy: els.policyView,
    settings: els.settingsView,
    advanced: els.advancedFlowView
  };
  Object.entries(views).forEach(([key, element]) => {
    element?.classList.toggle("hidden", key !== view);
    element?.classList.toggle("active-view", key === view);
  });
  if (view === "advanced") setTimeout(() => fitEditorView(), 0);
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
  renderWorkbench();
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
    return (state.data.capabilities || []).filter((item) => item.kind === "script_action").map((skill) => ({
      id: skill.id,
      type: "skill",
      label: skill.name,
      subtitle: skill.script,
      description: "Skill 中明确选择的可执行脚本",
      ref: skill.ref,
      params: { script: skill.script },
      meta: skill
    }));
  }
  return (state.data.capabilities || []).filter((item) => item.kind === "mcp_tool").map((tool) => ({
    id: tool.id,
    type: "mcp",
    label: tool.name,
    subtitle: tool.ref,
    description: tool.description,
    ref: tool.ref,
    params: { server: tool.ref, tool: tool.name, args: {} },
    meta: tool
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
  const position = findFreeNodePosition(x - 99, y - 42);
  addEditorNode({
    id,
    type: asset.type,
    label: asset.label,
    x: position.x,
    y: position.y,
    ref: asset.ref || asset.id,
    params: asset.params || {},
    meta: asset.meta
  });
  syncFlowFromEditor(true);
  state.selectedNodeId = id;
  renderDetails();
}

function findFreeNodePosition(x, y, ignoredDrawflowId = null) {
  const width = 216;
  const height = 120;
  const gap = 28;
  const start = { x: Math.max(12, x), y: Math.max(12, y) };
  const boxes = Object.values(state.editor?.drawflow.drawflow.Home.data || {})
    .filter((node) => String(node.id) !== String(ignoredDrawflowId))
    .map((node) => {
      const element = els.flowCanvas.querySelector(`#node-${cssEscape(String(node.id))}`);
      return {
        x: node.pos_x,
        y: node.pos_y,
        width: element?.offsetWidth || width,
        height: element?.offsetHeight || height
      };
    });
  for (let row = 0; row < boxes.length + 2; row += 1) {
    for (let column = 0; column < boxes.length + 2; column += 1) {
      const candidate = { x: start.x + column * (width + gap), y: start.y + row * (height + gap) };
      if (!boxes.some((box) => boxesOverlap(candidate, { width, height }, box, gap))) return candidate;
    }
  }
  return start;
}

function boxesOverlap(position, size, box, gap) {
  return position.x < box.x + box.width + gap &&
    position.x + size.width + gap > box.x &&
    position.y < box.y + box.height + gap &&
    position.y + size.height + gap > box.y;
}

function renderCanvas({ fit = false } = {}) {
  const editor = state.editor;
  if (!editor || !state.data) return;
  state.renderingFlow = true;
  state.layoutAdjusted = false;
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
  if (state.layoutAdjusted) syncFlowFromEditor(true);
  if (fit) fitEditorView();
  selectEditorNode(state.selectedNodeId);
  els.flowStats.textContent = `${state.data.flow.nodes.length} 个节点 / ${state.data.flow.edges.length} 条连线`;
}

function addEditorNode(node) {
  const editor = state.editor;
  if (!editor) return null;
  const before = new Set(Object.keys(editor.drawflow.drawflow.Home.data));
  const ports = nodePorts(node.type);
  const requested = { x: Math.max(12, Number(node.x) || 12), y: Math.max(12, Number(node.y) || 12) };
  const position = findFreeNodePosition(requested.x, requested.y);
  if (position.x !== requested.x || position.y !== requested.y) state.layoutAdjusted = true;
  editor.addNode(
    node.type,
    ports.inputs,
    ports.outputs,
    position.x,
    position.y,
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
  els.modelApiKeyInput.value = model.api_key || "";
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
  els.allowedMcpToolsInput.value = JSON.stringify(agent.allowed_mcp_tools || {}, null, 2);
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
  let allowedMcpTools;
  let interruptOn;
  let responseFormat;
  try {
    mcpServers = JSON.parse(els.mcpServersInput.value || "{}");
    allowedMcpTools = JSON.parse(els.allowedMcpToolsInput.value || "{}");
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
    api_key: els.modelApiKeyInput.value,
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
    allowed_mcp_tools: allowedMcpTools,
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
    setActiveView("settings");
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
        api_key: "",
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
    api_key: "",
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

function renderWorkbench() {
  if (!state.data) return;
  const capabilities = state.data.capabilities || [];
  const targets = capabilities.filter((item) => item.executable);
  const previousTarget = els.testTargetSelect.value;
  els.testTargetSelect.innerHTML = [
    '<option value="">选择 Agent、Skill Binding、Script Action 或 MCP Tool</option>',
    ...targets.map((item) => {
      const unavailable = item.health === "issue";
      const suffix = unavailable ? ` · 不可用：${item.health_issue || "健康检查失败"}` : "";
      return `<option value="${escapeHtml(item.id)}" ${unavailable ? "disabled" : ""}>${escapeHtml(item.name)} · ${translateCapabilityKind(item.kind)}${escapeHtml(suffix)}</option>`;
    })
  ].join("");
  els.testTargetSelect.value = targets.some((item) => item.id === previousTarget) ? previousTarget : "";
  renderCapabilityList(capabilities);
  const cases = state.data.testCases || [];
  if (!cases.some((item) => item.id === state.selectedTestCaseId)) state.selectedTestCaseId = cases[0]?.id || null;
  renderTestCaseList(cases);
  if (state.selectedTestCaseId) selectTestCase(state.selectedTestCaseId, { preserveRun: true });
  else renderBaselineState();
  renderRunHistory(state.data.runs || []);
  renderRevisionControls();
  if (els.policyWorkspace) els.policyWorkspace.value = state.workspace || "";
  renderPolicyConfig();
}

function renderPolicyConfig() {
  const policy = state.data?.config?.policy || {};
  const approvals = policy.require_approval || [];
  if (els.policyAgentApproval) els.policyAgentApproval.checked = approvals.includes("agent");
  if (els.policyScriptApproval) els.policyScriptApproval.checked = approvals.includes("script");
  if (els.policyMcpApproval) els.policyMcpApproval.checked = approvals.includes("mcp:*");
  if (els.policyAllowNetwork) els.policyAllowNetwork.checked = Boolean(policy.allow_network);
  if (els.policyNetworkHosts) els.policyNetworkHosts.value = (policy.allowed_network_hosts || []).join("\n");
  if (els.policyCommands) els.policyCommands.value = (policy.allowed_commands || ["python"]).join("\n");
  if (els.policyExposedEnv) {
    els.policyExposedEnv.value = [
      ...new Set([...(policy.allowed_env_vars || []), ...(policy.exposed_env || [])])
    ].join("\n");
  }
}

async function savePolicyConfig() {
  const config = structuredClone(state.data.config);
  const currentPolicy = config.policy || {};
  const representedApprovals = new Set(["agent", "script", "mcp:*"]);
  const envNames = lines(els.policyExposedEnv.value);
  config.policy = {
    ...currentPolicy,
    require_approval: [
      ...(currentPolicy.require_approval || []).filter((item) => !representedApprovals.has(item)),
      ...(els.policyAgentApproval.checked ? ["agent"] : []),
      ...(els.policyScriptApproval.checked ? ["script"] : []),
      ...(els.policyMcpApproval.checked ? ["mcp:*"] : [])
    ],
    allowed_commands: lines(els.policyCommands.value),
    allow_network: els.policyAllowNetwork.checked,
    allowed_network_hosts: lines(els.policyNetworkHosts.value),
    allowed_env_vars: envNames,
    exposed_env: envNames
  };
  await window.agentFirewall.saveConfig(state.workspace, config);
  state.data.config = config;
  const status = document.querySelector("#policyStatus strong");
  if (status) status.textContent = "策略已保存";
}

function runPolicyCheck() {
  const commands = lines(els.policyCommands.value);
  const hosts = lines(els.policyNetworkHosts.value);
  const envNames = lines(els.policyExposedEnv.value);
  const invalidEnv = envNames.filter((name) => !/^[A-Za-z_][A-Za-z0-9_]*$/.test(name));
  const status = document.querySelector("#policyStatus strong");
  const detail = document.querySelector("#policyStatus small");
  const dot = document.querySelector("#policyStatus .status-dot");
  let message = "策略字段有效";
  let description = "命令、网络和环境变量规则可被执行器读取";
  let className = "success";
  if (!commands.length) {
    message = "所有 Script Action 将被阻止";
    description = "命令白名单为空";
    className = "idle";
  } else if (invalidEnv.length) {
    message = "环境变量名无效";
    description = invalidEnv.join(", ");
    className = "danger";
  } else if (els.policyAllowNetwork.checked && !hosts.length) {
    message = "网络范围过宽";
    description = "允许外部网络但未限制主机";
    className = "idle";
  }
  status.textContent = message;
  detail.textContent = description;
  dot.className = `status-dot ${className}`;
}

function lines(value) {
  return [...new Set(String(value || "").split("\n").map((item) => item.trim()).filter(Boolean))];
}

function renderRevisionControls() {
  const revisions = state.data?.revisions || [];
  if (!revisions.some((item) => item.id === state.selectedRevisionId)) state.selectedRevisionId = revisions[0]?.id || null;
  els.revisionSelect.innerHTML = [
    '<option value="">选择修订</option>',
    ...revisions.map((item) => `<option value="${item.id}">#${item.id} · ${escapeHtml(item.target_type)}:${escapeHtml(item.target_ref)} · ${translateRevisionStatus(item.status)}</option>`)
  ].join("");
  els.revisionSelect.value = state.selectedRevisionId || "";

  const currentTarget = els.revisionTarget.value;
  const targets = (state.data?.testCases || []).filter((testCase) => testCase.baseline_run_id).map((testCase) => ({
    value: String(testCase.id),
    label: `${testCase.name} · ${translateCapabilityKind(testCase.target_type)} · 有基线`
  }));
  els.revisionTarget.innerHTML = [
    '<option value="">选择已有基线的测试用例</option>',
    ...targets.map((item) => `<option value="${escapeHtml(item.value)}">${escapeHtml(item.label)}</option>`)
  ].join("");
  const preferredTarget = String(state.selectedTestCaseId || "");
  if (targets.some((item) => item.value === currentTarget)) els.revisionTarget.value = currentTarget;
  else if (targets.some((item) => item.value === preferredTarget)) els.revisionTarget.value = preferredTarget;
  els.createRevision.disabled = targets.length === 0;
  els.createRevision.title = targets.length ? "" : "先运行测试并显式设为基线";
  selectRevision(state.selectedRevisionId);
}

function selectRevision(revisionId) {
  state.selectedRevisionId = revisionId;
  const revision = (state.data?.revisions || []).find((item) => item.id === revisionId);
  els.revisionSelect.value = revisionId || "";
  if (!revision) {
    els.revisionState.textContent = "尚未创建";
    els.revisionDiff.textContent = "尚未生成修改。";
    els.applyRevision.disabled = true;
    els.revertRevision.disabled = true;
    els.runRevisionCandidate.disabled = true;
    els.reviewRevision.disabled = true;
    return;
  }
  const comparison = comparisonForRevision(revision);
  const reviewed = Boolean(revision.reviewed_at && revision.comparison_id);
  els.revisionState.textContent = `#${revision.id} · ${revisionStage(revision, comparison)}`;
  els.revisionDiff.textContent = revision.diff || formatRevisionDiff(revision.before_json, revision.after_json);
  els.runRevisionCandidate.disabled = Boolean(state.activeTestOperationId) || revision.status !== "draft" || !revision.test_case_id || !revision.baseline_run_id;
  els.reviewRevision.disabled = revision.status !== "draft" || reviewed || !comparison?.result_json?.passed;
  els.applyRevision.disabled = revision.status !== "draft" || !reviewed;
  els.revertRevision.disabled = revision.status !== "applied";
}

async function createWorkbenchRevision() {
  const testCase = (state.data?.testCases || []).find((item) => item.id === Number(els.revisionTarget.value));
  const reason = els.revisionReason.value.trim();
  if (!testCase || !reason) return setWorkbenchError("请选择证据用例并填写修改原因。");
  if (!testCase.baseline_run_id) return setWorkbenchError("创建修订前，请先为证据用例设置成功基线。");
  let after;
  try {
    after = parseJsonField(els.revisionAfterJson, {});
    if (!after || Array.isArray(after) || typeof after !== "object") throw new Error("变更字段必须是 JSON 对象");
  } catch (error) {
    return setWorkbenchError(`修改 JSON 无效: ${error.message}`);
  }
  els.createRevision.disabled = true;
  try {
    const revision = await window.agentFirewall.createRevision(state.workspace, {
      target_type: testCase.target_type,
      target_ref: testCase.target_ref,
      after,
      reason,
      test_case_id: testCase.id,
      baseline_run_id: testCase.baseline_run_id
    });
    state.selectedRevisionId = revision.id;
    await refreshWorkspaceData();
    selectRevision(revision.id);
  } catch (error) {
    setWorkbenchError(error.message);
  } finally {
    els.createRevision.disabled = !(state.data?.testCases || []).some((item) => item.baseline_run_id);
  }
}

async function applySelectedRevision() {
  const revision = (state.data?.revisions || []).find((item) => item.id === state.selectedRevisionId);
  if (!revision || revision.status !== "draft" || !revision.reviewed_at || !revision.comparison_id) return;
  if (!window.confirm(`应用已通过回归比较并完成审核的修订 #${revision.id}？`)) return;
  els.applyRevision.disabled = true;
  try {
    await window.agentFirewall.applyRevision(state.workspace, revision.id);
    await refreshWorkspaceData();
    selectRevision(revision.id);
  } catch (error) {
    setWorkbenchError(error.message);
    selectRevision(revision.id);
  }
}

async function reviewSelectedRevision() {
  const revision = (state.data?.revisions || []).find((item) => item.id === state.selectedRevisionId);
  const comparison = comparisonForRevision(revision);
  if (!revision || revision.status !== "draft" || !comparison?.result_json?.passed) return;
  els.reviewRevision.disabled = true;
  try {
    await window.agentFirewall.reviewRevision(state.workspace, revision.id, comparison.id);
    await refreshWorkspaceData();
    selectRevision(revision.id);
  } catch (error) {
    setWorkbenchError(error.message);
    selectRevision(revision.id);
  }
}

async function revertSelectedRevision() {
  const revision = (state.data?.revisions || []).find((item) => item.id === state.selectedRevisionId);
  if (!revision || revision.status !== "applied") return;
  if (!window.confirm(`回滚修订 #${revision.id}，恢复应用前配置？`)) return;
  els.revertRevision.disabled = true;
  try {
    await window.agentFirewall.revertRevision(state.workspace, revision.id);
    await refreshWorkspaceData();
    selectRevision(revision.id);
  } catch (error) {
    setWorkbenchError(error.message);
    selectRevision(revision.id);
  }
}

function formatRevisionDiff(before, after) {
  const left = JSON.stringify(before || {}, null, 2).split("\n").map((line) => `-${line}`);
  const right = JSON.stringify(after || {}, null, 2).split("\n").map((line) => `+${line}`);
  return ["--- before", "+++ after", ...left, ...right].join("\n");
}

function translateRevisionStatus(status) {
  return ({ draft: "待审核", applied: "已应用", reverted: "已回滚" })[status] || status;
}

function comparisonForRevision(revision) {
  if (!revision) return null;
  const comparisons = state.data?.comparisons || [];
  if (revision.comparison_id) return comparisons.find((item) => item.id === revision.comparison_id) || null;
  return comparisons.find((item) => item.revision_id === revision.id && item.candidate_run_id === revision.candidate_run_id) || null;
}

function revisionStage(revision, comparison) {
  if (revision.status !== "draft") return translateRevisionStatus(revision.status);
  if (revision.reviewed_at && revision.comparison_id) return "已审核 · 待应用";
  if (comparison?.result_json?.passed) return "比较通过 · 待审核";
  if (comparison) return "比较未通过";
  if (revision.candidate_run_id) return "候选已运行 · 待比较";
  return "待运行候选";
}

function renderCapabilityList(items) {
  if (!els.capabilityList) return;
  const visible = items.filter((item) => {
    const kindMatches = !state.capabilityKind || item.kind === state.capabilityKind || (
      state.capabilityKind === "skill" && item.kind === "script_action"
    );
    const queryMatches = !state.capabilityQuery || [item.name, item.description, item.ref, item.kind]
      .some((value) => String(value || "").toLowerCase().includes(state.capabilityQuery));
    return kindMatches && queryMatches;
  });
  els.capabilityList.innerHTML = visible.length ? visible.map((item) => {
    const discovery = state.mcpDiscoveryStatus[item.id];
    const healthClass = discovery?.status === "error" ? "danger" : discovery?.status === "running" ? "warning" : item.health === "available" ? "success" : item.health === "issue" ? "danger" : "neutral";
    const healthText = discovery?.status === "error" ? "发现失败" : discovery?.status === "running" ? "发现中" : discovery?.count != null ? `已发现 ${discovery.count}` : item.health === "available" ? "可用" : item.health === "issue" ? "有问题" : "未检查";
    return `
      <article class="capability-item" ${discovery?.message ? `title="${escapeHtml(discovery.message)}"` : ""}>
        <div class="capability-kind">${escapeHtml(translateCapabilityKind(item.kind))}</div>
        <div><strong>${escapeHtml(item.name)}</strong><small>${escapeHtml(item.description || item.ref || "")}</small></div>
        <span class="status-label ${healthClass}">${escapeHtml(healthText)}</span>
        <code>${item.kind === "agent" && Object.keys(item.allowed_mcp_tools || {}).length ? `允许 ${Object.values(item.allowed_mcp_tools).flat().length} 个 MCP Tool` : item.executable ? "可执行" : item.kind === "mcp_server" ? "连接容器" : "绑定资源"}</code>
        <div class="capability-actions">
          ${item.kind === "mcp_server" ? `<button data-discover-mcp="${escapeHtml(item.id)}" type="button" ${discovery?.status === "running" ? "disabled" : ""}>发现工具</button>` : ""}
        </div>
      </article>
    `;
  }).join("") : '<div class="empty-state wide"><strong>没有发现能力</strong></div>';
  els.capabilityList.querySelectorAll("[data-discover-mcp]").forEach((button) => {
    button.addEventListener("click", () => discoverMcpServer(button.dataset.discoverMcp));
  });
}

async function discoverMcpServer(capabilityId) {
  const server = (state.data?.capabilities || []).find((item) => item.id === capabilityId && item.kind === "mcp_server");
  if (!server) return;
  const approvals = state.data?.config?.policy?.require_approval || [];
  const requiresApproval = approvals.includes("mcp:*") || approvals.includes("mcp:connect");
  if (requiresApproval && !window.confirm(`批准本次连接并发现 MCP Server “${server.name}” 的工具？`)) return;
  state.mcpDiscoveryStatus[capabilityId] = { status: "running" };
  renderCapabilityList(state.data.capabilities || []);
  try {
    const tools = await window.agentFirewall.discoverMcpTools(
      state.workspace, server.agent, server.ref, requiresApproval
    );
    state.mcpDiscoveryStatus[capabilityId] = { status: "success", count: tools.length };
    await refreshWorkspaceData();
  } catch (error) {
    state.mcpDiscoveryStatus[capabilityId] = { status: "error", message: error.message };
    renderCapabilityList(state.data.capabilities || []);
  }
}

function renderTestCaseList(cases) {
  if (!els.testCaseList) return;
  if (!cases.length) {
    els.testCaseList.innerHTML = '<button class="test-case-item active" data-new-test-case type="button"><span class="status-dot idle"></span><span><strong>新测试用例</strong><small>尚未保存</small></span></button>';
    els.testCaseList.querySelector("[data-new-test-case]")?.addEventListener("click", () => newWorkbenchCase());
    return;
  }
  els.testCaseList.innerHTML = cases.map((item) => `
    <button class="test-case-item ${item.id === state.selectedTestCaseId ? "active" : ""}" data-test-id="${item.id}" type="button">
      <span class="status-dot ${item.baseline_run_id ? "success" : "idle"}"></span><span><strong>${escapeHtml(item.name)}</strong><small>${escapeHtml(translateCapabilityKind(item.target_type))} · ${item.baseline_run_id ? "有基线" : "未设基线"}</small></span>
    </button>
  `).join("");
  els.testCaseList.querySelectorAll("[data-test-id]").forEach((button) => button.addEventListener("click", () => selectTestCase(Number(button.dataset.testId))));
}

function newWorkbenchCase() {
  if (state.activeTestOperationId) return;
  state.selectedTestCaseId = null;
  state.lastTestResult = null;
  els.testNameInput.value = "";
  els.testTargetSelect.value = "";
  els.testGoalInput.value = "";
  els.testInputJson.value = "{}";
  els.testAssertionsJson.value = "[]";
  renderTestCaseList(state.data?.testCases || []);
  renderBaselineState();
}

function selectTestCase(id, { preserveRun = false } = {}) {
  const item = (state.data.testCases || []).find((test) => test.id === id);
  if (!item) return;
  state.selectedTestCaseId = id;
  if (!preserveRun) state.lastTestResult = null;
  els.testNameInput.value = item.name;
  els.testGoalInput.value = item.goal;
  const capability = (state.data.capabilities || []).find((candidate) => {
    if (candidate.kind !== item.target_type || candidate.ref !== item.target_ref) return false;
    if (item.target_type === "mcp_tool") {
      return candidate.name === item.input_json?.tool && (!item.input_json?.agent || candidate.agent === item.input_json.agent);
    }
    if (item.target_type === "script_action") return candidate.script === item.input_json?.script;
    if (item.target_type === "skill_binding") return candidate.agent === item.input_json?.agent;
    return true;
  });
  els.testTargetSelect.value = capability?.id || "";
  els.testInputJson.value = JSON.stringify(item.input_json || {}, null, 2);
  els.testAssertionsJson.value = JSON.stringify(item.assertions_json || [], null, 2);
  if ([...els.revisionTarget.options].some((option) => option.value === String(id))) {
    els.revisionTarget.value = String(id);
  }
  renderTestCaseList(state.data.testCases || []);
  renderBaselineState();
}

function applyTargetDefaults() {
  const capability = selectedCapability();
  if (!capability) return;
  const current = parseJsonField(els.testInputJson, {});
  if (capability.kind === "script_action") current.script = capability.script;
  if (capability.kind === "skill_binding") current.agent = capability.agent;
  if (capability.kind === "mcp_tool") Object.assign(current, {
    agent: capability.agent,
    server: capability.ref,
    tool: capability.name,
    input_schema: capability.input_schema || {},
    args: current.args || {}
  });
  els.testInputJson.value = JSON.stringify(current, null, 2);
}

function selectedCapability() {
  return (state.data?.capabilities || []).find((item) => item.id === els.testTargetSelect?.value);
}

async function saveWorkbenchCase() {
  const capability = selectedCapability();
  if (!capability) return setWorkbenchError("请选择可执行目标能力。");
  if (capability.health === "issue") {
    return setWorkbenchError(`目标能力不可用：${capability.health_issue || "健康检查失败"}`);
  }
  let input;
  let assertions;
  try {
    input = parseJsonField(els.testInputJson, {});
    assertions = parseJsonField(els.testAssertionsJson, []);
  } catch (error) {
    return setWorkbenchError(`JSON 无效: ${error.message}`);
  }
  const value = {
    ...(state.selectedTestCaseId ? { id: state.selectedTestCaseId } : {}),
    name: els.testNameInput.value.trim() || "未命名测试",
    target_type: capability.kind,
    target_ref: capability.ref,
    goal: els.testGoalInput.value.trim(),
    input_json: input,
    assertions_json: assertions
  };
  const saved = await window.agentFirewall.saveTestCase(state.workspace, value);
  state.selectedTestCaseId = saved.id;
  const index = (state.data.testCases || []).findIndex((item) => item.id === saved.id);
  if (index >= 0) state.data.testCases[index] = saved;
  else state.data.testCases.unshift(saved);
  renderTestCaseList(state.data.testCases);
  setWorkbenchStatus("success", "测试用例已保存");
  return saved;
}

async function executeWorkbenchCase(approved = false, revisionId = null) {
  if (state.activeTestOperationId) return;
  const operationId = crypto.randomUUID();
  try {
    const revision = (state.data?.revisions || []).find((item) => item.id === revisionId);
    const saved = revision
      ? (state.data?.testCases || []).find((item) => item.id === revision.test_case_id)
      : await saveWorkbenchCase();
    if (!saved) return;
    if (revision) {
      state.selectedTestCaseId = saved.id;
      selectTestCase(saved.id, { preserveRun: true });
      state.selectedRevisionId = revision.id;
    }
    const baselineRunId = revision?.baseline_run_id || saved.baseline_run_id || "";
    state.activeTestOperationId = operationId;
    state.testStartedAt = Date.now();
    startTestRunPolling(operationId);
    setWorkbenchRunning(true);
    const result = await window.agentFirewall.runTestCase(
      state.workspace,
      saved.id,
      baselineRunId,
      approved,
      operationId,
      revision?.id || ""
    );
    if (result.status === "cancelled") {
      try {
        const cancelledRun = await window.agentFirewall.getRunDetails(state.workspace, operationId);
        result.run_id = operationId;
        result.test_case_id = saved.id;
        result.events = cancelledRun.events || [];
      } catch {
        result.run_id = operationId;
        result.test_case_id = saved.id;
      }
    }
    result.durationMs = Date.now() - state.testStartedAt;
    if (result.status !== "cancelled" && baselineRunId && result.run_id && result.run_id !== baselineRunId) {
      try {
        result.comparison = await window.agentFirewall.compareRuns(state.workspace, baselineRunId, result.run_id);
      } catch (error) {
        result.comparisonError = error.message;
      }
    }
    state.lastTestResult = result;
    state.pendingRevisionId = result.status === "needs_input" ? revision?.id || null : null;
    state.selectedTestCaseId = saved.id;
    await refreshWorkspaceData();
    renderTestResult(result);
  } catch (error) {
    setWorkbenchError(error.message);
  } finally {
    stopTestRunPolling();
    if (state.activeTestOperationId === operationId) state.activeTestOperationId = null;
    setWorkbenchRunning(false);
  }
}

function renderTestResult(result) {
  const events = result.events || [];
  renderTraceEvents(events, result.status === "cancelled");
  if (result.status === "cancelled") {
    els.diagnosisPanel.innerHTML = '<div class="section-title"><span>运行状态</span><span class="status-label warning">已取消</span></div><p>本地后端进程已终止，取消终态和事件已写入运行记录。</p>';
  } else if (result.diagnosis) {
    const statusClass = result.status === "needs_input" ? "warning" : "danger";
    els.diagnosisPanel.innerHTML = `<div class="section-title"><span>失败定位</span><span class="status-label ${statusClass}">${escapeHtml(result.diagnosis.layer)}</span></div><p>${escapeHtml(result.diagnosis.message)}</p>`;
  } else {
    const comparison = result.comparison?.result_json;
    const comparisonText = result.comparisonError
      ? `运行通过，但基线比较未保存：${result.comparisonError}`
      : comparison ? (comparison.passed ? "候选通过基线比较。" : `检测到回归：${comparison.regressions.join("；") || "候选未通过"}`) : "全部断言通过，可显式设为基线。";
    const comparisonClass = result.comparisonError ? "warning" : comparison && !comparison.passed ? "danger" : "success";
    const comparisonLabel = result.comparisonError ? "比较失败" : comparison ? (comparison.passed ? "比较通过" : "检测到回归") : "通过";
    els.diagnosisPanel.innerHTML = `<div class="section-title"><span>验收结果</span><span class="status-label ${comparisonClass}">${comparisonLabel}</span></div><p>${escapeHtml(comparisonText)}</p>`;
  }
  renderAssertionEvidence(result.assertions);
  els.traceEventCount.textContent = `${events.length} 个事件`;
  els.traceDuration.textContent = `耗时 ${formatDuration(result.durationMs)}`;
  els.traceStatus.textContent = translateStatus(result.status);
  els.traceStatus.className = `status-label ${statusClass(result.status)}`;
  setWorkbenchStatus(result.status, translateStatus(result.status));
  els.approveOperation.disabled = result.status !== "needs_input";
  els.rerunTestCase.disabled = result.status === "cancelled" || !state.selectedTestCaseId;
  renderBaselineState();
}

function renderTraceEvents(events, cancelled = false) {
  if (!events.length) {
    els.traceList.innerHTML = cancelled
      ? '<div class="empty-state"><strong>运行已取消</strong><p>取消终态已写入本地运行记录。</p></div>'
      : '<div class="empty-state"><strong>等待首个事件</strong></div>';
    return;
  }
  els.traceList.innerHTML = events.map((event) => `
    <article class="trace-event">
      <span class="status-dot ${event.event_type === "run_finished" && ["failed", "cancelled"].includes(event.payload?.status) ? "danger" : "success"}"></span>
      <div><strong>${escapeHtml(event.event_type)}</strong><small>${escapeHtml(event.node_id || "run")}</small><pre>${escapeHtml(JSON.stringify(event.payload, null, 2))}</pre></div>
    </article>
  `).join("");
  els.traceList.scrollTop = els.traceList.scrollHeight;
}

function startTestRunPolling(runId) {
  stopTestRunPolling();
  const workspace = state.workspace;
  const poll = async () => {
    if (state.testPollBusy || state.activeTestOperationId !== runId || state.workspace !== workspace) return;
    state.testPollBusy = true;
    try {
      const run = await window.agentFirewall.getRunDetails(workspace, runId);
      if (state.activeTestOperationId !== runId || state.workspace !== workspace) return;
      renderLiveTestRun(run);
    } catch {
      // The run row may not exist during the first process startup tick.
    } finally {
      state.testPollBusy = false;
    }
  };
  state.testPollTimer = window.setInterval(poll, 600);
  poll();
}

function stopTestRunPolling() {
  if (state.testPollTimer) window.clearInterval(state.testPollTimer);
  state.testPollTimer = null;
  state.testPollBusy = false;
}

function renderLiveTestRun(run) {
  const events = run?.events || [];
  renderTraceEvents(events);
  els.traceEventCount.textContent = `${events.length} 个事件`;
  els.traceDuration.textContent = `耗时 ${formatDuration(Date.now() - new Date(run.started_at).getTime())}`;
  els.traceStatus.textContent = translateStatus(run.status);
  els.traceStatus.className = `status-label ${statusClass(run.status)}`;
  setWorkbenchStatus(run.status, `${translateStatus(run.status)} · ${events.length} 个事件`);
  const assertions = [...events].reverse().find((event) => event.event_type === "assertions_evaluated");
  if (assertions) renderAssertionEvidence(assertions.payload);
  const diagnosis = [...events].reverse().find((event) => event.event_type === "diagnosis_created");
  if (diagnosis) {
    els.diagnosisPanel.innerHTML = `<div class="section-title"><span>失败定位</span><span class="status-label danger">${escapeHtml(diagnosis.payload.layer)}</span></div><p>${escapeHtml(diagnosis.payload.message)}</p>`;
  }
}

function startFlowRunPolling(runId) {
  stopFlowRunPolling();
  const poll = async () => {
    if (state.flowPollBusy || state.activeFlowOperationId !== runId) return;
    state.flowPollBusy = true;
    try {
      const run = await window.agentFirewall.getRunDetails(state.workspace, runId);
      state.lastRun = run;
      const events = (run.events || [])
        .filter((event) => ["node_started", "node_finished", "node_retrying", "run_paused", "run_resumed"].includes(event.event_type))
        .map(formatRunEvent);
      els.runStatus.textContent = translateStatus(run.status);
      els.runOutput.textContent = [`运行: ${run.run_id}`, ...events, run.final_summary || ""].filter(Boolean).join("\n");
    } catch {
      // The run row may not exist during the first process startup tick.
    } finally {
      state.flowPollBusy = false;
    }
  };
  state.flowPollTimer = window.setInterval(poll, 600);
  poll();
}

function stopFlowRunPolling() {
  if (state.flowPollTimer) window.clearInterval(state.flowPollTimer);
  state.flowPollTimer = null;
  state.flowPollBusy = false;
}

function renderAssertionEvidence(assertions) {
  if (!els.evidenceSection) return;
  const results = assertions?.results || [];
  els.evidenceSection.innerHTML = `
    <div class="section-title"><span>断言证据</span><small>${results.length} 项</small></div>
    ${results.length ? results.map((item) => `<div class="empty-inline">${item.passed ? "通过" : "失败"} · ${escapeHtml(item.message || item.kind || "断言")}</div>`).join("") : '<div class="empty-inline">本次运行没有断言结果。</div>'}
  `;
}

function currentTestCase() {
  return (state.data?.testCases || []).find((item) => item.id === state.selectedTestCaseId) || null;
}

function renderBaselineState() {
  const testCase = currentTestCase();
  const baselineRunId = testCase?.baseline_run_id || "";
  els.baselineStatus.textContent = baselineRunId ? "基线已设置" : "未设置基线";
  els.baselineRunId.textContent = baselineRunId || "--";
  els.baselineRunId.title = baselineRunId;
  const result = state.lastTestResult;
  const canSet = result?.status === "success" && !result.revision_id && result.test_case_id === testCase?.id && result.run_id !== baselineRunId;
  els.setBaseline.disabled = state.activeTestOperationId || !canSet;
  els.runTestCase.textContent = baselineRunId ? "▶ 运行候选并比较" : "▶ 运行测试";
}

function setWorkbenchRunning(running) {
  els.runTestCase.disabled = running;
  els.saveTestCase.disabled = running;
  const canAbandon = !running && ["needs_input", "blocked"].includes(state.lastTestResult?.status) && Boolean(state.lastTestResult?.run_id);
  els.cancelTestRun.disabled = !running && !canAbandon;
  els.cancelTestRun.textContent = canAbandon ? "放弃本次运行" : "取消测试";
  els.runRevisionCandidate.disabled = running;
  els.reviewRevision.disabled = running;
  els.applyRevision.disabled = running;
  if (running) {
    els.approveOperation.disabled = true;
    els.rerunTestCase.disabled = true;
    els.setBaseline.disabled = true;
    els.traceList.innerHTML = '<div class="empty-state"><strong>本地后端进程运行中</strong><p>正在从 SQLite 增量载入执行事件。</p></div>';
    els.traceStatus.textContent = "运行中";
    els.traceStatus.className = "status-label warning";
    els.traceEventCount.textContent = "0 个事件";
    els.traceDuration.textContent = "耗时 --";
    setWorkbenchStatus("running", "运行中 · 事件实时载入");
  }
  renderBaselineState();
  if (!running) selectRevision(state.selectedRevisionId);
}

function setWorkbenchStatus(status, text) {
  const dotClass = status === "success" ? "success" : ["failed", "error"].includes(status) ? "danger" : "idle";
  els.workbenchStatusDot.className = `status-dot ${dotClass}`;
  els.workbenchStatusText.textContent = text;
}

async function cancelActiveTestRun() {
  const operationId = state.activeTestOperationId || state.lastTestResult?.run_id;
  if (!operationId) return;
  els.cancelTestRun.disabled = true;
  setWorkbenchStatus("running", "正在停止本地进程");
  try {
    await window.agentFirewall.cancelOperation(state.workspace, operationId);
    if (!state.activeTestOperationId) {
      const run = await window.agentFirewall.getRunDetails(state.workspace, operationId);
      state.lastTestResult = { ...run, test_case_id: state.selectedTestCaseId, durationMs: Date.now() - new Date(run.started_at).getTime() };
      renderTestResult(state.lastTestResult);
      await refreshWorkspaceData();
      setWorkbenchRunning(false);
    }
  } catch (error) {
    setWorkbenchError(`停止运行失败: ${error.message}`);
  }
}

async function cancelActiveFlowRun() {
  const operationId = state.activeFlowOperationId;
  if (!operationId) return;
  els.cancelFlow.disabled = true;
  els.runStatus.textContent = "正在停止";
  try {
    const signalled = await window.agentFirewall.cancelOperation(state.workspace, operationId);
    if (!signalled) els.runOutput.textContent = "运行已经结束，未找到可停止的本地进程。";
  } catch (error) {
    els.runStatus.textContent = "停止失败";
    els.runOutput.textContent = error.message;
  }
}

async function setCurrentRunAsBaseline() {
  const result = state.lastTestResult;
  if (!result?.run_id || result.status !== "success") return;
  await setRunAsBaseline(result.test_case_id, result.run_id);
}

async function setRunAsBaseline(testCaseId, runId) {
  const testCase = (state.data?.testCases || []).find((item) => item.id === testCaseId);
  const run = (state.data?.runs || []).find((item) => item.run_id === runId);
  if (!testCase || run?.status !== "success" || run.revision_id) return setWorkbenchError("只有非修订候选的成功测试运行可以设为基线。");
  if (testCase.baseline_run_id && testCase.baseline_run_id !== runId && !window.confirm("替换该测试用例当前基线？")) return;
  els.setBaseline.disabled = true;
  try {
    await window.agentFirewall.setTestBaseline(state.workspace, testCaseId, runId);
    state.selectedTestCaseId = testCaseId;
    await refreshWorkspaceData();
    setWorkbenchStatus("success", "基线已保存");
  } catch (error) {
    setWorkbenchError(error.message);
    renderBaselineState();
  }
}

function renderRunHistory(runs) {
  if (!els.runHistoryList) return;
  const filtered = state.runStatusFilter ? runs.filter((run) => run.status === state.runStatusFilter) : runs;
  const comparisons = state.data?.comparisons || [];
  els.runHistoryList.innerHTML = filtered.length ? filtered.map((run) => {
    const testCaseId = testCaseIdForRun(run);
    const testCase = (state.data?.testCases || []).find((item) => item.id === testCaseId);
    const snapshotCase = run.flow_snapshot?.test_case || {};
    const isTest = run.run_kind === "test_case" || Boolean(testCaseId);
    const isBaseline = Boolean(run.is_baseline || (testCase?.baseline_run_id && testCase.baseline_run_id === run.run_id));
    const isCandidate = Boolean(run.parent_run_id || run.revision_id);
    const comparison = comparisons.find((item) => item.candidate_run_id === run.run_id);
    const comparisonText = comparison ? (comparison.result_json?.passed ? "比较通过" : "检测到回归") : isBaseline ? "基线" : isCandidate ? "候选 · 待比较" : "未比较";
    const targetName = isTest ? (testCase?.name || snapshotCase.name || `测试用例 #${testCaseId}`) : (run.flow_name || "default");
    const targetRef = isTest ? `${translateCapabilityKind(testCase?.target_type || snapshotCase.target_type)} · ${testCase?.target_ref || snapshotCase.target_ref || "--"}` : run.goal;
    return `
      <article class="run-history-row">
        <div class="run-context"><span class="run-type-badge ${isTest ? "test" : ""}">${isTest ? "TEST CASE" : "FLOW"}</span><code>${escapeHtml(run.run_id.slice(0, 8))}</code><span>${run.revision_id ? `修订 #${run.revision_id}` : isBaseline ? "基线" : isCandidate ? "候选" : ""}</span></div>
        <div class="run-target"><strong>${escapeHtml(targetName)}</strong><small>${escapeHtml(targetRef)}</small></div>
        <div class="run-comparison"><span class="status-label ${statusClass(run.status)}">${escapeHtml(translateStatus(run.status))}</span><small>${escapeHtml(comparisonText)}</small></div>
        <span>${formatRunDuration(run)}</span>
        <time title="${escapeHtml(run.started_at || "")}">${escapeHtml(formatDateTime(run.started_at))}</time>
        <div class="run-row-actions">
          ${isTest ? `<button data-open-test="${testCaseId}" data-run-id="${escapeHtml(run.run_id)}" type="button">查看</button>` : ""}
          ${isTest && run.status === "success" && !isBaseline && !run.revision_id ? `<button data-set-baseline="${testCaseId}" data-run-id="${escapeHtml(run.run_id)}" type="button">设为基线</button>` : ""}
        </div>
      </article>
    `;
  }).join("") : '<div class="empty-state wide"><strong>暂无匹配的运行记录</strong></div>';
  els.runHistoryList.querySelectorAll("[data-open-test]").forEach((button) => {
    button.addEventListener("click", () => openTestRun(Number(button.dataset.openTest), button.dataset.runId));
  });
  els.runHistoryList.querySelectorAll("[data-set-baseline]").forEach((button) => {
    button.addEventListener("click", () => setRunAsBaseline(Number(button.dataset.setBaseline), button.dataset.runId));
  });
}

async function openTestRun(testCaseId, runId) {
  selectTestCase(testCaseId);
  setActiveView("workbench");
  try {
    const run = await window.agentFirewall.getRunDetails(state.workspace, runId);
    if (state.selectedTestCaseId !== testCaseId) return;
    const events = run.events || [];
    const assertions = [...events].reverse().find((event) => event.event_type === "assertions_evaluated")?.payload;
    const diagnosis = [...events].reverse().find((event) => event.event_type === "diagnosis_created")?.payload;
    state.lastTestResult = {
      ...run,
      test_case_id: testCaseId,
      assertions,
      diagnosis,
      durationMs: run.finished_at ? new Date(run.finished_at).getTime() - new Date(run.started_at).getTime() : 0
    };
    renderTestResult(state.lastTestResult);
  } catch (error) {
    setWorkbenchError(error.message);
  }
}

function testCaseIdForRun(run) {
  if (run.test_case_id) return Number(run.test_case_id);
  if (String(run.flow_name || "").startsWith("test:")) return Number(String(run.flow_name).slice(5)) || null;
  return Number(run.flow_snapshot?.test_case?.id) || null;
}

function formatRunDuration(run) {
  if (!run.started_at || !run.finished_at) return "--";
  return formatDuration(new Date(run.finished_at).getTime() - new Date(run.started_at).getTime());
}

function formatDuration(milliseconds) {
  if (!Number.isFinite(milliseconds) || milliseconds < 0) return "--";
  if (milliseconds < 1000) return `${Math.round(milliseconds)} ms`;
  return `${(milliseconds / 1000).toFixed(milliseconds < 10000 ? 1 : 0)} s`;
}

function formatDateTime(value) {
  if (!value) return "--";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString("zh-CN", { hour12: false });
}

function statusClass(status) {
  if (status === "success") return "success";
  if (["running", "needs_input", "blocked", "cancelled"].includes(status)) return "warning";
  if (["failed", "error", "timeout"].includes(status)) return "danger";
  return "neutral";
}

async function refreshWorkspaceData() {
  const refreshed = await window.agentFirewall.loadWorkspace(state.workspace);
  setWorkspaceData(refreshed);
  return refreshed;
}

function parseJsonField(element, fallback) {
  const text = element?.value.trim();
  return text ? JSON.parse(text) : fallback;
}

function setWorkbenchError(message) {
  if (els.diagnosisPanel) els.diagnosisPanel.innerHTML = `<div class="section-title"><span>配置错误</span><span class="status-label danger">阻塞</span></div><p>${escapeHtml(message)}</p>`;
  if (els.traceStatus) {
    els.traceStatus.textContent = "错误";
    els.traceStatus.className = "status-label danger";
  }
  if (els.workbenchStatusText) setWorkbenchStatus("error", "操作失败");
  return null;
}

function translateCapabilityKind(kind) {
  return ({ agent: "Agent", skill: "Skill", skill_binding: "Skill Binding", script_action: "Script Action", mcp_server: "MCP Server", mcp_tool: "MCP Tool" })[kind] || kind;
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
    timeout: "超时",
    running: "运行中",
    cancelled: "已取消"
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
