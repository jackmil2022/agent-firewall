const { spawn } = require("child_process");
const path = require("path");

async function loadWorkspace(workspace) {
  return runPythonJson(workspace, ["-m", "agent_firewall", "workspace-json"]);
}

async function saveFlow(workspace, flow) {
  assertInsideWorkspace(workspace, workspace);
  return runPythonJson(workspace, ["-m", "agent_firewall", "flow-save"], JSON.stringify(flow));
}

async function saveConfig(workspace, config) {
  assertInsideWorkspace(workspace, workspace);
  return runPythonJson(workspace, ["-m", "agent_firewall", "config-save"], JSON.stringify(config));
}

async function saveAndStartFlow(workspace, flow) {
  const saved = await saveFlow(workspace, flow);
  const started = await startFlow(workspace, saved.path);
  return { ...started, flowPath: saved.path };
}

function startFlow(workspace, flowPath) {
  return new Promise((resolve) => {
    const startedAt = new Date().toISOString();
    const child = spawn(pythonCommand(), ["-m", "agent_firewall", "run"], {
      cwd: workspace,
      env: { ...process.env },
      windowsHide: true
    });

    let stdout = "";
    let stderr = "";
    const timeout = setTimeout(() => {
      child.kill();
      resolve({
        ok: false,
        status: "timeout",
        startedAt,
        command: `${pythonCommand()} -m agent_firewall run`,
        stdout,
        stderr: `${stderr}\nTimed out after 60 seconds.`.trim()
      });
    }, 60000);

    child.stdout.on("data", (chunk) => {
      stdout += chunk.toString();
    });
    child.stderr.on("data", (chunk) => {
      stderr += chunk.toString();
    });
    child.on("error", (error) => {
      clearTimeout(timeout);
      resolve({
        ok: false,
        status: "error",
        startedAt,
        command: `${pythonCommand()} -m agent_firewall run`,
        stdout,
        stderr: error.message
      });
    });
    child.on("close", (code) => {
      clearTimeout(timeout);
      resolve({
        ok: code === 0,
        status: code === 0 ? "started" : "failed",
        code,
        startedAt,
        finishedAt: new Date().toISOString(),
        command: `${pythonCommand()} -m agent_firewall run`,
        stdout: stdout.trim(),
        stderr: stderr.trim()
      });
    });
  });
}

function runPythonJson(workspace, args, stdin) {
  return new Promise((resolve, reject) => {
    const child = spawn(pythonCommand(), args, {
      cwd: workspace,
      env: { ...process.env },
      windowsHide: true
    });
    let stdout = "";
    let stderr = "";
    child.stdout.on("data", (chunk) => {
      stdout += chunk.toString();
    });
    child.stderr.on("data", (chunk) => {
      stderr += chunk.toString();
    });
    child.on("error", reject);
    child.on("close", (code) => {
      if (code !== 0) {
        reject(new Error(stderr.trim() || `python exited with ${code}`));
        return;
      }
      try {
        resolve(JSON.parse(stdout));
      } catch (error) {
        reject(new Error(`invalid json from python: ${error.message}\n${stdout}`));
      }
    });
    if (stdin) child.stdin.write(stdin);
    child.stdin.end();
  });
}

function pythonCommand() {
  if (process.env.PYTHON) return process.env.PYTHON;
  return process.platform === "win32" ? "python" : "python3";
}

function assertInsideWorkspace(workspace, target) {
  const relative = path.relative(workspace, target);
  if (relative.startsWith("..") || path.isAbsolute(relative)) {
    throw new Error("target must stay inside workspace");
  }
}

module.exports = {
  loadWorkspace,
  saveConfig,
  saveFlow,
  saveAndStartFlow,
  startFlow
};
