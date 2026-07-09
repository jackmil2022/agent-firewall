# agent-firewall

Cross-platform deepagents app shell for guarded, skill-aware agents.

## What is included

- Deepagents engine wrapper with configurable agents and subagents.
- SQLite-backed config, flow, run, and event storage under `.agent-firewall/agent-firewall.sqlite3`.
- Project-local skills initialized under `.agent-firewall/skills`.
- MCP tool loading through `langchain-mcp-adapters`.
- ACP serving through `deepagents-acp`, including an optional flow-runner endpoint.
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

Create the configured deep agent. The default `fake:echo` model works without API keys for self-tests; update the SQLite config to use a provider model such as `openai:gpt-5` for real LLM use.

```bash
agent-firewall agent
```

Run the configured flow. Each run and node event is stored in SQLite.

```bash
agent-firewall run --goal "Inspect this workspace and hand off to the right skill"
```

Serve over ACP stdio:

```bash
agent-firewall acp
```

Serve the SQLite-backed flow runner over ACP stdio:

```bash
agent-firewall acp --runner
```

## Customize agents, skills, MCP, and ACP

Configuration and flows are stored in `.agent-firewall/agent-firewall.sqlite3` after running `agent-firewall init`.

Export, edit, and save config JSON:

```bash
agent-firewall config-export --output config.json
agent-firewall config-save --file config.json
```

- Add custom agents under `agents`.
- Set `active_agent` to choose the default agent.
- Add shared model presets under `models`; agents reference a model preset by name through their `model` field. Model presets keep `provider`, `model`, `base_url`, `api_key_env`, `enabled`, and optional `params`.
- Add skill directories through each agent's `skills` list.
- Add MCP servers under each agent's `mcp_servers`.
- Configure ACP stdio options under `acp`.

For automation, save a flow JSON document to SQLite:

```bash
cat flow.json | agent-firewall flow-save
```

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
