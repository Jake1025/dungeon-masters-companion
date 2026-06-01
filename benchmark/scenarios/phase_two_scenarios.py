from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List

@dataclass
class PhaseTwoCase:
    id: str
    description: str
    player_input: str

    # Game state setup (initial state, before Phase 2 mutates anything)
    player_location: str
    npc_locations: Dict[str, str] = field(default_factory=dict)
    discovered_keys: List[str] = field(default_factory=list)
    visited_keys: List[str] = field(default_factory=list)
    conversation_history: List[str] = field(default_factory=list)
    story_status: str = ""

    # inputs from Phase 1 + Narration
    turn_summary: str = ""
    narration_focus: str = ""
    blocked_reason: str = ""
    narration: str = ""
    phase_one_tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    action_tool_calls: List[Dict[str, Any]] = field(default_factory=list)

    # Tool-call expectations (closed-world; finalize_writes is implicit)
    expect_finalize_writes: bool = True
    expected_tools_called: List[Any] = field(default_factory=list)
    expected_writes_summary_keywords: List[List[str]] = field(default_factory=list)
    max_iterations: int = 0

    # State-change expectations
    expected_location_after: str = ""
    expected_npc_locations_after: Dict[str, str] = field(default_factory=dict)
    expected_visited_added: List[str] = field(default_factory=list)
    expected_discovered_added: List[str] = field(default_factory=list)
    expected_memory_writes: List[str] = field(default_factory=list)
    
