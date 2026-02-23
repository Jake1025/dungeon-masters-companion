from typing import Any, Dict, Sequence, Optional

from pathlib import Path

from ..world_state.persistence.state_store import StateStore

from .conversation_log import History
from ..world_state.story import StoryGraph, BEAT_LIST, STARTING_STATE
from ..llm_interaction.adapter import LLMAdapter
from .session_state import BeatTracker, SessionSummary, ActiveKeyManager, FocusManager, SnapshotBuilder
from .step_registry import build_steps
from .step import parse_sections, validate_narration_step
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
from ..world_state.story import create_initial_game_state, NodeType
import json
#from ..world_state.tools import TOOL_DEFINITIONS, VALIDATE_TOOLS, execute_tool, move_to_location
from ..world_state.tools import TOOL_DEFINITIONS, VALIDATE_TOOLS, execute_tool


def _repo_root_from_pipeline() -> Path:
    """
    EN: repo_root/orchestrator/runtime_flow/pipeline.py -> repo_root
    中文：从 pipeline.py 推断仓库根目录
    """
    return Path(__file__).resolve().parents[2]


def _default_world_state_path() -> Path:
    """
    EN: Default world_state.json -> <repo_root>/state/world_state.json
    中文：默认 world_state.json 路径
    """
    repo_root = _repo_root_from_pipeline()
    state_dir = repo_root / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    return state_dir / "world_state.json"

