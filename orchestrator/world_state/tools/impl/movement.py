# orchestrator/world_state/tools/impl/movement.py
# ============================================================
# 中文：
#   移动相关工具实现：
#   - move_to_location：玩家移动（支持直连 / 自动寻路）
#   - move_npc：DM 移动 NPC（用于剧情推进）
#
#   本版本重点修复：
#   1) move_log 强制写入 repo 根目录下的 state/move_log.jsonl
#      （避免 VS Code / 不同启动目录导致相对路径写偏）
#   2) 默认开启 auto_path：若目标非直连则自动寻路（BFS）
#
# English:
#   Movement tools:
#   - move_to_location: move player (direct / auto-path)
#   - move_npc: DM tool to move an NPC for story progression
#
#   Key fixes in this version:
#   1) Force move_log into <repo_root>/state/move_log.jsonl
#      (avoids CWD issues when launching from VS Code / different entrypoints)
#   2) auto_path defaults to True: if not directly connected, try BFS routing
# ============================================================

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from ...story import GameState, StoryGraph, NodeType
from ..registry import tool

# EN: No silent fallback. If these imports fail, fix package structure.
# 中文：不做静默降级。若导入失败，请修正包结构/路径。
from ..movement.pathfinding import shortest_path_bfs
from ..movement.rules import LocationIndex, can_traverse_with_index, blocked_to_dict
from ..movement.movement_logger import log_move


# ------------------------------------------------------------------
# EN: Helpers
# 中文：辅助函数
# ------------------------------------------------------------------
def _get_lang(game_state: GameState) -> str:
    """
    EN: Read language flag from game_state.quest_flags. Default "en".
    中文：从 game_state.quest_flags 读取语言开关，默认 "en"。
    """
    lang = "en"
    if isinstance(game_state.quest_flags, dict):
        v = game_state.quest_flags.get("lang")
        if isinstance(v, str) and v.strip():
            lang = v.strip().lower()
    return lang


def _repo_root_from_here() -> Path:
    """
    EN: Infer repo root by walking up from this file:
        orchestrator/world_state/tools/impl/movement.py -> repo root (…/dungeon-masters-companion)
    中文：从当前文件位置向上推断仓库根目录：
        orchestrator/world_state/tools/impl/movement.py -> 仓库根目录（…/dungeon-masters-companion）
    """
    # This file is: <repo>/orchestrator/world_state/tools/impl/movement.py
    # parents[0]=impl, [1]=tools, [2]=world_state, [3]=orchestrator, [4]=repo
    return Path(__file__).resolve().parents[4]


def _resolve_state_log_path(path_str: Optional[str], *, default_name: str) -> str:
    """
    EN:
      Resolve a log path:
      - If path_str is absolute: keep it
      - If path_str is relative or None: place it under <repo_root>/state/
    中文：
      解析日志路径：
      - 若 path_str 是绝对路径：直接使用
      - 若为相对路径或 None：强制放到 <repo_root>/state/ 下
    """
    repo_root = _repo_root_from_here()
    state_dir = repo_root / "state"
    state_dir.mkdir(parents=True, exist_ok=True)

    if not path_str:
        return str(state_dir / default_name)

    p = Path(path_str)
    if p.is_absolute():
        p.parent.mkdir(parents=True, exist_ok=True)
        return str(p)

    # EN: relative -> repo_root/state/<filename or subpath>
    # 中文：相对路径 -> repo_root/state/<文件名或子路径>
    return str(state_dir / p)


