from __future__ import annotations
import argparse
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from .runtime_flow.pipeline import StoryEngine
from .world_state.story import STARTING_STATE

DEFAULT_MODEL = "glm-4.7-flash:q8_0"
DEFAULT_TRUNCATE_LIMIT = 200

def truncate(text: str, limit: int = DEFAULT_TRUNCATE_LIMIT) -> str:
    """
    Shorten long text blocks for terminal display.
    """
    if not text:
        return text
    text = text.lstrip()
    if len(text) <= limit:
        return text
    return text[:limit] + f"...[truncated {len(text) - limit} chars]"


def print_llm_verbose(turn_number: int, trace: Dict[str, Any]) -> None:
    """
    Pretty-print all LLM step debug info for a single turn,
    including retries and optional state snapshot.
    """
    print(f"\n=================================== TURN {turn_number} ===================================\n")

    # -------------------------
    # State BEFORE
    # -------------------------
    state_before = trace.get("STATE_BEFORE")
    if state_before:
        print("STATE SNAPSHOT (BEFORE TURN)")
        print(f"Beat Current: {truncate(state_before.get('beat_current',''),120)}")
        print(f"Beat Next: {truncate(state_before.get('beat_next',''),120)}")
        print(f"Beat Guide: {truncate(state_before.get('beat_guide',''),120)}")

        scene = state_before.get("scene", {})
        print("\nScene:")
        print(f"Location/Focus: {scene.get('location_focus')}")
        print(f"Active Nodes: {scene.get('active_nodes')}")
        print(f"Status: {scene.get('status')}")
        print(
            f"Session Summary: "
            f"{truncate(scene.get('session_summary',''),120)}"
        )
        print("-" * 60)

    # -------------------------
    # State AFTER ACTION (NEW)
    # -------------------------
    state_after_action = trace.get("STATE_AFTER_ACTION")
    if state_after_action:
        print("STATE SNAPSHOT (AFTER ACTION EXECUTION)")
        print(f"Beat Current: {truncate(state_after_action.get('beat_current',''),120)}")
        
        scene = state_after_action.get("scene", {})
        print("\nScene:")
        print(f"Location/Focus: {scene.get('location_focus')}")
        print(f"Active Nodes: {scene.get('active_nodes')}")
        print("-" * 60)

    # -------------------------
    # Steps
    # -------------------------
    for step_name, data in trace.items():
        # Skip special entries
        if step_name.startswith("STATE_") or step_name in {"TOOL_CALLS", "ACTION_TOOLS", "MOVEMENT_BLOCKED"}:
            continue

        print(f"[LLM] {step_name} STEP")

        # Handle different data structures
        if not isinstance(data, dict):
            print(f"Unexpected data type: {type(data)}")
            print("-" * 60)
            continue

        attempts = data.get("attempts", [])

        if not attempts:
            print("No attempts recorded.")
            print("-" * 60)
            continue

        for attempt in attempts:
            attempt_num = attempt.get("attempt")

            prompt = attempt.get("prompt", "")
            raw = attempt.get("raw", "")
            sections = attempt.get("sections", {})
            parsed = attempt.get("parsed")
            error = attempt.get("error")
            error_details = attempt.get("error_details")

            print(f"\n--- Attempt {attempt_num} ---")

            print("PROMPT:")
            print(truncate(prompt.strip()) or "<empty>")
            print()

            print("RAW:")
            print(truncate(raw.strip()) or "<empty>")
            print()

            if error:
                print("ERROR:")
                print(error)
                if error_details:
                    print("\nERROR DETAILS:")
                    for k, v in error_details.items():
                        print(f"  {k}: {truncate(str(v), 200)}")
                print()

            if sections:
                print("SECTIONS:")
                for k, v in sections.items():
                    print(f"{k}: {truncate(str(v), 200)}")
                print()

            if parsed is not None:
                print("PARSED:")
                if isinstance(parsed, dict):
                    for key, value in parsed.items():
                        print(f"{key}={truncate(str(value), 200)}")
                else:
                    print(truncate(str(parsed), 400))
                print()

        # Show tool calls for VALIDATE step
        if step_name == "VALIDATE" and "tool_calls" in data:
            tool_calls = data["tool_calls"]
            if tool_calls:
                print("\nVALIDATION TOOL CALLS:")
                for idx, call in enumerate(tool_calls, 1):
                    print(f"  {idx}. {call['name']}: {truncate(json.dumps(call['result']), 200)}")
                print()

        print("-" * 60)

    # -------------------------
    # Action Tools
    # -------------------------
    action_tools = trace.get("ACTION_TOOLS", [])
    if action_tools:
        print("[ACTION] TOOL EXECUTION")
        print()
        
        if isinstance(action_tools, list):
            if not action_tools:
                print("No actions executed")
            else:
                for idx, call in enumerate(action_tools, 1):
                    print(f"--- Tool Call {idx} ---")
                    print(f"Function: {call.get('name', 'unknown')}")
                    print(f"Arguments: {call.get('arguments', {})}")
                    print(f"Result:")
                    result = call.get('result', {})
                    print(f"  Success: {result.get('success', False)}")
                    print(f"  Reason: {result.get('reason', 'N/A')}")
                    if 'new_location' in result:
                        print(f"  New Location: {result.get('new_location')}")
                    print()
        else:
            print(f"Unexpected ACTION_TOOLS format: {type(action_tools)}")
        
        print("-" * 60)

    # -------------------------
    # Movement Blocked Flag
    # -------------------------
    if trace.get("MOVEMENT_BLOCKED"):
        print("[INFO] Movement was blocked - narration will re-describe current scene")
        print("-" * 60)

    # -------------------------
    # Tool Calls (Old)
    # -------------------------
    tool_calls = trace.get("TOOL_CALLS", [])
    if tool_calls:
        print("[LLM] TOOL_CALLS (Legacy)")
        print()
        for idx, call in enumerate(tool_calls, 1):
            print(f"--- Tool Call {idx} ---")
            print(f"Function: {call['name']}")
            print(f"Arguments: {call['arguments']}")
            print(f"Result:")
            print(truncate(json.dumps(call['result'], indent=2), 400))
            print()
        print("-" * 60)

    # -------------------------
    # State AFTER
    # -------------------------
    state_after = trace.get("STATE_AFTER")
    if state_after:
        print("STATE SNAPSHOT (AFTER TURN)")
        print(f"Beat Current: {truncate(state_after.get('beat_current',''),120)}")
        print(f"Beat Next: {truncate(state_after.get('beat_next',''),120)}")
        print(f"Beat Guide: {truncate(state_after.get('beat_guide',''),120)}")

        scene = state_after.get("scene", {})
        print("\nScene:")
        print(f"Location/Focus: {scene.get('location_focus')}")
        print(f"Active Nodes: {scene.get('active_nodes')}")
        print(f"Status: {scene.get('status')}")
        print(
            f"Session Summary: "
            f"{truncate(scene.get('session_summary',''),120)}"
        )
    print(f"\n=============================== END OF TURN {turn_number} ================================\n")




