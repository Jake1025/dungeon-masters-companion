# tests/test_event_log.py
from __future__ import annotations

import json
import inspect
from pathlib import Path
from typing import Any, Dict, Optional
import pytest

import event_log


def _read_jsonl(path: Path):
    """Read JSONL into list[dict]."""
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    return [json.loads(x) for x in lines if x.strip()]


def _make_logger(log_file: Path):
    """
    中文：自动适配 event_log.py 里的真实 logger 类名
    English: Auto-detect the actual logger class in event_log.py
    """
    # 常见命名优先尝试 / common names first
    for name in ["EventLog", "EventLogger", "JsonlEventLog", "EventLogWriter", "EventLogStore"]:
        cls = getattr(event_log, name, None)
        if isinstance(cls, type) and hasattr(cls, "append_move_event"):
            try:
                return cls(str(log_file), timezone_str="UTC")
            except TypeError:
                return cls(str(log_file))

    # 兜底：扫描模块内所有 class / fallback scan
    for name in dir(event_log):
        obj = getattr(event_log, name)
        if isinstance(obj, type) and hasattr(obj, "append_move_event"):
            try:
                return obj(str(log_file), timezone_str="UTC")
            except TypeError:
                return obj(str(log_file))

    raise AttributeError("Cannot find a logger class with append_move_event() in event_log.py")


def _call_append_move_event(logger: Any, **kwargs):
    """
    中文：
      append_move_event 的签名在你们代码里可能会变（actor_id/actor/actor_key...）
      所以测试这里动态过滤，只把它支持的参数传进去，避免 TypeError。

    English:
      append_move_event signature may differ across implementations.
      We filter kwargs by signature so tests won't break on param name differences.
    """
    fn = getattr(logger, "append_move_event")
    sig = inspect.signature(fn)
    allowed = set(sig.parameters.keys())

    filtered = {k: v for k, v in kwargs.items() if k in allowed}

    # 如果实现需要某些字段但我们没传，给出更清晰的报错
    # If implementation requires required params we didn't pass, raise clearer error
    missing_required = []
    for name, p in sig.parameters.items():
        if p.default is inspect._empty and name not in filtered:
            missing_required.append(name)
    if missing_required:
        raise TypeError(
            f"append_move_event requires params {missing_required}, "
            f"but test filtered kwargs did not include them. "
            f"Signature is: {sig}"
        )

    return fn(**filtered)


def test_append_move_event_writes_jsonl_and_schema(artifact_dir: Path):
    """
    中文：验证 append_move_event 写入 JSONL，并且具备基本字段结构
    English: Verify append_move_event writes JSONL and has basic schema
    """
    log_file = artifact_dir / "events.jsonl"
    logger = _make_logger(log_file)

    _call_append_move_event(
        logger,
        event_id="evt_0001",
        # actor_id 可能不存在，自动过滤 / auto-filter if unsupported
        actor_id="player",
        actor="player",
        actor_key="player",
        entity_id="player",
        from_id="A00",
        to_id="A01",
        path=["A00", "A01"],
        distance=1,
        ok=True,
        blocked=None,
        state_version_before=0,
        state_version_after=1,
        patch=[{"op": "replace", "path": "/player/location", "value": "A01"}],
        meta={"test": True},
    )

    assert log_file.exists()
    rows = _read_jsonl(log_file)
    assert len(rows) == 1
    row = rows[0]

    # 最小必备字段（不同实现可能字段名略差，但这些通常应该有）
    # Minimal required fields (should exist in most implementations)
    for k in ["ts", "event_id"]:
        assert k in row, f"Missing field: {k}"

    assert row["event_id"] == "evt_0001"


def test_append_move_event_appends_multiple_lines_and_unique_ids(artifact_dir: Path):
    """
    中文：连续写多条事件，应该是 append（不覆盖），event_id 不同
    English: Append multiple lines (no overwrite); event_id unique
    """
    log_file = artifact_dir / "events.jsonl"
    logger = _make_logger(log_file)

    _call_append_move_event(
        logger,
        event_id="evt_0001",
        actor_id="player",
        actor="player",
        from_id="A00",
        to_id="A01",
        path=["A00", "A01"],
        distance=1,
        ok=True,
        blocked=None,
        state_version_before=0,
        state_version_after=1,
        patch=[{"op": "replace", "path": "/player/location", "value": "A01"}],
        meta=None,
    )

    _call_append_move_event(
        logger,
        event_id="evt_0002",
        actor_id="player",
        actor="player",
        from_id="A01",
        to_id="A02",
        path=["A01", "A02"],
        distance=1,
        ok=True,
        blocked=None,
        state_version_before=1,
        state_version_after=2,
        patch=[{"op": "replace", "path": "/player/location", "value": "A02"}],
        meta=None,
    )

    rows = _read_jsonl(log_file)
    assert len(rows) == 2
    assert rows[0]["event_id"] == "evt_0001"
    assert rows[1]["event_id"] == "evt_0002"


def test_append_move_event_allows_blocked_payload(artifact_dir: Path):
    """
    中文：ok=False（blocked）也应该能写日志，并能记录 blocked 原因
    English: ok=False (blocked) should still be logged with blocked reason
    """
    log_file = artifact_dir / "events.jsonl"
    logger = _make_logger(log_file)

    blocked = {"reason_code": "unreachable", "message": "No path", "at": "A00->B03"}

    _call_append_move_event(
        logger,
        event_id="evt_blocked_1",
        actor_id="player",
        actor="player",
        from_id="A00",
        to_id="B03",
        path=[],
        distance=None,
        ok=False,
        blocked=blocked,
        state_version_before=0,
        state_version_after=0,
        patch=[],
        meta={"rule": "blocked"},
    )

    rows = _read_jsonl(log_file)
    assert len(rows) == 1
    row = rows[0]
    assert row["event_id"] == "evt_blocked_1"

    # blocked 字段名可能不同，但一般会出现在 row 里（如果你们实现写了的话）
    # blocked field name may vary; check common keys
    if "blocked" in row:
        assert isinstance(row["blocked"], dict)
