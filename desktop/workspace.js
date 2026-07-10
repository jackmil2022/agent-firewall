const { spawn } = require("child_process");
const fs = require("fs");
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
  await saveFlow(workspace, flow);
  return startFlow(workspace);
}

function startFlow(workspace) {
  return runFlowCommand(workspace, ["-m", "agent_firewall", "run"]);
}

function resumeFlow(workspace, runId, correction = "") {
  return runFlowCommand(workspace, [
    "-m",
    "agent_firewall",
    "resume",
    "--run-id",
    runId,
    "--correction",
    correction
  ]);
}

function runFlowCommand(workspace, args) {
  return new Promise((resolve) => {
    const startedAt = new Date().toISOString();
    const python = pythonCommand(workspace);
    const child = spawn(python, args, {
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
        command: `${python} ${args.join(" ")}`,
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
        command: `${python} ${args.join(" ")}`,
        stdout,
        stderr: error.message
      });
    });
    child.on("close", (code) => {
      clearTimeout(timeout);
      let run = null;
      try {
        run = JSON.parse(stdout);
      } catch {
        run = null;
      }
      resolve({
        ok: run?.status === "success",
        status: run?.status || (code === 0 ? "success" : "failed"),
        code,
        startedAt,
        finishedAt: new Date().toISOString(),
        command: `${python} ${args.join(" ")}`,
        stdout: stdout.trim(),
        stderr: stderr.trim(),
        run
      });
    });
  });
}

function runPythonJson(workspace, args, stdin) {
  return new Promise((resolve, reject) => {
    const child = spawn(pythonCommand(workspace), args, {
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

function pythonCommand(workspace) {
  if (process.env.PYTHON) return process.env.PYTHON;
  const local = process.platform === "win32"
    ? path.join(workspace, ".venv", "Scripts", "python.exe")
    : path.join(workspace, ".venv", "bin", "python");
  if (fs.existsSync(local)) return local;
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
  startFlow,
  resumeFlow
};
