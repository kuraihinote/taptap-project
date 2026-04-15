# schema_pod.py — POD schema context for LLM SQL generation
# Built from DDL knowledge + all SQL queries in the original hardcoded system.
# Active — pod schema access granted, POD queries working.

POD_SCHEMA_CONTEXT = """
You have access to the following tables for the POD (Problem of the Day) module.
Use ONLY these tables and columns — do not reference any other tables.

THIS MODULE COVERS: Problem of the Day activity only — daily challenges, who solved today, streaks, badges, coins, fastest solver, difficulty levels (easy/medium/hard), POD types (coding/aptitude/verbal), college rankings by POD activity.
NOT FOR: employability practice questions, formal assessments, company tests — those are in emp and assess modules.

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
    language                VARCHAR       -- language used e.g. 'python', 'java', 'c++'
    status                  TEXT          -- 'pass' or 'fail'
    obtained_score          INTEGER       -- score earned
    create_at               TIMESTAMPTZ   -- submission timestamp
)
KEY: status='pass' means the student solved it.
     pod_submission has NO type column — to filter coding/aptitude/verbal,
     JOIN to problem_of_the_day ON potd.id = ps.problem_of_the_day_id and filter potd.type.

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

-- Badges earned per student
pod.user_pod_badge (
    id              INTEGER
    user_id         VARCHAR     -- UUID matching public.user.id::text
    pod_badge_id    INTEGER     -- FK to pod.pod_badge.id
    image_url       VARCHAR
)
KEY: JOIN public.user u ON u.id::text = ub.user_id

-- Badge definitions
pod.pod_badge (
    id              INTEGER
    name            VARCHAR     -- e.g. 'Aptitude Silver', 'Bronze Explorer'
    badge_type      VARCHAR
    pod_category    VARCHAR     -- 'podCoding', 'podAptitude', 'podVerbal'
    streak_count    INTEGER
    questions_count INTEGER
)

-- Coins earned per student per event
pod.user_coins (
    id                      INTEGER
    user_id                 VARCHAR     -- UUID matching public.user.id::text
    coins_count             INTEGER     -- coins earned in this event; SUM() for total
    coin_earned_reason      VARCHAR     -- 'dailyLogin', 'problemOfTheDaySolved',
                                        -- 'dailyLoginAptitude', 'dailyLoginVerbal',
                                        -- 'problemOfTheDaySolvedAptitude',
                                        -- 'problemOfTheDaySolvedVerbal',
                                        -- 'mcqChallengeSolved'
    rewarded_date           DATE
    challenge_id            INTEGER
    problem_of_the_day_id   INTEGER
)
KEY: JOIN public.user u ON u.id::text = uc.user_id

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
user_coins      → public.user      via u.id::text = uc.user_id
user_pod_badge  → public.user      via u.id::text = ub.user_id
user_pod_badge  → pod_badge        via ub.pod_badge_id = b.id
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
- College filter: always use the exact college name provided in the question. Never substitute it with a similar or nearby campus name.
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

9. CONSISTENCY — students who solved POD every day in a period (e.g. every day this week):
SELECT
    (TRIM(u.first_name) || ' ' || TRIM(u.last_name)) AS name,
    c.name AS college,
    COUNT(DISTINCT ps.create_at::date) AS days_solved
FROM pod.pod_submission ps
JOIN public.user u ON u.id = ps.user_id
JOIN public.college c ON c.id = u.college_id
WHERE ps.status = 'pass'
  AND u.role = 'Student'
  AND ps.create_at >= date_trunc('week', CURRENT_DATE)
GROUP BY u.id, u.first_name, u.last_name, c.name
HAVING COUNT(DISTINCT ps.create_at::date) = (CURRENT_DATE - date_trunc('week', CURRENT_DATE)::date + 1)
ORDER BY days_solved DESC
LIMIT 50
NOTE: For 'every day this week' use HAVING COUNT(DISTINCT date) = days elapsed since Monday
      For 'every day in last 7 days' change WHERE to >= CURRENT_DATE - 7 and HAVING = 7
      For 'every day this month' use date_trunc('month', CURRENT_DATE) and HAVING = day-of-month

10. TODAY vs YESTERDAY — how many students solved POD today compared to yesterday:
SELECT
    COUNT(DISTINCT CASE WHEN ps.create_at::date = CURRENT_DATE     THEN ps.user_id END) AS solved_today,
    COUNT(DISTINCT CASE WHEN ps.create_at::date = CURRENT_DATE - 1 THEN ps.user_id END) AS solved_yesterday
FROM pod.pod_submission ps
JOIN public.user u ON u.id = ps.user_id
WHERE ps.status = 'pass'
  AND ps.create_at::date >= CURRENT_DATE - 1
  AND u.role = 'Student'

11. COLLEGE RANKING — which college has the most submissions/passes in last N days:
SELECT
    c.name                                                                AS college,
    COUNT(*)                                                              AS total_submissions,
    COUNT(DISTINCT ps.user_id)                                            AS unique_students,
    COUNT(CASE WHEN ps.status = 'pass' THEN 1 END)                       AS passed,
    ROUND(COUNT(CASE WHEN ps.status = 'pass' THEN 1 END) * 100.0
          / NULLIF(COUNT(*), 0), 2)                                       AS pass_rate_percent
FROM pod.pod_submission ps
JOIN public.user u ON u.id = ps.user_id
JOIN public.college c ON c.id = u.college_id
WHERE u.role = 'Student'
  AND ps.create_at::date >= CURRENT_DATE - INTERVAL '7 days'
GROUP BY c.id, c.name
ORDER BY total_submissions DESC
LIMIT 50

12. AVERAGE SCORE BY DIFFICULTY LEVEL:
SELECT
    ps.difficulty,
    ROUND(AVG(ps.obtained_score), 2)                                      AS avg_score,
    ROUND(AVG(CASE WHEN ps.status = 'pass' THEN ps.obtained_score END), 2) AS avg_passing_score,
    COUNT(*)                                                              AS total_submissions,
    COUNT(CASE WHEN ps.status = 'pass' THEN 1 END)                        AS passed,
    ROUND(COUNT(CASE WHEN ps.status = 'pass' THEN 1 END) * 100.0
          / NULLIF(COUNT(*), 0), 2)                                       AS pass_rate_percent
FROM pod.pod_submission ps
JOIN public.user u ON u.id = ps.user_id
WHERE u.role = 'Student'
  AND ps.difficulty IS NOT NULL
GROUP BY ps.difficulty
ORDER BY CASE ps.difficulty WHEN 'easy' THEN 1 WHEN 'medium' THEN 2 WHEN 'hard' THEN 3 END

13. DAILY AVERAGE ATTEMPTS OVER N DAYS (e.g. "average daily attempts this week"):
SELECT
    ROUND(AVG(daily_attempts), 2)  AS avg_attempts_per_day,
    ROUND(AVG(daily_passes), 2)    AS avg_passes_per_day,
    MIN(attempt_date)              AS period_start,
    MAX(attempt_date)              AS period_end,
    COUNT(*)                       AS days_counted
FROM (
    SELECT
        pa.create_at::date                                                       AS attempt_date,
        COUNT(DISTINCT pa.user_id)                                               AS daily_attempts,
        COUNT(DISTINCT CASE WHEN ps.status = 'pass' THEN ps.user_id END)        AS daily_passes
    FROM pod.pod_attempt pa
    JOIN public.user u ON u.id = pa.user_id
    LEFT JOIN pod.pod_submission ps
        ON ps.user_id = pa.user_id
        AND ps.problem_of_the_day_id = pa.problem_of_the_day_id
    WHERE pa.create_at::date >= CURRENT_DATE - INTERVAL '7 days'
      AND u.role = 'Student'
    GROUP BY pa.create_at::date
) daily

14. SUBMISSIONS GROUPED BY DIFFICULTY (use pod_submission.difficulty directly — no JOIN needed):
SELECT
    ps.difficulty,
    COUNT(*)                        AS total_submissions,
    COUNT(DISTINCT ps.user_id)      AS unique_students,
    COUNT(CASE WHEN ps.status = 'pass' THEN 1 END)  AS passed,
    ROUND(COUNT(CASE WHEN ps.status = 'pass' THEN 1 END) * 100.0
          / NULLIF(COUNT(*), 0), 2) AS pass_rate_percent
FROM pod.pod_submission ps
JOIN public.user u ON u.id = ps.user_id
WHERE u.role = 'Student'
  AND ps.difficulty IS NOT NULL
GROUP BY ps.difficulty
ORDER BY CASE ps.difficulty WHEN 'easy' THEN 1 WHEN 'medium' THEN 2 WHEN 'hard' THEN 3 END

15. TODAY'S TOP SCORER (highest obtained_score today):
SELECT
    (TRIM(u.first_name) || ' ' || TRIM(u.last_name)) AS name,
    c.name AS college,
    ps.title, ps.difficulty, ps.language,
    ps.obtained_score, ps.create_at
FROM pod.pod_submission ps
JOIN public.user u ON u.id = ps.user_id
JOIN public.college c ON c.id = u.college_id
WHERE ps.create_at::date = CURRENT_DATE
  AND ps.status = 'pass'
  AND u.role = 'Student'
ORDER BY ps.obtained_score DESC
LIMIT 1

16. FIRST-TIME SOLVERS TODAY — users with a submission today but no record before today:
SELECT COUNT(DISTINCT ps.user_id) AS first_time_today
FROM pod.pod_submission ps
WHERE ps.create_at::date = CURRENT_DATE
  AND NOT EXISTS (
      SELECT 1 FROM pod.pod_submission ps2
      WHERE ps2.user_id = ps.user_id
        AND ps2.create_at::date < CURRENT_DATE
  )

17. AVERAGE SCORE PER COLLEGE OVER N DAYS:
SELECT
    c.name                           AS college,
    COUNT(*)                         AS total_submissions,
    ROUND(AVG(ps.obtained_score), 2) AS avg_score
FROM pod.pod_submission ps
JOIN public.user u ON u.id = ps.user_id
JOIN public.college c ON c.id = u.college_id
WHERE u.role = 'Student'
  AND ps.create_at >= CURRENT_DATE - INTERVAL '7 days'
GROUP BY c.name
ORDER BY avg_score DESC
LIMIT 20
NOTE: Change INTERVAL '7 days' to match the requested period (e.g. '30 days', '1 day').

18. BADGE AND COIN LEADERS (most badges earned, with total coins):
SELECT
    TRIM(u.first_name) || ' ' || TRIM(u.last_name)  AS name,
    c.name                                            AS college,
    COUNT(DISTINCT ub.pod_badge_id)                   AS badges_earned,
    COALESCE(SUM(uc.coins_count), 0)                  AS total_coins
FROM pod.user_pod_badge ub
JOIN public.user u ON u.id::text = ub.user_id
LEFT JOIN public.college c ON c.id = u.college_id
LEFT JOIN pod.user_coins uc ON uc.user_id = ub.user_id
GROUP BY u.id, u.first_name, u.last_name, c.name
ORDER BY badges_earned DESC, total_coins DESC
LIMIT 10

19. COINS ONLY (POD solve coins, excluding login coins):
SELECT
    TRIM(u.first_name) || ' ' || TRIM(u.last_name)  AS name,
    SUM(uc.coins_count)                               AS pod_solve_coins
FROM pod.user_coins uc
JOIN public.user u ON u.id::text = uc.user_id
WHERE uc.coin_earned_reason IN (
    'problemOfTheDaySolved',
    'problemOfTheDaySolvedAptitude',
    'problemOfTheDaySolvedVerbal'
)
GROUP BY u.id, u.first_name, u.last_name
ORDER BY pod_solve_coins DESC
LIMIT 10
NOTE: For total coins (including login), remove the WHERE clause and SUM all coin_earned_reason values.
      For login coins only, filter coin_earned_reason IN ('dailyLogin', 'dailyLoginAptitude', 'dailyLoginVerbal').
"""