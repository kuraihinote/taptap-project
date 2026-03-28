# schema_pod.py — POD schema context for LLM SQL generation
# Built from DDL knowledge + all SQL queries in the original hardcoded system.
# Ready to inject into analytics.py once Abdul grants pod schema access.

POD_SCHEMA_CONTEXT = """
You have access to the following tables for the POD (Problem of the Day) module.
Use ONLY these tables and columns — do not reference any other tables.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CORE TABLES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

-- Daily problem definition
pod.problem_of_the_day (
    id                  INTEGER
    date                DATE           -- the date this problem was active
    difficulty          TEXT           -- 'easy', 'medium', 'hard'
    type                TEXT           -- 'coding', 'aptitude', 'verbal'
    unique_user_attempts INTEGER       -- total unique users who attempted
    is_active           BOOLEAN        -- whether this is the current active problem
)
KEY: MAX(date) gives today's problem. Filter type for coding/aptitude/verbal PODs.

-- Attempt log — one row per user per day they opened the POD
pod.pod_attempt (
    id                      INTEGER
    user_id                 VARCHAR       -- FK to public.user.id
    problem_of_the_day_id   INTEGER       -- FK to pod.problem_of_the_day.id
    status                  TEXT          -- 'completed' or in-progress
    time_taken              BIGINT        -- milliseconds taken to solve
    pod_started_at          TIMESTAMPTZ   -- when they started
    end_date                TIMESTAMPTZ   -- when they finished
    create_at               TIMESTAMPTZ   -- attempt date
)
KEY: Use create_at::date = CURRENT_DATE for today's attempts.
     time_taken / 1000.0 = seconds. Lower = faster solver.
     JOIN to pod_submission ON ps.user_id = pa.user_id AND ps.problem_of_the_day_id = pa.problem_of_the_day_id

-- Submission log — one row per user per question passed/failed
pod.pod_submission (
    id                      INTEGER
    user_id                 VARCHAR       -- FK to public.user.id
    problem_of_the_day_id   INTEGER       -- FK to pod.problem_of_the_day.id
    question_id             INTEGER       -- question identifier
    title                   VARCHAR       -- question title
    difficulty              TEXT          -- 'easy', 'medium', 'hard'
    type                    TEXT          -- 'coding', 'aptitude', 'verbal' (pod type)
    language                VARCHAR       -- language used e.g. 'python', 'java', 'c++'
    status                  TEXT          -- 'pass' or 'fail'
    obtained_score          INTEGER       -- score earned
    create_at               TIMESTAMPTZ   -- submission timestamp
)
KEY: status='pass' means the student solved it. Filter type for coding/aptitude/verbal.
     JOIN to problem_of_the_day ON potd.id = ps.problem_of_the_day_id for potd.type filter.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STREAK TABLES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

-- Student streak records — one row per streak period per student
pod.pod_streak (
    id              INTEGER
    user_id         VARCHAR       -- FK to public.user.id
    type            TEXT          -- streak type category
    streak_count    INTEGER       -- number of consecutive days
    is_active       BOOLEAN       -- true = currently active streak
    start_date      DATE          -- when streak started
    end_date        DATE          -- when streak ended (null if active)
)
KEY: is_active=true for current streaks. MAX(streak_count) for longest ever.
     end_date >= CURRENT_DATE - 7 for recently lost streaks.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
GAMIFICATION TABLES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

-- Coins earned by students
pod.user_coins (
    id              INTEGER
    user_id         VARCHAR       -- FK to public.user.id
    coins_count     INTEGER       -- coins in this transaction (can be negative)
    create_at       TIMESTAMPTZ
)
KEY: SUM(coins_count) for total coins. One row per coin transaction.

-- Badge definitions
pod.pod_badge (
    id              INTEGER
    name            VARCHAR       -- badge name e.g. '7-Day Streak'
    description     VARCHAR
    badge_type      TEXT          -- badge category
    pod_category    TEXT          -- which POD type this badge is for
)

-- Badges earned by students
pod.user_pod_badge (
    id              INTEGER
    user_id         VARCHAR       -- FK to public.user.id
    pod_badge_id    INTEGER       -- FK to pod.pod_badge.id
    create_at       TIMESTAMPTZ   -- when badge was earned
)
KEY: JOIN pod_badge pb ON pb.id = upb.pod_badge_id for badge details.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SHARED REFERENCE TABLES (public schema)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

public.user (
    id            VARCHAR   -- primary key
    first_name    VARCHAR
    last_name     VARCHAR
    email         VARCHAR
    role          TEXT      -- always filter role = 'Student' for students
    college_id    INTEGER   -- FK to public.college.id
)

public.college (
    id   INTEGER
    name VARCHAR
)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
KEY RELATIONSHIPS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

pod_submission  → public.user      via ps.user_id = u.id
pod_attempt     → public.user      via pa.user_id = u.id
pod_streak      → public.user      via ps.user_id = u.id
user_coins      → public.user      via uc.user_id = u.id
user_pod_badge  → public.user      via upb.user_id = u.id
user_pod_badge  → pod_badge        via upb.pod_badge_id = pb.id
pod_submission  → problem_of_the_day via ps.problem_of_the_day_id = potd.id
pod_attempt     → problem_of_the_day via pa.problem_of_the_day_id = potd.id
public.user     → public.college   via u.college_id = c.id

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
IMPORTANT NOTES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

- Always filter u.role = 'Student' when querying students
- For college filtering: c.name ILIKE '%keyword%'
- For student name filtering: (TRIM(u.first_name) || ' ' || TRIM(u.last_name)) ILIKE '%name%'
- "Today" = create_at::date = CURRENT_DATE
- "This week" = create_at::date >= date_trunc('week', CURRENT_DATE)
- "Last N days" = create_at::date >= CURRENT_DATE - INTERVAL 'N days'
- For fastest solver: ORDER BY pa.time_taken ASC (lower = faster), convert to seconds: pa.time_taken/1000.0
- For pass rate: ROUND(COUNT(CASE WHEN status='pass' THEN 1 END)*100.0 / NULLIF(COUNT(*),0), 2)
- For who never passed: user IN pod_submission but NOT IN pod_submission WHERE status='pass'
- For who hasn't attempted today: user NOT IN pod_attempt WHERE create_at::date = CURRENT_DATE
- Today's date: {today}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STANDARD QUERY PATTERNS — MANDATORY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. WHO SOLVED TODAY'S POD:
SELECT
    (TRIM(u.first_name) || ' ' || TRIM(u.last_name)) AS name,
    c.name AS college, ps.title, ps.difficulty,
    ps.language, ps.obtained_score, ps.create_at
FROM pod.pod_submission ps
JOIN public.user u ON u.id = ps.user_id
JOIN public.college c ON c.id = u.college_id
WHERE ps.status = 'pass'
  AND ps.create_at::date = CURRENT_DATE
  AND u.role = 'Student'
ORDER BY ps.create_at DESC
LIMIT 50

2. ATTEMPT COUNT TODAY (how many students attempted/passed/failed):
SELECT
    COUNT(DISTINCT pa.user_id)                                          AS total_attempts,
    COUNT(DISTINCT CASE WHEN ps.status='pass' THEN ps.user_id END)     AS passed,
    COUNT(DISTINCT CASE WHEN ps.status='fail' THEN ps.user_id END)     AS failed
FROM pod.pod_attempt pa
JOIN public.user u ON u.id = pa.user_id
JOIN public.college c ON c.id = u.college_id
LEFT JOIN pod.pod_submission ps
    ON ps.user_id = pa.user_id
    AND ps.problem_of_the_day_id = pa.problem_of_the_day_id
WHERE pa.create_at::date = CURRENT_DATE
  AND u.role = 'Student'

3. FASTEST SOLVER TODAY:
SELECT
    (TRIM(u.first_name) || ' ' || TRIM(u.last_name)) AS name,
    c.name AS college,
    ROUND(pa.time_taken / 1000.0, 1) AS time_taken_seconds
FROM pod.pod_attempt pa
JOIN public.user u ON u.id = pa.user_id
JOIN public.college c ON c.id = u.college_id
WHERE pa.create_at::date = CURRENT_DATE
  AND pa.status = 'completed'
  AND pa.time_taken IS NOT NULL
  AND u.role = 'Student'
ORDER BY pa.time_taken ASC
LIMIT 10

4. TOP SCORERS (leaderboard, by total score):
SELECT
    (TRIM(u.first_name) || ' ' || TRIM(u.last_name)) AS name,
    c.name AS college,
    SUM(ps.obtained_score)          AS total_score,
    COUNT(DISTINCT ps.question_id)  AS questions_attempted
FROM pod.pod_submission ps
JOIN public.user u ON u.id = ps.user_id
JOIN public.college c ON c.id = u.college_id
WHERE u.role = 'Student'
GROUP BY u.id, u.first_name, u.last_name, c.name
ORDER BY total_score DESC
LIMIT 10

5. LONGEST STREAKS:
SELECT
    (TRIM(u.first_name) || ' ' || TRIM(u.last_name)) AS name,
    c.name AS college,
    MAX(ps.streak_count) AS max_streak,
    BOOL_OR(ps.is_active) AS has_active_streak
FROM pod.pod_streak ps
JOIN public.user u ON u.id = ps.user_id
JOIN public.college c ON c.id = u.college_id
WHERE u.role = 'Student'
GROUP BY u.id, u.first_name, u.last_name, c.name
ORDER BY max_streak DESC
LIMIT 10

6. STUDENTS WHO NEVER PASSED:
SELECT
    (TRIM(u.first_name) || ' ' || TRIM(u.last_name)) AS name,
    u.email, c.name AS college
FROM public.user u
JOIN public.college c ON c.id = u.college_id
WHERE u.role = 'Student'
  AND u.id IN (SELECT DISTINCT user_id FROM pod.pod_submission)
  AND u.id NOT IN (SELECT DISTINCT user_id FROM pod.pod_submission WHERE status='pass')
ORDER BY u.first_name
LIMIT 20

7. STUDENT POD PROFILE (individual student submissions):
SELECT
    (TRIM(u.first_name) || ' ' || TRIM(u.last_name)) AS name,
    c.name AS college, ps.title, ps.language,
    ps.difficulty, ps.status, ps.obtained_score, ps.create_at
FROM pod.pod_submission ps
JOIN public.user u ON u.id = ps.user_id
JOIN public.college c ON c.id = u.college_id
WHERE u.role = 'Student'
  AND (TRIM(u.first_name) || ' ' || TRIM(u.last_name)) ILIKE '%fullname%'
ORDER BY ps.create_at DESC
LIMIT 50

8. DAILY TREND (avg students per day over N days):
WITH daily AS (
    SELECT
        pa.create_at::date                                              AS attempt_date,
        COUNT(DISTINCT pa.user_id)                                      AS students_attempted,
        COUNT(DISTINCT CASE WHEN ps.status='pass' THEN ps.user_id END) AS students_passed,
        ROUND(
            COUNT(DISTINCT CASE WHEN ps.status='pass' THEN ps.user_id END)*100.0
            / NULLIF(COUNT(DISTINCT pa.user_id), 0), 2
        )                                                               AS pass_rate_percent
    FROM pod.pod_attempt pa
    JOIN public.user u ON u.id = pa.user_id
    JOIN public.college c ON c.id = u.college_id
    LEFT JOIN pod.pod_submission ps
        ON ps.user_id = pa.user_id
        AND ps.problem_of_the_day_id = pa.problem_of_the_day_id
    WHERE pa.create_at::date >= CURRENT_DATE - INTERVAL '30 days'
      AND u.role = 'Student'
    GROUP BY pa.create_at::date
)
SELECT
    attempt_date, students_attempted, students_passed, pass_rate_percent,
    ROUND(AVG(students_attempted) OVER ())::int AS avg_students_per_day,
    ROUND(AVG(pass_rate_percent)  OVER (), 2)   AS avg_pass_rate_percent
FROM daily
ORDER BY attempt_date DESC
"""