# server.py
# ============================================================
# 中文：
#   Move MCP Tool Server（人物移动）
#   - 读取 map.json（地点图）
#   - 根据 from/to 计算最短路径（BFS）
#   - 接入 location_index.json（用于更友好的阻断信息与叙事提示）
#   - 可选持久化：严格“先写事件日志(JSONL) -> 再覆盖写状态快照(JSON)”
#
# English:
#   Move MCP Tool Server (character movement)
#   - Load map.json (location graph)
#   - Compute shortest path (BFS)
#   - Integrate location_index.json (better blocked messages / narration hints)
#   - Optional persistence: strictly "log first (JSONL) -> then snapshot state overwrite (JSON)"
# ============================================================

from __future__ import annotations

import secrets
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field

try:
    # 中文：优先使用官方 FastMCP（更省样板代码）
    # English: Prefer official FastMCP helper if available
    from mcp.server.fastmcp import FastMCP
    fastmcp_available = True
except Exception:
    fastmcp_available = False
    from mcp.server import Server

# ---------- Internal modules / 内部模块 ----------
from graph_store import GraphStore
from pathfinding import shortest_path_bfs, PathResult
from movement_rules import LocationIndex, can_traverse_with_index, blocked_to_dict
from state_store import StateStore
from event_log import EventLog


# ============================================================
# MCP Tool Schemas / 工具输入输出
# ============================================================

class MoveInput(BaseModel):
    """
    中文：移动输入
    English: Movement input
    """
    map_file: str = Field(description="Path to map.json")
    location_index_file: str = Field(
        default="data/location_index.json",
        description="Path to location_index.json (for enriched messages)"
    )

    # 中文：可选显式指定起点；不填则尝试从 state_file 的 player.location 读取
    # English: Optional explicit from_id; if omitted, read from state_file player.location
    from_id: Optional[str] = Field(default=None, description="Start location id (e.g., L001)")
    to_id: str = Field(description="Destination location id (e.g., L022)")

    # 中文：规则状态（锁/封锁/库存等），会覆盖 state_file 中的 rules/fields
    # English: Rule state (locks/blocks/inventory), overlays on top of snapshot state
    state: Dict[str, Any] = Field(default_factory=dict, description="Rule state dict")

    # 中文：是否持久化（先写 log 再写 state）
    # English: Whether to persist (log first, then state)
    persist: bool = Field(default=False)

    # 中文：持久化路径
    # English: Persistence paths
    state_file: Optional[str] = Field(default=None, description="Path to world_state.json (snapshot)")
    log_file: Optional[str] = Field(default=None, description="Path to state_events.jsonl (append-only)")

    timezone_str: str = Field(default="America/New_York", description="Timezone for event timestamps")


class MoveOutput(BaseModel):
    """
    中文：移动输出
    English: Movement output
    """
    ok: bool
    event_id: str

    from_id: str
    to_id: str

    new_location: str
    path: List[str] = Field(default_factory=list)
    distance: int = -1

    # 中文：若失败，blocked 给出原因与“带 index”的提示信息
    # English: On failure, blocked explains the reason with enriched info
    blocked: Optional[Dict[str, Any]] = None

    # 中文：持久化的回显（可选）
    # English: Persistence echoes (optional)
    persisted_log: Optional[Dict[str, Any]] = None
    persisted_state: Optional[Dict[str, Any]] = None


# ============================================================
# Helpers / 辅助函数
# ============================================================

def _load_snapshot_state(state_file: Optional[str]) -> Dict[str, Any]:
    """
    中文：读取快照状态（world_state.json），文件不存在则返回空 dict
    English: Load snapshot state; return {} if missing
    """
    if not state_file:
        return {}
    p = Path(state_file)
    if not p.exists():
        return {}
    import json
    text = p.read_text(encoding="utf-8").strip()
    if not text:
        return {}
    obj = json.loads(text)
    return obj if isinstance(obj, dict) else {}


def _resolve_from_id(inp: MoveInput, snapshot: Dict[str, Any]) -> str:
    """
    中文：
      解析起点：
      - 优先使用 inp.from_id
      - 否则尝试 snapshot["player"]["location"]
    English:
      Resolve starting location:
      - prefer inp.from_id
      - else snapshot["player"]["location"]
    """
    if inp.from_id:
        return inp.from_id

    player = snapshot.get("player")
    if isinstance(player, dict):
        loc = player.get("location")
        if isinstance(loc, str) and loc.strip():
            return loc.strip()

    raise ValueError("from_id is required (or state_file must contain player.location).")


