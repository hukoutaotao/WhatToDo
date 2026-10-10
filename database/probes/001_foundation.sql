-- Synthetic native PostgreSQL probes. NOT executed by the offline design tests.
-- Apply all five migrations to an isolated empty test database first.
-- Execute with psql ON_ERROR_STOP; everything created here is rolled back.
BEGIN;
SET LOCAL search_path = pg_catalog;
SET CONSTRAINTS ALL IMMEDIATE;
CREATE TEMP TABLE probe_marker (id integer);
CREATE FUNCTION pg_temp.expect_error(statement text, wanted_state text)
RETURNS void LANGUAGE plpgsql AS $probe$
BEGIN
  BEGIN
    EXECUTE statement;
  EXCEPTION WHEN OTHERS THEN
    IF SQLSTATE <> wanted_state THEN
      RAISE EXCEPTION 'Expected SQLSTATE %, observed %', wanted_state, SQLSTATE;
    END IF;
    RETURN;
  END;
  RAISE EXCEPTION 'Expected SQLSTATE %, but statement succeeded', wanted_state;
END;
$probe$;

-- Zero and unknown are distinct; exact numerator/denominator 1/3 is preserved.
SELECT 0::whattodo.seconds, NULL::whattodo.seconds,
       1::whattodo.positive_integer, 3::whattodo.positive_integer;
SELECT pg_temp.expect_error($sql$SELECT '-1'::whattodo.seconds$sql$, '23514');
SELECT pg_temp.expect_error($sql$SELECT '0.5'::whattodo.seconds$sql$, '23514');
SELECT pg_temp.expect_error($sql$SELECT 'NaN'::whattodo.measure$sql$, '23514');
SELECT pg_temp.expect_error($sql$SELECT 'Infinity'::whattodo.measure$sql$, '23514');
SELECT pg_temp.expect_error($sql$SELECT '0'::whattodo.positive_integer$sql$, '23514');
SELECT pg_temp.expect_error($sql$SELECT 'infinity'::whattodo.instant$sql$, '23514');
SELECT pg_temp.expect_error($sql$SELECT 'infinity'::whattodo.calendar_date$sql$, '23514');

INSERT INTO whattodo.source_scope VALUES ('synthetic', 'probe-scope', 'probe-account', '2026-01-01T00:00:00Z');
INSERT INTO whattodo.source_identity VALUES ('probe-source', 'synthetic', 'probe-scope', 'item-1', 'OTHER');
INSERT INTO whattodo.source_record
  (record_id, source_id, external_revision, content_hash, source_timestamp, captured_at, state, deleted_at, raw_content_ref)
VALUES
  ('probe-record', 'probe-source', NULL, repeat('a', 64), NULL, '2026-01-01T00:00:00Z', 'PRESENT', NULL, 'synthetic-raw');

SELECT pg_temp.expect_error($sql$
  INSERT INTO whattodo.source_record
    (record_id, source_id, external_revision, content_hash, source_timestamp, captured_at, state, deleted_at, raw_content_ref)
  VALUES ('duplicate-probe-record', 'probe-source', NULL, repeat('a', 64), NULL, '2026-01-01T00:00:00Z', 'PRESENT', NULL, 'synthetic-raw')
$sql$, '23505');
SELECT pg_temp.expect_error($sql$
  INSERT INTO whattodo.source_identity VALUES ('out-of-scope-source', 'synthetic', 'missing-scope', 'item-2', 'OTHER')
$sql$, '23503');
SELECT pg_temp.expect_error($sql$UPDATE whattodo.source_record SET state = 'DELETED' WHERE record_id = 'probe-record'$sql$, '23514');
SELECT pg_temp.expect_error($sql$DELETE FROM whattodo.source_record WHERE record_id = 'probe-record'$sql$, '23514');
SELECT pg_temp.expect_error($sql$TRUNCATE whattodo.schema_migration$sql$, '23514');
SELECT pg_temp.expect_error($sql$UPDATE whattodo.store_epoch SET revision = revision + 2$sql$, '23514');

-- Lifecycle events retain capture history without rewriting it or Task state.
INSERT INTO whattodo.source_lifecycle_event
  (event_id, record_id, sequence, state, observed_at, source_evidence_ref)
VALUES ('probe-tombstone', 'probe-record', 1, 'DELETED', '2026-01-02T00:00:00Z', 'probe-record');
SELECT pg_temp.expect_error($sql$DELETE FROM whattodo.source_lifecycle_event$sql$, '23514');

ROLLBACK;
