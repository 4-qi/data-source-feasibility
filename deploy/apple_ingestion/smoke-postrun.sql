-- Read-only, safe metadata only. Supply psql --set run_id=<actual UUID>.
-- Never SELECT title/body/source_review_id/raw snapshots/anomalies here.
\set ON_ERROR_STOP on
BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY;
SET LOCAL TIME ZONE 'UTC';

SELECT count(*) = 1 AS run_exists
FROM collection_run WHERE id = :'run_id'::uuid;

SELECT r.id, a.source_application_id, r.started_at, r.finished_at,
       r.execution_status, r.coverage_status, r.stop_reason, r.reference_run_id,
       r.config_snapshot->>'run_mode' AS evidence_mode,
       r.config_snapshot->>'parser_version' AS parser_version,
       r.config_snapshot->>'hash_contract_version' AS hash_contract_version,
       r.config_snapshot->>'access_decision_ref' IS NOT NULL AS has_policy_trace,
       r.config_snapshot->'config'->>'min_pages' AS min_pages,
       r.config_snapshot->'config'->>'max_pages' AS max_pages,
       r.config_snapshot->'config'->>'max_http_requests' AS max_http_requests,
       r.config_snapshot->'config'->>'retry_count' AS automatic_retries
FROM collection_run r JOIN application a ON a.id = r.application_id
WHERE r.id = :'run_id'::uuid;

SELECT request_number, page_number, format, attempt_number, started_at,
       finished_at, http_status, parsing_status, persistence_status,
       entry_count, response_bytes, error_codes
FROM fetch_attempt WHERE run_id = :'run_id'::uuid
ORDER BY request_number;

SELECT count(*) AS request_intents,
       max(request_number) AS largest_request_number,
       count(*) <= 10 AS within_http_cap,
       count(DISTINCT page_number) FILTER
           (WHERE persistence_status = 'committed') AS committed_logical_pages,
       count(*) FILTER (WHERE format = 'xml') AS xml_requests,
       count(*) FILTER (WHERE attempt_number <> 1) AS noninitial_attempts,
       count(*) FILTER (WHERE finished_at IS NULL OR parsing_status = 'pending'
           OR persistence_status IN ('pending', 'unknown')) AS unresolved_attempts,
       sum(entry_count) FILTER (WHERE persistence_status = 'committed')
           AS committed_record_occurrences
FROM fetch_attempt WHERE run_id = :'run_id'::uuid;

-- Full text stays inside PostgreSQL. These are storage/ownership sanity checks,
-- not proof of upstream completeness or absence of unsupported representations.
SELECT count(*) AS observed_distinct_reviews,
       coalesce(sum(o.occurrence_count), 0) AS observed_occurrences,
       coalesce(sum(o.conflict_count), 0) AS disputed_occurrences,
       count(*) FILTER (WHERE v.title IS NULL) AS null_titles,
       count(*) FILTER (WHERE v.title = '') AS empty_titles,
       count(*) FILTER (WHERE v.body = '') AS empty_bodies,
       min(char_length(v.title)) AS min_title_characters,
       max(char_length(v.title)) AS max_title_characters,
       min(char_length(v.body)) AS min_body_characters,
       max(char_length(v.body)) AS max_body_characters,
       count(*) FILTER (WHERE octet_length(v.content_hash) <> 32
           OR octet_length(v.metadata_hash) <> 32) AS invalid_hash_lengths,
       count(*) FILTER (WHERE v.id IS NULL OR v.review_id <> o.review_id
           OR v.application_id <> o.application_id) AS ownership_errors
FROM review_observation o LEFT JOIN review_version v ON v.id = o.observed_version_id
WHERE o.run_id = :'run_id'::uuid;

SELECT first_action, count(*) AS reviews,
       sum(occurrence_count) AS occurrences, sum(conflict_count) AS disputes
FROM review_observation WHERE run_id = :'run_id'::uuid
GROUP BY first_action ORDER BY first_action;

SELECT count(*) AS versions_created_this_run,
       count(*) FILTER (WHERE version_number = 1) AS first_versions,
       count(*) FILTER (WHERE version_number > 1) AS later_versions
FROM review_version WHERE detecting_run_id = :'run_id'::uuid;

SELECT count(*) AS reviews_with_multiple_versions_created_in_one_run
FROM (SELECT review_id FROM review_version
      WHERE detecting_run_id = :'run_id'::uuid
      GROUP BY review_id HAVING count(*) > 1) disputed;

WITH touched AS (
    SELECT review_id FROM review_observation WHERE run_id = :'run_id'::uuid
), history AS (
    SELECT review_id, count(*) AS versions, min(version_number) AS first_number,
           max(version_number) AS latest_number
    FROM review_version WHERE review_id IN (SELECT review_id FROM touched)
    GROUP BY review_id
)
SELECT count(*) FILTER (WHERE cv.id IS NULL OR cv.review_id <> i.id
           OR cv.application_id <> i.application_id) AS invalid_current_pointers,
       count(*) FILTER (WHERE cv.version_number <> h.latest_number)
           AS current_version_not_latest,
       count(*) FILTER (WHERE h.first_number <> 1 OR h.versions <> h.latest_number)
           AS version_sequence_gaps
FROM review i JOIN touched t ON t.review_id = i.id
LEFT JOIN review_version cv ON cv.id = i.current_version_id
LEFT JOIN history h ON h.review_id = i.id;

COMMIT;
