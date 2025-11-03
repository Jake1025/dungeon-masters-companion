# mcp_data_server_characters.py
import os
import json
import datetime
import psycopg
import psycopg.rows  # needed for dict_row
from typing import Any, Dict, Optional, Union
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict
from mcp.server.fastmcp import FastMCP

PG_DSN = os.getenv("PG_DSN", "postgresql://postgres:postgres@localhost:5432/dmai")

# ---------- Helpers ----------

def _ok(data: Any) -> Dict[str, Any]:
    return {
        "_v": "1",
        "ok": True,
        "data": data,
        "meta": {"source": "postgres", "ts": datetime.datetime.utcnow().isoformat() + "Z"},
    }

def _err(code: str, msg: str) -> Dict[str, Any]:
    return {"_v": "1", "ok": False, "error": {"code": code, "msg": msg}}

def _conn():
    return psycopg.connect(PG_DSN, autocommit=True, row_factory=psycopg.rows.dict_row)

def _ensure_audit_table(cur) -> None:
    """
    Compatibility-only: ensure the 'core' schema exists and that audit_log has a request_id column.
    Do NOT reshape columns like 'kind', 'actor', etc., to avoid fighting an existing stricter schema.
    """
    cur.execute("CREATE SCHEMA IF NOT EXISTS core;")
    # If the table doesn't exist at all, create it with the schema you already use.
    cur.execute("""
    DO $$
    BEGIN
      IF NOT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema='core' AND table_name='audit_log'
      ) THEN
        CREATE TABLE core.audit_log (
          id BIGSERIAL PRIMARY KEY,
          ts timestamptz NOT NULL DEFAULT now(),
          session_id uuid NOT NULL REFERENCES core.sessions(id) ON DELETE CASCADE,
          actor text NOT NULL CHECK (actor IN ('player','planner','validator','executor','tool')),
          kind text NOT NULL,
          input jsonb,
          output jsonb,
          request_id uuid UNIQUE
        );
      END IF;
    END $$;
    """)
    # Ensure request_id column exists (older tables might lack it)
    cur.execute("""
      DO $$
      BEGIN
        IF NOT EXISTS (
          SELECT 1 FROM information_schema.columns
          WHERE table_schema='core' AND table_name='audit_log' AND column_name='request_id'
        ) THEN
          ALTER TABLE core.audit_log ADD COLUMN request_id uuid UNIQUE;
        END IF;
      END $$;
    """)

# ---------- I/O Models ----------

class GetEntityIn(BaseModel):
    session_id: UUID
    name: str

class Envelope(BaseModel):
    _v: str
    ok: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None
    meta: Optional[Dict[str, Any]] = None

class ListEntitiesIn(BaseModel):
    session_id: UUID

