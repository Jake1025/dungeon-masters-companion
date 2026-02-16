from __future__ import annotations
"""
Data-driven story module (v3).

EN: Loads nodes/edges and story constants from JSON files (no fallback).
ZH: 从 JSON 文件读取节点/边以及故事常量（无兜底）。

Language switch / 语言切换:
- Default English: STORY_LANG=en (or unset)
- Chinese: set STORY_LANG=zh
- 默认英文；如需中文，将环境变量 STORY_LANG 设为 zh。

v3 change:
- Clues are re-numbered as C001..C004 (items remain I***). Graph and index updated.
- v3：线索节点改为 C001..C004（物品仍为 I***），并已同步更新图与索引。
"""
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Iterable, List, Sequence
import json
import os

class NodeType(Enum):
    """Type of story node / 节点类型"""
    LOCATION = "location"
    NPC = "npc"
    ITEM = "item"
    CLUE = "clue"

@dataclass(frozen=True)
class StoryNode:
    """Single story node with lightweight connections.
    单个故事节点，含轻量连接。
    """
    key: str
    description: str
    node_type: NodeType
    connections: Sequence[str] = field(default_factory=tuple)
    tags: Sequence[str] = field(default_factory=tuple)

@dataclass
class GameState:
    """Mutable game state - tracks dynamic information.
    可变游戏状态：记录动态信息。
    """
    player_location: str
    discovered_keys: set[str] = field(default_factory=set)
    conversation_history: list[dict] = field(default_factory=list)
    current_beat: int = 0
    quest_flags: dict[str, bool] = field(default_factory=dict)
    npc_locations: dict[str, str] = field(default_factory=dict)

# ----------------------------
# Paths / 路径
# ----------------------------
DATA_DIR = Path(__file__).resolve().parent / "data"
NODES_FILE = "nodes_v3.json"
GRAPH_FILE = "graph_full_v3.json"
DEFAULT_KEYS_FILE = "default_start_keys_v2_fixed.json"
STARTING_STATE_FILE = "starting_state_v2_fixed.json"
BEATS_FILE = "beat_list_v2_fixed.json"

def _load_json(path: Path) -> dict:
    """Load JSON (no fallback). / 读取 JSON（无兜底）。"""
    return json.loads(path.read_text(encoding="utf-8"))

def _lang() -> str:
    """Return 'en' or 'zh'. Default 'en'. / 返回 en 或 zh，默认 en。"""
    v = (os.getenv("STORY_LANG") or "en").strip().lower()
    return "zh" if v.startswith("zh") else "en"

def _build_default_nodes() -> list[StoryNode]:
    lang = _lang()
    nodes_obj = _load_json(DATA_DIR / NODES_FILE)
    graph_obj = _load_json(DATA_DIR / GRAPH_FILE)

    id_to_key: dict[str, str] = {nid: str(n["source_key"]) for nid, n in nodes_obj.items()}

    out: list[StoryNode] = []
    for node_id, n in nodes_obj.items():
        source_key = str(n["source_key"])
        node_type = NodeType(str(n["node_type"]))
        desc = str(n["desc_zh"] if lang == "zh" else n["desc_en"])

        neighbor_ids = graph_obj["edges"][node_id]
        connections = tuple(id_to_key[x] for x in neighbor_ids)

        tags = tuple(n.get("tags") or [])
        out.append(
            StoryNode(
                key=source_key,
                description=desc,
                node_type=node_type,
                connections=connections,
                tags=tags,
            )
        )
    return out

def _load_default_start_keys() -> list[str]:
    obj = _load_json(DATA_DIR / DEFAULT_KEYS_FILE)
    return list(obj["default_start_keys"])

def _load_starting_state() -> str:
    obj = _load_json(DATA_DIR / STARTING_STATE_FILE)
    return str(obj["starting_state_zh"] if _lang() == "zh" else obj["starting_state_en"])

def _load_beats() -> list[str]:
    obj = _load_json(DATA_DIR / BEATS_FILE)
    lang = _lang()
    return [str(b["text_zh"] if lang == "zh" else b["text_en"]) for b in obj["beats"]]

DEFAULT_NODES = _build_default_nodes()
DEFAULT_START_KEYS = _load_default_start_keys()
STARTING_STATE = _load_starting_state()
BEAT_LIST = _load_beats()

class StoryGraph:
    """Minimal lookup/describe helper for story nodes.
    最小化的节点检索/描述工具。
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
            raise ValueError("DEFAULT_START_KEYS contains no valid keys in the loaded nodes.")

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
    创建初始游戏状态：玩家位于首个起始地点。
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