# =====================================
# Argument Parsing
# =====================================

def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Story exploration demo.")

    parser.add_argument("--model", default=DEFAULT_MODEL, help="Ollama model id")

    parser.add_argument(
        "--start-key",
        dest="start_keys",
        action="append",
        help="Story node key to activate initially (repeatable)",
    )

    parser.add_argument(
        "--starting-state",
        help="Override the starting state text shown to the model",
    )

    parser.add_argument(
        "--session-name",
        default="session",
        help="Name for this play session (used in state folder)",
    )

    parser.add_argument(
        "--state-root",
        default="state",
        help="Directory root for session snapshots",
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show full LLM prompts, raw output, and parsed results",
    )

    return parser


# =====================================
# Main Application
# =====================================

def main() -> None:
    args = build_arg_parser().parse_args()

    # Keep logging quiet; verbose output is handled manually
    logging.basicConfig(level=logging.WARNING)

    if args.verbose:
        print("In verbose mode\n")


    engine = StoryEngine(
        model=args.model,
        verbose=args.verbose,
        initial_keys=args.start_keys,
        starting_state=args.starting_state or STARTING_STATE,
    )

    # ----- Session Folder -----

    session_dir: Path | None = None

    if args.state_root:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        session_dir = Path(args.state_root) / f"{stamp}_{args.session_name}"
        session_dir.mkdir(parents=True, exist_ok=True)
        print(f"Session snapshots will be written to: {session_dir}")

    # ----- Intro -----

    print("Story explorer. Type 'quit' to leave.")

    try:
        intro = engine.generate_intro()
        print(f"\n{intro['ic']}\n")
    except Exception:
        print(f"\n[Intro] {engine.starting_state}\n")

    # Save initial snapshot
    if session_dir:
        try:
            snapshot = engine.snapshot()
            (session_dir / "turn_000.json").write_text(
                json.dumps(snapshot, indent=2),
                encoding="utf-8",
            )
        except Exception as exc:
            logging.warning("Failed to write initial state snapshot: %s", exc)

    # ----- Game Loop -----

    while True:
        try:
            player_line = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            break

        if not player_line:
            continue

        if player_line.lower() in {"quit", "exit"}:
            print("Goodbye.")
            break

        turn: Dict[str, Any] = engine.run_turn(player_line)

        # Verbose LLM Trace
        if args.verbose and turn.get("llm_trace"):
            print_llm_verbose(turn["turn"], turn["llm_trace"])

        # Narrative Output
        print(f"\n{turn['narration']['ic']}\n")

        # Save snapshot
        if session_dir:
            try:
                snapshot = engine.snapshot()
                filename = f"turn_{turn.get('turn', engine.turn_index):03d}.json"
                (session_dir / filename).write_text(
                    json.dumps(snapshot, indent=2),
                    encoding="utf-8",
                )
            except Exception as exc:
                logging.warning("Failed to write state snapshot: %s", exc)


if __name__ == "__main__":
    main()
