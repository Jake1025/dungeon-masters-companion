# orchestrator/world_state/tools.py
from typing import Any
from .story import GameState, StoryGraph, NodeType
import json


def check_can_interact(entity_key: str, game_state: GameState, story_graph: StoryGraph) -> dict[str, Any]:
    """Check if player can interact with an entity."""
    node = story_graph.get_node(entity_key)
    
    if not node:
        return {
            "success": False,
            "can_interact": False,
            "reason": f"Entity '{entity_key}' does not exist."
        }
    
    player_loc = game_state.player_location
    
    if node.node_type == NodeType.LOCATION:
        current_node = story_graph.get_node(player_loc)
        if not current_node:
            return {"success": False, "can_interact": False, "reason": "Invalid player location"}
        
        if entity_key == player_loc:
            return {
                "success": True,
                "can_interact": True,
                "entity_type": "location",
                "reason": "You are already at this location."
            }
        
        if entity_key in current_node.connections:
            return {
                "success": True,
                "can_interact": True,
                "entity_type": "location",
                "reason": f"{entity_key} is accessible from here."
            }
        
        return {
            "success": True,
            "can_interact": False,
            "entity_type": "location",
            "reason": f"{entity_key} is not connected to {player_loc}."
        }
    
    elif node.node_type == NodeType.NPC:
        npc_location = game_state.npc_locations.get(entity_key)
        if npc_location is None:
            npc_location = node.connections[0] if node.connections else None
        
        if npc_location == player_loc:
            return {
                "success": True,
                "can_interact": True,
                "entity_type": "npc",
                "reason": f"{entity_key} is here."
            }
        
        return {
            "success": True,
            "can_interact": False,
            "entity_type": "npc",
            "reason": f"{entity_key} is at {npc_location}."
        }
    
    elif node.node_type in (NodeType.ITEM, NodeType.CLUE):
        entity_location = node.connections[0] if node.connections else None
        
        if entity_location == player_loc:
            return {
                "success": True,
                "can_interact": True,
                "entity_type": node.node_type.value,
                "reason": f"{entity_key} is here."
            }
        
        return {
            "success": True,
            "can_interact": False,
            "entity_type": node.node_type.value,
            "reason": f"{entity_key} is at {entity_location}."
        }
    
    return {"success": False, "can_interact": False, "reason": "Unknown entity type"}


def move_to_location(location_key: str, game_state: GameState, story_graph: StoryGraph) -> dict[str, Any]:
    """Move player to a new location."""
    node = story_graph.get_node(location_key)
    
    if not node:
        return {
            "success": False,
            "new_location": None,
            "reason": f"Location '{location_key}' does not exist."
        }
    
    if node.node_type != NodeType.LOCATION:
        return {
            "success": False,
            "new_location": None,
            "reason": f"'{location_key}' is not a location."
        }
    
    current_node = story_graph.get_node(game_state.player_location)
    if not current_node:
        return {"success": False, "new_location": None, "reason": "Invalid current location."}
    
    if location_key == game_state.player_location:
        return {
            "success": True,
            "new_location": location_key,
            "reason": "You are already here."
        }
    
    if location_key not in current_node.connections:
        return {
            "success": False,
            "new_location": None,
            "reason": f"Cannot move to {location_key}. Not connected to {game_state.player_location}."
        }
    
    # Move the player
    game_state.player_location = location_key
    game_state.discovered_keys.add(location_key)
    
    return {
        "success": True,
        "new_location": location_key,
        "reason": f"Moved to {location_key}."
    }


def get_current_context(game_state: GameState, story_graph: StoryGraph) -> dict[str, Any]:
    """Get information about player's current location."""
    current_node = story_graph.get_node(game_state.player_location)
    
    if not current_node:
        return {
            "location": game_state.player_location,
            "description": "Unknown location",
            "connected_locations": [],
            "npcs_here": [],
            "items_here": []
        }
    
    # Find NPCs at this location
    npcs_here = []
    for node in story_graph.nodes:
        if node.node_type == NodeType.NPC:
            npc_location = game_state.npc_locations.get(node.key)
            if npc_location is None:
                npc_location = node.connections[0] if node.connections else None
            if npc_location == game_state.player_location:
                npcs_here.append(node.key)
    
    # Find items/clues at this location
    items_here = []
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
        "items_here": items_here
    }


def move_npc(npc_key: str, new_location: str, game_state: GameState, story_graph: StoryGraph) -> dict[str, Any]:
    """Move an NPC to a new location (DM tool)."""
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
    
    game_state.npc_locations[npc_key] = new_location
    
    return {
        "success": True,
        "reason": f"{npc_key} moved to {new_location}."
    }


# Read-only tools for validation
VALIDATE_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "check_can_interact",
            "description": "Check if player can interact with an entity. Use this before narrating any interaction.",
            "parameters": {
                "type": "object",
                "properties": {
                    "entity_key": {
                        "type": "string",
                        "description": "Entity key to check (e.g., 'Mitch', 'Town Square')"
                    }
                },
                "required": ["entity_key"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_current_context",
            "description": "Get details about player's current location.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    }
]

# All tools including state-mutating ones for narration
TOOL_DEFINITIONS = [
    *VALIDATE_TOOLS,  # Include the read-only tools
    {
        "type": "function",
        "function": {
            "name": "move_to_location",
            "description": "Move player to a connected location.",
            "parameters": {
                "type": "object",
                "properties": {
                    "location_key": {
                        "type": "string",
                        "description": "Location key to move to"
                    }
                },
                "required": ["location_key"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "move_npc",
            "description": "Move an NPC to a different location (DM only, for story progression).",
            "parameters": {
                "type": "object",
                "properties": {
                    "npc_key": {"type": "string", "description": "NPC key"},
                    "new_location": {"type": "string", "description": "Destination location"}
                },
                "required": ["npc_key", "new_location"]
            }
        }
    }
]


def execute_tool(tool_name: str, arguments: dict[str, Any], game_state: GameState, story_graph: StoryGraph) -> dict[str, Any]:
    """Execute a tool by name."""
    if tool_name == "check_can_interact":
        return check_can_interact(arguments["entity_key"], game_state, story_graph)
    elif tool_name == "move_to_location":
        return move_to_location(arguments["location_key"], game_state, story_graph)
    elif tool_name == "get_current_context":
        return get_current_context(game_state, story_graph)
    elif tool_name == "move_npc":
        return move_npc(arguments["npc_key"], arguments["new_location"], game_state, story_graph)
    else:
        return {"success": False, "reason": f"Unknown tool: {tool_name}"}

__all__ = ["check_can_interact", "move_to_location", "get_current_context", "move_npc", 
           "TOOL_DEFINITIONS", "VALIDATE_TOOLS", "execute_tool"]