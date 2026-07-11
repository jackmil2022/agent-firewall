import sys
from pathlib import Path

from agent_firewall.runner import _script_command


def test_skill_script_uses_internal_runner_when_runtime_is_frozen(tmp_path: Path, monkeypatch) -> None:
    script = tmp_path / "echo.py"
    monkeypatch.setattr("agent_firewall.runner.sys.frozen", True, raising=False)

    command = _script_command(script)

    assert command == [sys.executable, "_script-run", "--file", str(script)]


def test_skill_script_uses_python_in_development(tmp_path: Path, monkeypatch) -> None:
    script = tmp_path / "echo.py"
    monkeypatch.delattr("agent_firewall.runner.sys.frozen", raising=False)

    assert _script_command(script) == [sys.executable, str(script)]
