# orchestrator/world_state/tools/__init__.py
from __future__ import annotations

"""
EN: Public tools package API.
    Exports:
      - VALIDATE_TOOLS: read-only tool schemas
      - TOOL_DEFINITIONS: all tool schemas
      - execute_tool: unified tool execution entry
      - selected tool fns for direct import (e.g., move_to_location)

中文：tools 包对外接口。
    导出：
      - VALIDATE_TOOLS：只读工具 schema
      - TOOL_DEFINITIONS：全部工具 schema
      - execute_tool：统一执行入口
      - 部分工具函数可被直接导入（如 move_to_location）
"""

from pathlib import Path
from uuid import uuid4

from .registry import REGISTRY
from .logging import ToolCallLogger

# -----------------------------------------------------------------------------
# EN: Import tool implementations so decorators register them into REGISTRY.
# 中文：导入工具实现，使装饰器将工具注册到 REGISTRY。
# -----------------------------------------------------------------------------
from .impl.interact import check_can_interact  # noqa: F401
from .impl.context import get_current_context  # noqa: F401
from .impl.movement import move_to_location, move_npc  # noqa: F401

# -----------------------------------------------------------------------------
# EN: Generated schema lists (no manual duplication).
# 中文：自动生成 schema 列表（无需手工维护两份）。
# -----------------------------------------------------------------------------
VALIDATE_TOOLS = REGISTRY.schema_list(readonly_only=True)
TOOL_DEFINITIONS = REGISTRY.schema_list(readonly_only=False)

# -----------------------------------------------------------------------------
# EN: Logger (JSONL, append-only). Separate files by category.
# 中文：日志记录器（JSONL 追加写）。按类别拆分不同文件。
# -----------------------------------------------------------------------------
_DEFAULT_STATE_DIR = Path("state")
_logger = ToolCallLogger(
    tool_log_file=_DEFAULT_STATE_DIR / "tool_calls.jsonl",
    # EN: movement events should ideally be written inside movement tool itself.
    # 中文：移动事件日志最好由 movement 工具内部写入；这里给默认文件名供你们统一配置。
    movement_log_file=_DEFAULT_STATE_DIR / "movement_events.jsonl",
    timezone_str="America/New_York",
)


def execute_tool(tool_name: str, arguments, game_state, story_graph):
    """
    EN: Execute tool via registry and log the call.
        Logging must not interrupt gameplay.
    中文：通过 registry 执行工具并记录日志。
        记录失败也不得影响游戏运行。
    """
    before_loc = getattr(game_state, "player_location", None)

    # EN: event_id correlates tool call + movement event (if movement uses it).
    # 中文：event_id 用来关联 tool call 与 movement event（若 movement 工具接入）。
    event_id = f"tool_{uuid4().hex}"

    # -------------------------------------------------------------------------
    # EN: Execute tool (via registry).
    # 中文：执行工具（通过注册表）。
    #
    # NOTE:
    # - If your REGISTRY.execute only accepts (name,args,game_state,story_graph),
    #   keep it as-is.
    # - If it supports kwargs, pass event_id/log file paths for correlation.
    #
    # 注意：
    # - 如果 REGISTRY.execute 只接受固定 4 参数，就保持原样；
    # - 如果支持透传 kwargs，可以把 event_id / log_file 传下去（更强）。
    # -------------------------------------------------------------------------
    try:
        # Try a "kwargs" call first (non-breaking fallback).
        result = REGISTRY.execute(
            tool_name,
            arguments,
            game_state,
            story_graph,
            event_id=event_id,
            movement_log_file=str(_logger.movement_log_file) if _logger.movement_log_file else None,
            timezone_str=_logger.timezone_str,
        )
    except TypeError:
        # Backward-compatible: registry does not accept kwargs.
        result = REGISTRY.execute(tool_name, arguments, game_state, story_graph)

    # -------------------------------------------------------------------------
    # EN: Always attempt to log, but never raise.
    # 中文：尽量记录，但绝不抛异常影响主流程。
    # -------------------------------------------------------------------------
    try:
        _logger.append_tool_call(
            event_id=event_id,
            tool=tool_name,
            args=arguments,
            result=result,
            game_state=game_state,
            before_location=before_loc,
        )
    except Exception:
        pass

    return result


__all__ = [
    # schemas / execution
    "VALIDATE_TOOLS",
    "TOOL_DEFINITIONS",
    "execute_tool",
    "REGISTRY",
    # direct tool fns (keep backward compatibility)
    "move_to_location",
    "move_npc",
    "check_can_interact",
    "get_current_context",
]