class _StoryGraphNeighborAdapter:
    """
    EN: Build an undirected neighbor map for LOCATION nodes.
        This makes BFS/pathfinding resilient even if the underlying data has one-way edges.
    中文：为地点节点构建“无向”的邻接表。
        即便底层数据存在单向边，也能正常寻路/回退。
    """

    def __init__(self, story_graph: StoryGraph) -> None:
        self.story_graph = story_graph
        self._adj: Dict[str, List[str]] = self._build_location_undirected_adj()

    def _build_location_undirected_adj(self) -> Dict[str, List[str]]:
        """
        EN: Create symmetric adjacency list for LOCATION <-> LOCATION only.
        中文：只对“地点-地点”连接做对称补全，NPC/物品/线索不参与寻路图。
        """
        adj_set: Dict[str, Set[str]] = {}

        # 1) collect all locations
        loc_keys: List[str] = []
        for n in self.story_graph.nodes:
            if n.node_type == NodeType.LOCATION:
                loc_keys.append(n.key)
                adj_set.setdefault(n.key, set())

        # 2) add edges, and force symmetry
        for src in loc_keys:
            src_node = self.story_graph.get_node(src)
            if not src_node:
                continue
            for dst in src_node.connections:
                dst_node = self.story_graph.get_node(dst)
                if not dst_node or dst_node.node_type != NodeType.LOCATION:
                    continue

                # EN: force undirected | 中文：强制无向
                adj_set[src].add(dst)
                adj_set.setdefault(dst, set()).add(src)

        # 3) freeze to list
        return {k: sorted(list(v)) for k, v in adj_set.items()}

    def neighbors(self, node: str) -> List[str]:
        """
        EN: Return LOCATION neighbors (already symmetric).
        中文：返回地点邻居（已对称补全）。
        """
        return list(self._adj.get(node, []))


def _parse_location_arg(args: Union[str, Dict[str, Any]]) -> Optional[str]:
    """
    EN: Accept args as str or dict and extract location key.
    中文：兼容 str/dict 两种入参，抽取 location_key。
    """
    if isinstance(args, str):
        return args.strip() or None
    if isinstance(args, dict):
        v = args.get("location_key")
        if isinstance(v, str):
            return v.strip() or None
    return None


def _parse_auto_path_arg(args: Union[str, Dict[str, Any]]) -> Optional[bool]:
    """
    EN: Extract auto_path from args if present (dict only).
    中文：从 args 中提取 auto_path（仅 dict 可能携带）。
    """
    if isinstance(args, dict) and "auto_path" in args:
        return bool(args.get("auto_path"))
    return None


def _write_move_log(
    *,
    qf: Dict[str, Any],
    before_loc: str,
    to_loc: str,
    ok: bool,
    path: List[str],
    distance: int,
    reason_code: Optional[str] = None,
    message: Optional[str] = None,
) -> None:
    """
    EN: Best-effort movement logging. Never raise.
        Always writes to <repo_root>/state/move_log.jsonl by default.
    中文：尽力写移动日志，永不抛异常影响主流程。
        默认强制写入 <repo_root>/state/move_log.jsonl。
    """
    try:
        move_log_file = _resolve_state_log_path(
            qf.get("move_log_file") if isinstance(qf.get("move_log_file"), str) else None,
            default_name="move_log.jsonl",
        )
        log_move(
            move_log_file,
            event_id=str(qf.get("last_event_id") or ""),
            from_id=str(before_loc),
            to_id=str(to_loc),
            ok=bool(ok),
            path=list(path),
            distance=int(distance),
            timezone_str=str(qf.get("tz") or "America/New_York"),
            reason_code=reason_code,
            message=message,
        )
    except Exception:
        # EN: Logging must never interrupt gameplay.
        # 中文：日志失败不得影响游戏运行。
        pass


