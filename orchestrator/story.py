from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, List, Sequence


@dataclass(frozen=True)
class CanonEntry:
    title: str
    synopsis: str
    excerpt: str
    keywords: Sequence[str]


DEFAULT_OUTLINE = """
Act I: Arrival at the Shrouded Archives
- The traveler reaches the abandoned mountain library.
- Whispers hint at a hidden chronicle that rewrites history.

Act II: Echoes of the Chronicle
- Guardian spirits test the traveler's intent.
- Secret halls reveal conflicting versions of the past.

Act III: Choosing the True Thread
- The traveler must decide which memory to preserve.
- The world shifts to reflect the chosen truth.
"""


DEFAULT_CANON: List[CanonEntry] = [
    CanonEntry(
        title="The Windway Stair",
        synopsis="A spiraling stairwell carved through glacier glass. Voices ride the wind, repeating fragments of lost chapters.",
        excerpt="Each landing held a frozen lectern. Upon the ice lay pages that thawed at the traveler's touch, sketching scenes of a city that never was.",
        keywords=("stair", "wind", "lectern", "city"),
    ),
    CanonEntry(
        title="Hall of Divergent Mirrors",
        synopsis="Mirrors reflect possible presents rather than the past.",
        excerpt="In one mirror the traveler wore an archivist's robes; in another, the hall stood crowded with petitioners pleading for their memories to be recorded.",
        keywords=("mirror", "hall", "memory", "petition"),
    ),
    CanonEntry(
        title="The Ember Scriptorium",
        synopsis="An underground chamber warmed by braziers that burn without fuel. Ash motes form shifting letters in the air.",
        excerpt="The chronicler-spirit asked only one price: speak a memory aloud and watch the flames devour it, leaving a brighter ember in exchange.",
        keywords=("ember", "flame", "scriptorium", "memory"),
    ),
    CanonEntry(
        title="Garden of Unchosen Paths",
        synopsis="A courtyard where plants grow into symbols of stories that were never told.",
        excerpt="Vines shaped into question marks clung to an archway, trailing petals that shimmered between silver and dusk-blue whenever a decision was near.",
        keywords=("garden", "path", "decision", "vines"),
    ),
]


class StoryCanon:
    """Extremely lightweight search over pre-written canon snippets."""

    def __init__(self, entries: Iterable[CanonEntry] | None = None, outline: str | None = None) -> None:
        self.entries: List[CanonEntry] = list(entries or DEFAULT_CANON)
        self.outline = outline or DEFAULT_OUTLINE

    def search(self, query: str, limit: int = 3) -> List[CanonEntry]:
        words = _tokenize(query)
        if not words:
            return self.entries[:limit]
        scored: List[tuple[int, CanonEntry]] = []
        for entry in self.entries:
            entry_words = {kw.lower() for kw in entry.keywords}
            score = sum(2 for kw in entry_words if kw in words)
            score += sum(1 for word in words if word in entry.synopsis.lower())
            score += sum(1 for word in words if word in entry.excerpt.lower())
            if score:
                scored.append((score, entry))
        if not scored:
            return self.entries[:limit]
        scored.sort(key=lambda item: item[0], reverse=True)
        return [entry for _, entry in scored[:limit]]


def format_entries(entries: Sequence[CanonEntry]) -> str:
    blocks = []
    for idx, entry in enumerate(entries, start=1):
        block = [f"[{idx}] {entry.title}", f"Synopsis: {entry.synopsis}", f"Excerpt: {entry.excerpt}"]
        blocks.append("\n".join(block))
    return "\n\n".join(blocks)


def _tokenize(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-zA-Z]+", text.lower()) if len(token) > 2}


__all__ = ["StoryCanon", "CanonEntry", "format_entries", "DEFAULT_OUTLINE"]
