from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence
import json
import re
from ..turn_context import TurnContext
from ..turn_heuristics import _extract_labeled_line, _mentions_unresolved_roll_request, _turn_has_resolved_roll, _tool_call_succeeded


_PHASE_ONE_CACHEABLE_TOOLS = frozenset({
    "check_can_interact",
    "get_current_context",
    "list_scene_entities",
    "get_entity_state",
    "get_world_graph",
    "get_world_connections",
    "get_world_location_overview",
    "get_world_location_detail",
    "retrieve_memory_tool",
    "get_recent_skill_checks",
})


# Keys that identify a finalize_turn payload emitted as text.
_FINALIZE_KEYS = ("turn_summary", "narration_focus", "blocked_reason")


def _coerce_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _iter_brace_objects(text: str):
    depth = 0
    start = -1
    for i, ch in enumerate(text):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            if depth > 0:
                depth -= 1
                if depth == 0 and start >= 0:
                    yield text[start:i + 1]
                    start = -1


def _salvage_finalize_payload(text: str) -> Optional[Dict[str, Any]]:
    """
    Recover a finalize_turn payload that the model wrote as text instead of doing a tool call.

    Handles three shapes seen in practice:
      1. A bare JSON object somewhere in the message.
      2. A JSON object inside a fenced ```json ... ``` block.
      3. A finalize_turn(...) / "Action: finalize_turn {...}" call written
         inline, where the braces hold the JSON payload.

    Returns a normalised payload dict (always carrying the three finalize keys)
    only when at least turn_summary can be recovered; otherwise None. The intent
    is to terminate the turn with the model's own content rather than burn
    iterations, NOT to reward the mistake: the caller still records that no real
    tool call was made.
    """
    if not text:
        return None

    for chunk in _iter_brace_objects(text):
        if not any(k in chunk for k in _FINALIZE_KEYS):
            continue
        try:
            payload = json.loads(chunk)
        except (ValueError, TypeError):
            continue
        if not isinstance(payload, dict):
            continue
        summary = _coerce_str(payload.get("turn_summary"))
        if not summary:
            continue
        return {
            "turn_summary": summary,
            "narration_focus": _coerce_str(payload.get("narration_focus")),
            "blocked_reason": _coerce_str(payload.get("blocked_reason")),
        }
    return None


@dataclass
class PhaseOneInput:
    """Everything Phase 1 needs to run. No engine reference; pass game_state + world directly."""
    state: Any # PromptState
    player_input: str
    turn_ctx: TurnContext
    game_state: Any
    roll_mode: str
    manual_roll_provider: Optional[Callable[[Dict[str, Any]], int]]


@dataclass
class PhaseOneOutput:
    """Everything Phase 1 produces. Consumed by narration and Phase 2."""
    finalize_payload: Dict[str, Any]
    phase_one_tool_calls: List[Dict[str, Any]]
    action_tool_calls: List[Dict[str, Any]]
    successful_tool_counts: Dict[str, int]
    prompt: str
    loop_result: Dict[str, Any]


