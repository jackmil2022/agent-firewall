const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("agentFirewall", {
  loadWorkspace: (workspace) => ipcRenderer.invoke("workspace:load", workspace),
  chooseWorkspace: () => ipcRenderer.invoke("workspace:choose"),
  saveFlow: (workspace, flow) => ipcRenderer.invoke("flow:save", { workspace, flow }),
  startFlow: (workspace, flow) => ipcRenderer.invoke("flow:start", { workspace, flow })
});
