# test_move_tool.py
# ============================================================
# 中文：
#   pytest 测试 MoveTool：
#   - 最短路径正确（BFS）
#   - 不可达（unreachable）
#   - 规则阻断（blocked_nodes / blocked_edges）
#   - 持久化：覆盖写 state + 追加写 jsonl
#   - tool handler 兼容 sync/async（FastMCP vs Server）
#
# English:
#   pytest suite for MoveTool:
#   - BFS shortest path correctness
#   - unreachable case
#   - rule-based blocking via state
#   - persistence: overwrite state + append JSONL
#   - sync/async handler compatibility
# ============================================================

import inspect
import json
from pathlib import Path

import pytest

import server


@pytest.fixture
def map_file(tmp_path: Path) -> Path:
    """
    中文：生成一个小地图用于测试
    English: build a small test map
    Graph:
        A01 - A00 - A02
               |
              B00 - B02 - B03
    """
    data = {
        "nodes": {
            "A00": {"name": "A00"},
            "A01": {"name": "A01"},
            "A02": {"name": "A02"},
            "B00": {"name": "B00"},
            "B02": {"name": "B02"},
            "B03": {"name": "B03"},
        },
        "edges": {
            "A00": ["A01", "A02", "B00"],
            "A01": ["A00"],
            "A02": ["A00"],
            "B00": ["A00", "B02"],
            "B02": ["B00", "B03"],
            "B03": ["B02"],
        },
    }
    p = tmp_path / "map.json"
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


def run_maybe_async(result):
    """
    中文：兼容 sync/async 两种 tool 实现
    English: handle both sync and async tool handlers
    """
    if inspect.iscoroutine(result):
        import asyncio
        return asyncio.run(result)
    return result


def test_shortest_path_success(map_file: Path):
    inp = server.ShortestPathInput(
        map_file=str(map_file),
        from_id="A01",
        to_id="B03",
        state={}
    )

    out = server.shortest_path(inp)
    out = run_maybe_async(out)

    assert out.ok is True
    assert out.path == ["A01", "A00", "B00", "B02", "B03"]
    assert out.distance == 4
    assert out.new_location == "B03"


def test_unreachable_when_graph_disconnected(tmp_path: Path):
    """
    中文：构造断开图：A00 不连 B03
    English: disconnected graph => unreachable
    """
    data = {
        "nodes": {"A00": {"name": "A00"}, "B03": {"name": "B03"}},
        "edges": {"A00": [], "B03": []},
    }
    m = tmp_path / "map.json"
    m.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    inp = server.CanMoveInput(
        map_file=str(m),
        from_id="A00",
        to_id="B03",
        state={}
    )
    out = server.can_move(inp)
    out = run_maybe_async(out)

    assert out.ok is False
    assert out.blocked is not None
    assert out.blocked["reason_code"] in {"unreachable", "edge_blocked", "node_blocked"}


def test_blocked_node_rule(map_file: Path):
    """
    中文：state 阻断 B03，不允许进入
    English: block node B03 via state
    """
    inp = server.CanMoveInput(
        map_file=str(map_file),
        from_id="A00",
        to_id="B03",
        state={"blocked_nodes": ["B03"]}
    )
    out = server.can_move(inp)
    out = run_maybe_async(out)

    assert out.ok is False
    assert out.blocked is not None
    assert out.blocked["reason_code"] == "node_blocked"


def test_blocked_edge_rule(map_file: Path):
    """
    中文：阻断关键边 B02->B03，导致不可达
    English: block edge B02->B03 => unreachable under rules
    """
    inp = server.CanMoveInput(
        map_file=str(map_file),
        from_id="A01",
        to_id="B03",
        state={"blocked_edges": [["B02", "B03"], ["B03", "B02"]]}
    )
    out = server.can_move(inp)
    out = run_maybe_async(out)

    assert out.ok is False
    assert out.blocked is not None
    assert out.blocked["reason_code"] in {"edge_blocked", "unreachable"}


def test_move_persist_logs_then_writes_state(map_file: Path, tmp_path: Path):
    """
    中文：
      测试 persist=true 的“先 log 再 state”语义：
      1) JSONL 事件日志必须被写入（至少一行）
      2) state 快照必须被覆盖写（player.location 更新，version+1，last_event_id）
      3) state.last_event_id 必须等于日志中的 event_id（证明两者对齐）
      4) 日志中的 state_version_before/state_version_after 必须与 state.version 对齐

    English:
      Validate persist=true with "log-first then state":
      1) JSONL event log is written (at least one line)
      2) state snapshot is overwritten (location updated, version+1, last_event_id)
      3) state.last_event_id equals event log event_id (consistency)
      4) log state_version_before/after aligns with snapshot version
    """
    state_file = tmp_path / "world_state.json"
    log_file = tmp_path / "state_events.jsonl"

    # 初始状态 / Initial snapshot
    state_file.write_text(
        json.dumps(
            {
                "version": 0,
                "player": {"location": "A00"},
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    inp = server.MoveInput(
        map_file=str(map_file),
        from_id=None,  # rely on state_file's player.location
        to_id="A02",
        state={},
        persist=True,
        state_file=str(state_file),
        log_file=str(log_file),
        timezone_str="America/New_York",
    )

    out = server.move(inp)
    out = run_maybe_async(out)

    assert out.ok is True
    assert out.new_location == "A02"
    assert out.persisted_log is not None
    assert out.persisted_state is not None

    # ---------------------------------------------------------
    # 1) 验证日志已写入 / Event log must exist & have >= 1 line
    # ---------------------------------------------------------
    assert log_file.exists()
    lines = log_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) >= 1

    # 中文：取最后一条事件（最稳：避免未来你们可能追加多条 commit 事件）
    # English: Use the last event line (robust if you later add more events)
    event = json.loads(lines[-1])

    # 基本字段 / Basic schema checks
    assert event.get("type") == "move"
    assert isinstance(event.get("event_id"), str) and len(event["event_id"]) > 0
    assert event.get("payload", {}).get("from") == "A00"
    assert event.get("payload", {}).get("to") == "A02"
    assert event.get("payload", {}).get("ok") is True

    # ---------------------------------------------------------
    # 2) 验证 state 已覆盖写 / State snapshot overwritten correctly
    # ---------------------------------------------------------
    new_state = json.loads(state_file.read_text(encoding="utf-8"))
    assert new_state["player"]["location"] == "A02"
    assert new_state["version"] == 1
    assert isinstance(new_state.get("last_event_id"), str)

    # ---------------------------------------------------------
    # 3) 关键一致性：state.last_event_id == log.event_id
    #    Key consistency: snapshot last_event_id matches log event_id
    # ---------------------------------------------------------
    assert new_state["last_event_id"] == event["event_id"]

    # ---------------------------------------------------------
    # 4) 版本对齐 / Version alignment between log and snapshot
    # ---------------------------------------------------------
    assert event.get("state_version_before") == 0
    assert event.get("state_version_after") == 1

    # ---------------------------------------------------------
    # 5) 距离校验（fixture 中 A00 <-> A02 直连 => distance=1）
    #    Distance check (A00 directly connects to A02 in fixture => distance=1)
    # ---------------------------------------------------------
    assert event["payload"]["distance"] == 1
    assert event["payload"]["path"] == ["A00", "A02"]
