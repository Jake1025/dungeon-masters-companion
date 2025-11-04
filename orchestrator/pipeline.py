from __future__ import annotations

import textwrap
from dataclasses import asdict
from typing import Dict, List, Optional

from .adapter import LLMAdapter
from .history import History
from .story import CanonEntry, StoryCanon, format_entries


NARRATE_PROMPT = """You are the narrator of an interactive text adventure.
You must keep the story grounded in the provided canon material and outline.
Respond with immersive prose addressed to the player. Avoid rules jargon.

Structure your reply with two sections:
Narrative: <the in-world narration, 2-4 paragraphs, second person>
Recap: <one or two sentences summarising key developments for memory>

Do not invent facts that contradict the canon or outline. If the player asks for
knowledge that is unavailable, acknowledge the gap politely and suggest a next
step that fits the existing material.
"""


class Orchestrator:
    """Story-focused orchestrator that keeps context and canon in view."""

    def __init__(
        self,
        *,
        initial_state: Optional[Dict[str, object]] = None,
        model: str = "gpt-oss:20b",
        story_canon: Optional[StoryCanon] = None,
        story_outline: Optional[str] = None,
        verbose: bool = False,
    ) -> None:
        self.game_state: Dict[str, object] = dict(initial_state or {})
        self.history = History(max_turns=8, keep_recent=4)
        self.story_canon = story_canon or StoryCanon()
        if story_outline:
            self.story_canon.outline = story_outline
        self.adapter = LLMAdapter(
            model=model,
            default_temperature=0.6,
            stage_temperatures={
                "narrate": 0.75,
                "summary": 0.4,
            },
            verbose=verbose,
        )
        self.verbose = verbose

    def run_turn(self, player_input: str) -> Dict[str, object]:
        self.history.add_player_turn(player_input)
        context_text = self.history.as_text()
        canon_hits = self.story_canon.search(player_input)

        narrator_input = self._build_narrator_payload(
            player_input=player_input,
            context_text=context_text,
            canon_hits=canon_hits,
        )
        raw_response = self.adapter.request_text("narrate", NARRATE_PROMPT, narrator_input)
        narrative, recap = _parse_narration(raw_response)

        narration_payload = {"ic": narrative, "recap": recap}
        self.history.add_dm_turn(narration_payload)
        self.history.maybe_summarize(self.adapter)

        return {
            "narration": narration_payload,
            "canon": [asdict(entry) for entry in canon_hits],
            "history": self.history.as_context(),
            "summary": self.history.summary.summary if self.history.summary else None,
        }

    def _build_narrator_payload(
        self,
        *,
        player_input: str,
        context_text: str,
        canon_hits: List[CanonEntry],
    ) -> str:
        outline = self.story_canon.outline
        canon_block = format_entries(canon_hits)
        return textwrap.dedent(
            f"""
            Story Outline:
            {outline}

            Canon Notes:
            {canon_block if canon_block else 'No specific excerpt matched; rely on established tone.'}

            Conversation Summary:
            {context_text or 'No previous turns yet.'}

            Player Input:
            {player_input}
            """
        ).strip()


def _parse_narration(raw: str) -> tuple[str, str]:
    lower = raw.lower()
    narrative = raw
    recap = ""
    if "recap:" in lower:
        idx = lower.rfind("recap:")
        recap = raw[idx + len("recap:") :].strip()
        narrative = raw[:idx].strip()
    if narrative.lower().startswith("narrative:"):
        narrative = narrative.split(":", 1)[1].strip()
    return narrative.strip(), recap.strip()


__all__ = ["Orchestrator"]
