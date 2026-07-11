#!/usr/bin/env bash
set -euo pipefail

NAME="${1:-agent-firewall}"
if [[ -n "${PYTHON:-}" ]]; then
  PYTHON_BIN="$PYTHON"
elif [[ -x .venv/bin/python ]]; then
  PYTHON_BIN=.venv/bin/python
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN=python3
else
  PYTHON_BIN=python
fi

if ! "$PYTHON_BIN" -m pip --version >/dev/null 2>&1; then
  "$PYTHON_BIN" -m ensurepip --upgrade
fi
"$PYTHON_BIN" -m pip install -e ".[app]"
"$PYTHON_BIN" -m PyInstaller --name "$NAME" --onefile --paths src --collect-all agent_firewall --collect-all playwright scripts/agent_firewall_entry.py
