-- Geo questions: sub-questions vs. "separate question right after the geo question".
-- Run:  psql "$MAPSURVEY_DB_URL" -P pager=off -f <this file>
-- Django FK `parent_question_id` -> column `parent_question_id_id`.

\echo '=== 1. Top-level geo questions: with / without sub-questions ==='
WITH geo AS (
  SELECT q.id, q.survey_section_id, q.order_number,
         EXISTS (SELECT 1 FROM survey_question s WHERE s.parent_question_id_id = q.id) AS has_sub
  FROM survey_question q
  WHERE q.input_type IN ('point','line','polygon') AND q.parent_question_id_id IS NULL
)
SELECT count(*) AS geo_questions,
       count(*) FILTER (WHERE has_sub) AS with_subq,
       count(*) FILTER (WHERE NOT has_sub) AS without_subq,
       round(100.0 * count(*) FILTER (WHERE has_sub) / count(*), 1) AS pct_with_subq
FROM geo;

\echo '=== 2. Geo questions WITHOUT sub-questions that are immediately followed (same section) by a plain question ==='
WITH geo AS (
  SELECT q.id, q.survey_section_id, q.order_number
  FROM survey_question q
  WHERE q.input_type IN ('point','line','polygon') AND q.parent_question_id_id IS NULL
    AND NOT EXISTS (SELECT 1 FROM survey_question s WHERE s.parent_question_id_id = q.id)
), nxt AS (
  SELECT g.id,
         (SELECT n.input_type FROM survey_question n
           WHERE n.survey_section_id = g.survey_section_id AND n.parent_question_id_id IS NULL
             AND n.order_number > g.order_number ORDER BY n.order_number LIMIT 1) AS next_type
  FROM geo g
)
SELECT count(*) AS geo_without_subq,
       count(*) FILTER (WHERE next_type IN ('text','text_line','choice','multichoice','rating','number','range','ranking','datetime','photo','audio','document')) AS followed_by_plain_q,
       count(*) FILTER (WHERE next_type IN ('point','line','polygon')) AS followed_by_geo,
       count(*) FILTER (WHERE next_type IS NULL) AS last_in_section,
       count(*) FILTER (WHERE next_type IN ('html','image')) AS followed_by_display
FROM nxt;

\echo '=== 3. Same, per survey (one row per survey with >=1 geo question), only surveys that have real sessions ==='
WITH geo AS (
  SELECT q.id, q.survey_section_id, q.order_number, sec.survey_header_id,
         EXISTS (SELECT 1 FROM survey_question s WHERE s.parent_question_id_id = q.id) AS has_sub,
         (SELECT n.input_type FROM survey_question n
           WHERE n.survey_section_id = q.survey_section_id AND n.parent_question_id_id IS NULL
             AND n.order_number > q.order_number ORDER BY n.order_number LIMIT 1) AS next_type
  FROM survey_question q JOIN survey_surveysection sec ON sec.id = q.survey_section_id
  WHERE q.input_type IN ('point','line','polygon') AND q.parent_question_id_id IS NULL
), per_survey AS (
  SELECT survey_header_id,
         bool_or(has_sub) AS uses_subq,
         bool_or(NOT has_sub AND next_type IN ('text','text_line','choice','multichoice','rating','number','range','ranking')) AS uses_followup_q
  FROM geo GROUP BY survey_header_id
), used AS (
  SELECT survey_id FROM survey_surveysession GROUP BY survey_id HAVING count(*) >= 5
)
SELECT count(*) AS surveys_with_geo,
       count(*) FILTER (WHERE uses_subq) AS use_subq,
       count(*) FILTER (WHERE uses_followup_q AND NOT uses_subq) AS only_followup_q,
       count(*) FILTER (WHERE uses_subq AND uses_followup_q) AS both,
       count(*) FILTER (WHERE NOT uses_subq AND NOT uses_followup_q) AS neither
FROM per_survey WHERE survey_header_id IN (SELECT survey_header_id FROM used);

\echo '=== 4. Examples of the follow-up pattern (geo question name -> next question name) ==='
SELECT h.name AS survey, q.name AS geo_q, n.input_type AS next_type, n.name AS next_q
FROM survey_question q
JOIN survey_surveysection sec ON sec.id = q.survey_section_id
JOIN survey_surveyheader h ON h.id = sec.survey_header_id
JOIN LATERAL (SELECT n.* FROM survey_question n
              WHERE n.survey_section_id = q.survey_section_id AND n.parent_question_id_id IS NULL
                AND n.order_number > q.order_number ORDER BY n.order_number LIMIT 1) n ON true
WHERE q.input_type IN ('point','line','polygon') AND q.parent_question_id_id IS NULL
  AND NOT EXISTS (SELECT 1 FROM survey_question s WHERE s.parent_question_id_id = q.id)
  AND n.input_type IN ('text','text_line','choice','multichoice','rating')
ORDER BY h.id DESC LIMIT 25;
