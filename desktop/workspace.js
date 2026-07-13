const { spawn } = require("child_process");
const fs = require("fs");
const path = require("path");

const activeOperations = new Map();

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

async function testModelConnection(workspace) {
  return runPythonJson(workspace, ["-m", "agent_firewall", "model-test"]);
}

async function saveTestCase(workspace, testCase) {
  return runPythonJson(workspace, ["-m", "agent_firewall", "test-case-save"], JSON.stringify(testCase));
}

async function setTestBaseline(workspace, testCaseId, runId) {
  return runPythonJson(workspace, [
    "-m", "agent_firewall", "test-case-baseline-set",
    "--id", String(testCaseId),
    "--run-id", runId
  ]);
}

async function runTestCase(workspace, testCaseId, baselineRunId = "", approved = false, operationId = "", revisionId = "") {
  const args = ["-m", "agent_firewall", "test-case-run", "--id", String(testCaseId)];
  if (operationId) args.push("--run-id", operationId);
  if (baselineRunId) args.push("--baseline-run-id", baselineRunId);
  if (revisionId) args.push("--revision-id", String(revisionId));
  if (approved) args.push("--approved");
  return runPythonJsonResult(workspace, args, undefined, operationId);
}

async function preflightFlow(workspace, flow) {
  return runPythonJsonResult(workspace, ["-m", "agent_firewall", "flow-preflight"], JSON.stringify(flow));
}

async function discoverMcpTools(workspace, agent, server, approved = false) {
  const args = ["-m", "agent_firewall", "mcp-tools", "--agent", agent, "--server", server];
  if (approved) args.push("--approved");
  return runPythonJson(workspace, args);
}

async function importLocalCapability(workspace, source) {
  return runPythonJson(workspace, ["-m", "agent_firewall", "capability-import-local", "--source", source]);
}

async function compareRuns(workspace, baseline, candidate) {
  return runPythonJson(workspace, ["-m", "agent_firewall", "run-compare", "--baseline", baseline, "--candidate", candidate]);
}

async function getRunDetails(workspace, runId) {
  return runPythonJson(workspace, ["-m", "agent_firewall", "run-json", "--run-id", runId]);
}

async function createRevision(workspace, revision) {
  return runPythonJson(workspace, ["-m", "agent_firewall", "revision-create"], JSON.stringify(revision));
}

async function applyRevision(workspace, revisionId) {
  return runPythonJson(workspace, ["-m", "agent_firewall", "revision-apply", "--id", String(revisionId)]);
}

async function reviewRevision(workspace, revisionId, comparisonId) {
  return runPythonJson(workspace, [
    "-m", "agent_firewall", "revision-review",
    "--id", String(revisionId),
    "--comparison-id", String(comparisonId)
  ]);
}

async function revertRevision(workspace, revisionId) {
  return runPythonJson(workspace, ["-m", "agent_firewall", "revision-revert", "--id", String(revisionId)]);
}

async function saveAndStartFlow(workspace, flow, goal = "", operationId = "") {
  await saveFlow(workspace, flow);
  return startFlow(workspace, goal, operationId);
}

function startFlow(workspace, goal = "", operationId = "") {
  return runFlowCommand(workspace, flowRunArgs(goal, operationId), operationId);
}

function flowRunArgs(goal = "", operationId = "") {
  const args = ["-m", "agent_firewall", "run"];
  if (goal) args.push("--goal", goal);
  if (operationId) args.push("--run-id", operationId);
  return args;
}

function resumeFlow(workspace, runId, correction = "", operationId = "") {
  return runFlowCommand(workspace, [
    "-m",
    "agent_firewall",
    "resume",
    "--run-id",
    runId,
    "--correction",
    correction
  ], operationId);
}

async function cancelOperation(workspace, operationId) {
  const operation = activeOperations.get(operationId);
  if (!operation) {
    await cancelPersistedRun(workspace, operationId);
    return true;
  }
  operation.cancelled = true;
  operation.cancelPromise = cancelPersistedRun(operation.workspace, operationId);
  operation.child.kill();
  await operation.cancelPromise;
  return true;
}

async function cancelPersistedRun(workspace, runId) {
  let lastError;
  for (let attempt = 0; attempt < 4; attempt += 1) {
    try {
      return await runPythonJson(workspace, ["-m", "agent_firewall", "run-cancel", "--run-id", runId]);
    } catch (error) {
      lastError = error;
      await new Promise((resolve) => setTimeout(resolve, 100));
    }
  }
  throw lastError;
}

