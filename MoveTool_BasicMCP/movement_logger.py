# movement_logger.py
# ============================================================
# 中文：
#   负责将移动事件写入 JSONL（append-only）。
#   每次写入一行 JSON，便于回放、统计、审计。
#
# English:
#   Append-only JSONL logger for movement events.
#   Writes one JSON object per line for replay/audit/analytics.
# ============================================================

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class MoveLogEntry:
    """
    中文：移动日志条目（可按需扩展字段）
    English: Movement log entry (extend as needed)
    """
    ts: str
    event_id: str
    from_id: str
    to_id: str
    ok: bool
    path: list[str]
    distance: int
    reason_code: Optional[str] = None
    message: Optional[str] = None
    state_version_before: Optional[int] = None
    state_version_after: Optional[int] = None


def now_iso(timezone_str: str = "America/New_York") -> str:
    """
    中文：返回带时区的 ISO 时间戳
    English: ISO timestamp with timezone
    """
    tz = ZoneInfo(timezone_str)
    return datetime.now(tz).isoformat(timespec="seconds")


def append_jsonl(log_file: str | Path, obj: Dict[str, Any]) -> None:
    """
    中文：追加写一行 JSONL
    English: Append one JSON object as a JSONL line
    """
    path = Path(log_file)
    path.parent.mkdir(parents=True, exist_ok=True)

    line = json.dumps(obj, ensure_ascii=False)
    with path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def log_move(
    log_file: str | Path,
    *,
    event_id: str,
    from_id: str,
    to_id: str,
    ok: bool,
    path: list[str],
    distance: int,
    timezone_str: str = "America/New_York",
    reason_code: Optional[str] = None,
    message: Optional[str] = None,
    state_version_before: Optional[int] = None,
    state_version_after: Optional[int] = None,
) -> Dict[str, Any]:
    """
    中文：构造 MoveLogEntry 并写入 JSONL，返回写入对象（dict）
    English: Build a MoveLogEntry, append to JSONL, and return the dict
    """
    entry = MoveLogEntry(
        ts=now_iso(timezone_str),
        event_id=event_id,
        from_id=from_id,
        to_id=to_id,
        ok=ok,
        path=path,
        distance=distance,
        reason_code=reason_code,
        message=message,
        state_version_before=state_version_before,
        state_version_after=state_version_after,
    )
    payload = entry.__dict__
    append_jsonl(log_file, payload)
    return payload
