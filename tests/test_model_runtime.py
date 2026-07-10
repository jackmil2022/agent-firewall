import os
from pathlib import Path

import pytest

from agent_firewall.config import ConfigError, load_config, write_default_config
from agent_firewall.engine import _resolve_model
from agent_firewall.store import AgentFirewallStore


def _model_config(tmp_path: Path, **model):
    write_default_config(tmp_path)
    store = AgentFirewallStore(tmp_path)
    data = store.get_config()
    data["models"]["work"] = {
        "provider": "openai",
        "model": "openai:gpt-5",
        "base_url": "https://models.example/v1",
        "api_key_env": "WORK_API_KEY",
        "enabled": True,
        "params": {"temperature": 0.1, "max_tokens": 321},
        **model,
    }
    data["agents"]["default"]["model"] = "work"
    store.save_config(data)
    return load_config(workspace=tmp_path)


def test_resolve_model_builds_configured_chat_model(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = _model_config(tmp_path)
    monkeypatch.setenv("WORK_API_KEY", "secret")
    captured = {}

    class FakeChatModel:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr("langchain_openai.ChatOpenAI", FakeChatModel)

    _resolve_model("work", config)

    assert captured == {
        "model": "gpt-5",
        "base_url": "https://models.example/v1",
        "api_key": "secret",
        "temperature": 0.1,
        "max_tokens": 321,
    }


def test_resolve_model_rejects_disabled_preset(tmp_path: Path) -> None:
    config = _model_config(tmp_path, enabled=False)

    with pytest.raises(ConfigError, match="disabled"):
        _resolve_model("work", config)


def test_resolve_model_reports_missing_api_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = _model_config(tmp_path)
    monkeypatch.delenv("WORK_API_KEY", raising=False)

    with pytest.raises(ConfigError, match="WORK_API_KEY"):
        _resolve_model("work", config)
