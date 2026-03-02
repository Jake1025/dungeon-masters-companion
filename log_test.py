#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
中文：
  ToolCallLogger 测试脚本（不依赖 LLM / Ollama）
  - 直接调用 orchestrator.world_state.tools.execute_tool
  - 模拟 pipeline.phase_tool_executor：
      - capture before/after player_location
      - per-turn log_seq 单调递增
      - 调用 ToolCallLogger.log_tool_call 写 JSONL（按 group 分文件）
  - 输出目录默认：_tmp_tool_log_test/checkpoints/logs/

English:
  ToolCallLogger test script (no LLM / Ollama required)
  - Calls orchestrator.world_state.tools.execute_tool directly
  - Mimics pipeline.phase_tool_executor:
      - capture before/after player_location
      - per-turn monotonic log_seq
      - calls ToolCallLogger.log_tool_call (group-split JSONL)
  - Default output: _tmp_tool_log_test/checkpoints/logs/
============================================================
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from orchestrator.world_state.story import create_initial_game_state
from orchestrator.world_state.tool_runtime import (
    bind_turn_orchestration_ctx,
    clear_turn_orchestration_ctx,
    set_world_checkpoint_root,
)
from orchestrator.world_state.tools import execute_tool
from orchestrator.world_state.world_model import build_world_model

# ✅ Your logger (matches what you pasted)
from orchestrator.world_state.tool_call_logging import ToolCallLogger


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    """
    中文：读取 JSONL 文件为 list[dict]
    English: Read JSONL into list[dict]
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


def _pretty(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2)


def main() -> int:
    parser = argparse.ArgumentParser(description="Test ToolCallLogger without running LLM pipeline.")
    parser.add_argument("--out", default="_tmp_tool_log_test", help="Output folder for the test run.")
    parser.add_argument("--turn", type=int, default=1, help="Fake turn number used in event_id.")
    args = parser.parse_args()

    out_dir = Path(args.out).expanduser().resolve()
    checkpoint_root = out_dir / "checkpoints"
    logs_dir = checkpoint_root / "logs"

    # ============================================================
    # 中文：初始化 world + game_state，并设置 checkpoint_root（logger 用它推导 logs_dir）
    # English: init world + game_state; set checkpoint_root (logger infers logs_dir from it)
    # ============================================================
    world = build_world_model()
    game_state = create_initial_game_state(
        starting_location=world.starting_location or "Town Square",
        world_model=world,
    )
    set_world_checkpoint_root(game_state, checkpoint_root)

    # ============================================================
    # 中文：绑定一个最小的 turn_ctx（logger 不依赖它，但你后续如果要扩展会方便）
    # English: bind a minimal turn_ctx (logger doesn't require it, but useful for extensions)
    # ============================================================
    turn_ctx: Dict[str, Any] = {
        "phase": "mechanics",
        "todo": [{"id": 1, "task": "test tool logging", "status": "in_progress"}],
        "todo_revision": 1,
        "todo_summary": "test tool logging",
        "notes": [],
        "current_location": getattr(game_state, "player_location", ""),
        "log_seq": 0,
    }
    bind_turn_orchestration_ctx(game_state, turn_ctx)

    logger = ToolCallLogger()

    def call_tool(tool_name: str, tool_args: Dict[str, Any], *, phase: str = "mechanics") -> Dict[str, Any]:
        """
        中文：
          模拟 pipeline.phase_tool_executor 的核心流程：
          1) before_location
          2) execute_tool
          3) after_location
          4) log_seq++ & event_id
          5) logger.log_tool_call(best-effort)

        English:
          Mimic pipeline.phase_tool_executor core steps.
        """
        before_location = getattr(game_state, "player_location", None)

        result = execute_tool(tool_name, tool_args, game_state)

        after_location = getattr(game_state, "player_location", None)

        turn_ctx["log_seq"] = int(turn_ctx.get("log_seq", 0)) + 1
        seq = int(turn_ctx["log_seq"])
        event_id = logger.build_event_id(turn=args.turn, seq=seq, tool=tool_name)

        # best-effort logging; swallow failures inside logger
        logger.log_tool_call(
            event_id=event_id,
            turn=args.turn,
            phase=phase,
            tool=tool_name,
            args=dict(tool_args or {}),
            result=result,
            game_state=game_state,
            before_location=before_location,
            after_location=after_location,
        )

        return result

    print("\n[TEST] Logs will be written under:\n ", str(logs_dir), "\n")

    # ============================================================
    # 中文：调用几个不同 group 的工具，确保能看到多个 *.jsonl
    # English: call tools across groups to produce multiple *.jsonl
    # ============================================================

    # 1) world_read group (get_world_scene)
    r1 = call_tool("get_world_scene", {"location_key": getattr(game_state, "player_location", "")}, phase="intent")
    print("[1] get_world_scene =>", r1.get("success"))

    # 2) context/scene group (get_current_context)
    r2 = call_tool("get_current_context", {}, phase="mechanics")
    print("[2] get_current_context =>", r2.get("success"))

    # 3) mechanics group (roll_dice)
    r3 = call_tool("roll_dice", {"sides": 20, "count": 1, "modifier": 0, "label": "test"}, phase="mechanics")
    print("[3] roll_dice =>", r3.get("success"), "total=", r3.get("total"))

    # 4) mechanics group (skill_check)
    r4 = call_tool("skill_check", {"entity_key": "Player", "skill": "perception", "dc": 10, "context": "test"}, phase="mechanics")
    print("[4] skill_check =>", r4.get("success"), "pass=", (r4.get("check") or {}).get("success"))

    # 5) scene/movement group (move_to_location) - choose a connected location dynamically
    scene_payload = execute_tool("get_world_scene", {"location_key": getattr(game_state, "player_location", "")}, game_state)
    connections = ((scene_payload.get("scene") or {}).get("connections") or []) if isinstance(scene_payload, dict) else []
    target: Optional[str] = next((str(c).strip() for c in connections if str(c).strip()), None)

    if target:
        r5 = call_tool("move_to_location", {"location_key": target}, phase="mechanics")
        print("[5] move_to_location =>", r5.get("success"), "new_location=", getattr(game_state, "player_location", None))
    else:
        print("[5] move_to_location => skipped (no connections found)")

    # ============================================================
    # 中文：检查日志输出：列出 logs_dir 下的 *.jsonl，并展示每个文件最后 1 行
    # English: verify output: list *.jsonl and show last line of each
    # ============================================================
    logs_dir.mkdir(parents=True, exist_ok=True)
    files = sorted(logs_dir.glob("*.jsonl"))

    if not files:
        print("\n[FAIL] No *.jsonl files found under logs_dir.")
        print("Possible causes:")
        print("  - checkpoint_root not set on game_state")
        print("  - ToolCallLogger._resolve_log_dir returned None")
        clear_turn_orchestration_ctx(game_state)
        return 2

    print("\n[OK] Found log files:")
    for f in files:
        rows = _read_jsonl(f)
        print(f"  - {f.name}: {len(rows)} lines")
        if rows:
            print("    last entry:")
            print(_pretty(rows[-1]))
            print("    " + "-" * 50)

    clear_turn_orchestration_ctx(game_state)
    print("\n[PASS] ToolCallLogger test finished.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())