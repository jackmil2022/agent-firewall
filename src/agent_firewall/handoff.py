from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

StepStatus = Literal["success", "failed", "needs_input", "blocked"]


@dataclass(frozen=True)
class Handoff:
    run_id: str
    goal: str
    from_node: str
    to_node: str | None
    summary: str
    decisions: list[str] = field(default_factory=list)
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    next_input: str = ""
    open_questions: list[str] = field(default_factory=list)
    status: StepStatus = "success"

    def to_mapping(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "goal": self.goal,
            "from_node": self.from_node,
            "to_node": self.to_node,
            "summary": self.summary,
            "decisions": self.decisions,
            "artifacts": self.artifacts,
            "next_input": self.next_input,
            "open_questions": self.open_questions,
            "status": self.status,
        }


@dataclass(frozen=True)
class StepResult:
    status: StepStatus
    summary: str
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    handoff: dict[str, Any] = field(default_factory=dict)

    def to_mapping(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "summary": self.summary,
            "artifacts": self.artifacts,
            "handoff": self.handoff,
        }


@dataclass(frozen=True)
class TaskPacket:
    run_id: str
    goal: str
    node_id: str
    incoming: list[dict[str, Any]] = field(default_factory=list)

    def prompt(self) -> str:
        parts = [f"Goal:\n{self.goal}"]
        if self.incoming:
            parts.append("Incoming handoffs:")
            parts.extend(str(item) for item in self.incoming)
        return "\n\n".join(parts)
