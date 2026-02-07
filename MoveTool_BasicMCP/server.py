# server.py
# ============================================================
# 中文：
#   Move MCP Tool Server（人物移动）
#   - 读取 map.json（地点图）
#   - 计算最短路径（BFS）
#   - 接入 location_index.json（更友好的阻断信息）
#   - 可选持久化：严格“先写事件日志(JSONL) -> 再覆盖写状态快照(JSON)”
#
#   重要：所有相对路径统一按 server.py 所在目录 BASE_DIR 解析
#
# English:
#   Move MCP Tool Server (character movement)
#   - Load map.json (location graph)
#   - Compute shortest path (BFS)
#   - Integrate location_index.json (enriched blocked messages)
#   - Optional persistence: strictly "log first -> state overwrite"
#
#   IMPORTANT: resolve relative paths against BASE_DIR (server.py directory)
# ============================================================

from __future__ import annotations

import secrets
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

try:
    from mcp.server.fastmcp import FastMCP
    fastmcp_available = True
except Exception:
    fastmcp_available = False
    from mcp.server import Server

from graph_store import GraphStore
from pathfinding import shortest_path_bfs, PathResult
from movement_rules import LocationIndex, can_traverse_with_index, blocked_to_dict
from state_store import StateStore
from event_log import EventLog

# ============================================================
# Path helpers / 路径辅助
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"


def resolve_path(p: Optional[str]) -> Optional[str]:
    """
    中文：相对路径 -> BASE_DIR 下的绝对路径；绝对路径保持不变
    English: resolve relative path against BASE_DIR; keep absolute as-is
    """
    if p is None:
        return None
    pp = Path(p)
    if pp.is_absolute():
        return str(pp)
    return str((BASE_DIR / pp).resolve())


# ============================================================
# Graph helpers / 图结构辅助（关键修复点）
# ============================================================

def graph_node_ids(graph: Any) -> set[str]:
    """
    中文：
      GraphStore.load() 可能返回 dict 或 Graph 对象。
      这里统一提取“所有节点 id 的集合”，用于校验 from/to 是否存在。
    English:
      GraphStore.load() may return dict or Graph object.
      This function extracts all node ids for membership checks.
    """
    # 1) adjacency dict: {node_id: [neighbors...]}
    if isinstance(graph, dict):
        return set(map(str, graph.keys()))

    # 2) Graph-like: graph.adj (dict)
    adj = getattr(graph, "adj", None)
    if isinstance(adj, dict):
        return set(map(str, adj.keys()))

    # 3) Graph-like: graph.edges (dict)
    edges = getattr(graph, "edges", None)
    if isinstance(edges, dict):
        return set(map(str, edges.keys()))

    # 4) Graph-like: graph.nodes
    nodes = getattr(graph, "nodes", None)
    if isinstance(nodes, dict):
        return set(map(str, nodes.keys()))
    if isinstance(nodes, list):
        return set(map(str, nodes))

    raise TypeError("Unsupported graph type: cannot extract node ids.")


# ============================================================
# MCP Tool Schemas / 工具输入输出
# ============================================================

class MoveInput(BaseModel):
    """
    中文：移动输入
    English: Movement input
    """
    map_file: str = Field(
        default=str(DATA_DIR / "map.json"),
        description="Path to map.json (relative to server.py if not absolute)"
    )
    location_index_file: str = Field(
        default=str(DATA_DIR / "location_index.json"),
        description="Path to location_index.json (relative to server.py if not absolute)"
    )

    from_id: Optional[str] = Field(default=None, description="Start location id (e.g., L001)")
    to_id: str = Field(description="Destination location id (e.g., L022)")

    state: Dict[str, Any] = Field(default_factory=dict, description="Rule state dict")

    persist: bool = Field(default=False)
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

    blocked: Optional[Dict[str, Any]] = None

    persisted_log: Optional[Dict[str, Any]] = None
    persisted_state: Optional[Dict[str, Any]] = None


# ============================================================
# Helpers / 辅助函数
# ============================================================

