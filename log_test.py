#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# ============================================================
# 中文：
#   兼容性测试脚本：验证现有 logging 与新工具实现是否兼容
#
#   覆盖内容：
#   - world tools: get_world_story / get_world_scene / get_world_location ...
#   - validate tools: check_can_interact
#   - scene tools: get_current_context / list_scene_entities / move_to_location / move_npc
#   - mechanics tools: roll_dice / skill_check / get_recent_skill_checks
#   - entity tools: get_entity_state / retrieve_memory_tool / write_memory_tool
#   - turn logging: ToolCallLogger 按 group 分文件写 JSONL
#
#   设计原则：
#   - 不依赖 LLM
#   - 不修改现有代码
#   - 尽量模拟 pipeline.phase_tool_executor 的 logging 行为
#
# English:
#   Compatibility test script for current logging + new tool behavior
#
#   Coverage:
#   - world tools
#   - validate tools
#   - scene tools
#   - mechanics tools
#   - entity tools
#   - ToolCallLogger grouped JSONL output
#
#   Principles:
#   - no LLM dependency
#   - no code changes required
#   - mimics pipeline.phase_tool_executor logging behavior
# ============================================================

from __future__ import annotations

import argparse
import json
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional

from orchestrator.world_state.story import create_initial_game_state
from orchestrator.world_state.tool_runtime import (
    bind_turn_orchestration_ctx,
    clear_turn_orchestration_ctx,
    ensure_entity_registry,
    set_world_checkpoint_root,
)
from orchestrator.world_state.tools import execute_tool
from orchestrator.world_state.world_model import build_world_model
from orchestrator.world_state.tool_call_logging import ToolCallLogger


# ============================================================
# 中文：基础工具函数
# English: Basic helper utilities
# ============================================================

def read_jsonl(path: Path) -> List[Dict[str, Any]]:
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


def print_header(title: str) -> None:
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


# ============================================================
# 中文：
#   兼容性测试器：
#   - 初始化 world + game_state
#   - 绑定 checkpoint root（供 logger 推导 logs 目录）
#   - 模拟 phase_tool_executor 的 logging 逻辑
#
# English:
#   Compatibility test runner:
#   - initializes world + game_state
#   - binds checkpoint root for logger
#   - mimics phase_tool_executor logging flow
# ============================================================

class CompatTestRunner:
    def __init__(self, out_dir: Path, turn_no: int = 1) -> None:
        self.out_dir = out_dir.resolve()
        self.turn_no = int(turn_no)
        self.checkpoint_root = self.out_dir / "checkpoints"
        self.logs_dir = self.checkpoint_root / "logs"

        self.world = build_world_model()
        self.game_state = create_initial_game_state(
            starting_location=self.world.starting_location or "Town Square",
            world_model=self.world,
        )
        set_world_checkpoint_root(self.game_state, self.checkpoint_root)

        self.turn_ctx: Dict[str, Any] = {
            "phase": "mechanics",
            "todo": [{"id": 1, "task": "compat logging test", "status": "in_progress"}],
            "todo_revision": 1,
            "todo_summary": "compat logging test",
            "notes": [],
            "intent_summary": "",
            "mechanics_summary": "",
            "mechanics_status": "",
            "all_world_tool_calls": [],
            "current_location": getattr(self.game_state, "player_location", ""),
            "log_seq": 0,
        }
        bind_turn_orchestration_ctx(self.game_state, self.turn_ctx)

        self.logger = ToolCallLogger()
        self.results: List[Dict[str, Any]] = []

        # make sure entity registry exists
        ensure_entity_registry(self.game_state)

    def cleanup(self) -> None:
        clear_turn_orchestration_ctx(self.game_state)

    def call_tool(self, tool_name: str, arguments: Dict[str, Any], phase: str = "mechanics") -> Dict[str, Any]:
        """
        中文：
          模拟 pipeline.phase_tool_executor：
          1) 记录 before_location
          2) execute_tool
          3) 记录 after_location
          4) 写 grouped jsonl log
          5) 把结果保存到内存测试结果

        English:
          Mimic pipeline.phase_tool_executor:
          1) capture before_location
          2) execute_tool
          3) capture after_location
          4) write grouped JSONL log
          5) store result in memory
        """
        self.turn_ctx["phase"] = phase
        before_location = getattr(self.game_state, "player_location", None)

        result = execute_tool(tool_name, dict(arguments or {}), self.game_state)

        after_location = getattr(self.game_state, "player_location", None)

        self.turn_ctx["log_seq"] = int(self.turn_ctx.get("log_seq", 0)) + 1
        seq = int(self.turn_ctx["log_seq"])
        event_id = self.logger.build_event_id(turn=self.turn_no, seq=seq, tool=tool_name)

        # best-effort logging
        self.logger.log_tool_call(
            event_id=event_id,
            turn=self.turn_no,
            phase=phase,
            tool=tool_name,
            args=dict(arguments or {}),
            result=result,
            game_state=self.game_state,
            before_location=before_location,
            after_location=after_location,
        )

        self.results.append(
            {
                "event_id": event_id,
                "phase": phase,
                "tool": tool_name,
                "arguments": dict(arguments or {}),
                "result": result,
                "before_location": before_location,
                "after_location": after_location,
            }
        )
        return result

    def pick_connected_location(self) -> Optional[str]:
        scene = execute_tool(
            "get_world_scene",
            {"location_key": getattr(self.game_state, "player_location", "")},
            self.game_state,
        )
        scene_payload = scene.get("scene") if isinstance(scene, dict) else {}
        connections = list((scene_payload or {}).get("connections") or [])
        for loc in connections:
            loc = str(loc).strip()
            if loc:
                return loc
        return None

    def pick_first_npc(self) -> Optional[str]:
        scene = execute_tool(
            "get_world_scene",
            {"location_key": getattr(self.game_state, "player_location", "")},
            self.game_state,
        )
        actors = list(((scene.get("scene") or {}).get("actors_here")) or [])
        for actor_key in actors:
            key = str(actor_key).strip()
            if key and key.lower() != "player":
                return key
        return None

    def find_any_other_location(self) -> Optional[str]:
        listing = execute_tool("list_world_locations", {}, self.game_state)
        locations = list(listing.get("locations") or [])
        current = getattr(self.game_state, "player_location", "")
        for loc in locations:
            key = str((loc or {}).get("key") or "").strip()
            if key and key != current:
                return key
        return None


