const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("agentFirewall", {
  loadWorkspace: (workspace) => ipcRenderer.invoke("workspace:load", workspace),
  chooseWorkspace: () => ipcRenderer.invoke("workspace:choose"),
  saveConfig: (workspace, config) => ipcRenderer.invoke("config:save", { workspace, config }),
  saveTestCase: (workspace, testCase) => ipcRenderer.invoke("test-case:save", { workspace, testCase }),
  runTestCase: (workspace, testCaseId, baselineRunId) =>
    ipcRenderer.invoke("test-case:run", { workspace, testCaseId, baselineRunId }),
  preflightFlow: (workspace, flow) => ipcRenderer.invoke("flow:preflight", { workspace, flow }),
  discoverMcpTools: (workspace, agent, server) =>
    ipcRenderer.invoke("mcp:discover", { workspace, agent, server }),
  compareRuns: (workspace, baseline, candidate) =>
    ipcRenderer.invoke("run:compare", { workspace, baseline, candidate }),
  createRevision: (workspace, revision) => ipcRenderer.invoke("revision:create", { workspace, revision }),
  applyRevision: (workspace, revisionId) => ipcRenderer.invoke("revision:apply", { workspace, revisionId }),
  revertRevision: (workspace, revisionId) => ipcRenderer.invoke("revision:revert", { workspace, revisionId }),
  saveFlow: (workspace, flow) => ipcRenderer.invoke("flow:save", { workspace, flow }),
  startFlow: (workspace, flow) => ipcRenderer.invoke("flow:start", { workspace, flow }),
  resumeFlow: (workspace, runId, correction) =>
    ipcRenderer.invoke("flow:resume", { workspace, runId, correction })
});
