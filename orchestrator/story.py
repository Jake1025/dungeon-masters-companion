from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, List, Sequence


@dataclass(frozen=True)
class StoryNode:
    """Single story location/person/clue with lightweight connections."""

    key: str
    description: str
    connections: Sequence[str] = field(default_factory=tuple)


DEFAULT_NODES = [
    StoryNode(
        key="Town Square",
        description=(
            "The cobbled heart of the harbor town. Lanterns hang from iron posts, a weathered fountain "
            "burbles at the center, and every major street spills into this crossroads of exhausted townsfolk, "
            "shouting vendors, and passing sailors. Talk of bloodstains and lost sleep hangs under every conversation."
        ),
        connections=(
            "Market Stalls",
            "Temple of the Tide",
            "Town Hall",
            "Harbor Gate",
            "Watch Barracks",
            "Old Well",
            "East Alley",
            "South Bridge",
            "Copper Cup",
            "Town Crier Jessa",
            "Street Performer Jorin",
            "Bronze Fountain Coin",
            "Mitch",
            "Wizard's House",
        ),
    ),
    StoryNode(
        key="Bronze Fountain Coin",
        description=(
            "A battered bronze coin wedged between the stones of the central fountain. Its face is worn smooth "
            "by years of water and fingertips, but faint engraving hints at an older crest."
        ),
        connections=("Town Square",),
    ),
    StoryNode(
        key="Town Crier Jessa",
        description=(
            "Jessa stands atop a low crate in the square, ringing a handbell as she calls out news of "
            "incoming ships, unexplained bloodstains, and the mayor's increasingly desperate decrees."
        ),
        connections=("Town Square", "Town Hall"),
    ),
    StoryNode(
        key="Street Performer Jorin",
        description=(
            "Jorin juggles knives and colored stones for gathered onlookers. Quick with a joke and quicker "
            "with his hands, he hears rumors before most anyone else."
        ),
        connections=("Town Square", "Market Stalls"),
    ),
    StoryNode(
        key="Market Stalls",
        description=(
            "A ring of canvas-topped stalls crowd the edge of the square. Fishmongers, spice sellers, and "
            "tinkers hawk their wares while children weave between crates and baskets."
        ),
        connections=("Town Square", "Harbor Gate", "Old Well", "Fishmonger Talo", "Spice Seller Nima"),
    ),
    StoryNode(
        key="Fishmonger Talo",
        description=(
            "Talo's stall overflows with the day's catch laid over crushed ice. He knows every captain on the "
            "docks and the gossip that rides in with their ships."
        ),
        connections=("Market Stalls", "Docks"),
    ),
    StoryNode(
        key="Spice Seller Nima",
        description=(
            "Nima sells jars of pungent spices and dried peppers from distant ports. Her keen nose and sharper "
            "memory make her a quiet observer of who buys what and why."
        ),
        connections=("Market Stalls", "Copper Cup"),
    ),
    StoryNode(
        key="Temple of the Tide",
        description=(
            "A modest stone temple overlooking the square, its doors carved with waves and storm-clouds. "
            "Inside, candles flicker before a statue of a calm, watchful sea goddess. Many townsfolk come here "
            "seeking answers for the nights they cannot remember."
        ),
        connections=("Town Square", "Cleric Serah", "Old Shrine", "Novice Arel", "Salt-Stained Prayer Beads"),
    ),
    StoryNode(
        key="Cleric Serah",
        description=(
            "Serah, a middle-aged cleric of the sea goddess, tends to sailors and townsfolk alike. "
            "She listens more than she speaks and keeps a careful eye on omens from the harbor—and on the strange "
            "emptiness in the eyes of those who wake up with blood on their doorsteps."
        ),
        connections=("Temple of the Tide", "Old Well", "Salt-Stained Prayer Beads"),
    ),
    StoryNode(
        key="Novice Arel",
        description=(
            "Arel is a young acolyte sweeping stone floors and lighting candles. Nervous but earnest, they "
            "have seen more than Serah realizes and struggle with what to share."
        ),
        connections=("Temple of the Tide", "Old Shrine", "Salt-Stained Prayer Beads"),
    ),
    StoryNode(
        key="Salt-Stained Prayer Beads",
        description=(
            "A loop of smooth wooden beads, crusted with a thin line of salt where they rest against wet robes. "
            "Some of the beads are carved with tiny wave symbols."
        ),
        connections=("Temple of the Tide", "Cleric Serah", "Novice Arel"),
    ),
    StoryNode(
        key="Town Hall",
        description=(
            "A tall, timber-framed hall with a slate roof and creaking signboard. Notices are nailed to a "
            "board outside, and a pair of clerks shuffle papers just inside the main doors. The notice board is "
            "cluttered with reports of nocturnal disturbances and 'unsettling stains' found in private homes."
        ),
        connections=("Town Square", "Mayor Elric", "Watch Barracks", "Scribe Loth", "Weathered Notice"),
    ),
    StoryNode(
        key="Mitch",
        description=(
            "Mitch is a broad-shouldered lumberjack with calloused hands and haunted eyes. He insists he just "
            "wants someone to uncover the truth behind the bloodstains, but his agitation cuts a little too deep."
        ),
        connections=("Town Square", "Lumberyard", "Mayor Elric"),
    ),
    StoryNode(
        key="Lumberyard",
        description=(
            "Stacks of freshly cut logs and the tang of sap fill the air. A small shack nearby shows scuffed "
            "floorboards and a corner where someone scrubbed at dried, dark stains."
        ),
        connections=("Mitch", "Riverside Path"),
    ),
    StoryNode(
        key="Mayor Elric",
        description=(
            "Mayor Elric is a tired man in a well-kept coat, juggling merchants' demands and the growing panic "
            "over unexplained bloodstains. No one has truly gone missing, but he fears the town is fraying and "
            "doesn't know how much longer he can pretend things are under control."
        ),
        connections=("Town Hall", "Town Square", "Mitch", "Town Wizard Arlen"),
    ),
    StoryNode(
        key="Scribe Loth",
        description=(
            "Loth is a meticulous scribe surrounded by inkpots and scrolls. He files complaints, tallies taxes, "
            "and occasionally buries inconvenient paperwork for the right favor."
        ),
        connections=("Town Hall", "Town Square", "Weathered Notice"),
    ),
    StoryNode(
        key="Weathered Notice",
        description=(
            "A curling parchment tacked to the town hall board, ink blurred by rain. It mentions strange lights "
            "near the old well and requests witnesses to report to the mayor's office."
        ),
        connections=("Town Hall", "Town Square", "Old Well"),
    ),
    StoryNode(
        key="Harbor Gate",
        description=(
            "An archway of weathered stone opening toward the piers. Guard posts on either side watch the flow "
            "of carts and sailors between the town and the docks."
        ),
        connections=("Town Square", "Docks", "Watch Barracks", "Market Stalls", "Gate Guard Ren", "Cracked Spyglass"),
    ),
    StoryNode(
        key="Gate Guard Ren",
        description=(
            "Ren leans on his spear at the harbor gate, sizing up everyone who passes. He's seen enough trouble "
            "to be wary, but a kind word or shared drink can loosen his tongue."
        ),
        connections=("Harbor Gate", "Watch Barracks", "Cracked Spyglass"),
    ),
    StoryNode(
        key="Cracked Spyglass",
        description=(
            "A once-fine brass spyglass with a hairline crack across one lens. It smells faintly of salt and oil "
            "and bears tiny etchings matching the town's crest."
        ),
        connections=("Harbor Gate", "Gate Guard Ren", "Docks"),
    ),
    StoryNode(
        key="Docks",
        description=(
            "Wooden piers stretch out over dark water, crowded with fishing boats and the occasional merchant "
            "ship. Ropes creak, gulls wheel overhead, and the smell of tar and brine hangs thick in the air."
        ),
        connections=(
            "Harbor Gate",
            "Warehouse Row",
            "Fishermen's Shacks",
            "Dockmaster Hara",
            "Deckhand Finn",
            "Frayed Mooring Rope",
        ),
    ),
    StoryNode(
        key="Dockmaster Hara",
        description=(
            "Hara keeps a ledger tucked under one arm as she strides up and down the docks. She knows which "
            "ships arrived late, which cargo went missing, and which captains owe favors. She is quietly furious "
            "about the unexplained stains turning up near her warehouses."
        ),
        connections=("Docks", "Warehouse Row"),
    ),
    StoryNode(
        key="Deckhand Finn",
        description=(
            "Finn is a young deckhand with rope-burned hands and boundless curiosity. He listens in on sailor "
            "gossip and can point out trouble brewing on the piers."
        ),
        connections=("Docks", "Fishermen's Shacks", "Frayed Mooring Rope"),
    ),
    StoryNode(
        key="Frayed Mooring Rope",
        description=(
            "A length of mooring rope stained a darker color near one end. Up close, the fibers look as though "
            "they were cut more than worn through by the sea."
        ),
        connections=("Docks", "Deckhand Finn"),
    ),
    StoryNode(
        key="Warehouse Row",
        description=(
            "A line of squat stone warehouses hugs the waterfront. Their heavy doors and barred windows suggest "
            "both valuable cargo and things better kept out of sight. One doorframe bears a faded, rusty smear "
            "that no one can quite explain."
        ),
        connections=("Docks", "Smuggler's Entrance", "Foreman Kesh", "Smugglers' Ledger"),
    ),
    StoryNode(
        key="Foreman Kesh",
        description=(
            "Kesh oversees the loading crews with a barked order and a sharp eye. He insists everything is above "
            "board, but his ledgers don't always match what moves in the night."
        ),
        connections=("Warehouse Row", "Smuggler's Entrance", "Smugglers' Ledger"),
    ),
    StoryNode(
        key="Smuggler's Entrance",
        description=(
            "A half-concealed grate and narrow stone steps leading below the warehouses. The smell of damp and "
            "old river-mud clings to the air here."
        ),
        connections=("Warehouse Row", "Old Well", "Smuggler Lia"),
    ),
    StoryNode(
        key="Smuggler Lia",
        description=(
            "Lia moves quietly through the shadows beneath the warehouses. She trades in information as much as "
            "contraband and always seems to know who's asking too many questions."
        ),
        connections=("Smuggler's Entrance", "Warehouse Row", "Smugglers' Ledger"),
    ),
    StoryNode(
        key="Smugglers' Ledger",
        description=(
            "A slim ledger bound in cracked leather, its pages filled with coded notes about shipments, routes, "
            "and initials. A few entries are smudged with what looks like river-mud."
        ),
        connections=("Warehouse Row", "Smuggler's Entrance", "Smuggler Lia", "Foreman Kesh"),
    ),
    StoryNode(
        key="Old Well",
        description=(
            "An old stone well at the edge of the square, its rope replaced more than once. Locals say its water "
            "never runs dry, and that it connects to forgotten tunnels beneath the town. Faint rust-brown stains "
            "cling to some of the stones as though someone once washed something away here."
        ),
        connections=("Town Square", "Smuggler's Entrance", "Temple of the Tide", "Market Stalls", "Old Tellan"),
    ),
    StoryNode(
        key="Old Tellan",
        description=(
            "Tellan sits on the well's rim spinning stories for anyone who will listen. Some tales are harmless "
            "gossip, others hint at things buried under the town and better left alone. Lately his stories keep "
            "circling back to nights no one quite remembers."
        ),
        connections=("Old Well", "Town Square"),
    ),
    StoryNode(
        key="Watch Barracks",
        description=(
            "A sturdy building flying the town's colors. Racks of spears stand by the door, and off-duty guards "
            "swap stories on the steps when the weather is mild."
        ),
        connections=("Town Square", "Harbor Gate", "Thom", "Captain Varr", "Guard's Lost Signet"),
    ),
    StoryNode(
        key="Captain Varr",
        description=(
            "Captain Varr is a broad-shouldered veteran with a scar along his jaw. He takes the town's safety "
            "personally and has little patience for fools, but respects those who pull their weight."
        ),
        connections=("Watch Barracks", "Harbor Gate", "Guard's Lost Signet"),
    ),
    StoryNode(
        key="Guard's Lost Signet",
        description=(
            "A small silver signet ring bearing the town's crest, scuffed as though it has been dragged along "
            "stone. It looks recently dropped."
        ),
        connections=("Watch Barracks", "Town Square", "Captain Varr"),
    ),
    StoryNode(
        key="East Alley",
        description=(
            "A narrow, shadowed alley slipping between tall buildings. Laundry lines crisscross overhead, and "
            "the back doors of several shops and taverns open onto it. Here and there, someone has scrubbed at "
            "dark stains that refuse to fully fade from the cobbles."
        ),
        connections=(
            "Town Square",
            "Back Door - Copper Cup",
            "Old Shrine",
            "Street Urchin Pip",
            "Fence Caris",
            "Hidden Alley Knife",
        ),
    ),
    StoryNode(
        key="Street Urchin Pip",
        description=(
            "Pip is a sharp-eyed child who knows every shortcut and loose shutter in the alleyways. They trade "
            "trinkets and rumors in exchange for coin, food, or kindness."
        ),
        connections=("East Alley", "Town Square"),
    ),
    StoryNode(
        key="Fence Caris",
        description=(
            "Caris leans in the shadows near a back door, dealing in small stolen goods and no questions asked. "
            "She prefers to stay out of sight when guards are near."
        ),
        connections=("East Alley", "Back Door - Copper Cup", "Hidden Alley Knife"),
    ),
    StoryNode(
        key="Hidden Alley Knife",
        description=(
            "A narrow-bladed knife tucked behind a loose brick at knee height. Its handle is wrapped in worn "
            "blue cloth, and a faint rust stain darkens the edge."
        ),
        connections=("East Alley", "Fence Caris"),
    ),
    StoryNode(
        key="Back Door - Copper Cup",
        description=(
            "A plain wooden door at the rear of the Copper Cup, used by staff and late-night regulars. Crates "
            "and empty barrels stack nearby, and the smell of stew drifts out when it opens. A faint dark streak "
            "runs along one stone, as if something was once dragged past in a hurry."
        ),
        connections=("East Alley", "Copper Cup", "Storeroom Door", "Cook Brenna"),
    ),
    StoryNode(
        key="Cook Brenna",
        description=(
            "Brenna is the Copper Cup's harried cook, always juggling pots and shouting orders through the "
            "kitchen door. She hears everything that happens near the back rooms."
        ),
        connections=("Back Door - Copper Cup", "Copper Cup"),
    ),
    StoryNode(
        key="Old Shrine",
        description=(
            "A crumbling wayside shrine tucked into a bend of the alley, its carvings worn by sea-wind and "
            "salt. Offerings of shells and coins gather in a shallow stone bowl."
        ),
        connections=("East Alley", "Temple of the Tide", "Caretaker Ilya", "Carved Driftwood Charm"),
    ),
    StoryNode(
        key="Caretaker Ilya",
        description=(
            "Ilya quietly cleans the old shrine and replaces wilted offerings. She claims to have seen strange "
            "lights near the well on stormy nights."
        ),
        connections=("Old Shrine", "Temple of the Tide", "Carved Driftwood Charm"),
    ),
    StoryNode(
        key="Carved Driftwood Charm",
        description=(
            "A piece of pale driftwood carved into the shape of a curling wave, hung on a faded blue cord. It "
            "smells faintly of incense and sea-salt."
        ),
        connections=("Old Shrine", "Temple of the Tide"),
    ),
    StoryNode(
        key="South Bridge",
        description=(
            "A low stone bridge arching over a narrow river that feeds the harbor. Lanterns line the parapet, "
            "and you can see both the town walls and the distant open sea from its center. More than one passerby "
            "has reported waking here with aching feet and no memory of how they arrived."
        ),
        connections=("Town Square", "Riverside Path", "Bridge Watcher Sol"),
    ),
    StoryNode(
        key="Bridge Watcher Sol",
        description=(
            "Sol leans on the bridge railing during most evening watches, counting lanterns and noting who "
            "comes and goes along the river path."
        ),
        connections=("South Bridge", "Riverside Path"),
    ),
    StoryNode(
        key="Riverside Path",
        description=(
            "A muddy path following the riverbank toward the outskirts. Reeds whisper in the breeze, and "
            "shallow boats are pulled up onto the shore."
        ),
        connections=("South Bridge", "Fishermen's Shacks", "Boatman Jaro"),
    ),
    StoryNode(
        key="Boatman Jaro",
        description=(
            "Jaro tends a small skiff tied to a worn post. For the right price, he'll ferry people quietly "
            "along the river—or look the other way when others do."
        ),
        connections=("Riverside Path", "Fishermen's Shacks"),
    ),
    StoryNode(
        key="Fishermen's Shacks",
        description=(
            "A cluster of small wooden shacks perched on pilings above the river. Nets hang to dry, and "
            "lantern-light spills from half-open doors late into the night. In more than one doorway, dark stains "
            "mar the floorboards with no memory of how they appeared."
        ),
        connections=("Riverside Path", "Docks", "Fisher Rian", "Fisher Mira"),
    ),
    StoryNode(
        key="Fisher Rian",
        description=(
            "Rian mends nets on an upturned crate outside his shack, grumbling about changing tides and strange "
            "catches pulled from deeper waters."
        ),
        connections=("Fishermen's Shacks", "Docks"),
    ),
    StoryNode(
        key="Fisher Mira",
        description=(
            "Mira cleans fish with quick, practiced motions, humming an old sea-song under her breath. She "
            "keeps an eye on the river for signs of storms or trouble, and she is one of the few who admits she "
            "sometimes wakes up with her boots wet and no memory of why."
        ),
        connections=("Fishermen's Shacks", "Riverside Path"),
    ),
    StoryNode(
        key="Wizard's House",
        description=(
            "A tall stone house with shuttered windows and a heavy iron fence, set just off the square. Lanterns "
            "burn late behind the curtains, and a pair of hired guards discourage casual callers."
        ),
        connections=("Town Square", "Town Wizard Arlen", "Watch Barracks"),
    ),
    StoryNode(
        key="Town Wizard Arlen",
        description=(
            "Arlen is a reclusive wizard who seldom leaves his guarded home. Whispers say he can pluck souls back "
            "from the brink and smooth away memories like ink from parchment."
        ),
        connections=("Wizard's House", "Mayor Elric"),
    ),
    StoryNode(
        key="Copper Cup",
        description=(
            "A low-beamed harbor tavern. Lanterns swing above crowded tables, and the air smells of "
            "stew, sea-salt, and woodsmoke. The barkeep Mara watches everything from behind the counter."
        ),
        connections=("Bar Counter", "Mara", "Brin", "Edda", "Thom", "Lysa", "Stair Landing"),
    ),
    StoryNode(
        key="Bar Counter",
        description="Shelves of bottles, a till, and crates tucked beneath. A loose crate hides something wedged behind it.",
        connections=("Mara", "Hidden Scrap", "Copper Cup"),
    ),
    StoryNode(
        key="Mara",
        description="The proprietor. Married to Brin. Her wedding anniversary is April 15th. Brisk, perceptive, and inclined to help if treated respectfully.",
        connections=("Bar Counter", "Hidden Scrap", "Storeroom Door", "Brin"),
    ),
    StoryNode(
        key="Brin",
        description="Mara's husband. A weather-beaten sailor with a limp. Forgetful of his wedding anniversary date.",
        connections=("Copper Cup", "Stair Landing", "Storeroom Door", "Mara"),
    ),
    StoryNode(
        key="Edda",
        description="A scholar cataloging tavern legends, forever scribbling into a leather folio.",
        connections=("Copper Cup", "Hidden Scrap", "Storeroom Door"),
    ),
    StoryNode(
        key="Thom",
        description="An off-duty guard who prefers order and dislikes surprises upstairs.",
        connections=("Copper Cup", "Stair Landing", "Storeroom Door"),
    ),
    StoryNode(
        key="Lysa",
        description="A traveling bard tuning a battered lute, eager for new tales.",
        connections=("Copper Cup", "Hidden Scrap", "Storeroom Door"),
    ),
    StoryNode(
        key="Hidden Scrap",
        description="A grease-stained note tucked behind a loose crate: 'cellar restock / upstairs lock is our wedding anniversary date'.",
        connections=("Bar Counter", "Storeroom Door", "Mara", "Brin"),
    ),
    StoryNode(
        key="Stair Landing",
        description="A narrow staircase creaks toward the upper rooms. A rope discourages casual wanderers.",
        connections=("Copper Cup", "Thom", "Storeroom Door"),
    ),
    StoryNode(
        key="Storeroom Door",
        description="A stout oak door with a brass four-dial combination lock. The correct code is 0415.",
        connections=("Hidden Scrap", "Mara", "Stair Landing"),
    ),
]


