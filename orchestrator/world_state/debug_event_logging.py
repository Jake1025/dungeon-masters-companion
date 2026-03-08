# orchestrator/world_state/debug_event_logging.py
# ============================================================
# 中文：
#   调试事件日志（JSONL，append-only）：
#   - 用于记录非 tool-call 级别的调试信息
#   - 例如：阶段失败、强制结束、fallback、异常吞掉、用户中断
#   - 默认写入到 session checkpoint root 下：<checkpoint_root>/logs/debug_events.jsonl
#   - 失败不抛异常，不影响主流程
#
# English:
#   Debug event logger (JSONL, append-only):
#   - Records non-tool-call debug information
#   - Examples: stage failure, forced termination, fallback, swallowed exception, user interrupt
#   - Writes under session checkpoint root: <checkpoint_root>/logs/debug_events.jsonl
#   - Never raises; failures are swallowed
# ============================================================

from __future__ import annotations

import json
import traceback
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Union
from zoneinfo import ZoneInfo

from .tool_runtime import get_world_checkpoint_root


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
class DebugEventLogger:
    """
    中文：
      调试事件日志记录器（best-effort）
      - 默认推导到 <checkpoint_root>/logs/debug_events.jsonl

    English:
      Debug event logger (best-effort)
      - Defaults to <checkpoint_root>/logs/debug_events.jsonl
    """
    timezone_str: str = "America/New_York"
    log_dir: Optional[Union[str, Path]] = None

    def _resolve_log_dir(self, game_state: Any) -> Optional[Path]:
        """
        中文：
          优先使用 self.log_dir；
          否则从 game_state 的 checkpoint_root 推导 logs 目录。

        English:
          Prefer self.log_dir;
          otherwise infer logs directory from game_state checkpoint_root.
        """
        try:
            if self.log_dir:
                return Path(self.log_dir).expanduser().resolve()

            root = get_world_checkpoint_root(game_state)
            if root is None:
                return None

            return Path(root) / "logs"
        except Exception:
            return None

    def log_event(
        self,
        *,
        game_state: Any,
        turn: Optional[int],
        phase: str,
        event_type: str,
        message: str,
        severity: str = "info",
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        中文：记录一条结构化调试事件
        English: Log one structured debug event
        """
        log_dir = self._resolve_log_dir(game_state)
        if log_dir is None:
            return

        payload: Dict[str, Any] = {
            "ts": _now_iso(self.timezone_str),
            "turn": turn,
            "phase": str(phase or "").strip(),
            "event_type": str(event_type or "").strip(),
            "severity": str(severity or "info").strip().lower(),
            "message": str(message or "").strip(),
            "details": details or {},
        }

        try:
            _append_jsonl(log_dir / "debug_events.jsonl", payload)
        except Exception:
            return

    def log_exception(
        self,
        *,
        game_state: Any,
        turn: Optional[int],
        phase: str,
        where: str,
        exc: Exception,
        details: Optional[Dict[str, Any]] = None,
        severity: str = "error",
        include_traceback: bool = True,
    ) -> None:
        """
        中文：
          记录一条通用异常事件。
          用于尽量统一保存目前所有 debug 类型报错。

        English:
          Log one generic exception event.
          Used to capture most debug/error cases in a unified format.
        """
        extra_details: Dict[str, Any] = dict(details or {})
        extra_details.update(
            {
                "where": str(where or "").strip(),
                "error_type": type(exc).__name__,
                "error": str(exc),
            }
        )

        if include_traceback:
            extra_details["traceback"] = traceback.format_exc()

        self.log_event(
            game_state=game_state,
            turn=turn,
            phase=phase,
            event_type="exception",
            severity=severity,
            message=f"Exception raised in {where}.",
            details=extra_details,
        )