# storyMCP.py
import os, datetime, psycopg, psycopg.rows
from typing import Any, Dict
from pydantic import BaseModel
from mcp.server.fastmcp import FastMCP

PG_DSN = os.getenv("PG_DSN", "postgresql://postgres:postgres@localhost:5432/dmai")

def _conn():
    return psycopg.connect(PG_DSN, autocommit=True, row_factory=psycopg.rows.dict_row)

def _ok(data: Any) -> Dict[str, Any]:
    return {"ok": True, "data": data, "meta": {"ts": datetime.datetime.utcnow().isoformat()+"Z", "source":"postgres"}}

def _err(code: str, msg: str) -> Dict[str, Any]:
    return {"ok": False, "error": {"code": code, "msg": msg}}

# ===== Models =====
class GetNodeIn(BaseModel):
    campaign_key: str
    key: str
    directed: bool = False  # optional: only outgoing when True

class NodeKeyIn(BaseModel):
    campaign_key: str
    key: str

class SearchIn(BaseModel):
    campaign_key: str
    query: str
    limit: int = 10

# ===== Server =====
mcp = FastMCP("dm-data.story.v1")

# ---- Tool: node + 1-hop neighbors (undirected by default) ----
@mcp.tool()
def story_get_node(input: GetNodeIn):
    if input.directed:
        q = """
        WITH camp AS (SELECT id FROM story.campaigns WHERE key = %s),
        node AS (
          SELECT id, key, description, attrs
          FROM story.nodes
          WHERE campaign_id = (SELECT id FROM camp) AND key = %s
        ),
        nbrs AS (
          SELECT e.kind, e.label, n2.id, n2.key, n2.description, n2.attrs
          FROM story.edges e
          JOIN story.nodes n2 ON n2.id = e.dst_node_id
          WHERE e.campaign_id = (SELECT id FROM camp)
            AND e.src_node_id = (SELECT id FROM node)
        )
        SELECT
          row_to_json(node.*) AS node,
          COALESCE(json_agg(json_build_object(
            'id', id, 'key', key, 'description', description, 'attrs', attrs,
            'kind', kind, 'label', label
          )), '[]'::json) AS neighbors
        FROM node
        LEFT JOIN nbrs ON true
        GROUP BY node.id, node.key, node.description, node.attrs;
        """
        params = (input.campaign_key, input.key)
    else:
        q = """
        WITH camp AS (SELECT id FROM story.campaigns WHERE key = %s),
        node AS (
          SELECT id, key, description, attrs
          FROM story.nodes
          WHERE campaign_id = (SELECT id FROM camp) AND key = %s
        ),
        nbrs AS (
          SELECT e.kind, e.label, n2.id, n2.key, n2.description, n2.attrs
          FROM story.edges e
          JOIN story.nodes n2 ON n2.id = e.dst_node_id
          WHERE e.campaign_id = (SELECT id FROM camp)
            AND e.src_node_id = (SELECT id FROM node)
          UNION ALL
          SELECT e.kind, e.label, n1.id, n1.key, n1.description, n1.attrs
          FROM story.edges e
          JOIN story.nodes n1 ON n1.id = e.src_node_id
          WHERE e.campaign_id = (SELECT id FROM camp)
            AND e.dst_node_id = (SELECT id FROM node)
        )
        SELECT
          row_to_json(node.*) AS node,
          COALESCE(json_agg(json_build_object(
            'id', id, 'key', key, 'description', description, 'attrs', attrs,
            'kind', kind, 'label', label
          )), '[]'::json) AS neighbors
        FROM node
        LEFT JOIN nbrs ON true
        GROUP BY node.id, node.key, node.description, node.attrs;
        """
        params = (input.campaign_key, input.key)

    with _conn() as cx, cx.cursor() as cur:
        cur.execute(q, params)
        row = cur.fetchone()
        if not row or not row["node"]:
            return _err("NOT_FOUND", "node not found")
        if row["neighbors"] is None:
            row["neighbors"] = []
        # trim long neighbor descriptions to keep model context lean
        for nb in row["neighbors"]:
            desc = nb.get("description")
            if isinstance(desc, str) and len(desc) > 220:
                nb["description"] = desc[:200] + "…"
        return _ok(row)

# ---- Tool: list 1-hop neighbors (undirected), keys + edge meta ----
@mcp.tool()
def story_list_adjacent(input: NodeKeyIn):
    q = """
    WITH camp AS (SELECT id FROM story.campaigns WHERE key = %s)
    SELECT n2.key AS neighbor, e.kind, e.label
    FROM story.edges e
    JOIN story.nodes n1 ON n1.id = e.src_node_id
    JOIN story.nodes n2 ON n2.id = e.dst_node_id
    WHERE e.campaign_id = (SELECT id FROM camp) AND n1.key = %s
    UNION ALL
    SELECT n1.key AS neighbor, e.kind, e.label
    FROM story.edges e
    JOIN story.nodes n1 ON n1.id = e.src_node_id
    JOIN story.nodes n2 ON n2.id = e.dst_node_id
    WHERE e.campaign_id = (SELECT id FROM camp) AND n2.key = %s
    ORDER BY neighbor;
    """
    with _conn() as cx, cx.cursor() as cur:
        cur.execute(q, (input.campaign_key, input.key, input.key))
        neighbors = cur.fetchall() or []
        return _ok({"neighbors": neighbors})

# ---- Tool: search nodes by text (FTS if available; fallback to ILIKE) ----
@mcp.tool()
def story_search(input: SearchIn):
    # prefer full-text index if present
    q_fts = """
    WITH camp AS (SELECT id FROM story.campaigns WHERE key = %s)
    SELECT key, ts_rank(search, websearch_to_tsquery(%s)) AS rank
    FROM story.nodes
    WHERE campaign_id = (SELECT id FROM camp)
      AND search @@ websearch_to_tsquery(%s)
    ORDER BY rank DESC
    LIMIT %s;
    """
    q_like = """
    WITH camp AS (SELECT id FROM story.campaigns WHERE key = %s)
    SELECT key, 0.0 AS rank
    FROM story.nodes
    WHERE campaign_id = (SELECT id FROM camp)
      AND (key ILIKE '%%' || %s || '%%' OR description ILIKE '%%' || %s || '%%')
    ORDER BY key
    LIMIT %s;
    """
    with _conn() as cx, cx.cursor() as cur:
        try:
            cur.execute(q_fts, (input.campaign_key, input.query, input.query, input.limit))
            rows = cur.fetchall() or []
            return _ok({"matches": rows})
        except Exception:
            cur.execute(q_like, (input.campaign_key, input.query, input.query, input.limit))
            rows = cur.fetchall() or []
            return _ok({"matches": rows})

# ---- Tool: get ordered beats for a campaign ----
@mcp.tool()
def story_get_beats(campaign_key: str):
    q = """
    SELECT b.ord, b.text
    FROM story.beats b
    JOIN story.campaigns c ON c.id = b.campaign_id
    WHERE c.key = %s
    ORDER BY b.ord;
    """
    with _conn() as cx, cx.cursor() as cur:
        cur.execute(q, (campaign_key,))
        beats = cur.fetchall() or []
        return _ok({"beats": beats})

# ---- Run server ----
if __name__ == "__main__":
    print("Story MCP server on stdio…")
    mcp.run()
