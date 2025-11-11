from __future__ import annotations

import argparse

from .pipeline import Orchestrator


def main() -> None:
    parser = argparse.ArgumentParser(description="Story exploration demo.")
    parser.add_argument("--model", help="Ollama model id", default="gpt-oss:20b")
    parser.add_argument("--verbose", action="store_true", help="Enable adapter debug logging")
    args = parser.parse_args()

    orchestrator = Orchestrator(model=args.model, verbose=args.verbose)

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
        unlocked = turn.get("unlocked_keys") or []
        if unlocked:
            print("[New Keys] " + ", ".join(unlocked))
            print()

        if args.verbose:
            print(f"[Plan] {turn.get('plan', '')}")
            validation = turn.get("validation", {})
            if validation:
                print(f"[Validation] {validation.get('verdict', '')}: {validation.get('notes', '')}")
            print("[Debug] Active keys:")
            print(", ".join(turn.get("active_keys", [])))


if __name__ == "__main__":
    main()
