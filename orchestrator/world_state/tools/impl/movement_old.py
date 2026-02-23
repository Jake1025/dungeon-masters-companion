# orchestrator/world_state/tools/impl/movement.py
from __future__ import annotations

from typing import Any, Dict, Union

from ...story import GameState, StoryGraph, NodeType
from ..registry import tool


@tool(
    name="move_to_location",
    description="Move player to a connected location.",
    parameters={
        "type": "object",
        "properties": {
            "location_key": {"type": "string", "description": "Location key to move to"}
        },
        "required": ["location_key"],
    },
    readonly=False,
)
def move_to_location(args: Union[str, Dict[str, Any]], game_state: GameState, story_graph: StoryGraph) -> dict[str, Any]:
    """
    EN: Move player to a connected location.
        Accepts either:
          - args as dict: {"location_key": "..."} (new tool-call style)
          - args as str:  "Docks" (legacy direct-call style)
    中文：移动玩家到相邻地点。
        入参兼容两种形式：
          - dict：{"location_key": "..."}（新工具调用风格）
          - str ："Docks"（旧的直接调用风格）
    """
    if isinstance(args, str):
        location_key = args
    else:
        location_key = args["location_key"]

    node = story_graph.get_node(location_key)

    if not node:
        return {"success": False, "new_location": None, "reason": f"Location '{location_key}' does not exist."}

    if node.node_type != NodeType.LOCATION:
        return {"success": False, "new_location": None, "reason": f"'{location_key}' is not a location."}

    current_node = story_graph.get_node(game_state.player_location)
    if not current_node:
        return {"success": False, "new_location": None, "reason": "Invalid current location."}

    if location_key == game_state.player_location:
        return {"success": True, "new_location": location_key, "reason": "You are already here."}

    if location_key not in current_node.connections:
        return {"success": False, "new_location": None, "reason": f"Cannot move to {location_key}. Not connected to {game_state.player_location}."}

    game_state.player_location = location_key
    game_state.discovered_keys.add(location_key)

    return {"success": True, "new_location": location_key, "reason": f"Moved to {location_key}."}


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
    npc_key = args["npc_key"]
    new_location = args["new_location"]

    npc_node = story_graph.get_node(npc_key)
    location_node = story_graph.get_node(new_location)

    if not npc_node:
        return {"success": False, "reason": f"NPC '{npc_key}' does not exist."}

    if npc_node.node_type != NodeType.NPC:
        return {"success": False, "reason": f"'{npc_key}' is not an NPC."}

    if not location_node:
        return {"success": False, "reason": f"Location '{new_location}' does not exist."}

    if location_node.node_type != NodeType.LOCATION:
        return {"success": False, "reason": f"'{new_location}' is not a location."}

    # EN: Apply state mutation | 中文：执行状态变更
    game_state.npc_locations[npc_key] = new_location

    return {"success": True, "reason": f"{npc_key} moved to {new_location}."}