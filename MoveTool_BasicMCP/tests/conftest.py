# tests/conftest.py
# ============================================================
# 中文：
#   pytest 公共 fixtures（tests/ 下所有测试可用）：
#   - run_dir / artifact_dir: 保存测试产物，避免覆盖历史
#   - map_file: 生成一个小型测试地图（unit tests）
#   - location_index_file: 生成一个小型 location_index（unit tests）
#   - real_map_file / real_location_index_file: 使用 data/ 下真实文件（e2e）
#   - reachable_pairs: 从真实地图里找若干“可达”点对（用于多轮 e2e）
#
# English:
#   Shared pytest fixtures for all tests under tests/:
#   - run_dir / artifact_dir: artifacts without overwriting history
#   - map_file / location_index_file: small synthetic data for unit tests
#   - real_*: real data from data/ for e2e tests
#   - reachable_pairs: several reachable pairs from real graph for parametrized e2e
# ============================================================

from __future__ import annotations

import os
import sys
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple
import pytest


# ---------- Ensure project root is importable / 确保可 import server 等 ----------
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# ---------- Artifact dirs / 产物目录 ----------
@pytest.fixture(scope="session")
def run_dir() -> Path:
    """
    中文：每次 pytest session 一个 run 目录（不覆盖历史）
    English: One run directory per pytest session (no overwrite)
    """
    base = ROOT / "tests_artifacts"

    run_id = os.getenv("PYTEST_RUN_ID")
    if not run_id:
        run_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    d = base / f"run_{run_id}"
    d.mkdir(parents=True, exist_ok=True)
    return d


@pytest.fixture
def artifact_dir(request, run_dir: Path) -> Path:
    """
    中文：每个测试函数一个子目录
    English: One subdir per test function
    """
    d = run_dir / request.node.name
    d.mkdir(parents=True, exist_ok=True)
    return d


# ---------- Small synthetic map / 小型测试地图 ----------
@pytest.fixture
def map_file(tmp_path: Path) -> Path:
    """
    中文：生成一个小型连通图，用于 shortest_path / move 的单测
    English: Create a small connected graph for unit tests
    """
    data = {
        "nodes": {
            "A00": {"name": "A00"},
            "A01": {"name": "A01"},
            "A02": {"name": "A02"},
            "B02": {"name": "B02"},
            "B03": {"name": "B03"},
        },
        "edges": {
            "A00": ["A01"],
            "A01": ["A00", "A02", "B02"],
            "A02": ["A01"],
            "B02": ["A01", "B03"],
            "B03": ["B02"],
        },
    }
    p = tmp_path / "map.json"
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


@pytest.fixture
def location_index_file(tmp_path: Path) -> Path:
    """
    中文：生成一个最小 location_index.json（含中文成语式短描述）
    English: Minimal location_index.json with short CN/EN descriptions
    """
    data = {
        "version": 1,
        "locations": {
            "A00": {"name_en": "A00", "name_zh": "甲零零", "desc_zh": "初来乍到", "desc_en": "starting point"},
            "A01": {"name_en": "A01", "name_zh": "甲零一", "desc_zh": "四通八达", "desc_en": "crossroads"},
            "A02": {"name_en": "A02", "name_zh": "甲零二", "desc_zh": "柳暗花明", "desc_en": "a new turn"},
            "B02": {"name_en": "B02", "name_zh": "乙零二", "desc_zh": "暗流涌动", "desc_en": "under-current"},
            "B03": {"name_en": "B03", "name_zh": "乙零三", "desc_zh": "山穷水尽", "desc_en": "dead end"},
        },
    }
    p = tmp_path / "location_index.json"
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


# ---------- Real data files / 真实数据文件 ----------
@pytest.fixture(scope="session")
def real_map_file() -> Path:
    """
    中文：使用 MoveTool_BasicMCP/data/map.json
    English: Use real map.json under data/
    """
    p = ROOT / "data" / "map.json"
    if not p.exists():
        raise FileNotFoundError(f"real_map_file not found: {p}")
    return p


@pytest.fixture(scope="session")
def real_location_index_file() -> Path:
    """
    中文：使用 MoveTool_BasicMCP/data/location_index.json
    English: Use real location_index.json under data/
    """
    p = ROOT / "data" / "location_index.json"
    if not p.exists():
        raise FileNotFoundError(f"real_location_index_file not found: {p}")
    return p


# ---------- Reachable pairs for parametrized e2e / e2e 可达点对 ----------
def _load_graph(map_path: Path) -> Dict[str, List[str]]:
    obj = json.loads(map_path.read_text(encoding="utf-8"))
    edges = obj.get("edges", {})
    # ensure list
    g = {k: list(v or []) for k, v in edges.items()}
    return g


def _bfs_path(g: Dict[str, List[str]], start: str, goal: str) -> List[str] | None:
    from collections import deque
    if start == goal:
        return [start]
    q = deque([start])
    prev = {start: None}
    while q:
        cur = q.popleft()
        for nxt in g.get(cur, []):
            if nxt in prev:
                continue
            prev[nxt] = cur
            if nxt == goal:
                # reconstruct
                path = [goal]
                p = cur
                while p is not None:
                    path.append(p)
                    p = prev[p]
                path.reverse()
                return path
            q.append(nxt)
    return None


@pytest.fixture(scope="session")
def reachable_pairs(real_map_file: Path) -> List[Tuple[str, str, List[str]]]:
    """
    中文：从真实地图里挑出若干对“可达”的 from/to，并给出期望 path（用于多轮 e2e）
    English: Pick several reachable from/to pairs from the real map and provide expected paths
    """
    g = _load_graph(real_map_file)
    nodes = sorted(g.keys())
    pairs: List[Tuple[str, str, List[str]]] = []

    # 简单策略：按顺序扫描，找到前 N 对可达点对
    # Simple strategy: scan pairs and collect first N reachable ones
    N = 6
    for i in range(len(nodes)):
        for j in range(len(nodes)):
            if i == j:
                continue
            a, b = nodes[i], nodes[j]
            path = _bfs_path(g, a, b)
            if path and len(path) >= 2:
                pairs.append((a, b, path))
                if len(pairs) >= N:
                    return pairs

    if not pairs:
        raise RuntimeError("No reachable pairs found in real map.json (graph may be empty)")
    return pairs
