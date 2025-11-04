from __future__ import annotations

from typing import Any, Dict

from .adapter import LLMAdapter
from .schemas import GatherResults, NarrationOutput, PlanOutput


NARRATE_PROMPT = (
    "You are the Narrate stage of a TTRPG orchestrator. "
    "Using the plan, executed tool results, and context, craft the final response. "
    "Return ONLY JSON with keys 'ic' and 'ooc'. "
    "'ic' must be in-character narration (no meta commentary). "
    "'ooc' must be any out-of-character meta commentary that is absolutely necessary to communicate to the player."
    "Do not invent new dice rolls or state changes."
)


class Narrator:
    """Generates the final narration and out-of-character metadata."""

    def __init__(self, adapter: LLMAdapter) -> None:
        self.adapter = adapter

    def narrate(
        self,
        *,
        history_context: Dict[str, Any],
        game_state: Dict[str, Any],
        player_input: str,
        gather_results: GatherResults,
        plan_output: PlanOutput,
    ) -> NarrationOutput:
        payload = {
            "conversation": history_context,
            "game_state": game_state,
            "player_input": player_input,
            "gather_results": gather_results.to_json(),
            "plan": plan_output.to_json(),
        }
        
        # Tolerant parsing: avoid KeyError on imperfect outputs
        try:
            raw = self.adapter.request_json(
                "narrate",
                NARRATE_PROMPT,
                payload,
                validator=None,
            )
        except Exception:
            raw = {}

        ic = _get_str(raw, ["ic", "text", "narration"]) or "The DM responds, narrating the scene."
        ic = ic.strip()
        ooc = raw.get("ooc") if isinstance(raw, dict) else {}
        ooc = ooc if isinstance(ooc, dict) else {}
        commit_ops = ooc.get("commit_ops", []) if isinstance(ooc.get("commit_ops", []), list) else []
        recap = _get_str(ooc, ["recap", "summary"]) or ""
        metadata = {k: v for k, v in ooc.items() if k not in {"commit_ops", "recap"}}
        
        return NarrationOutput(
            ic=ic,
            commit_ops=commit_ops,
            recap=recap,
            metadata=metadata,
        )


def _validate_narration(payload: Dict[str, Any]) -> None:
    if not isinstance(payload, dict):
        raise TypeError("Narration payload must be an object")
    if "ic" not in payload or "ooc" not in payload:
        raise ValueError("Narration payload requires 'ic' and 'ooc'")
    if not isinstance(payload["ic"], str):
        raise ValueError("'ic' must be a string")
    ooc = payload["ooc"]
    if not isinstance(ooc, dict):
        raise ValueError("'ooc' must be an object")
    commit_ops = ooc.get("commit_ops", [])
    if not isinstance(commit_ops, list):
        raise ValueError("'commit_ops' must be a list")
    if "recap" in ooc and not isinstance(ooc["recap"], str):
        raise ValueError("'recap' must be a string when provided")


__all__ = ["Narrator"]


def _get_str(obj: Any, keys: list[str]) -> str | None:
    if not isinstance(obj, dict):
        return None
    for k in keys:
        v = obj.get(k)
        if isinstance(v, str):
            return v
    return None