PHASE_TWO_CASES: List[PhaseTwoCase] = [

    # -------------------------------------------------------------------------
    # EASY (P2-01 through P2-10)
    # Single write action, small memory footprint, no judgment calls.
    # -------------------------------------------------------------------------

    PhaseTwoCase(
        id="P2-01",
        description="Standard movement: move player, write memories for player and location",
        player_input="I walk to the Copper Cup",
        player_location="Town Square",
        turn_summary="Player walked from Town Square to the Copper Cup.",
        narration_focus="Arrival at the Copper Cup.",
        blocked_reason="",
        narration=(
            "Thoughts: The player moves from the square into the warmth of the tavern.\n"
            "Narrative: You push through the Copper Cup's heavy door. Lamplight and the smell "
            "of malt close around you as the square disappears behind the wood."
        ),
        phase_one_tool_calls=[
            {"phase": "phase_one", "name": "check_can_interact",
             "arguments": {"entity_key": "Copper Cup"},
             "result": {"ok": True, "can_interact": True, "entity_type": "location"}},
        ],
        expect_finalize_writes=True,
        expected_tools_called=["move_to_location", "write_memory_tool"],
        expected_location_after="Copper Cup",
        expected_visited_added=["Copper Cup"],
        expected_discovered_added=["Back Door - Copper Cup", "Bar Counter", "Stair Landing"],
        expected_memory_writes=["Player", "Copper Cup"],
    ),
    PhaseTwoCase(
        id="P2-02",
        description="Conversation: write memories for both the player and the NPC",
        player_input="I ask Mara about the bloodstains on the floor",
        player_location="Copper Cup",
        npc_locations={"Mara": "Copper Cup"},
        turn_summary="Player asked Mara about the bloodstains. She gave a brief, reluctant answer.",
        narration_focus="Mara's terse response about a fight last night.",
        blocked_reason="",
        narration=(
            "Thoughts: Mara hesitates. She knows something but chooses her words carefully.\n"
            "Narrative: Mara stops polishing the cup. 'There was a fight last night,' she says, "
            "eyes moving briefly to the door. 'That is all I will say.'"
        ),
        phase_one_tool_calls=[
            {"phase": "phase_one", "name": "retrieve_memory_tool",
             "arguments": {"entity_name": "Mara"},
             "result": {"ok": True, "memories": ["Mara keeps the storeroom code private.", "She trusts the player more than most once they show respect."]}},
        ],
        expect_finalize_writes=True,
        expected_tools_called=["write_memory_tool"],
        expected_location_after="Copper Cup",
        expected_memory_writes=["Mara", "Player"],
    ),
    PhaseTwoCase(
        id="P2-03",
        description="Blocked movement: player stays put, a single player memory note is written",
        player_input="I head straight to the Fishermen's Shacks",
        player_location="Town Square",
        turn_summary="Player tried to move directly to the Fishermen's Shacks; that location is not reachable from Town Square in one step.",
        narration_focus="The path constraint conveyed without breaking immersion.",
        blocked_reason="Fishermen's Shacks is not directly reachable from Town Square.",
        narration=(
            "Thoughts: A direct path is not possible; the docks lie several streets away.\n"
            "Narrative: You start toward the harbor district but the route winds through streets "
            "you would need to take one at a time. The shacks are not reachable in one stride from here."
        ),
        expect_finalize_writes=True,
        expected_tools_called=["write_memory_tool"],
        expected_location_after="Town Square",
        expected_memory_writes=["Player"],
    ),
    PhaseTwoCase(
        id="P2-04",
        description="Pick up item: move the item to the player and write a player memory",
        player_input="I pick up the Bronze Fountain Coin from the fountain",
        player_location="Town Square",
        turn_summary="Player picked up the Bronze Fountain Coin from the central fountain.",
        narration_focus="The worn coin, the brief motion, the square continuing around the player.",
        blocked_reason="",
        narration=(
            "Thoughts: The coin is small and ordinary but the player chose to take it.\n"
            "Narrative: You work the coin free from the gap in the stone. It sits warm and battered "
            "in your palm. The fountain burbles on."
        ),
        phase_one_tool_calls=[
            {"phase": "phase_one", "name": "check_can_interact",
             "arguments": {"entity_key": "Bronze Fountain Coin"},
             "result": {"ok": True, "can_interact": True, "entity_type": "item"}},
        ],
        expect_finalize_writes=True,
        expected_tools_called=["move_world_item", "write_memory_tool"],
        expected_location_after="Town Square",
        expected_memory_writes=["Player"],
    ),
    PhaseTwoCase(
        id="P2-05",
        description="Trivial greeting: minimal or no writes required",
        player_input="hi",
        player_location="Town Square",
        turn_summary="Player offered a greeting. Nothing changed in the world.",
        narration_focus="Brief acknowledgement; scene preserved.",
        blocked_reason="",
        narration=(
            "Thoughts: A greeting in passing. Nothing requires action.\n"
            "Narrative: The square hums on around you, much as before."
        ),
        expect_finalize_writes=True,
        expected_location_after="Town Square",
        expected_tools_called=["write_memory_tool"],
        expected_memory_writes=["Player"],
        max_iterations=2,
    ),
    PhaseTwoCase(
        id="P2-06",
        description="Successful stealth past a guard: write a memory recording the outcome",
        player_input="I try to slip past Gate Guard Ren without him noticing",
        player_location="Harbor Gate",
        npc_locations={"Gate Guard Ren": "Harbor Gate"},
        turn_summary="Player slipped past Gate Guard Ren unseen. Stealth check succeeded with 15 vs DC 13.",
        narration_focus="Quiet success: each step placed with care, Ren's gaze missing the player.",
        blocked_reason="",
        narration=(
            "Thoughts: The check succeeded. The guard does not see the player pass.\n"
            "Narrative: You ease along the shadowed edge of the archway. Ren's eyes sweep the road "
            "and stop just short of you. You are through."
        ),
        action_tool_calls=[
            {"phase": "phase_one", "name": "skill_check",
             "arguments": {"entity_key": "Player", "skill": "stealth", "dc": 13},
             "result": {"ok": True, "success": True, "roll": 15, "total": 15, "dc": 13}},
        ],
        expect_finalize_writes=True,
        expected_tools_called=["write_memory_tool"],
        expected_location_after="Harbor Gate",
        expected_memory_writes=["Player", "Gate Guard Ren", "Harbor Gate"],
    ),
    PhaseTwoCase(
        id="P2-07",
        description="Failed persuasion attempt: write memories for both player and NPC reflecting the rebuff",
        player_input="I try to convince Mara to let me into the storeroom",
        player_location="Copper Cup",
        npc_locations={"Mara": "Copper Cup"},
        turn_summary="Player attempted to persuade Mara to open the storeroom. Persuasion failed with 6 vs DC 14. Mara gave a polite but firm refusal.",
        narration_focus="Mara closes the conversation without hostility; the refusal is final.",
        blocked_reason="",
        narration=(
            "Thoughts: The check failed. Mara is unmoved.\n"
            "Narrative: Mara's expression does not change. 'That room stays locked,' she says, "
            "and returns to the glasses on the shelf. The conversation is done."
        ),
        action_tool_calls=[
            {"phase": "phase_one", "name": "skill_check",
             "arguments": {"entity_key": "Player", "skill": "persuasion", "dc": 14},
             "result": {"ok": True, "success": False, "roll": 6, "total": 6, "dc": 14}},
        ],
        expect_finalize_writes=True,
        expected_tools_called=["write_memory_tool"],
        expected_location_after="Copper Cup",
        expected_memory_writes=["Player", "Mara", "Copper Cup"],
    ),
    PhaseTwoCase(
        id="P2-08",
        description="NPC moves location after agreeing to follow the player to the temple",
        player_input="I ask Novice Arel to come outside with me to the Old Shrine to talk privately",
        player_location="Temple of the Tide",
        npc_locations={"Novice Arel": "Temple of the Tide"},
        turn_summary="Player asked Novice Arel to follow them outside to the Old Shrine for a private talk. Arel agreed.",
        narration_focus="Arel agrees nervously, glancing at the altar as though asking permission.",
        blocked_reason="",
        narration=(
            "Thoughts: Both the player and Arel move to the Old Shrine.\n"
            "Narrative: Arel sets down the broom and follows with the kind of obedience that is "
            "really just a different sort of fear. The shrine is quieter, and closer."
        ),
        phase_one_tool_calls=[
            {"phase": "phase_one", "name": "check_can_interact",
             "arguments": {"entity_key": "Old Shrine"},
             "result": {"ok": True, "can_interact": True, "entity_type": "location"}},
        ],
        expect_finalize_writes=True,
        expected_tools_called=["move_to_location", "move_npc", "write_memory_tool"],
        expected_location_after="Old Shrine",
        expected_npc_locations_after={"Novice Arel": "Old Shrine"},
        expected_visited_added=["Old Shrine"],
        expected_memory_writes=["Player", "Novice Arel", "Old Shrine"],
    ),
    PhaseTwoCase(
        id="P2-09",
        description="NPC hands item to the player voluntarily: move item and write memories",
        player_input="I ask Cleric Serah if she will share the salt-stained prayer beads she found near the well",
        player_location="Temple of the Tide",
        npc_locations={"Cleric Serah": "Temple of the Tide"},
        turn_summary="Player asked Cleric Serah for the salt-stained prayer beads. She handed them over as a gesture of trust.",
        narration_focus="Serah passes the beads without ceremony, a small act of trust after careful thought.",
        blocked_reason="",
        narration=(
            "Thoughts: Serah has decided the player can be trusted with this.\n"
            "Narrative: Serah lifts the beads from her pocket and sets them in your hand. "
            "The salt on them is real. She says nothing, which is its own kind of statement."
        ),
        phase_one_tool_calls=[
            {"phase": "phase_one", "name": "retrieve_memory_tool",
             "arguments": {"entity_name": "Cleric Serah"},
             "result": {"ok": True, "memories": ["Serah keeps private notes on recurring symbols.", "She has treated people with unexplained wounds."]}},
        ],
        expect_finalize_writes=True,
        expected_tools_called=["move_world_item", "write_memory_tool"],
        expected_location_after="Temple of the Tide",
        expected_memory_writes=["Player", "Cleric Serah"],
    ),
    PhaseTwoCase(
        id="P2-10",
        description="Failed persuasion attempt with a civic official: write memories, no state changes",
        player_input="I ask Scribe Loth to show me the hidden duplicate ledger",
        player_location="Town Hall",
        npc_locations={"Scribe Loth": "Town Hall"},
        turn_summary="Player asked Scribe Loth about his hidden duplicate ledger. Persuasion failed DC 16, rolled 8. Loth denied everything.",
        narration_focus="Loth denies everything without looking up from his work.",
        blocked_reason="",
        narration=(
            "Thoughts: The check failed. Loth gives nothing away.\n"
            "Narrative: Loth keeps writing. 'I have no idea what you are referring to,' he says. "
            "The ink does not even pause."
        ),
        action_tool_calls=[
            {"phase": "phase_one", "name": "skill_check",
             "arguments": {"entity_key": "Player", "skill": "persuasion", "dc": 16},
             "result": {"ok": True, "success": False, "roll": 8, "total": 8, "dc": 16}},
        ],
        expect_finalize_writes=True,
        expected_tools_called=["write_memory_tool"],
        expected_location_after="Town Hall",
        expected_memory_writes=["Player", "Scribe Loth", "Town Hall"],
    ),

    # -------------------------------------------------------------------------
    # MEDIUM (P2-11 through P2-20)
    # Multiple tool calls per turn, quest flags, NPC movements, more entities
    # requiring memory writes.
    # -------------------------------------------------------------------------

    PhaseTwoCase(
        id="P2-11",
        description="Move to Docks and pick up the frayed mooring rope in the same turn",
        player_input="I go down to the Docks and pick up that frayed mooring rope near the pier",
        player_location="Harbor Gate",
        turn_summary="Player moved from Harbor Gate to the Docks and picked up the frayed mooring rope.",
        narration_focus="The pier, the smell of brine, the rope stiff and darker near one end.",
        blocked_reason="",
        narration=(
            "Thoughts: Player moves and collects a key piece of evidence.\n"
            "Narrative: The Docks smell of tar and cold salt. The frayed rope coils near a post, "
            "one end darker than sea-use alone could explain. You take it."
        ),
        phase_one_tool_calls=[
            {"phase": "phase_one", "name": "check_can_interact",
             "arguments": {"entity_key": "Docks"},
             "result": {"ok": True, "can_interact": True, "entity_type": "location"}},
            {"phase": "phase_one", "name": "check_can_interact",
             "arguments": {"entity_key": "Frayed Mooring Rope"},
             "result": {"ok": True, "can_interact": True, "entity_type": "item"}},
        ],
        expect_finalize_writes=True,
        expected_tools_called=["move_to_location", "move_world_item", "write_memory_tool"],
        expected_location_after="Docks",
        expected_visited_added=["Docks"],
        expected_discovered_added=["Fishermen's Shacks"],
        expected_memory_writes=["Player", "Docks"],
    ),
    PhaseTwoCase(
        id="P2-12",
        description="Successful persuasion of Jorin unlocks a quest flag and writes memories",
        player_input="I persuade Jorin to tell me exactly what he saw Mitch doing late at night",
        player_location="Town Square",
        npc_locations={"Street Performer Jorin": "Town Square"},
        turn_summary="Player persuaded Street Performer Jorin to share what he saw. Jorin confirmed he heard Mitch muttering about red hands that do not stay clean. Persuasion succeeded DC 12, rolled 15.",
        narration_focus="Jorin speaks with his eyes still on the crowd, voice low, like he is still performing but the act is something else now.",
        blocked_reason="",
        narration=(
            "Thoughts: The persuasion succeeded. Jorin gives up something real.\n"
            "Narrative: Jorin catches a stone before it lands and does not look at you. "
            "'Red hands that do not stay clean,' he says softly. 'That is what he kept saying. "
            "I thought it was the drink.'"
        ),
        action_tool_calls=[
            {"phase": "phase_one", "name": "skill_check",
             "arguments": {"entity_key": "Player", "skill": "persuasion", "dc": 12},
             "result": {"ok": True, "success": True, "roll": 15, "total": 15, "dc": 12}},
        ],
        expect_finalize_writes=True,
        expected_tools_called=["write_memory_tool"],
        expected_location_after="Town Square",
        expected_memory_writes=["Player", "Street Performer Jorin", "Town Square"],
    ),
    PhaseTwoCase(
        id="P2-13",
        description="Edda shares a legend that matches current events: quest flag set, three memory writes",
        player_input="I ask Edda about the old legend she keeps referencing that matches what is happening now",
        player_location="Copper Cup",
        npc_locations={"Edda": "Copper Cup"},
        turn_summary="Player asked Edda about the legend. She described an old blood-oath cycle tied to memory erasure for witnesses. The detail matches everything the player has found.",
        narration_focus="Edda speaks with the quiet energy of someone who has been waiting to be asked the right question.",
        blocked_reason="",
        narration=(
            "Thoughts: Edda has been holding this for someone who would listen.\n"
            "Narrative: Edda stops writing and turns her folio face-down. 'I was wondering when you "
            "would come to me,' she says. What follows takes a while and changes everything you thought "
            "you understood about what this town is remembering and what it is not."
        ),
        phase_one_tool_calls=[
            {"phase": "phase_one", "name": "retrieve_memory_tool",
             "arguments": {"entity_name": "Edda"},
             "result": {"ok": True, "memories": ["Edda noticed old legends describing memory theft tied to blood oaths.", "She thinks the present crisis mirrors an account from decades ago."]}},
        ],
        expect_finalize_writes=True,
        expected_tools_called=["write_memory_tool"],
        expected_location_after="Copper Cup",
        expected_memory_writes=["Player", "Edda", "Copper Cup"],
    ),
    PhaseTwoCase(
        id="P2-14",
        description="Intimidated NPC talks to player",
        player_input="I tell Fence Caris that either she talks to me or I walk her over to Captain Varr right now",
        player_location="East Alley",
        npc_locations={"Fence Caris": "East Alley"},
        turn_summary="Player threatened Fence Caris with the watch. Intimidation succeeded DC 12, rolled 16. Caris revealed she sold lock tools to someone matching Mitch's build, then moved away down the alley.",
        narration_focus="Caris talks fast and leaves faster.",
        blocked_reason="",
        narration=(
            "Thoughts: The check succeeded. Caris gives something up and gets out.\n"
            "Narrative: Caris looks at the alley entrance, then at you, and makes her calculation quickly. "
            "'Someone matching your man's description. Big. Smelled like sap.' She is through the back door "
            "before the sentence is finished."
        ),
        action_tool_calls=[
            {"phase": "phase_one", "name": "skill_check",
             "arguments": {"entity_key": "Player", "skill": "intimidation", "dc": 12},
             "result": {"ok": True, "success": True, "roll": 16, "total": 16, "dc": 12}},
        ],
        expect_finalize_writes=True,
        expected_tools_called=["write_memory_tool"],
        expected_location_after="East Alley",
        expected_memory_writes=["Player", "Fence Caris", "East Alley"],
    ),
    PhaseTwoCase(
        id="P2-15",
        description="Successful pickpocket: item moved from NPC to player, memory written",
        player_input="I lift the bent lockpick set from Pip's pocket while they are watching the street",
        player_location="East Alley",
        npc_locations={"Street Urchin Pip": "East Alley"},
        turn_summary="Player pickpocketed the Bent Lockpick Set from Street Urchin Pip. Sleight of hand succeeded DC 12, rolled 14.",
        narration_focus="The lift completes without incident; Pip keeps watching the street.",
        blocked_reason="",
        narration=(
            "Thoughts: The check succeeded. The item moves without detection.\n"
            "Narrative: Your fingers find the wrapped bundle in Pip's jacket. It comes free cleanly. "
            "Pip does not look around."
        ),
        action_tool_calls=[
            {"phase": "phase_one", "name": "skill_check",
             "arguments": {"entity_key": "Player", "skill": "sleight_of_hand", "dc": 12},
             "result": {"ok": True, "success": True, "roll": 14, "total": 14, "dc": 12}},
        ],
        expect_finalize_writes=True,
        expected_tools_called=["move_world_item", "write_memory_tool"],
        expected_location_after="East Alley",
        expected_memory_writes=["Player", "Street Urchin Pip"],
    ),
    PhaseTwoCase(
        id="P2-16",
        description="Player and NPC both move location together: move_to_location, move_npc, and memories",
        player_input="I motion for Boatman Jaro to follow me to South Bridge to meet Bridge Watcher Sol",
        player_location="Riverside Path",
        npc_locations={"Boatman Jaro": "Riverside Path"},
        turn_summary="Player led Boatman Jaro from the Riverside Path to South Bridge to introduce him to Bridge Watcher Sol.",
        narration_focus="The two move together; the bridge is closer than it seemed.",
        blocked_reason="",
        narration=(
            "Thoughts: Both move. The bridge is directly reachable from here.\n"
            "Narrative: Jaro ties off his skiff without a word and follows. The path to the bridge "
            "is muddy and short. Sol sees you coming before you see him."
        ),
        phase_one_tool_calls=[
            {"phase": "phase_one", "name": "check_can_interact",
             "arguments": {"entity_key": "South Bridge"},
             "result": {"ok": True, "can_interact": True, "entity_type": "location"}},
        ],
        expect_finalize_writes=True,
        expected_tools_called=["move_to_location", "move_npc", "write_memory_tool"],
        expected_location_after="South Bridge",
        expected_npc_locations_after={"Boatman Jaro": "South Bridge"},
        expected_visited_added=["South Bridge"],
        expected_memory_writes=["Player", "Boatman Jaro", "South Bridge"],
    ),
    PhaseTwoCase(
        id="P2-17",
        description="Player searches for and finds the hidden alley knife: create item, item moved, quest flag set",
        player_input="I search along the base of the wall in East Alley for the loose brick and the knife behind it",
        player_location="East Alley",
        turn_summary="Player searched the loose brick in East Alley and found the Hidden Alley Knife. Investigation succeeded.",
        narration_focus="The cold knife in the hand, the rust on the blade, the feeling of having found something no one was supposed to find.",
        blocked_reason="",
        narration=(
            "Thoughts: The check succeeded. The knife is recovered.\n"
            "Narrative: The brick shifts at finger pressure. Behind it, wrapped in cloth that has "
            "seen better weeks, is a narrow knife. The edge is rust-colored in a way that is not rust."
        ),
        action_tool_calls=[
            {"phase": "phase_one", "name": "skill_check",
             "arguments": {"entity_key": "Player", "skill": "investigation", "dc": 10},
             "result": {"ok": True, "success": True, "roll": 13, "total": 13, "dc": 10}},
        ],
        expect_finalize_writes=True,
        expected_tools_called=["create_item", "move_world_item", "write_memory_tool"],
        expected_location_after="East Alley",
        expected_memory_writes=["Player", "East Alley"],
    ),
    PhaseTwoCase(
        id="P2-18",
        description="Player gives the carved driftwood charm to Cleric Serah as an offering: item moves and memories written",
        player_input="I place the carved driftwood charm in Cleric Serah's hands as an offering and ask for her trust",
        player_location="Temple of the Tide",
        npc_locations={"Cleric Serah": "Temple of the Tide"},
        turn_summary="Player offered the Carved Driftwood Charm to Cleric Serah. She accepted it and shared more detail about the recurring symbols in her private notes.",
        narration_focus="The offering shifts something between them; Serah speaks more openly after.",
        blocked_reason="",
        narration=(
            "Thoughts: An item moves from player to NPC as a social gesture that pays off.\n"
            "Narrative: Serah closes both hands around the charm and is quiet for a moment. "
            "Then she takes you to a corner of the temple and opens her private folio."
        ),
        expect_finalize_writes=True,
        expected_tools_called=["move_world_item", "write_memory_tool"],
        expected_location_after="Temple of the Tide",
        expected_memory_writes=["Player", "Cleric Serah", "Temple of the Tide"],
    ),
    PhaseTwoCase(
        id="P2-19",
        description="Player reaches the Smuggler's Entrance and finds Lia there: move player, write memories",
        player_input="I slip down through the grate into the Smuggler's Entrance to look around",
        player_location="Old Well",
        npc_locations={"Smuggler Lia": "Smuggler's Entrance"},
        turn_summary="Player descended through the grate into the Smuggler's Entrance. Smuggler Lia was present.",
        narration_focus="The damp air, the river mud smell, Lia already watching from the dark.",
        blocked_reason="",
        narration=(
            "Thoughts: Player moves to a new location and encounters Lia.\n"
            "Narrative: The stone steps are slick. Below, it smells of mud and old water. "
            "Lia is leaning against the wall and does not look surprised to see you."
        ),
        phase_one_tool_calls=[
            {"phase": "phase_one", "name": "check_can_interact",
             "arguments": {"entity_key": "Smuggler's Entrance"},
             "result": {"ok": True, "can_interact": True, "entity_type": "location"}},
        ],
        expect_finalize_writes=True,
        expected_tools_called=["move_to_location", "write_memory_tool"],
        expected_location_after="Smuggler's Entrance",
        expected_visited_added=["Smuggler's Entrance", "Warehouse Row"],
        expected_memory_writes=["Player", "Smuggler Lia", "Smuggler's Entrance"],
    ),
    PhaseTwoCase(
        id="P2-20",
        description="Presenting two pieces of evidence to Serah causes her to share a major revelation: multiple flags and memories",
        player_input="I show Cleric Serah the hidden alley knife and the frayed mooring rope side by side and ask what she makes of them",
        player_location="Temple of the Tide",
        npc_locations={"Cleric Serah": "Temple of the Tide"},
        turn_summary="Player showed Cleric Serah both the Hidden Alley Knife and the Frayed Mooring Rope. She confirmed both match her private pattern notes and named a single perpetrator as the most likely source. This is the clearest confirmation yet.",
        narration_focus="Serah's recognition of the pattern is quiet and certain, like a diagnosis.",
        blocked_reason="",
        narration=(
            "Thoughts: Two items together unlock a significant revelation from Serah.\n"
            "Narrative: Serah sets both objects on the prayer ledge and does not touch them. "
            "She looks at them for a long time. 'I had hoped I was wrong,' she says finally."
        ),
        expect_finalize_writes=True,
        expected_tools_called=["write_memory_tool"],
        expected_location_after="Temple of the Tide",
        expected_memory_writes=["Player", "Cleric Serah", "Temple of the Tide"],
    ),

    # -------------------------------------------------------------------------
    # HARD (P2-21 through P2-30)
    # Four or more distinct write operations, cascading state changes, multiple
    # NPC memories, several quest flags, and situations that require careful
    # judgment about what to write and what not to write. Designed to be
    # very difficult to execute completely correctly.
    # -------------------------------------------------------------------------

    PhaseTwoCase(
        id="P2-21",
        description="Move to Watch Barracks, take logbook, persuade Varr: movement plus item plus flag plus four memory writes",
        player_input="I walk to the Watch Barracks, take the Night Patrol Logbook from the shelf, and tell Captain Varr I am conducting an authorized investigation",
        player_location="Town Square",
        npc_locations={"Captain Varr": "Watch Barracks"},
        turn_summary="Player moved to Watch Barracks, claimed investigative authority, and took the Night Patrol Logbook. Persuasion succeeded DC 14, rolled 16. Varr was skeptical but stood aside.",
        narration_focus="The ledger is in hand. Varr watches with the expression of a man making a note.",
        blocked_reason="",
        narration=(
            "Thoughts: Player moves, acquires a key item, and alters the NPC relationship.\n"
            "Narrative: The Barracks smell of oiled leather and old paper. The logbook is on the shelf "
            "right where you expected it. Varr watches you take it without speaking. His silence costs him something."
        ),
        action_tool_calls=[
            {"phase": "phase_one", "name": "skill_check",
             "arguments": {"entity_key": "Player", "skill": "persuasion", "dc": 14},
             "result": {"ok": True, "success": True, "roll": 16, "total": 16, "dc": 14}},
        ],
        phase_one_tool_calls=[
            {"phase": "phase_one", "name": "check_can_interact",
             "arguments": {"entity_key": "Watch Barracks"},
             "result": {"ok": True, "can_interact": True, "entity_type": "location"}},
        ],
        expect_finalize_writes=True,
        expected_tools_called=["create_item", "move_to_location", "move_world_item", "write_memory_tool"],
        expected_location_after="Watch Barracks",
        expected_visited_added=["Watch Barracks"],
        expected_memory_writes=["Player", "Captain Varr", "Watch Barracks"],
    ),
    PhaseTwoCase(
        id="P2-22",
        description="Persuade Dockmaster Hara and have her walk to Harbor Gate to report: NPC moves, memories for four entities",
        player_input="I convince Dockmaster Hara to take her ledger discrepancy notes to the Harbor Gate and file a formal complaint with Ren",
        player_location="Docks",
        npc_locations={"Dockmaster Hara": "Docks", "Gate Guard Ren": "Harbor Gate"},
        turn_summary="Player persuaded Dockmaster Hara to formally report her ledger discrepancies to the Harbor Gate watch post. Persuasion succeeded DC 13, rolled 17. Hara agreed and moved toward the gate.",
        narration_focus="Hara moving with purpose for the first time in weeks; the relief of having a formal next step.",
        blocked_reason="",
        narration=(
            "Thoughts: Hara is persuaded and takes action. She moves; the situation shifts.\n"
            "Narrative: Hara closes her ledger and tucks it under her arm. 'All right,' she says. "
            "'I should have done this three days ago.' She is already walking."
        ),
        action_tool_calls=[
            {"phase": "phase_one", "name": "skill_check",
             "arguments": {"entity_key": "Player", "skill": "persuasion", "dc": 13},
             "result": {"ok": True, "success": True, "roll": 17, "total": 17, "dc": 13}},
        ],
        expect_finalize_writes=True,
        expected_tools_called=["move_npc", "write_memory_tool"],
        expected_location_after="Docks",
        expected_npc_locations_after={"Dockmaster Hara": "Harbor Gate"},
        expected_memory_writes=["Player", "Dockmaster Hara", "Docks", "Gate Guard Ren"],
    ),
    PhaseTwoCase(
        id="P2-23",
        description="Confront Foreman Kesh at Warehouse Row, seize the smugglers' ledger, and send Kesh fleeing: item plus NPC move plus flag plus memories",
        player_input="I take the smugglers' ledger from Warehouse Row and tell Foreman Kesh to back off or I will go straight to the watch",
        player_location="Warehouse Row",
        npc_locations={"Foreman Kesh": "Warehouse Row"},
        turn_summary="Player seized the smugglers' ledger at Warehouse Row. Intimidation succeeded DC 13, rolled 15. Foreman Kesh backed down and retreated toward the Smuggler's Entrance.",
        narration_focus="The ledger is heavy and smells of river mud. Kesh watches the player from a distance now.",
        blocked_reason="",
        narration=(
            "Thoughts: Item acquired through intimidation; NPC retreats as a consequence.\n"
            "Narrative: Kesh folds first. He takes a step back, then another, until the warehouse wall "
            "is at his back and the entrance to the tunnels is close enough to use. The ledger is yours."
        ),
        action_tool_calls=[
            {"phase": "phase_one", "name": "skill_check",
             "arguments": {"entity_key": "Player", "skill": "intimidation", "dc": 13},
             "result": {"ok": True, "success": True, "roll": 15, "total": 15, "dc": 13}},
        ],
        expect_finalize_writes=True,
        expected_tools_called=["move_world_item", "move_npc", "write_memory_tool"],
        expected_location_after="Warehouse Row",
        expected_npc_locations_after={"Foreman Kesh": "Smuggler's Entrance"},
        expected_memory_writes=["Player", "Foreman Kesh", "Warehouse Row"],
    ),
    PhaseTwoCase(
        id="P2-24",
        description="Collect shattered lantern glass at South Bridge and debrief Bridge Watcher Sol: two items considered, three memory writes",
        player_input="I pick up the shattered lantern glass at South Bridge and ask Sol to walk me through the storm night in detail",
        player_location="South Bridge",
        npc_locations={"Bridge Watcher Sol": "South Bridge"},
        turn_summary="Player collected the Shattered Lantern Glass at South Bridge and debriefed Bridge Watcher Sol on the storm night incident. Sol provided significant new detail under questioning before going silent.",
        narration_focus="The glass shards, the smell of old smoke, Sol speaking in short sentences about the night he cannot fully remember.",
        blocked_reason="",
        narration=(
            "Thoughts: Item acquired and NPC debriefed in the same scene.\n"
            "Narrative: The glass is in a small cloth pouch, left exactly where someone thought no one "
            "would look twice. Sol talks for a while and then, at the part that matters most, stops."
        ),
        phase_one_tool_calls=[
            {"phase": "phase_one", "name": "check_can_interact",
             "arguments": {"entity_key": "Shattered Lantern Glass"},
             "result": {"ok": True, "can_interact": True, "entity_type": "item"}},
            {"phase": "phase_one", "name": "retrieve_memory_tool",
             "arguments": {"entity_name": "Bridge Watcher Sol"},
             "result": {"ok": True, "memories": ["Sol heard shouting near the bridge on a storm night.", "He logs late-night crossings no one later remembers."]}},
        ],
        expect_finalize_writes=True,
        expected_tools_called=["create_item", "move_world_item", "write_memory_tool"],
        expected_location_after="South Bridge",
        expected_memory_writes=["Player", "Bridge Watcher Sol", "South Bridge"],
    ),
    PhaseTwoCase(
        id="P2-25",
        description="Leave the driftwood charm at the shrine and send Ilya to deliver a message to Serah: NPC moves, item moves, quest flag, four memories",
        player_input="I leave the carved driftwood charm on the shrine as an offering, tell Caretaker Ilya everything I know, and ask her to carry the message to Cleric Serah at the temple",
        player_location="Old Shrine",
        npc_locations={"Caretaker Ilya": "Old Shrine"},
        turn_summary="Player placed the Carved Driftwood Charm as an offering at the Old Shrine and fully briefed Caretaker Ilya. Ilya agreed to carry the full account to Cleric Serah and left for the temple.",
        narration_focus="The charm on the stone, Ilya listening with her whole body, then leaving without delay.",
        blocked_reason="",
        narration=(
            "Thoughts: Item placed, NPC informed and dispatched, two flags triggered.\n"
            "Narrative: Ilya does not ask questions while you speak. When you finish she sets the charm "
            "carefully in the bowl and stands. 'I know the way,' she says, and goes."
        ),
        expect_finalize_writes=True,
        expected_tools_called=["move_world_item", "move_npc", "write_memory_tool"],
        expected_location_after="Old Shrine",
        expected_npc_locations_after={"Caretaker Ilya": "Temple of the Tide"},
        expected_memory_writes=["Player", "Caretaker Ilya", "Old Shrine", "Cleric Serah"],
    ),
    PhaseTwoCase(
        id="P2-26",
        description="Seize two items at the Watch Barracks after successful bluff: two item moves, two flags, three memories",
        player_input="I tell Captain Varr the mayor sent me, take the Night Patrol Logbook and the Guard's Lost Signet from the barracks, and walk out before he can check the story",
        player_location="Watch Barracks",
        npc_locations={"Captain Varr": "Watch Barracks"},
        turn_summary="Player bluffed Captain Varr with claimed mayoral authority and took both the Night Patrol Logbook and the Guard's Lost Signet. Deception succeeded DC 15, rolled 18. Varr allowed it but was visibly skeptical.",
        narration_focus="Two items in hand, Varr watching from the door, the bluff holding by a thread.",
        blocked_reason="",
        narration=(
            "Thoughts: A successful deception yields two items and leaves an NPC with doubts.\n"
            "Narrative: Varr's jaw tightens but he nods. The logbook is where you expected. "
            "The signet is in the tray beside it. You take both and do not look back."
        ),
        action_tool_calls=[
            {"phase": "phase_one", "name": "skill_check",
             "arguments": {"entity_key": "Player", "skill": "deception", "dc": 15},
             "result": {"ok": True, "success": True, "roll": 18, "total": 18, "dc": 15}},
        ],
        expect_finalize_writes=True,
        expected_tools_called=["move_world_item", "write_memory_tool"],
        expected_location_after="Watch Barracks",
        expected_memory_writes=["Player", "Captain Varr", "Watch Barracks"],
    ),
    PhaseTwoCase(
        id="P2-27",
        description="Seize barracks keyring from Varr under threat, Varr leaves for Town Hall: item from NPC, NPC moves, flag, four memories",
        player_input="I grab the Barracks Keyring from Varr's belt, show him the edited patrol logs as leverage, and tell him to step back or face a public inquiry",
        player_location="Watch Barracks",
        npc_locations={"Captain Varr": "Watch Barracks"},
        turn_summary="Player seized the Barracks Keyring directly from Captain Varr using evidence of edited reports as leverage. Intimidation succeeded DC 16, rolled 19. Varr backed down but left immediately toward Town Hall to report to the mayor.",
        narration_focus="The keyring in hand; Varr walking away with the expression of a man who has just decided something.",
        blocked_reason="",
        narration=(
            "Thoughts: An aggressive action succeeds but Varr goes to escalate through official channels.\n"
            "Narrative: Varr looks at the edited log entry for a long moment. Then he looks at you. "
            "He steps back. The keys are yours. He is out the door before you can speak again, "
            "and his boots on the stone are heading toward Town Hall."
        ),
        action_tool_calls=[
            {"phase": "phase_one", "name": "skill_check",
             "arguments": {"entity_key": "Player", "skill": "intimidation", "dc": 16},
             "result": {"ok": True, "success": True, "roll": 19, "total": 19, "dc": 16}},
        ],
        expect_finalize_writes=True,
        expected_tools_called=["create_item", "move_world_item", "move_npc", "write_memory_tool"],
        expected_location_after="Watch Barracks",
        expected_npc_locations_after={"Captain Varr": "Town Hall"},
        expected_memory_writes=["Player", "Captain Varr", "Watch Barracks", "Mayor Elric"],
    ),
    PhaseTwoCase(
        id="P2-28",
        description="Deal with Smuggler Lia to get the ledger and her testimony: item plus two flags plus four memories",
        player_input="I offer Lia a deal in the tunnel: she hands over the smugglers' ledger and tells me everything she saw before dawn, and I keep her name out of my report to the watch",
        player_location="Smuggler's Entrance",
        npc_locations={"Smuggler Lia": "Smuggler's Entrance"},
        turn_summary="Player offered Smuggler Lia immunity from the watch in exchange for the ledger and her testimony. Persuasion succeeded DC 15, rolled 16. Lia agreed, handed over the ledger, and described hurried pre-dawn cleanup operations near Warehouse Row.",
        narration_focus="The deal made in the dark, the ledger changing hands, Lia describing what she saw with the flat calm of someone who has decided to stop keeping a secret.",
        blocked_reason="",
        narration=(
            "Thoughts: Two flags triggered, item secured, and a detailed testimony received.\n"
            "Narrative: Lia is quiet for long enough that you think she will refuse. Then she holds out "
            "the ledger. 'Before the third bell,' she says. 'Every time. Someone cleaning up before "
            "anyone was supposed to be awake.' She watches you take the ledger. The deal is done."
        ),
        action_tool_calls=[
            {"phase": "phase_one", "name": "skill_check",
             "arguments": {"entity_key": "Player", "skill": "persuasion", "dc": 15},
             "result": {"ok": True, "success": True, "roll": 16, "total": 16, "dc": 15}},
        ],
        expect_finalize_writes=True,
        expected_tools_called=["create_item", "move_world_item", "write_memory_tool"],
        expected_location_after="Smuggler's Entrance",
        expected_memory_writes=["Player", "Smuggler Lia", "Smuggler's Entrance"],
    ),
    PhaseTwoCase(
        id="P2-29",
        description="Confront Arlen with all evidence and force a full admission: three flags and five memory writes, no movement",
        player_input="I lay the knife, the logbook, and the ledger in front of Arlen and tell him I know about the memory smoothing and I know about Mitch, and I want the full truth from him right now",
        player_location="Wizard's House",
        npc_locations={"Town Wizard Arlen": "Wizard's House"},
        turn_summary="Player confronted Wizard Arlen with three pieces of evidence. Under sustained pressure and a successful insight check DC 14, rolled 18, Arlen confirmed he has been smoothing memories after each violent episode. He named Mitch as the source but defended his own actions as damage control.",
        narration_focus="Arlen under the full weight of the evidence, no longer able to manage how much the player knows.",
        blocked_reason="",
        narration=(
            "Thoughts: Three flags triggered at once. Five entities have their understanding of events updated.\n"
            "Narrative: Arlen looks at the three items for a long time. When he finally speaks, "
            "his voice has none of the careful precision you have been listening to. "
            "'I did what I did to stop the panic,' he says. 'And yes. It is Mitch.' "
            "He does not look like a man confessing. He looks like a man who has been carrying something "
            "very heavy for a very long time and has just been told he can set it down."
        ),
        action_tool_calls=[
            {"phase": "phase_one", "name": "skill_check",
             "arguments": {"entity_key": "Player", "skill": "insight", "dc": 14},
             "result": {"ok": True, "success": True, "roll": 18, "total": 18, "dc": 14}},
        ],
        expect_finalize_writes=True,
        expected_tools_called=["write_memory_tool"],
        expected_location_after="Wizard's House",
        expected_memory_writes=["Player", "Town Wizard Arlen", "Wizard's House"],
    ),
    PhaseTwoCase(
        id="P2-30",
        description="Final resolution: distribute two items to two NPCs, set four flags, and write six memory entries across all present parties",
        player_input="With the mayor, Varr, Mitch, and Arlen all gathered in the square, I hand the Wax-Sealed Incident Packet to Mayor Elric, give the Night Patrol Logbook to Captain Varr, formally offer Mitch a path to treatment with Serah's help, and argue that Arlen must stop the memory manipulation in exchange for no public accusation",
        player_location="Town Square",
        npc_locations={
            "Mayor Elric": "Town Square",
            "Captain Varr": "Town Square",
            "Mitch": "Town Square",
            "Town Wizard Arlen": "Town Square",
        },
        turn_summary="Player distributed the Wax-Sealed Incident Packet to Mayor Elric and the Night Patrol Logbook to Captain Varr in Town Square, offered Mitch a path to treatment, and negotiated with Arlen for a cessation of memory manipulation. All parties accepted the compromise in principle after significant hesitation.",
        narration_focus="Four people in a square, each carrying a different version of events, all agreeing on a fragile next step.",
        blocked_reason="",
        narration=(
            "Thoughts: Six entity memories require updating. Four flags set. Two items change hands. "
            "The scene is the hardest to write because nothing is fully resolved.\n"
            "Narrative: The square is quiet in the way it gets when too many people are holding their breath. "
            "Elric takes the packet. Varr takes the logbook. Mitch is looking at his hands. "
            "Arlen is looking at Mitch. Nobody cheers. The agreement holds because everyone is too tired "
            "to fight it, and that is the best thing it can be right now."
        ),
        expect_finalize_writes=True,
        expected_tools_called=["move_world_item", "write_memory_tool"],
        expected_location_after="Town Square",
        expected_memory_writes=[
            "Player",
            "Mayor Elric",
            "Captain Varr",
            "Mitch",
            "Town Wizard Arlen",
            "Town Square",
        ],
    ),
]


__all__ = ["PhaseTwoCase", "PHASE_TWO_CASES"]