class StoryEngine:

    def __init__(
        self,
        *,
        model: str = "qwen3:8B",
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

        self.game_state = create_initial_game_state(self.story)
        # EN: Persistent "current world" snapshot store (atomic overwrite).
        # 中文：世界“当前状态”快照存储（原子覆盖写）。
        self.state_store = StateStore(_default_world_state_path())

        self.adapter = LLMAdapter(
            model=model,
            default_options={
                "temperature": 0.2,
                "top_p": 0.5,
                "repeat_penalty": 1.0, # No penalty for repeating tokens (deterministic)
                "top_k": 10, # Only consider top 10 most likely tokens (very narrow)
                "min_p": 0.1, # Minimum probability threshold
            },
            stage_options={
                "narrate": {
                    "temperature": 0.75,
                    "top_p": 0.93,
                    "repeat_penalty": 1.15, # Penalize repetition (more varied prose)
                    "top_k": 50, #wider variety
                    "min_p": 0.05, 
                },
            },
            verbose=verbose,
            # force_retry_stage="plan"
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
        entity_info = {}
        for key in self.active_keys:
            node = self.story.get_node(key)
            if node is None:
                continue

            info = {
                "node_type": node.node_type.value,
                "connections": ", ".join(node.connections) if node.connections else "none",
            }

            if node.node_type == NodeType.LOCATION:
                info["location"] = key
                info["discovered"] = key in self.game_state.discovered_keys

            elif node.node_type == NodeType.NPC:
                #npc_locations first, then fall back to home connection
                info["location"] = (
                    self.game_state.npc_locations.get(key)
                    or (node.connections[0] if node.connections else "unknown")
                )

            elif node.node_type in (NodeType.ITEM, NodeType.CLUE):
                #so the ittems are static and their location is always connections[0]
                info["location"] = node.connections[0] if node.connections else "unknown"

            #any relevant quest flags for this entity
            relevant_flags = {
                flag: val
                for flag, val in self.game_state.quest_flags.items()
                if key.lower().replace(" ", "_") in flag.lower()
            }
            if relevant_flags:
                info["flags"] = ", ".join(
                    f"{k}={'yes' if v else 'no'}" for k, v in relevant_flags.items()
                )

            entity_info[key] = info

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
            entity_info=entity_info,
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
        # Handle implicit_move by moving player (without changing intent)
        # -----------------------

        move_result: Optional[Dict[str, Any]] = None  # EN: always init | 中文：始终初始化避免 UnboundLocalError

        if intent.get("implicit_move") and intent.get("targets"):
            target = intent["targets"][0]

            # EN: Only attempt implicit movement if target is a location.
            # 中文：仅当目标确实是地点时才尝试 implicit move。
            target_node = self.story.get_node(target)
            if target_node and target_node.node_type == NodeType.LOCATION:
                # EN: Use execute_tool so we don't rely on direct import of move_to_location.
                # 中文：统一走 execute_tool，避免 move_to_location 未导出导致 NameError。
                move_result = execute_tool(
                    "move_to_location",
                    {"location_key": target, "auto_path": True},
                    self.game_state,
                    self.story,
                )

                if move_result.get("success"):
                    if self.adapter.verbose:
                        print(f"[INTENT] Implicit move succeeded: moved to {move_result.get('new_location')}")
                    # EN: Use returned new_location to avoid alias/name mapping issues.
                    # 中文：用返回的新地点名，避免别名/映射导致 focus 不一致。
                    self.current_focus = [move_result.get("new_location", target)]
                else:
                    if self.adapter.verbose:
                        print(f"[INTENT] Implicit move failed: {move_result.get('reason')}")
            else:
                if self.adapter.verbose:
                    if not target_node:
                        print(f"[INTENT] Implicit move skipped: target '{target}' not found in story graph.")
                    else:
                        print(f"[INTENT] Implicit move skipped: target '{target}' is not a location ({target_node.node_type}).")
        # -----------------------
        # PERSIST WORLD SNAPSHOT (world_state.json)
        # -----------------------
        try:
            # EN: Build a stable snapshot for reload/debug. Keep it deterministic.
            # 中文：构建稳定的快照用于重载/调试，尽量保持字段确定性。
            snapshot = {
                "turn": self.turn_index,
                "player": {
                    "location": self.game_state.player_location,
                    "inventory": list(getattr(self.game_state, "inventory", [])) if hasattr(self.game_state, "inventory") else [],
                },
                "focus": list(self.current_focus),
                "active_keys": sorted(self.active_keys),
                "discovered_keys": sorted(getattr(self.game_state, "discovered_keys", set())),
                "npc_locations": dict(getattr(self.game_state, "npc_locations", {})),
                "quest_flags": dict(getattr(self.game_state, "quest_flags", {})),
                # EN: Keep a short tail for context; do NOT store huge traces here.
                # 中文：保留少量对话尾巴；不要把 verbose trace 全塞进来。
                "history_tail": self.history.as_text(limit=12),
                "session_summary": self.summary.text(),
            }

            # EN: Overwrite save (atomic). Let StateStore handle .tmp + replace.
            # 中文：原子覆盖写。StateStore 内部会 .tmp + replace。
            self.state_store.apply_update(
                patch_fn=lambda _before: snapshot,
                event_id=str(self.turn_index),
                bump_version=True,
            )
        except Exception as e:
            if self.adapter.verbose:
                print(f"[STATE_STORE] Failed to write world_state.json: {e}")


        # -----------------------
        # REFRESH ACTIVE KEYS
        # -----------------------

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

        if trace is not None:
            trace["PLAN"] = plan_debug

        # -----------------------
        # VALIDATE (with read-only tools)
        # -----------------------

        validate_prompt = build_validate_prompt(state, plan)

        validate_tool_calls = []
        validate_messages = [{"role": "user", "content": validate_prompt}]

        max_validate_iterations = 3
        final_validate_content = ""

        for iteration in range(max_validate_iterations):
            if self.adapter.verbose:
                print(f"\n[TOOL] Validation iteration {iteration + 1}")
            
            response = self.adapter.request_with_tools(
                stage="validate",
                system_prompt=self.steps["validate"].system_prompt,
                messages=validate_messages,
                tools=VALIDATE_TOOLS  # Only read-only tools
            )
            
            message = response.get("message", {})
            tool_calls = message.get("tool_calls", [])
            
            if not tool_calls:
                final_validate_content = self.adapter._extract_content(response)
                if self.adapter.verbose:
                    print(f"[TOOL] No more tool calls, got validation result")
                break
            
            # Execute each tool call
            for tool_call in tool_calls:
                tool_name = tool_call["function"]["name"]
                arguments = tool_call["function"]["arguments"]
                if isinstance(arguments, str):
                    try:
                        arguments = json.loads(arguments)
                    except json.JSONDecodeError:
                        arguments = {}
                
                if self.adapter.verbose:
                    print(f"[TOOL] Calling {tool_name} with {arguments}")
                
                result = execute_tool(tool_name, arguments, self.game_state, self.story)
                validate_tool_calls.append({
                    "name": tool_name,
                    "arguments": arguments,
                    "result": result
                })
                
                if self.adapter.verbose:
                    print(f"[TOOL] Result: {result}")
            
            validate_messages.append({
                "role": "assistant",
                "content": message.get("content", ""),
                "tool_calls": tool_calls
            })
            
            for idx, tool_call in enumerate(tool_calls):
                validate_messages.append({
                    "role": "tool",
                    "content": json.dumps(validate_tool_calls[-(len(tool_calls) - idx)]["result"])
                })

        else:
            # Max iterations - force final response
            response = self.adapter.request_with_tools(
                stage="validate",
                system_prompt=self.steps["validate"].system_prompt + "\n\nProvide your validation verdict now.",
                messages=validate_messages,
                tools=[]
            )
            final_validate_content = self.adapter._extract_content(response)

        # Parse the validation result
        sections = parse_sections(final_validate_content, {"thoughts", "verdict", "notes", "advance"})
        parsed_result = self.steps["validate"].parser(sections)
        verdict, notes, advance = parsed_result
        
        # structure that matches the expected format with attempts array
        validate_debug = {
            "attempts": [{
                "attempt": 1,
                "prompt": validate_prompt,
                "raw": final_validate_content,
                "sections": sections,
                "parsed": parsed_result,
            }],
            "tool_calls": validate_tool_calls
        }

        if trace is not None:
            trace["VALIDATE"] = validate_debug

        # -----------------------
        # EXECUTE ACTIONS
        # -----------------------

        action_tool_calls = []
        
        if self.adapter.verbose:
            print(f"\n[ACTION] Executing actions based on intent and validation")
        
        # Only execute actions if validation approved
        if verdict.lower() == "approve":
            action = intent.get("action", "").lower()
            targets = intent.get("targets", [])
            
            # Handle movement actions
            if action == "move" and targets:
                target = targets[0]
                
                if self.adapter.verbose:
                    print(f"[ACTION] Attempting to move to {target}")
                
               # result = execute_tool("move_to_location", {"location_key": target}, 
               #                     self.game_state, self.story)
                qf = self.game_state.quest_flags if isinstance(self.game_state.quest_flags, dict) else {}
                auto_path = bool(qf.get("auto_path", True))

                result = execute_tool(
                    "move_to_location",
                    {"location_key": target, "auto_path": auto_path},
                    self.game_state,
                    self.story
                )
                
                action_tool_calls.append({
                    "name": "move_to_location",
                    "arguments": {"location_key": target, "auto_path": auto_path},
                    "result": result
                })
                
                if result.get("success"):
                    new_location = result["new_location"]
                    self.current_focus = [new_location]
                    
                    if self.adapter.verbose:
                        print(f"[ACTION] Movement succeeded, updated focus to {new_location}")
                    
                    # Refresh active keys with new focus
                    self.active_keys = self.active_manager.refresh(
                        self.story,
                        self.current_focus,
                        beat_text=self.beats.current(),
                    )
                else:
                    if self.adapter.verbose:
                        print(f"[ACTION] Movement failed: {result.get('reason')}")
            
                # Other action types can be handled here in the future
                # elif action == "take" and targets:
                #     ...
                # elif action == "use" and targets:
                #     ...
        
        else:
            if self.adapter.verbose:
                print(f"[ACTION] Validation verdict was '{verdict}', skipping action execution")

        # -----------------------
        # REBUILD STATE WITH UPDATED GAME STATE
        # -----------------------

        if self.adapter.verbose:
            print(f"\n[STATE] Rebuilding state with updated game state")
            print(f"[STATE] Player location: {self.game_state.player_location}")
            print(f"[STATE] Current focus: {self.current_focus}")
            print(f"[STATE] Active keys: {sorted(self.active_keys)}")

        state = self._make_state(player_input, intent)  # Fresh state with updated focus!

        if trace is not None:
            trace["STATE_AFTER_ACTION"] = build_state_snapshot()

        # -----------------------
        # NARRATE WITH UPDATED STATE
        # -----------------------

        narrate_prompt = build_narrate_prompt(state, plan, verdict, notes, action_tool_calls)

        if self.adapter.verbose:
            print(f"\n[NARRATE] Generating narrative with updated state")

        # Simple narration - no tool calls needed (actions already executed)
        narrative, narrate_debug = self.steps["narrate"].run(
            self.adapter,
            narrate_prompt,
        )

        if trace is not None:
            trace["ACTION_TOOLS"] = action_tool_calls
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
            "player_location": self.game_state.player_location,
            "tool_calls": action_tool_calls,
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
            intent={},
            player_input="",
            entity_info={},
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