# ============================================================
# 中文：具体测试项
# English: Individual test cases
# ============================================================

def test_world_tools(runner: CompatTestRunner) -> None:
    print_header("TEST: world tools")

    r1 = runner.call_tool("get_world_story", {}, phase="intent")
    assert_true(r1.get("success") is True, "get_world_story should succeed")

    current_loc = getattr(runner.game_state, "player_location", "")
    r2 = runner.call_tool("get_world_scene", {"location_key": current_loc}, phase="intent")
    assert_true(r2.get("success") is True, "get_world_scene should succeed")

    r3 = runner.call_tool("get_world_location", {"location_key": current_loc}, phase="intent")
    assert_true(r3.get("success") is True, "get_world_location should succeed")

    r4 = runner.call_tool("list_world_locations", {}, phase="intent")
    assert_true(r4.get("success") is True, "list_world_locations should succeed")

    print("PASS world tools")


def test_validate_tools(runner: CompatTestRunner) -> None:
    print_header("TEST: validate tools")

    # empty target should no longer hard-fail
    r1 = runner.call_tool("check_can_interact", {}, phase="intent")
    assert_true("can_interact" in r1, "check_can_interact(empty) should return can_interact")

    current_loc = getattr(runner.game_state, "player_location", "")
    partial = current_loc.split()[0] if current_loc else ""
    if partial:
        r2 = runner.call_tool("check_can_interact", {"entity_key": partial}, phase="intent")
        assert_true(r2.get("success") is True, "check_can_interact(partial location) should succeed")

    npc = runner.pick_first_npc()
    if npc:
        partial_npc = npc.split()[0]
        r3 = runner.call_tool("check_can_interact", {"entity_key": partial_npc}, phase="intent")
        assert_true(r3.get("success") is True, "check_can_interact(partial npc) should succeed")

    print("PASS validate tools")


def test_scene_tools(runner: CompatTestRunner) -> None:
    print_header("TEST: scene tools")

    r1 = runner.call_tool("get_current_context", {}, phase="mechanics")
    assert_true("location" in r1, "get_current_context should return location")

    r2 = runner.call_tool("list_scene_entities", {}, phase="mechanics")
    assert_true(r2.get("success") is True, "list_scene_entities should succeed")
    assert_true("scene_entities" in r2, "list_scene_entities should return scene_entities")

    # empty destination should not crash
    r3 = runner.call_tool("move_to_location", {}, phase="mechanics")
    assert_true(r3.get("success") is True, "move_to_location(empty) should succeed with no-op")

    target = runner.pick_connected_location()
    if target:
        partial_target = target.split()[0]
        r4 = runner.call_tool("move_to_location", {"location_key": partial_target}, phase="mechanics")
        assert_true("success" in r4, "move_to_location(partial) should return success field")

    npc = runner.pick_first_npc()
    other_loc = runner.find_any_other_location()
    if npc and other_loc:
        r5 = runner.call_tool(
            "move_npc",
            {"npc_key": npc.split()[0], "new_location": other_loc.split()[0]},
            phase="mechanics",
        )
        assert_true("success" in r5, "move_npc should return success field")

    print("PASS scene tools")


