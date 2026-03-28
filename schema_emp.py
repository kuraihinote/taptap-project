# schema_emp.py — Employability Track schema context for LLM SQL generation
# Moved out of analytics.py to match the schema file pattern of schema_pod.py / schema_assess.py

EMP_SCHEMA_CONTEXT = """
You have access to the following tables for the Employability Track module.
Use ONLY these tables and columns — do not reference any other tables.

-- Main submissions table (76,317 rows)
employability_track.employability_track_submission (
    user_id        VARCHAR     -- FK to public.user.id
    status         TEXT        -- 'pass' or 'fail'
    difficulty     TEXT        -- 'easy', 'medium', 'hard'
    obtained_score INTEGER     -- score the student got
    points         INTEGER     -- max possible score for the question
    title          VARCHAR     -- question title
    language       VARCHAR     -- programming language used (e.g. 'python', 'java')
    domain_id      INTEGER     -- FK to public.domains.id
    sub_domain_id  INTEGER     -- FK to public.question_sub_domain.id
    create_at      TIMESTAMPTZ -- submission timestamp
)

-- Question solved/attempted status per user (35,735 rows)
employability_track.question_status (
    user_id      VARCHAR  -- FK to public.user.id
    question_id  INTEGER  -- question identifier
    status       VARCHAR  -- 'solved' or 'attempted'
)

-- Question metadata (10,161 rows)
employability_track.employability_track_question (
    id           INTEGER
    question_id  INTEGER
    points       INTEGER  -- max score for this question
    test_type_id INTEGER  -- FK to public.test_type.id
)

-- Student identity (183,467 rows)
public.user (
    id            VARCHAR  -- primary key
    first_name    VARCHAR
    last_name     VARCHAR
    email         VARCHAR
    role          TEXT     -- filter to role = 'Student' for students
    college_id    INTEGER  -- FK to public.college.id
    department_id INTEGER  -- FK to public.department.id
)

-- College lookup (2,798 rows)
public.college (
    id   INTEGER
    name VARCHAR
)

-- Department/branch lookup (187 rows)
public.department (
    id   INTEGER
    name VARCHAR  -- e.g. 'Computer Science and Engineering', 'ECE', 'IT'
)

-- Domain lookup (145 rows)
public.domains (
    id     INTEGER
    domain VARCHAR  -- e.g. 'Data Structures', 'Python', 'Algorithms'
)

-- Sub-domain lookup (3,344 rows)
public.question_sub_domain (
    id   INTEGER
    name VARCHAR  -- topic name e.g. 'Arrays', 'Sorting', 'Recursion'
)

-- Question type lookup (56 rows)
public.test_type (
    id   INTEGER
    name VARCHAR  -- e.g. 'MCQ', 'Coding', 'Case Study'
)

IMPORTANT NOTES:
- Always JOIN public.user u ON u.id = ets.user_id to get student names
- Always JOIN public.college c ON c.id = u.college_id for college info
- For college filtering: c.name ILIKE '%keyword%'
- For domain filtering: d.domain ILIKE '%keyword%'
- For student name filtering ALWAYS use TRIM on each column separately before concat:
  (TRIM(u.first_name) || ' ' || TRIM(u.last_name)) ILIKE '%fullname%'
  IMPORTANT: Do NOT use TRIM(u.first_name || ' ' || u.last_name) — trailing spaces
  in individual columns cause double spaces in the concat, breaking the ILIKE match
- Always filter u.role = 'Student' when querying students
- Student names in the DB may have unusual capitalisation — always use ILIKE
- For "top scorers" or "leaderboard" queries ALWAYS rank by SUM(obtained_score) DESC
  NOT by percentage or ratio — faculty want absolute scores not percentages
- Today's date: {today}

STANDARD QUERY PATTERNS — MANDATORY. Use these exact structures for the listed query types:

1. STUDENT PROFILE (show [name]'s profile / submissions / activity):
SELECT
    (TRIM(u.first_name) || ' ' || TRIM(u.last_name)) AS name,
    c.name AS college,
    d.domain, qsd.name AS sub_domain,
    ets.title, ets.difficulty, ets.language,
    ets.status, ets.obtained_score, ets.points AS max_points,
    ets.create_at
FROM employability_track.employability_track_submission ets
JOIN public.user u ON u.id = ets.user_id
JOIN public.college c ON c.id = u.college_id
LEFT JOIN public.domains d ON d.id = ets.domain_id
LEFT JOIN public.question_sub_domain qsd ON qsd.id = ets.sub_domain_id
WHERE u.role = 'Student'
  AND (TRIM(u.first_name) || ' ' || TRIM(u.last_name)) ILIKE '%fullname%'
ORDER BY ets.create_at DESC
LIMIT 50

2. TOP SCORERS (leaderboard / highest score):
SELECT
    (TRIM(u.first_name) || ' ' || TRIM(u.last_name)) AS name,
    c.name AS college,
    COUNT(ets.id) AS total_submissions,
    SUM(ets.obtained_score) AS total_score,
    COUNT(CASE WHEN ets.status = 'pass' THEN 1 END) AS total_passed
FROM employability_track.employability_track_submission ets
JOIN public.user u ON u.id = ets.user_id
JOIN public.college c ON c.id = u.college_id
WHERE u.role = 'Student'
GROUP BY u.id, u.first_name, u.last_name, c.name
ORDER BY total_score DESC
LIMIT 10

3. PASS RATE BY DOMAIN:
SELECT
    d.domain,
    COUNT(ets.id) AS total_submissions,
    COUNT(DISTINCT ets.user_id) AS unique_students,
    COUNT(CASE WHEN ets.status = 'pass' THEN 1 END) AS passed,
    ROUND(COUNT(CASE WHEN ets.status = 'pass' THEN 1 END)*100.0 / NULLIF(COUNT(ets.id),0), 2) AS pass_rate_percent
FROM employability_track.employability_track_submission ets
JOIN public.domains d ON d.id = ets.domain_id
JOIN public.user u ON u.id = ets.user_id
JOIN public.college c ON c.id = u.college_id
WHERE u.role = 'Student'
  AND d.domain ILIKE '%domain_keyword%'
GROUP BY d.domain
ORDER BY total_submissions DESC
LIMIT 50

4. RECENT ACTIVITY (who submitted today / recently):
SELECT
    (TRIM(u.first_name) || ' ' || TRIM(u.last_name)) AS name,
    c.name AS college,
    COUNT(ets.id) AS total_submissions,
    COUNT(CASE WHEN ets.status = 'pass' THEN 1 END) AS passed,
    COUNT(CASE WHEN ets.status = 'fail' THEN 1 END) AS failed,
    MAX(ets.create_at) AS last_active
FROM employability_track.employability_track_submission ets
JOIN public.user u ON u.id = ets.user_id
JOIN public.college c ON c.id = u.college_id
WHERE u.role = 'Student'
  AND ets.create_at::date = CURRENT_DATE
GROUP BY u.id, u.first_name, u.last_name, c.name
ORDER BY last_active DESC
LIMIT 20

5. SUBDOMAIN BREAKDOWN (subtopic breakdown / weakest areas in a domain):
SELECT
    d.domain,
    qsd.name AS sub_domain,
    COUNT(ets.id) AS total_submissions,
    COUNT(DISTINCT ets.user_id) AS unique_students,
    COUNT(CASE WHEN ets.status = 'pass' THEN 1 END) AS passed,
    ROUND(COUNT(CASE WHEN ets.status = 'pass' THEN 1 END)*100.0 / NULLIF(COUNT(ets.id),0), 2) AS pass_rate_percent
FROM employability_track.employability_track_submission ets
JOIN public.domains d ON d.id = ets.domain_id
JOIN public.question_sub_domain qsd ON qsd.id = ets.sub_domain_id
JOIN public.user u ON u.id = ets.user_id
JOIN public.college c ON c.id = u.college_id
WHERE u.role = 'Student'
  AND d.domain ILIKE '%domain_keyword%'
GROUP BY d.domain, qsd.name
ORDER BY total_submissions DESC
LIMIT 20
"""