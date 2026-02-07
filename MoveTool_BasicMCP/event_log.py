# event_log.py
# ============================================================
# 中文：
#   事件日志（JSONL append-only）模块：
#   - 每条事件一行 JSON（便于回放、审计、统计）
#   - 提供统一事件结构：event_id/ts/type/actor/payload/patch/meta
#   - 支持记录 state_version_before/state_version_after
#   - move 事件支持 blocked 字段（dict），也兼容旧版 reason_code/message
#
# English:
#   Append-only event log (JSONL):
#   - One JSON event per line (replay/audit/analytics)
#   - Unified schema: event_id/ts/type/actor/payload/patch/meta
#   - Optional state version refs for consistency
#   - move events support 'blocked' dict; also backward compatible with reason_code/message
# ============================================================

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo


def now_iso(timezone_str: str = "UTC") -> str:
    """
    中文：返回当前时间 ISO 字符串。优先使用 IANA 时区；
          如果系统缺少 tzdata 或找不到时区，则退化为 UTC。
    English: Return ISO timestamp. Prefer IANA tz; fallback to UTC if tz missing.
    """
    try:
        tz = ZoneInfo(timezone_str)
        return datetime.now(tz).isoformat(timespec="seconds")
    except Exception:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")


def append_jsonl(path: str | Path, obj: Dict[str, Any]) -> None:
    """
    中文：追加写一行 JSONL（自动创建父目录）
    English: Append one JSON object as JSONL line (auto mkdir)
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(obj, ensure_ascii=False)
    with p.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


@dataclass(frozen=True)
class Event:
    """
    中文：通用事件结构
    English: General event structure
    """
    event_id: str
    ts: str
    type: str
    actor: str
    payload: Dict[str, Any]
    patch: Optional[List[Dict[str, Any]]] = None
    meta: Optional[Dict[str, Any]] = None
    state_version_before: Optional[int] = None
    state_version_after: Optional[int] = None


class EventLog:
    """
    中文：事件日志 writer（JSONL）
    English: JSONL event log writer
    """

    def __init__(self, log_file: str | Path, *, timezone_str: str = "America/New_York") -> None:
        self.log_file = Path(log_file)
        self.timezone_str = timezone_str

    def append(
        self,
        *,
        event_id: str,
        type: str,
        actor: str,
        payload: Dict[str, Any],
        patch: Optional[List[Dict[str, Any]]] = None,
        meta: Optional[Dict[str, Any]] = None,
        state_version_before: Optional[int] = None,
        state_version_after: Optional[int] = None,
        ts: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        中文：追加写一个事件，返回写入 dict
        English: Append one event entry, return written dict
        """
        entry = Event(
            event_id=event_id,
            ts=ts or now_iso(self.timezone_str),
            type=type,
            actor=actor,
            payload=payload,
            patch=patch,
            meta=meta,
            state_version_before=state_version_before,
            state_version_after=state_version_after,
        )
        obj = entry.__dict__
        append_jsonl(self.log_file, obj)
        return obj

    def append_move_event(
        self,
        *,
        event_id: str,
        actor: str,
        from_id: str,
        to_id: str,
        ok: bool,
        path: List[str],
        distance: Optional[int],
        # ✅ 新版：blocked 是一个 dict（reason_code/message/at/meta...）
        blocked: Optional[Dict[str, Any]] = None,
        # ✅ 旧版兼容：如果有人还传 reason_code/message，我们也能写进 payload
        reason_code: Optional[str] = None,
        message: Optional[str] = None,
        patch: Optional[List[Dict[str, Any]]] = None,
        meta: Optional[Dict[str, Any]] = None,
        state_version_before: Optional[int] = None,
        state_version_after: Optional[int] = None,
        ts: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        中文：
          便捷方法：写 move 事件（payload 标准化）
          - 优先记录 blocked(dict)
          - 同时兼容 reason_code/message（向后兼容旧调用）
        English:
          Convenience method for move events with standardized payload
          - Prefer 'blocked' dict
          - Also supports legacy reason_code/message (backward compatibility)
        """
        payload: Dict[str, Any] = {
            "from": from_id,
            "to": to_id,
            "ok": ok,
            "path": path,
            "distance": distance,
        }

        # 新版 blocked
        if blocked is not None:
            payload["blocked"] = blocked

        # 旧版字段兼容（如果有人还在用）
        if reason_code is not None:
            payload["reason_code"] = reason_code
        if message is not None:
            payload["message"] = message

        return self.append(
            event_id=event_id,
            type="move",
            actor=actor,
            payload=payload,
            patch=patch,
            meta=meta,
            state_version_before=state_version_before,
            state_version_after=state_version_after,
            ts=ts,
        )
