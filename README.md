# agent-firewall

Cross-platform deepagents app shell for guarded, skill-aware agents.

## What is included

- Deepagents engine wrapper with configurable agents and subagents.
- Project-local skills initialized under `.agent-firewall/skills`.
- MCP tool loading through `langchain-mcp-adapters`.
- ACP serving through `deepagents-acp`.
- Browser-control and skill-creator skills bundled by default.
- PyInstaller scripts for Windows and macOS binaries.

## Quick start

```bash
pip install -e ".[dev,browser]"
agent-firewall init
agent-firewall doctor
agent-firewall skills
```

Run the browser-control smoke test:

```bash
python -m playwright install chromium
agent-firewall browser-smoke
```

Create the configured deep agent. The default `fake:echo` model works without API keys for self-tests; change `.agent-firewall/config.json` to a provider model such as `openai:gpt-5` for real LLM use.

```bash
agent-firewall agent
```

Serve over ACP stdio:

```bash
agent-firewall acp
```

## Customize agents, skills, MCP, and ACP

Edit `.agent-firewall/config.json` after running `agent-firewall init`.

- Add custom agents under `agents`.
- Set `active_agent` to choose the default agent.
- Add skill directories through each agent's `skills` list.
- Add MCP servers under each agent's `mcp_servers`.
- Configure ACP stdio options under `acp`.

## Build app binaries

Windows:

```powershell
.\scripts\build_app.ps1
```

macOS:

```bash
./scripts/build_app.sh
```

## Desktop visual orchestrator

The desktop UI is an Electron app under `desktop/`. It shows configured agents,
skills, MCP servers, ACP status, and a drag-and-drop flow canvas. The canvas is
auto-saved and can also be saved manually to `.agent-firewall/flow.json`.

Use **Start** in the desktop app to save the current flow and launch the
configured Agent Firewall agent in one click. Run output appears in the right
side Run panel.

```bash
cd desktop
npm install
npm start
```

Or from the repository root:

```powershell
.\scripts\start_desktop.ps1
```

```bash
./scripts/start_desktop.sh
```

Build desktop installers:

```bash
npm run build:win
npm run build:mac
```
