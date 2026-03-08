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
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Union
from zoneinfo import ZoneInfo

from .tool_runtime import get_world_checkpoint_root


def _now_iso(timezone_str: str) -> str:
    tz = ZoneInfo(timezone_str)
    return datetime.now(tz).isoformat(timespec="seconds")


def _append_jsonl(path: Union[str, Path], obj: Dict[str, Any]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


@dataclass
class DebugEventLogger:
    timezone_str: str = "America/New_York"
    log_dir: Optional[Union[str, Path]] = None

    def _resolve_log_dir(self, game_state: Any) -> Optional[Path]:
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