from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping, Optional

from .adapter import LLMAdapter
from .schemas import GatherOutput, ToolCallSpec


GATHER_PROMPT = (
    "You are the Gather stage of a TTRPG orchestrator. "
    "Given the conversation context, game state, and the latest player input, "
    "list every tool call required before narration. "
    "Do not execute tools. Return JSON {\"tool_calls\": [...], \"justification\": \"...\", \"notes\": \"optional\"}. "
    "Request any tools you may need."
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
        # Be tolerant of imperfect LLM JSON: avoid raising on minor schema drift.
        try:
            raw = self.adapter.request_json(
                "gather",
                GATHER_PROMPT,
                payload,
                validator=None,  # we'll normalize instead of hard-failing
            )
        except Exception:
            raw = {}

        tool_calls_raw = _get_list(raw, ["tool_calls", "calls", "tools", "toolCalls"]) or []
        calls: List[ToolCallSpec] = []
        for item in tool_calls_raw[: self.max_calls]:
            spec = self._coerce_tool_call(item)
            if spec is not None:
                calls.append(spec)
        notes = _get_str(raw, ["notes", "comment", "summary"]) or None
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

    # -- Helpers -----------------------------------------------------------------

    def _coerce_tool_call(self, item: Any) -> Optional[ToolCallSpec]:
        if not isinstance(item, dict):
            return None
        # Accept common synonyms
        tool_name = _get_str(item, ["tool", "name", "id", "tool_name"]) or ""
        tool_name = self._resolve_tool_name(tool_name)
        if not tool_name:
            return None
        arguments = item.get("arguments")
        if not isinstance(arguments, dict):
            arguments = item.get("args") if isinstance(item.get("args"), dict) else {}
            if not isinstance(arguments, dict):
                arguments = item.get("parameters") if isinstance(item.get("parameters"), dict) else {}
        justification = _get_str(item, ["justification", "why", "reason", "rationale", "explanation"]) or ""
        tags = item.get("tags")
        if not isinstance(tags, list):
            tags = []
        budget = item.get("budget")
        if isinstance(budget, (int, float)):
            budget = {"cost": int(budget)}
        elif not isinstance(budget, dict):
            # Accept "cost" at top-level as a budget shorthand
            cost = item.get("cost")
            budget = {"cost": int(cost)} if isinstance(cost, (int, float)) else None
        return ToolCallSpec(
            tool=tool_name,
            arguments=arguments,
            justification=justification,
            tags=tags,
            budget=budget,
        )

    def _resolve_tool_name(self, name: str) -> str:
        """Map loose tool identifiers to the catalog's canonical ids."""
        if not name:
            return ""
        name_norm = name.strip().lower().replace(" ", ".").replace("_", ".")
        catalog = {str(t.get("tool", "")).lower(): str(t.get("tool", "")) for t in self.tools_catalog}
        if name in catalog.values():
            return name
        # exact lower match
        if name_norm in catalog:
            return catalog[name_norm]
        # common aliases
        alias_map = {
            "dice": "dice.roll",
            "roll": "dice.roll",
            "roll.dice": "dice.roll",
            "dice.roll": "dice.roll",
            "world": "world.query",
            "query": "world.query",
            "world.query": "world.query",
            "rules": "rules.lookup",
            "lookup": "rules.lookup",
            "rules.lookup": "rules.lookup",
        }
        return alias_map.get(name_norm, name)


# Local tolerant extractors ------------------------------------------------------

def _get_list(obj: Any, keys: List[str]) -> Optional[List[Any]]:
    if not isinstance(obj, dict):
        return None
    for k in keys:
        v = obj.get(k)
        if isinstance(v, list):
            return v
    return None


def _get_str(obj: Any, keys: List[str]) -> Optional[str]:
    if not isinstance(obj, dict):
        return None
    for k in keys:
        v = obj.get(k)
        if isinstance(v, str):
            return v
    return None


__all__ = ["Gatherer"]
