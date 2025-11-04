from __future__ import annotations

import argparse
import json

from .pipeline import Orchestrator


DEFAULT_GAME_STATE = {
    "location": "Shrouded Archives",
    "mood": "windswept and echoing with distant whispers",
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Story exploration demo.")
    parser.add_argument("--model", help="Ollama model id", default="gpt-oss:20b")
    parser.add_argument("--verbose", action="store_true", help="Enable adapter debug logging")
    args = parser.parse_args()

    orchestrator = Orchestrator(initial_state=DEFAULT_GAME_STATE, model=args.model, verbose=args.verbose)

    print("Story explorer. Type 'quit' to leave.")
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

        canon = turn.get("canon", [])
        if canon:
            print("Referenced canon:")
            for entry in canon:
                print(f"  - {entry['title']}: {entry['synopsis']}")
            print()

        if args.verbose:
            print("[Debug] History snapshot:")
            print(json.dumps(turn["history"], indent=2))


if __name__ == "__main__":
    main()
