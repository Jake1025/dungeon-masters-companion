# orchestrator/world_state/tools/movement/rules.py
# ============================================================
# 中文：
#   规则层：决定能否走一步 (src -> dst)。
#   - 支持 blocked_nodes / blocked_edges / locks
#   - 可接入 location_index + name<->id mapping，让阻断原因更可读
#   - 规则确定性：只依赖 state + index + (src,dst)
#
# English:
#   Rule layer: decides whether you can traverse an edge (src -> dst).
#   - Supports blocked_nodes / blocked_edges / locks
#   - Can use location_index + name<->id mapping for better messages
#   - Deterministic: depends only on state + index + (src,dst)
# ============================================================

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple


# -------------------------
# Blocked / 阻断原因
# -------------------------

@dataclass(frozen=True)
class Blocked:
    """
    中文：结构化阻断原因（兼容你们旧 pathfinding.py 字段）
    English: Structured blocked reason (compatible with older pathfinding.py fields)
    """
    reason_code: str
    message: str
    at: str               # node_id or "A->B"
    meta: Optional[Dict[str, Any]] = None


# -------------------------
# LocationIndex / 地点索引
# -------------------------

class LocationIndex:
    """
    中文：
      location_index.json 读取器（容错）：
      - 支持 {"L001": {...}} 或 {"locations": {"L001": {...}}}
    English:
      Reader for location_index.json (tolerant):
      - Supports {"L001": {...}} or {"locations": {...}}
    """

    def __init__(self, index_file: str | Path) -> None:
        self.index_file = Path(index_file)
        self._data: Dict[str, Dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        if not self.index_file.exists():
            self._data = {}
            return

        raw = self.index_file.read_text(encoding="utf-8").strip()
        if not raw:
            self._data = {}
            return

        obj = json.loads(raw)
        if isinstance(obj, dict):
            if "locations" in obj and isinstance(obj["locations"], dict):
                obj = obj["locations"]

            out: Dict[str, Dict[str, Any]] = {}
            for k, v in obj.items():
                if isinstance(v, dict):
                    out[str(k)] = v
            self._data = out
            return

        self._data = {}

    def get(self, loc_id: str) -> Optional[Dict[str, Any]]:
        return self._data.get(str(loc_id))

    def get_name(self, loc_id: str) -> str:
        rec = self.get(loc_id) or {}
        name = rec.get("name") or rec.get("title")
        if isinstance(name, str) and name.strip():
            return name.strip()
        return str(loc_id)

    def get_desc_zh(self, loc_id: str) -> str:
        rec = self.get(loc_id) or {}
        v = rec.get("desc_zh") or rec.get("zh") or ""
        return v.strip() if isinstance(v, str) else ""

    def get_desc_en(self, loc_id: str) -> str:
        rec = self.get(loc_id) or {}
        v = rec.get("desc_en") or rec.get("en") or ""
        return v.strip() if isinstance(v, str) else ""


# -------------------------
# Helpers / 辅助函数
# -------------------------

def blocked_to_dict(blocked: Optional[Blocked]) -> Optional[Dict[str, Any]]:
    """
    中文：Blocked -> dict（给日志/服务端/调试用）
    English: Blocked -> dict (for logs/server/debug)
    """
    if blocked is None:
        return None
    d = {"reason_code": blocked.reason_code, "message": blocked.message, "at": blocked.at}
    if blocked.meta is not None:
        d["meta"] = blocked.meta
    return d


def _mk_blocked(
    *,
    reason_code: str,
    message_zh: str,
    message_en: str,
    at: str,
    index: Optional[LocationIndex],
    src_id: Optional[str] = None,
    dst_id: Optional[str] = None,
    lang: str = "en",
) -> Blocked:
    """
    中文：构建可读 Blocked，meta 同时包含 zh/en
    English: Build readable Blocked; meta includes both zh/en
    """
    meta: Dict[str, Any] = {"message_zh": message_zh, "message_en": message_en}

    if index is not None and src_id:
        meta["from_id"] = src_id
        meta["from_name"] = index.get_name(src_id)
        meta["from_desc_zh"] = index.get_desc_zh(src_id)
        meta["from_desc_en"] = index.get_desc_en(src_id)

    if index is not None and dst_id:
        meta["to_id"] = dst_id
        meta["to_name"] = index.get_name(dst_id)
        meta["to_desc_zh"] = index.get_desc_zh(dst_id)
        meta["to_desc_en"] = index.get_desc_en(dst_id)

    if index is not None and "->" not in at:
        meta["at_name"] = index.get_name(at)

    # 默认英文；若 lang=zh 则 message 用中文
    message = message_zh if lang.lower().startswith("zh") else message_en
    return Blocked(reason_code=reason_code, message=message, at=at, meta=meta)


# -------------------------
# Main rule hook / 核心规则钩子
# -------------------------

def can_traverse_with_index(
    src_id: str,
    dst_id: str,
    state: Dict[str, Any],
    *,
    index: Optional[LocationIndex] = None,
    lang: str = "en",
) -> Tuple[bool, Optional[Blocked]]:
    """
    中文：
      带 location_index 的规则：
      - state["blocked_nodes"] = ["L022", ...]
      - state["blocked_edges"] = [["L021","L022"], ...]
      - state["locks"] = {"L022": {"requires": ["key_x"], "message_zh": "...", "message_en": "..."}}
    English:
      Rule hook with optional location_index enrichment.
    """

    # 1) blocked_nodes / 节点封锁
    blocked_nodes = set(state.get("blocked_nodes") or [])
    if dst_id in blocked_nodes:
        b = _mk_blocked(
            reason_code="node_blocked",
            message_zh=f"此地封禁：{index.get_name(dst_id) if index else dst_id}（寸步难行）",
            message_en=f"Destination blocked: {index.get_name(dst_id) if index else dst_id}.",
            at=dst_id,
            index=index,
            src_id=src_id,
            dst_id=dst_id,
            lang=lang,
        )
        return False, b

    # 2) blocked_edges / 边封锁
    blocked_edges = state.get("blocked_edges") or []
    be = set()
    for e in blocked_edges:
        if isinstance(e, (list, tuple)) and len(e) == 2:
            be.add((str(e[0]), str(e[1])))

    if (src_id, dst_id) in be:
        src_name = index.get_name(src_id) if index else src_id
        dst_name = index.get_name(dst_id) if index else dst_id
        b = _mk_blocked(
            reason_code="edge_blocked",
            message_zh=f"道路受阻：{src_name} → {dst_name}（此路不通）",
            message_en=f"Path blocked: {src_name} -> {dst_name}.",
            at=f"{src_id}->{dst_id}",
            index=index,
            src_id=src_id,
            dst_id=dst_id,
            lang=lang,
        )
        return False, b

    # 3) locks / 锁规则（可选）
    locks = state.get("locks") or {}
    if isinstance(locks, dict) and dst_id in locks and isinstance(locks[dst_id], dict):
        lock = locks[dst_id]
        requires = lock.get("requires") or []
        if not isinstance(requires, list):
            requires = [requires]

        # inventory 兼容两种结构 / support two structures
        inv = []
        if isinstance(state.get("player"), dict):
            inv = state["player"].get("inventory") or []
        if not inv:
            inv = state.get("inventory") or []

        inv_set = set(map(str, inv))
        missing = [str(k) for k in requires if str(k) not in inv_set]
        if missing:
            dst_name = index.get_name(dst_id) if index else dst_id
            msg_zh = str(lock.get("message_zh") or f"门锁森严：{dst_name}（无钥难入）")
            msg_en = str(lock.get("message_en") or f"Locked: {dst_name} (missing key).")

            b = _mk_blocked(
                reason_code="locked",
                message_zh=f"{msg_zh} 缺少：{', '.join(missing)}",
                message_en=f"{msg_en} Missing: {', '.join(missing)}",
                at=dst_id,
                index=index,
                src_id=src_id,
                dst_id=dst_id,
                lang=lang,
            )
            return False, b

    return True, None