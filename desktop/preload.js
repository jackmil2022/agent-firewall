const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("agentFirewall", {
  loadWorkspace: (workspace) => ipcRenderer.invoke("workspace:load", workspace),
  chooseWorkspace: () => ipcRenderer.invoke("workspace:choose"),
  saveConfig: (workspace, config) => ipcRenderer.invoke("config:save", { workspace, config }),
  saveFlow: (workspace, flow) => ipcRenderer.invoke("flow:save", { workspace, flow }),
  startFlow: (workspace, flow) => ipcRenderer.invoke("flow:start", { workspace, flow })
});
