from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class PhaseOneCase:
    id: str
    description: str
    player_input: str

    # Game state setup
    player_location: str
    npc_locations: Dict[str, str] = field(default_factory=dict)
    quest_flags: Dict[str, bool] = field(default_factory=dict)
    discovered_keys: List[str] = field(default_factory=list)
    visited_keys: List[str] = field(default_factory=list)
    conversation_history: List[str] = field(default_factory=list)
    story_status: str = ""

    # Expectations
    expect_finalize: bool = True
    expect_blocked: bool = False
    # Each entry: a tool name (str) or a dict with name + args, or a list (OR group).
    # Closed-world: only these names (plus finalize_turn) may be called; anything
    # else counts as an unexpected (false-positive) call.
    expected_tools_called: List[Any] = field(default_factory=list)
    # Keyword groups: each inner list is an OR group; all groups must match (AND).
    expected_turn_summary_keywords: List[List[str]] = field(default_factory=list)
    expected_narration_focus_keywords: List[List[str]] = field(default_factory=list)
    max_iterations: int = 0   # 0 means no constraint

    # Force the outcome of any skill_check (and the History roll inside
    # check_can_interact) that the model triggers during this case.
    skill_check_outcome: Optional[str] = None

PHASE_ONE_CASES: List[PhaseOneCase] = [

    # -------------------------------------------------------------------------
    # EASY (P1-01 through P1-10)
    # Single clear intent, zero or one tool, no judgment calls required.
    # -------------------------------------------------------------------------

    PhaseOneCase(
        id="P1-01",
        description="Trivial greeting with no action",
        player_input="hi",
        player_location="Town Square",
        expect_finalize=True,
        expect_blocked=False,
        expected_tools_called=[],
        max_iterations=1,
    ),
    PhaseOneCase(
        id="P1-02",
        description="Simple movement to an adjacent location",
        player_input="I walk over to the Copper Cup",
        player_location="Town Square",
        expect_finalize=True,
        expect_blocked=False,
        expected_tools_called=["check_can_interact"],
        expected_narration_focus_keywords=[["copper", "cup", "tavern"]],
    ),
    PhaseOneCase(
        id="P1-03",
        description="Look around the current location",
        player_input="I take stock of my surroundings and see what is in the square",
        player_location="Town Square",
        expect_finalize=True,
        expect_blocked=False,
        expected_tools_called=[["list_scene_entities", "get_current_context"]],
        expected_turn_summary_keywords=[["square"], ["Mitch", "Jorin", "Jessa"]],
    ),
    PhaseOneCase(
        id="P1-04",
        description="Pick up a visible item at the current location",
        player_input="I pick up the coin wedged between the fountain stones",
        player_location="Town Square",
        discovered_keys=["Bronze Fountain Coin"],
        conversation_history=[
            "I look around the square.",
            "A bronze coin catches your eye, wedged between the stones of the central fountain.",
        ],
        expect_finalize=True,
        expect_blocked=False,
        expected_tools_called=["check_can_interact"],
        expected_narration_focus_keywords=[["coin", "fountain", "pick"]],
    ),
    PhaseOneCase(
        id="P1-05",
        description="Ask a present NPC a simple question",
        player_input="I ask Jorin what he's been seeing at night around the square",
        player_location="Town Square",
        npc_locations={"Street Performer Jorin": "Town Square"},
        expect_finalize=True,
        expect_blocked=False,
        expected_tools_called=["check_can_interact"],
        expected_turn_summary_keywords=[["jorin"], ["ask", "question", "speak", "talk"]],
    ),
    PhaseOneCase(
        id="P1-06",
        description="Meta question about game rules",
        player_input="Can I actually read documents I find, or just pick them up?",
        player_location="Town Square",
        expect_finalize=True,
        expect_blocked=False,
        expected_tools_called=[],
        expected_turn_summary_keywords=[["allow", "allowed", "okay", "yes", "confirm", "confirmed"]],
    ),
    PhaseOneCase(
        id="P1-07",
        description="Movement to a location that is not directly reachable",
        player_input="I want to go straight to the Fishermen's Shacks",
        player_location="Town Square",
        expect_finalize=True,
        expect_blocked=True,
        expected_tools_called=["check_can_interact"],
        expected_turn_summary_keywords=[["can't", "not", "no", "blocked", "alternate"]],
    ),
    PhaseOneCase(
        id="P1-08",
        description="Examine a specific item mentioned in a recent conversation",
        player_input="I lean in and take a closer look at the cracked spyglass",
        player_location="Harbor Gate",
        conversation_history=[
            "I look around the gate.",
            "The archway is guarded. A cracked spyglass rests on a shelf in the guard post.",
        ],
        expect_finalize=True,
        expect_blocked=False,
        expected_tools_called=["check_can_interact"],
        expected_narration_focus_keywords=[["spyglass", "crack", "look", "inspect"]],
    ),
    PhaseOneCase(
        id="P1-09",
        description="Request current scene context and orientation",
        player_input="What exactly is going on here and where am I?",
        player_location="Copper Cup",
        npc_locations={"Mara": "Copper Cup"},
        expect_finalize=True,
        expect_blocked=False,
        expected_tools_called=["get_current_context"],
        expected_turn_summary_keywords=[["context", "situation", "orient", "explain", "state"]],
    ),
    PhaseOneCase(
        id="P1-10",
        description="Player checks their own inventory or state",
        player_input="What do I have on me right now?",
        player_location="Town Square",
        expect_finalize=True,
        expect_blocked=False,
        expected_tools_called=["get_entity_state"],
        expected_turn_summary_keywords=[["inventory", "carry", "item", "possess", "check", "have"]],
    ),

    # -------------------------------------------------------------------------
    # MEDIUM (P1-11 through P1-20)
    # Multi-step reasoning, skill checks, or blocked/conditional outcomes.
    # -------------------------------------------------------------------------

    PhaseOneCase(
        id="P1-11",
        description="Attempt to sneak past a guard at a checkpoint",
        player_input="I try to slip past Gate Guard Ren without him noticing me",
        player_location="Harbor Gate",
        npc_locations={"Gate Guard Ren": "Harbor Gate"},
        expect_finalize=True,
        expect_blocked=False,
        expected_tools_called=["check_can_interact", "skill_check"],
        expected_narration_focus_keywords=[["careful", "successful", "sneak", "stealth", "slip", "past"]],
    ),
    PhaseOneCase(
        id="P1-12",
        description="Attempt to persuade an NPC to share sensitive information",
        player_input="I try to convince Spice Seller Nima to tell me what she heard near the Old Well that night",
        player_location="Market Stalls",
        npc_locations={"Spice Seller Nima": "Market Stalls"},
        expect_finalize=True,
        expect_blocked=False,
        expected_tools_called=["check_can_interact", "skill_check"],
        expected_turn_summary_keywords=[["nima"], ["persuade", "convince", "charm", "ask"]],
    ),
    PhaseOneCase(
        id="P1-13",
        description="Investigate a crime scene for physical evidence",
        player_input="I search East Alley carefully for any clues about what happened here",
        player_location="East Alley",
        expect_finalize=True,
        expect_blocked=False,
        expected_tools_called=["get_current_context", "skill_check"],
        expected_turn_summary_keywords=[["search", "investigate", "examine", "look"], ["alley", "clue", "evidence"]],
    ),
    PhaseOneCase(
        id="P1-14",
        description="Attempt to pick pocket an item from an NPC",
        player_input="While Pip is distracted watching a cart go by, I try to lift the lockpick set from their pocket",
        player_location="East Alley",
        npc_locations={"Street Urchin Pip": "East Alley"},
        expect_finalize=True,
        expect_blocked=False,
        expected_tools_called=["check_can_interact", "skill_check"],
        expected_narration_focus_keywords=[["pick", "pocket", "steal", "lift", "lockpick", "pip"]],
    ),
    PhaseOneCase(
        id="P1-15",
        description="Try a locked door without the key or combination",
        player_input="I try the handle of the storeroom door to see if it will open",
        player_location="Storeroom Door",
        expect_finalize=True,
        expect_blocked=True,
        expected_tools_called=["check_can_interact"],
        expected_narration_focus_keywords=[["door", "lock", "storeroom", "handle"]],
    ),
    PhaseOneCase(
        id="P1-16",
        description="Ask a present NPC about an absent third party",
        player_input="I ask Jorin quietly whether he knows anything about Mitch",
        player_location="Town Square",
        npc_locations={"Street Performer Jorin": "Town Square"},
        expect_finalize=True,
        expect_blocked=False,
        expected_tools_called=["check_can_interact"],
        expected_turn_summary_keywords=[["jorin"], ["mitch"], ["ask", "question", "tell"]],
    ),
    PhaseOneCase(
        id="P1-17",
        description="Attempt to bluff an authority figure with a false claim",
        player_input="I tell Captain Varr that the mayor personally sent me to review the Night Patrol Logbook",
        player_location="Watch Barracks",
        npc_locations={"Captain Varr": "Watch Barracks"},
        expect_finalize=True,
        expect_blocked=False,
        expected_tools_called=["check_can_interact"],
        expected_narration_focus_keywords=[["bluff", "deceive", "lie", "claim", "mayor", "logbook"]],
    ),
    PhaseOneCase(
        id="P1-18",
        description="Search a location for hidden signs or marks",
        player_input="I search the Old Well area carefully for any unusual marks or recent activity",
        player_location="Old Well",
        npc_locations={"Old Tellan": "Old Well"},
        expect_finalize=True,
        expect_blocked=False,
        expected_tools_called=["list_scene_entities", "skill_check"],
        expected_narration_focus_keywords=[["search", "look", "find", "well", "mark", "sign"]],
    ),
    PhaseOneCase(
        id="P1-19",
        description="Player asks to review their recent skill check history",
        player_input="How have my skill checks been going so far?",
        player_location="Copper Cup",
        expect_finalize=True,
        expect_blocked=False,
        expected_tools_called=["get_recent_skill_checks"],
        expected_turn_summary_keywords=[["history", "check", "recent", "roll", "skill"]],
        max_iterations=4,
    ),
    PhaseOneCase(
        id="P1-20",
        description="Attempt to intimidate an NPC into not interfering with a restricted area",
        player_input="I step close to Thom and tell him in a low voice that he will let me up those stairs or things will get very uncomfortable for him",
        player_location="Copper Cup",
        npc_locations={"Thom": "Copper Cup"},
        expect_finalize=True,
        expect_blocked=False,
        expected_tools_called=["check_can_interact", "skill_check"],
        expected_narration_focus_keywords=[["intimidate", "threaten", "pressure", "thom", "stair"]],
    ),

    # -------------------------------------------------------------------------
    # HARD (P1-21 through P1-30)
    # Multiple simultaneous intentions, several tool calls, nuanced judgment,
    # and scenarios that are designed to be difficult to handle correctly.
    # -------------------------------------------------------------------------

    PhaseOneCase(
        id="P1-21",
        description="Memory Recollection",
        player_input="I try to remember what the bartender at the copper cup told me",
        player_location="Town Square",
        expect_finalize=True,
        expect_blocked=True,
        skill_check_outcome="success",
        expected_tools_called=["retrieve_memory_tool", "list_world_entities"],
        expected_turn_summary_keywords=[["copper", "cup", "bar"], ["bartender"]],
    ),
    PhaseOneCase(
        id="P1-22",
        description="Talk to Serah, ask about her private notes, and inspect the prayer beads, all at the temple",
        player_input="I speak with Cleric Serah about the patterns she has been tracking, ask to see those private notes she keeps, and take a close look at the salt-stained prayer beads on the altar",
        player_location="Temple of the Tide",
        npc_locations={"Cleric Serah": "Temple of the Tide"},
        expect_finalize=True,
        expect_blocked=False,
        expected_tools_called=["check_can_interact"],
    ),
    PhaseOneCase(
        id="P1-23",
        description="Charm Mara with conversation while also attempting to pocket her key ring",
        player_input="I start a warm conversation with Mara to put her at ease, and while she is distracted talking to me I try to slip the cellar brass ring off the hook behind the counter",
        player_location="Copper Cup",
        npc_locations={"Mara": "Copper Cup"},
        expect_finalize=True,
        expect_blocked=False,
        expected_tools_called=["check_can_interact", "skill_check", ["list_scene_entities", "get_entity_state"]],
        skill_check_outcome="success",
        expected_narration_focus_keywords=[["mara"], ["charm", "distract", "persuade", "key", "ring", "slip"]],
    ),
    PhaseOneCase(
        id="P1-24",
        description="Sneak past the hired guards at the Wizard's House and scan the interior",
        player_input="I creep up to the Wizard's House, slip past the guards without being seen, and once inside I look around to see what is in there",
        player_location="Town Square",
        npc_locations={"Town Wizard Arlen": "Wizard's House"},
        expect_finalize=True,
        expect_blocked=False,
        expected_tools_called=["skill_check", "check_can_interact", ["list_scene_entities", "get_world_location", "get_world_scene", "get_entity_state"]],
        expected_narration_focus_keywords=[["wizard", "house", "sneak", "guard", "inside"]],
    ),
    PhaseOneCase(
        id="P1-25",
        description="Move to East Alley, pick up the hidden knife, and ask Pip what it was doing there",
        player_input="I slip into East Alley, feel along the base of the wall for that loose brick Pip mentioned, pull out the knife that was hidden there, and then ask Pip directly what they know about it",
        player_location="Town Square",
        npc_locations={"Street Urchin Pip": "East Alley"},
        discovered_keys=["Hidden Alley Knife"],
        conversation_history=[
            "I talk to Pip.",
            "Pip mentions a knife wrap near a loose brick, left where only they can find it.",
        ],
        expect_finalize=True,
        expect_blocked=False,
        expected_tools_called=["check_can_interact"],
        expected_turn_summary_keywords=[["alley"], ["knife", "brick"], ["pip"]],
    ),
    PhaseOneCase(
        id="P1-26",
        description="Confront Mitch, press him hard for a confession, and watch carefully for signs of deception",
        player_input="I get in Mitch's face and demand he explain the inconsistencies in his story, watching his eyes and hands closely for any signs that he is lying to me",
        player_location="Town Square",
        npc_locations={"Mitch": "Town Square"},
        quest_flags={"talked_to_mitch": True},
        conversation_history=[
            "I speak with Mitch about the first bloodstain he found.",
            "Mitch describes finding it near the riverside but stumbles over the timeline.",
        ],
        expect_finalize=True,
        expect_blocked=False,
        expected_tools_called=["check_can_interact", "skill_check"],
        expected_narration_focus_keywords=[["mitch"], ["confront", "press", "demand", "lie", "watch"]],
    ),
    PhaseOneCase(
        id="P1-27",
        description="Attempt to pick the storeroom lock with the bent lockpick set while Brin is nearby",
        player_input="With the bent lockpick set in hand, I crouch at the storeroom door and work the lock quietly while keeping an eye on Brin to make sure he does not notice me",
        player_location="Storeroom Door",
        npc_locations={"Brin": "Copper Cup"},
        discovered_keys=["Bent Lockpick Set", "Storeroom Door"],
        conversation_history=[
            "I examine the storeroom door.",
            "The brass four-dial combination lock gleams under the lamplight.",
        ],
        expect_finalize=True,
        expect_blocked=False,
        expected_tools_called=["check_can_interact", "skill_check"],
        expected_narration_focus_keywords=[["lock", "pick", "storeroom", "door", "brin"]],
    ),
    PhaseOneCase(
        id="P1-28",
        description="At the Docks, persuade Hara, query Finn, and examine the frayed rope, all in one sweep",
        player_input="I press Dockmaster Hara for the details behind the ledger gaps, then pull aside Deckhand Finn to ask what he saw at the pump that night, and I take a close look at that frayed mooring rope near the pier",
        player_location="Docks",
        npc_locations={"Dockmaster Hara": "Docks", "Deckhand Finn": "Docks"},
        expect_finalize=True,
        expect_blocked=False,
        expected_tools_called=["skill_check", "check_can_interact", "get_entity_state"],
        expected_turn_summary_keywords=[["hara"], ["finn"], ["rope", "frayed"]],
    ),
    PhaseOneCase(
        id="P1-29",
        description="Enter the Smuggler's Entrance, deal with Lia, and try to take the ledger and learn what she knows",
        player_input="I climb down into the Smuggler's Entrance, find Smuggler Lia, and offer her a deal: I will not tell the watch about her operation if she hands over the ledger and tells me everything she has seen on those pre-dawn cleanup nights",
        player_location="Old Well",
        npc_locations={"Smuggler Lia": "Smuggler's Entrance"},
        expect_finalize=True,
        expect_blocked=False,
        expected_tools_called=["check_can_interact", ["get_world_scene", "get_entity_state"], "skill_check"],
        expected_turn_summary_keywords=[["smuggler", "lia", "entrance"], ["ledger"], ["deal", "offer", "bargain", "convince"]],
    ),
    PhaseOneCase(
        id="P1-30",
        description="Full assault on the Wizard's House: push past guards, confront Arlen, search for the vial, inspect the chalk, scan the room",
        player_input="I march straight to the Wizard's House, tell the hired guards to stand aside in a way that makes it clear I am not asking, then once I am in front of Arlen I confront him with what I know and demand the truth while looking around the room for the silver memory vial and that arcane chalk I have heard about",
        player_location="Town Square",
        npc_locations={"Town Wizard Arlen": "Wizard's House"},
        quest_flags={"arlen_confronted": False},
        conversation_history=[
            "I have gathered evidence pointing to memory manipulation in the town.",
            "Witnesses describe the wizard working late, and the arcane chalk and silver vial have been mentioned in hushed tones.",
        ],
        expect_finalize=True,
        expect_blocked=False,
        expected_tools_called=[
            "check_can_interact",
            "skill_check",
            ["get_entity_state", "get_world_scene"],
            "list_scene_entities",
        ],
        expected_turn_summary_keywords=[
            ["wizard", "arlen", "house"],
            ["guard", "push", "confront"],
            ["vial", "chalk", "memory"],
        ],
    ),
]


__all__ = ["PhaseOneCase", "PHASE_ONE_CASES"]