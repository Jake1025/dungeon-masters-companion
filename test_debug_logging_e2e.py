#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
中文：
  Debug 日志端到端测试脚本（E2E）
  - 通过 subprocess 启动 orchestrator.cli
  - 自动喂入几句输入
  - 检查 state/<session>/checkpoints/logs/debug_events.jsonl 是否生成
  - 验证日志文件字段是否完整
  - 可选检查某些 event_type 是否出现

  适用场景：
  - 你已经把 DebugEventLogger 接入了 cli.py / pipeline.py
  - 想验证“真实运行时”是否会写 debug 日志

English:
  End-to-end debug logging test script
  - Launches orchestrator.cli via subprocess
  - Feeds a few input lines automatically
  - Verifies debug_events.jsonl is created under session logs
  - Validates log structure
  - Optionally checks expected event types

  Use this when:
  - DebugEventLogger has been integrated into cli.py / pipeline.py
  - You want to verify real runtime debug logging
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
    candidates = [
        p for p in state_root.iterdir()
        if p.is_dir() and p.name.endswith(f"_{session_name}")
    ]
    if not candidates:
        return None
    return sorted(candidates)[-1]


def main() -> int:
    parser = argparse.ArgumentParser(description="E2E test for debug event logging.")
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
        "--expect-event",
        action="append",
        default=[],
        help=(
            "Expected event_type in debug_events.jsonl. "
            "Can be passed multiple times, e.g. "
            "--expect-event intro_fallback --expect-event user_interrupt"
        ),
    )
    args = parser.parse_args()

    state_root = Path(args.state_root).expanduser().resolve()
    state_root.mkdir(parents=True, exist_ok=True)

    # ============================================================
    # 中文：
    #   这里的输入尽量简单：
    #   - 先来一条玩家输入
    #   - 再 quit 正常退出
    #
    #   如果你已经在 CLI / pipeline 中加了 debug logging，
    #   那么：
    #   - intro 失败时可能会写 intro_fallback
    #   - 正常退出未必会写 user_interrupt（因为 quit 不是 Ctrl+C）
    #
    # English:
    #   Keep input simple:
    #   - one player instruction
    #   - then quit
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
    print("START DEBUG LOGGING E2E TEST")
    print("=" * 80)
    print("Command:")
    print(" ".join(cmd))
    print("\nState root:")
    print(state_root)

    # ============================================================
    # 中文：运行 CLI 子进程
    # English: run CLI as subprocess
    # ============================================================
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

    # CLI return code may still be 0 even if intro falls back.
    assert_true(proc.returncode == 0, f"CLI exited with non-zero code: {proc.returncode}")

    # ============================================================
    # 中文：查找 session 目录
    # English: locate session directory
    # ============================================================
    session_dir = find_latest_session_dir(state_root, args.session_name)
    assert_true(session_dir is not None, f"Could not find session dir for: {args.session_name}")
    assert_true(session_dir is not None, "session_dir should not be None")

    print("\nDetected session dir:")
    print(session_dir)

    debug_log = session_dir / "checkpoints" / "logs" / "debug_events.jsonl"

    # ============================================================
    # 中文：
    #   验证 debug 日志文件：
    #   - 如果你的 cli/pipeline 还没接上 debug_logger，这里会失败
    #   - 这是预期的“接入检查”
    #
    # English:
    #   Verify debug log file exists.
    #   This will fail if debug logger has not been integrated yet.
    # ============================================================
    assert_true(debug_log.exists(), f"debug_events.jsonl was not created: {debug_log}")

    rows = read_jsonl(debug_log)
    assert_true(len(rows) > 0, "debug_events.jsonl exists but is empty")

    required_keys = {"ts", "turn", "phase", "event_type", "severity", "message", "details"}
    for i, row in enumerate(rows, start=1):
        missing = required_keys - set(row.keys())
        assert_true(not missing, f"Row {i} missing required keys: {sorted(missing)}")

    event_types = {str(row.get("event_type")) for row in rows}

    # Optional assertions
    for expected in args.expect_event:
        assert_true(expected in event_types, f"Expected event_type not found: {expected}")

    print("\n[PASS] debug_events.jsonl exists and is valid.")
    print(f"[INFO] Total debug rows: {len(rows)}")
    print(f"[INFO] Debug log path: {debug_log}")
    print(f"[INFO] Event types seen: {sorted(event_types)}")

    print("\nLast 5 debug entries:")
    for row in rows[-5:]:
        print(pretty(row))
        print("-" * 60)

    print("\n" + "=" * 80)
    print("DEBUG LOGGING E2E TEST PASSED")
    print("=" * 80)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())