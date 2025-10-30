from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict, List, Optional

from .adapter import LLMAdapter
from .schemas import HistorySummary, HistoryTurn


SUMMARY_PROMPT = (
    "You are the campaign chronicler. Summarize the adventure so far in under 120 words. "
    "Return JSON {\"summary\": \"...\"}. Use only the provided turns."
)


class History:
    """Tracks player/DM turns and maintains a running summary when context grows."""

    def __init__(self, max_turns: int = 8, keep_recent: int = 4) -> None:
        self.turns: List[HistoryTurn] = []
        self.summary: Optional[HistorySummary] = None
        self.max_turns = max_turns
        self.keep_recent = keep_recent

    def add_player_turn(self, player_input: str) -> None:
        payload = {"player_input": player_input}
        self.turns.append(HistoryTurn(role="player", payload=payload))

    def add_dm_turn(self, narration: Dict[str, Any]) -> None:
        self.turns.append(HistoryTurn(role="dm", payload=narration))

    def as_context(self) -> Dict[str, Any]:
        context = {
            "turns": [asdict(turn) for turn in self.turns[-self.max_turns :]],
        }
        if self.summary is not None:
            context["summary"] = self.summary.summary
        return context

    def maybe_summarize(self, adapter: LLMAdapter) -> None:
        if len(self.turns) < self.max_turns:
            return
        payload = {
            "turns": [asdict(turn) for turn in self.turns],
        }
        try:
            data = adapter.request_json(
                "summary",
                SUMMARY_PROMPT,
                payload,
                validator=_validate_summary,
            )
        except Exception:
            # Non-fatal: keep current turn buffer and try again later.
            return
        summary = data.get("summary", "").strip()
        if summary:
            self.summary = HistorySummary(summary=summary, turns=self.turns[-self.keep_recent :])
            self.turns = self.turns[-self.keep_recent :]


def _validate_summary(payload: Dict[str, Any]) -> None:
    if not isinstance(payload, dict):
        raise TypeError("Summary payload must be an object")
    summary = payload.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        raise ValueError("Summary must contain a non-empty 'summary' string")


__all__ = ["History"]
