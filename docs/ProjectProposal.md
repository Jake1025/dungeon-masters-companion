# The Dungeon Master’s Companion: Structured AI for Narrative Fidelity in Interactive Campaigns

**Stakeholder / Sponsor:**  
Stephen Mazzeo, MFA \- Adjunct Faculty, Screenwriting & Game Design, Drexel University  
[ssm26@drexel.edu](mailto:ssm26@drexel.edu)

## Background:

Interactive narrative systems face a persistent conflict between player agency and authorial intent. In tabletop role playing games (RPGs)  like *Dungeons & Dragons* (D\&D), human Dungeon Masters (DMs) mitigate this tension by using their improvisational ability to allow players to explore while guiding stories toward intended beats. Large language models (LLMs) show promise as improvisational DMs, but they struggle to provide the architectural backbone that a human-guided campaigns often have. Furthermore, LLMs can contradict established facts, or misuse rules; undermining the player experience and eroding trust in AI-driven storytelling.

Prior work has highlighted D\&D as an ideal domain for studying narrative AI because it integrates descriptive worldbuilding, numerical character systems, and procedural mechanics into a single interactive framework. However, existing AI DM efforts have primarily relied on unconstrained model generation or simple retrieval-augmented prompting, both of which lack reliable guardrails for enforcing narrative fidelity.

## Abstract:

This thesis proposes a structured AI architecture for maintaining authorial intent in interactive storytelling, with D\&D as the testbed. The system will leverage Anthropic’s Model Context Protocol (MCP) to expose three complementary classes of resources: (1) qualitative information such as story outlines, descriptive text, and player decisions; (2) quantitative information such as character statistics, inventories, and numeric relationships; and (3) functional tools such as dice rollers, rule calculators, and resource trackers. By compartmentalizing these elements into accessible, queryable MCP servers, models can remain grounded in authoritative facts rather than drifting into improvisation. Story progression will be managed through a Planner \-\> Validator \-\> Executor loop: the Planner proposes next steps, the Validator enforces consistency with narrative facts and rules, and Executors generate dialogue and narration constrained by validated action masks. An ancillary goal of this system is to create a compartmentalized structure that allows components to be logically divided and connected via the MCP transport layer. By leveraging this connection layer we hope to create a model-agnostic system that can be easily adapted to more advanced models for those with access to broader resources. 

## Proposed Solution:

We propose a AI-Dungeon Master (DMAI) system where an LLM is connected to structured narrative and rule resources via the Model Context Protocol (MCP). Authors define the intended outline, NPC sheets, and world descriptions. A Planner \-\> Validator \-\> Executor pipeline then governs play:

* **Planner:** proposes next steps toward the authored outline.  
* **Validator:** checks proposals against canonical story facts, NPC definitions, and simplified mechanics using deterministic calculators.  
* **Executors:** generate NPC dialogue and narration within those boundaries, constrained by action masks.

The focus will be on **single-player, text-only, single-session campaigns** emphasizing social and exploratory play, chosen for feasibility and clarity of evaluation.

# Technical Structure

## Components:

* **StoryDB**: stores narrative outline, facts, and player decisions.  
* **RulesDB**: SQL-backed store of mechanics (spells, conditions, abilities).  
* **CharacterDB**: structured NPC sheets (stats \+ persona).  
* **LocationDB**: textual location descriptions and relationships.  
* **MCP Servers**: expose each DB as resources/tools; include deterministic utilities (dice roller, save DC calculator).  
* **Pipeline**: Planner (LLM) \-\> Validator (DB \+ calculators) \-\> Executors (NPC agents \+ narrator).

## Research Methodology:

### Participants

* N=\~10 single-player participants recruited from local playtest communities.  
* Each participant plays through the same authored single-session campaign.

  ### Quantitative Data

* Rule correctness rate (% of outputs validated correctly).  
* Citation coverage (outputs citing governing facts/rules).  
* Contradiction rate (Validator veto frequency).  
* Arc adherence (MonoBERTa classifier tagging logs vs outline).

  ### Qualitative Data

* Player surveys on perceived agency, coherence, and narrative quality.  
* Blind ratings by external reviewers of character fidelity and story flow.

## Data Analysis:

### Quantitative Analysis

* Compare unconstrained LLM runs to Planner/Validator/Executor runs using paired statistical tests. Ablation studies: LLM-only, \+RAG, \+Validator, \+Validator+Masks.  
  Qualitative Analysis  
* Code transcripts for examples of narrative drift, character contradictions, and rule errors. Thematic analysis of player survey responses.

## References (More to come):

* Callison-Burch, C., et al. “Dungeons and Dragons as a Testbed for Interactive Narrative AI.” (Penn research).  
* Model Context Protocol documentation.  
* Mazzeo, S. single-session D\&D campaigns (primary narrative testbed).

## Team Member Roles:

For this project we believe a division of work amongst a total group size of 2-3 people with the following areas of focus is appropriate:

### AI/ML Developer

* Primary responsibility for MCP tool development and structuring the Rules Database (SRD mechanics, NPC stats, inventories).  
* Contribute to the Planner \-\> Validator \-\> Executor loop, including prompt design and recursive self-revision.  
* Background in AI/ML or NLP would be valuable.

### Software Engineer / Interface Developer

* Develop the chat interface to support single-player campaign play.  
* Implement automated testing pipelines to validate consistency, correctness, and regression during development.  
* Suitable for a student with strong software engineering or full-stack development skills.

### Research Investigator:

* Assist in running playtest sessions to collect transcripts and survey data.  
* Contribute to data analysis (quantitative and qualitative) and to writing the paper/presentation for final submission.  
* This role is flexible: could be filled by a CS, AIML, or research-oriented student interested in evaluation and documentation.

## Project Plan

| Phase | Key Activities | Deliverables | Completion Date |
| ----- | ----- | ----- | ----- |
| **Proposal & Literature Review**  | Finalize proposal, review prior AI+D\&D, narrative AI, MCP docs | Approved proposal, annotated bibliography | Week 0 \- 1 |
| **Structural Planning**  | Define schemas (StoryDB, RulesDB, CharacterDB); design Planner→Validator→Executor loop | System architecture diagrams, initial schemas | Week 2 |
| **Prototype Development**  | Implement MCP servers, calculators, MVP on-shot scene | Prototype demo, draft requirements & design docs | Week 3 \- 7 |
| **Testing**  | Run small playtests with 2–3 participants | Pilot study report, revised prototype | Week 8  |
| **Write-up & Presentation**  | Draft thesis chapters, revise, defend | Final thesis and defense presentation | Week 9 \- 10 |

