param(
  [string]$Name = "agent-firewall"
)

$Python = if ($env:PYTHON) {
  $env:PYTHON
} elseif (Test-Path ".venv\\Scripts\\python.exe") {
  ".venv\\Scripts\\python.exe"
} else {
  "python"
}

& $Python -m pip --version *> $null
if ($LASTEXITCODE -ne 0) {
  & $Python -m ensurepip --upgrade
}
& $Python -m pip install -e ".[app]"
& $Python -m PyInstaller --name $Name --onefile --paths src --collect-all agent_firewall --collect-all playwright scripts/agent_firewall_entry.py