# ------------------------------------------------------------------
# Tool: move_to_location
# ------------------------------------------------------------------
@tool(
    name="move_to_location",
    description="Move player to a connected location. Optionally supports auto pathfinding.",
    parameters={
        "type": "object",
        "properties": {
            "location_key": {"type": "string", "description": "Location key to move to"},
            "auto_path": {"type": "boolean", "description": "Enable multi-step pathfinding (auto-route)"},
        },
        "required": ["location_key"],
    },
    readonly=False,
)
def move_to_location(
    args: Union[str, Dict[str, Any]],
    game_state: GameState,
    story_graph: StoryGraph,
) -> dict[str, Any]:
    """
    EN:
      Move player to a new location.
      - Direct move: if destination is directly connected, move immediately.
      - Auto-path (default): if not directly connected, find a multi-step route via BFS.

    中文：
      移动玩家到新地点。
      - 直连移动：若目标在当前 connections 内则直接移动。
      - 自动寻路（默认开启）：若非直连则 BFS 多步找路并移动。
    """
    location_key = _parse_location_arg(args)
    if not location_key:
        return {"success": False, "new_location": None, "reason": "Missing location_key."}

    lang = _get_lang(game_state)

    # ---- validate target exists and is LOCATION / 校验目标存在且为地点 ----
    target = story_graph.get_node(location_key)
    if not target:
        return {"success": False, "new_location": None, "reason": f"Location '{location_key}' does not exist."}
    if target.node_type != NodeType.LOCATION:
        return {"success": False, "new_location": None, "reason": f"'{location_key}' is not a location."}

    current = story_graph.get_node(game_state.player_location)
    if not current:
        return {"success": False, "new_location": None, "reason": "Invalid current location."}

    if location_key == game_state.player_location:
        return {"success": True, "new_location": location_key, "reason": "You are already here."}

    # ---- read flags / 读取开关 ----
    qf = game_state.quest_flags if isinstance(game_state.quest_flags, dict) else {}

    # EN: Default auto_path=True, args override quest_flags.
    # 中文：默认 auto_path=True，args 优先于 quest_flags。
    auto_path = bool(qf.get("auto_path", True))
    arg_auto_path = _parse_auto_path_arg(args)
    if arg_auto_path is not None:
        auto_path = arg_auto_path

    # ---- optional index + rules state / 可选索引与规则状态 ----
    location_index_file = qf.get("location_index_file") if isinstance(qf.get("location_index_file"), str) else None
    name_to_id = qf.get("name_to_id") if isinstance(qf.get("name_to_id"), dict) else {}
    if not isinstance(name_to_id, dict):
        name_to_id = {}

    # EN: rules state comes from quest_flags (blocked_nodes/blocked_edges/locks).
    # 中文：规则状态默认放在 quest_flags（blocked_nodes/blocked_edges/locks）。
    state: Dict[str, Any] = dict(qf) if isinstance(qf, dict) else {}

    index = LocationIndex(location_index_file) if location_index_file else None
    to_id = lambda n: name_to_id.get(n, n)

    # ------------------------------------------------------------------
    # MODE 1) Direct move (preferred if possible) / 优先直连移动
    # ------------------------------------------------------------------
    if location_key in current.connections:
        ok, blocked = can_traverse_with_index(
            to_id(game_state.player_location),
            to_id(location_key),
            state,
            index=index,
        )
        if not ok:
            msg = blocked.message if blocked else ("Blocked by rules." if lang == "en" else "规则阻断，无法前往。")
            _write_move_log(
                qf=qf,
                before_loc=str(game_state.player_location),
                to_loc=str(location_key),
                ok=False,
                path=[str(game_state.player_location), str(location_key)],
                distance=1,
                reason_code=getattr(blocked, "reason_code", None) if blocked else "blocked",
                message=msg,
            )
            return {
                "success": False,
                "new_location": None,
                "reason": msg,
                "blocked": blocked_to_dict(blocked),
            }

        before_loc = game_state.player_location
        game_state.player_location = location_key
        game_state.discovered_keys.add(location_key)

        _write_move_log(
            qf=qf,
            before_loc=str(before_loc),
            to_loc=str(location_key),
            ok=True,
            path=[str(before_loc), str(location_key)],
            distance=1,
        )

        return {"success": True, "new_location": location_key, "reason": f"Moved to {location_key}."}

    # ------------------------------------------------------------------
    # MODE 2) Auto path / 自动寻路（多步）
    # ------------------------------------------------------------------
    if not auto_path:
        # EN/中文：auto_path 关闭时，非直连一律拒绝
        return {
            "success": False,
            "new_location": None,
            "reason": f"Cannot move to {location_key}. Not connected to {game_state.player_location}.",
        }

    graph_adapter = _StoryGraphNeighborAdapter(story_graph)

    def rule_hook(src_name: str, dst_name: str, s: Dict[str, Any]):
        return can_traverse_with_index(
            to_id(src_name),
            to_id(dst_name),
            s,
            index=index,
        )

    result = shortest_path_bfs(
        graph_adapter,
        game_state.player_location,
        location_key,
        state=state,
        can_traverse=rule_hook,
    )

    if not result.ok:
        msg = result.blocked.message if result.blocked else ("Unreachable." if lang == "en" else "道路不通，无法到达。")
        _write_move_log(
            qf=qf,
            before_loc=str(game_state.player_location),
            to_loc=str(location_key),
            ok=False,
            path=[str(game_state.player_location), str(location_key)],
            distance=-1,
            reason_code=getattr(result.blocked, "reason_code", None) if result.blocked else "unreachable",
            message=msg,
        )
        return {
            "success": False,
            "new_location": None,
            "reason": msg,
            "blocked": blocked_to_dict(result.blocked) if result.blocked else None,
        }

    before_loc = game_state.player_location

    # EN: Apply full path instantly (you can change to step-per-turn later).
    # 中文：默认一次性走完路径（如需每回合一步，可在此处改）。
    for step in result.path[1:]:
        game_state.player_location = step
        game_state.discovered_keys.add(step)

    _write_move_log(
        qf=qf,
        before_loc=str(before_loc),
        to_loc=str(location_key),
        ok=True,
        path=list(result.path),
        distance=int(result.distance),
    )

    return {
        "success": True,
        "new_location": location_key,
        "reason": f"Moved to {location_key} via path.",
        "path": result.path,
        "distance": result.distance,
    }


