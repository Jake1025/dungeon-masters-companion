from __future__ import annotations

import os
from typing import List, Sequence, Tuple

import psycopg
from psycopg.rows import dict_row

from .story import StoryGraph, StoryNode


DEFAULT_PG_DSN = os.getenv("PG_DSN", "postgresql://postgres:postgres@localhost:5432/dmai")


class PostgresStorySource:
    """
    Lightweight loader for story nodes and beats backed by the story.* schema.

    This keeps the orchestrator decoupled from the MCP server runtime; it just
    reads the same tables the MCP tools expose.
    """

    def __init__(self, campaign_key: str, *, dsn: str | None = None) -> None:
        self.campaign_key = campaign_key
        self.dsn = dsn or DEFAULT_PG_DSN

    def build_graph(self, *, initial_keys: Sequence[str] | None = None) -> Tuple[StoryGraph, List[str]]:
        nodes, beats = self._fetch_full_graph()
        graph = StoryGraph(nodes=nodes, initial_keys=initial_keys)
        return graph, beats

    def fetch_node_and_neighbors(self, key: str) -> List[StoryNode]:
        """Return the requested node plus its 1-hop neighbors (undirected)."""
        with psycopg.connect(self.dsn, row_factory=dict_row, autocommit=True) as cx, cx.cursor() as cur:
            cur.execute(
                """
                SELECT n.id::text AS id, n.key, n.description
                FROM story.nodes n
                JOIN story.campaigns c ON c.id = n.campaign_id
                WHERE c.key = %s AND n.key = %s
                """,
                (self.campaign_key, key),
            )
            node_row = cur.fetchone()
            if not node_row:
                return []

            node_id = node_row["id"]
            cur.execute(
                """
                SELECT e.src_node_id::text AS src, e.dst_node_id::text AS dst
                FROM story.edges e
                JOIN story.campaigns c ON c.id = e.campaign_id
                WHERE c.key = %s AND (e.src_node_id = %s OR e.dst_node_id = %s)
                """,
                (self.campaign_key, node_id, node_id),
            )
            edges = cur.fetchall() or []

            related_ids = {node_id}
            for edge in edges:
                related_ids.add(edge["src"])
                related_ids.add(edge["dst"])

            cur.execute(
                """
                SELECT n.id::text AS id, n.key, n.description
                FROM story.nodes n
                WHERE n.id = ANY(%s)
                """,
                (list(related_ids),),
            )
            node_rows = cur.fetchall() or []

        id_to_key = {row["id"]: row["key"] for row in node_rows}
        connections = {row["key"]: set() for row in node_rows}
        for edge in edges:
            src_key = id_to_key.get(edge["src"])
            dst_key = id_to_key.get(edge["dst"])
            if not src_key or not dst_key:
                continue
            connections[src_key].add(dst_key)
            connections[dst_key].add(src_key)

        nodes = [
            StoryNode(
                key=row["key"],
                description=row["description"],
                connections=tuple(sorted(connections.get(row["key"]) or ())),
            )
            for row in node_rows
        ]
        return nodes

    # -----------------
    # Internal helpers
    # -----------------
    def _fetch_full_graph(self) -> Tuple[List[StoryNode], List[str]]:
        with psycopg.connect(self.dsn, row_factory=dict_row, autocommit=True) as cx, cx.cursor() as cur:
            cur.execute(
                """
                SELECT n.id::text AS id, n.key, n.description
                FROM story.nodes n
                JOIN story.campaigns c ON c.id = n.campaign_id
                WHERE c.key = %s
                ORDER BY n.key
                """,
                (self.campaign_key,),
            )
            node_rows = cur.fetchall() or []
            if not node_rows:
                raise ValueError(f"No nodes found for campaign '{self.campaign_key}'")

            id_to_key = {row["id"]: row["key"] for row in node_rows}
            connections = {row["key"]: set() for row in node_rows}

            cur.execute(
                """
                SELECT e.src_node_id::text AS src, e.dst_node_id::text AS dst
                FROM story.edges e
                JOIN story.campaigns c ON c.id = e.campaign_id
                WHERE c.key = %s
                """,
                (self.campaign_key,),
            )
            for edge in cur.fetchall() or []:
                src = id_to_key.get(edge["src"])
                dst = id_to_key.get(edge["dst"])
                if not src or not dst:
                    continue
                connections[src].add(dst)
                connections[dst].add(src)

            nodes = [
                StoryNode(
                    key=row["key"],
                    description=row["description"],
                    connections=tuple(sorted(connections.get(row["key"]) or ())),
                )
                for row in node_rows
            ]

            cur.execute(
                """
                SELECT b.text
                FROM story.beats b
                JOIN story.campaigns c ON c.id = b.campaign_id
                WHERE c.key = %s
                ORDER BY b.ord
                """,
                (self.campaign_key,),
            )
            beats = [row["text"] for row in cur.fetchall() or []]

        return nodes, beats


__all__ = ["PostgresStorySource"]
