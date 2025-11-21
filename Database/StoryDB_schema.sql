-- schema: story
CREATE SCHEMA IF NOT EXISTS story;

-- A campaign (one-shot or multi-session arc)
CREATE TABLE story.campaigns (
  id           uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  key          citext UNIQUE NOT NULL,     -- e.g., 'copper-cup'
  title        text NOT NULL,
  author       text,
  created_at   timestamptz NOT NULL DEFAULT now()
);

-- Nodes are your places/people/clues (your StoryNode)
CREATE TABLE story.nodes (
  id            uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  campaign_id   uuid NOT NULL REFERENCES story.campaigns(id) ON DELETE CASCADE,
  key           citext NOT NULL,           -- 'Copper Cup', 'Mara', 'Hidden Scrap'
  description   text NOT NULL,
  attrs         jsonb NOT NULL DEFAULT '{}'::jsonb,  -- optional metadata, tags, flags
  UNIQUE (campaign_id, key)
);

-- Edges connect nodes (typed & directed)
CREATE TABLE story.edges (
  id            uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  campaign_id   uuid NOT NULL REFERENCES story.campaigns(id) ON DELETE CASCADE,
  src_node_id   uuid NOT NULL REFERENCES story.nodes(id) ON DELETE CASCADE,
  dst_node_id   uuid NOT NULL REFERENCES story.nodes(id) ON DELETE CASCADE,
  kind          text NOT NULL DEFAULT 'linked',  -- 'linked','knows','located_at', etc.
  label         text,                             -- optional display label
  UNIQUE (campaign_id, src_node_id, dst_node_id, kind)
);

-- Beats (authorial intent checklist)
CREATE TABLE story.beats (
  id            uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  campaign_id   uuid NOT NULL REFERENCES story.campaigns(id) ON DELETE CASCADE,
  ord           int NOT NULL,
  text          text NOT NULL,
  UNIQUE (campaign_id, ord)
);

-- Fast search (optional but recommended)
CREATE EXTENSION IF NOT EXISTS pg_trgm;
ALTER TABLE story.nodes ADD COLUMN IF NOT EXISTS search tsvector GENERATED ALWAYS AS (
  to_tsvector('english', coalesce(key,'') || ' ' || coalesce(description,''))
) STORED;
CREATE INDEX IF NOT EXISTS nodes_search_idx ON story.nodes USING GIN (search);
CREATE INDEX IF NOT EXISTS nodes_key_trgm ON story.nodes USING GIN (key gin_trgm_ops);
