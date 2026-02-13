from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Sequence
from enum import Enum
from pathlib import Path
import json
import os


# ============================================================
# Language selection / 语言选择
#
# EN:
#   Default is English. Set environment variable STORY_LANG=zh to switch.
# ZH:
#   默认英文。设置环境变量 STORY_LANG=zh 可切换中文。
# ============================================================

def _get_lang() -> str:
    raw = (os.getenv("STORY_LANG") or "").strip().lower()
    if raw in {"zh", "zh-cn", "zh_cn", "chinese", "cn"}:
        return "zh"
    return "en"

LANG = _get_lang()


# ============================================================
# NodeType / 节点类型
# ============================================================

class NodeType(Enum):
    """Type of story node / 故事节点类型"""
    LOCATION = "location"
    NPC = "npc"
    ITEM = "item"
    CLUE = "clue"


# ============================================================
# StoryNode / 故事节点
# ============================================================

@dataclass(frozen=True)
class StoryNode:
    """Single story location/person/item/clue with lightweight connections.
    单个故事节点：地点/人物/物品/线索 + 轻量连接关系。
    """
    key: str
    description: str
    node_type: NodeType
    connections: Sequence[str] = field(default_factory=tuple)
    tags: Sequence[str] = field(default_factory=tuple)


# ============================================================
# GameState / 游戏状态（可变）
# ============================================================

@dataclass
class GameState:
    """Mutable game state - tracks dynamic information.
    可变游戏状态：追踪动态信息。
    """
    player_location: str
    discovered_keys: set[str] = field(default_factory=set)
    conversation_history: list[dict] = field(default_factory=list)
    current_beat: int = 0
    quest_flags: dict[str, bool] = field(default_factory=dict)
    npc_locations: dict[str, str] = field(default_factory=dict)


# ============================================================
# Data files / 数据文件
# ============================================================

DATA_DIR = Path(__file__).resolve().parent / "data"

NODES_FILE = "nodes_v2.json"
GRAPH_FILE = "graph_full_v2.json"
START_KEYS_FILE = "default_start_keys_v2.json"
STARTING_STATE_FILE = "starting_state_v2.json"
BEAT_LIST_FILE = "beat_list_v2.json"


def _load_json(path: Path) -> Any:
    """Load JSON from disk / 从磁盘读取 JSON"""
    return json.loads(path.read_text(encoding="utf-8"))


def _node_type_from_str(t: str) -> NodeType:
    """Parse node type string to NodeType / 将字符串解析为 NodeType"""
    t = (t or "").strip().lower()
    if t == "location":
        return NodeType.LOCATION
    if t in {"npc", "person", "people"}:
        return NodeType.NPC
    if t == "clue":
        return NodeType.CLUE
    return NodeType.ITEM


def _format_desc(payload: Dict[str, Any]) -> str:
    """Select description by LANG / 按语言选择描述"""
    en = str(payload.get("desc_en") or "").strip()
    zh = str(payload.get("desc_zh") or "").strip()
    if LANG == "zh":
        return zh or en
    return en or zh


def _load_graph_connections() -> Dict[str, List[str]]:
    """Load graph edges and convert ID edges -> source_key edges.
    读取图 edges，并将 ID edges 映射为 source_key（节点 key）edges。
    """
    g = _load_json(DATA_DIR / GRAPH_FILE)
    nodes = g.get("nodes", {})
    edges = g.get("edges", {})
    if not isinstance(nodes, dict) or not isinstance(edges, dict):
        raise ValueError("graph_full_v2.json must contain dict 'nodes' and dict 'edges'.")

    # id -> key
    id_to_key: Dict[str, str] = {}
    for nid, p in nodes.items():
        if isinstance(p, dict):
            sk = str(p.get("source_key") or p.get("name") or "").strip()
            if sk:
                id_to_key[str(nid)] = sk

    # key -> [key,...]
    conn: Dict[str, List[str]] = {}
    for from_id, to_ids in edges.items():
        from_key = id_to_key.get(str(from_id))
        if not from_key:
            continue
        out: List[str] = []
        seen = set()
        if isinstance(to_ids, list):
            for tid in to_ids:
                to_key = id_to_key.get(str(tid))
                if not to_key:
                    continue
                if to_key not in seen:
                    seen.add(to_key)
                    out.append(to_key)
        conn[from_key] = out

    return conn


