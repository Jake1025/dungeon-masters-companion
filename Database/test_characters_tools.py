# tests/test_characters_tools.py
# UUID-safe pytest for your MCP characters tools.
# - Casts UUIDs to text in SQL (session_id) and str() for ids from tool outputs
# - Includes an idempotency replay check for set_equipped

import os
import uuid

# Point to your local Compose Postgres unless PG_DSN is already set
os.environ.setdefault("PG_DSN", "postgresql://postgres:postgres@localhost:5432/dmai")
PG_DSN = os.environ["PG_DSN"]

# Import tools from your server module.
# Adjust the import below if your file/module name differs.
try:
    # Preferred path if your repo keeps it under Database/
    from Database.mcp_data_server_characters import (
        characters_list_entities,
        characters_get_entity,
        characters_set_equipped,
        ListEntitiesIn,
        GetEntityIn,
        SetEquippedIn,
    )
except ImportError:
    # Fallback if your module is named differently in your environment
    from MCP_data_characters import (
        characters_list_entities,
        characters_get_entity,
        characters_set_equipped,
        ListEntitiesIn,
        GetEntityIn,
        SetEquippedIn,
    )

from psycopg import rows, connect


def _get_session_id_for(name: str = "Test Hero") -> str:
    """
    Fetch a session_id (as text) for the given character name.
    Casting s.id::text ensures we get a Python str instead of a UUID object.
    """
    with connect(PG_DSN, row_factory=rows.dict_row) as cx, cx.cursor() as cur:
        cur.execute(
            """
            SELECT s.id::text AS session_id
            FROM core.sessions s
            JOIN characters.entities e ON e.session_id = s.id
            WHERE e.name = %s
            ORDER BY s.created_at DESC
            LIMIT 1;
            """,
            (name,),
        )
        row = cur.fetchone()
        assert row is not None, f"No session found that contains '{name}'. Seed data missing?"
        return row["session_id"]  # already a str thanks to ::text


def test_list_and_get_roundtrip():
    # --- Discover the session containing Test Hero ---
    sid = _get_session_id_for("Test Hero")
    assert isinstance(sid, str)

    # --- List entities in that session ---
    out = characters_list_entities(ListEntitiesIn(session_id=sid))
    assert out.ok, f"list_entities not ok: {out.error}"
    entities = (out.data or {}).get("entities") or []
    assert entities, "Expected at least one entity in session"

    # Find Test Hero; normalize id to str (tool may return UUID or str)
    hero = next((e for e in entities if e["name"] == "Test Hero"), None)
    assert hero, "Test Hero not found in list_entities output"
    hero_id = str(hero["id"])

    # --- Get full sheet and verify same id ---
    got = characters_get_entity(GetEntityIn(session_id=sid, name="Test Hero"))
    assert got.ok, f"get_entity not ok: {got.error}"
    returned_id = str(got.data["entity"]["id"])
    assert returned_id == hero_id, "Entity id mismatch between list and get"

    # --- Equip mutation (idempotent) ---
    req_id = str(uuid.uuid4())
    res = characters_set_equipped(
        SetEquippedIn(
            session_id=sid,
            entity_id=hero_id,          # ensure string
            item_name="Greatsword",
            equipped=True,
            request_id=req_id,
        )
    )
    assert res.ok, f"set_equipped failed: {res.error}"

    # Replay the same request_id: should be treated as a safe duplicate
    res2 = characters_set_equipped(
        SetEquippedIn(
            session_id=sid,
            entity_id=hero_id,
            item_name="Greatsword",
            equipped=True,
            request_id=req_id,  # same UUID -> idempotent replay
        )
    )
    assert res2.ok, f"idempotent replay failed: {res2.error}"
