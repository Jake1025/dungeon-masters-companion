#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
中文：
  DebugEventLogger 测试脚本
  - 不依赖 LLM
  - 不依赖 CLI
  - 直接创建 game_state + checkpoint_root
  - 写入多条 debug event
  - 验证 debug_events.jsonl 是否生成且字段完整

English:
  DebugEventLogger test script
  - No LLM required
  - No CLI required
  - Creates game_state + checkpoint_root directly
  - Writes multiple debug events
  - Verifies debug_events.jsonl exists and has valid fields
============================================================
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

from orchestrator.world_state.story import create_initial_game_state
from orchestrator.world_state.tool_runtime import set_world_checkpoint_root
from orchestrator.world_state.world_model import build_world_model
from orchestrator.world_state.debug_event_logging import DebugEventLogger


def read_jsonl(path: Path) -> List[Dict[str, Any]]:
    """
    中文：读取 JSONL 文件
    English: Read a JSONL file
    """
    if not path.exists():
        return []
    rows: List[Dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def pretty(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2)


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    parser = argparse.ArgumentParser(description="Test DebugEventLogger.")
    parser.add_argument(
        "--out",
        default="_tmp_debug_log_test",
        help="Output directory for test artifacts.",
    )
    args = parser.parse_args()

    out_dir = Path(args.out).expanduser().resolve()
    checkpoint_root = out_dir / "checkpoints"
    log_file = checkpoint_root / "logs" / "debug_events.jsonl"

    print("=" * 80)
    print("START DEBUG LOGGER TEST")
    print("=" * 80)
    print(f"Output directory: {out_dir}")

    # ============================================================
    # 中文：初始化 world + game_state，并设置 checkpoint_root
    # English: initialize world + game_state and set checkpoint_root
    # ============================================================
    world = build_world_model()
    game_state = create_initial_game_state(
        starting_location=world.starting_location or "Town Square",
        world_model=world,
    )
    set_world_checkpoint_root(game_state, checkpoint_root)

    logger = DebugEventLogger()

    # ============================================================
    # 中文：写入几种典型 debug 事件
    # English: write several representative debug events
    # ============================================================
    logger.log_event(
        game_state=game_state,
        turn=0,
        phase="intro",
        event_type="intro_fallback",
        severity="error",
        message="Intro generation failed; falling back to starting_state.",
        details={"error": "Simulated intro error for test."},
    )

    logger.log_event(
        game_state=game_state,
        turn=1,
        phase="intent",
        event_type="fallback_plan",
        severity="warning",
        message="Intent phase finished without a todo plan; fallback todo was generated.",
        details={
            "player_input": "i want to investigate the hall",
            "intent_summary": "",
        },
    )

    logger.log_event(
        game_state=game_state,
        turn=1,
        phase="mechanics",
        event_type="loop_incomplete",
        severity="warning",
        message="Mechanics phase did not complete normally.",
        details={
            "status": "max_iterations",
            "todo_count": 3,
        },
    )

    logger.log_event(
        game_state=game_state,
        turn=1,
        phase="cli",
        event_type="user_interrupt",
        severity="warning",
        message="Session terminated by user input interrupt.",
        details={"error_type": "KeyboardInterrupt"},
    )

    # ============================================================
    # 中文：检查日志文件是否生成
    # English: verify that the log file exists
    # ============================================================
    assert_true(log_file.exists(), f"Expected log file was not created: {log_file}")

    rows = read_jsonl(log_file)
    assert_true(len(rows) >= 4, "Expected at least 4 debug log entries.")

    # ============================================================
    # 中文：检查字段完整性
    # English: validate required fields
    # ============================================================
    required_keys = {"ts", "turn", "phase", "event_type", "severity", "message", "details"}

    for i, row in enumerate(rows, start=1):
        missing = required_keys - set(row.keys())
        assert_true(not missing, f"Row {i} is missing required keys: {sorted(missing)}")

    # ============================================================
    # 中文：检查具体事件类型是否都写进去了
    # English: verify specific event types were written
    # ============================================================
    event_types = {str(row.get("event_type")) for row in rows}
    assert_true("intro_fallback" in event_types, "Missing intro_fallback event.")
    assert_true("fallback_plan" in event_types, "Missing fallback_plan event.")
    assert_true("loop_incomplete" in event_types, "Missing loop_incomplete event.")
    assert_true("user_interrupt" in event_types, "Missing user_interrupt event.")

    print("\n[PASS] debug_events.jsonl created successfully.")
    print(f"[INFO] Total rows: {len(rows)}")
    print(f"[INFO] Log file: {log_file}")

    print("\nLast 4 entries:")
    for row in rows[-4:]:
        print(pretty(row))
        print("-" * 60)

    print("\n" + "=" * 80)
    print("DEBUG LOGGER TEST PASSED")
    print("=" * 80)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())