# test_mcp_e2e.py
# ============================================================
# 中文：
#   端到端（E2E）测试 Move MCP Tool：
#   - 使用 MoveTool_BasicMCP/data 目录中的真实 map.json / location_index.json
#   - 自动从真实地图中挑选一对“可达”的起点/终点，避免写死节点 id
#   - persist=True 时验证“先 log 再 state”语义与一致性
#   - 所有测试生成文件保存到 MoveTool_BasicMCP/tests_artifacts/
#
# English:
#   End-to-end tests for Move MCP Tool:
#   - Use real data/map.json and data/location_index.json
#   - Automatically pick a reachable from/to pair from the real map
#   - Verify persist=True "log-first then state" semantics and consistency
#   - Save all artifacts under MoveTool_BasicMCP/tests_artifacts/
# ============================================================

from __future__ import annotations

import json
import shutil
from collections import deque
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import os
import pytest
import server

import random
from datetime import datetime

# ------------------------------------------------------------
# Helpers / 辅助函数
# ------------------------------------------------------------

def _load_map_json(map_path: Path) -> Tuple[Dict[str, dict], Dict[str, List[str]]]:
    """
    中文：读取 data/map.json，返回 nodes 与 edges
    English: Load data/map.json and return nodes & edges
    """
    obj = json.loads(map_path.read_text(encoding="utf-8"))
    nodes = obj.get("nodes") or {}
    edges = obj.get("edges") or {}

    if not isinstance(nodes, dict) or not nodes:
        raise AssertionError("map.json missing non-empty 'nodes' dict")
    if not isinstance(edges, dict) or not edges:
        raise AssertionError("map.json missing non-empty 'edges' dict")

    # normalize adjacency to list[str]
    norm_edges: Dict[str, List[str]] = {}
    for k, v in edges.items():
        if isinstance(v, list):
            norm_edges[str(k)] = [str(x) for x in v]
        else:
            norm_edges[str(k)] = []
    return nodes, norm_edges


def _bfs_find_any_reachable_pair(edges: Dict[str, List[str]]) -> Optional[Tuple[str, str, List[str]]]:
    """
    中文：
      从真实图中找任意一对“不同节点且可达”的 (start, goal, path)。
      若图只有孤立点，返回 None。

    English:
      Find any reachable pair (start != goal) with a BFS path.
      Return None if graph is totally disconnected.
    """
    all_nodes = list(edges.keys())
    if len(all_nodes) < 2:
        return None

    # Try BFS from each node until we find a different reachable goal.
    for start in all_nodes:
        # BFS tree
        q = deque([start])
        parent = {start: None}

        while q:
            cur = q.popleft()
            for nxt in edges.get(cur, []):
                if nxt not in parent:
                    parent[nxt] = cur
                    q.append(nxt)

        # pick any goal reachable != start
        for goal in parent.keys():
            if goal != start:
                # reconstruct path
                path = []
                p = goal
                while p is not None:
                    path.append(p)
                    p = parent[p]
                path.reverse()
                return start, goal, path

    return None

def find_reachable_pairs(edges: Dict[str, List[str]], max_pairs: int = 5):
    """
    中文：
      找多组可达 (start, goal, path)，并尽量保证 goal 不重复，
      这样多轮测试会覆盖不同目的地，而不是老跑到同一个点（比如 L002）。

    English:
      Find multiple reachable (start, goal, path) pairs, preferring unique goals
      so multi-round tests cover different destinations.
    """
    pairs: List[Tuple[str, str, List[str]]] = []
    used_goals = set()
    used_pairs = set()

    for start in edges.keys():
        # BFS from start
        q = deque([start])
        parent = {start: None}

        while q:
            cur = q.popleft()
            for nxt in edges.get(cur, []):
                if nxt not in parent:
                    parent[nxt] = cur
                    q.append(nxt)

        # collect reachable goals except start
        goals = [g for g in parent.keys() if g != start]

        # 关键：先挑“没用过的 goal”，再挑剩下的
        goals_sorted = sorted(goals, key=lambda g: (g in used_goals, g))

        for goal in goals_sorted:
            key = (start, goal)
            if key in used_pairs:
                continue

            # reconstruct path
            path: List[str] = []
            p = goal
            while p is not None:
                path.append(p)
                p = parent[p]
            path.reverse()

            pairs.append((start, goal, path))
            used_pairs.add(key)
            used_goals.add(goal)

            if len(pairs) >= max_pairs:
                return pairs

    return pairs


def _project_data_dir() -> Path:
    """
    中文：定位 MoveTool_BasicMCP/data 目录
    English: locate MoveTool_BasicMCP/data directory
    """
    base = Path(__file__).resolve().parent
    return base / "data"


# ------------------------------------------------------------
# Fixtures / 固件（产物保存到 MCP 文件夹）
# ------------------------------------------------------------



