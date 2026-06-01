### Abstract:

We have created a system of LLM-driven improvisational storytelling based on human authored role playing games (RPGs). We hope to share this system as a proposed high-level structure for other works, and for insight into specific low-level challenges that may arise when crafting such products. Our driving goal is to balance improvisational storytelling rooted in player agency with adherence to the original authorial intent of a given source material. Our system proposes solutions to several conceptual problems associated with LLM storytelling such as: source material grounding, recall of past novel events, world-logic and rule adherence, consistent tool use, and the preservation of player agency in dynamic storytelling systems.

### History: 

Scale is one of the major bottlenecks in interactive media. Take an analogue example that has become synonymous with the genre Choose Your Own Adventure novels. In Edward Packard’s first entry in the eponymous series, The Cave of Time (Edward Packard, 1979), there are 40 possible endings that one can arrive at split roughly evenly among positive and negative outcomes. Packard accomplished this feat within 144 pages of text and 88 decisions by keeping each narrative run fairly short. Packard also employs some clever tactics of branching narratives like recombining a branching decision into a single outcome \[Diamond pattern illustration\], and allowing readers to “jump” across branches with a few decisions.   
![][image1]  
\[IMAGE COURTESY OF Sam Kabo Ashwell [https://heterogenoustasks.wordpress.com/2011/08/05/cyoa-structures-the-cave-of-time/](https://heterogenoustasks.wordpress.com/2011/08/05/cyoa-structures-the-cave-of-time/) \]

Packard is forced to make concessions in terms of length and narrative quality for the sake of his reader’s agency, a stubborn problem that has continued to plague interactive media. The heart of the issue can be expressed mathematically as follows.

In a purely branching narrative the number of possible routes grows multiplicatively with each decision point. If bi represents the number of options at a decision point i, then the total number of possible paths after d decisions is:

N= i=1dbi

Using an approximation based on an average branching factor b we can rewrite this equation:  
N= bd

Finally, we can graph an approximation of Packard’s given an approximate average of 2 decisions per branch. 

![][image2]  
In theory paths rise exponentially; in practice, Packard uses early termination, recombination of pathways, and bridging of branches to keep his endings in a reasonable scope. 

With staggering advances in modern gaming one might conclude that we have invented complex narratological solutions to this issue of scale. In reality, little has changed conceptually in the nearly 50 years passed since its publication. Video games employ similar tactics to mask narratively inconsequential decisions. The budgets and scale of highly dynamic open-world games have ballooned to astronomical proportions \[CITE GTA 5&6\] and often are met with harsh criticism when the edges of their narrative scope are plainly visible \[reference ME3\]. 

A potential solution to this problem actually emerged five years prior to Packard’s first novel, with the first release of Dungeons & Dragons (D\&D) in 1974 by Tactical Studies Rules (TSR). While the terminology, style and ownership has drifted significantly over the years, at its core, D\&D places one person in the seat of Dungeon Master (DM) where they are the captain of the narrative voyage. This can either be through pre-written or entirely improvisational material, the choice is up to the player’s and limited only by the ingenuity of the DM. 

D\&D attempts to solve the explosion of branches by leaving only the scaffolding of choices in place with the responsibility placed on the DM to unfold the specifics at a moment's notice. To ground this practice in some objective reality D\&D offers a set of universal rules and standards that players can adhere to. Common abilities, traits, character compositions, and actions are meant to provide a method of navigation through the story being laid out in front of them. 

If Packard’s novels can be likened to paving every possible road ahead in anticipation of where one may want to go, D\&D is the equivalent of bringing along the paving machine for the ride. 

One could argue that both approaches have wildly successful progeny. In some ways all modern narrative games can trace their lineage to Packard’s style of storytelling. Similarly, D\&D has not only stayed relevant, but has grown tremendously in the public consciousness for over 50 years. However, both have limits. We’ve already covered the drawbacks of Packard’s approach, but in the case of D\&D the limitations aren’t easy to express so succinctly with mathematics. 

D\&D relies entirely on the quality of cooperative storytelling formed between the players and the DM. While both are undeniably crucial to the process, we will focus on the role of the DM. From the head of the table the DM must architect the world the players can interact with to the best of their ability, which as with any creative skill will vary greatly person to person. Top tier dungeon masters are a rare commodity, and similarly expertly written campaign modules are scarce. 

The result is that D\&D has an extremely high logistical bar to reach if you want a high level story. Its also unbelievably difficult to commoditize. Even modern RPGs that draw direct lineage to the D\&D media properties \[Baldur’s Gate 3\] and have done an excellent job at implementing all of the relevant systems, remain very fundamentally rooted in Packard’s approach even with a D\&D veneer.   
A fundamental piece is missing that prevents the true encapsulated recreation of the dynamic storytelling methodology employed in D\&D, the dungeon master. Until it is possible to ship a world class DM with each copy of a campaign, ready to plug in and enjoy, we have not truly solved the problem Packard wrestled with a half century ago. 

### The Solution:

To this end, we propose a system architecture to computationally recreate the effect of putting human intellect at the forefront of an interactive story. By combining the awe-inspiring improvisational ability of Large Language Models (LLMs) with an intelligent context management system we seek to create a storytelling platform that can have a truly dynamic branching narrative with grounding in human authored source material. 

To achieve this goal we needed to architect a system that could effectively unfold a story based on player input while staying grounded in both the source material and the logic of the narrative world. 

We approached this problem with broad usability in mind. So we chose not to train or fine-tune any of the models used in this system. We sought to craft an architecture widely usable across many genres and campaigns. In theory, any tool aware model should be compatible with this system architecture. We designed our implementation to run with locally hosted Ollama served models, as well as Anthropic and OpenAI APIs. 

We chose D\&D not only as inspiration structurally, but as the explicit storytelling framework in this project. We modeled our system loosely off of the Creative Commons license SRD 5.2 from Wizards of the Coast. There are a multitude of reasons for using D\&D as a foundation, it is a well-tested and logically grounded narrative system with widespread adoption, but for our work three key reasons stood out:

First, our source material was created with D\&D as its basis. The campaign we tested was a bespoke “homebrew” campaign written by project stakeholder Prof. Stephen Mazzeo MFA. This campaign provided us with an opportunity to have an author specifically write material into the data structures we define later on. 

Second, D\&D provides an excellent grounding of world-logic in deterministic systems. This allowed us to use common character ability structures as the basis for our non-player character (NPC) and player classes. 

Finally, the semantics of D\&D are widely published, which allows us to conveniently use terminology like "Dungeon Master” in system prompts to convey instructions to the LLM. This is a major area of concern and in some ways violates our principle of adaptability, but it points out a limitation of LLMs for highly specific use cases where terminology might not already be well learned during model pre-training.   
As mentioned, we created several data structures for holding story information that were appropriate for our RPG setting. These structures covered NPC skills, backstories, dynamic memory, location descriptions, adjacency, and player character information. Our data structures, and consequently our tools are built around RPG and some specific D\&D logic. However, this is not to say that they have to be. As you will hopefully come to see, we believe this system can easily be redesigned to support many story structures with the broad-strokes of the system still-in place. Our application and source material do influence the specifics of our implementation, but the idea is far-reaching. 

Our pipeline for generating turn-responses went through many iterations. It started as a series of cascading one-shot prompts, but has since evolved into a multi-stage agent orchestration system to preserve LLM reasoning capabilities while maintaining a general thought-process guidance. Our structure has proven effective for this system of RPG storytelling and context management, but many other structures of reasoning are plausible. The reasoning pipeline built should be a reflection of context management systems, and consequently the underlying storytelling framework. For example, this system reworked to a video-game style of storytelling would require different specific processes and pipelines, though the same general structure would likely be applicable.

The result is a prototype system built around human authored source material that can consistently helm a short RPG campaign in a text-based chat. The system can dynamically unfold narrative branches while maintaining a general guide for major events. The system can recall previous player events, check narrative coherence, and stay grounded in a mutable but logical world state. Players can take action in line with conventional D\&D dice-roll mechanics such as skill checks. The system has been evaluated with a wide range of models served both locally and over common inference APIs. Our suite of models tested for this effort were GPT OSS 20B, Llama 3.1 70B, Gemma 4 31B, Claude Haiku/Sonnet/Opus, as well as GPT 5.5/4. \[TBD\]

The following sections describe our implemented version of this architecture. We begin with the system as a whole, then review the data structures that hold our source material, our LLM tools that constrain model behavior, the turn-processing pipeline, the provider layer, the interface, and finally the benchmarks we used to evaluate model behavior. 

### System Architecture:

Our system architecture is built around the LLM as our narrative engine, it provides us with the raw horsepower needed to generate new narrative pathways, but on it’s own its directionless. The context management as a way to channel this output in the right direction. Like the wheels on a car we take the erratic force of the linguistic engine and channel it into a useful direction.

At a high level, our system is a text-based interactive narrative engine in which the LLM performs the expressive role of Dungeon Master while the runtime maintains authority over world state. This separation of powers is essential. In an unconstrained LLM storytelling system, the model may be asked to remember the entire story, decide what is possible, narrate the outcome, and silently update its understanding of the world all in one continuous act of generation. That gives the model enormous freedom, but it also invites contradiction. A model left to its own devices will inevitably invent plot detail, forget past events, break the fourth wall, or violate the logical premise of the world. 

Our architecture separates these responsibilities. The pre-written world is represented in structured data, while the current session is represented in mutable runtime state. The model is given tools for reading and altering that state in a governed way. The goal of this separation is to allow the handoff of human authored source material to the LLM without the need to simply pack the context window with an entire story.

To help maintain consistency, a turn is divided into distinct phases of reading, narration, writing, and reconciliation. In early stages we tried more and less structured approaches, both explicitly asking for tool calls, and simply letting the LLM have full reign over all tool selection. We found the best approach was a hybrid where we allow for several agentic reasoning loops each with their own pool of available tools and tuned system prompts. The result is a system in which the LLM still improvises locally, but it does so inside a scaffold that can be inspected and tested.

The central runtime object is StoryEngine. A turn begins when the player submits free-form natural language input. The engine then builds a prompt-ready view of the current world-state: the player's current location, scene description, visible entities and items, visited and discovered locations, current story status, narrative beat context, recent history, and relevant memory. The engine then snapshots the world before model-controlled changes occur. This snapshot is later compared with the post-turn world, allowing the system to distinguish what was merely said from what was actually written into state.

\[Insert system architecture diagram here\]

### World Model Data Structures:

We attempted to find a middle ground between what was most appropriate for both the system’s programmatic access to information and the author's ability to translate source material to logical structures. What we settled on was a lore compendium akin to a wiki page with some grounding in the D\&D structures of ability scores, and a separate narrative progression backbone in the form of a beat list. 

The source material, in this case campaign notes, is translated into a set of structured JSON records that the runtime can load into memory as class structures, inspect, and expose to the LLM through tools and context window management. 

The default campaign, Harbor of Broken Mornings, is stored in JSON files under orchestrator/world\_state/data/world\_model/ in the accompanying code repository. These files divide the campaign into story information, locations, NPCs, and items. Classes inherit from a BaseEntity that defines a basic schema for descriptions and semantic memory, but the inheritance structure allows us to add different parameters for each entity type. For example, a location needs adjacency, where an NPC needs a current location. The World Model itself is also a separate structure that holds out starting information as well as a record of the story beatlist.Treating these as separate structures let us build tools for accessing the pertinent parts of each structure, and efficiently manage the injection of information into the context window during turn processing. 

Our early approaches relied on less structured methods such as RAG with FAISS over large text corpuses and very bare-bones entity classes. While these are certainly viable for simply finding grounding information, they limit our ability to construct deterministic systems in line with the D\&D world. 

There is an important trade off to be aware of, the more articulated a world model is the less flexible it becomes. For instance, if we define doors as a separate entity class with locking abilities, we must be assured that we check each door the player attempts to pass through for this locked state and consequently build systems to handle keys, lockpicking, the durability of doors, alternative routes into rooms. Suddenly, by over-defining one small part of the world model we have increased the resolution of other areas to an unmanageable degree. D\&D offers an alternative, a very loose operate-by-feel approach to most situations with the DM deciding the bar of difficulty by setting a Difficulty Class (DC). The DC is a threshold that a player must roll above to pass a skill check. Players apply skill modifiers to boost their chances of passing a check. The result is a set of 18 skills that are all handled through a unified system of dice rolls and modifiers that act as the base way of constrained interaction with the world. Revisiting our locked door example, a rickety wooden door with a rusty key-lock might fall easily to a barbarian trying to kick it down, while a sturdy metal gate with a complex locking system might need to be breached by an expert locksmith. With this system, D\&D shrinks the problem of world resolution to the impressions of the DM and a simple dice roll. 

Our world model contains:

* 22 locations  
* 31 actors/entities, including the player  
* 19 items

Locations provide the spatial logic of the town. Their adjacency relationships determine where the player can move directly and what locations can plausibly be discovered. Actors provide social and mechanical context: who exists, where they are, how they are described, what skills or stats they have, and what they remember. Items provide clue objects and portable world objects. Story data provides the starting state, starting location, and beat guide.

The system also separates authored source material from mutable session state. The authored world is loaded into WorldModel, while the current session is tracked in GameState. This distinction is important for interactive storytelling because the world must both remain faithful to its source and change in response to play. The author supplies the initial state and constraints. The session records what the player has done within those constraints.

Memory is handled at both the entity and global levels by two separate recall systems. Each entity carries a mutable sentence memory object. This lets memory be retrieved in relation to a specific query based on semantic similarity. NPCs, locations, items, and the player all maintain individual memory records. On the global level we maintain a rolling summary of recent events to keep recent event context coherent.

In the current implementation, these memories are sentence strings searched with lexical top-N matching and recent-memory fallback. This keeps the memory system simple and inspectable.

The data structures are D\&D RPG-shaped because this prototype is. However, the broader pattern does not depend on this exact schema. A political story might replace actors and items with factions and resources. A relationship drama might emphasize relationships, emotional states, and episodes. A survival game might emphasize resources, hazards, and locations. The important principle is that authorial intent is externalized into structured, inspectable material before the model begins improvising.

### 

### LLM Tools:

The tool layer is the primary mechanism by which the system turns an LLM from an unconstrained narrator into a constrained participant in a runtime. In this system, a tool is not merely a convenience function. It is a boundary between model imagination and world authority.

For example, the model may describe the atmosphere of the Copper Cup tavern in its own words. But it should not simply decide that the player is at the Copper Cup unless movement has been validated and written into state. It may infer that a suspicious action calls for a skill check and decide the DC, but the actual roll should be performed by a mechanics tool. We keep deterministic systems and world-state facts handled with code, and let the model improvise and choose in subjective areas. 

Tools are implemented as Python functions under orchestrator/world\_state/ and registered through tool\_registry.py. The registry defines which tools are legal in each phase, dispatches tool calls to the correct handler, normalizes common argument aliases, filters arguments to match the handler signature, and returns structured tool results to the agent loop.

The most important tool families are:

scene tools, for current location context, movement, scene listings, and interaction validation  
entity tools, for object state reads and memory lookup/write  
mechanics tools, for dice rolls, d20-style skill checks, and recent check history  
world model tools, for reading source material, moving items, and materializing newly engaged NPCs or items

turn tools, for phase bookkeeping and terminal finalize calls

The system deliberately separates read tools from write tools. Phase 1 tools are used to inspect the world, validate actions, retrieve memory, and resolve mechanics. Phase 2 tools are used to apply changes. This phase separation addresses a common LLM failure mode: the model deciding what happened, narrating it, and mutating state all at once without any clear point where the decision can be inspected.

The central Phase 1 grounding tool is check\_can\_interact. It determines whether the player can plausibly interact with a target. This may mean checking whether an NPC is in the current scene, whether an item is present or carried, whether a location is adjacent, whether a destination has been visited or discovered, or whether a referenced object is not yet registered. When interaction is possible, the tool also surfaces recent memory from that target so narration can remain continuous.

The most important Phase 2 tools are the write tools. move\_to\_location changes player location. move\_npc changes NPC location. move\_world\_item changes item ownership or placement. write\_memory\_tool stores new sentence memories. create\_npc and create\_item materialize unregistered details when the player directly engages them. These materialization tools are important because they let the model enrich a scene without requiring every descriptive detail to be pre-authored. If the player talks to "the woman behind the bar," the system can convert that phrase into a canonical NPC record rather than losing it as one-turn flavor.

### 

### Pipeline:

The turn-processing pipeline is the part of the system that changed most during development. Early versions relied more heavily on cascading one-shot prompts: one prompt would interpret the player, another would narrate, another might update state. This basic structure was useful, but it did not give the model enough room to reason with tools while still enforcing a consistent process. The current system therefore uses a multi-stage agent orchestration pipeline.

The purpose of the pipeline is not to imitate human thought step by step. It is to separate responsibilities that need different constraints. A model that is deciding whether the player can reach a location should have access to world-state tools. A model writing player-facing narration should not be changing state. A model applying state changes should be constrained to the changes already implied by the narration. These jobs are related, but they should not be identical.

The first phase, Phase 1, is the read and resolve phase. The model receives the current prompt state and a read/mechanics tool set. It can inspect the scene, validate interaction, retrieve off-scene memory, or resolve uncertainty through dice and skill checks. It must eventually call finalize\_turn, producing a turn summary and narration focus. This finalization step gives the narration phase a compact account of what was resolved before prose is written.

The second step is narration. This is the only stage whose output is directly shown to the player. Narration receives the Phase 1 summary, tool trace, current scene context, surfaced memories, and narration focus. It does not receive tools. This restriction is deliberate. The narrator should not be reaching back into the world to invent new state changes while composing prose. It should express the outcome already resolved by Phase 1\.

The third step, Phase 2, is the write phase. Here the model receives the player input, Phase 1 result, narration, and current world context, but it is restricted to write and materialization tools. Its job is to make durable state match the narrated outcome. If the narration says the player entered the Copper Cup, Phase 2 should call move\_to\_location. If the narration shows a meaningful conversation with Mitch, Phase 2 should write memory to the Player and Mitch. If the narration introduces a directly engaged new person, Phase 2 can call create\_npc.

The final step is reconciliation. Reconciliation is a deterministic audit over the before and after state. It computes changes in location, inventory, memories, entities, items, visited/discovered locations, quest flags, and summary state. This gives the system a record of what actually changed. In a conventional LLM chat, continuity is often implied by the transcript. In this system, continuity is written into explicit runtime structures.

### 

### Model Providers:

One of the design goals of this project was broad usability. To that end, the system does not depend on training or fine-tuning a model on the campaign. The story, rules, tools, memory, and state are all external to the model. This means that the system's portability depends less on model weights and more on whether a model can follow instructions and use tools reliably.

The implementation supports this through a provider abstraction. The runtime does not directly depend on the native API shape of Ollama, OpenAI, or Anthropic. Instead, providers translate between each API and a shared internal representation. Each provider receives canonical messages and optional tool definitions, performs the native API call, and returns a normalized response containing text and tool calls.

This is an important architectural point. The LLM is replaceable not because all models are equally capable, but because the system defines a common role for them to play. A model must read prompts, decide when to call tools, produce structured tool arguments, and generate narration. Some models will do this better than others, and the evaluation should measure that difference. But the world model and tool architecture do not have to be rewritten for each provider.

### 

### Interface:

Although the core contribution is architectural, the interface matters because it determines whether the system can be inspected, debugged, and authored in practice. A storytelling system like this cannot be treated as a black box. If the model behaves unexpectedly, the developer needs to know whether the error came from the source data, the prompt state, the tool choice, the tool result, the narration, the write phase, or reconciliation.

The repository therefore exposes the engine through both a command-line interface and a Streamlit application. The CLI is useful for direct play, reproducible debugging, and verbose inspection. It can print phase traces, tool calls, prompts, model outputs, and state changes. This is especially useful when testing whether a model is failing to call a tool, calling the wrong tool, or narrating a change that Phase 2 does not write.

The Streamlit app provides the main interactive experience. It includes a chat-style player interface, provider and model selection, hosted-provider API key fields, story source selection, roll-mode controls, and inspection panels. It also includes world-authoring and world-inspection tools: users can inspect locations, actors, items, memory, turn traces, and world model records. The app can query the live memory store and can edit or replace the current world model.

This interface supports the broader purpose of the project. If authorial intent is represented as structured data, then authors and developers need ways to see and modify that structure. The interface is therefore not only a front-end for play. It is also a debugging and authoring surface for the underlying narrative system.

### 

### Evaluation:

The evaluation for this project is currently a benchmark harness rather than a human-subject playtest. This is an important distinction. A human playtest would measure perceived agency, enjoyment, coherence, and narrative satisfaction. The current benchmark instead measures whether the system's internal control structure is working: whether models call the expected tools, avoid forbidden tools, preserve narration constraints, and write the expected state changes.

This is appropriate for the current stage of the project because many failures in LLM-driven storytelling are not only subjective failures of prose quality. They are procedural failures. A model may write beautiful narration but fail to call the movement tool. It may produce a compelling NPC exchange but forget to write memory. It may ask the player to roll even though the mechanics tool already resolved the roll. It may narrate a successful action that should have been blocked by world topology. These are measurable failures, and they are exactly the failures the benchmark targets.

The benchmark is organized around the same phase structure as the runtime:

Phase 1 benchmarks test read, validation, memory, and mechanics behavior.  
Narration benchmarks test player-facing prose constraints.  
Phase 2 benchmarks test write tools and state mutation.  
Each scenario sets up a controlled world state, runs the relevant phase, records tool traces and outputs, and scores them against an expected answer key. The current scenario set contains 7 Phase 1 cases, 5 narration cases, and 5 Phase 2 cases.

The scoring is deliberately phase-specific. Phase 1 scoring looks at whether expected tools were called, whether unexpected tools were avoided, whether finalize\_turn was called, whether summaries and narration focus contain expected concepts, and whether the model remained within iteration limits. Narration scoring looks at required sections, second-person narration, agency preservation, roll-request avoidance, and scene grounding. Phase 2 scoring looks at expected write tools, finalize\_writes, and concrete before/after state deltas such as player location, discovered locations, item holders, NPC movement, and memory writes.

The final paper should present model results as evidence about tool-grounded orchestration, not as a universal ranking of LLMs. A model that produces better prose but fails to write state may be less useful for this architecture than a model with plainer prose and stronger tool discipline. The most interesting evaluation results will likely be failure-mode comparisons: which models skip tools, which models over-call tools, which models preserve player agency, and which models reliably complete Phase 2 writes.

### 

### References:

- The Cave of Time (Edward Packard, 1979\)  
- (Cave of time analysis article) [https://heterogenoustasks.wordpress.com/2011/08/05/cyoa-structures-the-cave-of-time/](https://heterogenoustasks.wordpress.com/2011/08/05/cyoa-structures-the-cave-of-time/)  
- D\&D SRD 5.2  
- Anthropic and OpenAI APIs  
- 