from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence


@dataclass
class ToolCallSpec:
    tool: str
    arguments: Dict[str, Any]
    justification: str
    tags: List[str] = field(default_factory=list)
    budget: Optional[Dict[str, Any]] = None

    def to_json(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "tool": self.tool,
            "arguments": self.arguments,
            "justification": self.justification,
        }
        if self.tags:
            payload["tags"] = self.tags
        if self.budget is not None:
            payload["budget"] = self.budget
        return payload


@dataclass
class ToolExecution:
    tool: str
    arguments: Dict[str, Any]
    status: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    justification: Optional[str] = None

    def to_json(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "tool": self.tool,
            "arguments": self.arguments,
            "status": self.status,
        }
        if self.result is not None:
            payload["result"] = self.result
        if self.error is not None:
            payload["error"] = self.error
        if self.justification is not None:
            payload["justification"] = self.justification
        return payload


@dataclass
class GatherOutput:
    tool_calls: Sequence[ToolCallSpec]
    notes: Optional[str] = None

    def to_json(self) -> Dict[str, Any]:
        payload = {
            "tool_calls": [tool_call.to_json() for tool_call in self.tool_calls],
        }
        if self.notes:
            payload["notes"] = self.notes
        return payload


@dataclass
class GatherResults:
    executions: Sequence[ToolExecution]
    notes: Optional[str] = None

    def to_json(self) -> Dict[str, Any]:
        payload = {
            "executions": [execution.to_json() for execution in self.executions],
        }
        if self.notes:
            payload["notes"] = self.notes
        return payload


@dataclass
class PlanStep:
    action: str
    description: str
    payload: Dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> Dict[str, Any]:
        payload = {
            "action": self.action,
            "description": self.description,
        }
        if self.payload:
            payload["payload"] = self.payload
        return payload


@dataclass
class PlanOutput:
    steps: Sequence[PlanStep]
    summary: Optional[str] = None

    def to_json(self) -> Dict[str, Any]:
        payload = {
            "steps": [step.to_json() for step in self.steps],
        }
        if self.summary:
            payload["summary"] = self.summary
        return payload


@dataclass
class NarrationOutput:
    ic: str
    commit_ops: Sequence[Dict[str, Any]] = field(default_factory=list)
    recap: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> Dict[str, Any]:
        return {
            "ic": self.ic,
            "ooc": {
                "commit_ops": list(self.commit_ops),
                "recap": self.recap or "",
                **self.metadata,
            },
        }


@dataclass
class HistoryTurn:
    role: str  # "player" or "dm"
    payload: Dict[str, Any]


@dataclass
class HistorySummary:
    summary: str
    turns: List[HistoryTurn] = field(default_factory=list)

