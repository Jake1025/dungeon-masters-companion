from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping, Optional

from .adapter import LLMAdapter
from .schemas import GatherOutput, ToolCallSpec


GATHER_PROMPT = (
    "You are the Gather stage of a TTRPG orchestrator. "
    "Given the conversation context, game state, and the latest player input, "
    "list every tool call required before narration. "
    "Do not execute tools. Return JSON {\"tool_calls\": [...], \"justification\": \"...\", \"notes\": \"optional\"}. "
    "Only request tools you truly need."
)


class Gatherer:
    """Produces the list of tool invocations required for the upcoming turn."""

    def __init__(
        self,
        adapter: LLMAdapter,
        tools_catalog: Iterable[Mapping[str, Any]],
        *,
        max_calls: int = 8,
    ) -> None:
        self.adapter = adapter
        self.tools_catalog = list(tools_catalog)
        self.max_calls = max_calls

    def gather(
        self,
        *,
        history_context: Dict[str, Any],
        game_state: Dict[str, Any],
        player_input: str,
    ) -> GatherOutput:
        payload = {
            "tools": self.tools_catalog,
            "conversation": history_context,
            "game_state": game_state,
            "player_input": player_input,
        }
        raw = self.adapter.request_json(
            "gather",
            GATHER_PROMPT,
            payload,
            validator=self._validate_response,
        )
        calls = [
            ToolCallSpec(
                tool=item["tool"],
                arguments=item.get("arguments", {}),
                justification=item["justification"],
                tags=item.get("tags", []),
                budget=item.get("budget"),
            )
            for item in raw["tool_calls"][: self.max_calls]
        ]
        notes = raw.get("notes")
        return GatherOutput(tool_calls=calls, notes=notes)

    @staticmethod
    def _validate_response(payload: Dict[str, Any]) -> None:
        if not isinstance(payload, dict):
            raise TypeError("Gather response must be an object")
        tool_calls = payload.get("tool_calls")
        if not isinstance(tool_calls, list):
            raise ValueError("Gather response must include 'tool_calls'")
        for call in tool_calls:
            if not isinstance(call, dict):
                raise ValueError("Each tool call must be an object")
            if "tool" not in call or "justification" not in call:
                raise ValueError("Tool calls require 'tool' and 'justification'")
            if not isinstance(call.get("arguments", {}), dict):
                raise ValueError("Tool call 'arguments' must be an object if provided")


__all__ = ["Gatherer"]
