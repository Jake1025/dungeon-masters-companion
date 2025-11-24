from __future__ import annotations

import argparse
import logging

from .pipeline import Orchestrator
from .story import STARTING_STATE


def main() -> None:
    parser = argparse.ArgumentParser(description="Story exploration demo.")
    parser.add_argument("--model", help="Ollama model id", default="gpt-oss:20b")
    parser.add_argument("--campaign-key", help="Load story nodes/beats from Postgres story.* schema")
    parser.add_argument(
        "--pg-dsn",
        help="Postgres DSN for campaign lookup (defaults to PG_DSN env or local docker-compose value)",
    )
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
        "--state-dump",
        help="Optional path to write a JSON snapshot of state after each turn (for external viewers)",
    )
    parser.add_argument("--verbose", action="store_true", help="Enable adapter debug logging")
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.WARNING)

    orchestrator = Orchestrator(
        model=args.model,
        verbose=args.verbose,
        campaign_key=args.campaign_key,
        pg_dsn=args.pg_dsn,
        initial_keys=args.start_keys,
        starting_state=args.starting_state or STARTING_STATE,
    )

    print("Story explorer. Type 'quit' to leave.")
    try:
        intro = orchestrator.generate_intro()
        print(f"\n{intro['ic']}\n")
        if intro.get("recap"):
            print(f"[Recap] {intro['recap']}\n")
    except Exception:
        # Fall back to plain starting state if intro generation fails
        print(f"\n[Intro] {orchestrator.starting_state}\n")
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

        turn = orchestrator.run_turn(player_line)
        narration = turn["narration"]
        print(f"\n{narration['ic']}\n")
        if narration.get("recap"):
            print(f"[Recap] {narration['recap']}\n")
        unlocked = turn.get("unlocked_keys") or []
        if unlocked:
            print("[New Keys] " + ", ".join(unlocked))
            print()

        if args.verbose:
            print(f"[Plan] {turn.get('plan', '')}")
            validation = turn.get("validation", {})
            if validation:
                print(f"[Validation] {validation.get('verdict', '')}: {validation.get('notes', '')}")
                if "advance" in validation:
                    print(f"[Beat Advance Requested] {validation['advance']}")
            beat_state = turn.get("beat_state", {})
            if beat_state:
                cur = beat_state.get("current")
                nxt = beat_state.get("next")
                print(f"[Beat] {beat_state.get('current_index', 0)+1}: {cur}")
                if nxt:
                    print(f"[Next Beat] {nxt}")
            focus = turn.get("focus") or []
            if focus:
                print("[Focus] " + ", ".join(focus))
            print("[Debug] Active keys:")
            print(", ".join(turn.get("active_keys", [])))
            discovered = turn.get("discovered_keys") or []
            if discovered:
                print(f"[Discovered] {', '.join(discovered)}")
            summary = turn.get("session_summary")
            if summary:
                print("[Summary]")
                print(summary)

        if args.state_dump:
            try:
                import json
                from pathlib import Path

                snapshot = orchestrator.snapshot()
                Path(args.state_dump).write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
            except Exception as exc:
                logging.warning("Failed to write state snapshot: %s", exc)


if __name__ == "__main__":
    main()
