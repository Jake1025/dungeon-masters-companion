from __future__ import annotations

import textwrap
from typing import Dict, Iterable, List, Optional

from .adapter import LLMAdapter
from .history import History
from .story import BEAT_LIST, STARTING_STATE, StoryGraph


PLAN_PROMPT = """You are planning the next response in an interactive narrative.
Use the provided story nodes, their connections, and the conversation so far.

Instructions:
- Think step-by-step about the most grounded next move (write under Thoughts).
- The player must drive all agency and change in the story. Do not take actions for them. 
- Capture the actionable plan in 1-3 sentences (write under Plan).
- Do not narrate yet; this is just preparation. 

Format exactly:
Thoughts: <free-form reasoning>
Plan: <concise plan>
"""

VALIDATE_PROMPT = """You are the logic validator.
Examine the proposed plan, story nodes, and conversation.

Instructions:
- Ensure the plan respects the known story information (locks need codes, etc.).
- Confirm it makes sense chronologically and logically.
- Approve only if no conflicts; otherwise request revision.

Format exactly:
Thoughts: <analysis>
Verdict: approve | revise
Notes: <brief justification>
"""

NARRATE_PROMPT = """You are the storyteller.
Use the story nodes, the approved plan, and the validator notes.

Instructions:
- Think privately before writing (Thoughts).
- Produce immersive second-person narration (Narrative) and a one-sentence recap (Recap).
- If additional nodes are needed, add 'Lookup: key one, key two'. Only request connected keys.

Format exactly:
Thoughts: <hidden reasoning>
Narrative: <story prose>
Recap: <summary>
[Optional] Lookup: key one, key two
"""


class Orchestrator:
    def __init__(
        self,
        *,
        model: str = "gpt-oss:20b",
        story_graph: Optional[StoryGraph] = None,
        verbose: bool = False,
    ) -> None:
        self.history = History(max_turns=12)
        self.story = story_graph or StoryGraph()
        self.active_keys: set[str] = set(self.story.initial_keys)
        self.adapter = LLMAdapter(
            model=model,
            default_temperature=0.6,
            stage_temperatures={"narrate": 0.75},
            verbose=verbose,
        )

    def run_turn(self, player_input: str) -> Dict[str, object]:
        self.history.add_player_turn(player_input)
        plan_prompt = self._build_plan_prompt(player_input)
        plan_raw = self.adapter.request_text("plan", PLAN_PROMPT, plan_prompt)
        plan = _parse_plan(plan_raw)

        validate_prompt = self._build_validate_prompt(player_input, plan)
        validate_raw = self.adapter.request_text("validate", VALIDATE_PROMPT, validate_prompt)
        verdict, notes = _parse_validation(validate_raw)

        narrate_prompt = self._build_narrate_prompt(player_input, plan, verdict, notes)
        narrate_raw = self.adapter.request_text("narrate", NARRATE_PROMPT, narrate_prompt)
        narrative, recap, lookup_keys = _parse_narration(narrate_raw)

        unlocked = self._unlock_keys(lookup_keys)
        dm_entry = f"{narrative}\nRecap: {recap}" if recap else narrative
        self.history.add_dm_turn(dm_entry)

        return {
            "plan": plan,
            "validation": {"verdict": verdict, "notes": notes},
            "narration": {"ic": narrative, "recap": recap},
            "unlocked_keys": unlocked,
            "active_keys": sorted(self.active_keys),
        }

    def _build_plan_prompt(self, player_input: str) -> str:
        keys = sorted(self.active_keys)
        return textwrap.dedent(
            f"""
            Starting State:
            {STARTING_STATE}

            Beat Guide:
            {', '.join(BEAT_LIST)}

            Story Nodes:
            {self.story.describe(keys)}

            Connections:
            {self.story.list_connections(keys)}

            Conversation So Far:
            {self.history.as_text(limit=8) or 'No prior conversation.'}

            Player Input:
            {player_input}
            """
        ).strip()

    def _build_validate_prompt(self, player_input: str, plan: str) -> str:
        keys = sorted(self.active_keys)
        return textwrap.dedent(
            f"""
            Starting State:
            {STARTING_STATE}

            Beat Guide:
            {', '.join(BEAT_LIST)}

            Story Nodes:
            {self.story.describe(keys)}

            Connections:
            {self.story.list_connections(keys)}

            Conversation So Far:
            {self.history.as_text(limit=8) or 'No prior conversation.'}

            Player Input:
            {player_input}

            Proposed Plan:
            {plan}
            """
        ).strip()

    def _build_narrate_prompt(self, player_input: str, plan: str, verdict: str, notes: str) -> str:
        keys = sorted(self.active_keys)
        return textwrap.dedent(
            f"""
            Starting State:
            {STARTING_STATE}

            Beat Guide:
            {', '.join(BEAT_LIST)}

            Story Nodes:
            {self.story.describe(keys)}

            Connections:
            {self.story.list_connections(keys)}

            Conversation So Far:
            {self.history.as_text(limit=8) or 'No prior conversation.'}

            Player Input:
            {player_input}

            Validated Plan:
            {plan}

            Validator Verdict: {verdict}
            Validator Notes: {notes}
            """
        ).strip()

    def _unlock_keys(self, keys: Iterable[str]) -> List[str]:
        unlocked: List[str] = []
        for key in keys:
            node = self.story.get_node(key)
            if not node:
                continue
            if key in self.active_keys:
                continue
            self.active_keys.add(key)
            unlocked.append(key)
            for neighbor in node.connections:
                if neighbor in self.story.by_key:
                    self.active_keys.add(neighbor)
        return unlocked


def _parse_plan(raw: str) -> str:
    sections = _parse_sections(raw, {"thoughts", "plan"})
    return sections.get("plan") or raw.strip()


def _parse_validation(raw: str) -> tuple[str, str]:
    sections = _parse_sections(raw, {"thoughts", "verdict", "notes"})
    verdict = sections.get("verdict", "approve")
    notes = sections.get("notes", "")
    return verdict.strip(), notes.strip()


def _parse_narration(raw: str) -> tuple[str, str, List[str]]:
    sections = _parse_sections(raw, {"thoughts", "narrative", "recap", "lookup"})
    narrative = sections.get("narrative", raw.strip())
    recap = sections.get("recap", "")
    lookups = []
    if "lookup" in sections:
        lookups = [token.strip() for token in sections["lookup"].split(",") if token.strip()]
    return narrative.strip(), recap.strip(), lookups


def _parse_sections(text: str, tags: set[str]) -> Dict[str, str]:
    collected: Dict[str, List[str]] = {tag: [] for tag in tags}
    current: str | None = None
    for line in text.splitlines():
        stripped = line.strip()
        lower = stripped.lower()
        matched = None
        for tag in tags:
            prefix = f"{tag}:"
            if lower.startswith(prefix):
                matched = tag
                content = stripped[len(prefix) :].strip()
                collected[tag].append(content)
                current = tag
                break
        if matched is None and current:
            collected[current].append(stripped)
    return {tag: "\n".join(parts).strip() for tag, parts in collected.items() if parts}


__all__ = ["Orchestrator"]
