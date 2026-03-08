#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
中文：
  Debug / Tool Logging 端到端测试脚本（更新版）
  - 通过 subprocess 启动 orchestrator.cli
  - 自动喂入几句输入
  - 检查 session 目录、tool logs、debug logs 是否生成
  - 默认要求 debug_events.jsonl 至少包含一个稳定可触发事件：session_start
  - 可选要求某些 event_type 必须出现
  - 可选要求某些 event_type 只要出现就展示

  适用场景：
  - 你已经把 ToolCallLogger / DebugEventLogger 接入了 CLI / pipeline
  - 想验证真实运行路径中的日志是否正常写入

English:
  Updated end-to-end test for debug/tool logging
  - Launches orchestrator.cli via subprocess
  - Feeds a few scripted inputs
  - Verifies session dir, tool logs, and debug logs
  - By default expects a stable debug event: session_start
  - Can optionally require specific event types
  - Can optionally display soft-expected event types if present

  Use this when:
  - ToolCallLogger / DebugEventLogger have been integrated into CLI / pipeline
  - You want to verify real runtime logging behavior
============================================================
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional


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


def find_latest_session_dir(state_root: Path, session_name: str) -> Optional[Path]:
    """
    中文：
      在 state_root 下寻找最新的、名字以 _<session_name> 结尾的 session 目录

    English:
      Find the latest session directory ending with _<session_name>
    """
    if not state_root.exists():
        return None

    candidates = [
        p for p in state_root.iterdir()
        if p.is_dir() and p.name.endswith(f"_{session_name}")
    ]
    if not candidates:
        return None
    return sorted(candidates)[-1]


