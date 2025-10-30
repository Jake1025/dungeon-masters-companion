from __future__ import annotations

from typing import Any, Dict

from .adapter import LLMAdapter
from .schemas import GatherResults, PlanOutput, PlanStep


PLAN_PROMPT = (
    "You are the Plan stage of a TTRPG orchestrator. "
    "Using the provided game state, player input, and executed tool results, "
    "produce a concise JSON plan. "
    "Each step must be atomic (e.g., describe, apply_state, announce_roll, prompt_player). "
    "Return JSON {\"steps\": [...], \"summary\": \"optional\"}. "
    "Do not invent new dice results or world data."
)


class Planner:
    """Transforms gathered data into an action plan for narration."""

    def __init__(self, adapter: LLMAdapter) -> None:
        self.adapter = adapter

    def build_plan(
        self,
        *,
        history_context: Dict[str, Any],
        game_state: Dict[str, Any],
        player_input: str,
        gather_results: GatherResults,
    ) -> PlanOutput:
        payload = {
            "conversation": history_context,
            "game_state": game_state,
            "player_input": player_input,
            "gather_results": gather_results.to_json(),
        }
        # Tolerant parsing: don't hard-fail if the LLM drifts slightly.
        try:
            raw = self.adapter.request_json(
                "plan",
                PLAN_PROMPT,
                payload,
                validator=None,  # normalize instead of strict validation
            )
        except Exception:
            raw = {}

        steps_raw = _get_list(raw, ["steps", "plan", "actions", "sequence"]) or []
        steps: list[PlanStep] = []
        for item in steps_raw:
            if not isinstance(item, dict):
                continue
            action = _get_str(item, ["action", "type", "name", "op"]) or ""
            if not action:
                continue
            description = _get_str(item, ["description", "desc", "text", "summary"]) or ""
            payload_data = item.get("payload")
            if not isinstance(payload_data, dict):
                payload_data = item.get("data") if isinstance(item.get("data"), dict) else {}
                if not isinstance(payload_data, dict):
                    alt = item.get("arguments") if isinstance(item.get("arguments"), dict) else {}
                    payload_data = alt if isinstance(alt, dict) else {}
            steps.append(PlanStep(action=action, description=description.strip(), payload=payload_data))

        if not steps:
            # Fallback: ensure at least one step so narration can proceed.
            steps = [
                PlanStep(
                    action="describe",
                    description="Provide a short in-character response and recap.",
                    payload={},
                )
            ]

        summary = _get_str(raw, ["summary", "recap", "notes"]) or None
        return PlanOutput(steps=steps, summary=summary)


def _validate_plan(payload: Dict[str, Any]) -> None:
    if not isinstance(payload, dict):
        raise TypeError("Plan response must be an object")
    steps = payload.get("steps")
    if not isinstance(steps, list) or not steps:
        raise ValueError("Plan response must include at least one step")
    for step in steps:
        if not isinstance(step, dict):
            raise ValueError("Each plan step must be an object")
        if "action" not in step:
            raise ValueError("Plan step missing 'action'")
        # description is recommended but not strictly required
        if not isinstance(step.get("payload", {}), dict):
            raise ValueError("Plan step payload must be an object if provided")


__all__ = ["Planner"]


# Local tolerant extractors ------------------------------------------------------

def _get_list(obj: Any, keys: list[str]) -> Optional[list[Any]]:
    if not isinstance(obj, dict):
        return None
    for k in keys:
        v = obj.get(k)
        if isinstance(v, list):
            return v
    return None


def _get_str(obj: Any, keys: list[str]) -> Optional[str]:
    if not isinstance(obj, dict):
        return None
    for k in keys:
        v = obj.get(k)
        if isinstance(v, str):
            return v
    return None
