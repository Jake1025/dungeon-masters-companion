# test_move_tool.py
# ============================================================
# 中文：MoveTool_BasicMCP 的 pytest 测试
# English: pytest tests for MoveTool_BasicMCP
# ============================================================

from __future__ import annotations

import json
from pathlib import Path

import pytest

import server

import shutil


# ------------------------------------------------------------
# Fixtures / 固件
# ------------------------------------------------------------


#@pytest.fixture
def artifact_dir(request) -> Path:
    """
    中文：每个测试函数一个独立产物目录（避免互相污染）
    English: One artifact subdirectory per test (no cross-test pollution)
    """
    base = Path(__file__).resolve().parent / "tests_artifacts"
    test_dir = base / request.node.name

    if test_dir.exists():
        shutil.rmtree(test_dir)
    test_dir.mkdir(parents=True, exist_ok=True)

    return test_dir


#@pytest.fixture
def map_file(artifact_dir: Path) -> Path:
    """
    中文：
      生成一个可用的测试地图 map.json，并保存到 MCP 文件夹下的 tests_artifacts/<testname>/ 中。
      A00-A01-A02 与 B00-B01-B02-B03，并用 A02-B02 作为桥连接。

    English:
      Build a test map.json under tests_artifacts/<testname>/.
      Two rows connected by a bridge A02<->B02.
    """
    data = {
        "nodes": {
            "A00": {"name": "A00"},
            "A01": {"name": "A01"},
            "A02": {"name": "A02"},
            "B00": {"name": "B00"},
            "B01": {"name": "B01"},
            "B02": {"name": "B02"},
            "B03": {"name": "B03"},
        },
        "edges": {
            "A00": ["A01"],
            "A01": ["A00", "A02"],
            "A02": ["A01", "B02"],
            "B00": ["B01"],
            "B01": ["B00", "B02"],
            "B02": ["B01", "B03", "A02"],
            "B03": ["B02"],
        },
    }
    m = artifact_dir / "map.json"
    m.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return m


#@pytest.fixture
def location_index_file(artifact_dir: Path) -> Path:
    """
    中文：最小 location_index.json（只要 name/desc 字段即可），同样写到 artifact_dir 中。
    English: minimal location_index.json written into artifact_dir.
    """
    idx = {
        "A00": {"name": "A00", "desc_zh": "起点", "desc_en": "start"},
        "A01": {"name": "A01"},
        "A02": {"name": "A02"},
        "B00": {"name": "B00"},
        "B01": {"name": "B01"},
        "B02": {"name": "B02"},
        "B03": {"name": "B03"},
    }
    p = artifact_dir / "location_index.json"
    p.write_text(json.dumps(idx, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


# ------------------------------------------------------------
# Tests / 测试
# ------------------------------------------------------------

def test_shortest_path_success(map_file: Path, location_index_file: Path):
    """
    中文：最短路成功 A01 -> B03
    English: shortest path success A01 -> B03
    """
    inp = server.MoveInput(
        map_file=str(map_file),
        location_index_file=str(location_index_file),
        from_id="A01",
        to_id="B03",
        state={},
        persist=False,
    )

    out = server.move(inp)

    assert out.ok is True
    assert out.from_id == "A01"
    assert out.to_id == "B03"
    assert out.new_location == "B03"
    assert out.path[0] == "A01" and out.path[-1] == "B03"
    assert out.distance == len(out.path) - 1


def test_unreachable_when_graph_disconnected(tmp_path: Path, location_index_file: Path):
    """
    中文：构造断开图 => 不可达
    English: disconnected graph => unreachable
    """
    data = {
        "nodes": {"A00": {"name": "A00"}, "B03": {"name": "B03"}},
        "edges": {"A00": [], "B03": []},
    }
    m = tmp_path / "map.json"
    m.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    inp = server.MoveInput(
        map_file=str(m),
        location_index_file=str(location_index_file),
        from_id="A00",
        to_id="B03",
        state={},
        persist=False,
    )

    out = server.move(inp)
    assert out.ok is False
    assert out.new_location == "A00"
    assert out.blocked is not None
    # 中文：具体 reason_code 取决于你们 pathfinding.py 的实现
    # English: reason_code depends on your pathfinding.py implementation
    # 这里至少确保有 reason_code 与 message
    assert "reason_code" in out.blocked
    assert "message" in out.blocked


def test_blocked_node_rule(map_file: Path, location_index_file: Path):
    """
    中文：state 阻断 B03，不允许进入
    English: block node B03 via state
    """
    inp = server.MoveInput(
        map_file=str(map_file),
        location_index_file=str(location_index_file),
        from_id="A00",
        to_id="B03",
        state={"blocked_nodes": ["B03"]},
        persist=False,
    )

    out = server.move(inp)
    assert out.ok is False
    assert out.new_location == "A00"
    assert out.blocked is not None
    assert out.blocked["reason_code"] in {"node_blocked", "blocked", "forbidden"}


def test_blocked_edge_rule(map_file: Path, location_index_file: Path):
    """
    中文：阻断关键边 B02->B03（和反向），导致不可达/或被规则阻断
    English: block edge B02->B03 (and reverse) => unreachable/blocked under rules
    """
    inp = server.MoveInput(
        map_file=str(map_file),
        location_index_file=str(location_index_file),
        from_id="A01",
        to_id="B03",
        state={"blocked_edges": [["B02", "B03"], ["B03", "B02"]]},
        persist=False,
    )

    out = server.move(inp)
    assert out.ok is False
    assert out.new_location == "A01"
    assert out.blocked is not None
    assert out.blocked["reason_code"] in {"edge_blocked", "unreachable", "blocked"}


def test_move_persist_logs_then_writes_state(map_file, location_index_file, artifact_dir):

    """
    中文：
      测试 persist=true 的“先 log 再 state”语义：
      1) JSONL 事件日志必须写入至少一行
      2) state 快照必须覆盖写（player.location 更新，version+1，last_event_id）
      3) state.last_event_id 必须等于日志中的 event_id
      4) 日志 state_version_before/state_version_after 与 state.version 对齐

    English:
      Validate persist=true with "log-first then state":
      1) event log written
      2) snapshot overwritten (location/version/last_event_id)
      3) last_event_id equals log event_id
      4) log before/after versions align with snapshot version
    """
    state_file = artifact_dir / "world_state.json"
    log_file = artifact_dir / "state_events.jsonl"

    # Initial snapshot / 初始状态
    state_file.write_text(
        json.dumps({"version": 0, "player": {"location": "A00"}}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    inp = server.MoveInput(
        map_file=str(map_file),
        location_index_file=str(location_index_file),
        from_id=None,  # rely on snapshot player.location
        to_id="A02",
        state={},
        persist=True,
        state_file=str(state_file),
        log_file=str(log_file),
        timezone_str="America/New_York",
    )

    out = server.move(inp)
    assert out.persisted_log is not None
    assert out.persisted_state is not None

    # 1) Log exists / 日志必须存在
    assert log_file.exists()
    lines = log_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) >= 1

    last_event = json.loads(lines[-1])
    # 2) Snapshot updated / 快照必须更新
    snap = json.loads(state_file.read_text(encoding="utf-8"))
    assert snap["player"]["location"] == out.new_location
    assert snap["version"] == 1
    assert "last_event_id" in snap

    # 3) event_id alignment / event_id 对齐
    assert snap["last_event_id"] == last_event["event_id"] == out.event_id

    # 4) version alignment / 版本对齐
    assert last_event["state_version_before"] == 0
    assert last_event["state_version_after"] == 1
