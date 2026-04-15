HACKATHON_SCHEMA_CONTEXT = """
You have access to the following tables for the Hackathon module.
Use ONLY these tables and columns — do not reference any other tables.

THIS MODULE COVERS: named hackathon tests, skill assessments, employability tests,
placement mock tests (including TCS Placement Mock), profiling tests, monthly hackathon
assessments. Top scorers in a specific named test or event. Subject-level performance:
verbal (MCQ), aptitude (MCQ), coding question scores. Student performance in a specific
named test. Completion and pass rates for a specific test. College-level performance in
a named test.
NOT FOR: POD daily challenges or streaks — use pod module.
NOT FOR: Employability Track practice questions by domain (DSA, Python, Algorithms etc.) — use emp module.
NOT FOR: Formal company recruitment assessments and shortlisting in gest schema — use assess module.
NOTE: TCS NQT does not exist in the DB. TCS Placement Mock Tests DO exist here — route those to this module.
NOTE: hackathon.domain column is free-text garbage ('Other', 'Hackathon', 'Daily Test') — never filter by it.

-- Named test / hackathon events
public.hackathon (
    id                 INTEGER
    title              VARCHAR     -- test/event name — always filter using keyword AND pattern
    domain             VARCHAR     -- UNRELIABLE free-text — NEVER use for filtering
    start_date         TIMESTAMPTZ  -- when the event opens
    end_date           TIMESTAMPTZ  -- when the event closes; use this for month-based filtering
    status             VARCHAR     -- 'published' or 'pending'
    registration_count INTEGER
)

-- Per-student total score per event (PRIMARY table for leaderboards)
public.user_hackathon_participation (
    id             INTEGER
    hackathon_id   INTEGER     -- FK to public.hackathon.id
    user_id        VARCHAR     -- matches public.user.id directly (both numeric and UUID)
                               -- simple JOIN public.user u ON u.id = p.user_id covers all users
    current_score  INTEGER     -- pre-aggregated total score for this student in this event
                               -- USE THIS for leaderboards — no SUM needed
    start_time     TIMESTAMPTZ
    end_time       TIMESTAMPTZ
)
KEY JOIN: public.user u ON u.id = p.user_id  (direct string match, no cast needed)

-- Per-question submission detail (use for skill/difficulty breakdown)
public.hackathon_final_attempt_submission (
    id                     INTEGER
    user_id                VARCHAR     -- matches public.user.id directly (both numeric and UUID)
    hackathon_id           INTEGER
    obtained_score         NUMERIC     -- score earned on this question
    question_score         NUMERIC     -- max possible score for this question
    status                 TEXT        -- 'pass' or 'fail'
    question_type          TEXT        -- 'mcq', 'coding', 'subjective'
    skill                  TEXT        -- 'Aptitude', 'Coding', 'English' (verbal), NULL
                                       -- THIS IS THE ONLY TABLE WITH skill COLUMN
    question_sub_domain    TEXT[]      -- ARRAY e.g. ['Percentages'], ['Arrays']
    difficulty             TEXT        -- 'easy', 'medium', 'hard'
)

-- Per-question breakdown with subdomain detail (use for subdomain/difficulty queries)
gest.user_hackathon_question_reports (
    id               INTEGER
    user_id          VARCHAR     -- matches public.user.id directly (both numeric and UUID)
    hackathon_id     INTEGER
    question_type    TEXT        -- 'mcq', 'coding', 'subjective'
    subdomain        TEXT[]      -- ARRAY subdomain tags
    status           TEXT        -- 'pass' or 'fail'
    difficulty       TEXT        -- 'easy', 'medium', 'hard'
    total_score      NUMERIC     -- score for this question
    question_score   NUMERIC     -- max possible
)

-- Student profiles
public.user (
    id             VARCHAR     -- both numeric ('479') and UUID strings — covers all platform users
    first_name     VARCHAR
    last_name      VARCHAR
    email          VARCHAR
    college_id     INTEGER     -- FK to public.college.id
)

public.college (
    id     INTEGER
    name   VARCHAR
)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CRITICAL RULES — ALWAYS FOLLOW
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. For leaderboards and total scores: use user_hackathon_participation.current_score
   It is pre-aggregated — do NOT SUM from other tables for total score.

2. For skill breakdown (aptitude/verbal/coding): use hackathon_final_attempt_submission
   The skill column ONLY exists on this table. Filter: WHERE f.skill = 'Aptitude' etc.
   skill values: 'Aptitude', 'Coding', 'English' (English = verbal)

3. For subdomain/difficulty breakdown: use user_hackathon_question_reports

4. For title filtering: split faculty's phrase into individual keywords with AND:
   (h.title ILIKE '%word1%' AND h.title ILIKE '%word2%')
   NEVER join the full phrase into one ILIKE — punctuation and separators will break it.

5. hackathon.domain column is free-text and unreliable — NEVER filter by it.
   Always filter events by h.title ILIKE '%keyword%'.

6. For "this month" or "latest" event queries, do not rely on date filters —
   use ORDER BY h.start_date DESC LIMIT 1 to get the most recent matching event.

6. Join pattern for leaderboards:
   FROM public.user_hackathon_participation p
   JOIN public.user u ON u.id = p.user_id
   JOIN public.hackathon h ON h.id = p.hackathon_id
   LEFT JOIN public.college c ON c.id = u.college_id

7. Join pattern for skill queries:
   FROM public.hackathon_final_attempt_submission f
   JOIN public.user u ON u.id = f.user_id
   JOIN public.hackathon h ON h.id = f.hackathon_id
   LEFT JOIN public.college c ON c.id = u.college_id

8. course.students — DO NOT USE. The correct join is public.user.

9. attempt_score in hackathon_attempt is 0 for most events — DO NOT USE for scores.
   current_score in user_hackathon_participation is the correct score column.

10. College filter: always use the exact college name provided in the question. Never substitute it with a similar or nearby campus name.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STANDARD QUERY PATTERNS — MANDATORY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. TOP SCORERS IN A NAMED EVENT:
SELECT
    TRIM(u.first_name) || ' ' || TRIM(u.last_name)  AS name,
    c.name                                            AS college,
    h.title                                           AS hackathon,
    p.current_score                                   AS total_score
FROM public.user_hackathon_participation p
JOIN public.user u ON u.id = p.user_id
JOIN public.hackathon h ON h.id = p.hackathon_id
LEFT JOIN public.college c ON c.id = u.college_id
WHERE (h.title ILIKE '%word1%' AND h.title ILIKE '%word2%')
ORDER BY p.current_score DESC
LIMIT 10;

2. OVERALL LEADERBOARD ACROSS ALL EVENTS:
SELECT
    TRIM(u.first_name) || ' ' || TRIM(u.last_name)  AS name,
    c.name                                            AS college,
    SUM(p.current_score)                              AS total_score,
    COUNT(DISTINCT p.hackathon_id)                    AS events_participated
FROM public.user_hackathon_participation p
JOIN public.user u ON u.id = p.user_id
LEFT JOIN public.college c ON c.id = u.college_id
GROUP BY u.id, u.first_name, u.last_name, c.name
ORDER BY total_score DESC
LIMIT 10;

3. SKILL BREAKDOWN — APTITUDE / VERBAL / CODING:
SELECT
    f.skill,
    COUNT(DISTINCT f.user_id)                                              AS students_attempted,
    SUM(f.obtained_score)                                                  AS total_score,
    COUNT(CASE WHEN f.status = 'pass' THEN 1 END)                         AS questions_passed,
    ROUND(COUNT(CASE WHEN f.status = 'pass' THEN 1 END) * 100.0
          / NULLIF(COUNT(f.id), 0), 2)                                     AS pass_rate_percent
FROM public.hackathon_final_attempt_submission f
WHERE f.skill IS NOT NULL
GROUP BY f.skill
ORDER BY total_score DESC;

4. TOP SCORERS BY SKILL IN A NAMED EVENT:
SELECT
    TRIM(u.first_name) || ' ' || TRIM(u.last_name)  AS name,
    c.name                                            AS college,
    f.skill,
    SUM(f.obtained_score)                             AS skill_score,
    COUNT(f.id)                                       AS questions_attempted
FROM public.hackathon_final_attempt_submission f
JOIN public.user u ON u.id = f.user_id
JOIN public.hackathon h ON h.id = f.hackathon_id
LEFT JOIN public.college c ON c.id = u.college_id
WHERE f.skill = 'Aptitude'   -- or 'Coding' or 'English'
AND (h.title ILIKE '%word1%' AND h.title ILIKE '%word2%')
GROUP BY u.id, u.first_name, u.last_name, c.name, f.skill
ORDER BY skill_score DESC
LIMIT 10;

5. SUBDOMAIN BREAKDOWN (e.g. Percentages, Arrays, Listening):
SELECT
    UNNEST(r.subdomain)                                                    AS subdomain,
    COUNT(DISTINCT r.user_id)                                              AS students_attempted,
    ROUND(COUNT(CASE WHEN r.status = 'pass' THEN 1 END) * 100.0
          / NULLIF(COUNT(r.id), 0), 2)                                     AS pass_rate_percent
FROM gest.user_hackathon_question_reports r
GROUP BY subdomain
ORDER BY students_attempted DESC
LIMIT 20;

6. DIFFICULTY BREAKDOWN:
SELECT
    f.difficulty,
    COUNT(DISTINCT f.user_id)                                              AS students_attempted,
    ROUND(COUNT(CASE WHEN f.status = 'pass' THEN 1 END) * 100.0
          / NULLIF(COUNT(f.id), 0), 2)                                     AS pass_rate_percent
FROM public.hackathon_final_attempt_submission f
WHERE f.difficulty IS NOT NULL
GROUP BY f.difficulty
ORDER BY f.difficulty;

7. STUDENT PROFILE ACROSS ALL HACKATHONS (no event filter needed):
SELECT
    TRIM(u.first_name) || ' ' || TRIM(u.last_name)  AS name,
    c.name                                            AS college,
    COUNT(DISTINCT p.hackathon_id)                    AS events_participated,
    SUM(p.current_score)                              AS total_score,
    MAX(p.current_score)                              AS best_event_score,
    MIN(p.start_time)                                 AS first_participation,
    MAX(p.start_time)                                 AS latest_participation
FROM public.user_hackathon_participation p
JOIN public.user u ON u.id = p.user_id
LEFT JOIN public.college c ON c.id = u.college_id
WHERE (TRIM(u.first_name) || ' ' || TRIM(u.last_name)) ILIKE '%student name%'
GROUP BY u.id, u.first_name, u.last_name, c.name
LIMIT 10;

8. COLLEGE LEADERBOARD IN A NAMED EVENT:
SELECT
    c.name                                            AS college,
    COUNT(DISTINCT p.user_id)                         AS students_participated,
    SUM(p.current_score)                              AS total_score,
    ROUND(AVG(p.current_score), 2)                    AS avg_score
FROM public.user_hackathon_participation p
JOIN public.user u ON u.id = p.user_id
JOIN public.hackathon h ON h.id = p.hackathon_id
LEFT JOIN public.college c ON c.id = u.college_id
WHERE (h.title ILIKE '%word1%' AND h.title ILIKE '%word2%')
GROUP BY c.name
ORDER BY avg_score DESC
LIMIT 10;
"""