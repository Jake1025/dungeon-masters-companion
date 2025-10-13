CREATE SCHEMA rules;

-- Top-level rules organized by key; keep both text and machine-usable JSON
CREATE TABLE rules.entries (
  id          uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  key         citext UNIQUE NOT NULL,  -- 'attack_roll', 'cover_three_quarters'
  title       text NOT NULL,
  text        text NOT NULL,
  data        jsonb,                   -- e.g., {"cover":{"three_quarters":5}}
  citation_id uuid REFERENCES core.citations(id)
);

-- Spells/abilities as structured rows (subset for your one-shot)
CREATE TABLE rules.spells (
  id          uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  name        citext UNIQUE NOT NULL,
  level       int NOT NULL CHECK (level BETWEEN 0 AND 9),
  school      text NOT NULL,
  casting_time text NOT NULL,
  range       text NOT NULL,
  components  text[],
  duration    text NOT NULL,
  classes     text[],
  text        text NOT NULL,
  data        jsonb                    -- save type, damage dice, conditions, etc.
);

-- Conditions, resistances, statuses
CREATE TABLE rules.conditions (
  id          uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  name        citext UNIQUE NOT NULL,   -- 'blinded','poisoned'
  text        text NOT NULL,
  data        jsonb                     -- mechanical effects usable by validators
);