#@pytest.fixture(scope="session")
def sampled_pairs(real_map_file: Path):
    nodes, edges = _load_map_json(real_map_file)
    all_pairs = find_reachable_pairs(edges, max_pairs=50)

    random.seed(42)  # 固定 seed，保证可复现
    return random.sample(all_pairs, k=min(5, len(all_pairs)))


#@pytest.fixture(scope="session")
def reachable_pairs(real_map_file: Path):
    """
    中文：从真实 map.json 中生成若干可达地点对
    English: Generate reachable pairs from real map.json
    """
    nodes, edges = _load_map_json(real_map_file)
    pairs = find_reachable_pairs(edges, max_pairs=5)
    if not pairs:
        pytest.skip("No reachable location pairs found in real map")
    return pairs



#@pytest.fixture(scope="session")
def run_dir() -> Path:
    """
    中文：每次 pytest run 创建一个新的 run 目录（不会覆盖历史）
    English: Create a new run directory per pytest session (no overwriting)
    """
    base = Path(__file__).resolve().parent / "tests_artifacts"

    # 你也可以用 CI 的环境变量，比如 GITHUB_RUN_ID
    run_id = os.getenv("PYTEST_RUN_ID")
    if not run_id:
        run_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    d = base / f"run_{run_id}"
    d.mkdir(parents=True, exist_ok=True)
    return d


#@pytest.fixture
def artifact_dir(request, run_dir: Path) -> Path:
    """
    中文：每个测试函数一个子目录，且归属到本次 run 目录下
    English: One subdir per test under the session run directory
    """
    test_dir = run_dir / request.node.name
    test_dir.mkdir(parents=True, exist_ok=True)
    return test_dir


#@pytest.fixture(scope="session")
def real_map_file() -> Path:
    """
    中文：真实 map.json 路径（session级，避免 ScopeMismatch）
    English: real map.json path (session-scoped)
    """
    p = _project_data_dir() / "map.json"
    if not p.exists():
        raise AssertionError(f"Missing real map.json at: {p}")
    return p


#@pytest.fixture(scope="session")
def real_location_index_file() -> Path:
    """
    中文：真实 location_index.json 路径（session级）
    English: real location_index.json path (session-scoped)
    """
    p = _project_data_dir() / "location_index.json"
    if not p.exists():
        raise AssertionError(f"Missing real location_index.json at: {p}")
    return p



# ------------------------------------------------------------
# E2E Test / 端到端测试
# ------------------------------------------------------------


    """
    中文：
      使用真实 data/map.json 与 data/location_index.json 做一次端到端测试：
      1) 从真实地图中自动挑选一对可达的地点 (from, to)
      2) persist=True 触发 “先 log 再 state”
      3) 验证：
         - move 输出 ok=True、path 合法
         - log_file 写入一行事件
         - state_file 覆盖写，version+1，player.location 更新
         - state.last_event_id == log.event_id == out.event_id
         - log 的 state_version_before/after 与快照一致

    English:
      E2E test with real map/index:
      1) pick any reachable (from,to) pair automatically
      2) persist=True => "log first then state"
      3) validate output/path + log/state consistency
    """

# 跑 3 轮（你也可以改成 5、10）
@pytest.mark.parametrize("pair_index", [0, 1, 2])
def test_mcp_move_e2e_persist_real_data(
    pair_index: int,
    reachable_pairs,
    real_map_file: Path,
    real_location_index_file: Path,
    artifact_dir: Path,
):
    from_id, to_id, expected_path = reachable_pairs[pair_index]

    # （可选）调试打印，配合 -s 查看每轮选点
    # print("E2E pick:", pair_index, from_id, "->", to_id)

    state_file = artifact_dir / "world_state.json"
    log_file = artifact_dir / "state_events.jsonl"

    state_file.write_text(
        json.dumps({"version": 0, "player": {"location": from_id}}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    inp = server.MoveInput(
        map_file=str(real_map_file),
        location_index_file=str(real_location_index_file),
        from_id=None,
        to_id=to_id,
        state={},
        persist=True,
        state_file=str(state_file),
        log_file=str(log_file),
        timezone_str="America/New_York",
    )

    out = server.move(inp)

    assert out.ok is True
    assert out.from_id == from_id
    assert out.to_id == to_id
    assert out.new_location == to_id
    assert out.path[0] == from_id and out.path[-1] == to_id
    assert out.distance == len(out.path) - 1

    assert log_file.exists()
    lines = log_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) >= 1
    last_event = json.loads(lines[-1])

    snap = json.loads(state_file.read_text(encoding="utf-8"))
    assert snap["version"] == 1
    assert snap["player"]["location"] == to_id
    assert snap["last_event_id"] == out.event_id

    assert last_event["event_id"] == out.event_id
    assert last_event["state_version_before"] == 0
    assert last_event["state_version_after"] == 1
