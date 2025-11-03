-- seed_filler_session_and_char.sql
BEGIN;

-- 1) Create a test session
WITH sess AS (
  INSERT INTO core.sessions (name, campaign_key, author_config)
  VALUES ('Filler Playtest', 'demo-one-shot', '{"house_rules":{}}'::jsonb)
  RETURNING id AS session_id
),

-- 2) Create a single PC entity
pc AS (
  INSERT INTO characters.entities
    (session_id, name, kind, level, class, race, alignment,
     ac, max_hp, current_hp, speed, proficiency_bonus, persona)
  SELECT session_id,
         'Test Hero'::citext, 'pc', 3, 'Fighter', 'Human', 'NG',
         16, 27, 27, 30, 2,
         '{"voice":"confident","quirks":["taps pommel when thinking"]}'::jsonb
  FROM sess
  RETURNING id AS entity_id, session_id
),

-- 3) Ability scores
abil AS (
  INSERT INTO characters.ability_scores (entity_id, str, dex, con, int_, wis, cha)
  SELECT entity_id, 16, 14, 14, 10, 12, 10 FROM pc
  RETURNING entity_id
),

-- 4) A couple of catalog items (simple demo values)
sword AS (
  INSERT INTO characters.items (name, type, data)
  VALUES ('Greatsword','weapon','{"damage":"2d6","type":"slashing","properties":["heavy","two-handed"]}')
  RETURNING id AS item_id
),
armor AS (
  INSERT INTO characters.items (name, type, data)
  VALUES ('Shield','armor','{"base_ac_bonus":2,"slot":"off-hand"}')
  RETURNING id AS item_id
),

-- 5) Put items into inventory (equip shield by default)
inv1 AS (
  INSERT INTO characters.inventory (entity_id, item_id, qty, equipped)
  SELECT (SELECT entity_id FROM pc), (SELECT item_id FROM sword), 1, false
  RETURNING entity_id
),
inv2 AS (
  INSERT INTO characters.inventory (entity_id, item_id, qty, equipped)
  SELECT (SELECT entity_id FROM pc), (SELECT item_id FROM armor), 1, true
  RETURNING entity_id
)

-- 6) Output the identifiers you’ll need for MCP calls
SELECT
  (SELECT session_id FROM pc)    AS session_id,
  (SELECT entity_id  FROM pc)    AS entity_id,
  'Test Hero'::text              AS name;

COMMIT;
