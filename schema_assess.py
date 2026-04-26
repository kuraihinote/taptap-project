# schema_assess.py — Unified Assessments schema context for LLM SQL generation
# Covers TWO distinct assessment systems under one domain:
#   1. Hackathons / hackathon events / MET / profiling tests  → public.hackathon + user_hackathon_participation
#      MET (Monthly Employability Test) = hackathons with test_type_id = 6
#   2. Custom assessments / skill tests / smart interviews    → gest.* tables
#
# The chatbot uses a single "assess" domain for both. The decision of which
# table family to query is made by reading the faculty's question.

ASSESS_SCHEMA_CONTEXT = """
You have access to TWO assessment systems under the Assessments module.
Use ONLY the tables and columns listed below — do not reference any other tables.

THIS MODULE COVERS: all formal assessments on the platform — hackathons, hackathon
events, coding competitions, placement mock tests, profiling tests, MET (Monthly
Employability Test), Monthly Hackathon Assessments, custom assessments, skill tests,
smart interviews, recruiter-style tests, FDP program tests, BB Screening, Daily Tests,
Practice Tests.
Use for: top scorers in a named test/event, shortlisted students, who submitted vs who
didn't, pass rates, skill breakdowns, subdomain accuracy, round-wise scores, completion
rates, monthly MET results.

NOT FOR: Practice Track / Employability Track practice questions (those are in emp).
NOT FOR: POD / Challenge of the Day / daily challenge (those are in pod).
NOT FOR: overall employability score in combined_leaderboard (that is in emp).

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CRITICAL DECISION RULE — WHICH TABLE FAMILY TO USE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Read the faculty's question and pick ONE of two systems:

  A. HACKATHON tables (public.hackathon + public.user_hackathon_participation)
     Use when the question mentions ANY named test or event where students participate —
     hackathons, weekly tests, daily tests, profiling tests, MET, placement mocks,
     screening tests, coding challenges, or any other event-style assessment.
     Use the test_type_id routing guide below to apply the correct filter.
     Always use test_type_id filter when the category is clear.

  B. GEST custom assessment tables (gest.assessment_shortlist + gest.assessment_final_attempt_submission)
     Use ONLY when the question involves shortlisting — where specific students are
     selected/invited for a recruitment-style assessment. Key signals:
     - "who was shortlisted", "shortlisted students", "didn't submit after shortlisting"
     - Named role-based assessments: "Backend Developer - DSA in C", "Smart Interview",
       "Unified Assessment Library", "Web Development test"
     - Assessment rounds (Round 1, Round 2) for recruitment pipelines

  If ambiguous: the key distinction is SHORTLISTING. If the question involves students
  being selected/invited for a test → System B. If it's an open participation event
  where any student can attempt → System A.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SYSTEM A — HACKATHON TABLES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

-- Named hackathon events (70 columns, most are recruitment metadata — only use the ones listed)
public.hackathon (
    id                       INTEGER     -- primary key
    title                    VARCHAR     -- event name — always filter using keyword AND pattern
    start_date               TIMESTAMPTZ -- when the event opens; used for "latest" queries
    end_date                 TIMESTAMPTZ -- when the event closes
    status                   VARCHAR     -- 'published' or 'pending'
    registration_count       INTEGER     -- total scheduled/registered students (may be NULL)
    registered_college_count INTEGER     -- how many colleges registered
    test_type_id             INTEGER     -- type of test — use this for filtering, NOT domain column
    domain                   VARCHAR     -- UNRELIABLE free-text — NEVER filter by this
)

TEST TYPE MAPPING (test_type_id values) — use these for filtering by event category:
    3  = Hackathon-based Hiring
    4  = Company Assessment
    6  = Employability Test          ← MET / Monthly Hackathon Assessments
    8  = PGEST
    9  = Interview Preparation Test
    13 = Daily Test
    17 = BB Screening
    19 = Industry Based Hackathons
    40 = Placement Preparation
    43 = Weekly Test
    54 = Profiling Test
    62 = Coding Challenge
    63 = Placement Test

ROUTING GUIDE — which test_type_id to use based on faculty's question:
    "MET" / "monthly employability test" / "monthly hackathon assessment" → test_type_id = 6
    "profiling test" / "profiling assessment"                             → test_type_id = 54
    "daily test"                                                          → test_type_id = 13
    "BB Screening" / "blackbucks screening"                               → test_type_id = 17
    "weekly test"                                                         → test_type_id = 43
    "placement test" / "placement mock"                                   → test_type_id = 63
    "placement preparation"                                               → test_type_id = 40
    "coding challenge"                                                    → test_type_id = 62
    "industry hackathon" / "company hackathon"                            → test_type_id = 3 or 19
    General named event with no category signal                           → filter by h.title ILIKE only

CRITICAL — "LATEST" EVENT SUBQUERY:
When faculty asks for "latest" or "most recent" test of any category, the subquery
MUST join to user_hackathon_participation and use HAVING COUNT > 0 to skip empty events.
See Pattern A7 and A10 for the correct subquery structure — always follow that same
structure regardless of which test_type_id is being filtered.

NOTE: There is NO allowed_colleges column. College filtering must go via public.user → public.college.
NOTE: Always prefer test_type_id filter over title keywords when the category is clear from
      the faculty's question. Combine both when faculty mentions both a category and a name.

-- Per-student total score per hackathon event (PRIMARY table for leaderboards)
public.user_hackathon_participation (
    id                INTEGER
    hackathon_id      INTEGER     -- FK to public.hackathon.id
    user_id           VARCHAR     -- FK to public.user.id (direct, no cast needed)
    current_score     INTEGER     -- pre-aggregated total score — USE for leaderboards, no SUM needed
    start_time        TIMESTAMPTZ
    end_time          TIMESTAMPTZ
    round_start_time  TIMESTAMPTZ
    round_end_time    TIMESTAMPTZ
    report            JSONB       -- rich per-question breakdown (use for advanced analysis only)
    create_at         TIMESTAMPTZ
)

KEY FACTS:
    - 910k rows, current_score fully populated (range 0–3350, avg ~101)
    - report JSONB populated for ~96% of rows
    - For simple leaderboards, use current_score — DO NOT parse JSONB unnecessarily
    - JSONB structure (only when needed for round-wise or subdomain queries):
        report->'questionReports' = array of per-question objects
        each object has: status, roundId, difficulty, subDomain (array), totalScore, questionScore, questionType

-- Per-question submission detail (use for skill/difficulty breakdown at question level)
-- PERFORMANCE WARNING: This table has ~24 million rows.
-- ALWAYS filter by hackathon_id or test_type_id FIRST — never query without a WHERE filter.
-- Unfiltered queries will time out. Every query MUST include one of:
--   WHERE f.hackathon_id = (SELECT id FROM public.hackathon WHERE ...)
--   WHERE f.test_type_id = <id>
public.hackathon_final_attempt_submission (
    id                   INTEGER
    user_id              VARCHAR     -- FK to public.user.id (direct)
    hackathon_id         INTEGER     -- FK to public.hackathon.id
    round_id             INTEGER     -- FK to public.round_with_score.id
    test_type_id         INTEGER     -- same mapping as public.hackathon.test_type_id
                                     -- use to filter by test category on submissions
    obtained_score       NUMERIC     -- score earned on this question
    question_score       NUMERIC     -- max possible score
    status               TEXT        -- 'pass' or 'fail'
    question_type        TEXT        -- 'mcq', 'coding', 'subjective'
    skill                TEXT        -- 'Aptitude', 'Coding', 'English' — only on this table
    question_sub_domain  TEXT[]      -- array of topic tags e.g. ['Percentages'], ['Arrays']
                                     -- expand with: UNNEST(f.question_sub_domain) AS topic
                                     -- do NOT use jsonb_array_elements — this is a TEXT[] not JSONB
    difficulty           TEXT        -- 'easy', 'medium', 'hard'
    time_taken           BIGINT      -- milliseconds
)

-- Proctoring violations per student per hackathon
public.hackathon_proctoring_violation (
    id                    INTEGER
    hackathon_id          INTEGER     -- FK to public.hackathon.id
    round_id              INTEGER     -- FK to public.round_with_score.id
    user_id               VARCHAR     -- FK to public.user.id (direct)
    type                  VARCHAR     -- violation type:
                                     --   'RightClick', 'FullScreenExit', 'Copy',
                                     --   'Paste', 'Cut', 'DevToolsAccess'
    violation_capture_url VARCHAR     -- screenshot URL (do not expose in output)
)
NOTE: Join to public.hackathon via hackathon_id, to public.user via user_id.
NOTE: Multiple rows per student per violation — use COUNT(DISTINCT user_id) for student counts.
NOTE: 'FullScreenExit' and 'RightClick' are most common — not necessarily intentional cheating.
      'DevToolsAccess', 'Copy', 'Paste' are stronger signals of integrity concern.

-- Round definitions for hackathons (needed for per-round normalization)
public.round_with_score (
    id            INTEGER       -- round ID
    hackathon_id  INTEGER       -- FK to public.hackathon.id
    title         VARCHAR
    display_name  VARCHAR
    skill         VARCHAR       -- 'english', 'coding', 'aptitude' (lowercase)
    score         INTEGER       -- max_score for this round — used for normalization
    "order"       INTEGER       -- display order
)
NOTE: The column is named "order" — always quote it as "order" since it is a reserved word.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SYSTEM B — GEST CUSTOM ASSESSMENTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

-- Assessment definitions + shortlisted students
gest.assessment_shortlist (
    id                              UUID          -- primary key (cast to text for joins)
    assessment_title                VARCHAR       -- e.g. 'Backend Developer - DSA in C | Easy-Medium (Round 1)'
    status                          VARCHAR       -- always 'shortlisted' — not a useful filter
    assessment_type                 VARCHAR       -- 'open' = active/live | 'shortlisted' = not yet open
    open_time                       TIMESTAMPTZ
    close_time                      TIMESTAMPTZ
    round_number                    INTEGER       -- 1 through 4
    shortlisted_students            JSONB         -- array of user UUIDs shortlisted
    assessment_submitted_students   JSONB         -- array of user UUIDs who submitted
    created_at                      TIMESTAMPTZ
)

-- Per-question submission records
gest.assessment_final_attempt_submission (
    id                    INTEGER
    user_id               VARCHAR       -- FK to public.user.id (direct)
    assessment_id         VARCHAR       -- FK to gest.assessment_shortlist.id::text
    question_id           INTEGER
    status                TEXT          -- 'pass' | 'fail' | 'partiallyCorrect' | 'underReview'
    obtained_score        NUMERIC
    question_score        NUMERIC       -- max possible
    language              VARCHAR
    question_type         TEXT          -- 'MCQ', 'Coding', etc.
    skill                 TEXT
    difficulty            TEXT          -- 'easy', 'medium', 'hard'
    hackathon_sub_domain  ARRAY
    submission_time       TIMESTAMPTZ
    time_taken            BIGINT        -- milliseconds
    create_at             TIMESTAMPTZ
)

-- Attempt start/completion history
gest.assessment_round_attempt_history (
    id             INTEGER
    user_id        VARCHAR       -- FK to public.user.id (use u.id::text = r.user_id)
    assessment_id  INTEGER       -- FK to gest.assessment_shortlist.id (INTEGER join, NOT ::text)
    status         TEXT          -- 'completed', 'started'
    started_at     TIMESTAMPTZ
    submitted_at   TIMESTAMPTZ
)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SHARED REFERENCE TABLES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

public.user (
    id          VARCHAR   -- primary key (both numeric '479' and UUID format)
    first_name  VARCHAR
    last_name   VARCHAR
    email       VARCHAR
    role        TEXT      -- filter role = 'Student' for students
    college_id  INTEGER   -- FK to public.college.id
    roll_number VARCHAR   -- mostly NULL — do not include by default
)

public.college (
    id   INTEGER
    name VARCHAR
)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
KEY RELATIONSHIPS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

HACKATHON:
    user_hackathon_participation → public.hackathon         via p.hackathon_id = h.id
    user_hackathon_participation → public.user              via p.user_id = u.id
    hackathon_final_attempt_submission → public.user        via f.user_id = u.id
    hackathon_final_attempt_submission → public.hackathon   via f.hackathon_id = h.id
    round_with_score → public.hackathon                     via r.hackathon_id = h.id
    hackathon_proctoring_violation → public.hackathon       via v.hackathon_id = h.id
    hackathon_proctoring_violation → public.user            via v.user_id = u.id

GEST:
    assessment_final_attempt_submission → assessment_shortlist  via s.assessment_id = a.id::text
    assessment_final_attempt_submission → public.user           via s.user_id = u.id
    assessment_round_attempt_history   → assessment_shortlist   via r.assessment_id = a.id (INTEGER)
    assessment_round_attempt_history   → public.user            via u.id::text = r.user_id

COLLEGE:
    public.user → public.college                           via u.college_id = c.id

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CRITICAL RULES — APPLY TO BOTH SYSTEMS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. TITLE FILTERING (for hackathon.title and assessment_title):
   Split the faculty's phrase into individual meaningful words and combine with AND:
     (h.title ILIKE '%word1%' AND h.title ILIKE '%word2%')
   NEVER join the full phrase into one ILIKE — punctuation and separators like ' - ' and '|'
   will break the match. Skip filler words like 'show', 'in', 'the', 'for' — use only content
   words from the faculty's question.

2. STATUS COLUMNS — different across both systems:
   - hackathon.status:                        'published' | 'pending'
   - hackathon_final_attempt_submission.status: 'pass' | 'fail'
   - assessment_shortlist.status:             always 'shortlisted' — NEVER filter by this
   - assessment_final_attempt_submission.status: 'pass' | 'fail' | 'partiallyCorrect' | 'underReview'
     — for pass rate, include 'partiallyCorrect' and 'underReview' as non-pass unless specified
   - assessment_round_attempt_history.status:  'completed' | 'started'

3. ASSESSMENT_TYPE (on assessment_shortlist):
   - 'open'        = currently active/live assessment
   - 'shortlisted' = shortlisted but not yet opened

4. STUDENT NAME — always TRIM each column separately:
   (TRIM(u.first_name) || ' ' || TRIM(u.last_name)) AS name
   NEVER: TRIM(u.first_name || ' ' || u.last_name) — causes double spaces.

5. COLLEGE FILTERING:
   Applies to both systems via public.user → public.college:
     JOIN public.college c ON c.id = u.college_id
     WHERE c.name ILIKE '%keyword%'
   public.hackathon does NOT have an allowed_colleges column — go through user → college.
   Always use the exact college name provided. Never substitute with a similar campus name.

6. ROLL NUMBER — mostly NULL. Do not include in SELECT or GROUP BY by default.
   Only include if faculty explicitly asks for roll numbers.

7. Always filter u.role = 'Student' when joining public.user for student analytics.

8. shortlisted_students JSONB in assessment_shortlist may be empty — to find participants
   always use assessment_final_attempt_submission joined on assessment_id.

9. For SCORE DISTRIBUTION queries on gest assessments (no platform-defined pass threshold),
   use Pattern B4b which buckets students into >=80, 60-79, <60.
   students_above_80 + students_60_to_80 + students_below_60 MUST equal students_attempted.
   Always use COUNT(DISTINCT CASE WHEN ... THEN s.user_id END) — never COUNT(CASE WHEN ...)
   which counts question rows instead of students.

10. NESTED AGGREGATES — PostgreSQL rejects SUM(MAX(...)) and similar. Always use a CTE:
    WITH per_user_best AS (SELECT MAX(...) FROM ...) SELECT SUM(...) FROM per_user_best
    NEVER write SUM(MAX(...)) inline — it will throw a GroupingError.

11. Today's date: {today}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
QUERY PATTERNS — SYSTEM A (HACKATHON)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

PATTERN A1 — TOP SCORERS IN A NAMED HACKATHON EVENT:
SELECT
    (TRIM(u.first_name) || ' ' || TRIM(u.last_name)) AS name,
    c.name AS college,
    h.title AS hackathon,
    p.current_score AS total_score
FROM public.user_hackathon_participation p
JOIN public.user u ON u.id = p.user_id
JOIN public.hackathon h ON h.id = p.hackathon_id
LEFT JOIN public.college c ON c.id = u.college_id
WHERE u.role = 'Student'
  AND (h.title ILIKE '%word1%' AND h.title ILIKE '%word2%')
  -- AND c.name ILIKE '%college_keyword%'   -- uncomment for college filter
ORDER BY p.current_score DESC
LIMIT 10

PATTERN A2 — OVERALL HACKATHON LEADERBOARD ACROSS ALL EVENTS:
SELECT
    (TRIM(u.first_name) || ' ' || TRIM(u.last_name)) AS name,
    c.name AS college,
    SUM(p.current_score) AS total_score,
    COUNT(DISTINCT p.hackathon_id) AS events_participated
FROM public.user_hackathon_participation p
JOIN public.user u ON u.id = p.user_id
LEFT JOIN public.college c ON c.id = u.college_id
WHERE u.role = 'Student'
GROUP BY u.id, u.first_name, u.last_name, c.name
ORDER BY total_score DESC
LIMIT 10

PATTERN A3 — SKILL BREAKDOWN (Aptitude / Coding / English) FOR A NAMED HACKATHON OR TEST TYPE:
-- For a specific named event: join to public.hackathon and filter by title
-- For a test category (e.g. all MET tests): filter by f.test_type_id directly
-- Example for all MET: WHERE f.test_type_id = 6
-- Example for named event: JOIN public.hackathon h ON h.id = f.hackathon_id AND (h.title ILIKE '%word1%')
SELECT
    f.skill,
    COUNT(DISTINCT f.user_id) AS students_attempted,
    SUM(f.obtained_score) AS total_score,
    COUNT(CASE WHEN f.status = 'pass' THEN 1 END) AS questions_passed,
    ROUND(COUNT(CASE WHEN f.status = 'pass' THEN 1 END) * 100.0
          / NULLIF(COUNT(f.id), 0), 2) AS pass_rate_percent
FROM public.hackathon_final_attempt_submission f
JOIN public.hackathon h ON h.id = f.hackathon_id
WHERE f.skill IS NOT NULL
  AND (h.title ILIKE '%word1%' AND h.title ILIKE '%word2%')  -- replace with test type filter if needed
GROUP BY f.skill
ORDER BY total_score DESC

PATTERN A4 — TOP SCORERS BY SKILL IN A NAMED HACKATHON:
SELECT
    (TRIM(u.first_name) || ' ' || TRIM(u.last_name)) AS name,
    c.name AS college,
    f.skill,
    SUM(f.obtained_score) AS skill_score,
    COUNT(f.id) AS questions_attempted
FROM public.hackathon_final_attempt_submission f
JOIN public.user u ON u.id = f.user_id
JOIN public.hackathon h ON h.id = f.hackathon_id
LEFT JOIN public.college c ON c.id = u.college_id
WHERE u.role = 'Student'
  AND f.skill = 'Aptitude'   -- or 'Coding' or 'English'
  AND (h.title ILIKE '%word1%' AND h.title ILIKE '%word2%')
GROUP BY u.id, u.first_name, u.last_name, c.name, f.skill
ORDER BY skill_score DESC
LIMIT 10

PATTERN A5 — DIFFICULTY BREAKDOWN FOR A NAMED HACKATHON:
SELECT
    f.difficulty,
    COUNT(DISTINCT f.user_id) AS students_attempted,
    COUNT(f.id) AS total_submissions,
    COUNT(CASE WHEN f.status = 'pass' THEN 1 END) AS passed,
    ROUND(COUNT(CASE WHEN f.status = 'pass' THEN 1 END) * 100.0
          / NULLIF(COUNT(f.id), 0), 2) AS pass_rate_percent
FROM public.hackathon_final_attempt_submission f
JOIN public.hackathon h ON h.id = f.hackathon_id
WHERE f.difficulty IS NOT NULL
  AND (h.title ILIKE '%word1%' AND h.title ILIKE '%word2%')
GROUP BY f.difficulty
ORDER BY f.difficulty

PATTERN A6 — COLLEGE LEADERBOARD IN A NAMED HACKATHON:
SELECT
    c.name AS college,
    COUNT(DISTINCT p.user_id) AS students_participated,
    SUM(p.current_score) AS total_score,
    ROUND(AVG(p.current_score), 2) AS avg_score
FROM public.user_hackathon_participation p
JOIN public.user u ON u.id = p.user_id
JOIN public.hackathon h ON h.id = p.hackathon_id
LEFT JOIN public.college c ON c.id = u.college_id
WHERE u.role = 'Student'
  AND (h.title ILIKE '%word1%' AND h.title ILIKE '%word2%')
GROUP BY c.name
ORDER BY avg_score DESC
LIMIT 10

PATTERN A7 — LATEST / MOST RECENT HACKATHON LEADERBOARD:
-- For "latest hackathon", "most recent event" — never use date range filters.
-- Instead pick the most recent event WITH ACTUAL PARTICIPANTS.
-- CRITICAL: The subquery MUST include JOIN + HAVING COUNT > 0 — without this it will
-- pick empty/future events. NEVER simplify to just ORDER BY start_date DESC LIMIT 1.
-- For test-type-specific "latest" queries (MET, profiling, weekly etc.) use Pattern A10/A10b.
SELECT
    (TRIM(u.first_name) || ' ' || TRIM(u.last_name)) AS name,
    c.name AS college,
    h.title AS hackathon,
    p.current_score AS total_score
FROM public.user_hackathon_participation p
JOIN public.user u ON u.id = p.user_id
JOIN public.hackathon h ON h.id = p.hackathon_id
LEFT JOIN public.college c ON c.id = u.college_id
WHERE u.role = 'Student'
  AND h.id = (
      SELECT h2.id
      FROM public.hackathon h2
      JOIN public.user_hackathon_participation p2 ON p2.hackathon_id = h2.id
      GROUP BY h2.id, h2.start_date
      HAVING COUNT(DISTINCT p2.user_id) > 0
      ORDER BY h2.start_date DESC
      LIMIT 1
  )
ORDER BY p.current_score DESC
LIMIT 10
NOTE: When faculty specifies a title keyword (e.g. "latest MVSR hackathon"), add
      AND (h2.title ILIKE '%word1%' AND h2.title ILIKE '%word2%') inside the subquery WHERE.

PATTERN A8 — SUBDOMAIN ACCURACY FROM JSONB (advanced, for weak-area analysis):
-- Use ONLY when faculty names a SPECIFIC hackathon event by title.
-- DO NOT use for general topic/weak-area questions with no named event — use Pattern A8b instead.
-- DO NOT use jsonb_array_elements on question_sub_domain — that column is TEXT[], not JSONB.
-- This pattern reads from user_hackathon_participation.report JSONB field only.
WITH expanded_questions AS (
    SELECT
        uhp.user_id,
        (qr->'report'->>'status') AS status,
        (qr->'report'->>'roundId')::int AS round_id,
        jsonb_array_elements_text(qr->'report'->'subDomain') AS subdomain
    FROM public.user_hackathon_participation uhp
    CROSS JOIN LATERAL jsonb_array_elements(uhp.report->'questionReports') AS qr
    WHERE uhp.hackathon_id = (
        SELECT id FROM public.hackathon
        WHERE (title ILIKE '%word1%' AND title ILIKE '%word2%')
        ORDER BY start_date DESC LIMIT 1
    )
)
SELECT
    subdomain,
    COUNT(DISTINCT user_id) AS students_attempted,
    COUNT(DISTINCT CASE WHEN status = 'pass' THEN user_id END) AS students_passed,
    ROUND(COUNT(DISTINCT CASE WHEN status = 'pass' THEN user_id END) * 100.0
          / NULLIF(COUNT(DISTINCT user_id), 0), 2) AS accuracy_percent
FROM expanded_questions
GROUP BY subdomain
ORDER BY accuracy_percent ASC
LIMIT 20
NOTE: accuracy_percent < 40 is Weak, 40-59 is Moderate, 60-79 is Strong, >=80 is Very Strong.

PATTERN A8b — TOPIC / SUB-DOMAIN WEAK AREAS (uses question_sub_domain TEXT[] column):
-- Use when faculty asks about topics, sub-domains, or weak/strong areas for a specific event.
-- Source: question_sub_domain TEXT[] on hackathon_final_attempt_submission.
-- CRITICAL: Use UNNEST() — never jsonb_array_elements or jsonb_array_elements_text.
-- question_sub_domain is TEXT[], not JSONB. Pattern A8 uses JSONB and is for named events only.
-- PERFORMANCE: Always use WHERE hackathon_id = (subquery) — never a CTE JOIN pattern.
-- The direct WHERE subquery hits the (hackathon_id, user_id) index and returns fast.
-- Add h.test_type_id filter inside subquery if faculty specifies a test category.
-- Add h.title ILIKE filter inside subquery if faculty names a specific event.
SELECT
    UNNEST(f.question_sub_domain) AS topic,
    COUNT(*) AS total_attempts,
    COUNT(CASE WHEN f.status = 'pass' THEN 1 END) AS passed,
    ROUND(COUNT(CASE WHEN f.status = 'pass' THEN 1 END) * 100.0
          / NULLIF(COUNT(*), 0), 2) AS pass_rate_percent
FROM public.hackathon_final_attempt_submission f
WHERE f.question_sub_domain IS NOT NULL
  AND f.hackathon_id = (
      SELECT h.id FROM public.hackathon h
      JOIN public.user_hackathon_participation p ON p.hackathon_id = h.id
      -- AND h.test_type_id = <id>       -- add if faculty specifies a test type
      -- AND h.title ILIKE '%keyword%'    -- add if faculty names a specific event
      GROUP BY h.id, h.start_date
      HAVING COUNT(DISTINCT p.user_id) > 0
      ORDER BY h.start_date DESC
      LIMIT 1
  )
GROUP BY topic
ORDER BY pass_rate_percent ASC
LIMIT 50
NOTE: Order ASC surfaces weakest topics first. Same accuracy bands as A8 apply.
NOTE: WHERE hackathon_id = (subquery) is mandatory — it uses the DB index and is fast.
NOTE: Do not use a CTE + JOIN to pass hackathon_id — PostgreSQL cannot push it to the index.

PATTERN A8c — PROCTORING VIOLATIONS / ACADEMIC INTEGRITY FOR A NAMED EVENT:
-- Use when faculty asks about cheating, violations, integrity, tab switches, copy-paste,
-- DevTools access, or any suspicious behaviour during a test.
-- Violation types: 'RightClick', 'FullScreenExit', 'Copy', 'Paste', 'Cut', 'DevToolsAccess'
-- DevToolsAccess, Copy, Paste are stronger integrity signals than RightClick or FullScreenExit.
-- Always use COUNT(DISTINCT v.user_id) for student counts — multiple rows per student per type.
-- For a named event: filter by h.title ILIKE. For latest event: use the standard subquery.
SELECT
    (TRIM(u.first_name) || ' ' || TRIM(u.last_name)) AS name,
    u.email,
    c.name AS college,
    COUNT(*) AS total_violations,
    COUNT(DISTINCT v.type) AS violation_types,
    STRING_AGG(DISTINCT v.type, ', ') AS violation_types_list
FROM public.hackathon_proctoring_violation v
JOIN public.user u ON u.id = v.user_id
JOIN public.hackathon h ON h.id = v.hackathon_id
LEFT JOIN public.college c ON c.id = u.college_id
WHERE u.role = 'Student'
  AND (h.title ILIKE '%word1%' AND h.title ILIKE '%word2%')
  -- AND v.type IN ('DevToolsAccess', 'Copy', 'Paste')  -- uncomment for high-risk only
GROUP BY u.id, u.first_name, u.last_name, u.email, c.name
ORDER BY total_violations DESC
LIMIT 50
NOTE: To get a summary count instead of per-student list, GROUP BY v.type and COUNT(DISTINCT user_id).
NOTE: Do not expose violation_capture_url in any output.

PATTERN A8d — SCORE BAND DISTRIBUTION FOR A NAMED HACKATHON EVENT:
-- Use when faculty asks about band distribution, placement readiness, A++/A+/A/B/C breakdown,
-- score tiers, or how many students are placement-ready for a specific event.
-- Bands are computed dynamically from current_score / SUM(round_with_score.score):
--   A++ = >=80%  | A+ = 60-79%  | A = 40-59%  | B = 30-39%  | C = <30%
-- For a named event: filter by h.title ILIKE. For latest event: use the standard subquery.
-- IMPORTANT: JOIN round_with_score to get max possible score — never hardcode it.
WITH max_score AS (
    SELECT hackathon_id, SUM(score) AS total_max
    FROM public.round_with_score
    WHERE hackathon_id = (
        SELECT h.id FROM public.hackathon h
        JOIN public.user_hackathon_participation p ON p.hackathon_id = h.id
        WHERE (h.title ILIKE '%word1%' AND h.title ILIKE '%word2%')
        GROUP BY h.id, h.start_date
        HAVING COUNT(DISTINCT p.user_id) > 0
        ORDER BY h.start_date DESC
        LIMIT 1
    )
    GROUP BY hackathon_id
)
SELECT
    CASE
        WHEN ROUND(p.current_score * 100.0 / NULLIF(m.total_max, 0), 2) >= 80 THEN 'A++'
        WHEN ROUND(p.current_score * 100.0 / NULLIF(m.total_max, 0), 2) >= 60 THEN 'A+'
        WHEN ROUND(p.current_score * 100.0 / NULLIF(m.total_max, 0), 2) >= 40 THEN 'A'
        WHEN ROUND(p.current_score * 100.0 / NULLIF(m.total_max, 0), 2) >= 30 THEN 'B'
        ELSE 'C'
    END AS band,
    COUNT(DISTINCT p.user_id) AS student_count,
    ROUND(COUNT(DISTINCT p.user_id) * 100.0 / NULLIF(SUM(COUNT(DISTINCT p.user_id)) OVER (), 0), 2) AS pct_of_total
FROM public.user_hackathon_participation p
JOIN public.hackathon h ON h.id = p.hackathon_id
JOIN max_score m ON m.hackathon_id = p.hackathon_id
JOIN public.user u ON u.id = p.user_id
WHERE u.role = 'Student'
  AND (h.title ILIKE '%word1%' AND h.title ILIKE '%word2%')
GROUP BY
    CASE
        WHEN ROUND(p.current_score * 100.0 / NULLIF(m.total_max, 0), 2) >= 80 THEN 'A++'
        WHEN ROUND(p.current_score * 100.0 / NULLIF(m.total_max, 0), 2) >= 60 THEN 'A+'
        WHEN ROUND(p.current_score * 100.0 / NULLIF(m.total_max, 0), 2) >= 40 THEN 'A'
        WHEN ROUND(p.current_score * 100.0 / NULLIF(m.total_max, 0), 2) >= 30 THEN 'B'
        ELSE 'C'
    END
ORDER BY MIN(p.current_score * 100.0 / NULLIF(m.total_max, 0)) DESC
NOTE: For per-student band list instead of summary, remove GROUP BY band and SELECT band per student.
NOTE: Band cutoffs match BlackBucks platform standard — A++ >= 80%, A+ >= 60%, A >= 40%, B >= 30%, C < 30%.

PATTERN A9 — PARTICIPATION RATE FOR A NAMED HACKATHON:
SELECT
    h.title AS hackathon,
    h.registration_count AS total_scheduled,
    COUNT(DISTINCT p.user_id) AS students_attempted,
    ROUND(COUNT(DISTINCT p.user_id) * 100.0
          / NULLIF(h.registration_count, 0), 2) AS participation_rate_percent
FROM public.hackathon h
LEFT JOIN public.user_hackathon_participation p ON p.hackathon_id = h.id
WHERE (h.title ILIKE '%word1%' AND h.title ILIKE '%word2%')
GROUP BY h.id, h.title, h.registration_count

PATTERN A10 — MET / MONTHLY EMPLOYABILITY TEST LEADERBOARD (latest month):
-- Use for: "latest MET", "latest monthly employability test", "latest monthly hackathon assessment"
-- MET = hackathons with test_type_id = 6. Both the outer query AND subquery must filter
-- by test_type_id = 6 — this is what distinguishes MET from regular hackathons.
-- "Latest MET" = most recent hackathon with test_type_id = 6 that has participants.
-- CRITICAL: The subquery MUST include JOIN + HAVING COUNT > 0 — without this it will
-- pick empty events. Never simplify the subquery to just ORDER BY start_date DESC LIMIT 1.
SELECT
    (TRIM(u.first_name) || ' ' || TRIM(u.last_name)) AS name,
    c.name AS college,
    h.title AS met_title,
    h.start_date,
    p.current_score AS total_score
FROM public.user_hackathon_participation p
JOIN public.user u ON u.id = p.user_id
JOIN public.hackathon h ON h.id = p.hackathon_id
LEFT JOIN public.college c ON c.id = u.college_id
WHERE u.role = 'Student'
  AND h.test_type_id = 6
  AND h.id = (
      SELECT h2.id
      FROM public.hackathon h2
      JOIN public.user_hackathon_participation p2 ON p2.hackathon_id = h2.id
      WHERE h2.test_type_id = 6
      GROUP BY h2.id, h2.start_date
      HAVING COUNT(DISTINCT p2.user_id) > 0
      ORDER BY h2.start_date DESC
      LIMIT 1
  )
  -- AND c.name ILIKE '%college_keyword%'   -- uncomment for college filter
ORDER BY p.current_score DESC
LIMIT 50

PATTERN A10b — LATEST EVENT BY TEST TYPE (profiling, weekly, daily, placement, BB Screening etc.):
-- Use this pattern for ALL "latest X test" queries where X maps to a test_type_id.
-- Replace <TYPE_ID> with the correct test_type_id from the routing guide above.
-- CRITICAL: The subquery MUST include JOIN + HAVING COUNT > 0 — without this it will
-- pick empty/future events. NEVER simplify to just WHERE + ORDER BY start_date DESC LIMIT 1.
-- WRONG subquery (will return empty events):
--   SELECT h2.id FROM public.hackathon h2 WHERE h2.test_type_id = <TYPE_ID>
--   ORDER BY h2.start_date DESC LIMIT 1
-- CORRECT subquery (always use this):
--   SELECT h2.id FROM public.hackathon h2
--   JOIN public.user_hackathon_participation p2 ON p2.hackathon_id = h2.id
--   WHERE h2.test_type_id = <TYPE_ID>
--   GROUP BY h2.id, h2.start_date
--   HAVING COUNT(DISTINCT p2.user_id) > 0
--   ORDER BY h2.start_date DESC LIMIT 1
SELECT
    (TRIM(u.first_name) || ' ' || TRIM(u.last_name)) AS name,
    c.name AS college,
    h.title AS test_title,
    h.start_date,
    p.current_score AS total_score
FROM public.user_hackathon_participation p
JOIN public.user u ON u.id = p.user_id
JOIN public.hackathon h ON h.id = p.hackathon_id
LEFT JOIN public.college c ON c.id = u.college_id
WHERE u.role = 'Student'
  AND h.test_type_id = <TYPE_ID>             -- replace with correct test_type_id
  AND h.id = (
      SELECT h2.id
      FROM public.hackathon h2
      JOIN public.user_hackathon_participation p2 ON p2.hackathon_id = h2.id
      WHERE h2.test_type_id = <TYPE_ID>      -- same value as above
      GROUP BY h2.id, h2.start_date
      HAVING COUNT(DISTINCT p2.user_id) > 0
      ORDER BY h2.start_date DESC
      LIMIT 1
  )
  -- AND c.name ILIKE '%college_keyword%'   -- uncomment for college filter
ORDER BY p.current_score DESC
LIMIT 50

PATTERN A11 — MET RESULTS FOR A SPECIFIC MONTH (e.g. "March 2026 MET"):
-- Faculty will say "March MET" or "February monthly test" — match by title keyword.
-- MET event titles follow patterns like "Monthly Hackathon Assessment March -2026"
-- or "August Monthly Employability Test-2025" — use month name as keyword.
SELECT
    (TRIM(u.first_name) || ' ' || TRIM(u.last_name)) AS name,
    c.name AS college,
    h.title AS met_title,
    p.current_score AS total_score
FROM public.user_hackathon_participation p
JOIN public.user u ON u.id = p.user_id
JOIN public.hackathon h ON h.id = p.hackathon_id
LEFT JOIN public.college c ON c.id = u.college_id
WHERE u.role = 'Student'
  AND h.test_type_id = 6
  AND h.title ILIKE '%March%'    -- replace with requested month name
  -- AND c.name ILIKE '%college_keyword%'   -- uncomment for college filter
ORDER BY p.current_score DESC
LIMIT 50

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
QUERY PATTERNS — SYSTEM B (GEST CUSTOM ASSESSMENTS)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

PATTERN B1 — LIST ASSESSMENTS:
SELECT
    a.id::text AS id,
    a.assessment_title AS title,
    a.assessment_type,
    a.open_time, a.close_time, a.round_number,
    jsonb_array_length(a.shortlisted_students)::int          AS shortlisted_count,
    jsonb_array_length(a.assessment_submitted_students)::int AS submitted_count,
    a.created_at
FROM gest.assessment_shortlist a
ORDER BY a.created_at DESC
LIMIT 20

PATTERN B1b — LIST OPEN / ACTIVE ASSESSMENTS:
SELECT
    a.id::text AS id,
    a.assessment_title AS title,
    a.open_time, a.close_time, a.round_number,
    jsonb_array_length(a.shortlisted_students)::int          AS shortlisted_count,
    jsonb_array_length(a.assessment_submitted_students)::int AS submitted_count
FROM gest.assessment_shortlist a
WHERE a.assessment_type = 'open'
ORDER BY a.created_at DESC
LIMIT 20

PATTERN B2 — ASSESSMENT OVERVIEW (shortlisted vs submitted vs pass rate):
SELECT
    a.assessment_title AS title,
    jsonb_array_length(a.shortlisted_students)::int          AS shortlisted_count,
    jsonb_array_length(a.assessment_submitted_students)::int AS submitted_count,
    COUNT(DISTINCT s.user_id)                                AS students_with_submissions,
    COUNT(s.id)                                              AS total_question_submissions,
    COUNT(CASE WHEN s.status='pass' THEN 1 END)              AS total_passed,
    ROUND(COUNT(CASE WHEN s.status='pass' THEN 1 END) * 100.0
          / NULLIF(COUNT(s.id), 0), 2)                       AS pass_rate_percent
FROM gest.assessment_shortlist a
LEFT JOIN gest.assessment_final_attempt_submission s ON s.assessment_id = a.id::text
WHERE a.assessment_title ILIKE '%keyword%'
GROUP BY a.id, a.assessment_title, a.shortlisted_students, a.assessment_submitted_students
ORDER BY a.created_at DESC

PATTERN B3 — TOP SCORERS IN A NAMED CUSTOM ASSESSMENT:
SELECT
    (TRIM(u.first_name) || ' ' || TRIM(u.last_name)) AS name,
    u.email,
    c.name AS college,
    a.assessment_title AS assessment,
    SUM(s.obtained_score) AS total_score,
    COUNT(CASE WHEN s.status='pass' THEN 1 END) AS questions_passed,
    COUNT(s.id) AS questions_attempted
FROM gest.assessment_final_attempt_submission s
JOIN public.user u ON u.id = s.user_id
LEFT JOIN public.college c ON c.id = u.college_id
JOIN gest.assessment_shortlist a ON a.id::text = s.assessment_id
WHERE u.role = 'Student'
  AND (a.assessment_title ILIKE '%word1%' AND a.assessment_title ILIKE '%word2%')
GROUP BY u.id, u.first_name, u.last_name, u.email, c.name, a.assessment_title
ORDER BY total_score DESC
LIMIT 10

PATTERN B4 — PASS RATE FOR A SPECIFIC ASSESSMENT:
SELECT
    a.assessment_title AS assessment,
    COUNT(s.id) AS total_submissions,
    COUNT(CASE WHEN s.status='pass' THEN 1 END) AS passed,
    COUNT(CASE WHEN s.status='fail' THEN 1 END) AS failed,
    COUNT(CASE WHEN s.status='partiallyCorrect' THEN 1 END) AS partial,
    COUNT(CASE WHEN s.status='underReview' THEN 1 END) AS under_review,
    ROUND(COUNT(CASE WHEN s.status='pass' THEN 1 END) * 100.0
          / NULLIF(COUNT(s.id), 0), 2) AS pass_rate_percent,
    ROUND(AVG(s.obtained_score), 2) AS avg_score
FROM gest.assessment_shortlist a
LEFT JOIN gest.assessment_final_attempt_submission s ON s.assessment_id = a.id::text
WHERE (a.assessment_title ILIKE '%word1%' AND a.assessment_title ILIKE '%word2%')
GROUP BY a.id, a.assessment_title
ORDER BY pass_rate_percent DESC

PATTERN B4b — SCORE DISTRIBUTION ACROSS LATEST ASSESSMENTS (no specific title):
-- CRITICAL: Start from assessment_final_attempt_submission, NOT assessment_shortlist.
-- Do NOT use a simple LEFT JOIN from assessment_shortlist — returns NULLs.
-- Use a subquery to compute per-student score_pct first, then bucket.
SELECT
    a.assessment_title AS assessment,
    COUNT(DISTINCT s.user_id) AS students_attempted,
    ROUND(AVG(student_scores.score_pct), 2) AS avg_score_percent,
    COUNT(DISTINCT CASE WHEN student_scores.score_pct >= 80
                        THEN s.user_id END) AS students_above_80,
    COUNT(DISTINCT CASE WHEN student_scores.score_pct >= 60
                         AND student_scores.score_pct < 80
                        THEN s.user_id END) AS students_60_to_80,
    COUNT(DISTINCT CASE WHEN student_scores.score_pct < 60
                        THEN s.user_id END) AS students_below_60
FROM gest.assessment_final_attempt_submission s
JOIN gest.assessment_shortlist a ON a.id::text = s.assessment_id
JOIN (
    SELECT
        user_id,
        assessment_id,
        ROUND(SUM(obtained_score) * 100.0 / NULLIF(SUM(question_score), 0), 2) AS score_pct
    FROM gest.assessment_final_attempt_submission
    GROUP BY user_id, assessment_id
) student_scores ON student_scores.user_id = s.user_id
                AND student_scores.assessment_id = s.assessment_id
GROUP BY a.assessment_title
ORDER BY students_attempted DESC
LIMIT 20

PATTERN B5 — SHORTLISTED BUT NOT SUBMITTED (who didn't show up):
SELECT
    a.assessment_title AS assessment,
    (TRIM(u.first_name) || ' ' || TRIM(u.last_name)) AS name,
    u.email,
    c.name AS college
FROM gest.assessment_shortlist a
JOIN public.user u
    ON u.id::text = ANY(SELECT jsonb_array_elements_text(a.shortlisted_students))
LEFT JOIN public.college c ON c.id = u.college_id
WHERE u.role = 'Student'
  AND NOT (
      u.id::text = ANY(SELECT jsonb_array_elements_text(a.assessment_submitted_students))
  )
  AND (a.assessment_title ILIKE '%word1%' AND a.assessment_title ILIKE '%word2%')
ORDER BY a.assessment_title, u.first_name
LIMIT 50

PATTERN B6 — STUDENTS WHO PASSED AN ASSESSMENT:
SELECT
    (TRIM(u.first_name) || ' ' || TRIM(u.last_name)) AS name,
    u.email,
    c.name AS college,
    a.assessment_title AS assessment,
    COUNT(CASE WHEN s.status='pass' THEN 1 END) AS questions_passed,
    COUNT(s.id) AS total_questions,
    SUM(s.obtained_score) AS total_score,
    ROUND(COUNT(CASE WHEN s.status='pass' THEN 1 END) * 100.0
          / NULLIF(COUNT(s.id), 0), 2) AS pass_rate_percent
FROM gest.assessment_final_attempt_submission s
JOIN public.user u ON u.id = s.user_id
LEFT JOIN public.college c ON c.id = u.college_id
JOIN gest.assessment_shortlist a ON a.id::text = s.assessment_id
WHERE u.role = 'Student'
  AND (a.assessment_title ILIKE '%word1%' AND a.assessment_title ILIKE '%word2%')
GROUP BY u.id, u.first_name, u.last_name, u.email, c.name, a.assessment_title
HAVING COUNT(CASE WHEN s.status='pass' THEN 1 END) > 0
ORDER BY questions_passed DESC, total_score DESC
LIMIT 50

PATTERN B7 — INDIVIDUAL STUDENT RESULT IN AN ASSESSMENT:
SELECT
    (TRIM(u.first_name) || ' ' || TRIM(u.last_name)) AS student_name,
    c.name AS college,
    a.assessment_title AS assessment,
    s.question_type, s.skill, s.difficulty,
    s.language, s.status, s.obtained_score, s.question_score,
    s.submission_time
FROM gest.assessment_final_attempt_submission s
JOIN public.user u ON u.id = s.user_id
LEFT JOIN public.college c ON c.id = u.college_id
JOIN gest.assessment_shortlist a ON a.id::text = s.assessment_id
WHERE (TRIM(u.first_name) || ' ' || TRIM(u.last_name)) ILIKE '%name%'
ORDER BY s.submission_time DESC
LIMIT 50

PATTERN B8 — SKILL BREAKDOWN FOR A NAMED ASSESSMENT:
SELECT
    a.assessment_title AS assessment,
    s.skill,
    COUNT(s.id) AS total_submissions,
    COUNT(DISTINCT s.user_id) AS unique_students,
    COUNT(CASE WHEN s.status='pass' THEN 1 END) AS passed,
    ROUND(COUNT(CASE WHEN s.status='pass' THEN 1 END) * 100.0
          / NULLIF(COUNT(s.id), 0), 2) AS pass_rate_percent,
    ROUND(AVG(s.obtained_score), 2) AS avg_score
FROM gest.assessment_final_attempt_submission s
JOIN gest.assessment_shortlist a ON a.id::text = s.assessment_id
WHERE s.skill IS NOT NULL
  AND (a.assessment_title ILIKE '%word1%' AND a.assessment_title ILIKE '%word2%')
GROUP BY a.assessment_title, s.skill
ORDER BY total_submissions DESC

PATTERN B9 — COMPLETION RATE (shortlisted vs actually completed):
SELECT
    a.assessment_title AS assessment,
    jsonb_array_length(a.shortlisted_students)::int          AS shortlisted_count,
    jsonb_array_length(a.assessment_submitted_students)::int AS submitted_count,
    ROUND(
        jsonb_array_length(a.assessment_submitted_students)::int * 100.0
        / NULLIF(jsonb_array_length(a.shortlisted_students)::int, 0), 2
    ) AS completion_rate_percent
FROM gest.assessment_shortlist a
WHERE (a.assessment_title ILIKE '%word1%' AND a.assessment_title ILIKE '%word2%')
ORDER BY a.created_at DESC

PATTERN B10 — STUDENTS SHORTLISTED ACROSS MULTIPLE ASSESSMENTS:
WITH shortlisted AS (
    SELECT
        a.id AS assessment_id,
        a.assessment_title,
        jsonb_array_elements_text(a.shortlisted_students) AS user_id
    FROM gest.assessment_shortlist a
)
SELECT
    (TRIM(u.first_name) || ' ' || TRIM(u.last_name)) AS name,
    u.email,
    c.name AS college,
    COUNT(DISTINCT sl.assessment_id) AS assessments_shortlisted
FROM shortlisted sl
JOIN public.user u ON u.id = sl.user_id
LEFT JOIN public.college c ON c.id = u.college_id
WHERE u.role = 'Student'
GROUP BY u.id, u.first_name, u.last_name, u.email, c.name
HAVING COUNT(DISTINCT sl.assessment_id) > 1
ORDER BY assessments_shortlisted DESC
LIMIT 50
NOTE: Change HAVING > 1 to HAVING >= N for "shortlisted in at least N assessments".
"""