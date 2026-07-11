import os
from pathlib import Path

import pytest

from agent_firewall.config import ConfigError, load_config, write_default_config
from agent_firewall.engine import _resolve_model, probe_model_connection
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
        "use_responses_api": False,
    }


def test_resolve_model_honors_openai_provider_with_unprefixed_model(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _model_config(tmp_path, model="gpt-5")
    monkeypatch.setenv("WORK_API_KEY", "secret")
    captured = {}

    class FakeChatModel:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr("langchain_openai.ChatOpenAI", FakeChatModel)

    _resolve_model("work", config)

    assert captured["model"] == "gpt-5"
    assert captured["base_url"] == "https://models.example/v1"
    assert captured["api_key"] == "secret"
    assert captured["temperature"] == 0.1


def test_resolve_model_uses_configured_non_openai_provider(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _model_config(
        tmp_path,
        provider="anthropic",
        model="claude-sonnet-4-5",
        base_url="https://models.example/v1",
    )
    monkeypatch.setenv("WORK_API_KEY", "secret")
    captured = {}

    def fake_init_chat_model(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr("langchain.chat_models.init_chat_model", fake_init_chat_model)

    _resolve_model("work", config)

    assert captured == {
        "model": "claude-sonnet-4-5",
        "model_provider": "anthropic",
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


def test_resolve_model_prefers_plaintext_api_key_over_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _model_config(tmp_path, api_key="stored-secret")
    monkeypatch.setenv("WORK_API_KEY", "environment-secret")
    captured = {}

    class FakeChatModel:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr("langchain_openai.ChatOpenAI", FakeChatModel)

    _resolve_model("work", config)

    assert captured["api_key"] == "stored-secret"


def test_model_connection_invokes_the_global_model(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = _model_config(tmp_path, provider="fake", base_url="")
    captured = {}

    class FakeModel:
        def invoke(self, prompt):
            captured["prompt"] = prompt
            return type("Response", (), {"content": "OK"})()

    monkeypatch.setattr("agent_firewall.engine._resolve_model", lambda model, current: FakeModel())

    assert probe_model_connection(config) == {"ok": True, "model": "work", "response": "OK"}
    assert captured["prompt"] == "Reply with exactly: OK"
