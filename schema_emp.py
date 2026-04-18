# schema_emp.py — Employability Track schema context for LLM SQL generation
# Updated: added combined_leaderboard (band/score/rank queries), track ID filtering,
# weighted scoring formula, problems-solved deduplication, days_active pattern.

EMP_SCHEMA_CONTEXT = """
You have access to the following tables for the Employability Track module.
Use ONLY these tables and columns — do not reference any other tables.

THIS MODULE COVERS: employability band/grade (A++, A+, A, B, C, F), employability score
percentage, overall/college rank, practice track leaderboard (problems solved, success rate,
points, easy/medium/hard breakdown, days active, weighted score), track-specific stats
(Coding, Aptitude, Verbal), domain/subdomain pass rates, student activity, top scorers,
and student profiles.
NOT FOR: named company tests, MET, profiling tests, formal assessments — those are in the
assess module. Challenge of the Day / daily POD — those are in the pod module.

=== TABLE 1: combined_leaderboard (pre-computed employability summary per student) ===
-- USE THIS TABLE for: band/grade queries, employabilityScore %, ranks, component scores.
-- College filter is built-in — no join to public.college needed for college filtering.

public.combined_leaderboard (
    "userId"               VARCHAR   -- FK to public.user.id (must be quoted — camelCase)
    "employabilityScore"   NUMERIC   -- overall employability score % (0–100, avg ~27)
    "employabilityBand"    VARCHAR   -- letter grade: 'A++', 'A+', 'A', 'B', 'C', 'F', 'NA'
    "aptitudePercentage"   NUMERIC   -- aptitude component score % (0–100)
    "codingPercentage"     NUMERIC   -- coding component score % (0–100)
    "englishPercentage"    NUMERIC   -- verbal/english component score % (0–100)
    "overallRank"          INTEGER   -- rank across all colleges
    "collegeRank"          INTEGER   -- rank within the student's college
    "collegeName"          VARCHAR   -- college name — already denormalized, no join needed
    "collegeId"            INTEGER   -- college ID
    "lastMonthPercentage"  NUMERIC   -- employability score % for last month
    name                   VARCHAR   -- full student name — already denormalized, no join needed
    email                  VARCHAR   -- student email — already denormalized, no join needed
)

CRITICAL: All camelCase columns MUST be double-quoted in SQL or PostgreSQL will fold
them to lowercase and throw "column does not exist":
    cl."userId", cl."employabilityBand", cl."employabilityScore", cl."collegeName",
    cl."collegeRank", cl."overallRank", cl."codingPercentage", cl."aptitudePercentage",
    cl."englishPercentage", cl."lastMonthPercentage"

NO JOIN NEEDED for name or college on combined_leaderboard queries:
    - cl.name already contains the full student name (denormalized)
    - cl."collegeName" already contains the college name (denormalized)
    - Only join public."user" if you need role filtering or roll_number

BAND VALUES (exact strings, case-sensitive as stored):
    'A++' — highest band
    'A+'
    'A'
    'B'
    'C'
    'F'  — lowest passing band
    'NA' — insufficient data / student hasn't started

=== TABLE 2: employability_track.employability_track_submission (raw submission log) ===
-- USE THIS TABLE for: problems solved, success rate, points, easy/medium/hard breakdown,
-- days active, weighted score, track-specific (Coding/Aptitude/Verbal), domain/subdomain stats,
-- recent activity, submission counts.

employability_track.employability_track_submission (
    user_id        VARCHAR     -- FK to public.user.id
    question_id    INTEGER     -- question identifier (use for distinct problem counting)
    status         TEXT        -- 'pass' or 'fail'
    difficulty     TEXT        -- 'easy', 'medium', 'hard'
    obtained_score INTEGER     -- score the student got (0–5)
    points         INTEGER     -- max possible score for the question
    title          VARCHAR     -- question title
    language       VARCHAR     -- programming language used (e.g. 'python', 'java')
    domain_id      INTEGER     -- FK to public.domains.id
    sub_domain_id  INTEGER     -- FK to public.question_sub_domain.id
    create_at      TIMESTAMPTZ -- submission timestamp
)

TRACK FILTERING — join employability_track_question and filter test_type_id:
    JOIN employability_track.employability_track_question etq ON etq.question_id = ets.question_id
    Coding track:   etq.test_type_id = 79
    Aptitude track: etq.test_type_id = 84
    Verbal track:   etq.test_type_id = 87
    All tracks (Overall): etq.test_type_id = ANY(ARRAY[79, 84, 87])
    IMPORTANT: When faculty asks about a specific track (coding/aptitude/verbal), ALWAYS
    join employability_track_question and filter by the correct test_type_id.

PROBLEMS SOLVED — always deduplicate:
    COUNT(DISTINCT CASE WHEN ets.status = 'pass' THEN ets.question_id END) AS problems_solved
    NEVER use COUNT(*) or COUNT(status='pass') for problems solved — same student can submit
    the same question multiple times; only count distinct question_ids they passed.

WEIGHTED SCORE FORMULA (for ranking/leaderboard):
    (COUNT(DISTINCT CASE WHEN ets.difficulty='hard'   AND ets.status='pass' THEN ets.question_id END) * 3)
  + (COUNT(DISTINCT CASE WHEN ets.difficulty='medium' AND ets.status='pass' THEN ets.question_id END) * 2)
  + (COUNT(DISTINCT CASE WHEN ets.difficulty='easy'   AND ets.status='pass' THEN ets.question_id END) * 1)
    AS weighted_score
    Use this formula for any leaderboard/top scorers/ranking query on Practice Track.

TIEBREAK ORDER for leaderboard:
    ORDER BY weighted_score DESC, problems_solved DESC, total_points DESC, success_rate DESC

DAYS ACTIVE:
    COUNT(DISTINCT DATE(ets.create_at)) AS days_active

SUCCESS RATE:
    ROUND(COUNT(CASE WHEN ets.status = 'pass' THEN 1 END)::numeric
          / NULLIF(COUNT(*), 0)::numeric * 100, 2) AS success_rate

=== OTHER LOOKUP TABLES ===

-- Student identity (183,467 rows)
public.user (
    id            VARCHAR  -- primary key
    first_name    VARCHAR
    last_name     VARCHAR
    email         VARCHAR
    role          TEXT     -- always filter role = 'Student'
    college_id    INTEGER  -- FK to public.college.id
    roll_number   VARCHAR  -- mostly NULL — do not include by default in SELECT or GROUP BY.
                           -- Only use if faculty explicitly asks for roll numbers.
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

-- Question metadata
employability_track.employability_track_question (
    id           INTEGER
    question_id  INTEGER
    points       INTEGER
    test_type_id INTEGER  -- 79=Coding, 84=Aptitude, 87=Verbal
)

=== CRITICAL RULES ===

1. WHICH TABLE TO USE — decision rule:

   USE combined_leaderboard when faculty asks about:
   - Band/grade: "A++", "A+", "A", "B", "C", "F" students
   - Employability score % threshold: "above 80%", "below 50%"
   - Ranks: "top ranked", "college rank", "overall rank"
   - Component score columns as a filter: "coding percentage above X"

   USE employability_track_submission when faculty asks about:
   - "Top students in coding / aptitude / verbal" — this is a LEADERBOARD query,
     always use Pattern 3 with test_type_id filtering. NEVER use combined_leaderboard
     for leaderboard/ranking queries — it does not have problems solved or weighted score.
   - Problems solved, success rate, points, days active, weighted score
   - Track-specific activity: "coding track", "aptitude track", "verbal track"
   - Domain/subdomain pass rates, submission counts, recent activity

   NEVER use combined_leaderboard for "top students in [track]" — it only has
   pre-aggregated percentages, not the leaderboard metrics faculty expect (problems
   solved, weighted score, E/M/H breakdown). Always use Pattern 3 for those.

2. BAND QUERIES — always use exact string match with quoted column:
   WHERE cl."employabilityBand" = 'A++'   ← correct
   NEVER compute band from percentages — it is pre-stored in combined_leaderboard.

3. 'NA' band — means the student has no data yet. Exclude from results unless
   faculty specifically asks about students who haven't started.

4. COLLEGE FILTERING:
   - On combined_leaderboard: WHERE cl."collegeName" ILIKE '%keyword%'  (no join needed)
   - On employability_track_submission: JOIN public.college c ON c.id = u.college_id
     WHERE c.name ILIKE '%keyword%'
   - Always use the exact college name provided. Never substitute with a similar campus name.
   - College names are full proper-case with city suffix e.g. "SRKR Engineering College, Bhimavaram"
     Faculty shorthand like "SRKR" or "KL" will match via ILIKE — always use ILIKE '%keyword%'
   - AMBIGUITY WARNING: Some college groups have multiple campuses with similar names
     e.g. "Vignan's Institute of Information Technology" and "Vignan's Institute of Engineering for Women"
     If faculty say just "Vignan", query may return both — that is correct behaviour unless
     faculty specify which campus.

5. STUDENT NAME on combined_leaderboard:
   Use cl.name directly — it is already denormalized. No join to public.user needed.
   On employability_track_submission: (TRIM(u.first_name) || ' ' || TRIM(u.last_name)) AS name
   NEVER: TRIM(u.first_name || ' ' || u.last_name) — causes double spaces.

6. DOMAIN NAMES are free-text and user-created. Split into keyword fragments with OR:
   (d.domain ILIKE '%word1%' OR d.domain ILIKE '%word2%')

7. Always filter u.role = 'Student' when joining public.user.
   On combined_leaderboard queries that don't join public.user — no role filter needed.

8. Today's date: {today}

=== QUERY PATTERNS ===

PATTERN 1 — BAND/GRADE QUERY (show students with A++ / A+ / B band etc.):
SELECT
    cl.name,
    cl."collegeName"          AS college,
    cl."employabilityBand"    AS band,
    cl."employabilityScore"   AS employability_score_percent,
    cl."codingPercentage"     AS coding_percent,
    cl."aptitudePercentage"   AS aptitude_percent,
    cl."englishPercentage"    AS verbal_percent,
    cl."collegeRank",
    cl."overallRank"
FROM public.combined_leaderboard cl
WHERE cl."employabilityBand" = 'A++'          -- replace band value as needed
  AND cl."employabilityBand" != 'NA'
ORDER BY cl."employabilityScore" DESC
LIMIT 50

PATTERN 2 — EMPLOYABILITY SCORE THRESHOLD (above/below X%):
-- Use for: "students with score above 80%", "students below 50% employability"
-- DO NOT use for: "top students in coding" — that is Pattern 3 (Practice Track leaderboard)
SELECT
    cl.name,
    cl."collegeName"          AS college,
    cl."employabilityBand"    AS band,
    cl."employabilityScore"   AS employability_score_percent,
    cl."collegeRank",
    cl."overallRank"
FROM public.combined_leaderboard cl
WHERE cl."employabilityScore" > 80            -- replace operator and threshold
  AND cl."employabilityBand" != 'NA'
ORDER BY cl."employabilityScore" DESC
LIMIT 50
NOTE: > for above/more than, < for below/less than, >= for at least, <= for at most

PATTERN 3 — PRACTICE TRACK LEADERBOARD (top students by weighted score, overall or per track):
-- Use for: "top students in coding", "coding track leaderboard", "aptitude leaderboard",
--          "who has the most problems solved", "top performers in verbal"
-- ALWAYS use this pattern for track-specific rankings — NOT combined_leaderboard.
-- For ALL tracks (Overall): use test_type_id = ANY(ARRAY[79, 84, 87])
-- For Coding only:   test_type_id = 79
-- For Aptitude only: test_type_id = 84
-- For Verbal only:   test_type_id = 87
SELECT
    (TRIM(u.first_name) || ' ' || TRIM(u.last_name)) AS name,
    c.name AS college,
    COUNT(DISTINCT CASE WHEN ets.status = 'pass' THEN ets.question_id END) AS problems_solved,
    COUNT(DISTINCT ets.question_id) AS problems_attempted,
    COUNT(*) AS total_submissions,
    ROUND(COUNT(CASE WHEN ets.status = 'pass' THEN 1 END)::numeric
          / NULLIF(COUNT(*), 0)::numeric * 100, 2) AS success_rate,
    SUM(ets.obtained_score) AS total_points,
    COUNT(DISTINCT CASE WHEN ets.difficulty='easy'   AND ets.status='pass' THEN ets.question_id END) AS easy_solved,
    COUNT(DISTINCT CASE WHEN ets.difficulty='medium' AND ets.status='pass' THEN ets.question_id END) AS medium_solved,
    COUNT(DISTINCT CASE WHEN ets.difficulty='hard'   AND ets.status='pass' THEN ets.question_id END) AS hard_solved,
    COUNT(DISTINCT DATE(ets.create_at)) AS days_active,
    (COUNT(DISTINCT CASE WHEN ets.difficulty='hard'   AND ets.status='pass' THEN ets.question_id END) * 3
   + COUNT(DISTINCT CASE WHEN ets.difficulty='medium' AND ets.status='pass' THEN ets.question_id END) * 2
   + COUNT(DISTINCT CASE WHEN ets.difficulty='easy'   AND ets.status='pass' THEN ets.question_id END) * 1
    ) AS weighted_score
FROM employability_track.employability_track_submission ets
JOIN public."user" u ON u.id = ets.user_id
JOIN public.college c ON c.id = u.college_id
JOIN employability_track.employability_track_question etq ON etq.question_id = ets.question_id
WHERE u.role = 'Student'
  AND etq.test_type_id = ANY(ARRAY[79, 84, 87])  -- replace for specific track
GROUP BY u.id, u.first_name, u.last_name, c.name
ORDER BY weighted_score DESC, problems_solved DESC, total_points DESC, success_rate DESC
LIMIT 50

PATTERN 4 — DAILY ACTIVITY (who submitted today / on a specific date):
SELECT
    (TRIM(u.first_name) || ' ' || TRIM(u.last_name)) AS name,
    c.name AS college,
    COUNT(DISTINCT CASE WHEN ets.status = 'pass' THEN ets.question_id END) AS problems_solved,
    COUNT(*) AS total_submissions,
    COUNT(CASE WHEN ets.status = 'pass' THEN 1 END) AS successful_submissions,
    ROUND(COUNT(CASE WHEN ets.status = 'pass' THEN 1 END)::numeric
          / NULLIF(COUNT(*), 0)::numeric * 100, 2) AS success_rate,
    SUM(ets.obtained_score) AS total_points,
    MAX(ets.create_at) AS last_submission_time
FROM employability_track.employability_track_submission ets
JOIN public."user" u ON u.id = ets.user_id
JOIN public.college c ON c.id = u.college_id
JOIN employability_track.employability_track_question etq ON etq.question_id = ets.question_id
WHERE u.role = 'Student'
  AND etq.test_type_id = ANY(ARRAY[79, 84, 87])
  AND DATE(ets.create_at) = CURRENT_DATE      -- replace with specific date if needed
GROUP BY u.id, u.first_name, u.last_name, c.name
ORDER BY problems_solved DESC, success_rate DESC
LIMIT 50

PATTERN 5 — PASS RATE BY DOMAIN (which domain has lowest/highest pass rate):
SELECT
    d.domain,
    COUNT(ets.id)                                                              AS total_submissions,
    COUNT(DISTINCT ets.user_id)                                                AS unique_students,
    COUNT(CASE WHEN ets.status = 'pass' THEN 1 END)                           AS passed,
    ROUND(COUNT(CASE WHEN ets.status = 'pass' THEN 1 END) * 100.0
          / NULLIF(COUNT(ets.id), 0), 2)                                       AS pass_rate_percent
FROM employability_track.employability_track_submission ets
JOIN public.domains d ON d.id = ets.domain_id
JOIN public."user" u ON u.id = ets.user_id
WHERE u.role = 'Student'
GROUP BY d.domain
ORDER BY pass_rate_percent ASC    -- ASC for weakest, DESC for strongest
LIMIT 50

PATTERN 6 — DOMAIN-SPECIFIC PASS RATE (filter to a named domain e.g. DSA, Python):
SELECT
    d.domain,
    COUNT(ets.id)                                                              AS total_submissions,
    COUNT(DISTINCT ets.user_id)                                                AS unique_students,
    COUNT(CASE WHEN ets.status = 'pass' THEN 1 END)                           AS passed,
    ROUND(COUNT(CASE WHEN ets.status = 'pass' THEN 1 END) * 100.0
          / NULLIF(COUNT(ets.id), 0), 2)                                       AS pass_rate_percent
FROM employability_track.employability_track_submission ets
JOIN public.domains d ON d.id = ets.domain_id
JOIN public."user" u ON u.id = ets.user_id
WHERE u.role = 'Student'
  AND (d.domain ILIKE '%data%' OR d.domain ILIKE '%structure%')  -- replace keywords
GROUP BY d.domain
ORDER BY total_submissions DESC
LIMIT 50

PATTERN 7 — SUBDOMAIN BREAKDOWN (weakest subtopics within a domain):
SELECT
    d.domain,
    qsd.name AS sub_domain,
    COUNT(ets.id)                                                              AS total_submissions,
    COUNT(DISTINCT ets.user_id)                                                AS unique_students,
    COUNT(CASE WHEN ets.status = 'pass' THEN 1 END)                           AS passed,
    ROUND(COUNT(CASE WHEN ets.status = 'pass' THEN 1 END) * 100.0
          / NULLIF(COUNT(ets.id), 0), 2)                                       AS pass_rate_percent
FROM employability_track.employability_track_submission ets
JOIN public.domains d ON d.id = ets.domain_id
JOIN public.question_sub_domain qsd ON qsd.id = ets.sub_domain_id
JOIN public."user" u ON u.id = ets.user_id
WHERE u.role = 'Student'
  AND (d.domain ILIKE '%keyword%')
GROUP BY d.domain, qsd.name
ORDER BY pass_rate_percent ASC
LIMIT 20

PATTERN 8 — STUDENT PROFILE (individual student's full activity):
SELECT
    (TRIM(u.first_name) || ' ' || TRIM(u.last_name)) AS name,
    c.name AS college,
    d.domain,
    qsd.name AS sub_domain,
    ets.title,
    ets.difficulty,
    ets.language,
    ets.status,
    ets.obtained_score,
    ets.points AS max_points,
    ets.create_at
FROM employability_track.employability_track_submission ets
JOIN public."user" u ON u.id = ets.user_id
JOIN public.college c ON c.id = u.college_id
LEFT JOIN public.domains d ON d.id = ets.domain_id
LEFT JOIN public.question_sub_domain qsd ON qsd.id = ets.sub_domain_id
WHERE u.role = 'Student'
  AND (TRIM(u.first_name) || ' ' || TRIM(u.last_name)) ILIKE '%fullname%'
ORDER BY ets.create_at DESC
LIMIT 50

PATTERN 9 — COMPONENT SCORE COMPARISON (coding % vs aptitude % vs verbal % per student):
SELECT
    cl.name,
    cl."collegeName"          AS college,
    cl."employabilityBand"    AS band,
    cl."employabilityScore"   AS overall_score,
    cl."codingPercentage"     AS coding_percent,
    cl."aptitudePercentage"   AS aptitude_percent,
    cl."englishPercentage"    AS verbal_percent,
    cl."collegeRank",
    cl."overallRank"
FROM public.combined_leaderboard cl
WHERE cl."employabilityBand" != 'NA'
ORDER BY cl."employabilityScore" DESC
LIMIT 50

PATTERN 10 — RANK QUERY (top students by college rank or overall rank):
SELECT
    cl.name,
    cl."collegeName"          AS college,
    cl."employabilityBand"    AS band,
    cl."employabilityScore"   AS employability_score_percent,
    cl."collegeRank",
    cl."overallRank"
FROM public.combined_leaderboard cl
WHERE cl."employabilityBand" != 'NA'
ORDER BY cl."collegeRank" ASC     -- use "overallRank" ASC for global rank
LIMIT 10
"""