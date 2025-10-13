CREATE SCHEMA characters;

-- Character sheet core
CREATE TABLE characters.entities (
  id            uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  session_id    uuid NOT NULL REFERENCES core.sessions(id) ON DELETE CASCADE,
  name          citext NOT NULL,
  kind          text NOT NULL CHECK (kind IN ('pc','npc','monster')),
  level         int,
  class         text,
  race          text,
  alignment     text,
  ac            int,                 -- base AC; dynamic AC via effects possible
  max_hp        int,
  current_hp    int,
  speed         int,
  proficiency_bonus int,
  persona       jsonb,               -- motives, voice, quirks (for Executors)
  UNIQUE (session_id, name)
);

-- Ability scores
CREATE TABLE characters.ability_scores (
  entity_id uuid PRIMARY KEY REFERENCES characters.entities(id) ON DELETE CASCADE,
  str int NOT NULL, dex int NOT NULL, con int NOT NULL,
  int_ int NOT NULL, wis int NOT NULL, cha int NOT NULL
);

-- Skills + proficiencies (store only non-defaults)
CREATE TABLE characters.skills (
  entity_id uuid REFERENCES characters.entities(id) ON DELETE CASCADE,
  skill     text NOT NULL,       -- 'stealth','persuasion'
  rank      text NOT NULL CHECK (rank IN ('none','proficient','expertise')),
  UNIQUE (entity_id, skill)
);

-- Ongoing effects (buffs/debuffs, conditions)
CREATE TABLE characters.effects (
  id          uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  entity_id   uuid NOT NULL REFERENCES characters.entities(id) ON DELETE CASCADE,
  source      text NOT NULL,           -- 'spell:bless','condition:poisoned'
  started_at  timestamptz NOT NULL DEFAULT now(),
  expires_at  timestamptz,
  data        jsonb NOT NULL           -- e.g., {"attack_bonus":1} or {"disadvantage":["ability:wis(check)"]}
);

-- Inventory and equipment
CREATE TABLE characters.items (
  id          uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  name        text NOT NULL,
  type        text NOT NULL,           -- 'weapon','armor','gear','consumable'
  data        jsonb                    -- weapon dice, armor base, etc.
);

CREATE TABLE characters.inventory (
  entity_id   uuid NOT NULL REFERENCES characters.entities(id) ON DELETE CASCADE,
  item_id     uuid NOT NULL REFERENCES characters.items(id),
  qty         int NOT NULL DEFAULT 1,
  equipped    boolean NOT NULL DEFAULT false,
  meta        jsonb,
  PRIMARY KEY (entity_id, item_id)
);
