from __future__ import annotations

import argparse
import logging

from .adapter import LLMError
from .pipeline import Orchestrator


DEFAULT_GAME_STATE = {
    "scene": {
        "id": "tavern",
        "lighting": "dim",
        "environment": "indoors",
        "description": "A cold tavern filled with snow and shivering patrons.",
    },
    "actors": {
        "Bartender": {
            "skills": {
                "Persuasion": 14,
                "Perception": 12,
                "Arcana": 6,
                "Dexterity": 10,
                "Constitution": 14,
                "Intelligence": 12,
                "Wisdom": 14,
                "Charisma": 16,
                "Strength": 10,
                "Stealth": 8,
                "Intimidation": 10,
                "Deception": 12,
            },
            "inventory": {
                "gold": 200,
                "items": ["bartender's kit", "flask of whiskey"],
            },
            "hp": 30,
            "conditions": [],
        },
        "Jake": {
            "skills": {
                "Persuasion": 12,
                "Perception": 16,
                "Arcana": 20,
                "Dexterity": 12,
                "Constitution": 10,
                "Intelligence": 18,
                "Wisdom": 16,
                "Charisma": 8,
                "Strength": 14,
                "Stealth": 8,
                "Intimidation": 12,
                "Deception": 8,
            },
            "inventory": {
                "gold": 150,
                "items": ["short sword", "leather armor", "healing potion"],
            },
            "hp": 22,
            "conditions": [],
        },
    },
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the four-stage DM orchestrator demo.")
    parser.add_argument("--model", help="Override the Ollama model id to use.", default=None)
    parser.add_argument("--verbose", action="store_true", help="Enable verbose stage logging.")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(levelname)s:%(name)s:%(message)s",
        force=True,
    )

    model_id = args.model or "gpt-oss:20b"
    orchestrator = Orchestrator(initial_state=DEFAULT_GAME_STATE, model=model_id, verbose=args.verbose)
    print("Four-stage DM orchestrator demo. Type 'quit' to exit.")
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
        try:
            turn = orchestrator.run_turn(player_line)
        except LLMError as exc:
            print(f"[ERROR] LLM failed to return valid JSON: {exc}")
            continue

        for execution in turn["results"]["executions"]:
            status = execution["status"]
            tool = execution["tool"]
            if status == "ok":
                print(f"[TOOL] {tool} -> ok")
            else:
                error = execution.get("error", "unknown error")
                print(f"[TOOL] {tool} -> {status}: {error}")

        response = turn["response"]
        print(f"DM: {response['ic']}")
        if response["ooc"].get("recap"):
            print(f"[RECAP] {response['ooc']['recap']}")


if __name__ == "__main__":
    main()