DEFAULT_START_KEYS = [
    "Town Square",
    "Market Stalls",
    "Temple of the Tide",
    "Town Hall",
    "Harbor Gate",
    "Copper Cup",
    "Bar Counter",
    "Mara",
    "Brin",
    "Edda",
    "Thom",
    "Lysa",
    "Stair Landing",
]

STARTING_STATE = (
    "Dusk settles over the harbor town as you stand in the middle of its cobbled square. Lanterns flicker to "
    "life one by one, and the people moving between the Temple of the Tide, the town hall, and the Copper Cup "
    "all wear the same drawn, sleepless look. In hushed tones they talk about bloodstains found in houses all "
    "over town, nights they cannot remember, and the town wizard who never seems to leave his guarded home." 
    "You've heard strange rumors about this town, about murderous stains with no missing bodies."
)

BEAT_LIST = [
    "Introduce the town square at dusk, the weary mood of the townsfolk, and rumors of unexplained bloodstains with no missing bodies. Let the player explore until they learn enough about the mystery to proceed with an investigation.",
    "Once the player encounters Mitch, the anxious lumberjack, he will plead with the newly arrived player in the square to investigate the bloodstains. Mitch will suggest that the Wizard is involved, but very dangerous.",
    "Let the player freely investigate houses and locations around town to gather clues about the bloodstains, memory gaps, and the reclusive town wizard.",
    "When the player has gathered enough information to have a theory the wizard will speak with them directly with Mitch in attendance. The wizard will reveal that Mitch is the killer and each night he erases everyones memory and undoes his crimes. Mitch is driven to madness by the revelation and begs the player to kill the Wizard. The Wizard asks the player to put Mitch out of his misery.",
    "The player can decide to handle the situation however they see fit, including killing either Mitch or the Wizard, trying to convince Mitch to stop, or finding another solution entirely.",
]