class Phase1Runner:
    """
    Dependencies:
        adapter:            LLMAdapter (the tool-loop transport)
        execute_world_tool: callable(tool_name, args, game_state) -> result dict
        find_world_object:  callable(name, game_state) -> object or None
        tool_defs:          list of OpenAI-style tool definitions to expose
        tool_names:         iterable of allowed tool names (without finalize_turn)
        finalize_tool_def:  the finalize_turn tool definition
        system_prompt:      the Phase 1 system prompt
        prompt_builder:     callable(state) -> str
    """

    def __init__(
        self,
        *,
        adapter,
        execute_world_tool: Callable[[str, Dict[str, Any], Any], Dict[str, Any]],
        find_world_object: Callable[[str, Any], Any],
        tool_defs: Sequence[Dict[str, Any]],
        tool_names: Sequence[str],
        finalize_tool_def: Dict[str, Any],
        system_prompt: str,
        prompt_builder: Callable[[Any], str],
        max_iterations: int = 16,
    ) -> None:
        self.adapter = adapter
        self.execute_world_tool = execute_world_tool
        self.find_world_object = find_world_object
        self.tool_defs = list(tool_defs) + [finalize_tool_def]
        self.allowed_names = set(tool_names) | {"finalize_turn"}
        self.system_prompt = system_prompt
        self.prompt_builder = prompt_builder
        self.max_iterations = max_iterations

    def run(self, inp: PhaseOneInput) -> PhaseOneOutput:
        turn_ctx = inp.turn_ctx
        state = inp.state
        player_input = inp.player_input
        game_state = inp.game_state

        action_tool_calls: List[Dict[str, Any]] = []
        successful_tool_counts: Dict[str, int] = {}

        turn_ctx.phase = "phase_one"
        prompt = self.prompt_builder(state)

        def cache_signature(tool_name: str, args: Dict[str, Any]) -> str:
            cleaned = {
                key: value
                for key, value in (args or {}).items()
                if not str(key).startswith("_")
            }
            try:
                payload = json.dumps(cleaned, sort_keys=True, default=str)
            except Exception:
                payload = repr(sorted((args or {}).items()))
            return f"{tool_name}::{payload}"

        def tool_executor(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
            args = dict(arguments or {})
            turn_ctx.current_location = game_state.player_location

            # This prevents check_can_interact from prompting for a second History roll when the model just
            # needed to add a Decision Summary header to its text.
            cache = turn_ctx.phase_one_tool_cache
            cache_key = cache_signature(tool_name, args)
            if tool_name in _PHASE_ONE_CACHEABLE_TOOLS and cache_key in cache:
                cached_result = dict(cache[cache_key])
                cached_result["_cached"] = True
                turn_ctx.append_tool_call({
                    "phase": "phase_one",
                    "name": tool_name,
                    "arguments": args,
                    "result": cached_result,
                    "cached": True,
                })
                return cached_result

            # Manual roll passthrough (UI-supplied d20) for skill_check or single-die roll_dice.
            manual_roll_supported = (
                tool_name == "skill_check"
                or (tool_name == "roll_dice" and int(args.get("count", 1) or 1) == 1)
            )
            if (
                manual_roll_supported
                and inp.roll_mode == "manual"
                and callable(inp.manual_roll_provider)
                and "_manual_roll" not in args
            ):
                args["_manual_roll"] = int(inp.manual_roll_provider({
                    "tool_name": tool_name,
                    "phase": "phase_one",
                    "arguments": dict(args),
                }))

            result = self.execute_world_tool(tool_name, args, game_state)

            success = result.get("ok")
            if success is None:
                success = result.get("success", True)

            turn_ctx.append_tool_call({
                "phase": "phase_one",
                "name": tool_name,
                "arguments": args,
                "result": result,
            })

            if success and tool_name in _PHASE_ONE_CACHEABLE_TOOLS:
                cache[cache_key] = dict(result)

            if success:
                successful_tool_counts[tool_name] = successful_tool_counts.get(tool_name, 0) + 1

            if tool_name in {"roll_dice", "skill_check"}:
                action_tool_calls.append({
                    "phase": "phase_one",
                    "name": tool_name,
                    "arguments": args,
                    "result": result,
                })

            return result

        def pre_tool_use(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
            _ = arguments
            if tool_name not in self.allowed_names:
                return {
                    "allow": False,
                    "retryable": False,
                    "reason": (
                        f"Tool '{tool_name}' is not available in Phase 1. "
                        "Use only read tools, mechanics tools, and finalize_turn."
                    ),
                }
            if tool_name == "finalize_turn" and turn_ctx.finalize is not None:
                return {
                    "allow": False,
                    "retryable": False,
                    "reason": (
                        "finalize_turn was already called and succeeded. "
                        "STOP RESPONDING. Do not call finalize_turn again. "
                        "Do not call any more tools. The narrator will run automatically."
                    ),
                }
            return {"allow": True}

        def post_tool_use(tool_name: str, arguments: Dict[str, Any], payload: Dict[str, Any]) -> Optional[str]:
            _ = arguments
            success = payload.get("ok")
            if success is None:
                success = payload.get("success", True)
            if success:
                return None
            error_text = str(payload.get("error") or payload.get("reason") or "").lower()
            if "unknown tool" in error_text:
                return f"Unknown tool `{tool_name}`. Use one of the provided tools."
            if tool_name == "skill_check":
                reason = str(payload.get("reason") or payload.get("error") or "unknown reason")
                return f"skill_check failed: {reason}. Retry with valid entity_key and skill name."
            return None

        def response_hook(assistant_text: str, tool_calls: Sequence[Dict[str, Any]], _iteration: int) -> Optional[str]:
            text = str(assistant_text or "").strip()
            if len(tool_calls) > 1:
                return "Use at most one tool call per response."
            if not text:
                if tool_calls:
                    return None
                return "Every response must include a `Decision Summary:` line."
            if not _extract_labeled_line(text, "Decision Summary"):
                return "Every response must begin with `Decision Summary: ...`."
            # Catch the "finalize as text" failure mode in both its forms:
            # the model names finalize_turn in prose, OR it emits the bare payload
            # object (the JSON with turn_summary / narration_focus keys) with no
            # real tool call. Either way nothing ran and the turn is unfinalized.
            if not tool_calls and turn_ctx.finalize is None:
                wrote_name = bool(re.search(r"(?i)finalize_turn", text))
                wrote_payload = _salvage_finalize_payload(text) is not None
                if wrote_name or wrote_payload:
                    return (
                        "Your finalize_turn content was written as text, so "
                        "nothing ran. finalize_turn is a function you must call "
                        "through the tool interface, not text to print. Re-issue "
                        "it as a real tool call. Do not paste the JSON into your "
                        "message."
                    )
            if (
                not tool_calls
                and _mentions_unresolved_roll_request(text)
                and turn_ctx.finalize is None
                and not _turn_has_resolved_roll(turn_ctx.as_dict())
            ):
                return "If a roll/check is needed, call `skill_check` now. Do not defer rolls to narration."
            return None

        def stop_hook(assistant_text: str, already_fired: bool) -> Optional[str]:
            if turn_ctx.finalize is not None:
                return None
            # Last resort: if the model kept writing the finalize payload as text
            # instead of calling the tool, recover it so the turn terminates with
            # the model's own content rather than exhausting all iterations.
            salvaged = _salvage_finalize_payload(str(assistant_text or ""))
            if salvaged is not None:
                salvaged["salvaged_from_text"] = True
                turn_ctx.finalize = salvaged
                return None
            return (
                "The phase is not finished, and nothing has been finalized. You "
                "must finish by CALLING the finalize_turn function through the "
                "tool interface. Writing its name or its JSON in your message "
                "does not run it. Make the finalize_turn tool call now, with no "
                "other tools first, and do not put any JSON in the message body."
            )

        loop_result = self.adapter.run_tool_loop(
            stage="phase_one",
            system_prompt=self.system_prompt,
            messages=[{"role": "user", "content": prompt}],
            tools=self.tool_defs,
            tool_executor=tool_executor,
            max_iterations=self.max_iterations,
            pre_tool_use=pre_tool_use,
            post_tool_use=post_tool_use,
            assistant_response_hook=response_hook,
            stop_hook=stop_hook,
            early_exit=lambda: turn_ctx.finalize is not None,
        )

        finalize_payload = turn_ctx.finalize or {
            "turn_summary": f"Turn ended without an explicit finalize_turn call. Player action: {player_input}",
            "narration_focus": "",
            "blocked_reason": "Phase 1 hit max iterations before finalizing.",
        }

        phase_one_tool_calls = turn_ctx.calls_for_phase("phase_one")

        return PhaseOneOutput(
            finalize_payload=finalize_payload,
            phase_one_tool_calls=phase_one_tool_calls,
            action_tool_calls=action_tool_calls,
            successful_tool_counts=successful_tool_counts,
            prompt=prompt,
            loop_result=loop_result,
        )


__all__ = ["Phase1Runner", "PhaseOneInput", "PhaseOneOutput"]