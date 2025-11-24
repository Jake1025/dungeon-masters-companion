from __future__ import annotations

import logging
import textwrap
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence

from .adapter import LLMAdapter
from .history import History
from .story import BEAT_LIST, STARTING_STATE, StoryGraph
from .story_data import PostgresStorySource


logger = logging.getLogger(__name__)


PLAN_PROMPT = """You are planning the next response in an interactive narrative.
Use the provided story nodes, their connections, and the conversation so far.

Instructions:
- Think step-by-step about the most grounded next move (write under Thoughts).
- The player must drive all agency and change in the story. Do not take actions for them.
- Work within the current beat; do not jump ahead unless the player pushes time forward or explicitly completes the beat.
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
- Decide if the current beat has been meaningfully fulfilled; set Advance to yes only when the player’s actions/time justify moving to the next beat.

Format exactly:
Thoughts: <analysis>
Verdict: approve | revise
Notes: <brief justification>
Advance: yes | no
"""

NARRATE_PROMPT = """You are the storyteller.
Use the story nodes, the approved plan, and the validator notes.

Instructions:
- Think privately before writing (Thoughts).
- Produce immersive second-person narration (Narrative) and a one-sentence recap (Recap).
- If additional nodes are needed, add 'Lookup: key one, key two'. Only request connected keys.
- Stay within the current beat unless the validator advanced to the next one; you may foreshadow the next beat lightly.
- Set 'Focus: key one, key two' to indicate the primary location/subjects the DM should keep active next turn.

Format exactly:
Thoughts: <hidden reasoning>
Narrative: <story prose>
Recap: <summary>
[Optional] Lookup: key one, key two
[Optional] Focus: key one, key two
"""

INTRO_PROMPT = """You are setting the scene for an interactive narrative.
Use the provided starting state, active story nodes, and current beat to craft a concise introduction.

Instructions:
- Write in second person, immersive but brief (3-6 sentences).
- Do not assume player actions or decisions; just describe the scene and immediate situation.
- Avoid offering explicit choices; keep it open for the player to act next.

Format exactly:
Thoughts: <hidden reasoning>
Narrative: <scene-setting prose>
Recap: <one-line condensation>
"""


@dataclass
class BeatTracker:
    beats: List[str]
    index: int = 0

    def current(self) -> str:
        return self.beats[self.index] if self.beats else ""

    def next(self) -> str:
        if not self.beats:
            return ""
        nxt = self.index + 1
        return self.beats[nxt] if 0 <= nxt < len(self.beats) else ""

    def progress_text(self) -> str:
        if not self.beats:
            return "No beats provided."
        return f"{self.index + 1}/{len(self.beats)}: {self.current()}"

    def advance(self) -> None:
        if self.index + 1 < len(self.beats):
            self.index += 1


class SessionSummary:
    """Compact rolling summary of the session (player + recap highlights)."""

    def __init__(self, max_items: int | None = None, max_chars: int | None = None) -> None:
        self.events: List[str] = []
        self.max_items = max_items
        self.max_chars = max_chars

    def add(self, label: str, text: str) -> None:
        cleaned = text.strip()
        if not cleaned:
            return
        entry = f"{label}: {cleaned}"
        self.events.append(entry)
        self._trim()

    def text(self) -> str:
        return "\n".join(self.events)

    def _trim(self) -> None:
        if self.max_items is None and self.max_chars is None:
            return
        while True:
            if self.max_items is not None and len(self.events) > self.max_items:
                self.events = self.events[1:]
                continue
            if self.max_chars is not None and len(self.text()) > self.max_chars:
                self.events = self.events[1:]
                continue
            break


