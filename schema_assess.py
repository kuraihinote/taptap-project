# schema_assess.py — Assessment schema context for LLM SQL generation
# Built from DDL knowledge + all SQL queries in the original hardcoded system.
# Ready to inject into analytics.py once Abdul grants gest schema access.

ASSESS_SCHEMA_CONTEXT = """
You have access to the following tables for the Assessments module.
Use ONLY these tables and columns — do not reference any other tables.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CORE TABLES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

-- Assessment definitions and shortlisted students
gest.assessment_shortlist (
    id                              UUID          -- primary key (cast to text for joins)
    assessment_title                VARCHAR       -- e.g. 'Backend Developer - DSA in C | Easy-Medium'
    status                          VARCHAR       -- assessment status
    assessment_type                 VARCHAR       -- type of assessment
    open_time                       TIMESTAMPTZ   -- when assessment opens
    close_time                      TIMESTAMPTZ   -- when assessment closes
    round_number                    INTEGER       -- round number
    shortlisted_students            JSONB         -- array of user UUIDs shortlisted
    assessment_submitted_students   JSONB         -- array of user UUIDs who submitted
    created_at                      TIMESTAMPTZ
)
KEY: jsonb_array_length(shortlisted_students) = total shortlisted count
     jsonb_array_length(assessment_submitted_students) = total submitted count
     To get shortlisted students: jsonb_array_elements_text(shortlisted_students)
     To get submitted students: jsonb_array_elements_text(assessment_submitted_students)

-- Final submission records — one row per question per student per assessment
gest.assessment_final_attempt_submission (
    id                  INTEGER
    user_id             VARCHAR       -- student user ID (VARCHAR, joins to public.user.id)
    assessment_id       VARCHAR       -- FK to gest.assessment_shortlist.id::text
    question_id         INTEGER
    status              TEXT          -- 'pass' or 'fail'
    obtained_score      NUMERIC       -- score earned on this question
    question_score      NUMERIC       -- max possible score
    language            VARCHAR       -- programming language used
    question_type       TEXT          -- 'MCQ', 'Coding', etc.
    skill               TEXT          -- skill being tested
    difficulty          TEXT          -- 'easy', 'medium', 'hard'
    hackathon_sub_domain ARRAY        -- sub-domain tags
    submission_time     TIMESTAMPTZ
    time_taken          BIGINT        -- milliseconds
    create_at           TIMESTAMPTZ
)
KEY: JOIN assessment_shortlist ON a.id::text = s.assessment_id
     JOIN public.user ON u.id = s.user_id  (both are VARCHAR)

-- Attempt history — tracks who started/completed the assessment
gest.assessment_round_attempt_history (
    id              INTEGER
    user_id         VARCHAR       -- FK to public.user.id
    assessment_id   INTEGER       -- FK to gest.assessment_shortlist.id (as integer)
    status          TEXT          -- 'completed', 'started'
    started_at      TIMESTAMPTZ
    submitted_at    TIMESTAMPTZ
)
KEY: JOIN assessment_shortlist ON a.id = r.assessment_id (integer join here, not text)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SHARED REFERENCE TABLES (public schema)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

public.user (
    id          VARCHAR   -- primary key
    first_name  VARCHAR
    last_name   VARCHAR
    email       VARCHAR
    role        TEXT      -- filter role = 'Student' for students
    college_id  INTEGER   -- FK to public.college.id
)

public.college (
    id   INTEGER
    name VARCHAR
)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
KEY RELATIONSHIPS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

assessment_final_attempt_submission → assessment_shortlist via s.assessment_id = a.id::text
assessment_final_attempt_submission → public.user via s.user_id = u.id
assessment_round_attempt_history    → assessment_shortlist via r.assessment_id = a.id (INTEGER)
assessment_round_attempt_history    → public.user via r.user_id = u.id::text
public.user → public.college via u.college_id = c.id

CRITICAL JOIN NOTES:
- assessment_final_attempt_submission.user_id is VARCHAR — joins to public.user.id directly
- assessment_round_attempt_history.user_id is VARCHAR — use u.id::text = r.user_id
- assessment_shortlist.id is UUID — cast to text: a.id::text = s.assessment_id
- For shortlisted/submitted student lists: expand JSONB array with jsonb_array_elements_text()

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
IMPORTANT NOTES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

- For assessment title filtering: a.assessment_title ILIKE '%keyword%'
  If title contains ' - ' or is > 25 chars, use exact match: ILIKE '%full title%'
  Otherwise split keywords: (ILIKE '%word1%' OR ILIKE '%word2%')
- For student name filtering: (TRIM(u.first_name) || ' ' || TRIM(u.last_name)) ILIKE '%name%'
- For pass rate: ROUND(COUNT(CASE WHEN s.status='pass' THEN 1 END)*100.0 / NULLIF(COUNT(s.id),0), 2)
- Today's date: {today}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STANDARD QUERY PATTERNS — MANDATORY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. LIST ASSESSMENTS:
SELECT
    a.id::text AS id,
    a.assessment_title AS title,
    a.status, a.assessment_type,
    a.open_time, a.close_time, a.round_number,
    jsonb_array_length(a.shortlisted_students)::int          AS shortlisted_count,
    jsonb_array_length(a.assessment_submitted_students)::int AS submitted_count,
    a.created_at
FROM gest.assessment_shortlist a
WHERE 1=1
ORDER BY a.created_at DESC
LIMIT 20

2. ASSESSMENT OVERVIEW (shortlisted vs submitted vs pass rate):
SELECT
    a.assessment_title AS title,
    a.status,
    jsonb_array_length(a.shortlisted_students)::int          AS shortlisted_count,
    jsonb_array_length(a.assessment_submitted_students)::int AS submitted_count,
    COUNT(DISTINCT s.user_id)                                AS students_with_submissions,
    COUNT(s.id)                                              AS total_question_submissions,
    COUNT(CASE WHEN s.status='pass' THEN 1 END)              AS total_passed,
    ROUND(COUNT(CASE WHEN s.status='pass' THEN 1 END)*100.0 / NULLIF(COUNT(s.id),0), 2) AS pass_rate_percent
FROM gest.assessment_shortlist a
LEFT JOIN gest.assessment_final_attempt_submission s ON s.assessment_id = a.id::text
WHERE a.assessment_title ILIKE '%keyword%'
GROUP BY a.id, a.assessment_title, a.status, a.shortlisted_students, a.assessment_submitted_students
ORDER BY a.created_at DESC

3. TOP SCORERS IN ASSESSMENT:
SELECT
    (TRIM(u.first_name) || ' ' || TRIM(u.last_name)) AS name,
    u.email,
    a.assessment_title AS assessment,
    SUM(s.obtained_score)                               AS total_score,
    COUNT(CASE WHEN s.status='pass' THEN 1 END)         AS questions_passed,
    COUNT(s.id)                                         AS questions_attempted
FROM gest.assessment_final_attempt_submission s
JOIN public.user u ON u.id = s.user_id
JOIN gest.assessment_shortlist a ON a.id::text = s.assessment_id
WHERE a.assessment_title ILIKE '%keyword%'
GROUP BY u.id, u.first_name, u.last_name, u.email, a.assessment_title
ORDER BY total_score DESC
LIMIT 10

4. PASS RATE FOR ASSESSMENT:
SELECT
    a.assessment_title AS assessment,
    a.status,
    COUNT(s.id)                                         AS total_submissions,
    COUNT(CASE WHEN s.status='pass' THEN 1 END)         AS passed,
    COUNT(CASE WHEN s.status='fail' THEN 1 END)         AS failed,
    ROUND(COUNT(CASE WHEN s.status='pass' THEN 1 END)*100.0 / NULLIF(COUNT(s.id),0), 2) AS pass_rate_percent,
    ROUND(AVG(s.obtained_score), 2)                     AS avg_score
FROM gest.assessment_shortlist a
LEFT JOIN gest.assessment_final_attempt_submission s ON s.assessment_id = a.id::text
WHERE a.assessment_title ILIKE '%keyword%'
GROUP BY a.id, a.assessment_title, a.status
ORDER BY pass_rate_percent DESC

5. SHORTLISTED BUT NOT SUBMITTED (who didn't show up):
SELECT
    a.assessment_title AS assessment,
    (TRIM(u.first_name) || ' ' || TRIM(u.last_name)) AS name,
    u.email, c.name AS college
FROM gest.assessment_shortlist a
JOIN public.user u
    ON u.id::text = ANY(SELECT jsonb_array_elements_text(a.shortlisted_students))
LEFT JOIN public.college c ON c.id = u.college_id
WHERE NOT (
    u.id::text = ANY(SELECT jsonb_array_elements_text(a.assessment_submitted_students))
)
AND a.assessment_title ILIKE '%keyword%'
ORDER BY a.assessment_title, u.first_name
LIMIT 50

6. STUDENTS WHO PASSED AN ASSESSMENT:
SELECT
    (TRIM(u.first_name) || ' ' || TRIM(u.last_name)) AS name,
    u.email, c.name AS college,
    a.assessment_title AS assessment,
    COUNT(CASE WHEN s.status='pass' THEN 1 END)         AS questions_passed,
    COUNT(s.id)                                         AS total_questions,
    SUM(s.obtained_score)                               AS total_score,
    ROUND(COUNT(CASE WHEN s.status='pass' THEN 1 END)*100.0 / NULLIF(COUNT(s.id),0), 2) AS pass_rate_percent
FROM gest.assessment_final_attempt_submission s
JOIN public.user u ON u.id = s.user_id
LEFT JOIN public.college c ON c.id = u.college_id
JOIN gest.assessment_shortlist a ON a.id::text = s.assessment_id
WHERE a.assessment_title ILIKE '%keyword%'
GROUP BY u.id, u.first_name, u.last_name, u.email, c.name, a.assessment_title
HAVING COUNT(CASE WHEN s.status='pass' THEN 1 END) > 0
ORDER BY questions_passed DESC, total_score DESC
LIMIT 50

7. STUDENT RESULT IN ASSESSMENT:
SELECT
    (TRIM(u.first_name) || ' ' || TRIM(u.last_name)) AS student_name,
    a.assessment_title AS assessment,
    s.question_type, s.skill, s.difficulty,
    s.language, s.status, s.obtained_score, s.question_score,
    s.submission_time
FROM gest.assessment_final_attempt_submission s
JOIN public.user u ON u.id = s.user_id
JOIN gest.assessment_shortlist a ON a.id::text = s.assessment_id
WHERE (TRIM(u.first_name) || ' ' || TRIM(u.last_name)) ILIKE '%name%'
ORDER BY s.submission_time DESC
LIMIT 50

8. SKILL BREAKDOWN FOR ASSESSMENT:
SELECT
    a.assessment_title AS assessment,
    s.skill,
    COUNT(s.id)                                         AS total_submissions,
    COUNT(DISTINCT s.user_id)                           AS unique_students,
    COUNT(CASE WHEN s.status='pass' THEN 1 END)         AS passed,
    ROUND(COUNT(CASE WHEN s.status='pass' THEN 1 END)*100.0 / NULLIF(COUNT(s.id),0), 2) AS pass_rate_percent,
    ROUND(AVG(s.obtained_score), 2)                     AS avg_score
FROM gest.assessment_final_attempt_submission s
JOIN gest.assessment_shortlist a ON a.id::text = s.assessment_id
WHERE s.skill IS NOT NULL
  AND a.assessment_title ILIKE '%keyword%'
GROUP BY a.assessment_title, s.skill
ORDER BY total_submissions DESC

9. COMPLETION RATE (shortlisted vs actually completed):
SELECT
    a.assessment_title AS assessment,
    a.status,
    jsonb_array_length(a.shortlisted_students)::int              AS shortlisted_count,
    jsonb_array_length(a.assessment_submitted_students)::int     AS submitted_count,
    ROUND(
        jsonb_array_length(a.assessment_submitted_students)::int * 100.0
        / NULLIF(jsonb_array_length(a.shortlisted_students)::int, 0), 2
    ) AS completion_rate_percent
FROM gest.assessment_shortlist a
WHERE a.assessment_title ILIKE '%keyword%'
ORDER BY a.created_at DESC
"""