def test_mechanics_tools(runner: CompatTestRunner) -> None:
    print_header("TEST: mechanics tools")

    r1 = runner.call_tool("roll_dice", {"sides": 20, "count": 1, "modifier": 0, "label": "compat"}, phase="mechanics")
    assert_true(r1.get("success") is True, "roll_dice should succeed")
    assert_true("total" in r1, "roll_dice should return total")

    r2 = runner.call_tool(
        "skill_check",
        {
            "entity_key": "Player",
            "skill": "perception",
            "dc": 10,
            "context": "compat test",
        },
        phase="mechanics",
    )
    assert_true(r2.get("success") is True, "skill_check should succeed")
    assert_true("check" in r2, "skill_check should return check payload")

    r3 = runner.call_tool("get_recent_skill_checks", {"limit": 5}, phase="mechanics")
    assert_true(r3.get("success") is True, "get_recent_skill_checks should succeed")
    assert_true("checks" in r3, "get_recent_skill_checks should return checks")

    print("PASS mechanics tools")


def test_entity_tools(runner: CompatTestRunner) -> None:
    print_header("TEST: entity tools")

    r1 = runner.call_tool("get_entity_state", {"entity_key": "Player"}, phase="mechanics")
    assert_true(r1.get("success") is True, "get_entity_state(Player) should succeed")

    # write/read memory on Player to test memory tools compatibility
    r2 = runner.call_tool(
        "write_memory_tool",
        {
            "entity_name": "Player",
            "memory": "Compatibility test memory entry.",
            "relevance": 100.0,
        },
        phase="mechanics",
    )
    assert_true(r2.get("success") is True, "write_memory_tool(Player) should succeed")

    r3 = runner.call_tool(
        "retrieve_memory_tool",
        {
            "entity_name": "Player",
            "context": "compatibility test memory",
            "top_n": 3,
        },
        phase="mechanics",
    )
    assert_true(r3.get("success") is True, "retrieve_memory_tool(Player) should succeed")
    assert_true("memories" in r3, "retrieve_memory_tool should return memories")

    print("PASS entity tools")


def test_logging_output(runner: CompatTestRunner) -> None:
    print_header("TEST: logging output")

    assert_true(runner.logs_dir.exists(), "logs directory should exist")

    log_files = sorted(runner.logs_dir.glob("*.jsonl"))
    assert_true(len(log_files) > 0, "at least one grouped jsonl log file should exist")

    total_rows = 0
    for path in log_files:
        rows = read_jsonl(path)
        total_rows += len(rows)
        assert_true(len(rows) > 0, f"{path.name} should not be empty")

        last = rows[-1]
        for required_key in (
            "ts",
            "event_id",
            "turn",
            "phase",
            "group",
            "tool",
            "ok",
            "before_location",
            "after_location",
            "args",
            "result",
        ):
            assert_true(required_key in last, f"{path.name} missing key: {required_key}")

    assert_true(total_rows >= len(runner.results), "logged row count should be >= tool calls made")

    # monotonic event ids in memory trace
    assert_true(runner.turn_ctx["log_seq"] == len(runner.results), "log_seq should equal number of tool calls")

    print("PASS logging output")

    print("\nGenerated log files:")
    for path in log_files:
        rows = read_jsonl(path)
        print(f"  - {path.name}: {len(rows)} rows")


# ============================================================
# 中文：主函数
# English: main entrypoint
# ============================================================

def main() -> int:
    parser = argparse.ArgumentParser(description="Test compatibility between current logging and new tool behavior.")
    parser.add_argument("--out", default="_tmp_compat_test", help="Output directory for test artifacts.")
    parser.add_argument("--turn", type=int, default=1, help="Fake turn number used in event_id generation.")
    args = parser.parse_args()

    out_dir = Path(args.out).expanduser().resolve()

    print_header("START compatibility test")
    print(f"Output directory: {out_dir}")

    runner = CompatTestRunner(out_dir=out_dir, turn_no=args.turn)

    try:
        test_world_tools(runner)
        test_validate_tools(runner)
        test_scene_tools(runner)
        test_mechanics_tools(runner)
        test_entity_tools(runner)
        test_logging_output(runner)

        print_header("ALL TESTS PASSED")
        print("Compatibility between current logging and new tool behavior looks good.")
        print(f"Logs written to: {runner.logs_dir}")
        return 0

    except Exception as exc:
        print_header("TEST FAILED")
        print(f"Error: {exc}")
        print("\nTraceback:")
        traceback.print_exc()
        print("\nPartial in-memory tool trace:")
        for row in runner.results[-5:]:
            print(pretty(row))
            print("-" * 60)
        return 1

    finally:
        runner.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())