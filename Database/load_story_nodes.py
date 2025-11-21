# load_story_nodes.py
import os, psycopg, uuid
from psycopg.rows import dict_row
from story_graph import DEFAULT_NODES, BEAT_LIST  # import the file you shared

PG_DSN = os.getenv("PG_DSN", "postgresql://postgres:postgres@localhost:5432/dmai")
CAMPAIGN_KEY = "copper-cup"

with psycopg.connect(PG_DSN, row_factory=dict_row, autocommit=True) as cx, cx.cursor() as cur:
    cur.execute("INSERT INTO story.campaigns (key, title) VALUES (%s,%s) ON CONFLICT (key) DO UPDATE SET title=EXCLUDED.title RETURNING id;",
                (CAMPAIGN_KEY, "The Copper Cup"))
    camp_id = cur.fetchone()["id"]

    # Insert nodes
    name_to_id = {}
    for n in DEFAULT_NODES:
        cur.execute("""INSERT INTO story.nodes (campaign_id, key, description)
                       VALUES (%s,%s,%s)
                       ON CONFLICT (campaign_id, key) DO UPDATE SET description=EXCLUDED.description
                       RETURNING id;""",
                    (camp_id, n.key, n.description))
        name_to_id[n.key] = cur.fetchone()["id"]

    # Insert edges
    for n in DEFAULT_NODES:
        src = name_to_id[n.key]
        for dst_key in n.connections:
            dst = name_to_id.get(dst_key)
            if not dst:
                continue
            cur.execute("""INSERT INTO story.edges (campaign_id, src_node_id, dst_node_id, kind)
                           VALUES (%s,%s,%s,'linked')
                           ON CONFLICT DO NOTHING;""",
                        (camp_id, src, dst))

    # Beats
    for i, text in enumerate(BEAT_LIST, start=1):
        cur.execute("""INSERT INTO story.beats (campaign_id, ord, text)
                       VALUES (%s,%s,%s)
                       ON CONFLICT (campaign_id, ord) DO UPDATE SET text=EXCLUDED.text;""",
                    (camp_id, i, text))

print("Seeded campaign:", CAMP_KEY := CAMPAIGN_KEY)
