from typing import Any, Dict, Sequence, Optional
from .conversation_log import History
from ..world_state.story import StoryGraph, BEAT_LIST, STARTING_STATE
from ..llm_interaction.adapter import LLMAdapter
from .session_state import BeatTracker, SessionSummary, ActiveKeyManager, FocusManager, SnapshotBuilder
from .step_registry import build_steps
from ..llm_interaction.prompt_builders import (
    PromptState,
    build_intro_prompt,
    build_intent_prompt,
    build_focus_prompt,
    build_plan_prompt,
    build_validate_prompt,
    build_narrate_prompt,
    build_status_prompt,
)


class StoryEngine:

    def __init__(
        self,
        *,
        model: str = "gemma3:4b",
        story_graph: Optional[StoryGraph] = None,
        initial_keys: Optional[Sequence[str]] = None,
        beats: Optional[Sequence[str]] = None,
        starting_state: str = STARTING_STATE,
        verbose: bool = False,
    ) -> None:

        self.history = History()
        self.summary = SessionSummary()
        self.turn_index = 0
        self.story_status = ""

        self.beats = BeatTracker(list(beats or BEAT_LIST))

        self.story = story_graph or StoryGraph(initial_keys=initial_keys)
        self.starting_state = starting_state
        self.current_focus = list(self.story.initial_keys[:1])
        self.discovered_keys = set(self.story.initial_keys)
        self.active_keys = set()

        self.adapter = LLMAdapter(
            model=model,
            default_temperature=0.6,
            stage_temperatures={"narrate": 0.75},
            verbose=verbose,
        )


        self.steps = build_steps()
        self.focus_manager = FocusManager()
        self.active_manager = ActiveKeyManager()
        self.snapshot_builder = SnapshotBuilder()

        self.active_keys = self.active_manager.refresh(
            self.story,
            self.current_focus,
            beat_text=self.beats.current(),
        )

    # -----------------------

    def _make_state(self, player_input, intent):
        return PromptState(
            history_text=self.history.as_text(limit=8),
            active_keys=sorted(self.active_keys),
            focus=self.current_focus,
            beat_current=self.beats.progress_text(),
            beat_next=self.beats.next() or "None",
            beat_guide=", ".join(self.beats.beats),
            story_status=self.story_status,
            session_summary=self.summary.text(),
            intent=intent,
            player_input=player_input,
        )

    # -----------------------
    def run_turn(self, player_input: str):

        trace = {} if self.adapter.verbose else None

        # -----------------------
        # INTENT
        # -----------------------

        intent_prompt = build_intent_prompt(
            self.history.as_text(limit=6),
            player_input,
        )

        intent, intent_debug = self.steps["intent"].run(
            self.adapter,
            intent_prompt,
        )

        if trace is not None:
            trace["INTENT"] = intent_debug

        # -----------------------

        self.current_focus = self.focus_manager.apply_intent(
            intent,
            self.current_focus,
            self.story,
        )

        self.active_keys = self.active_manager.refresh(
            self.story,
            self.current_focus,
            beat_text=self.beats.current(),
        )


        def build_state_snapshot():
            return {
                "beat_current": state.beat_current,
                "beat_next": state.beat_next,
                "beat_guide": state.beat_guide,
                "scene": {
                    "location_focus": state.focus,
                    "active_nodes": sorted(self.active_keys),
                    "status": state.story_status,
                    "session_summary": state.session_summary,
                },
            }
        
        state = self._make_state(player_input, intent)
        if trace is not None:
            trace["STATE_BEFORE"] = build_state_snapshot()




        # -----------------------
        # PLAN
        # -----------------------

        plan_prompt = build_plan_prompt(state)

        plan, plan_debug = self.steps["plan"].run(
            self.adapter,
            plan_prompt,
        )

        # if trace is not None:
        #     trace["PLAN"] = {
        #         **plan_debug,
        #         "state": state_snapshot,
        #     }
        if trace is not None:
            trace["PLAN"] = plan_debug



        # -----------------------
        # VALIDATE
        # -----------------------

        validate_prompt = build_validate_prompt(state, plan)

        (verdict, notes, advance), validate_debug = self.steps["validate"].run(
            self.adapter,
            validate_prompt,
        )

        # if trace is not None:
        #     trace["VALIDATE"] = {
        #         **validate_debug,
        #         "state": state_snapshot,
        #     }
        if trace is not None:
            trace["VALIDATE"] = validate_debug

        if advance:
            self.beats.advance()

        # -----------------------
        # NARRATE
        # -----------------------

        narrate_prompt = build_narrate_prompt(
            state, plan, verdict, notes
        )

        narrative, narrate_debug = self.steps["narrate"].run(
            self.adapter,
            narrate_prompt,
        )

        # if trace is not None:
        #     trace["NARRATE"] = {
        #         **narrate_debug,
        #         "state": state_snapshot,
        #     }
        if trace is not None:
            trace["NARRATE"] = narrate_debug


        # -----------------------
        # COMMIT TURN
        # -----------------------

        self.history.add_player_turn(player_input)
        self.history.add_dm_turn(narrative)
        self.summary.add("Recap", narrative)
        self.turn_index += 1

        result = {
            "turn": self.turn_index,
            "narration": {"ic": narrative},
            "intent": intent,
            "beat": self.beats.current(),
            "active_keys": sorted(self.active_keys),
            "focus": self.current_focus,
        }

        if trace is not None:
            trace["STATE_AFTER"] = build_state_snapshot()
            result["llm_trace"] = trace

        return result

    # -----------------------
    def generate_intro(self):

        state = PromptState(
            history_text=self.history.as_text(limit=4),
            active_keys=sorted(self.active_keys),
            focus=self.current_focus,
            beat_current=self.beats.progress_text(),
            beat_next=self.beats.next() or "None",
            beat_guide=", ".join(self.beats.beats),
            story_status=self.story_status,
            session_summary=self.summary.text(),
            intent={},          # no intent yet
            player_input="",    # no input yet
        )

        prompt = build_intro_prompt(state)

        narrative, _ = self.steps["narrate"].run(
            self.adapter,
            prompt,
        )

        self.history.add_dm_turn(narrative)
        self.summary.add("Intro", narrative)

        return {"ic": narrative, "recap": ""}




    # -----------------------

    def snapshot(self):
        return self.snapshot_builder.build(self)
