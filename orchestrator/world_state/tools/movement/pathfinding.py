# orchestrator/world_state/tools/movement/pathfinding.py
# ============================================================
# 中文：
#   BFS 最短路径搜索（无权图），并支持规则钩子过滤不可走边。
#
# English:
#   BFS shortest path (unweighted graph) with a deterministic rule hook.
# ============================================================

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Protocol, Tuple

from .rules import Blocked


class NeighborGraph(Protocol):
    """
    中文：只要求实现 neighbors(node) -> iterable
    English: Minimal graph protocol: neighbors(node) -> iterable
    """
    def neighbors(self, node: str) -> List[str]:
        ...


@dataclass(frozen=True)
class PathResult:
    """
    中文：路径结果
    English: Path result
    """
    ok: bool
    path: List[str]
    distance: int
    blocked: Optional[Blocked] = None


def shortest_path_bfs(
    graph: NeighborGraph,
    start: str,
    goal: str,
    *,
    state: Optional[Dict[str, Any]] = None,
    can_traverse: Optional[Callable[[str, str, Dict[str, Any]], Tuple[bool, Optional[Blocked]]]] = None,
) -> PathResult:
    """
    中文：BFS 求最短路径 + 规则过滤
    English: BFS shortest path + rule filtering
    """
    state = dict(state or {})
    if can_traverse is None:
        # 默认“全可走”
        def can_traverse(_src: str, _dst: str, _state: Dict[str, Any]) -> Tuple[bool, Optional[Blocked]]:
            return True, None

    if start == goal:
        return PathResult(ok=True, path=[start], distance=0)

    q = deque([start])
    parent: Dict[str, Optional[str]] = {start: None}

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
                path = _reconstruct(parent, goal)
                return PathResult(ok=True, path=path, distance=len(path) - 1)

            q.append(nxt)

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


def _reconstruct(parent: Dict[str, Optional[str]], goal: str) -> List[str]:
    """
    中文：回溯 parent 得到路径
    English: Reconstruct path by backtracking parent pointers
    """
    out: List[str] = []
    cur: Optional[str] = goal
    while cur is not None:
        out.append(cur)
        cur = parent.get(cur)
    out.reverse()
    return out