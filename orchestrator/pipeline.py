from __future__ import annotations

import copy
import json
import logging
from typing import Any, Dict, Mapping, Optional

from DiceTool_BasicMCP import server as dice_server  # type: ignore

from .adapter import LLMAdapter
from .executor import Executor
from .gatherer import Gatherer
from .history import History
from .narrator import Narrator
from .planner import Planner
from .schemas import GatherResults, NarrationOutput, PlanOutput
from .state import apply_commit_ops


DEFAULT_TOOL_CATALOG = [
    {
        "tool": "dice.roll",
        "description": "Roll a d20 skill/ability check. Arguments: actor, skill, dc, advantage ('advantage'|'disadvantage'|'none').",
    },
    {
        "tool": "world.query",
        "description": "Retrieve factual information from the known game state using 'path' (dot separated) or 'query'.",
    },
    {
        "tool": "rules.lookup",
        "description": "Look up lightweight system guidance. Arguments: topic (string).",
    },
]

DEFAULT_BUDGETS = {
    "dice.roll": 2,
    "world.query": 4,
    "rules.lookup": 2,
}

RULES_COMPENDIUM = {
    "advantage": "Roll 2d20, keep the highest result, then add modifiers.",
    "disadvantage": "Roll 2d20, keep the lowest result, then add modifiers.",
    "ability check": "Roll 1d20 and add the relevant ability or skill modifier. Compare against DC.",
}