class EntitySummary(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    id: str
    name: str
    kind: str
    level: Optional[int] = None
    class_: Optional[str] = Field(default=None, validation_alias="class")
    race: Optional[str] = None

class SetEquippedIn(BaseModel):
    # Accept UUID or str; we cast in SQL as ::uuid
    session_id: Union[UUID, str]
    entity_id: Union[UUID, str]
    item_name: str
    equipped: bool
    request_id: Union[UUID, str]
    audit_log: Optional[Dict[str, Any]] = None  # optional metadata

# ---------- MCP Server ----------

mcp = FastMCP("dm-data.characters.v1")

@mcp.tool()
def characters_list_entities(input: ListEntitiesIn) -> Envelope:
    q = """
    SELECT
      id::text AS id,
      name,
      kind,
      level,
      class,
      race
    FROM characters.entities
    WHERE session_id = %s::uuid
    ORDER BY kind, name;
    """
    with _conn() as cx, cx.cursor() as cur:
        cur.execute(q, (str(input.session_id),))
        rows = cur.fetchall() or []
    entities = [EntitySummary(**row).model_dump(by_alias=False) for row in rows]
    return Envelope(_v="1", ok=True, data={"entities": entities}, meta={"source": "postgres"})

@mcp.tool()
def characters_get_entity(input: GetEntityIn) -> Envelope:
    q = """
WITH ent AS (
  SELECT e.*
  FROM characters.entities e
  WHERE e.session_id = %s::uuid AND e.name = %s
),
abil AS (
  SELECT a.* FROM characters.ability_scores a
  JOIN ent ON ent.id = a.entity_id
),
sk AS (
  SELECT jsonb_agg(jsonb_build_object('skill', s.skill, 'rank', s.rank)) AS skills
  FROM characters.skills s JOIN ent ON ent.id = s.entity_id
),
eff AS (
  SELECT jsonb_agg(jsonb_build_object(
      'source', ef.source,
      'started_at', ef.started_at,
      'expires_at', ef.expires_at,
      'data', ef.data
  )) AS effects
  FROM characters.effects ef JOIN ent ON ent.id = ef.entity_id
),
eq AS (
  SELECT jsonb_agg(jsonb_build_object(
      'name', i.name,
      'type', i.type,
      'qty', inv.qty,
      'equipped', inv.equipped,
      'data', i.data
  )) AS equipment
  FROM characters.inventory inv
  JOIN characters.items i ON i.id = inv.item_id
  JOIN ent ON ent.id = inv.entity_id
),
eff_ac AS (
  SELECT e.id AS entity_id,
         e.ac + COALESCE((
            SELECT SUM((ef.data->>'ac_bonus')::int)
            FROM characters.effects ef
            WHERE ef.entity_id = e.id
              AND (ef.expires_at IS NULL OR ef.expires_at > now())
         ),0) AS effective_ac
  FROM ent e
)
SELECT
  to_jsonb(ent.*)                             AS entity,
  jsonb_build_object(
    'str', abil.str, 'dex', abil.dex, 'con', abil.con,
    'int', abil.int_, 'wis', abil.wis, 'cha', abil.cha
  )                                           AS ability_scores,
  COALESCE(sk.skills, '[]'::jsonb)            AS skills,
  COALESCE(eff.effects, '[]'::jsonb)          AS effects,
  COALESCE(eq.equipment, '[]'::jsonb)         AS equipment,
  jsonb_build_object('effective_ac', eff_ac.effective_ac) AS derived
FROM ent
JOIN abil   ON true
LEFT JOIN sk      ON true
LEFT JOIN eff     ON true
LEFT JOIN eq      ON true
JOIN eff_ac ON true;
"""
    with _conn() as cx, cx.cursor() as cur:
        cur.execute(q, (str(input.session_id), input.name))
        row = cur.fetchone()
        if not row:
            return Envelope(**_err("NOT_FOUND", "entity not found"))
        return Envelope(**_ok(row))

@mcp.tool()
def characters_set_equipped(input: SetEquippedIn) -> Envelope:
    """
    Toggle equipped state for a named item in an entity's inventory.
    Idempotent via request_id using core.audit_log (your existing schema).
    """
    upd = """
    WITH ent AS (
      SELECT e.id
      FROM characters.entities e
      WHERE e.id = %s::uuid AND e.session_id = %s::uuid
    ), itm AS (
      SELECT i.id FROM characters.items i WHERE i.name = %s
    ), inv AS (
      SELECT inv.entity_id, inv.item_id, inv.qty, inv.equipped
      FROM characters.inventory inv
      JOIN ent ON ent.id = inv.entity_id
      JOIN itm ON itm.id = inv.item_id
    ), ensure AS (
      SELECT
        (SELECT id FROM ent)       AS entity_id,
        (SELECT id FROM itm)       AS item_id,
        (SELECT qty FROM inv)      AS qty,
        (SELECT equipped FROM inv) AS was_equipped
    ), precheck AS (
      SELECT CASE
          WHEN (SELECT entity_id FROM ensure) IS NULL THEN 'NO_ENTITY'
          WHEN (SELECT item_id   FROM ensure) IS NULL THEN 'NO_ITEM'
          WHEN (SELECT qty       FROM ensure) IS NULL THEN 'NO_INVENTORY'
          ELSE NULL
        END AS err
    ), change AS (
      UPDATE characters.inventory inv
      SET equipped = %s
      FROM ensure e
      WHERE inv.entity_id = e.entity_id AND inv.item_id = e.item_id
      RETURNING inv.entity_id, inv.item_id, inv.qty, inv.equipped
    )
    SELECT
      (SELECT err FROM precheck)            AS err,
      (SELECT was_equipped FROM ensure)     AS was_equipped,
      (SELECT equipped FROM change LIMIT 1) AS now_equipped;
    """

    with _conn() as cx, cx.cursor() as cur:
        cur.execute("BEGIN;")
        try:
            _ensure_audit_table(cur)

            # Idempotency: request_id unique (if provided)
            cur.execute("SELECT 1 FROM core.audit_log WHERE request_id = %s::uuid;", (str(input.request_id),))
            if cur.fetchone():
                cur.execute("ROLLBACK;")
                return Envelope(_v="1", ok=True, data={"duplicate": True}, meta={"note": "idempotent replay"})

            # Perform change
            cur.execute(
                upd,
                (str(input.entity_id), str(input.session_id), input.item_name, input.equipped)
            )
            row = cur.fetchone()
            if not row:
                cur.execute("ROLLBACK;")
                return Envelope(**_err("UNEXPECTED", "no result from update"))

            if row["err"]:
                cur.execute("ROLLBACK;")
                code = row["err"]
                msg = {
                    "NO_ENTITY": "entity not found in session",
                    "NO_ITEM": "item not found by name",
                    "NO_INVENTORY": "item not in entity inventory",
                }.get(code, "unknown error")
                return Envelope(**_err(code, msg))

            # Audit insert for your schema (session_id, actor, kind, input, request_id)
            cur.execute(
                "INSERT INTO core.audit_log (session_id, actor, kind, input, request_id) "
                "VALUES (%s::uuid, %s, %s, %s::jsonb, %s::uuid)",
                (
                    str(input.session_id),
                    "tool",  # matches CHECK constraint on actor
                    "characters.set_equipped",
                    json.dumps(input.model_dump()),
                    str(input.request_id),
                )
            )

            cur.execute("COMMIT;")
            return Envelope(
                _v="1",
                ok=True,
                data={
                    "item_name": input.item_name,
                    "equipped": input.equipped,
                    "was_equipped": row["was_equipped"],
                    "now_equipped": row["now_equipped"],
                },
                meta={"source": "postgres"},
            )
        except Exception as ex:
            cur.execute("ROLLBACK;")
            return Envelope(**_err("EXCEPTION", str(ex)))

# ---------- Entrypoint ----------

if __name__ == "__main__":
    print("Characters MCP server (Postgres) on stdio…")
    mcp.run()
