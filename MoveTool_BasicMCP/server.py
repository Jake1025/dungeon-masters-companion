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
        if not inp.state_file or not inp.log_file:
            raise ValueError("persist=true requires both state_file and log_file.")

        # Update state snapshot (overwrite)
        persisted_state = dict(state)
        player = dict(persisted_state.get("player") or {})
        player["location"] = new_location
        persisted_state["player"] = player

        # versioning (optional but recommended)
        before_version = int(persisted_state.get("version") or 0)
        after_version = before_version + 1
        persisted_state["version"] = after_version
        persisted_state["last_event_id"] = event_id

        atomic_write_json(inp.state_file, persisted_state)

        # Append movement log (jsonl)
        persisted_log = log_move(
            inp.log_file,
            event_id=event_id,
            from_id=from_id,
            to_id=to_id,
            ok=ok,
            path=(res.path if ok else []),
            distance=(res.distance if ok else -1),
            timezone_str=inp.timezone_str,
            reason_code=(res.blocked.reason_code if (not ok and res.blocked) else None),
            message=(res.blocked.message if (not ok and res.blocked) else None),
            state_version_before=before_version,
            state_version_after=after_version,
        )

        out.persisted_state = persisted_state
        out.persisted_log = persisted_log

    return out


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