def _build_default_nodes() -> List[StoryNode]:
    """Build DEFAULT_NODES from nodes_v2.json + graph_full_v2.json.
    用 nodes_v2.json + graph_full_v2.json 构建 DEFAULT_NODES。
    """
    nodes_obj = _load_json(DATA_DIR / NODES_FILE)
    if not isinstance(nodes_obj, dict):
        raise ValueError("nodes_v2.json must be dict[id -> payload].")

    conn = _load_graph_connections()

    # Build node list: prefer all nodes defined in nodes_v2.json
    # 节点集以 nodes_v2.json 为准
    key_payloads: Dict[str, Dict[str, Any]] = {}
    for _id, payload in nodes_obj.items():
        if not isinstance(payload, dict):
            continue
        name = str(payload.get("name") or payload.get("source_key") or "").strip()
        if not name:
            continue
        key_payloads[name] = payload

    out: List[StoryNode] = []
    for key, payload in sorted(key_payloads.items(), key=lambda kv: kv[0]):
        node_type = _node_type_from_str(str(payload.get("node_type") or "item"))
        tags = payload.get("tags") or []
        if not isinstance(tags, list):
            tags = []
        desc = _format_desc(payload)
        out.append(
            StoryNode(
                key=key,
                description=desc,
                node_type=node_type,
                connections=tuple(conn.get(key, [])),
                tags=tuple(str(t).strip() for t in tags if str(t).strip()),
            )
        )

    return out


def _load_default_start_keys() -> List[str]:
    obj = _load_json(DATA_DIR / START_KEYS_FILE)
    keys = obj.get("default_start_keys", [])
    if not isinstance(keys, list) or not all(isinstance(x, str) for x in keys):
        raise ValueError("default_start_keys must be list[str].")
    return keys


def _load_starting_state() -> str:
    obj = _load_json(DATA_DIR / STARTING_STATE_FILE)
    en = str(obj.get("starting_state_en") or "").strip()
    zh = str(obj.get("starting_state_zh") or "").strip()
    if LANG == "zh":
        return zh or en
    return en or zh


def _load_beats() -> List[str]:
    obj = _load_json(DATA_DIR / BEAT_LIST_FILE)
    beats = obj.get("beats", [])
    if not isinstance(beats, list):
        raise ValueError("beats must be a list.")
    out: List[str] = []
    for b in beats:
        if isinstance(b, dict):
            en = str(b.get("text_en") or "").strip()
            zh = str(b.get("text_zh") or "").strip()
            out.append((zh or en) if LANG == "zh" else (en or zh))
        elif isinstance(b, str):
            out.append(b.strip())
    if not out:
        raise ValueError("beats list is empty.")
    return out


# ============================================================
# Public constants (no fallback) / 对外常量（无回退）
# ============================================================

DEFAULT_NODES = _build_default_nodes()
DEFAULT_START_KEYS = _load_default_start_keys()
STARTING_STATE = _load_starting_state()
BEAT_LIST = _load_beats()


# ============================================================
# StoryGraph / 故事图
# ============================================================

class StoryGraph:
    """Minimal lookup/describe helper for story nodes.
    最小化图查询/描述工具。
    """

    def __init__(
        self,
        nodes: Iterable[StoryNode] | None = None,
        initial_keys: Sequence[str] | None = None,
    ) -> None:
        self.nodes: List[StoryNode] = list(nodes or DEFAULT_NODES)
        self.by_key = {node.key: node for node in self.nodes}

        defaults = initial_keys or DEFAULT_START_KEYS
        self.initial_keys = [key for key in defaults if key in self.by_key]
        if not self.initial_keys:
            self.initial_keys = list(self.by_key.keys())

    def describe(self, keys: Sequence[str]) -> str:
        lines = []
        for key in keys:
            node = self.by_key.get(key)
            if not node:
                continue
            lines.append(f"{key}: {node.description}")
        return "\n".join(lines)

    def list_connections(self, keys: Sequence[str]) -> str:
        lines = []
        for key in keys:
            node = self.by_key.get(key)
            if not node or not node.connections:
                continue
            connections = ", ".join(node.connections)
            lines.append(f"{key} -> {connections}")
        return "\n".join(lines)

    def get_node(self, key: str) -> StoryNode | None:
        return self.by_key.get(key)


def create_initial_game_state(story_graph: StoryGraph) -> GameState:
    """Create initial game state with player at first location.
    创建初始游戏状态：玩家初始位置为第一个 initial_key。
    """
    initial_location = story_graph.initial_keys[0] if story_graph.initial_keys else "Town Square"
    return GameState(
        player_location=initial_location,
        discovered_keys={initial_location},
        conversation_history=[],
        current_beat=0,
        quest_flags={},
        npc_locations={},
    )


__all__ = [
    "StoryGraph",
    "StoryNode",
    "GameState",
    "NodeType",
    "DEFAULT_START_KEYS",
    "STARTING_STATE",
    "BEAT_LIST",
    "create_initial_game_state",
]
