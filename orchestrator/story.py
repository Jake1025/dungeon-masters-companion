from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, List, Sequence


@dataclass(frozen=True)
class StoryNode:
    """Single story location/person/clue with lightweight connections."""

    key: str
    description: str
    connections: Sequence[str] = field(default_factory=tuple)


DEFAULT_NODES = [
    StoryNode(
        key="Copper Cup",
        description=(
            "A low-beamed harbor tavern. Lanterns swing above crowded tables, and the air smells of "
            "stew, sea-salt, and woodsmoke. The barkeep Mara watches everything from behind the counter."
        ),
        connections=("Bar Counter", "Mara", "Brin", "Edda", "Thom", "Lysa", "Stair Landing"),
    ),
    StoryNode(
        key="Bar Counter",
        description="Shelves of bottles, a till, and crates tucked beneath. A loose crate hides something wedged behind it.",
        connections=("Mara", "Hidden Scrap", "Copper Cup"),
    ),
    StoryNode(
        key="Mara",
        description="The proprietor. Married to Brin. Her wedding anniversary is April 15th. Brisk, perceptive, and inclined to help if treated respectfully.",
        connections=("Bar Counter", "Hidden Scrap", "Storeroom Door", "Brin"),
    ),
    StoryNode(
        key="Brin",
        description="Mara's husband. A weather-beaten sailor with a limp. Forgetful of his wedding anniversary date.",
        connections=("Copper Cup", "Stair Landing", "Storeroom Door", "Mara"),
    ),
    StoryNode(
        key="Edda",
        description="A scholar cataloging tavern legends, forever scribbling into a leather folio.",
        connections=("Copper Cup", "Hidden Scrap", "Storeroom Door"),
    ),
    StoryNode(
        key="Thom",
        description="An off-duty guard who prefers order and dislikes surprises upstairs.",
        connections=("Copper Cup", "Stair Landing", "Storeroom Door"),
    ),
    StoryNode(
        key="Lysa",
        description="A traveling bard tuning a battered lute, eager for new tales.",
        connections=("Copper Cup", "Hidden Scrap", "Storeroom Door"),
    ),
    StoryNode(
        key="Hidden Scrap",
        description="A grease-stained note tucked behind a loose crate: 'cellar restock / upstairs lock is our wedding anniversary date'.",
        connections=("Bar Counter", "Storeroom Door", "Mara", "Brin"),
    ),
    StoryNode(
        key="Stair Landing",
        description="A narrow staircase creaks toward the upper rooms. A rope discourages casual wanderers.",
        connections=("Copper Cup", "Thom", "Storeroom Door"),
    ),
    StoryNode(
        key="Storeroom Door",
        description="A stout oak door with a brass four-dial combination lock. The correct code is 0415.",
        connections=("Hidden Scrap", "Mara", "Stair Landing"),
    ),
]


DEFAULT_START_KEYS = ["Copper Cup", "Bar Counter", "Mara", "Brin", "Edda", "Thom", "Lysa", "Stair Landing"]

STARTING_STATE = (
    "You arrived at The Copper Cup just past dusk. The storm outside rattles the shutters, "
    "Mara keeps a wary eye on newcomers, and whispers mention a locked storeroom upstairs."
)

BEAT_LIST = [
    "Set the tavern mood and introduce at least one patron.",
    "Surface a hint about the locked upstairs room.",
    "Discover the hidden scrap with the combination clue.",
    "Use the code to open the storeroom door.",
]


class StoryGraph:
    """Minimal lookup/describe helper for story nodes."""

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

    def upsert_node(self, node: StoryNode) -> StoryNode:
        """
        Add a node to the graph or merge new connections/description into an existing one.
        Connections are stored symmetrically but the caller should ensure reciprocity.
        """
        existing = self.by_key.get(node.key)
        if existing:
            merged_connections = sorted(set(existing.connections) | set(node.connections))
            description = node.description or existing.description
            merged = StoryNode(key=existing.key, description=description, connections=tuple(merged_connections))
            for idx, current in enumerate(self.nodes):
                if current.key == node.key:
                    self.nodes[idx] = merged
                    break
        else:
            merged = StoryNode(key=node.key, description=node.description, connections=tuple(node.connections))
            self.nodes.append(merged)

        self.by_key[node.key] = merged
        return merged

    def upsert_nodes(self, nodes: Iterable[StoryNode]) -> List[StoryNode]:
        merged: List[StoryNode] = []
        for node in nodes:
            merged.append(self.upsert_node(node))
        return merged


__all__ = ["StoryGraph", "StoryNode", "DEFAULT_START_KEYS", "STARTING_STATE", "BEAT_LIST"]
