const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("agentFirewall", {
  loadWorkspace: (workspace) => ipcRenderer.invoke("workspace:load", workspace),
  chooseWorkspace: () => ipcRenderer.invoke("workspace:choose"),
  saveConfig: (workspace, config) => ipcRenderer.invoke("config:save", { workspace, config }),
  testModelConnection: (workspace) => ipcRenderer.invoke("model:test", workspace),
  saveTestCase: (workspace, testCase) => ipcRenderer.invoke("test-case:save", { workspace, testCase }),
  setTestBaseline: (workspace, testCaseId, runId) =>
    ipcRenderer.invoke("test-case:baseline-set", { workspace, testCaseId, runId }),
  runTestCase: (workspace, testCaseId, baselineRunId, approved, operationId, revisionId) =>
    ipcRenderer.invoke("test-case:run", { workspace, testCaseId, baselineRunId, approved, operationId, revisionId }),
  cancelOperation: (workspace, operationId) => ipcRenderer.invoke("operation:cancel", { workspace, operationId }),
  preflightFlow: (workspace, flow) => ipcRenderer.invoke("flow:preflight", { workspace, flow }),
  discoverMcpTools: (workspace, agent, server, approved) =>
    ipcRenderer.invoke("mcp:discover", { workspace, agent, server, approved }),
  importLocalCapability: (workspace) => ipcRenderer.invoke("capability:import-local", workspace),
  compareRuns: (workspace, baseline, candidate) =>
    ipcRenderer.invoke("run:compare", { workspace, baseline, candidate }),
  getRunDetails: (workspace, runId) => ipcRenderer.invoke("run:details", { workspace, runId }),
  createRevision: (workspace, revision) => ipcRenderer.invoke("revision:create", { workspace, revision }),
  reviewRevision: (workspace, revisionId, comparisonId) =>
    ipcRenderer.invoke("revision:review", { workspace, revisionId, comparisonId }),
  applyRevision: (workspace, revisionId) => ipcRenderer.invoke("revision:apply", { workspace, revisionId }),
  revertRevision: (workspace, revisionId) => ipcRenderer.invoke("revision:revert", { workspace, revisionId }),
  saveFlow: (workspace, flow) => ipcRenderer.invoke("flow:save", { workspace, flow }),
  startFlow: (workspace, flow, goal, operationId) => ipcRenderer.invoke("flow:start", { workspace, flow, goal, operationId }),
  resumeFlow: (workspace, runId, correction, operationId) =>
    ipcRenderer.invoke("flow:resume", { workspace, runId, correction, operationId })
});
