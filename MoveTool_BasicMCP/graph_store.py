# graph_store.py
# ============================================================
# 中文：
#   负责从 JSON 文件加载“地点节点 + 连边（邻接表）”，并做基本校验。
#   - nodes: {node_id: {"name": "...", ...}}
#   - edges: {node_id: [neighbor_id, ...]}
#
# English:
#   Loads a graph (nodes + adjacency list) from a JSON file and validates it.
# ============================================================

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set


@dataclass(frozen=True)
class Node:
    """
    中文：节点对象（地点）
    English: Node object (location)
    """
    node_id: str
    name: str


@dataclass
class Graph:
    """
    中文：图对象，包含节点和邻接表
    English: Graph object containing nodes and adjacency list
    """
    nodes: Dict[str, Node]
    adj: Dict[str, List[str]]

    def has_node(self, node_id: str) -> bool:
        return node_id in self.nodes

    def neighbors(self, node_id: str) -> List[str]:
        return list(self.adj.get(node_id, []))


class GraphStore:
    """
    中文：从 map.json 加载图，并提供校验/规范化。
    English: Load a graph from map.json with validation/normalization.
    """

    def __init__(self, map_file: str | Path, *, enforce_undirected: bool = True) -> None:
        self.map_file = Path(map_file)
        self.enforce_undirected = enforce_undirected

    def load(self) -> Graph:
        """
        中文：加载并返回 Graph
        English: Load and return a Graph
        """
        data = json.loads(self.map_file.read_text(encoding="utf-8"))

        if not isinstance(data, dict):
            raise ValueError("Map JSON must be an object/dict.")

        raw_nodes = data.get("nodes", {})
        raw_edges = data.get("edges", {})

        if not isinstance(raw_nodes, dict) or not raw_nodes:
            raise ValueError("'nodes' must be a non-empty dict in map JSON.")
        if not isinstance(raw_edges, dict) or not raw_edges:
            raise ValueError("'edges' must be a non-empty dict in map JSON.")

        # ---------- Parse nodes ----------
        nodes: Dict[str, Node] = {}
        for node_id, payload in raw_nodes.items():
            if not isinstance(node_id, str) or not node_id.strip():
                raise ValueError(f"Invalid node id: {node_id}")
            if not isinstance(payload, dict):
                raise ValueError(f"Node payload must be dict for node {node_id}")

            name = str(payload.get("name", "")).strip()
            if not name:
                # 中文：如果没有 name，也允许 fallback 到 node_id
                # English: If name missing, fallback to node_id
                name = node_id

            nodes[node_id] = Node(node_id=node_id, name=name)

        # ---------- Parse edges ----------
        adj: Dict[str, List[str]] = {}
        for src, nbrs in raw_edges.items():
            if src not in nodes:
                raise ValueError(f"Edge source '{src}' not found in nodes.")
            if not isinstance(nbrs, list):
                raise ValueError(f"Edges for '{src}' must be a list.")
            clean: List[str] = []
            for dst in nbrs:
                if not isinstance(dst, str):
                    raise ValueError(f"Neighbor id must be str, got {type(dst)}")
                if dst not in nodes:
                    raise ValueError(f"Edge '{src}' -> '{dst}' points to unknown node.")
                if dst != src and dst not in clean:
                    clean.append(dst)
            adj[src] = clean

        # 中文：确保所有节点都有邻接表键（没有连边也给空列表）
        # English: Ensure every node has an adjacency entry (empty list if missing)
        for node_id in nodes.keys():
            adj.setdefault(node_id, [])

        # ---------- Optional: enforce undirected symmetry ----------
        if self.enforce_undirected:
            self._make_undirected(adj)

        return Graph(nodes=nodes, adj=adj)

    @staticmethod
    def _make_undirected(adj: Dict[str, List[str]]) -> None:
        """
        中文：将邻接表补齐为无向图（A->B 则补 B->A）
        English: Make adjacency list symmetric for undirected graphs
        """
        for src, nbrs in list(adj.items()):
            for dst in nbrs:
                if src not in adj.get(dst, []):
                    adj[dst].append(src)
