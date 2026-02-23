# orchestrator/world_state/tools/logging/tool_call_logger.py
# ============================================================
# 中文：
#   Tool 调用日志（JSONL，append-only）：
#   - 每次 tool 执行写入一行 JSON
#   - 字段包含：event_id / tool / args / result / before/after location / ts
#   - 不依赖外部框架，失败不抛异常（由调用者 swallow）
#
# English:
#   Tool call logger (JSONL, append-only):
#   - One JSON per tool call
#   - Includes: event_id / tool / args / result / before/after location / ts
#   - No framework dependency; caller should ignore logging failures
# ============================================================

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Union
from zoneinfo import ZoneInfo


def _now_iso(timezone_str: str) -> str:
    """
    中文：生成带时区 ISO 时间戳
    English: ISO timestamp with timezone
    """
    tz = ZoneInfo(timezone_str)
    return datetime.now(tz).isoformat(timespec="seconds")


def _append_jsonl(path: Union[str, Path], obj: Dict[str, Any]) -> None:
    """
    中文：追加写 JSONL（一行一个 JSON 对象）
    English: Append JSONL (one JSON object per line)
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


@dataclass
class ToolCallLogger:
    """
    中文：工具调用日志记录器
    English: Tool call logger
    """
    tool_log_file: Optional[Union[str, Path]] = None
    movement_log_file: Optional[Union[str, Path]] = None
    timezone_str: str = "America/New_York"

    def append_tool_call(
        self,
        *,
        event_id: str,
        tool: str,
        args: Any,
        result: Any,
        game_state: Any,
        before_location: Optional[str] = None,
    ) -> None:
        """
        中文：记录一次工具调用（写入 tool_calls.jsonl）
        English: Log a tool call entry into tool_calls.jsonl
        """
        if not self.tool_log_file:
            return

        after_location = getattr(game_state, "player_location", None)
        ok = True
        if isinstance(result, dict) and "success" in result:
            ok = bool(result.get("success"))

        payload: Dict[str, Any] = {
            "ts": _now_iso(self.timezone_str),
            "event_id": event_id,
            "tool": tool,
            "ok": ok,
            "before_location": before_location,
            "after_location": after_location,
            "args": args,
            "result": result,
        }

        _append_jsonl(self.tool_log_file, payload)