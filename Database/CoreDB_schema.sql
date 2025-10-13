-- Enable helpful extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS citext;

CREATE SCHEMA core;

-- One playthrough == one session (even for the same authored module)
CREATE TABLE core.sessions (
  id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  name          citext NOT NULL,
  campaign_key  text   NOT NULL,     -- e.g., 'mazzeo-one-shot-01'
  created_at    timestamptz NOT NULL DEFAULT now(),
  author_config jsonb   NOT NULL     -- knobs: house rules, allowed sources, etc.
);

-- Immutable event log (planner proposals, validator results, tool calls)
CREATE TABLE core.audit_log (
  id           bigserial PRIMARY KEY,
  ts           timestamptz NOT NULL DEFAULT now(),
  session_id   UUID NOT NULL REFERENCES core.sessions(id) ON DELETE CASCADE,
  actor        text NOT NULL CHECK (actor IN ('player','planner','validator','executor','tool')),
  kind         text NOT NULL,  -- 'proposal','validation','narration','rule_lookup','dice_roll', etc.
  input        jsonb,
  output       jsonb
);

-- Content/source attribution (rules, story bible citations)
CREATE TABLE core.citations (
  id           uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  label        text,                 -- short key used in text (e.g., [SRD5.1-ATTACK])
  source_name  text NOT NULL,        -- 'SRD 5.1', 'Author Bible v2'
  source_uri   text,
  license      text,                 -- 'CC-BY-4.0'
  extra        jsonb
);
