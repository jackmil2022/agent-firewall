from __future__ import annotations

from typing import Any

from langchain_core.language_models.chat_models import SimpleChatModel


class EchoChatModel(SimpleChatModel):
    """Tiny tool-bindable chat model for local deepagents smoke tests."""

    @property
    def _llm_type(self) -> str:
        return "agent-firewall-echo"

    def _call(self, messages: list[Any], stop: list[str] | None = None, **kwargs: Any) -> str:
        return "Agent Firewall self-test response."

    def bind_tools(self, tools: Any, **kwargs: Any) -> "EchoChatModel":
        return self
