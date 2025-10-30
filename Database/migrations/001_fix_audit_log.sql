CREATE SCHEMA IF NOT EXISTS core;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

DO $$
BEGIN
  -- create table if missing
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema='core' AND table_name='audit_log'
  ) THEN
    CREATE TABLE core.audit_log (
      id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
      request_id uuid UNIQUE,
      at timestamptz NOT NULL DEFAULT now(),
      actor text,
      action text,
      payload jsonb
    );
  ELSE
    -- add request_id if missing
    IF NOT EXISTS (
      SELECT 1 FROM information_schema.columns
      WHERE table_schema='core' AND table_name='audit_log' AND column_name='request_id'
    ) THEN
      ALTER TABLE core.audit_log ADD COLUMN request_id uuid UNIQUE;
    -- or convert to uuid if wrong type
    ELSIF EXISTS (
      SELECT 1 FROM information_schema.columns
      WHERE table_schema='core' AND table_name='audit_log'
        AND column_name='request_id' AND data_type <> 'uuid'
    ) THEN
      ALTER TABLE core.audit_log
        ALTER COLUMN request_id TYPE uuid USING request_id::uuid;
    END IF;
  END IF;

  -- ensure a unique index on request_id
  IF NOT EXISTS (
    SELECT 1 FROM pg_indexes
    WHERE schemaname='core' AND indexname='audit_log_request_id_idx'
  ) THEN
    CREATE UNIQUE INDEX audit_log_request_id_idx ON core.audit_log(request_id);
  END IF;
END $$;
