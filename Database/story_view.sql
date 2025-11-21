CREATE OR REPLACE VIEW story.neighbors AS
SELECT e.campaign_id,
       e.src_node_id AS node_id,
       e.dst_node_id AS neighbor_id,
       e.kind, e.label
FROM story.edges e
UNION ALL
SELECT e.campaign_id,
       e.dst_node_id AS node_id,
       e.src_node_id AS neighbor_id,
       e.kind, e.label
FROM story.edges e;

-- Query by campaign key + node key:
WITH camp AS (SELECT id FROM story.campaigns WHERE key = $1),
node AS (SELECT id, key, description, attrs
         FROM story.nodes WHERE campaign_id=(SELECT id FROM camp) AND key=$2)
SELECT
  row_to_json(node.*) AS node,
  COALESCE(json_agg(json_build_object(
    'id', n2.id, 'key', n2.key, 'description', n2.description, 'attrs', n2.attrs,
    'kind', nb.kind, 'label', nb.label
  )), '[]'::json) AS neighbors
FROM node
LEFT JOIN story.neighbors nb
  ON nb.campaign_id = (SELECT id FROM camp) AND nb.node_id = node.id
LEFT JOIN story.nodes n2
  ON n2.id = nb.neighbor_id
GROUP BY node.id, node.key, node.description, node.attrs;