class Orchestrator:
    def __init__(
        self,
        *,
        model: str = "gpt-oss:20b",
        story_graph: Optional[StoryGraph] = None,
        campaign_key: Optional[str] = None,
        pg_dsn: Optional[str] = None,
        initial_keys: Optional[Sequence[str]] = None,
        beats: Optional[Sequence[str]] = None,
        starting_state: str = STARTING_STATE,
        verbose: bool = False,
    ) -> None:
        self.history = History(max_turns=None)
        self.starting_state = starting_state
        self.beat_list = list(beats or BEAT_LIST)
        self.beats = BeatTracker(self.beat_list)
        self.summary = SessionSummary()
        self.story_source: PostgresStorySource | None = None

        graph = story_graph
        loaded_beats: List[str] | None = None
        if graph is None and campaign_key:
            try:
                self.story_source = PostgresStorySource(campaign_key=campaign_key, dsn=pg_dsn)
                graph, loaded_beats = self.story_source.build_graph(initial_keys=initial_keys)
            except Exception as exc:
                logger.warning(
                    "Falling back to built-in story graph; could not load campaign '%s': %s",
                    campaign_key,
                    exc,
                )

        self.story = graph or StoryGraph(initial_keys=initial_keys)
        if loaded_beats:
            self.beat_list = loaded_beats
            self.beats = BeatTracker(self.beat_list)

        self.discovered_keys: set[str] = set(self.story.initial_keys)
        self.current_focus: List[str] = list(self.story.initial_keys[:1])
        self.active_keys: set[str] = set()
        self._refresh_active_keys()
        self.adapter = LLMAdapter(
            model=model,
            default_temperature=0.6,
            stage_temperatures={"narrate": 0.75},
            verbose=verbose,
        )

    def run_turn(self, player_input: str) -> Dict[str, object]:
        # refresh active slice before building prompts
        self._refresh_active_keys()
        self.history.add_player_turn(player_input)
        self.summary.add("Player", player_input)
        plan_prompt = self._build_plan_prompt(player_input)
        plan_raw = self.adapter.request_text("plan", PLAN_PROMPT, plan_prompt)
        plan = _parse_plan(plan_raw)

        validate_prompt = self._build_validate_prompt(player_input, plan)
        validate_raw = self.adapter.request_text("validate", VALIDATE_PROMPT, validate_prompt)
        verdict, notes, advance = _parse_validation(validate_raw)
        if advance and verdict.lower().startswith("approve"):
            self.beats.advance()

        narrate_prompt = self._build_narrate_prompt(player_input, plan, verdict, notes)
        narrate_raw = self.adapter.request_text("narrate", NARRATE_PROMPT, narrate_prompt)
        narrative, recap, lookup_keys, focus_keys = _parse_narration(narrate_raw)

        # Load any missing nodes from source before updating focus/discovery
        self._expand_from_source(lookup_keys + focus_keys)

        # Update focus if the model provided it
        if focus_keys:
            self.current_focus = [k for k in focus_keys if k in self.story.by_key]

        unlocked = self._register_discovery(lookup_keys + focus_keys)
        self._refresh_active_keys(explicit_keys=lookup_keys + focus_keys)

        dm_entry = f"{narrative}\nRecap: {recap}" if recap else narrative
        self.history.add_dm_turn(dm_entry)
        if recap:
            self.summary.add("Recap", recap)

        return {
            "plan": plan,
            "validation": {"verdict": verdict, "notes": notes, "advance": advance},
            "narration": {"ic": narrative, "recap": recap},
            "unlocked_keys": unlocked,
            "active_keys": sorted(self.active_keys),
            "focus": list(self.current_focus),
            "discovered_keys": sorted(self.discovered_keys),
            "beat_state": {
                "current_index": self.beats.index,
                "current": self.beats.current(),
                "next": self.beats.next(),
            },
            "session_summary": self.summary.text(),
        }

    def generate_intro(self) -> Dict[str, str]:
        prompt = self._build_intro_prompt()
        intro_raw = self.adapter.request_text("intro", INTRO_PROMPT, prompt)
        narrative, recap, _ = _parse_narration(intro_raw)
        dm_entry = f"{narrative}\nRecap: {recap}" if recap else narrative
        self.history.add_dm_turn(dm_entry)
        if recap:
            self.summary.add("Intro", recap)
        return {"ic": narrative, "recap": recap}

    def snapshot(self) -> Dict[str, object]:
        """Return a JSON-serializable snapshot of the current session state."""
        nodes = []
        for key, node in self.story.by_key.items():
            nodes.append(
                {
                    "key": key,
                    "description": node.description,
                    "connections": list(node.connections),
                    "flags": {
                        "active": key in self.active_keys,
                        "focus": key in self.current_focus,
                        "discovered": key in self.discovered_keys,
                    },
                }
            )
        edges = []
        seen_edges = set()
        for key, node in self.story.by_key.items():
            for neighbor in node.connections:
                if neighbor not in self.story.by_key:
                    continue
                edge_key = tuple(sorted((key, neighbor)))
                if edge_key in seen_edges:
                    continue
                seen_edges.add(edge_key)
                edges.append({"src": key, "dst": neighbor})

        history_turns = [{"role": role, "content": content} for role, content in self.history.turns]

        return {
            "beat_state": {
                "current_index": self.beats.index,
                "current": self.beats.current(),
                "next": self.beats.next(),
            },
            "active_keys": sorted(self.active_keys),
            "focus": list(self.current_focus),
            "discovered_keys": sorted(self.discovered_keys),
            "session_summary": self.summary.text(),
            "history": history_turns,
            "nodes": nodes,
            "edges": edges,
        }

    def _build_plan_prompt(self, player_input: str) -> str:
        keys = sorted(self.active_keys)
        beat_text = self._beat_guide()
        summary = self._summary_text()
        return textwrap.dedent(
            f"""
            Starting State:
            {self.starting_state}

            Beat Guide:
            {beat_text}

            Current Beat:
            {self.beats.progress_text()}
            Next Beat:
            {self.beats.next() or 'None'}

            Story Nodes:
            {self.story.describe(keys)}

            Connections:
            {self.story.list_connections(keys)}

            Session Summary:
            {summary}

            Conversation So Far:
            {self.history.as_text(limit=8) or 'No prior conversation.'}

            Player Input:
            {player_input}
            """
        ).strip()

    def _build_validate_prompt(self, player_input: str, plan: str) -> str:
        keys = sorted(self.active_keys)
        beat_text = self._beat_guide()
        summary = self._summary_text()
        return textwrap.dedent(
            f"""
            Starting State:
            {self.starting_state}

            Beat Guide:
            {beat_text}

            Current Beat:
            {self.beats.progress_text()}
            Next Beat:
            {self.beats.next() or 'None'}

            Story Nodes:
            {self.story.describe(keys)}

            Connections:
            {self.story.list_connections(keys)}

            Session Summary:
            {summary}

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
        beat_text = self._beat_guide()
        summary = self._summary_text()
        return textwrap.dedent(
            f"""
            Starting State:
            {self.starting_state}

            Beat Guide:
            {beat_text}

            Current Beat:
            {self.beats.progress_text()}
            Next Beat:
            {self.beats.next() or 'None'}

            Story Nodes:
            {self.story.describe(keys)}

            Connections:
            {self.story.list_connections(keys)}

            Session Summary:
            {summary}

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

    def _build_intro_prompt(self) -> str:
        keys = sorted(self.active_keys)
        beat_text = self._beat_guide()
        summary = self._summary_text()
        return textwrap.dedent(
            f"""
            Starting State:
            {self.starting_state}

            Beat Guide:
            {beat_text}

            Current Beat:
            {self.beats.progress_text()}
            Next Beat:
            {self.beats.next() or 'None'}

            Story Nodes:
            {self.story.describe(keys)}

            Connections:
            {self.story.list_connections(keys)}

            Session Summary:
            {summary}

            Conversation So Far:
            {self.history.as_text(limit=4) or 'No prior conversation.'}
            """
        ).strip()

    def _beat_guide(self) -> str:
        return ", ".join(self.beat_list) if self.beat_list else "No beats provided."

    def _summary_text(self) -> str:
        return self.summary.text() or "No significant actions yet."

    def _refresh_active_keys(self, explicit_keys: Iterable[str] | None = None) -> List[str]:
        explicit = {k for k in (explicit_keys or []) if k in self.story.by_key}
        focus = [k for k in self.current_focus if k in self.story.by_key]
        if not focus and self.story.initial_keys:
            focus = [self.story.initial_keys[0]]
            self.current_focus = focus

        active: List[str] = []

        def add(key: str) -> None:
            if key and key in self.story.by_key and key not in active:
                active.append(key)

        # Always include focus nodes
        for key in focus:
            add(key)

        # Neighbors of focus nodes
        for key in focus:
            node = self.story.get_node(key)
            if not node:
                continue
            for neighbor in node.connections:
                add(neighbor)

        # Explicit keys (e.g., from Lookup/Focus output)
        for key in explicit:
            add(key)

        # Beat-pinned heuristic: include nodes whose keys appear verbatim in the current beat text
        beat_text = self.beats.current().lower()
        if beat_text:
            for key in self.story.by_key:
                if key.lower() in beat_text:
                    add(key)

        # Cap size; keep focus first, then explicit, then others
        MAX_ACTIVE = 14
        if len(active) > MAX_ACTIVE:
            keep: List[str] = []
            seen = set()
            for key in focus:
                if key not in seen:
                    keep.append(key)
                    seen.add(key)
            for key in explicit:
                if key not in seen:
                    keep.append(key)
                    seen.add(key)
            for key in active:
                if key not in seen:
                    keep.append(key)
                    seen.add(key)
                if len(keep) >= MAX_ACTIVE:
                    break
            active = keep

        self.active_keys = set(active)
        return active

    def _expand_from_source(self, keys: Iterable[str]) -> List[str]:
        if not self.story_source:
            return []
        added: List[str] = []
        for key in keys:
            if not key or self.story.get_node(key):
                continue
            try:
                nodes = self.story_source.fetch_node_and_neighbors(key)
            except Exception as exc:
                logger.warning("Lookup for key '%s' failed: %s", key, exc)
                continue
            merged = self.story.upsert_nodes(nodes)
            for node in merged:
                if node.key not in added and node.key not in self.active_keys:
                    added.append(node.key)
        return added

    def _register_discovery(self, keys: Iterable[str]) -> List[str]:
        unlocked: List[str] = []
        for key in keys:
            if key in self.discovered_keys:
                continue
            if key not in self.story.by_key:
                continue
            self.discovered_keys.add(key)
            unlocked.append(key)
        return unlocked


def _parse_plan(raw: str) -> str:
    sections = _parse_sections(raw, {"thoughts", "plan"})
    return sections.get("plan") or raw.strip()


def _parse_validation(raw: str) -> tuple[str, str, bool]:
    sections = _parse_sections(raw, {"thoughts", "verdict", "notes", "advance"})
    verdict = sections.get("verdict", "approve")
    notes = sections.get("notes", "")
    advance_raw = sections.get("advance", "no").lower()
    advance = advance_raw.startswith("y")
    return verdict.strip(), notes.strip(), advance


def _parse_narration(raw: str) -> tuple[str, str, List[str], List[str]]:
    sections = _parse_sections(raw, {"thoughts", "narrative", "recap", "lookup", "focus"})
    narrative = sections.get("narrative", raw.strip())
    recap = sections.get("recap", "")
    lookups = []
    if "lookup" in sections:
        lookups = [token.strip() for token in sections["lookup"].split(",") if token.strip()]
    focus = []
    if "focus" in sections:
        focus = [token.strip() for token in sections["focus"].split(",") if token.strip()]
    return narrative.strip(), recap.strip(), lookups, focus


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
