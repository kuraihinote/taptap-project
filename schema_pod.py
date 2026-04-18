# schema_pod.py — POD (Problem of the Day / Challenge of the Day) schema context
# Updated: aligned scoring logic to production (MAX-then-SUM), added production-accurate
# leaderboard patterns, explicit track filtering, and vocabulary coverage
# (POD / Challenge of the Day / Daily Challenge).

POD_SCHEMA_CONTEXT = """
You have access to the following tables for the POD (Problem of the Day) module.
Use ONLY these tables and columns — do not reference any other tables.

THIS MODULE COVERS: Problem of the Day / Challenge of the Day / Daily Challenge —
daily coding, aptitude, and verbal problems. Who solved today's problem, daily and
all-time leaderboards, streaks, badges, coins, fastest solver, consistency (students
who solve every day), college rankings for POD activity, and POD score / problems-solved
counts. Supports specific tracks: coding, aptitude, verbal.

Faculty may refer to this as POD, Challenge of the Day, COTD, daily challenge, daily
problem, today's problem, or today's POD — all mean the same thing.

NOT FOR: employability practice questions / Practice Track / overall employability score
(those are in the emp module). Not for formal assessments, hackathons, company tests,
MET, profiling tests, skill tests (those are in assess/hackathon modules).

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CORE TABLES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

-- Daily problem definition — one row per (date, type) POD challenge
pod.problem_of_the_day (
    id                    INTEGER
    date                  DATE          -- the calendar date this problem was active
    difficulty            TEXT          -- 'easy', 'medium', 'hard'
    type                  TEXT          -- 'coding' | 'aptitude' | 'verbal'
    unique_user_attempts  INTEGER       -- denormalised count of unique attempters
    is_active             BOOLEAN       -- currently active POD flag
)

KEY RULES:
    - potd.date is the authoritative "which day this problem belongs to".
    - Use potd.date = CURRENT_DATE for today's problem.
    - Use potd.type = 'coding' | 'aptitude' | 'verbal' for track filtering.
    - Overall (all tracks): potd.type = ANY(ARRAY['coding','aptitude','verbal'])

-- Attempt log — one row per user per POD problem they opened
pod.pod_attempt (
    id                      INTEGER
    user_id                 VARCHAR       -- FK to public.user.id
    problem_of_the_day_id   INTEGER       -- FK to pod.problem_of_the_day.id
    status                  TEXT          -- 'completed' | 'started' (NOT 'pass'/'fail')
    time_taken              BIGINT        -- MILLISECONDS taken to solve
    pod_started_at          TIMESTAMPTZ   -- when they started
    end_date                TIMESTAMPTZ   -- when they finished (null if ongoing)
    create_at               TIMESTAMPTZ   -- attempt creation timestamp
)

KEY RULES:
    - pod_attempt.status = 'completed' means the student finished the POD.
      (Contrast with pod_submission.status which is 'pass' | 'fail' per question.)
    - time_taken / 1000.0 = seconds. Lower = faster.
    - For "solved" or "problems solved" count, always use:
      COUNT(DISTINCT CASE WHEN pa.status='completed' THEN pa.problem_of_the_day_id END)
    - JOIN to problem_of_the_day for track filtering and date binding:
      JOIN pod.problem_of_the_day potd ON pa.problem_of_the_day_id = potd.id

-- Submission log — one row per user per question attempt (retries allowed)
pod.pod_submission (
    id                      INTEGER
    user_id                 VARCHAR       -- FK to public.user.id
    problem_of_the_day_id   INTEGER       -- FK to pod.problem_of_the_day.id
    question_id             INTEGER       -- question identifier (many per POD)
    title                   VARCHAR       -- question title
    difficulty              TEXT          -- 'easy' | 'medium' | 'hard'
    language                VARCHAR       -- e.g. 'python', 'java', 'c++'
    status                  TEXT          -- 'pass' | 'fail' (per question)
    obtained_score          INTEGER       -- score earned on this submission
    create_at               TIMESTAMPTZ   -- submission timestamp
)

KEY RULES:
    - A student can submit the same question multiple times. Only their BEST
      attempt should count toward their score.
    - pod_submission has NO type column. For track filtering, JOIN to problem_of_the_day:
      JOIN pod.problem_of_the_day potd ON ps.problem_of_the_day_id = potd.id
    - For per-user total score (production formula):
        Step 1: MAX(obtained_score) per (user_id, problem_of_the_day_id, question_id)
        Step 2: SUM those maxes
      Use the subquery pattern shown in Pattern 2 below. Do NOT just SUM(obtained_score) —
      that double-counts retries.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STREAK TABLE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

pod.pod_streak (
    id              INTEGER
    user_id         VARCHAR       -- FK to public.user.id
    type            TEXT          -- streak category
    streak_count    INTEGER       -- consecutive days
    is_active       BOOLEAN       -- currently active streak
    start_date      DATE
    end_date        DATE          -- null if still active
)

KEY RULES:
    - Current streaks: is_active = true AND streak_count > 0
    - Longest ever for a student: MAX(streak_count) across their rows
    - Recently lost streaks: is_active = false AND end_date >= CURRENT_DATE - 7

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
GAMIFICATION TABLES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

-- Badges earned per student
pod.user_pod_badge (
    id              INTEGER
    user_id         VARCHAR       -- UUID text; JOIN u.id::text = ub.user_id
    pod_badge_id    INTEGER       -- FK to pod.pod_badge.id
    image_url       VARCHAR
)

-- Badge definitions / master list
pod.pod_badge (
    id                INTEGER
    name              VARCHAR     -- e.g. 'Aptitude Silver', 'Bronze Explorer'
    badge_type        VARCHAR
    pod_category      VARCHAR     -- 'podCoding' | 'podAptitude' | 'podVerbal'
    streak_count      INTEGER     -- threshold for streak-type badges
    questions_count   INTEGER     -- threshold for solved-count badges
)

-- Coins earned per student per event
pod.user_coins (
    id                      INTEGER
    user_id                 VARCHAR    -- UUID text; JOIN u.id::text = uc.user_id
    coins_count             INTEGER    -- coins earned this event; SUM() for totals
    coin_earned_reason      VARCHAR    -- see enum below
    rewarded_date           DATE
    challenge_id            INTEGER
    problem_of_the_day_id   INTEGER
)

COIN REASONS (enum values):
    Login coins:
        'dailyLogin', 'dailyLoginAptitude', 'dailyLoginVerbal'
    POD solve coins:
        'problemOfTheDaySolved', 'problemOfTheDaySolvedAptitude',
        'problemOfTheDaySolvedVerbal'
    MCQ challenge:
        'mcqChallengeSolved'

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SHARED REFERENCE TABLES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

public.user (
    id            VARCHAR
    first_name    VARCHAR
    last_name     VARCHAR
    email         VARCHAR
    role          TEXT          -- always filter role = 'Student'
    college_id    INTEGER
    roll_number   VARCHAR
)

public.college (
    id   INTEGER
    name VARCHAR
)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
KEY RELATIONSHIPS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

pod_attempt        → public.user           via pa.user_id = u.id
pod_submission     → public.user           via ps.user_id = u.id
pod_streak         → public.user           via pst.user_id = u.id
user_coins         → public.user           via u.id::text = uc.user_id     (UUID cast)
user_pod_badge     → public.user           via u.id::text = ub.user_id     (UUID cast)
user_pod_badge     → pod_badge             via ub.pod_badge_id = pb.id
pod_attempt        → problem_of_the_day    via pa.problem_of_the_day_id = potd.id
pod_submission     → problem_of_the_day    via ps.problem_of_the_day_id = potd.id
public.user        → public.college        via u.college_id = c.id

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CRITICAL RULES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. TRACK FILTERING (coding / aptitude / verbal):
   - Default to ALL tracks unless faculty specifies one:
       JOIN pod.problem_of_the_day potd ON ...
       WHERE potd.type = ANY(ARRAY['coding','aptitude','verbal'])
   - If faculty says "coding POD", "aptitude POD", "verbal POD", filter to that one:
       WHERE potd.type = 'coding'
   - Always join problem_of_the_day to enforce this — never skip it.

2. STATUS COLUMNS — pod_attempt vs pod_submission are DIFFERENT:
   - pod_attempt.status: 'completed' | 'started'  → use 'completed' for "solved a POD"
   - pod_submission.status: 'pass' | 'fail'       → use 'pass' for "passed a question"

3. SCORE CALCULATION (production formula) — ALWAYS use a CTE, NEVER an inline subquery:
   The score calculation requires two aggregation steps. PostgreSQL does not allow
   nested aggregates like SUM(MAX(...)) — this will always throw a GroupingError.
   The ONLY correct approach is a CTE:

   CORRECT — always use this CTE structure:
   WITH best_scores AS (
       SELECT user_id, problem_of_the_day_id, question_id,
              MAX(obtained_score) AS max_score       ← step 1: MAX per question in CTE
       FROM pod.pod_submission
       GROUP BY user_id, problem_of_the_day_id, question_id
   ),
   scoped_submissions AS (
       SELECT user_id, problem_of_the_day_id,
              SUM(max_score) AS total_pod_score      ← step 2: SUM in second CTE
       FROM best_scores
       GROUP BY user_id, problem_of_the_day_id
   )
   -- then LEFT JOIN scoped_submissions in the outer query

   WRONG — never do this (causes GroupingError):
   LEFT JOIN (
       SELECT user_id, SUM(MAX(obtained_score)) AS total_pod_score  ← INVALID
       FROM pod.pod_submission GROUP BY user_id
   ) ss ON ...

   WRONG — never do this (double-counts retries):
   SUM(ps.obtained_score) AS total_score  ← INVALID, inflated by retries

4. PROBLEMS SOLVED (count of PODs completed, not questions passed):
   COUNT(DISTINCT CASE WHEN pa.status='completed' THEN pa.problem_of_the_day_id END)
   from pod_attempt. Don't use pod_submission for this — that gives question-level counts.

5. TODAY'S POD — two equivalent options:
   - potd.date = CURRENT_DATE              (authoritative — use this preferentially)
   - pa.create_at::date = CURRENT_DATE     (user's attempt date — may differ from potd.date)

6. TIME / SPEED — time_taken is in MILLISECONDS:
   ROUND(pa.time_taken / 1000.0, 2) AS seconds

7. STUDENT NAME — always TRIM each column separately:
   (TRIM(u.first_name) || ' ' || TRIM(u.last_name)) AS name
   Never: TRIM(u.first_name || ' ' || u.last_name) — causes double spaces.

8. COLLEGE FILTERING:
   c.name ILIKE '%keyword%'
   Always use the exact college name provided. Never substitute with a similar campus name.

9. Always filter u.role = 'Student' when joining public.user.

10. UUID CAST for user_coins / user_pod_badge:
    JOIN public.user u ON u.id::text = uc.user_id
    JOIN public.user u ON u.id::text = ub.user_id
    (Cast is required — these columns store UUID as text.)

11. ROLL NUMBER — roll_number in public.user is mostly NULL across all users.
    Do NOT include it in SELECT or GROUP BY by default in leaderboard/performance queries.
    Only include it if the faculty explicitly asks for roll numbers.

12. Today's date: {today}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
QUERY PATTERNS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

PATTERN 1 — WHO SOLVED TODAY'S POD (track-aware, all tracks by default):
SELECT
    (TRIM(u.first_name) || ' ' || TRIM(u.last_name)) AS name,
    u.roll_number,
    c.name AS college,
    potd.type AS track,
    potd.difficulty,
    ROUND(pa.time_taken / 1000.0, 2) AS time_taken_seconds,
    pa.end_date
FROM pod.pod_attempt pa
JOIN pod.problem_of_the_day potd ON pa.problem_of_the_day_id = potd.id
JOIN public."user" u ON u.id = pa.user_id
JOIN public.college c ON c.id = u.college_id
WHERE u.role = 'Student'
  AND pa.status = 'completed'
  AND potd.date = CURRENT_DATE
  AND potd.type = ANY(ARRAY['coding','aptitude','verbal'])   -- change to single track if asked
ORDER BY pa.time_taken ASC NULLS LAST
LIMIT 50

PATTERN 2 — ALL-TIME POD LEADERBOARD (production-accurate scoring):
-- Coins and streaks use scalar subqueries instead of JOINs to stay within the 6-JOIN limit.
-- For specific track: change potd.type filter in both the CTE and outer query.
-- For college filter: add WHERE c.name ILIKE '%keyword%' in the OUTER query only.
--   DO NOT collapse the CTEs — keep the best_scores + scoped_submissions structure.
WITH best_scores AS (
    SELECT ps.user_id, ps.problem_of_the_day_id, ps.question_id,
           MAX(ps.obtained_score) AS max_score
    FROM pod.pod_submission ps
    JOIN pod.problem_of_the_day potd ON ps.problem_of_the_day_id = potd.id
    WHERE potd.type = ANY(ARRAY['coding','aptitude','verbal'])   -- change for specific track
    GROUP BY ps.user_id, ps.problem_of_the_day_id, ps.question_id
),
scoped_submissions AS (
    SELECT user_id, problem_of_the_day_id,
           SUM(max_score) AS total_pod_score
    FROM best_scores
    GROUP BY user_id, problem_of_the_day_id
)
SELECT
    (TRIM(u.first_name) || ' ' || TRIM(u.last_name)) AS name,
    c.name AS college,
    COUNT(DISTINCT CASE WHEN pa.status='completed' THEN pa.problem_of_the_day_id END) AS problems_solved,
    COALESCE(SUM(ss.total_pod_score), 0) AS total_score,
    COALESCE((
        SELECT SUM(uc.coins_count)
        FROM pod.user_coins uc
        WHERE uc.user_id = u.id::text
    ), 0) AS total_coins,
    COALESCE((
        SELECT MAX(pst.streak_count)
        FROM pod.pod_streak pst
        WHERE pst.user_id = u.id
          AND pst.is_active = true
    ), 0) AS current_streak
FROM pod.pod_attempt pa
JOIN pod.problem_of_the_day potd ON pa.problem_of_the_day_id = potd.id
JOIN public."user" u ON u.id = pa.user_id
JOIN public.college c ON c.id = u.college_id
LEFT JOIN scoped_submissions ss
    ON ss.user_id = pa.user_id AND ss.problem_of_the_day_id = pa.problem_of_the_day_id
WHERE u.role = 'Student'
  AND potd.type = ANY(ARRAY['coding','aptitude','verbal'])   -- change for specific track
  -- AND c.name ILIKE '%college_keyword%'   -- uncomment and replace for college filter
GROUP BY u.id, u.first_name, u.last_name, c.name
ORDER BY problems_solved DESC, total_score DESC, total_coins DESC
LIMIT 50

PATTERN 3 — DAILY POD LEADERBOARD (specific date, production RANK formula):
-- For specific date: change CURRENT_DATE in best_scores and user_performance CTEs
-- For specific track: change potd.type filter in both places
-- For college filter: add WHERE c.name ILIKE '%keyword%' in the OUTERMOST SELECT only.
--   DO NOT collapse the CTEs — keep the three-CTE structure even with a college filter.
WITH best_scores AS (
    SELECT ps.user_id, ps.problem_of_the_day_id, ps.question_id,
           MAX(ps.obtained_score) AS max_score
    FROM pod.pod_submission ps
    JOIN pod.problem_of_the_day potd ON ps.problem_of_the_day_id = potd.id
    WHERE potd.date = CURRENT_DATE                -- change to target date
      AND potd.type = ANY(ARRAY['coding','aptitude','verbal'])
    GROUP BY ps.user_id, ps.problem_of_the_day_id, ps.question_id
),
daily_scores AS (
    SELECT user_id, problem_of_the_day_id, SUM(max_score) AS total_pod_score
    FROM best_scores
    GROUP BY user_id, problem_of_the_day_id
),
user_performance AS (
    SELECT
        pa.user_id,
        COUNT(DISTINCT CASE WHEN pa.status='completed' THEN pa.problem_of_the_day_id END) AS problems_solved,
        COALESCE(SUM(ds.total_pod_score), 0) AS total_score,
        ROUND(AVG(CASE WHEN pa.status='completed' THEN pa.time_taken END) / 1000.0, 2) AS avg_time_seconds
    FROM pod.pod_attempt pa
    JOIN pod.problem_of_the_day potd ON pa.problem_of_the_day_id = potd.id
    LEFT JOIN daily_scores ds
        ON ds.user_id = pa.user_id AND ds.problem_of_the_day_id = pa.problem_of_the_day_id
    WHERE potd.date = CURRENT_DATE
      AND potd.type = ANY(ARRAY['coding','aptitude','verbal'])
    GROUP BY pa.user_id
)
SELECT
    (TRIM(u.first_name) || ' ' || TRIM(u.last_name)) AS name,
    c.name AS college,
    up.problems_solved,
    up.total_score,
    up.avg_time_seconds,
    RANK() OVER (ORDER BY up.problems_solved DESC, up.total_score DESC, up.avg_time_seconds ASC NULLS LAST) AS rank
FROM user_performance up
JOIN public."user" u ON u.id = up.user_id
JOIN public.college c ON c.id = u.college_id
WHERE u.role = 'Student'
  -- AND c.name ILIKE '%college_keyword%'   -- uncomment and replace keyword for college filter
ORDER BY rank ASC
LIMIT 50

PATTERN 4 — ATTEMPT / COMPLETION COUNT TODAY (how many attempted vs completed):
SELECT
    COUNT(DISTINCT pa.user_id)                                                AS total_attempters,
    COUNT(DISTINCT CASE WHEN pa.status='completed' THEN pa.user_id END)       AS completed,
    COUNT(DISTINCT CASE WHEN pa.status='started'   THEN pa.user_id END)       AS ongoing
FROM pod.pod_attempt pa
JOIN pod.problem_of_the_day potd ON pa.problem_of_the_day_id = potd.id
JOIN public."user" u ON u.id = pa.user_id
WHERE u.role = 'Student'
  AND potd.date = CURRENT_DATE
  AND potd.type = ANY(ARRAY['coding','aptitude','verbal'])

PATTERN 5 — FASTEST SOLVER (today, track-aware):
SELECT
    (TRIM(u.first_name) || ' ' || TRIM(u.last_name)) AS name,
    c.name AS college,
    potd.type AS track,
    ROUND(pa.time_taken / 1000.0, 2) AS time_taken_seconds
FROM pod.pod_attempt pa
JOIN pod.problem_of_the_day potd ON pa.problem_of_the_day_id = potd.id
JOIN public."user" u ON u.id = pa.user_id
JOIN public.college c ON c.id = u.college_id
WHERE u.role = 'Student'
  AND pa.status = 'completed'
  AND pa.time_taken IS NOT NULL
  AND potd.date = CURRENT_DATE
  AND potd.type = ANY(ARRAY['coding','aptitude','verbal'])
ORDER BY pa.time_taken ASC
LIMIT 10

PATTERN 6 — LONGEST STREAKS (current or all-time):
SELECT
    (TRIM(u.first_name) || ' ' || TRIM(u.last_name)) AS name,
    c.name AS college,
    MAX(pst.streak_count) AS max_streak,
    BOOL_OR(pst.is_active) AS has_active_streak
FROM pod.pod_streak pst
JOIN public."user" u ON u.id = pst.user_id
JOIN public.college c ON c.id = u.college_id
WHERE u.role = 'Student'
GROUP BY u.id, u.first_name, u.last_name, c.name
ORDER BY max_streak DESC
LIMIT 10
NOTE: For CURRENT active streaks only, add WHERE pst.is_active = true AND pst.streak_count > 0

PATTERN 7 — STUDENTS WHO NEVER PASSED A POD QUESTION:
SELECT
    (TRIM(u.first_name) || ' ' || TRIM(u.last_name)) AS name,
    u.email,
    c.name AS college
FROM public."user" u
JOIN public.college c ON c.id = u.college_id
WHERE u.role = 'Student'
  AND u.id IN (SELECT DISTINCT user_id FROM pod.pod_submission)
  AND u.id NOT IN (SELECT DISTINCT user_id FROM pod.pod_submission WHERE status='pass')
ORDER BY u.first_name
LIMIT 50

PATTERN 8 — INDIVIDUAL STUDENT POD PROFILE:
SELECT
    (TRIM(u.first_name) || ' ' || TRIM(u.last_name)) AS name,
    c.name AS college,
    potd.type AS track,
    ps.title,
    ps.language,
    ps.difficulty,
    ps.status,
    ps.obtained_score,
    ps.create_at
FROM pod.pod_submission ps
JOIN pod.problem_of_the_day potd ON ps.problem_of_the_day_id = potd.id
JOIN public."user" u ON u.id = ps.user_id
JOIN public.college c ON c.id = u.college_id
WHERE u.role = 'Student'
  AND (TRIM(u.first_name) || ' ' || TRIM(u.last_name)) ILIKE '%fullname%'
ORDER BY ps.create_at DESC
LIMIT 50

PATTERN 9 — DAILY TREND (last N days of POD engagement):
WITH daily AS (
    SELECT
        pa.create_at::date                                                        AS attempt_date,
        COUNT(DISTINCT pa.user_id)                                                AS students_attempted,
        COUNT(DISTINCT CASE WHEN pa.status='completed' THEN pa.user_id END)       AS students_completed
    FROM pod.pod_attempt pa
    JOIN pod.problem_of_the_day potd ON pa.problem_of_the_day_id = potd.id
    JOIN public."user" u ON u.id = pa.user_id
    WHERE pa.create_at::date >= CURRENT_DATE - INTERVAL '7 days'
      AND u.role = 'Student'
      AND potd.type = ANY(ARRAY['coding','aptitude','verbal'])
    GROUP BY pa.create_at::date
)
SELECT
    attempt_date,
    students_attempted,
    students_completed,
    ROUND(students_completed * 100.0 / NULLIF(students_attempted, 0), 2) AS completion_rate_percent
FROM daily
ORDER BY attempt_date DESC

PATTERN 10 — CONSISTENCY (students who solved POD every day in a period):
SELECT
    (TRIM(u.first_name) || ' ' || TRIM(u.last_name)) AS name,
    c.name AS college,
    COUNT(DISTINCT potd.date) AS days_solved
FROM pod.pod_attempt pa
JOIN pod.problem_of_the_day potd ON pa.problem_of_the_day_id = potd.id
JOIN public."user" u ON u.id = pa.user_id
JOIN public.college c ON c.id = u.college_id
WHERE u.role = 'Student'
  AND pa.status = 'completed'
  AND potd.date >= date_trunc('week', CURRENT_DATE)::date
  AND potd.type = ANY(ARRAY['coding','aptitude','verbal'])
GROUP BY u.id, u.first_name, u.last_name, c.name
HAVING COUNT(DISTINCT potd.date) = (CURRENT_DATE - date_trunc('week', CURRENT_DATE)::date + 1)
ORDER BY days_solved DESC
LIMIT 50
NOTE: "every day this week"  → HAVING = days elapsed since Monday
      "every day last 7 days" → change WHERE to CURRENT_DATE - 7, HAVING = 7
      "every day this month"  → use date_trunc('month', CURRENT_DATE), HAVING = day-of-month

PATTERN 11 — TODAY vs YESTERDAY COMPARISON:
SELECT
    COUNT(DISTINCT CASE WHEN potd.date = CURRENT_DATE     THEN pa.user_id END) AS completed_today,
    COUNT(DISTINCT CASE WHEN potd.date = CURRENT_DATE - 1 THEN pa.user_id END) AS completed_yesterday
FROM pod.pod_attempt pa
JOIN pod.problem_of_the_day potd ON pa.problem_of_the_day_id = potd.id
JOIN public."user" u ON u.id = pa.user_id
WHERE u.role = 'Student'
  AND pa.status = 'completed'
  AND potd.date >= CURRENT_DATE - 1
  AND potd.type = ANY(ARRAY['coding','aptitude','verbal'])

PATTERN 12 — COLLEGE RANKING BY POD ACTIVITY (last N days):
SELECT
    c.name                                                                  AS college,
    COUNT(DISTINCT pa.user_id)                                              AS active_students,
    COUNT(DISTINCT CASE WHEN pa.status='completed' THEN pa.id END)          AS total_completions,
    ROUND(
        COUNT(DISTINCT CASE WHEN pa.status='completed' THEN pa.id END) * 100.0
        / NULLIF(COUNT(*), 0), 2
    )                                                                       AS completion_rate_percent
FROM pod.pod_attempt pa
JOIN pod.problem_of_the_day potd ON pa.problem_of_the_day_id = potd.id
JOIN public."user" u ON u.id = pa.user_id
JOIN public.college c ON c.id = u.college_id
WHERE u.role = 'Student'
  AND pa.create_at >= CURRENT_DATE - INTERVAL '7 days'
  AND potd.type = ANY(ARRAY['coding','aptitude','verbal'])
GROUP BY c.id, c.name
ORDER BY total_completions DESC
LIMIT 50

PATTERN 13 — PASS RATE BY DIFFICULTY (question-level):
SELECT
    ps.difficulty,
    COUNT(*)                                                                AS total_submissions,
    COUNT(DISTINCT ps.user_id)                                              AS unique_students,
    COUNT(CASE WHEN ps.status = 'pass' THEN 1 END)                          AS passed,
    ROUND(COUNT(CASE WHEN ps.status = 'pass' THEN 1 END) * 100.0
          / NULLIF(COUNT(*), 0), 2)                                         AS pass_rate_percent
FROM pod.pod_submission ps
JOIN public."user" u ON u.id = ps.user_id
WHERE u.role = 'Student'
  AND ps.difficulty IS NOT NULL
GROUP BY ps.difficulty
ORDER BY CASE ps.difficulty WHEN 'easy' THEN 1 WHEN 'medium' THEN 2 WHEN 'hard' THEN 3 END

PATTERN 14 — FIRST-TIME SOLVERS TODAY (users with their first-ever submission today):
SELECT COUNT(DISTINCT ps.user_id) AS first_time_today
FROM pod.pod_submission ps
WHERE ps.create_at::date = CURRENT_DATE
  AND NOT EXISTS (
      SELECT 1 FROM pod.pod_submission ps2
      WHERE ps2.user_id = ps.user_id
        AND ps2.create_at::date < CURRENT_DATE
  )

PATTERN 15 — BADGE AND COIN LEADERS:
SELECT
    (TRIM(u.first_name) || ' ' || TRIM(u.last_name)) AS name,
    c.name AS college,
    COUNT(DISTINCT ub.pod_badge_id) AS badges_earned,
    COALESCE(MAX(uct.total_coins), 0) AS total_coins
FROM pod.user_pod_badge ub
JOIN public."user" u ON u.id::text = ub.user_id
LEFT JOIN public.college c ON c.id = u.college_id
LEFT JOIN (
    SELECT user_id, SUM(coins_count) AS total_coins
    FROM pod.user_coins
    GROUP BY user_id
) uct ON uct.user_id = u.id::text
WHERE u.role = 'Student'
GROUP BY u.id, u.first_name, u.last_name, c.name
ORDER BY badges_earned DESC, total_coins DESC
LIMIT 10

PATTERN 16 — COINS BREAKDOWN BY REASON (solve coins vs login coins):
SELECT
    (TRIM(u.first_name) || ' ' || TRIM(u.last_name)) AS name,
    SUM(CASE WHEN uc.coin_earned_reason IN (
        'problemOfTheDaySolved',
        'problemOfTheDaySolvedAptitude',
        'problemOfTheDaySolvedVerbal'
    ) THEN uc.coins_count ELSE 0 END) AS solve_coins,
    SUM(CASE WHEN uc.coin_earned_reason IN (
        'dailyLogin',
        'dailyLoginAptitude',
        'dailyLoginVerbal'
    ) THEN uc.coins_count ELSE 0 END) AS login_coins,
    SUM(uc.coins_count) AS total_coins
FROM pod.user_coins uc
JOIN public."user" u ON u.id::text = uc.user_id
WHERE u.role = 'Student'
GROUP BY u.id, u.first_name, u.last_name
ORDER BY total_coins DESC
LIMIT 10

PATTERN 17 — TODAY'S TOP SCORER (single highest):
WITH best_today AS (
    SELECT ps.user_id, ps.problem_of_the_day_id, ps.question_id,
           MAX(ps.obtained_score) AS max_score
    FROM pod.pod_submission ps
    JOIN pod.problem_of_the_day potd ON ps.problem_of_the_day_id = potd.id
    WHERE potd.date = CURRENT_DATE
      AND potd.type = ANY(ARRAY['coding','aptitude','verbal'])
    GROUP BY ps.user_id, ps.problem_of_the_day_id, ps.question_id
)
SELECT
    (TRIM(u.first_name) || ' ' || TRIM(u.last_name)) AS name,
    c.name AS college,
    SUM(bt.max_score) AS score_today
FROM best_today bt
JOIN public."user" u ON u.id = bt.user_id
JOIN public.college c ON c.id = u.college_id
WHERE u.role = 'Student'
GROUP BY u.id, u.first_name, u.last_name, c.name
ORDER BY score_today DESC
LIMIT 1
"""