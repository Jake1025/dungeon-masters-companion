from __future__ import annotations
import argparse
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from .pipeline import StoryEngine
from .story import STARTING_STATE

DEFAULT_MODEL = "gemma3:4b"
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
    # Steps
    # -------------------------
    for step_name, data in trace.items():
        if step_name.startswith("STATE_"):
            continue

        print(f"[LLM] {step_name}")

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

            print(f"\n--- Attempt {attempt_num} ---")

            print("PROMPT:")
            print(truncate(prompt.strip()) or "<empty>")
            print()

            print("RAW:")
            print(truncate(raw.strip()) or "<empty>")
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

            if error:
                print("ERROR:")
                print(error)
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
    print("-" * 60)




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
