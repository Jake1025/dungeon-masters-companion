# movement_rules.py
# ============================================================
# 中文：
#   规则层：决定“能不能走这一步边 (src -> dst)”。
#   重点：接入 location_index.json，让阻断信息更可读：
#     - 节点/边被封锁时，返回包含中文/英文地点名与简短提示的 Blocked
#     - 规则完全确定性：只依赖 state + index + (src,dst)
#
# English:
#   Rule layer: decides whether you can traverse an edge (src -> dst).
#   Key: uses location_index.json to enrich blocked reasons with names + short messages.
#   Deterministic: depends only on state + index + (src,dst).
# ============================================================

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple


# -------------------------
# Types / 类型
# -------------------------

@dataclass(frozen=True)
class LocationInfo:
    """
    中文：地点索引信息（从 location_index.json 读取）
    English: Location info loaded from location_index.json
    """
    name: str
    desc_zh: str = ""
    desc_en: str = ""


class LocationIndex:
    """
    中文：读取 location_index.json，并提供 lookup
    English: Loads location_index.json and provides lookups
    """

    def __init__(self, index_file: str | Path) -> None:
        self.index_file = Path(index_file)
        self._cache: Optional[Dict[str, LocationInfo]] = None

    def load(self) -> Dict[str, LocationInfo]:
        """
        中文：加载索引（带缓存）
        English: Load index (cached)
        """
        if self._cache is not None:
            return self._cache

        raw = json.loads(self.index_file.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("location_index.json must be a dict/object.")

        out: Dict[str, LocationInfo] = {}
        for loc_id, payload in raw.items():
            if not isinstance(payload, dict):
                continue
            out[str(loc_id)] = LocationInfo(
                name=str(payload.get("name", loc_id)),
                desc_zh=str(payload.get("desc_zh", "") or ""),
                desc_en=str(payload.get("desc_en", "") or ""),
            )

        self._cache = out
        return out

    def get_name(self, loc_id: str) -> str:
        """
        中文：取英文地点名（找不到则回退到 loc_id）
        English: Get English name (fallback to loc_id)
        """
        data = self.load()
        info = data.get(loc_id)
        return info.name if info else loc_id

    def get_desc_zh(self, loc_id: str) -> str:
        data = self.load()
        info = data.get(loc_id)
        return info.desc_zh if info else ""

    def get_desc_en(self, loc_id: str) -> str:
        data = self.load()
        info = data.get(loc_id)
        return info.desc_en if info else ""


# -------------------------
# Blocked format helper / 阻断信息辅助
# -------------------------

@dataclass(frozen=True)
class Blocked:
    """
    中文：阻断原因结构化表示（与 pathfinding.py 保持兼容字段）
    English: Structured blocked reason (compatible with pathfinding.py fields)
    """
    reason_code: str
    message: str
    at: str  # node_id or "A->B"
    # 中文：额外增强字段（不影响旧逻辑；server.py 转 dict 时可选择带上）
    # English: extra enriched fields (optional)
    meta: Optional[Dict[str, Any]] = None


def _mk_blocked(
    *,
    reason_code: str,
    message_zh: str,
    message_en: str,
    at: str,
    index: LocationIndex,
    src: Optional[str] = None,
    dst: Optional[str] = None,
) -> Blocked:
    """
    中文：构建更可读的 Blocked（包含地点名/描述）
    English: Build an enriched Blocked with names/descriptions
    """
    meta: Dict[str, Any] = {
        "message_zh": message_zh,
        "message_en": message_en,
    }

    if src:
        meta["from_id"] = src
        meta["from_name"] = index.get_name(src)
        meta["from_desc_zh"] = index.get_desc_zh(src)
        meta["from_desc_en"] = index.get_desc_en(src)

    if dst:
        meta["to_id"] = dst
        meta["to_name"] = index.get_name(dst)
        meta["to_desc_zh"] = index.get_desc_zh(dst)
        meta["to_desc_en"] = index.get_desc_en(dst)

    # 中文：给 at 也补一份 name（如果 at 本身是节点 id）
    # English: also enrich 'at' if it looks like a node id
    if "->" not in at:
        meta["at_name"] = index.get_name(at)

    # 中文：message 字段保留英文/通用（兼容旧 UI），细节放 meta
    # English: keep a generic message in message; details in meta
    return Blocked(
        reason_code=reason_code,
        message=message_en,
        at=at,
        meta=meta,
    )


# -------------------------
# Rule implementation / 规则实现
# -------------------------

def can_traverse_with_index(
    src: str,
    dst: str,
    state: Dict[str, Any],
    *,
    index: LocationIndex,
) -> Tuple[bool, Optional[Blocked]]:
    """
    中文：
      带 location_index 的默认规则钩子（可扩展）：
      - state["blocked_nodes"] = ["L022", ...] 禁止进入这些地点
      - state["blocked_edges"] = [["L021","L022"], ...] 禁止走这些边
      - 可选：state["locks"]，例如：
          locks = {"L022": {"requires": ["key_storeroom"], "message_zh": "...", "message_en": "..."}}
        若缺少钥匙则阻断进入 dst
    English:
      Default rule hook with location_index enrichment:
      - blocked_nodes blocks entering nodes
      - blocked_edges blocks traversing edges
      - optional locks: lock rules by destination
    """

    # -------------------------
    # 1) blocked_nodes / 节点封锁
    # -------------------------
    blocked_nodes = set(state.get("blocked_nodes") or [])
    if dst in blocked_nodes:
        b = _mk_blocked(
            reason_code="node_blocked",
            message_zh=f"此地封禁：{index.get_name(dst)}（寸步难行）",
            message_en=f"Destination blocked: {index.get_name(dst)}.",
            at=dst,
            index=index,
            src=src,
            dst=dst,
        )
        return False, b

    # -------------------------
    # 2) blocked_edges / 边封锁
    # -------------------------
    blocked_edges = state.get("blocked_edges") or []
    be = set()
    for e in blocked_edges:
        if isinstance(e, (list, tuple)) and len(e) == 2:
            be.add((str(e[0]), str(e[1])))

    if (src, dst) in be:
        b = _mk_blocked(
            reason_code="edge_blocked",
            message_zh=f"道路受阻：{index.get_name(src)} → {index.get_name(dst)}（此路不通）",
            message_en=f"Path blocked: {index.get_name(src)} -> {index.get_name(dst)}.",
            at=f"{src}->{dst}",
            index=index,
            src=src,
            dst=dst,
        )
        return False, b

    # -------------------------
    # 3) locks (optional) / 锁规则（可选）
    # -------------------------
    locks = state.get("locks") or {}
    if isinstance(locks, dict) and dst in locks and isinstance(locks[dst], dict):
        lock = locks[dst]
        requires = lock.get("requires") or []
        if not isinstance(requires, list):
            requires = [requires]

        # 中文：钥匙来源示例：state["player"]["inventory"] 或 state["inventory"]
        # English: key source example: state["player"]["inventory"] or state["inventory"]
        inv = []
        if isinstance(state.get("player"), dict):
            inv = state["player"].get("inventory") or []
        if not inv:
            inv = state.get("inventory") or []

        inv_set = set(map(str, inv))
        missing = [str(k) for k in requires if str(k) not in inv_set]

        if missing:
            # 可以用自定义提示 / allow custom messages
            msg_zh = str(lock.get("message_zh") or f"门锁森严：{index.get_name(dst)}（无钥难入）")
            msg_en = str(lock.get("message_en") or f"Locked: {index.get_name(dst)} (missing key).")

            b = _mk_blocked(
                reason_code="locked",
                message_zh=f"{msg_zh} 缺少：{', '.join(missing)}",
                message_en=f"{msg_en} Missing: {', '.join(missing)}",
                at=dst,
                index=index,
                src=src,
                dst=dst,
            )
            return False, b

    # If nothing blocks, allow traversal
    return True, None


def blocked_to_dict(blocked: Optional[Blocked]) -> Optional[Dict[str, Any]]:
    """
    中文：Blocked -> dict（可给 server.py 用）
    English: Blocked -> dict (for server.py)
    """
    if blocked is None:
        return None

    d = {
        "reason_code": blocked.reason_code,
        "message": blocked.message,
        "at": blocked.at,
    }

    # ✅ 兼容：Blocked 可能没有 meta 字段
    # ✅ Compatibility: Blocked may not have "meta"
    meta = getattr(blocked, "meta", None)
    if meta is not None:
        d["meta"] = meta

    return d
