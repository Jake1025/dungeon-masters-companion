from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict, List, Optional

from .adapter import LLMAdapter
from .schemas import HistorySummary, HistoryTurn


SUMMARY_PROMPT = (
    "You are the campaign chronicler. Summarize the adventure so far in under 120 words. "
    "Respond with plain prose only—no JSON, no bullet list. Use only the provided turns."
)


class History:
    """Tracks player/DM turns and maintains a running summary when context grows."""

    def __init__(self, max_turns: int = 8, keep_recent: int = 4) -> None:
        self.turns: List[HistoryTurn] = []
        self.summary: Optional[HistorySummary] = None
        self.max_turns = max_turns
        self.keep_recent = keep_recent

    def add_player_turn(self, player_input: str) -> None:
        payload = {"text": player_input}
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
        turns_text = _render_turns(self.turns)
        try:
            summary = adapter.request_text(
                "summary",
                SUMMARY_PROMPT,
                turns_text,
            ).strip()
        except Exception:
            return
        if summary:
            self.summary = HistorySummary(summary=summary, turns=self.turns[-self.keep_recent :])
            self.turns = self.turns[-self.keep_recent :]

    def as_text(self, max_turns: Optional[int] = None) -> str:
        turns = self.turns[-(max_turns or self.max_turns) :]
        lines: List[str] = []
        if self.summary is not None:
            lines.append(f"Summary so far: {self.summary.summary}")
        for turn in turns:
            if turn.role == "player":
                text = turn.payload.get("text") if isinstance(turn.payload, dict) else str(turn.payload)
                lines.append(f"Player: {text}")
            else:
                payload = turn.payload
                if isinstance(payload, dict):
                    ic = payload.get("ic") or payload.get("text") or payload.get("narrative")
                    recap = payload.get("recap")
                    if ic:
                        lines.append(f"Narrator: {ic}")
                    if recap:
                        lines.append(f"Recap noted: {recap}")
                else:
                    lines.append(f"Narrator: {payload}")
        return "\n".join(lines).strip()


def _render_turns(turns: List[HistoryTurn]) -> str:
    lines = []
    for turn in turns:
        prefix = "Player" if turn.role == "player" else "Narrator"
        payload = turn.payload
        if isinstance(payload, dict):
            if turn.role == "player":
                text = payload.get("text") or payload.get("player_input")
            else:
                text = payload.get("ic") or payload.get("text") or payload.get("narrative")
                recap = payload.get("recap")
                if recap:
                    text = f"{text} (Recap: {recap})" if text else f"Recap: {recap}"
            if text:
                lines.append(f"{prefix}: {text}")
        else:
            lines.append(f"{prefix}: {payload}")
    return "\n".join(lines)


__all__ = ["History"]