def _merge_rule_state(snapshot: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """
    中文：
      合并规则状态：
      - 以 snapshot 为基础（尤其是 player.inventory / inventory）
      - 用 override 覆盖同名字段
      注意：这里做浅合并即可（复杂结构你们后续可扩展成深合并）。
    English:
      Merge rule state:
      - base from snapshot (especially inventory)
      - overlay with override (shallow merge)
    """
    base = dict(snapshot) if isinstance(snapshot, dict) else {}
    merged = dict(base)
    for k, v in (override or {}).items():
        merged[k] = v
    return merged


# ============================================================
# Core move implementation / 移动核心逻辑
# ============================================================

def move_impl(inp: MoveInput) -> MoveOutput:
    """
    中文：同步实现（FastMCP / 低层 Server 都能用）
    English: Sync implementation (works for FastMCP or low-level Server)
    """

    # 事件 ID（用于 log 与 state 的一致性）
    # Event id (used for log/state consistency)
    event_id = secrets.token_hex(8)

    # 1) Load snapshot (optional) / 读取快照（可选）
    snapshot = _load_snapshot_state(inp.state_file)

    # 2) Resolve from/to / 解析起点终点
    from_id = _resolve_from_id(inp, snapshot)
    to_id = inp.to_id.strip()

    # 3) Load map graph / 加载地图图结构
    gstore = GraphStore(inp.map_file, enforce_undirected=True)
    graph = gstore.load()

    if from_id not in graph:
        raise ValueError(f"Unknown from_id: {from_id}")
    if to_id not in graph:
        raise ValueError(f"Unknown to_id: {to_id}")

    # 4) Load location index / 加载地点索引（用于更友好提示）
    lindex = LocationIndex(inp.location_index_file)

    # 5) Merge rule state / 合并规则状态（snapshot + input override）
    rule_state = _merge_rule_state(snapshot, inp.state)

    # 6) Shortest path with rules / 使用规则计算最短路
    # 中文：把 can_traverse_with_index 包装成 BFS 需要的函数签名
    # English: wrap can_traverse_with_index into BFS signature
    def _can_traverse(src: str, dst: str, st: Dict[str, Any]):
        return can_traverse_with_index(src, dst, st, index=lindex)

    res: PathResult = shortest_path_bfs(
        graph=graph,
        start=from_id,
        goal=to_id,
        state=rule_state,
        can_traverse=_can_traverse,
    )

    # 7) Build output / 构造输出
    if res.ok:
        ok = True
        path = res.path
        distance = res.distance
        new_location = to_id
        blocked = None
    else:
        ok = False
        path = []
        distance = -1
        new_location = from_id
        blocked = blocked_to_dict(res.blocked)

    out = MoveOutput(
        ok=ok,
        event_id=event_id,
        from_id=from_id,
        to_id=to_id,
        new_location=new_location,
        path=path,
        distance=distance,
        blocked=blocked,
    )

    # ============================================================
    # 8) Optional persistence (LOG FIRST -> STATE SECOND)
    #    可选持久化（严格：先写日志 -> 再写状态）
    # ============================================================
    if inp.persist:
        if not inp.state_file or not inp.log_file:
            raise ValueError("persist=true requires both state_file and log_file.")

        store = StateStore(inp.state_file)
        elog = EventLog(inp.log_file, timezone_str=inp.timezone_str)

        # 读取当前 state 版本（用于记录 event 中的 before/after）
        # Load current version for version refs in event log
        current_state = store.load()
        version_before = int(current_state.get("version") or 0)
        version_after = version_before + 1

        # 生成 patch（JSON Patch 风格，便于回放/审计）
        # Build patch (JSON Patch style) for replay/audit
        patch = [
            {"op": "replace", "path": "/player/location", "value": new_location},
            {"op": "replace", "path": "/version", "value": version_after},
            {"op": "replace", "path": "/last_event_id", "value": event_id},
        ]

        # 1) 先写事件日志（即使 state 写失败，也至少保留事件证据）
        # 1) Write event log first (even if state write fails, the event remains)
        persisted_log = elog.append_move_event(
            event_id=event_id,
            actor="orchestrator",
            from_id=from_id,
            to_id=to_id,
            ok=ok,
            path=(res.path if res.ok else []),
            distance=(res.distance if res.ok else -1),
            reason_code=(res.blocked.reason_code if (not res.ok and res.blocked) else None),
            message=(res.blocked.message if (not res.ok and res.blocked) else None),
            patch=patch,
            state_version_before=version_before,
            state_version_after=version_after,
        )

        # 2) 再覆盖写 state 快照（原子写 + bump version + last_event_id）
        # 2) Overwrite snapshot state (atomic + bump version + last_event_id)
        def patch_fn(before: Dict[str, Any]) -> Dict[str, Any]:
            after = dict(before)
            player = dict(after.get("player") or {})
            player["location"] = new_location
            after["player"] = player
            return after

        update_result = store.apply_update(
            patch_fn=patch_fn,
            event_id=event_id,
            bump_version=True,
        )

        out.persisted_log = persisted_log
        out.persisted_state = update_result.after

    return out


# ============================================================
# MCP Wiring / MCP 工具注册
# ============================================================

if fastmcp_available:
    mcp = FastMCP("dm-move")

    @mcp.tool()
    def move(input: MoveInput) -> MoveOutput:
        """
        中文：MCP 工具入口（同步）
        English: MCP tool entry (sync)
        """
        return move_impl(input)

else:
    from mcp.types import Tool, CallToolResult  # type: ignore
    mcp = Server("dm-move")

    @mcp.tool("move", input_model=MoveInput, output_model=MoveOutput)
    async def move(input: MoveInput) -> MoveOutput:  # type: ignore
        """
        中文：MCP 工具入口（异步包装）
        English: MCP tool entry (async wrapper)
        """
        return move_impl(input)


if __name__ == "__main__":
    # 中文：stdio 模式运行（Claude Desktop / MCP Inspector）
    # English: run via stdio (Claude Desktop / MCP Inspector)
    mcp.run()