def summarize_tool_logs(logs_dir: Path) -> Dict[str, int]:
    """
    中文：统计 logs_dir 下所有非 debug 的 jsonl 行数
    English: Count rows of all non-debug jsonl log files under logs_dir
    """
    summary: Dict[str, int] = {}
    if not logs_dir.exists():
        return summary

    for path in sorted(logs_dir.glob("*.jsonl")):
        if path.name == "debug_events.jsonl":
            continue
        summary[path.name] = len(read_jsonl(path))
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Updated E2E test for tool/debug logging.")
    parser.add_argument(
        "--model",
        default="qwen3:8b",
        help="Ollama model to use for CLI run.",
    )
    parser.add_argument(
        "--session-name",
        default="debug_e2e_test",
        help="Session name suffix for this test run.",
    )
    parser.add_argument(
        "--state-root",
        default="_tmp_debug_e2e_state",
        help="State root directory for CLI output.",
    )
    parser.add_argument(
        "--python",
        default=sys.executable,
        help="Python interpreter to use.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Pass --verbose to orchestrator.cli.",
    )
    parser.add_argument(
        "--strict-debug-log",
        action="store_true",
        help=(
            "Strict mode: require debug_events.jsonl to exist. "
            "Recommended when DebugEventLogger is known to be integrated."
        ),
    )
    parser.add_argument(
        "--require-event",
        action="append",
        default=[],
        help=(
            "Require a specific debug event_type to exist. "
            "Can be repeated, e.g. --require-event session_start --require-event intro_fallback"
        ),
    )
    parser.add_argument(
        "--soft-event",
        action="append",
        default=[],
        help=(
            "Soft expectation: if this event exists, it will be reported, "
            "but absence will not fail the test."
        ),
    )
    args = parser.parse_args()

    state_root = Path(args.state_root).expanduser().resolve()
    state_root.mkdir(parents=True, exist_ok=True)

    # ============================================================
    # 中文：
    #   这里用最常见、最稳定的输入：
    #   - 移动
    #   - 观察
    #   - quit 正常退出
    #
    # English:
    #   Use simple, stable scripted inputs:
    #   - move
    #   - inspect
    #   - quit normally
    # ============================================================
    scripted_input = "\n".join([
        "i want to go to the town hall",
        "i look around carefully for clues",
        "quit",
        "",
    ])

    cmd = [
        args.python,
        "-m",
        "orchestrator.cli",
        "--model",
        args.model,
        "--session-name",
        args.session_name,
        "--state-root",
        str(state_root),
    ]
    if args.verbose:
        cmd.append("--verbose")

    print("=" * 80)
    print("START UPDATED DEBUG LOGGING E2E TEST")
    print("=" * 80)
    print("Command:")
    print(" ".join(cmd))
    print("\nState root:")
    print(state_root)

    proc = subprocess.run(
        cmd,
        input=scripted_input,
        text=True,
        capture_output=True,
    )

    print("\nCLI return code:", proc.returncode)

    print("\n--- CLI STDOUT (tail) ---")
    stdout_tail = "\n".join(proc.stdout.splitlines()[-80:])
    print(stdout_tail)

    if proc.stderr.strip():
        print("\n--- CLI STDERR ---")
        print(proc.stderr)

    assert_true(proc.returncode == 0, f"CLI exited with non-zero code: {proc.returncode}")

    session_dir = find_latest_session_dir(state_root, args.session_name)
    assert_true(session_dir is not None, f"Could not find session dir for: {args.session_name}")
    assert_true(session_dir is not None, "session_dir should not be None")

    print("\nDetected session dir:")
    print(session_dir)

    logs_dir = session_dir / "checkpoints" / "logs"
    assert_true(logs_dir.exists(), f"Logs directory does not exist: {logs_dir}")

    # ============================================================
    # 中文：先检查 tool logs
    # English: verify tool logs first
    # ============================================================
    tool_log_summary = summarize_tool_logs(logs_dir)
    print("\nTool log summary:")
    if tool_log_summary:
        for name, count in tool_log_summary.items():
            print(f"  - {name}: {count} rows")
    else:
        print("  (no grouped tool logs found)")

    assert_true(
        any(count > 0 for count in tool_log_summary.values()),
        "No grouped tool logs were found or all were empty.",
    )

    # ============================================================
    # 中文：再检查 debug log
    # English: verify debug log
    # ============================================================
    debug_log = logs_dir / "debug_events.jsonl"
    debug_rows: List[Dict[str, Any]] = []
    debug_event_types: set[str] = set()

    if debug_log.exists():
        debug_rows = read_jsonl(debug_log)
        debug_event_types = {str(row.get("event_type")) for row in debug_rows}

        print("\nDebug log found:")
        print(f"  - {debug_log}")
        print(f"  - rows: {len(debug_rows)}")
        print(f"  - event types: {sorted(debug_event_types)}")

        required_keys = {"ts", "turn", "phase", "event_type", "severity", "message", "details"}
        for i, row in enumerate(debug_rows, start=1):
            missing = required_keys - set(row.keys())
            assert_true(not missing, f"debug_events row {i} missing required keys: {sorted(missing)}")

    else:
        print("\nDebug log not found:")
        print(f"  - expected path: {debug_log}")

    # strict mode
    if args.strict_debug_log:
        assert_true(debug_log.exists(), f"debug_events.jsonl was not created: {debug_log}")
        assert_true(len(debug_rows) > 0, "debug_events.jsonl exists but is empty")

    # default expectation:
    # if debug log exists, session_start should usually be there
    # if debug log does not exist and strict mode is off, we do not fail here
    if debug_log.exists():
        assert_true(
            "session_start" in debug_event_types,
            "debug_events.jsonl exists, but expected stable event 'session_start' was not found.",
        )

    # required explicit events
    for expected in args.require_event:
        assert_true(debug_log.exists(), f"Required event '{expected}' requested, but debug_events.jsonl does not exist.")
        assert_true(expected in debug_event_types, f"Required debug event not found: {expected}")

    # soft events
    if args.soft_event:
        print("\nSoft-expected events:")
        if not debug_log.exists():
            print("  - debug_events.jsonl not present, so no soft events available")
        else:
            for expected in args.soft_event:
                if expected in debug_event_types:
                    print(f"  - present: {expected}")
                else:
                    print(f"  - absent : {expected}")

    # Show tails
    print("\nRecent tool log entries:")
    for path in sorted(logs_dir.glob("*.jsonl")):
        rows = read_jsonl(path)
        if not rows:
            continue
        print(f"\n[{path.name}] last entry:")
        print(pretty(rows[-1]))

    print("\n" + "=" * 80)
    print("UPDATED DEBUG LOGGING E2E TEST PASSED")
    print("=" * 80)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())