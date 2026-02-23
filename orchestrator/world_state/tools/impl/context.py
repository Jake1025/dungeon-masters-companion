# orchestrator/world_state/tools/impl/context.py
from __future__ import annotations

from typing import Any, Dict

from ...story import GameState, StoryGraph, NodeType
from ..registry import tool


@tool(
    name="get_current_context",
    description="Get details about player's current location.",
    parameters={"type": "object", "properties": {}},
    readonly=True,
)
def get_current_context(
    args: Dict[str, Any],
    game_state: GameState,
    story_graph: StoryGraph,
) -> Dict[str, Any]:
    """
    EN: Return player's current location context:
        - description
        - connected locations
        - NPCs present
        - items/clues present
    中文：返回玩家当前环境信息：
        - 地点描述
        - 可达地点
        - 在场 NPC
        - 在场 物品/线索
    """
    current_node = story_graph.get_node(game_state.player_location)

    if not current_node:
        return {
            "location": game_state.player_location,
            "description": "Unknown location",
            "connected_locations": [],
            "npcs_here": [],
            "items_here": [],
        }

    # EN: Find NPCs at this location (dynamic overrides static)
    # 中文：查找当前位置 NPC（动态位置优先）
    npcs_here: list[str] = []
    for node in story_graph.nodes:
        if node.node_type == NodeType.NPC:
            npc_location = game_state.npc_locations.get(node.key)
            if npc_location is None:
                npc_location = node.connections[0] if node.connections else None
            if npc_location == game_state.player_location:
                npcs_here.append(node.key)

    # EN: Find items/clues at this location (static connection[0] as location anchor)
    # 中文：查找当前位置物品/线索（通常用 connections[0] 表示归属地点）
    items_here: list[str] = []
    for node in story_graph.nodes:
        if node.node_type in (NodeType.ITEM, NodeType.CLUE):
            item_location = node.connections[0] if node.connections else None
            if item_location == game_state.player_location:
                items_here.append(node.key)

    return {
        "location": game_state.player_location,
        "description": current_node.description,
        "connected_locations": list(current_node.connections),
        "npcs_here": npcs_here,
        "items_here": items_here,
    }