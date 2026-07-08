const { spawn } = require("child_process");
const fs = require("fs/promises");
const path = require("path");

async function loadWorkspace(workspace) {
  const configPath = path.join(workspace, ".agent-firewall", "config.json");
  const flowPath = path.join(workspace, ".agent-firewall", "flow.json");
  const config = await readJson(configPath);
  const skills = await readSkills(path.join(workspace, ".agent-firewall", "skills"));
  const agents = Object.entries(config.agents || {}).map(([key, value]) => ({
    key,
    name: value.name || key,
    model: value.model || "",
    systemPrompt: value.system_prompt || "",
    tools: value.tools || [],
    skills: value.skills || [],
    subagents: value.subagents || [],
    mcpServers: value.mcp_servers || {}
  }));
  const activeAgent = config.active_agent || (agents[0] && agents[0].key) || "";
  const flow = await readOptionalJson(flowPath);
  return {
    workspace,
    configPath,
    activeAgent,
    acp: config.acp || {},
    agents,
    skills,
    mcpServers: collectMcpServers(agents),
    flow: flow || defaultFlow(agents, skills)
  };
}

async function saveFlow(workspace, flow) {
  assertInsideWorkspace(workspace, workspace);
  const target = path.join(workspace, ".agent-firewall", "flow.json");
  await fs.mkdir(path.dirname(target), { recursive: true });
  await fs.writeFile(target, JSON.stringify(flow, null, 2), "utf8");
  return { ok: true, path: target };
}

async function saveAndStartFlow(workspace, flow) {
  const saved = await saveFlow(workspace, flow);
  const started = await startFlow(workspace, saved.path);
  return { ...started, flowPath: saved.path };
}

function startFlow(workspace, flowPath) {
  return new Promise((resolve) => {
    const startedAt = new Date().toISOString();
    const child = spawn("python", ["-m", "agent_firewall", "agent"], {
      cwd: workspace,
      env: { ...process.env, AGENT_FIREWALL_FLOW: flowPath },
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
        command: "python -m agent_firewall agent",
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
        command: "python -m agent_firewall agent",
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
        command: "python -m agent_firewall agent",
        stdout: stdout.trim(),
        stderr: stderr.trim()
      });
    });
  });
}

async function readJson(filePath) {
  const text = await fs.readFile(filePath, "utf8");
  return JSON.parse(text);
}

async function readOptionalJson(filePath) {
  try {
    return await readJson(filePath);
  } catch (error) {
    if (error.code === "ENOENT") return null;
    throw error;
  }
}

async function readSkills(skillsRoot) {
  let entries = [];
  try {
    entries = await fs.readdir(skillsRoot, { withFileTypes: true });
  } catch (error) {
    if (error.code === "ENOENT") return [];
    throw error;
  }
  const skills = [];
  for (const entry of entries) {
    if (!entry.isDirectory()) continue;
    const skillPath = path.join(skillsRoot, entry.name);
    const skillMd = path.join(skillPath, "SKILL.md");
    try {
      const text = await fs.readFile(skillMd, "utf8");
      const manifest = parseFrontmatter(text);
      skills.push({
        id: entry.name,
        name: manifest.name || entry.name,
        description: manifest.description || "",
        path: skillPath
      });
    } catch (error) {
      if (error.code !== "ENOENT") throw error;
    }
  }
  return skills;
}

function parseFrontmatter(text) {
  const lines = text.split(/\r?\n/);
  if (lines[0] !== "---") return {};
  const manifest = {};
  for (let i = 1; i < lines.length; i += 1) {
    const line = lines[i];
    if (line === "---") break;
    const separator = line.indexOf(":");
    if (separator === -1) continue;
    const key = line.slice(0, separator).trim();
    const value = line.slice(separator + 1).trim().replace(/^"|"$/g, "");
    manifest[key] = value;
  }
  return manifest;
}

function collectMcpServers(agents) {
  return agents.flatMap((agent) =>
    Object.entries(agent.mcpServers).map(([key, value]) => ({
      id: `${agent.key}:${key}`,
      key,
      agent: agent.key,
      config: value
    }))
  );
}

function defaultFlow(agents, skills) {
  const nodes = [];
  const edges = [];
  agents.forEach((agent, index) => {
    nodes.push({
      id: `agent:${agent.key}`,
      type: "agent",
      label: agent.name,
      x: 360,
      y: 120 + index * 145,
      meta: { model: agent.model, key: agent.key }
    });
  });
  skills.slice(0, 4).forEach((skill, index) => {
    const id = `skill:${skill.id}`;
    nodes.push({
      id,
      type: "skill",
      label: skill.name,
      x: 720,
      y: 120 + index * 130,
      meta: { path: skill.path }
    });
    if (agents[0]) edges.push({ from: `agent:${agents[0].key}`, to: id });
  });
  return { nodes, edges, updatedAt: new Date().toISOString() };
}

function assertInsideWorkspace(workspace, target) {
  const relative = path.relative(workspace, target);
  if (relative.startsWith("..") || path.isAbsolute(relative)) {
    throw new Error("target must stay inside workspace");
  }
}

module.exports = {
  loadWorkspace,
  saveFlow,
  saveAndStartFlow,
  startFlow,
  defaultFlow
};
