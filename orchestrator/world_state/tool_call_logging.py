# orchestrator/world_state/tool_call_logging.py
# ============================================================
# 中文：
#   通用 Tool 调用日志（JSONL，append-only）：
#   - 每次 tool 执行写入一行 JSON（失败吞掉，不影响主流程）
#   - 自动按你们现有的 TOOL_DEFINITION_GROUPS 分组（turn/scene/entity/...）
#   - 默认写入到 session checkpoint root 下：<checkpoint_root>/logs/
#   - 字段包含：event_id / turn / phase / group / tool / args / result / before/after location / ts
#
# English:
#   Generic tool call logger (JSONL, append-only):
#   - One JSON line per tool execution (best-effort; swallow failures)
#   - Categorizes tool calls using existing TOOL_DEFINITION_GROUPS
#   - Writes under session checkpoint root: <checkpoint_root>/logs/
#   - Fields: event_id / turn / phase / group / tool / args / result / before/after location / ts
# ============================================================

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Union
from zoneinfo import ZoneInfo

from .tool_registry import TOOL_DEFINITION_GROUPS  # uses existing grouping info
from .tool_runtime import get_world_checkpoint_root  # session root already exists in your flow


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


def _build_tool_group_index() -> Dict[str, str]:
    """
    中文：根据 TOOL_DEFINITION_GROUPS 构建 tool_name -> group_name 映射
    English: Build tool_name -> group_name index from TOOL_DEFINITION_GROUPS
    """
    index: Dict[str, str] = {}
    for group_name, defs in TOOL_DEFINITION_GROUPS.items():
        for tool_def in defs:
            fn = (tool_def or {}).get("function") or {}
            name = str(fn.get("name") or "").strip()
            if name and name not in index:
                index[name] = str(group_name)
    return index


_TOOL_GROUP_INDEX = _build_tool_group_index()


@dataclass
class ToolCallLogger:
    """
    中文：工具调用日志记录器（best-effort）
    English: Tool call logger (best-effort)
    """

    timezone_str: str = "America/New_York"
    # 中文：可选固定输出目录；None 时自动使用 session checkpoint root
    # English: Optional fixed output dir; if None, infer from session checkpoint root
    log_dir: Optional[Union[str, Path]] = None

    def _resolve_log_dir(self, game_state: Any) -> Optional[Path]:
        """
        中文：优先用 self.log_dir，否则用 game_state 的 checkpoint_root/logs
        English: Prefer self.log_dir; otherwise use game_state checkpoint_root/logs
        """
        try:
            if self.log_dir:
                return Path(self.log_dir).expanduser().resolve()

            root = get_world_checkpoint_root(game_state)
            if root is None:
                return None
            # root is ".../checkpoints" per your cli.py
            return Path(root) / "logs"
        except Exception:
            return None

    def tool_group(self, tool_name: str) -> str:
        """
        中文：返回工具分组（基于现有 TOOL_DEFINITION_GROUPS）
        English: Return tool group based on TOOL_DEFINITION_GROUPS
        """
        key = str(tool_name or "").strip()
        return _TOOL_GROUP_INDEX.get(key, "unknown")

    def build_event_id(self, *, turn: int, seq: int, tool: str) -> str:
        """
        中文：生成稳定可读的 event_id（同一 turn 内单调递增）
        English: Generate a readable event_id (monotonic within a turn)
        """
        safe_tool = str(tool or "tool").strip().replace(" ", "_")
        return f"turn_{int(turn):03d}:{int(seq):03d}:{safe_tool}"

    def log_tool_call(
        self,
        *,
        event_id: str,
        turn: int,
        phase: str,
        tool: str,
        args: Any,
        result: Any,
        game_state: Any,
        before_location: Optional[str] = None,
        after_location: Optional[str] = None,
    ) -> None:
        """
        中文：记录一次工具调用（写入 tool_calls.jsonl）
        English: Log a tool call entry into tool_calls.jsonl
        """
        log_dir = self._resolve_log_dir(game_state)
        if log_dir is None:
            return

        # 中文：尽量推断 after_location
        # English: best-effort infer after_location
        if after_location is None:
            after_location = getattr(game_state, "player_location", None)

        # 中文：兼容你们 success/ok 两套返回字段
        # English: support both success/ok payload conventions
        ok = True
        if isinstance(result, dict):
            if "success" in result:
                ok = bool(result.get("success"))
            elif "ok" in result:
                ok = bool(result.get("ok"))

        payload: Dict[str, Any] = {
            "ts": _now_iso(self.timezone_str),
            "event_id": event_id,
            "turn": int(turn),
            "phase": str(phase or "").strip(),
            "group": self.tool_group(tool),
            "tool": str(tool or "").strip(),
            "ok": bool(ok),
            "before_location": before_location,
            "after_location": after_location,
            "args": args,
            "result": result,
        }

        # 中文：append-only 写入；失败吞掉
        # English: append-only; swallow failures
        try:
            _append_jsonl(log_dir / f"{payload['group']}.jsonl", payload)
        except Exception:
            return