class StoryGraph:
    """Minimal lookup/describe helper for story nodes."""

    _ALIASES = {
        "bar": "Copper Cup",
        "tavern": "Copper Cup",
    }

    def __init__(
        self,
        nodes: Iterable[StoryNode] | None = None,
        initial_keys: Sequence[str] | None = None,
    ) -> None:
        self.nodes: List[StoryNode] = list(nodes or DEFAULT_NODES)
        self.by_key = {node.key: node for node in self.nodes}
        defaults = initial_keys or DEFAULT_START_KEYS
        self.initial_keys = [key for key in defaults if key in self.by_key]
        if not self.initial_keys:
            self.initial_keys = list(self.by_key.keys())

    def describe(self, keys: Sequence[str]) -> str:
        lines = []
        for key in keys:
            node = self.by_key.get(key)
            if not node:
                continue
            lines.append(f"{key}: {node.description}")
        return "\n".join(lines)

    def list_connections(self, keys: Sequence[str]) -> str:
        lines = []
        for key in keys:
            node = self.by_key.get(key)
            if not node or not node.connections:
                continue
            connections = ", ".join(node.connections)
            lines.append(f"{key} -> {connections}")
        return "\n".join(lines)

    def get_node(self, key: str) -> StoryNode | None:
        return self.by_key.get(key)

    def resolve_alias(self, token: str) -> str | None:
        """Return the canonical node key for a known alias, if present."""
        return self._ALIASES.get(token)

    def upsert_node(self, node: StoryNode) -> StoryNode:
        """
        Add a node to the graph or merge new connections/description into an existing one.
        Connections are stored symmetrically but the caller should ensure reciprocity.
        """
        existing = self.by_key.get(node.key)
        if existing:
            merged_connections = sorted(set(existing.connections) | set(node.connections))
            description = node.description or existing.description
            merged = StoryNode(key=existing.key, description=description, connections=tuple(merged_connections))
            for idx, current in enumerate(self.nodes):
                if current.key == node.key:
                    self.nodes[idx] = merged
                    break
        else:
            merged = StoryNode(key=node.key, description=node.description, connections=tuple(node.connections))
            self.nodes.append(merged)

        self.by_key[node.key] = merged
        return merged

    def upsert_nodes(self, nodes: Iterable[StoryNode]) -> List[StoryNode]:
        merged: List[StoryNode] = []
        for node in nodes:
            merged.append(self.upsert_node(node))
        return merged


__all__ = ["StoryGraph", "StoryNode", "DEFAULT_START_KEYS", "STARTING_STATE", "BEAT_LIST"]
