"""Minimal entity model and an Ollama-ready movement tool."""

from dataclasses import dataclass
from typing import Any, Dict, Tuple, TypedDict, List

# Map human-readable location names to simple 2D grid coordinates.
LOCATION_GRID: Dict[str, Tuple[int, int]] = {
    "Town Square": (0, 0),
    "Copper Cup": (0, 1),
    "Town Well": (1, 0),
    "Copper Mine": (1, 1),
}

@dataclass
class Location:
    name: str
    connections: List[str]  # List of (location name, distance)


@dataclass
class Entity:
    name: str
    description: str
    memory: Any
    location: str

    def location_vector(self) -> Tuple[int, int]:
        return LOCATION_GRID[self.location]

    def move_to(self, destination: str) -> Tuple[bool, str]:
        if destination not in LOCATION_GRID:
            return False, f"Unknown location '{destination}'."
        self.location = destination
        return True, f"{self.name} moved to {destination} at {LOCATION_GRID[destination]}."


# Registry so the tool can look up entities by name when called via Ollama.
ENTITY_REGISTRY: Dict[str, Entity] = {}


class LocationPayload(TypedDict):
    name: str
    vector: Tuple[int, int]


class ChangeLocationResult(TypedDict):
    success: bool
    message: str
    location: LocationPayload | None


# JSON schema Ollama expects when registering a function tool.
OLLAMA_TOOL_SPEC: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "change_location_tool",
        "description": "Move a registered entity to a named location on the grid.",
        "parameters": {
            "type": "object",
            "properties": {
                "entity_name": {
                    "type": "string",
                    "description": "Name of the registered entity to move.",
                },
                "destination": {
                    "type": "string",
                    "description": "Target location name.",
                    "enum": list(LOCATION_GRID.keys()),
                },
            },
            "required": ["entity_name", "destination"],
            "additionalProperties": False,
        },
    },
}


def register_entity(entity: Entity) -> None:
    """Register an entity so the tool can find and move it."""
    ENTITY_REGISTRY[entity.name] = entity


def change_location_tool(entity_name: str, destination: str) -> ChangeLocationResult:
    """
    Move a registered entity to a destination on the LOCATION_GRID.

    Parameters
    ----------
    entity_name: str
        The name of the entity to move (must be registered via register_entity).
    destination: str
        The target location name from LOCATION_GRID.

    Returns
    -------
    ChangeLocationResult
        success: bool - whether the move succeeded
        message: str  - human-readable status
        location: {name, vector} or None if the entity was not found
    """

    """
    if the entity is in a location that connects to the desired destination, move, if not don't move. -JM
    """


    entity = ENTITY_REGISTRY.get(entity_name)
    if entity is None:
        return {
            "success": False,
            "message": f"Entity '{entity_name}' is not registered.",
            "location": None,
        }

    success, message = entity.move_to(destination)
    return {
        "success": success,
        "message": message,
        "location": {
            "name": entity.location,
            "vector": LOCATION_GRID.get(entity.location),
        },
    }




if __name__ == "__main__":
    # Quick manual check.
    player = Entity(
        name="Player",
        description="A curious traveler.",
        memory={},
        location="Town Square",
    )
    register_entity(player)
    print(change_location_tool("Player", "Copper Cup"))
