CREATE SCHEMA world;

CREATE TABLE world.locations (
  id            uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  session_id    uuid NOT NULL REFERENCES core.sessions(id) ON DELETE CASCADE,
  name          citext NOT NULL,
  description   text NOT NULL,
  tags          text[] DEFAULT '{}',      -- 'town','dungeon','tavern'
  state         jsonb DEFAULT '{}'::jsonb, -- mutable state flags: doors, alarms, etc.
  UNIQUE (session_id, name)
);

-- Graph of connections (for travel options, action masks)
CREATE TABLE world.edges (
  from_id   uuid NOT NULL REFERENCES world.locations(id) ON DELETE CASCADE,
  to_id     uuid NOT NULL REFERENCES world.locations(id) ON DELETE CASCADE,
  kind      text NOT NULL,               -- 'road','secret_passage','portal'
  cost      int,                         -- travel minutes, checks, etc.
  data      jsonb,
  PRIMARY KEY (from_id, to_id)
);

-- Entities currently at a location (for encounter setup)
CREATE TABLE world.occupancy (
  location_id uuid NOT NULL REFERENCES world.locations(id) ON DELETE CASCADE,
  entity_id   uuid NOT NULL REFERENCES characters.entities(id) ON DELETE CASCADE,
  arrived_at  timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (location_id, entity_id)
);
