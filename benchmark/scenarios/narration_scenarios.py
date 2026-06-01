from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class NarrationCase:
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

    # Phase 1 outputs to feed the narrator
    turn_summary: str = ""
    narration_focus: str = ""
    blocked_reason: str = ""
    action_tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    phase_one_tool_calls: List[Dict[str, Any]] = field(default_factory=list)

    # Checks to apply to the resulting narrative
    checks: List[str] = field(default_factory=list)
    forbidden_patterns: List[str] = field(default_factory=list)

_BASE_CHECKS = [
    "has_two_sections",
    "thoughts_before_narrative",
    "second_person",
    "no_explicit_choices",
    "minimum_length:30",
    "concise:300",
    "no_player_agency_taken",
    "narrative_no_the_player",
    "narrative_no_bare_i",
]


NARRATION_CASES: List[NarrationCase] = [

    # -------------------------------------------------------------------------
    # EASY (NAR-01 through NAR-10)
    # Single clear event, uncomplicated tone, no competing demands on the writer.
    # -------------------------------------------------------------------------

    NarrationCase(
        id="NAR-01",
        description="Standard arrival narration after moving to the Copper Cup",
        player_input="I walk to the Copper Cup",
        player_location="Copper Cup",
        visited_keys=["Town Square", "Copper Cup"],
        turn_summary="Player walked from Town Square to the Copper Cup.",
        narration_focus="Describe the arrival at the Copper Cup: warm lamplight, smell of ale, the regulars at the bar.",
        blocked_reason="",
        phase_one_tool_calls=[
            {"phase": "phase_one", "name": "check_can_interact",
             "arguments": {"entity_key": "Copper Cup"},
             "result": {"ok": True, "can_interact": True, "entity_type": "location"}},
        ],
        checks=_BASE_CHECKS + ["mentions_current_location"],
        forbidden_patterns=[r"\broll\b", r"\bDC\s*\d"],
    ),
    NarrationCase(
        id="NAR-02",
        description="Trivial greeting should produce a brief, scene-preserving response",
        player_input="hi",
        player_location="Town Square",
        turn_summary="Player offered a greeting; nothing in the world changed.",
        narration_focus="Brief acknowledgement; keep the scene alive around the player.",
        blocked_reason="",
        checks=[
            "has_two_sections",
            "thoughts_before_narrative",
            "second_person",
            "no_explicit_choices",
            "concise:120",
            "no_player_agency_taken",
            "narrative_no_the_player",
            "narrative_no_bare_i",
        ],
    ),
    NarrationCase(
        id="NAR-03",
        description="Player picks up a small item; narration should be brief and tactile",
        player_input="I pick up the coin from the fountain stones",
        player_location="Town Square",
        turn_summary="Player picked up the Bronze Fountain Coin from the central fountain.",
        narration_focus="Describe the feel of the worn coin, the brief movement, and the square continuing around the player.",
        blocked_reason="",
        phase_one_tool_calls=[
            {"phase": "phase_one", "name": "check_can_interact",
             "arguments": {"entity_key": "Bronze Fountain Coin"},
             "result": {"ok": True, "can_interact": True, "entity_type": "item"}},
        ],
        checks=_BASE_CHECKS,
        forbidden_patterns=[r"(?i)\broll\b", r"(?i)\bcheck\b"],
    ),
    NarrationCase(
        id="NAR-04",
        description="First look at the Town Square on arrival",
        player_input="I look around the square",
        player_location="Town Square",
        visited_keys=["Town Square"],
        turn_summary="Player surveyed Town Square and noted the lanterns, the crowd, and the uneasy atmosphere.",
        narration_focus="Paint the square at dusk: the lanterns coming alive, the hollow-eyed crowd, the low murmur of fear passing from mouth to mouth.",
        blocked_reason="",
        phase_one_tool_calls=[
            {"phase": "phase_one", "name": "list_scene_entities",
             "arguments": {},
             "result": {"ok": True, "entities": ["Street Performer Jorin", "Town Crier Jessa", "Mitch", "Bronze Fountain Coin"]}},
        ],
        checks=_BASE_CHECKS + ["mentions_current_location"],
        forbidden_patterns=[r"(?i)\broll\b"],
    ),
    NarrationCase(
        id="NAR-05",
        description="Brief pleasant exchange with Jorin who answers helpfully",
        player_input="I ask Jorin what he has been seeing at night",
        player_location="Town Square",
        npc_locations={"Street Performer Jorin": "Town Square"},
        turn_summary="Player asked Street Performer Jorin about recent nights. Jorin answered freely, mentioning that he spots who is lying about where they were.",
        narration_focus="Let Jorin answer with easy charm, juggling as he talks, hinting that he knows more than he lets on.",
        blocked_reason="",
        phase_one_tool_calls=[
            {"phase": "phase_one", "name": "retrieve_memory_tool",
             "arguments": {"entity_name": "Street Performer Jorin"},
             "result": {"ok": True, "memories": ["Jorin watches faces and can spot who is lying about the night.", "He heard Mitch muttering about red hands."]}},
        ],
        checks=_BASE_CHECKS,
        forbidden_patterns=[r"(?i)\bprovide your\b", r"(?i)\bwhat would you like\b"],
    ),
    NarrationCase(
        id="NAR-06",
        description="First arrival at the Temple of the Tide",
        player_input="I go to the Temple of the Tide",
        player_location="Temple of the Tide",
        visited_keys=["Town Square", "Temple of the Tide"],
        turn_summary="Player arrived at the Temple of the Tide for the first time.",
        narration_focus="Capture the hush of the temple: candles before the sea goddess statue, the smell of salt incense, the faces of worried townsfolk seeking answers.",
        blocked_reason="",
        phase_one_tool_calls=[
            {"phase": "phase_one", "name": "check_can_interact",
             "arguments": {"entity_key": "Temple of the Tide"},
             "result": {"ok": True, "can_interact": True, "entity_type": "location"}},
        ],
        checks=_BASE_CHECKS + ["mentions_current_location"],
        forbidden_patterns=[r"\broll\b", r"(?i)\berror\b"],
    ),
    NarrationCase(
        id="NAR-07",
        description="Player picks up the Carved Driftwood Charm at the Old Shrine",
        player_input="I take the carved driftwood charm from the shrine bowl",
        player_location="Old Shrine",
        npc_locations={"Caretaker Ilya": "Old Shrine"},
        turn_summary="Player took the Carved Driftwood Charm from the offering bowl at the Old Shrine.",
        narration_focus="Describe the pale driftwood, the faint incense smell, the carvings of a curling wave, and the weight of taking something left as an offering.",
        blocked_reason="",
        phase_one_tool_calls=[
            {"phase": "phase_one", "name": "check_can_interact",
             "arguments": {"entity_key": "Carved Driftwood Charm"},
             "result": {"ok": True, "can_interact": True, "entity_type": "item"}},
        ],
        checks=_BASE_CHECKS,
        forbidden_patterns=[r"(?i)\broll\b", r"(?i)\bcheck\b"],
    ),
    NarrationCase(
        id="NAR-08",
        description="Arrival at the Watch Barracks for the first time",
        player_input="I walk to the Watch Barracks",
        player_location="Watch Barracks",
        visited_keys=["Town Square", "Watch Barracks"],
        turn_summary="Player arrived at the Watch Barracks from Town Square.",
        narration_focus="Describe the sturdy building, the racks of spears, the off-duty guards and their wary glances at a stranger entering their space.",
        blocked_reason="",
        phase_one_tool_calls=[
            {"phase": "phase_one", "name": "check_can_interact",
             "arguments": {"entity_key": "Watch Barracks"},
             "result": {"ok": True, "can_interact": True, "entity_type": "location"}},
        ],
        checks=_BASE_CHECKS + ["mentions_current_location"],
        forbidden_patterns=[r"\broll\b"],
    ),
    NarrationCase(
        id="NAR-09",
        description="Meta question about game mechanics handled with a brief, in-character answer",
        player_input="Wait, can I actually pick locks in this game?",
        player_location="Copper Cup",
        turn_summary="Player asked a meta question about whether lockpicking is possible. It is possible with the right tools and a sleight of hand check.",
        narration_focus="Acknowledge the meta question briefly and confirm that lockpicking is possible with the right tools.",
        blocked_reason="",
        checks=[
            "has_two_sections",
            "thoughts_before_narrative",
            "no_explicit_choices",
            "concise:150",
            "no_player_agency_taken",
        ],
        forbidden_patterns=[],
    ),
    NarrationCase(
        id="NAR-10",
        description="Player finds and reads the Hidden Scrap note at the Bar Counter",
        player_input="I search behind the crates at the bar counter for anything useful",
        player_location="Bar Counter",
        npc_locations={"Mara": "Bar Counter"},
        turn_summary="Player found the Hidden Scrap note tucked behind a loose crate at the Bar Counter. The note hints at the storeroom lock code.",
        narration_focus="Convey the small discovery: the greasy paper, the handwriting, the line about the lock being the wedding anniversary date.",
        blocked_reason="",
        phase_one_tool_calls=[
            {"phase": "phase_one", "name": "check_can_interact",
             "arguments": {"entity_key": "Hidden Scrap"},
             "result": {"ok": True, "can_interact": True, "entity_type": "item"}},
        ],
        checks=_BASE_CHECKS,
        forbidden_patterns=[r"(?i)\broll\b"],
    ),

    # -------------------------------------------------------------------------
    # MEDIUM (NAR-11 through NAR-20)
    # Competing tones, failure states, reluctant NPCs, partial outcomes.
    # -------------------------------------------------------------------------

    NarrationCase(
        id="NAR-11",
        description="Successful stealth check past Gate Guard Ren",
        player_input="I try to slip past Gate Guard Ren",
        player_location="Harbor Gate",
        npc_locations={"Gate Guard Ren": "Harbor Gate"},
        turn_summary="Player attempted to sneak past Gate Guard Ren. Stealth check succeeded with 15 vs DC 13.",
        narration_focus="Show the quiet success: each step placed with care, Ren's gaze drifting across the cobbles and missing the player entirely.",
        blocked_reason="",
        action_tool_calls=[
            {"phase": "phase_one", "name": "skill_check",
             "arguments": {"entity_key": "Player", "skill": "stealth", "dc": 13},
             "result": {"ok": True, "success": True, "roll": 15, "total": 15, "dc": 13}},
        ],
        checks=_BASE_CHECKS,
        forbidden_patterns=[r"(?i)roll\s+(a|an|your)", r"(?i)provide\s+your\s+(bonus|modifier)"],
    ),
    NarrationCase(
        id="NAR-12",
        description="Failed persuasion attempt with Mara who refuses to open up",
        player_input="I try to convince Mara to let me into the storeroom",
        player_location="Copper Cup",
        npc_locations={"Mara": "Copper Cup"},
        turn_summary="Player attempted to persuade Mara to open the storeroom. Persuasion failed with 6 vs DC 14. Mara gave a polite but firm refusal.",
        narration_focus="Show Mara's polite deflection without breaking her character: she is not hostile, just unwilling. Her manner closes the conversation.",
        blocked_reason="",
        action_tool_calls=[
            {"phase": "phase_one", "name": "skill_check",
             "arguments": {"entity_key": "Player", "skill": "persuasion", "dc": 14},
             "result": {"ok": True, "success": False, "roll": 6, "total": 6, "dc": 14}},
        ],
        checks=_BASE_CHECKS,
        forbidden_patterns=[r"(?i)\bgame over\b", r"(?i)\byou fail\b"],
    ),
    NarrationCase(
        id="NAR-13",
        description="Blocked movement: player cannot reach Warehouse Row directly from the Temple",
        player_input="I head straight to Warehouse Row",
        player_location="Temple of the Tide",
        turn_summary="Player tried to move directly from the Temple of the Tide to Warehouse Row. Those locations are not connected.",
        narration_focus="Acknowledge the player's intent and surface the path constraint without game-world jargon. Suggest the route exists but must be taken in steps.",
        blocked_reason="Warehouse Row is not directly reachable from the Temple of the Tide.",
        checks=_BASE_CHECKS,
        forbidden_patterns=[r"(?i)\berror\b", r"(?i)\bblocked\b", r"(?i)\bnot\s+possible\b"],
    ),
    NarrationCase(
        id="NAR-14",
        description="Cleric Serah reluctantly shares a piece of her private pattern notes",
        player_input="I ask Serah about the patterns she has been documenting",
        player_location="Temple of the Tide",
        npc_locations={"Cleric Serah": "Temple of the Tide"},
        turn_summary="Player asked Cleric Serah about the patterns she tracks in her private notes. She shared a fragment: the same three symbols appear near every bloodstain.",
        narration_focus="Convey Serah's careful weighing of trust versus danger. Let the clue feel earned: a small, precise detail offered after a pause.",
        blocked_reason="",
        phase_one_tool_calls=[
            {"phase": "phase_one", "name": "retrieve_memory_tool",
             "arguments": {"entity_name": "Cleric Serah"},
             "result": {"ok": True, "memories": ["Serah keeps private notes on recurring symbols linked to bloodstains.", "She has treated people with unexplained wounds."]}},
        ],
        checks=_BASE_CHECKS,
        forbidden_patterns=[r"(?i)\broll\b", r"(?i)\bwhat would you like\b"],
    ),
    NarrationCase(
        id="NAR-15",
        description="Cook Brenna nervously shares what she saw near the back door",
        player_input="I ask Brenna quietly what she remembers about those pre-dawn mornings",
        player_location="Back Door - Copper Cup",
        npc_locations={"Cook Brenna": "Back Door - Copper Cup"},
        turn_summary="Player asked Cook Brenna about what she saw before dawn. Brenna described Mitch pacing the back door and dark smears on a crate that were gone by morning.",
        narration_focus="Brenna speaks in bursts between glances at the door. She is scared, loyal to the tavern, and not sure she should be talking. Let her words arrive in pieces.",
        blocked_reason="",
        phase_one_tool_calls=[
            {"phase": "phase_one", "name": "retrieve_memory_tool",
             "arguments": {"entity_name": "Cook Brenna"},
             "result": {"ok": True, "memories": ["Brenna noticed Mitch pacing the back door before dawn twice this week.", "She saw dark smears on a crate that were gone after sunrise."]}},
        ],
        checks=_BASE_CHECKS,
        forbidden_patterns=[r"(?i)\broll\b"],
    ),
    NarrationCase(
        id="NAR-16",
        description="Failed pickpocket attempt caught by Pip",
        player_input="I try to lift the lockpick set from Pip's pocket",
        player_location="East Alley",
        npc_locations={"Street Urchin Pip": "East Alley"},
        turn_summary="Player attempted to pickpocket Street Urchin Pip. Sleight of hand failed with 5 vs DC 12. Pip noticed immediately and stepped back.",
        narration_focus="Pip catches the movement before it completes. Their expression shifts from streetwise boredom to flat suspicion. No shouting, just a long look that says everything.",
        blocked_reason="",
        action_tool_calls=[
            {"phase": "phase_one", "name": "skill_check",
             "arguments": {"entity_key": "Player", "skill": "sleight_of_hand", "dc": 12},
             "result": {"ok": True, "success": False, "roll": 5, "total": 5, "dc": 12}},
        ],
        checks=_BASE_CHECKS,
        forbidden_patterns=[r"(?i)\bgame over\b", r"(?i)\byou fail\b"],
    ),
    NarrationCase(
        id="NAR-17",
        description="Captain Varr stonewalls the request to review the patrol logbook",
        player_input="I ask Captain Varr to let me review the Night Patrol Logbook",
        player_location="Watch Barracks",
        npc_locations={"Captain Varr": "Watch Barracks"},
        turn_summary="Player asked Captain Varr for access to the Night Patrol Logbook. Varr refused without a writ of authorization from the mayor.",
        narration_focus="Varr is not hostile, only immovable. His respect for chain of command is genuine. The refusal is professional, almost gentle, and absolutely final.",
        blocked_reason="",
        phase_one_tool_calls=[
            {"phase": "phase_one", "name": "retrieve_memory_tool",
             "arguments": {"entity_name": "Captain Varr"},
             "result": {"ok": True, "memories": ["Varr takes safety personally.", "He is suspicious of the wizard but equally wary of vigilantism."]}},
        ],
        checks=_BASE_CHECKS,
        forbidden_patterns=[r"(?i)\berror\b", r"(?i)\byou cannot\b"],
    ),
    NarrationCase(
        id="NAR-18",
        description="Scribe Loth flatly denies the existence of a duplicate ledger",
        player_input="I ask Scribe Loth to show me the hidden duplicate records",
        player_location="Town Hall",
        npc_locations={"Scribe Loth": "Town Hall"},
        turn_summary="Player asked Scribe Loth about the hidden duplicate ledger. Loth denied everything and went back to his paperwork.",
        narration_focus="Loth's denial should feel practiced. He does not look up, barely pauses his writing, and the words come out the way someone recites a line they have said many times before.",
        blocked_reason="",
        phase_one_tool_calls=[
            {"phase": "phase_one", "name": "retrieve_memory_tool",
             "arguments": {"entity_name": "Scribe Loth"},
             "result": {"ok": True, "memories": ["Loth maintains a hidden duplicate ledger.", "Public records keep getting quietly amended."]}},
        ],
        checks=_BASE_CHECKS,
        forbidden_patterns=[r"(?i)\berror\b"],
    ),
    NarrationCase(
        id="NAR-19",
        description="Failed stealth attempt at Warehouse Row: Foreman Kesh spots the player",
        player_input="I try to slip into Warehouse Row without Kesh noticing me",
        player_location="Warehouse Row",
        npc_locations={"Foreman Kesh": "Warehouse Row"},
        turn_summary="Player tried to enter Warehouse Row unnoticed. Stealth check failed with 4 vs DC 11. Foreman Kesh spotted the player and called out.",
        narration_focus="The moment of failure: a boot scraping stone, Kesh's head turning, eyes finding the player instantly. No dramatics, just the cold fact of being seen.",
        blocked_reason="",
        action_tool_calls=[
            {"phase": "phase_one", "name": "skill_check",
             "arguments": {"entity_key": "Player", "skill": "stealth", "dc": 11},
             "result": {"ok": True, "success": False, "roll": 4, "total": 4, "dc": 11}},
        ],
        checks=_BASE_CHECKS,
        forbidden_patterns=[r"(?i)\bgame over\b", r"(?i)roll\s+(a|an|your)"],
    ),
    NarrationCase(
        id="NAR-20",
        description="Successful intimidation of Brin gets a small admission",
        player_input="I press Brin hard about the night he claims he cannot remember",
        player_location="Copper Cup",
        npc_locations={"Brin": "Copper Cup"},
        turn_summary="Player pressed Brin on his memory gaps. Intimidation succeeded with 14 vs DC 12. Brin admitted he sometimes wakes not knowing if he worked the late shift.",
        narration_focus="Brin caves under pressure but only to the truth he already suspects. He is not hiding something dramatic, just his own fear. Let his words be small and ashamed.",
        blocked_reason="",
        action_tool_calls=[
            {"phase": "phase_one", "name": "skill_check",
             "arguments": {"entity_key": "Player", "skill": "intimidation", "dc": 12},
             "result": {"ok": True, "success": True, "roll": 14, "total": 14, "dc": 12}},
        ],
        phase_one_tool_calls=[
            {"phase": "phase_one", "name": "retrieve_memory_tool",
             "arguments": {"entity_name": "Brin"},
             "result": {"ok": True, "memories": ["Brin swears he locked the storeroom himself but sometimes wakes unsure.", "He trusts Mara and avoids speaking openly about the stains."]}},
        ],
        checks=_BASE_CHECKS,
        forbidden_patterns=[r"(?i)\bgame over\b"],
    ),

    # -------------------------------------------------------------------------
    # HARD (NAR-21 through NAR-30)
    # Multi-event turns, emotionally charged scenes, moral weight, competing
    # tones, and situations where a lesser narrator would break character or
    # take player agency. These are designed to be very difficult to execute well.
    # -------------------------------------------------------------------------

    NarrationCase(
        id="NAR-21",
        description="Multi-event turn: move to East Alley, find hidden knife, brief tense exchange with Pip",
        player_input="I slip into East Alley, find the knife behind the loose brick, and ask Pip about it",
        player_location="East Alley",
        npc_locations={"Street Urchin Pip": "East Alley"},
        visited_keys=["Town Square", "East Alley"],
        turn_summary="Player moved to East Alley, recovered the Hidden Alley Knife from behind the loose brick, and questioned Street Urchin Pip about what they knew.",
        narration_focus="Three beats in one: the alley's wet stone underfoot, the knife cold and rust-smelling in the hand, and Pip watching the player with an expression that is more calculation than surprise.",
        blocked_reason="",
        phase_one_tool_calls=[
            {"phase": "phase_one", "name": "check_can_interact",
             "arguments": {"entity_key": "East Alley"},
             "result": {"ok": True, "can_interact": True, "entity_type": "location"}},
            {"phase": "phase_one", "name": "check_can_interact",
             "arguments": {"entity_key": "Hidden Alley Knife"},
             "result": {"ok": True, "can_interact": True, "entity_type": "item"}},
            {"phase": "phase_one", "name": "retrieve_memory_tool",
             "arguments": {"entity_name": "Street Urchin Pip"},
             "result": {"ok": True, "memories": ["Pip found a knife wrap with fresh rust near a loose brick.", "They know hidden routes through the alley."]}},
        ],
        checks=_BASE_CHECKS + ["minimum_length:80"],
        forbidden_patterns=[r"(?i)\broll\b", r"(?i)\byou find\b"],
    ),
    NarrationCase(
        id="NAR-22",
        description="Emotionally charged confrontation with Mitch who is on the edge of breaking",
        player_input="I press Mitch hard, show him what I know, and demand the truth",
        player_location="Town Square",
        npc_locations={"Mitch": "Town Square"},
        quest_flags={"talked_to_mitch": True},
        turn_summary="Player confronted Mitch in the square with accumulated evidence. Intimidation succeeded with 17 vs DC 14. Mitch did not confess fully but cracked visibly, becoming agitated and contradicting himself more openly.",
        narration_focus="Mitch is not a liar by nature. He is a frightened man whose own mind has been working against him. The confrontation should feel like watching someone fight to hold a story together as it falls apart.",
        blocked_reason="",
        action_tool_calls=[
            {"phase": "phase_one", "name": "skill_check",
             "arguments": {"entity_key": "Player", "skill": "intimidation", "dc": 14},
             "result": {"ok": True, "success": True, "roll": 17, "total": 17, "dc": 14}},
        ],
        phase_one_tool_calls=[
            {"phase": "phase_one", "name": "retrieve_memory_tool",
             "arguments": {"entity_name": "Mitch"},
             "result": {"ok": True, "memories": ["Mitch's story shifts when pressed for exact times.", "He wakes exhausted with injuries from work he cannot recall.", "He keeps blaming the wizard."]}},
        ],
        checks=_BASE_CHECKS + ["minimum_length:100"],
        forbidden_patterns=[r"(?i)\bconfess\b", r"(?i)\bgame over\b", r"(?i)\byou have proven\b"],
    ),
    NarrationCase(
        id="NAR-23",
        description="Wizard Arlen answers questions but conceals the full truth; player reads the gap",
        player_input="I question Arlen closely about what he has been doing to people's memories",
        player_location="Wizard's House",
        npc_locations={"Town Wizard Arlen": "Wizard's House"},
        turn_summary="Player questioned Wizard Arlen about memory manipulation. Insight check succeeded with 18 vs DC 14. Arlen confirmed he has worked with memories but framed it as mercy, not deception. The player can tell there is more.",
        narration_focus="Arlen answers carefully and truthfully in the most technical sense. Every word he uses is accurate and every silence he holds is meaningful. The player should feel the shape of what is being left unsaid.",
        blocked_reason="",
        action_tool_calls=[
            {"phase": "phase_one", "name": "skill_check",
             "arguments": {"entity_key": "Player", "skill": "insight", "dc": 14},
             "result": {"ok": True, "success": True, "roll": 18, "total": 18, "dc": 14}},
        ],
        phase_one_tool_calls=[
            {"phase": "phase_one", "name": "retrieve_memory_tool",
             "arguments": {"entity_name": "Town Wizard Arlen"},
             "result": {"ok": True, "memories": ["Arlen has used risky memory-working spells to reduce panic.", "He believes containment is safer than exposure."]}},
        ],
        checks=_BASE_CHECKS + ["minimum_length:100"],
        forbidden_patterns=[r"(?i)\bhe confesses\b", r"(?i)\bhe admits\b", r"(?i)\byou know the truth\b"],
    ),
    NarrationCase(
        id="NAR-24",
        description="Successful stealth reveals Mitch sleepwalking to the Old Well in the dark",
        player_input="I follow Mitch quietly at night to see where he goes",
        player_location="Old Well",
        npc_locations={"Mitch": "Old Well"},
        turn_summary="Player followed Mitch through the dark after curfew. Stealth check succeeded with 16 vs DC 13. Mitch walked to the Old Well in a blank-eyed trance, stood over it for several minutes, then turned back toward the square.",
        narration_focus="This should be unsettling in a quiet way. Mitch is not menacing here; he is absent. The well is just a well. The horror is in how ordinary everything looks and how wrong it all is.",
        blocked_reason="",
        action_tool_calls=[
            {"phase": "phase_one", "name": "skill_check",
             "arguments": {"entity_key": "Player", "skill": "stealth", "dc": 13},
             "result": {"ok": True, "success": True, "roll": 16, "total": 16, "dc": 13}},
        ],
        checks=_BASE_CHECKS + ["minimum_length:100"],
        forbidden_patterns=[r"(?i)\broll\b", r"(?i)\byou have proven\b", r"(?i)\bthe mystery is solved\b"],
    ),
    NarrationCase(
        id="NAR-25",
        description="Bridge Watcher Sol breaks down while recalling a terrible night at the South Bridge",
        player_input="I ask Sol to walk me through everything he remembers from that storm night on the bridge",
        player_location="South Bridge",
        npc_locations={"Bridge Watcher Sol": "South Bridge"},
        turn_summary="Player asked Bridge Watcher Sol to describe the storm night he mentioned in his logs. Sol began his account but became visibly distressed partway through, described shouting and then silence, and then stopped talking entirely.",
        narration_focus="Sol does not dramatize his distress. He just stops. A man who has watched bridges his whole life, suddenly very still in the middle of a sentence. What he does not say is as heavy as what he does.",
        blocked_reason="",
        phase_one_tool_calls=[
            {"phase": "phase_one", "name": "retrieve_memory_tool",
             "arguments": {"entity_name": "Bridge Watcher Sol"},
             "result": {"ok": True, "memories": ["Sol heard shouting near the South Bridge on a storm night, then silence and no witnesses.", "He logs repeated late-night crossings no one later remembers making."]}},
        ],
        checks=_BASE_CHECKS + ["minimum_length:100"],
        forbidden_patterns=[r"(?i)\bhe cries\b", r"(?i)\bhe weeps\b", r"(?i)\byou comfort him\b"],
    ),
    NarrationCase(
        id="NAR-26",
        description="Two NPCs contradict each other in front of the player at the Market Stalls",
        player_input="I get Jorin and Nima talking together about what they each saw near the Old Well",
        player_location="Market Stalls",
        npc_locations={"Street Performer Jorin": "Town Square", "Spice Seller Nima": "Market Stalls"},
        turn_summary="Player brought Jorin and Nima's accounts into the same conversation. The two contradict each other on the time of the argument near the Old Well: Jorin places it before the bells, Nima places it after. Both are certain.",
        narration_focus="Neither Jorin nor Nima is lying. The contradiction should feel like a clue, not a failure. Both speak with the same conviction, neither backing down, and the gap between their accounts sits in the air between them.",
        blocked_reason="",
        phase_one_tool_calls=[
            {"phase": "phase_one", "name": "retrieve_memory_tool",
             "arguments": {"entity_name": "Street Performer Jorin"},
             "result": {"ok": True, "memories": ["Jorin heard Mitch muttering about red hands.", "He watches faces and spots who is lying about where they were."]}},
            {"phase": "phase_one", "name": "retrieve_memory_tool",
             "arguments": {"entity_name": "Spice Seller Nima"},
             "result": {"ok": True, "memories": ["Nima remembers voices arguing near Old Well just before dawn on market day.", "She noticed a spike in lye, lamp oil, and bandages."]}},
        ],
        checks=_BASE_CHECKS + ["minimum_length:120"],
        forbidden_patterns=[r"(?i)\bone of them is lying\b", r"(?i)\bthe truth is\b"],
    ),
    NarrationCase(
        id="NAR-27",
        description="Failed intimidation at the Watch Barracks brings guards to the scene",
        player_input="I grab Thom by the collar and tell him to stand aside or face consequences",
        player_location="Watch Barracks",
        npc_locations={"Thom": "Watch Barracks", "Captain Varr": "Watch Barracks"},
        turn_summary="Player attempted to physically intimidate Thom at the Watch Barracks. Intimidation failed with 7 vs DC 15. Thom reacted badly and called for Captain Varr.",
        narration_focus="The failure has weight. Thom does not look scared. He looks annoyed, and that is worse. Varr arriving is not a rescue for the player; it is a consequence. The moment should feel like a door closing.",
        blocked_reason="",
        action_tool_calls=[
            {"phase": "phase_one", "name": "skill_check",
             "arguments": {"entity_key": "Player", "skill": "intimidation", "dc": 15},
             "result": {"ok": True, "success": False, "roll": 7, "total": 7, "dc": 15}},
        ],
        checks=_BASE_CHECKS + ["minimum_length:100"],
        forbidden_patterns=[r"(?i)\bgame over\b", r"(?i)\byou are arrested\b", r"(?i)\byou fail\b"],
    ),
    NarrationCase(
        id="NAR-28",
        description="Player presents evidence publicly in the Town Square to the gathered crowd",
        player_input="I stand up in the square and tell everyone what I have found about the bloodstains and the memory manipulation",
        player_location="Town Square",
        npc_locations={
            "Street Performer Jorin": "Town Square",
            "Town Crier Jessa": "Town Square",
            "Mitch": "Town Square",
        },
        quest_flags={"serah_revealed_pattern": True, "jorin_shared_mitch_info": True},
        turn_summary="Player made a public address in Town Square presenting gathered evidence. The crowd reacted with a mix of disbelief, fear, and the uneasy feeling that some of it rings too true. Mitch went very still.",
        narration_focus="This is a public moment with private consequences. Some faces go blank. Mitch stands at the edge of the crowd, not moving. Jessa reaches for her bell but does not ring it. Give the scene its weight without resolving it.",
        blocked_reason="",
        checks=_BASE_CHECKS + ["minimum_length:150"],
        forbidden_patterns=[
            r"(?i)\bthe crowd cheers\b",
            r"(?i)\bthe mystery is solved\b",
            r"(?i)\bthe case is closed\b",
        ],
    ),
    NarrationCase(
        id="NAR-29",
        description="Simultaneous confrontation: Mitch and Arlen are both present and both defensive",
        player_input="With both Mitch and Arlen here, I lay out everything and ask each of them to answer for their part in this",
        player_location="Town Square",
        npc_locations={"Mitch": "Town Square", "Town Wizard Arlen": "Town Square"},
        quest_flags={
            "arlen_confronted": True,
            "mitch_confronted": True,
            "serah_revealed_pattern": True,
        },
        turn_summary="Player confronted both Mitch and Arlen simultaneously in the square. Arlen admitted to memory smoothing. Mitch denied direct violence but could not explain his injuries. Neither fully implicated the other, but neither could maintain their full original story.",
        narration_focus="Two people who have been carefully not looking at each other, now forced to look. Arlen's answers are precise; Mitch's are desperate. The silence between their responses is the most telling thing in the scene.",
        blocked_reason="",
        checks=_BASE_CHECKS + ["minimum_length:180"],
        forbidden_patterns=[
            r"(?i)\bthe truth is finally out\b",
            r"(?i)\bthe mystery is solved\b",
            r"(?i)\byou have won\b",
        ],
    ),
    NarrationCase(
        id="NAR-30",
        description="Final resolution: player brokers a difficult compromise between all parties in the square",
        player_input="I argue for a compromise: Mitch gets treatment from Serah, Arlen stops the memory manipulation, and the mayor opens a formal inquiry with full records",
        player_location="Town Square",
        npc_locations={
            "Mitch": "Town Square",
            "Town Wizard Arlen": "Town Square",
            "Mayor Elric": "Town Square",
            "Captain Varr": "Town Square",
        },
        quest_flags={
            "arlen_confronted": True,
            "mitch_confronted": True,
            "serah_revealed_pattern": True,
            "arlen_admitted_memory_magic": True,
            "mitch_identified_as_culprit": True,
        },
        turn_summary="Player proposed a three-part compromise in the public square. After considerable tension, all parties accepted in principle. The resolution is fragile and uncertain, but it holds for now.",
        narration_focus="This is not a triumph. It is a difficult thing agreed to by exhausted people. Arlen does not look relieved; Mitch does not look saved. The mayor looks like a man who knows this is not the end. Hold all of that at once.",
        blocked_reason="",
        checks=_BASE_CHECKS + ["minimum_length:200"],
        forbidden_patterns=[
            r"(?i)\bthe town is safe\b",
            r"(?i)\beveryone cheers\b",
            r"(?i)\bthe case is closed\b",
            r"(?i)\bgame over\b",
        ],
    ),
]


__all__ = ["NarrationCase", "NARRATION_CASES"]