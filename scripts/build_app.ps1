param(
  [string]$Name = "agent-firewall"
)

python -m pip install -e ".[app]"
python -m PyInstaller --name $Name --onefile --paths src --collect-all agent_firewall --collect-all playwright scripts/agent_firewall_entry.py
