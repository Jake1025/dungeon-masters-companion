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
        raw = self.adapter.request_json(
            "plan",
            PLAN_PROMPT,
            payload,
            validator=_validate_plan,
        )
        steps = [
            PlanStep(
                action=item["action"],
                description=item.get("description", "").strip(),
                payload=item.get("payload", {}),
            )
            for item in raw["steps"]
        ]
        summary = raw.get("summary")
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
        if "description" not in step:
            raise ValueError("Plan step missing 'description'")
        if not isinstance(step.get("payload", {}), dict):
            raise ValueError("Plan step payload must be an object if provided")


__all__ = ["Planner"]
