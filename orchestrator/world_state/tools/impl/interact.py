# orchestrator/world_state/tools/impl/interact.py
from __future__ import annotations

from typing import Any, Dict

from ...story import GameState, StoryGraph, NodeType
from ..registry import tool


@tool(
    name="check_can_interact",
    description="Check if player can interact with an entity. Use this before narrating any interaction.",
    parameters={
        "type": "object",
        "properties": {
            "entity_key": {
                "type": "string",
                "description": "Entity key to check (e.g., 'Mitch', 'Town Square')",
            }
        },
        "required": ["entity_key"],
    },
    readonly=True,
)
def check_can_interact(
    args: Dict[str, Any],
    game_state: GameState,
    story_graph: StoryGraph,
) -> Dict[str, Any]:
    """
    EN: Validate whether the player can interact with a target entity.
        - LOCATION: must be current location or connected location
        - NPC: must be at player's location (consider dynamic npc_locations first)
        - ITEM/CLUE: must be located at player's location
    中文：校验玩家是否能与目标实体交互。
        - 地点：必须是当前地点或相邻可达地点
        - NPC：必须在玩家当前位置（优先读取 npc_locations 动态位置）
        - 物品/线索：必须在玩家当前位置
    """
    entity_key = args["entity_key"]
    node = story_graph.get_node(entity_key)

    if not node:
        return {
            "success": False,
            "can_interact": False,
            "reason": f"Entity '{entity_key}' does not exist.",
        }

    player_loc = game_state.player_location

    # -------------------------
    # LOCATION
    # -------------------------
    if node.node_type == NodeType.LOCATION:
        current_node = story_graph.get_node(player_loc)
        if not current_node:
            return {"success": False, "can_interact": False, "reason": "Invalid player location"}

        if entity_key == player_loc:
            return {
                "success": True,
                "can_interact": True,
                "entity_type": "location",
                "reason": "You are already at this location.",
            }

        if entity_key in current_node.connections:
            return {
                "success": True,
                "can_interact": True,
                "entity_type": "location",
                "reason": f"{entity_key} is accessible from here.",
            }

        return {
            "success": True,
            "can_interact": False,
            "entity_type": "location",
            "reason": f"{entity_key} is not connected to {player_loc}.",
        }

    # -------------------------
    # NPC
    # -------------------------
    if node.node_type == NodeType.NPC:
        # EN: npc_locations overrides static first-connection location
        # 中文：npc_locations 动态位置优先于静态 connections[0]
        npc_location = game_state.npc_locations.get(entity_key)
        if npc_location is None:
            npc_location = node.connections[0] if node.connections else None

        if npc_location == player_loc:
            return {
                "success": True,
                "can_interact": True,
                "entity_type": "npc",
                "reason": f"{entity_key} is here.",
            }

        return {
            "success": True,
            "can_interact": False,
            "entity_type": "npc",
            "reason": f"{entity_key} is at {npc_location}.",
        }

    # -------------------------
    # ITEM / CLUE
    # -------------------------
    if node.node_type in (NodeType.ITEM, NodeType.CLUE):
        entity_location = node.connections[0] if node.connections else None

        if entity_location == player_loc:
            return {
                "success": True,
                "can_interact": True,
                "entity_type": node.node_type.value,
                "reason": f"{entity_key} is here.",
            }

        return {
            "success": True,
            "can_interact": False,
            "entity_type": node.node_type.value,
            "reason": f"{entity_key} is at {entity_location}.",
        }

    return {"success": False, "can_interact": False, "reason": "Unknown entity type"}