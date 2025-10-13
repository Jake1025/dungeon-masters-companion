------------------------------------
------Example Seed & Queries--------
------------------------------------

-- Create a session
INSERT INTO core.sessions (name, campaign_key, author_config)
VALUES ('Colin - Playtest 01', 'mazzeo-one-shot-01', '{"house_rules":{"crit_damage":"double_dice"}}')
RETURNING id;

-- Insert a canon fact
INSERT INTO story.facts (session_id, key, value)
VALUES ($SESSION, 'npc.aldrin.alive', 'true');

-- Insert a PC and put them in the Tavern
-- (…insert into characters.entities, ability_scores…)
-- (…insert into world.locations(name='Gildermere Tavern')…)
INSERT INTO world.occupancy (location_id, entity_id) VALUES ($LOC_TAVERN, $PC_ID);

-- Query: LLM asks “what’s my current AC?”
SELECT effective_ac FROM characters.current_ac WHERE entity_id = $PC_ID;

-- Query: Validator checks a proposed travel
SELECT 1
FROM world.edges e
JOIN world.locations f ON f.id = e.from_id
JOIN world.locations t ON t.id = e.to_id
WHERE f.name = 'Gildermere Tavern' AND t.name = 'Old Quarry';

------------------------------------
----Example Index and View usage----
------------------------------------


-- Fast fact lookups
CREATE INDEX ON story.facts (session_id, key);

-- Latest synopsis already has a view (story.synopsis_latest)

-- Derived “current state” view: AC with effects applied (simple example)
CREATE VIEW characters.current_ac AS
SELECT e.id AS entity_id,
       e.name,
       e.ac
       + COALESCE( (SELECT SUM( (eff.data->>'ac_bonus')::int )
                    FROM characters.effects eff
                    WHERE eff.entity_id = e.id
                      AND (eff.expires_at IS NULL OR eff.expires_at > now())), 0 ) AS effective_ac
FROM characters.entities e;
