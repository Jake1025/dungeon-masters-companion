#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
中文：
  强制触发当前所有可记录 debug / exception 事件的测试脚本
  - 不依赖 LLM
  - 不依赖 CLI
  - 直接验证 DebugEventLogger 是否能写出目前所有可记录类型
  - 覆盖：
      - session_start
      - intro_fallback
      - fallback_plan
      - loop_incomplete
      - user_interrupt
      - uncaught_exception
      - exception

English:
  Forced test script for all currently recordable debug / exception events
  - No LLM required
  - No CLI required
  - Directly verifies DebugEventLogger can write all currently supported types
  - Covers:
      - session_start
      - intro_fallback
      - fallback_plan
      - loop_incomplete
      - user_interrupt
      - uncaught_exception
      - exception
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
    English: Read JSONL file
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


def trigger_session_start(logger: DebugEventLogger, game_state: Any) -> None:
    logger.log_event(
        game_state=game_state,
        turn=0,
        phase="cli",
        event_type="session_start",
        severity="info",
        message="CLI session started.",
        details={
            "session_dir": "_forced_test_session",
            "source": "test_debug_events_forced.py",
        },
    )


def trigger_intro_fallback(logger: DebugEventLogger, game_state: Any) -> None:
    logger.log_event(
        game_state=game_state,
        turn=0,
        phase="intro",
        event_type="intro_fallback",
        severity="error",
        message="Intro generation failed; falling back to starting_state.",
        details={
            "error": "Forced intro fallback test event.",
            "source": "test_debug_events_forced.py",
        },
    )


def trigger_fallback_plan(logger: DebugEventLogger, game_state: Any) -> None:
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
            "source": "test_debug_events_forced.py",
        },
    )


def trigger_loop_incomplete(logger: DebugEventLogger, game_state: Any) -> None:
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
            "source": "test_debug_events_forced.py",
        },
    )


def trigger_user_interrupt(logger: DebugEventLogger, game_state: Any) -> None:
    logger.log_event(
        game_state=game_state,
        turn=1,
        phase="cli",
        event_type="user_interrupt",
        severity="warning",
        message="Session terminated by user input interrupt.",
        details={
            "error_type": "KeyboardInterrupt",
            "source": "test_debug_events_forced.py",
        },
    )


def trigger_uncaught_exception(logger: DebugEventLogger, game_state: Any) -> None:
    logger.log_event(
        game_state=game_state,
        turn=1,
        phase="global",
        event_type="uncaught_exception",
        severity="critical",
        message="Uncaught exception reached global exception hook.",
        details={
            "error_type": "RuntimeError",
            "error": "Forced uncaught_exception test event.",
            "source": "test_debug_events_forced.py",
        },
    )


def trigger_generic_exception(logger: DebugEventLogger, game_state: Any) -> None:
    try:
        raise RuntimeError("Forced generic exception test event.")
    except Exception as exc:
        logger.log_exception(
            game_state=game_state,
            turn=2,
            phase="mechanics",
            where="test_debug_events_forced.trigger_generic_exception",
            exc=exc,
            details={"source": "test_debug_events_forced.py"},
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Force all currently recordable debug/exception event types."
    )
    parser.add_argument(
        "--out",
        default="_tmp_forced_debug_events",
        help="Output directory for test artifacts.",
    )
    parser.add_argument(
        "--event",
        action="append",
        default=[],
        help=(
            "Optional subset of event names to force. Can be repeated.\n"
            "Choices:\n"
            "  session_start\n"
            "  intro_fallback\n"
            "  fallback_plan\n"
            "  loop_incomplete\n"
            "  user_interrupt\n"
            "  uncaught_exception\n"
            "  exception\n"
            "If omitted, all supported types are written."
        ),
    )
    args = parser.parse_args()

    out_dir = Path(args.out).expanduser().resolve()
    checkpoint_root = out_dir / "checkpoints"
    debug_log = checkpoint_root / "logs" / "debug_events.jsonl"

    world = build_world_model()
    game_state = create_initial_game_state(
        starting_location=world.starting_location or "Town Square",
        world_model=world,
    )
    set_world_checkpoint_root(game_state, checkpoint_root)

    logger = DebugEventLogger()

    supported = [
        "session_start",
        "intro_fallback",
        "fallback_plan",
        "loop_incomplete",
        "user_interrupt",
        "uncaught_exception",
        "exception",
    ]
    requested_events = args.event or supported

    print("=" * 80)
    print("FORCED DEBUG / EXCEPTION EVENT TEST")
    print("=" * 80)
    print("Output dir:", out_dir)
    print("Requested events:", requested_events)

    for event_name in requested_events:
        if event_name == "session_start":
            trigger_session_start(logger, game_state)
        elif event_name == "intro_fallback":
            trigger_intro_fallback(logger, game_state)
        elif event_name == "fallback_plan":
            trigger_fallback_plan(logger, game_state)
        elif event_name == "loop_incomplete":
            trigger_loop_incomplete(logger, game_state)
        elif event_name == "user_interrupt":
            trigger_user_interrupt(logger, game_state)
        elif event_name == "uncaught_exception":
            trigger_uncaught_exception(logger, game_state)
        elif event_name == "exception":
            trigger_generic_exception(logger, game_state)
        else:
            raise ValueError(f"Unsupported event type: {event_name}")

    assert_true(debug_log.exists(), f"debug_events.jsonl not found: {debug_log}")

    rows = read_jsonl(debug_log)
    assert_true(len(rows) >= len(requested_events), "Not enough rows written to debug_events.jsonl")

    required_keys = {"ts", "turn", "phase", "event_type", "severity", "message", "details"}
    for i, row in enumerate(rows, start=1):
        missing = required_keys - set(row.keys())
        assert_true(not missing, f"Row {i} missing required keys: {sorted(missing)}")

    event_types = {str(row.get("event_type")) for row in rows}

    # event_name == exception -> event_type should be "exception"
    expected_event_types = []
    for name in requested_events:
        if name == "exception":
            expected_event_types.append("exception")
        else:
            expected_event_types.append(name)

    for event_type in expected_event_types:
        assert_true(event_type in event_types, f"Missing event_type: {event_type}")

    print("\n[PASS] All requested debug/exception event types were written successfully.")
    print(f"[INFO] Log file: {debug_log}")
    print(f"[INFO] Total rows: {len(rows)}")
    print(f"[INFO] Event types seen: {sorted(event_types)}")

    print("\nLast entries:")
    for row in rows[-len(requested_events):]:
        print(pretty(row))
        print("-" * 60)

    print("\n" + "=" * 80)
    print("FORCED DEBUG / EXCEPTION EVENT TEST PASSED")
    print("=" * 80)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())