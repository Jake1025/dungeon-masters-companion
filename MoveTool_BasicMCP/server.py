# server.py
# ============================================================
# 中文：
#   MCP Tool：人物移动（move/can_move/shortest_path）
#   - 地图：JSON（只读）
#   - 状态：JSON（覆盖写，可选 persist）
#   - 日志：JSONL（追加写，可选 persist）
#
# English:
#   MCP tool for movement (move/can_move/shortest_path)
#   - Map: read-only JSON
#   - State: overwrite JSON snapshot (optional persist)
#   - Log: append-only JSONL (optional persist)
# ============================================================

from __future__ import annotations

import json
import secrets
from pathlib import Path
from typing import Any, Dict, List, Optional
# 中文：引入新的状态存储与事件日志模块
# English: Import the new state snapshot store and append-only event log
from state_store import StateStore
from event_log import EventLog

from pydantic import BaseModel, Field

try:
    from mcp.server.fastmcp import FastMCP
    fastmcp_available = True
except Exception:
    fastmcp_available = False
    from mcp.server import Server

from graph_store import GraphStore
from pathfinding import shortest_path_bfs, PathResult
from movement_logger import log_move


# ----------------------------
# State IO helpers / 状态读写辅助
# ----------------------------

def read_json(path: str | Path) -> Dict[str, Any]:
    """
    中文：读取 JSON，若文件不存在返回空 dict
    English: Read JSON; return {} if missing
    """
    p = Path(path)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def atomic_write_json(path: str | Path, obj: Dict[str, Any]) -> None:
    """
    中文：原子覆盖写 JSON（避免写一半崩溃导致文件损坏）
    English: Atomic overwrite write for JSON to avoid partial corruption
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(p)


# ----------------------------
# MCP models / 输入输出模型
# ----------------------------

class CanMoveInput(BaseModel):
    map_file: str = Field(description="Path to map.json")
    from_id: str = Field(description="Current location node id")
    to_id: str = Field(description="Target location node id")
    state: Dict[str, Any] = Field(default_factory=dict, description="World/player state (rules input)")


class ShortestPathInput(BaseModel):
    map_file: str = Field(description="Path to map.json")
    from_id: str = Field(description="Start node id")
    to_id: str = Field(description="Goal node id")
    state: Dict[str, Any] = Field(default_factory=dict, description="World/player state (rules input)")


class MoveInput(BaseModel):
    map_file: str = Field(description="Path to map.json")

    # 中文：如果你们由 orchestrator 传 from/to，就用它；
    #      如果你想从 state_file 自动读当前位置，也可以传 state_file+persist。
    # English: Use explicit from/to, or optionally load from state_file when persisting.
    from_id: Optional[str] = Field(default=None, description="Current location (optional if using state_file)")
    to_id: str = Field(description="Target location node id")

    # 中文：状态可以直接传入（推荐：orchestrator 控制）；也可用 state_file 读取
    # English: Pass state directly (recommended) or load from state_file
    state: Dict[str, Any] = Field(default_factory=dict, description="World/player state (rules input)")

    # 中文：持久化选项：写状态快照与日志（可选）
    # English: Persistence options: overwrite state snapshot + append log (optional)
    persist: bool = Field(default=False, description="If true, write state_file and log_file")
    state_file: Optional[str] = Field(default=None, description="Path to world_state.json (overwrite)")
    log_file: Optional[str] = Field(default=None, description="Path to movement_log.jsonl (append)")

    timezone_str: str = Field(default="America/New_York", description="Timezone for timestamp/logging")


class MoveOutput(BaseModel):
    ok: bool
    from_id: str
    to_id: str
    path: List[str]
    distance: int
    blocked: Optional[Dict[str, Any]] = None

    # 中文：建议的新位置（通常等于 to_id，失败则为原地）
    # English: Recommended new location (usually equals to_id; unchanged if failed)
    new_location: str

    # 中文：用于关联日志/请求
    # English: Request/event id for tracing
    event_id: str
    request_id: str

    # 中文：可选：如果 persist=true，返回写入的日志条目
    # English: optional: return persisted log entry when persist=true
    persisted_log: Optional[Dict[str, Any]] = None

    # 中文：可选：如果 persist=true，返回更新后的 state 快照
    # English: optional: updated state snapshot when persist=true
    persisted_state: Optional[Dict[str, Any]] = None


# ----------------------------
# Core functions / 核心逻辑
# ----------------------------

def _load_graph(map_file: str):
    store = GraphStore(map_file, enforce_undirected=True)
    return store.load()


def _ensure_nodes(graph, from_id: str, to_id: str) -> None:
    if not graph.has_node(from_id):
        raise ValueError(f"Unknown from_id: {from_id}")
    if not graph.has_node(to_id):
        raise ValueError(f"Unknown to_id: {to_id}")


def _blocked_to_dict(blocked) -> Optional[Dict[str, Any]]:
    if blocked is None:
        return None
    return {
        "reason_code": blocked.reason_code,
        "message": blocked.message,
        "at": blocked.at,
    }


def can_move_impl(map_file: str, from_id: str, to_id: str, state: Dict[str, Any]) -> MoveOutput:
    graph = _load_graph(map_file)
    _ensure_nodes(graph, from_id, to_id)

    event_id = secrets.token_hex(8)
    request_id = secrets.token_hex(8)

    res = shortest_path_bfs(graph, from_id, to_id, state=state)

    if res.ok:
        return MoveOutput(
            ok=True,
            from_id=from_id,
            to_id=to_id,
            path=res.path,
            distance=res.distance,
            blocked=None,
            new_location=to_id,
            event_id=event_id,
            request_id=request_id,
        )

    return MoveOutput(
        ok=False,
        from_id=from_id,
        to_id=to_id,
        path=[],
        distance=-1,
        blocked=_blocked_to_dict(res.blocked),
        new_location=from_id,
        event_id=event_id,
        request_id=request_id,
    )


def shortest_path_impl(map_file: str, from_id: str, to_id: str, state: Dict[str, Any]) -> MoveOutput:
    # 中文：为了统一输出结构，我们复用 MoveOutput（ok/path/distance/blocked）
    # English: Reuse MoveOutput for consistent schema
    return can_move_impl(map_file, from_id, to_id, state)


def move_impl(inp: MoveInput) -> MoveOutput:
    graph = _load_graph(inp.map_file)

    # ---------- Load state if persisting and state_file provided ----------
    state = dict(inp.state or {})
    loaded_state: Dict[str, Any] = {}

    if inp.persist and inp.state_file:
        loaded_state = read_json(inp.state_file)
        # 中文：合并策略：input.state 覆盖 state_file 的同名键（你也可以反过来）
        # English: Merge: input.state overrides loaded_state
        merged = dict(loaded_state)
        merged.update(state)
        state = merged

    # Determine from_id
    from_id = inp.from_id
    if from_id is None:
        # 中文：若没显式给 from_id，尝试从 state 里取 player.location
        # English: If from_id not provided, try reading player.location from state
        from_id = (state.get("player") or {}).get("location")
    if not from_id:
        raise ValueError("from_id is required, or state.player.location must exist when from_id is omitted.")

    to_id = inp.to_id
    _ensure_nodes(graph, from_id, to_id)

    event_id = secrets.token_hex(8)
    request_id = secrets.token_hex(8)

    res: PathResult = shortest_path_bfs(graph, from_id, to_id, state=state)

    # Compute output
    ok = res.ok
    new_location = to_id if ok else from_id
    out = MoveOutput(
        ok=ok,
        from_id=from_id,
        to_id=to_id,
        path=res.path if ok else [],
        distance=res.distance if ok else -1,
        blocked=_blocked_to_dict(res.blocked) if not ok else None,
        new_location=new_location,
        event_id=event_id,
        request_id=request_id,
    )

    # ---------- Optional persistence ----------
    if inp.persist:
        # 中文：persist=true 需要同时提供 state_file 与 log_file
        # English: persist=true requires both state_file and log_file
        if not inp.state_file or not inp.log_file:
            raise ValueError("persist=true requires both state_file and log_file.")

        # 中文：初始化状态存储与事件日志（JSONL）
        # English: Initialize snapshot store and event log (JSONL)
        store = StateStore(inp.state_file)
        elog = EventLog(inp.log_file, timezone_str=inp.timezone_str)

        # 中文：读取“当前快照”，以便记录 version_before，并决定 from_id（如果你依赖 state_file）
        # English: Load current snapshot to capture version_before (and possibly source location)
        current_state = store.load()
        version_before = int(current_state.get("version") or 0)
        version_after = version_before + 1  # 我们默认每次持久化都 bump version

        # 中文：准备写入事件日志（先写 log，再写 state）
        # English: Prepare event log entry (log first, then state)
        path_used = res.path if ok else []
        distance_used = res.distance if ok else -1
        reason_code = res.blocked.reason_code if (not ok and res.blocked) else None
        message = res.blocked.message if (not ok and res.blocked) else None

        # 中文：可选 patch（JSON Patch 风格），用于回放/审计/统计
        # English: Optional patch (JSON Patch style) for replay/audit/analytics
        patch = [
            {"op": "replace", "path": "/player/location", "value": new_location},
            {"op": "replace", "path": "/version", "value": version_after},
            {"op": "replace", "path": "/last_event_id", "value": event_id},
        ]

        # 1) 先写入 JSONL 事件日志
        # 1) Append JSONL event log first
        persisted_log = elog.append_move_event(
            event_id=event_id,
            actor="orchestrator",  # 中文：你也可以改成 "tool" 或传参进来
            from_id=from_id,
            to_id=to_id,
            ok=ok,
            path=path_used,
            distance=distance_used,
            reason_code=reason_code,
            message=message,
            patch=patch,
            state_version_before=version_before,
            state_version_after=version_after,
        )

        # 2) 再覆盖写 state 快照（原子写）
        # 2) Overwrite snapshot state after logging (atomic)
        def patch_fn(before: dict) -> dict:
            after = dict(before)
            player = dict(after.get("player") or {})
            player["location"] = new_location
            after["player"] = player
            # 中文：version 与 last_event_id 在 apply_update 内会设置，这里不必重复写也可以
            # English: version/last_event_id can be set by apply_update; safe either way
            return after

        update_result = store.apply_update(
            patch_fn=patch_fn,
            event_id=event_id,
            bump_version=True,
        )

        out.persisted_log = persisted_log
        out.persisted_state = update_result.after



# ----------------------------
# MCP tool wiring / MCP 工具注册
# ----------------------------

if fastmcp_available:
    mcp = FastMCP("dm-move")

    @mcp.tool()
    def can_move(input: CanMoveInput) -> MoveOutput:
        return can_move_impl(input.map_file, input.from_id, input.to_id, input.state)

    @mcp.tool()
    def shortest_path(input: ShortestPathInput) -> MoveOutput:
        return shortest_path_impl(input.map_file, input.from_id, input.to_id, input.state)

    @mcp.tool()
    def move(input: MoveInput) -> MoveOutput:
        return move_impl(input)

else:
    mcp = Server("dm-move")

    @mcp.tool("can_move", input_model=CanMoveInput, output_model=MoveOutput)
    async def can_move(input: CanMoveInput) -> MoveOutput:  # type: ignore
        return can_move_impl(input.map_file, input.from_id, input.to_id, input.state)

    @mcp.tool("shortest_path", input_model=ShortestPathInput, output_model=MoveOutput)
    async def shortest_path(input: ShortestPathInput) -> MoveOutput:  # type: ignore
        return shortest_path_impl(input.map_file, input.from_id, input.to_id, input.state)

    @mcp.tool("move", input_model=MoveInput, output_model=MoveOutput)
    async def move(input: MoveInput) -> MoveOutput:  # type: ignore
        return move_impl(input)


if __name__ == "__main__":
    # 中文：stdio 模式运行（Claude Desktop / MCP Inspector）
    # English: run over stdio (Claude Desktop / MCP Inspector)
    mcp.run()
