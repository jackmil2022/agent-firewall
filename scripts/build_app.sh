#!/usr/bin/env bash
set -euo pipefail

NAME="${1:-agent-firewall}"
python -m pip install -e ".[app]"
python -m PyInstaller --name "$NAME" --onefile --paths src --collect-all agent_firewall --collect-all playwright scripts/agent_firewall_entry.py
