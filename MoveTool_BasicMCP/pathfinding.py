# pathfinding.py
# ============================================================
# 中文：
#   最短路径搜索（默认 BFS），并支持“规则钩子（rule hook）”过滤不可走的边/点。
#   规则完全确定性：从 state 读取 blocked_nodes/blocked_edges 等。
#
# English:
#   Shortest path search (BFS by default) with a deterministic rule hook.
#   Rules are enforced by reading blocked_nodes/blocked_edges from state.
# ============================================================

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

from graph_store import Graph


@dataclass(frozen=True)
class Blocked:
    """
    中文：阻断原因结构化表示
    English: Structured blocked reason
    """
    reason_code: str
    message: str
    at: str  # node_id or "A00->B00"


@dataclass(frozen=True)
class PathResult:
    """
    中文：最短路径结果
    English: Shortest path result
    """
    ok: bool
    path: List[str]
    distance: int
    blocked: Optional[Blocked] = None


def default_can_traverse(src: str, dst: str, state: Dict[str, Any]) -> Tuple[bool, Optional[Blocked]]:
    """
    中文：
      默认规则（你可以替换/扩展）：
      - state["blocked_nodes"] = ["B03", ...]  -> 禁止进入这些节点
      - state["blocked_edges"] = [["A00","B00"], ["B00","A00"]] -> 禁止走这些边
    English:
      Default rule hook (replace/extend as needed):
      - state["blocked_nodes"] blocks entering nodes
      - state["blocked_edges"] blocks traversing edges
    """
    blocked_nodes = set(state.get("blocked_nodes") or [])
    if dst in blocked_nodes:
        return False, Blocked(
            reason_code="node_blocked",
            message=f"Node '{dst}' is blocked by rules/state.",
            at=dst,
        )

    blocked_edges = state.get("blocked_edges") or []
    # Normalize edge list to set of tuples
    be = set()
    for e in blocked_edges:
        if isinstance(e, (list, tuple)) and len(e) == 2:
            be.add((str(e[0]), str(e[1])))

    if (src, dst) in be:
        return False, Blocked(
            reason_code="edge_blocked",
            message=f"Edge '{src}->{dst}' is blocked by rules/state.",
            at=f"{src}->{dst}",
        )

    return True, None


def shortest_path_bfs(
    graph: Graph,
    start: str,
    goal: str,
    *,
    state: Optional[Dict[str, Any]] = None,
    can_traverse: Optional[Callable[[str, str, Dict[str, Any]], Tuple[bool, Optional[Blocked]]]] = None,
) -> PathResult:
    """
    中文：BFS 求无权图最短路径，并结合规则过滤不可走边/点
    English: BFS shortest path on an unweighted graph with rule-aware filtering
    """
    state = dict(state or {})
    can_traverse = can_traverse or default_can_traverse

    if start == goal:
        return PathResult(ok=True, path=[start], distance=0)

    # BFS queue holds current node
    q = deque([start])
    parent: Dict[str, Optional[str]] = {start: None}

    # 中文：记录遇到的第一条阻断原因（用于返回更可解释的失败原因）
    # English: record first observed blocked reason for explainability
    first_blocked: Optional[Blocked] = None

    while q:
        cur = q.popleft()
        for nxt in graph.neighbors(cur):
            if nxt in parent:
                continue

            ok, blocked = can_traverse(cur, nxt, state)
            if not ok:
                if first_blocked is None and blocked is not None:
                    first_blocked = blocked
                continue

            parent[nxt] = cur
            if nxt == goal:
                path = _reconstruct_path(parent, goal)
                return PathResult(ok=True, path=path, distance=len(path) - 1)

            q.append(nxt)

    # Not found
    if first_blocked is not None:
        return PathResult(ok=False, path=[], distance=-1, blocked=first_blocked)

    return PathResult(
        ok=False,
        path=[],
        distance=-1,
        blocked=Blocked(
            reason_code="unreachable",
            message=f"No path from '{start}' to '{goal}' under current rules.",
            at=f"{start}->{goal}",
        ),
    )


def _reconstruct_path(parent: Dict[str, Optional[str]], goal: str) -> List[str]:
    """
    中文：从 parent 指针回溯出路径
    English: reconstruct path by backtracking parent pointers
    """
    out: List[str] = []
    cur: Optional[str] = goal
    while cur is not None:
        out.append(cur)
        cur = parent.get(cur)
    out.reverse()
    return out