def _load_snapshot_state(state_file_abs: Optional[str]) -> Dict[str, Any]:
    """
    中文：读取快照状态，文件不存在则返回 {}
    English: load snapshot; return {} if missing
    """
    if not state_file_abs:
        return {}
    p = Path(state_file_abs)
    if not p.exists():
        return {}
    import json
    txt = p.read_text(encoding="utf-8").strip()
    if not txt:
        return {}
    obj = json.loads(txt)
    return obj if isinstance(obj, dict) else {}


def _resolve_from_id(inp: MoveInput, snapshot: Dict[str, Any]) -> str:
    """
    中文：优先 inp.from_id；否则取 snapshot["player"]["location"]
    English: prefer inp.from_id; else snapshot["player"]["location"]
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
    中文：浅合并 snapshot + override
    English: shallow merge snapshot + override
    """
    merged = dict(snapshot) if isinstance(snapshot, dict) else {}
    for k, v in (override or {}).items():
        merged[k] = v
    return merged


# ============================================================
# Core move logic / 移动核心逻辑
# ============================================================

def move_impl(inp: MoveInput) -> MoveOutput:
    """
    中文：同步实现（FastMCP / low-level Server 都可用）
    English: sync implementation
    """
    event_id = secrets.token_hex(8)

    # Resolve paths relative to BASE_DIR
    map_file_abs = resolve_path(inp.map_file)
    index_file_abs = resolve_path(inp.location_index_file)
    state_file_abs = resolve_path(inp.state_file)
    log_file_abs = resolve_path(inp.log_file)

    # Load snapshot (optional)
    snapshot = _load_snapshot_state(state_file_abs)

    # Resolve start/destination
    from_id = _resolve_from_id(inp, snapshot)
    to_id = inp.to_id.strip()

    # Load graph
    gstore = GraphStore(map_file_abs, enforce_undirected=True)
    graph = gstore.load()

    # ✅ FIX: Graph may not be iterable; use graph_node_ids()
    nodes = graph_node_ids(graph)
    if from_id not in nodes:
        raise ValueError(f"Unknown from_id: {from_id}")
    if to_id not in nodes:
        raise ValueError(f"Unknown to_id: {to_id}")

    # Load location index
    lindex = LocationIndex(index_file_abs)

    # Merge rule state (snapshot + override)
    rule_state = _merge_rule_state(snapshot, inp.state)

    # Wrap traversal rules
    def _can_traverse(src: str, dst: str, st: Dict[str, Any]):
        return can_traverse_with_index(src, dst, st, index=lindex)

    # Compute path
    res: PathResult = shortest_path_bfs(
        graph=graph,
        start=from_id,
        goal=to_id,
        state=rule_state,
        can_traverse=_can_traverse,
    )

    # Build output
    if res.ok:
        ok = True
        new_location = to_id
        path = res.path
        distance = res.distance
        blocked = None
    else:
        ok = False
        new_location = from_id
        path = []
        distance = -1
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

    # Persist: LOG FIRST -> STATE SECOND
    if inp.persist:
        if not state_file_abs or not log_file_abs:
            raise ValueError("persist=true requires both state_file and log_file.")

        store = StateStore(state_file_abs)
        elog = EventLog(log_file_abs, timezone_str=inp.timezone_str)

        current_state = store.load()
        version_before = int(current_state.get("version") or 0)
        version_after = version_before + 1

        patch = [
            {"op": "replace", "path": "/player/location", "value": new_location},
            {"op": "replace", "path": "/version", "value": version_after},
            {"op": "replace", "path": "/last_event_id", "value": event_id},
        ]

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
    mcp = Server("dm-move")

    @mcp.tool("move", input_model=MoveInput, output_model=MoveOutput)
    async def move(input: MoveInput) -> MoveOutput:  # type: ignore
        """
        中文：MCP 工具入口（异步包装）
        English: MCP tool entry (async wrapper)
        """
        return move_impl(input)


if __name__ == "__main__":
    mcp.run()
