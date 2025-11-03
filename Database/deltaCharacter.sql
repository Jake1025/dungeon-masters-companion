-- characters.get_entity query (parameter: entity name + session)
WITH ent AS (
  SELECT e.*
  FROM characters.entities e
  WHERE e.session_id = $1 AND e.name = $2
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
         e.ac
         + COALESCE((
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
