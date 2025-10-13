CREATE SCHEMA story;

-- Authorial outline = intended beats
CREATE TABLE story.outline_beats (
  id           uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  campaign_key text NOT NULL,
  seq          int  NOT NULL,       -- order
  title        text NOT NULL,
  description  text NOT NULL,
  gating_flags text[] DEFAULT '{}', -- e.g., ['has_key_of_thorns']
  UNIQUE (campaign_key, seq)
);

-- Canon “facts” the validator enforces (and that Executors must not contradict)
CREATE TABLE story.facts (
  id           uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  session_id   uuid NOT NULL REFERENCES core.sessions(id) ON DELETE CASCADE,
  key          citext NOT NULL,     -- e.g., 'npc.aldrin.alive'
  value        jsonb  NOT NULL,     -- scalar or structured
  provenance   uuid   REFERENCES core.citations(id),
  UNIQUE (session_id, key)
);

-- Player decisions, normalized and timestamped, linkable to a beat
CREATE TABLE story.decisions (
  id           bigserial PRIMARY KEY,
  session_id   uuid NOT NULL REFERENCES core.sessions(id) ON DELETE CASCADE,
  beat_id      uuid REFERENCES story.outline_beats(id),
  ts           timestamptz NOT NULL DEFAULT now(),
  actor        text NOT NULL,       -- 'player'
  action_key   text NOT NULL,       -- 'accept_quest', 'attack_guard', etc.
  payload      jsonb NOT NULL       -- free-form details (dialogue, item ids)
);

-- Rolling synopsis materialized per session (LLM reads this a lot)
CREATE TABLE story.synopsis_versions (
  id           bigserial PRIMARY KEY,
  session_id   uuid NOT NULL REFERENCES core.sessions(id) ON DELETE CASCADE,
  ts           timestamptz NOT NULL DEFAULT now(),
  summary_md   text NOT NULL,       -- human-readable markdown
  summary_json jsonb NOT NULL       -- machine-usable outline (optional)
);

-- Latest synopsis view for fast access
CREATE VIEW story.synopsis_latest AS
SELECT DISTINCT ON (session_id)
  session_id, id AS synopsis_id, ts, summary_md, summary_json
FROM story.synopsis_versions
ORDER BY session_id, ts DESC;
