from __future__ import annotations

from typing import Iterable, List, Optional, Sequence, Tuple


class History:
    """Keeps a rolling window of conversational turns as plain text."""

    def __init__(self, max_turns: Optional[int] = None) -> None:
        """
        max_turns: None means unbounded; otherwise keep only the most recent N turns.
        """
        self.max_turns = max_turns
        self.turns: List[Tuple[str, str]] = []

    def add_player_turn(self, text: str) -> None:
        self._add("player", text)

    def add_dm_turn(self, text: str) -> None:
        self._add("narrator", text)

    def recent(self, limit: int | None = None) -> Sequence[Tuple[str, str]]:
        lim = limit or self.max_turns
        return self.turns[-lim:]

    def as_text(self, limit: int | None = None) -> str:
        lines = [f"{role.title()}: {content}" for role, content in self.recent(limit)]
        return "\n".join(lines).strip()

    def _add(self, role: str, content: str) -> None:
        text = content.strip()
        if not text:
            return
        self.turns.append((role, text))
        if self.max_turns is not None and len(self.turns) > self.max_turns:
            self.turns = self.turns[-self.max_turns :]


__all__ = ["History"]