# ------------------------------------------------------------------
# Tool: move_npc
# ------------------------------------------------------------------
@tool(
    name="move_npc",
    description="Move an NPC to a different location (DM only, for story progression).",
    parameters={
        "type": "object",
        "properties": {
            "npc_key": {"type": "string", "description": "NPC key"},
            "new_location": {"type": "string", "description": "Destination location"},
        },
        "required": ["npc_key", "new_location"],
    },
    readonly=False,
)
def move_npc(
    args: Dict[str, Any],
    game_state: GameState,
    story_graph: StoryGraph,
) -> Dict[str, Any]:
    """
    EN: DM tool - move an NPC to a new location.
    中文：DM 工具 - 将 NPC 移动到新地点（用于剧情推进）。
    """
    npc_key = args.get("npc_key")
    new_location = args.get("new_location")

    if not isinstance(npc_key, str) or not npc_key.strip():
        return {"success": False, "reason": "Missing npc_key."}
    if not isinstance(new_location, str) or not new_location.strip():
        return {"success": False, "reason": "Missing new_location."}

    npc_key = npc_key.strip()
    new_location = new_location.strip()

    npc_node = story_graph.get_node(npc_key)
    loc_node = story_graph.get_node(new_location)

    if not npc_node:
        return {"success": False, "reason": f"NPC '{npc_key}' does not exist."}
    if npc_node.node_type != NodeType.NPC:
        return {"success": False, "reason": f"'{npc_key}' is not an NPC."}

    if not loc_node:
        return {"success": False, "reason": f"Location '{new_location}' does not exist."}
    if loc_node.node_type != NodeType.LOCATION:
        return {"success": False, "reason": f"'{new_location}' is not a location."}

    game_state.npc_locations[npc_key] = new_location
    return {"success": True, "reason": f"{npc_key} moved to {new_location}."}