class Orchestrator:
    """High-level pipeline that coordinates the Gather→Execute→Plan→Narrate stages."""

    def __init__(
        self,
        initial_state: Optional[Dict[str, Any]] = None,
        *,
        model: str = "gpt-oss:20b",
        tool_catalog: Optional[list[dict[str, Any]]] = None,
        budgets: Optional[Mapping[str, int]] = None,
        verbose: bool = False,
    ) -> None:
        self.game_state: Dict[str, Any] = copy.deepcopy(initial_state or {})
        self.history = History()
        self.verbose = verbose
        self.logger = logging.getLogger(__name__)
        self.adapter = LLMAdapter(
            model=model,
            default_temperature=0.0,
            stage_temperatures={
                "gather": 0.1,
                "plan": 0.2,
                "narrate": 0.7,
                "summary": 0.2,
            },
            verbose=verbose,
        )
        catalog = tool_catalog or DEFAULT_TOOL_CATALOG
        self.gatherer = Gatherer(self.adapter, catalog)
        self.executor = Executor(
            {
                "dice.roll": self._dice_roll,
                "world.query": self._world_query,
                "rules.lookup": self._rules_lookup,
            },
            budgets=budgets or DEFAULT_BUDGETS,
            verbose=verbose,
            logger=self.logger.getChild("executor"),
        )
        self.planner = Planner(self.adapter)
        self.narrator = Narrator(self.adapter)

    def run_turn(self, player_input: str) -> Dict[str, Any]:
        self.history.add_player_turn(player_input)
        history_context = self.history.as_context()
        self._log_verbose("turn_input", {"player_input": player_input})
        self._log_verbose("history_context", history_context)
        self._log_verbose("game_state_pre", self.game_state)

        gather_output = self.gatherer.gather(
            history_context=history_context,
            game_state=self.game_state,
            player_input=player_input,
        )
        self._log_verbose("gather_output", gather_output.to_json())
        gather_results = self.executor.execute(
            gather_output,
            context={"game_state": self.game_state},
        )
        self._log_verbose("gather_results", gather_results.to_json())

        plan_output = self.planner.build_plan(
            history_context=history_context,
            game_state=self.game_state,
            player_input=player_input,
            gather_results=gather_results,
        )
        self._log_verbose("plan_output", plan_output.to_json())

        narration = self.narrator.narrate(
            history_context=history_context,
            game_state=self.game_state,
            player_input=player_input,
            gather_results=gather_results,
            plan_output=plan_output,
        )
        self._log_verbose("narration_output", narration.to_json())

        apply_commit_ops(self.game_state, narration.commit_ops)
        self.history.add_dm_turn(narration.to_json())
        self.history.maybe_summarize(self.adapter)
        self._log_verbose("game_state_post", self.game_state)

        return {
            "gather": gather_output.to_json(),
            "results": gather_results.to_json(),
            "plan": plan_output.to_json(),
            "response": narration.to_json(),
            "game_state": copy.deepcopy(self.game_state),
        }

    def _log_verbose(self, label: str, data: Any) -> None:
        if not self.verbose:
            return
        try:
            pretty = json.dumps(data, indent=2)
        except TypeError:
            pretty = str(data)
        self.logger.debug("== %s ==\n%s", label.upper(), pretty)

    @staticmethod
    def _dice_roll(arguments: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        game_state = context.get("game_state", {})
        actor = arguments.get("actor")
        skill = arguments.get("skill")
        dc = int(arguments.get("dc", 10))
        advantage = (arguments.get("advantage") or arguments.get("adv") or "none").lower()
        actor_data = game_state.get("actors", {}).get(actor, {}) if actor else {}
        skill_mod = actor_data.get("skills", {}).get(skill)
        if skill_mod is None:
            raise ValueError(f"Unknown skill '{skill}' for actor '{actor}'")
        modifier = int(skill_mod)
        formula = f"1d20{modifier:+d}"
        policy_map = {
            "advantage": "advantage.v1",
            "disadvantage": "disadvantage.v1",
            "none": "core.v1",
        }
        policy = policy_map.get(advantage, "core.v1")
        roll = dice_server.engine.run(formula, policy)
        breakdown = roll["breakdown"]
        kept = breakdown.get("kept") or breakdown["rolls"]
        nat20 = max(kept) == 20 if kept else False
        nat1 = min(kept) == 1 if kept else False
        return {
            "actor": actor,
            "skill": skill,
            "dc": dc,
            "formula": formula,
            "policy": policy,
            "total": roll["total"],
            "breakdown": breakdown,
            "kept": kept,
            "nat20": bool(nat20),
            "nat1": bool(nat1),
        }

    @staticmethod
    def _world_query(arguments: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        game_state = context.get("game_state", {})
        path = arguments.get("path")
        if path:
            value = _get_by_path(game_state, path)
            return {"path": path, "value": value}
        query = arguments.get("query")
        if query:
            return {"query": query, "value": _search_state(game_state, query)}
        raise ValueError("world.query requires 'path' or 'query'")

    @staticmethod
    def _rules_lookup(arguments: Dict[str, Any], _: Dict[str, Any]) -> Dict[str, Any]:
        topic = str(arguments.get("topic", "")).lower()
        if not topic:
            raise ValueError("rules.lookup requires a 'topic'")
        best = RULES_COMPENDIUM.get(topic)
        if best is None:
            return {"topic": topic, "note": "No entry found in compendium."}
        return {"topic": topic, "excerpt": best}


def _get_by_path(state: Dict[str, Any], path: str) -> Any:
    cursor: Any = state
    for part in path.split("."):
        if isinstance(cursor, dict) and part in cursor:
            cursor = cursor[part]
        else:
            return None
    return cursor


def _search_state(state: Dict[str, Any], query: str) -> Any:
    query_lower = query.lower()
    matches = []

    def _walk(node: Any, prefix: str = "") -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                new_prefix = f"{prefix}.{key}" if prefix else key
                _walk(value, new_prefix)
        elif isinstance(node, list):
            for idx, value in enumerate(node):
                new_prefix = f"{prefix}[{idx}]"
                _walk(value, new_prefix)
        else:
            text = str(node).lower()
            if query_lower in text:
                matches.append({"path": prefix, "value": node})

    _walk(state)
    return matches[:5]


__all__ = ["Orchestrator"]
