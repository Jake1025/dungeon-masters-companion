# orchestrator/world_state/tools/dispatcher.py
# ============================================================
# 中文：
#   Tool 执行入口（execute_tool）
#   - 分发到各 impl
#   - 可选：记录 tool_calls.jsonl（append-only）
#   - 可选：为 move_to_location 注入 event_id，实现日志关联
#
# English:
#   Tool execution entry (execute_tool)
#   - Dispatches into impl modules
#   - Optional: logs into tool_calls.jsonl (append-only)
#   - Optional: injects event_id into move_to_location for correlation
# ============================================================

from __future__ import annotations

from typing import Any, Dict, Optional
from uuid import uuid4

from ..story import GameState, StoryGraph

from .impl.movement import move_to_location
from .impl.interaction import check_can_interact, get_current_context
from .impl.npc import move_npc

from .logging.tool_call_logger import log_tool_call


def execute_tool(
    tool_name: str,
    arguments: Dict[str, Any],
    game_state: GameState,
    story_graph: StoryGraph,
    *,
    # ---- logging (optional) ----
    tool_log_file: Optional[str] = None,
    movement_log_file: Optional[str] = None,
    timezone_str: str = "America/New_York",
    # ---- movement config (optional) ----
    location_index_file: Optional[str] = None,
    name_to_id: Optional[Dict[str, str]] = None,
    auto_path: bool = False,
    # ---- state versions (optional) ----
    state_version_before: Optional[int] = None,
    state_version_after: Optional[int] = None,
) -> Dict[str, Any]:
    """
    中文：执行工具并返回结果（可选写入 tool_calls.jsonl）
    English: Execute tool and return result (optionally logs tool call)
    """
    # 中文：为本次调用生成 event_id（用于关联 tool_call 与 movement_event）
    # English: generate an event_id for correlating tool_call and movement_event
    event_id = f"tool_{uuid4().hex}"

    if tool_name == "check_can_interact":
        result = check_can_interact(arguments, game_state, story_graph)

    elif tool_name == "get_current_context":
        result = get_current_context(arguments, game_state, story_graph)

    elif tool_name == "move_to_location":
        # 注入 movement logger + event_id
        result = move_to_location(
            arguments,
            game_state,
            story_graph,
            location_index_file=location_index_file,
            name_to_id=name_to_id,
            auto_path=auto_path,
            movement_log_file=movement_log_file,
            timezone_str=timezone_str,
            event_id=event_id.replace("tool_", "move_"),  # keep related but distinguishable
            state_version_before=state_version_before,
            state_version_after=state_version_after,
        )

    elif tool_name == "move_npc":
        result = move_npc(arguments, game_state, story_graph)

    else:
        result = {"success": False, "reason": f"Unknown tool: {tool_name}"}

    # ---- write tool call log (optional) ----
    if tool_log_file:
        log_tool_call(
            tool_log_file,
            tool_name=tool_name,
            arguments=arguments,
            result=result,
            timezone_str=timezone_str,
            event_id=event_id,
            state_version_before=state_version_before,
            state_version_after=state_version_after,
        )

    return result