function runFlowCommand(workspace, args, operationId = "") {
  return new Promise((resolve) => {
    const startedAt = new Date().toISOString();
    const python = pythonCommand(workspace);
    const launchArgs = backendArgs(python, args);
    const child = spawn(python, launchArgs, {
      cwd: workspace,
      env: { ...process.env },
      windowsHide: true
    });
    const operation = trackOperation(operationId, child, workspace);

    let stdout = "";
    let stderr = "";
    const timeout = setTimeout(async () => {
      forgetOperation(operationId, child);
      child.kill();
      if (operationId) {
        try {
          await cancelPersistedRun(workspace, operationId);
        } catch {
          // The timeout result remains visible even if the run row disappeared.
        }
      }
      resolve({
        ok: false,
        status: "timeout",
        startedAt,
        command: `${python} ${launchArgs.join(" ")}`,
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
      forgetOperation(operationId, child);
      resolve({
        ok: false,
        status: "error",
        startedAt,
        command: `${python} ${launchArgs.join(" ")}`,
        stdout,
        stderr: error.message
      });
    });
    child.on("close", async (code) => {
      clearTimeout(timeout);
      forgetOperation(operationId, child);
      if (operation?.cancelled) {
        try {
          await operation.cancelPromise;
        } catch {
          // The cancel IPC reports persistence failures to the renderer.
        }
        resolve({
          ok: false,
          status: "cancelled",
          code,
          startedAt,
          finishedAt: new Date().toISOString(),
          command: `${python} ${launchArgs.join(" ")}`,
          stdout: stdout.trim(),
          stderr: stderr.trim(),
          run: null
        });
        return;
      }
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
        command: `${python} ${launchArgs.join(" ")}`,
        stdout: stdout.trim(),
        stderr: stderr.trim(),
        run
      });
    });
  });
}

function runPythonJson(workspace, args, stdin) {
  return new Promise((resolve, reject) => {
    const command = pythonCommand(workspace);
    const child = spawn(command, backendArgs(command, args), {
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

function runPythonJsonResult(workspace, args, stdin, operationId = "") {
  return new Promise((resolve, reject) => {
    const command = pythonCommand(workspace);
    const child = spawn(command, backendArgs(command, args), { cwd: workspace, env: { ...process.env }, windowsHide: true });
    const operation = trackOperation(operationId, child, workspace);
    let stdout = "";
    let stderr = "";
    child.stdout.on("data", (chunk) => { stdout += chunk.toString(); });
    child.stderr.on("data", (chunk) => { stderr += chunk.toString(); });
    child.on("error", (error) => {
      forgetOperation(operationId, child);
      reject(error);
    });
    child.on("close", async () => {
      forgetOperation(operationId, child);
      if (operation?.cancelled) {
        try {
          await operation.cancelPromise;
        } catch {
          // The cancel IPC reports persistence failures to the renderer.
        }
        resolve({ status: "cancelled", cancelled: true, events: [] });
        return;
      }
      try {
        resolve(JSON.parse(stdout));
      } catch (error) {
        reject(new Error(stderr.trim() || `invalid json from python: ${error.message}`));
      }
    });
    if (stdin) child.stdin.write(stdin);
    child.stdin.end();
  });
}

function trackOperation(operationId, child, workspace) {
  if (!operationId) return null;
  const operation = { child, workspace, cancelled: false };
  activeOperations.set(operationId, operation);
  return operation;
}

function forgetOperation(operationId, child) {
  if (activeOperations.get(operationId)?.child === child) activeOperations.delete(operationId);
}

function pythonCommand(workspace) {
  const packaged = process.resourcesPath && path.join(
    process.resourcesPath,
    "backend",
    process.platform === "win32" ? "agent-firewall.exe" : "agent-firewall"
  );
  if (packaged && fs.existsSync(packaged)) return packaged;
  if (process.env.PYTHON) return process.env.PYTHON;
  const development = process.platform === "win32"
    ? path.resolve(__dirname, "..", ".venv", "Scripts", "python.exe")
    : path.resolve(__dirname, "..", ".venv", "bin", "python");
  if (fs.existsSync(development)) return development;
  const local = process.platform === "win32"
    ? path.join(workspace, ".venv", "Scripts", "python.exe")
    : path.join(workspace, ".venv", "bin", "python");
  if (fs.existsSync(local)) return local;
  return process.platform === "win32" ? "python" : "python3";
}

function backendArgs(command, args) {
  const name = String(command).split(/[\\/]/).pop();
  return /^agent-firewall(?:\.exe)?$/i.test(name) ? args.slice(2) : args;
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
  testModelConnection,
  saveTestCase,
  setTestBaseline,
  runTestCase,
  preflightFlow,
  discoverMcpTools,
  importLocalCapability,
  compareRuns,
  getRunDetails,
  createRevision,
  reviewRevision,
  applyRevision,
  revertRevision,
  saveFlow,
  saveAndStartFlow,
  startFlow,
  resumeFlow,
  cancelOperation,
  backendArgs,
  flowRunArgs,
  pythonCommand
};
