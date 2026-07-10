const { app, BrowserWindow, ipcMain, dialog, Menu } = require("electron");
const path = require("path");
const {
  loadWorkspace,
  saveConfig,
  saveFlow,
  saveAndStartFlow,
  resumeFlow,
  saveTestCase,
  runTestCase,
  preflightFlow,
  discoverMcpTools,
  compareRuns,
  createRevision,
  applyRevision,
  revertRevision
} = require("./workspace");

let mainWindow;

function resolveWorkspace(input) {
  return path.resolve(input || path.join(__dirname, ".."));
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1320,
    height: 860,
    minWidth: 1080,
    minHeight: 700,
    show: false,
    title: "Agent Firewall",
    backgroundColor: "#111411",
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false
    }
  });

  mainWindow.loadFile(path.join(__dirname, "renderer", "index.html"));
  mainWindow.once("ready-to-show", () => mainWindow.show());
}

app.whenReady().then(() => {
  createMenu();
  registerIpc();
  createWindow();
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});

app.on("activate", () => {
  if (BrowserWindow.getAllWindows().length === 0) createWindow();
});

function registerIpc() {
  ipcMain.handle("workspace:load", async (_event, workspaceArg) => {
    const workspace = resolveWorkspace(workspaceArg);
    return loadWorkspace(workspace);
  });

  ipcMain.handle("workspace:choose", async () => {
    const result = await dialog.showOpenDialog(mainWindow, {
      properties: ["openDirectory"],
      title: "选择 Agent Firewall 工作区"
    });
    if (result.canceled || result.filePaths.length === 0) return null;
    return loadWorkspace(result.filePaths[0]);
  });

  ipcMain.handle("flow:save", async (_event, payload) => {
    const workspace = path.resolve(payload.workspace);
    return saveFlow(workspace, payload.flow);
  });

  ipcMain.handle("config:save", async (_event, payload) => {
    const workspace = path.resolve(payload.workspace);
    return saveConfig(workspace, payload.config);
  });

  ipcMain.handle("test-case:save", async (_event, payload) =>
    saveTestCase(path.resolve(payload.workspace), payload.testCase));
  ipcMain.handle("test-case:run", async (_event, payload) =>
    runTestCase(path.resolve(payload.workspace), payload.testCaseId, payload.baselineRunId, payload.approved));
  ipcMain.handle("flow:preflight", async (_event, payload) =>
    preflightFlow(path.resolve(payload.workspace), payload.flow));
  ipcMain.handle("mcp:discover", async (_event, payload) =>
    discoverMcpTools(path.resolve(payload.workspace), payload.agent, payload.server));
  ipcMain.handle("run:compare", async (_event, payload) =>
    compareRuns(path.resolve(payload.workspace), payload.baseline, payload.candidate));
  ipcMain.handle("revision:create", async (_event, payload) =>
    createRevision(path.resolve(payload.workspace), payload.revision));
  ipcMain.handle("revision:apply", async (_event, payload) =>
    applyRevision(path.resolve(payload.workspace), payload.revisionId));
  ipcMain.handle("revision:revert", async (_event, payload) =>
    revertRevision(path.resolve(payload.workspace), payload.revisionId));

  ipcMain.handle("flow:start", async (_event, payload) => {
    const workspace = path.resolve(payload.workspace);
    return saveAndStartFlow(workspace, payload.flow);
  });

  ipcMain.handle("flow:resume", async (_event, payload) => {
    const workspace = path.resolve(payload.workspace);
    return resumeFlow(workspace, payload.runId, payload.correction);
  });
}

function createMenu() {
  const template = [
    {
      label: "文件",
      submenu: [
        { role: "quit", label: "退出" }
      ]
    },
    {
      label: "编辑",
      submenu: [
        { role: "undo", label: "撤销" },
        { role: "redo", label: "重做" },
        { type: "separator" },
        { role: "cut", label: "剪切" },
        { role: "copy", label: "复制" },
        { role: "paste", label: "粘贴" },
        { role: "selectAll", label: "全选" }
      ]
    },
    {
      label: "视图",
      submenu: [
        { role: "reload", label: "重新加载" },
        { role: "toggleDevTools", label: "开发者工具" },
        { type: "separator" },
        { role: "resetZoom", label: "重置缩放" },
        { role: "zoomIn", label: "放大" },
        { role: "zoomOut", label: "缩小" },
        { role: "togglefullscreen", label: "全屏" }
      ]
    },
    {
      label: "窗口",
      submenu: [
        { role: "minimize", label: "最小化" },
        { role: "close", label: "关闭" }
      ]
    },
    {
      label: "帮助",
      submenu: [
        {
          label: "关于 Agent Firewall",
          click: () => {
            dialog.showMessageBox(mainWindow, {
              type: "info",
              title: "关于 Agent Firewall",
              message: "Agent Firewall",
              detail: "用于展示、编排并启动 agent / skills / MCP 的桌面应用。"
            });
          }
        }
      ]
    }
  ];
  Menu.setApplicationMenu(Menu.buildFromTemplate(template));
}
