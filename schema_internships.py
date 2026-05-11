# schema_internships.py — Internship domain schema context for LLM SQL generation
#
# Covers the internship programs module under schema: report
# Tables: report.internships, report.internship_domain, report.internship_batch,
#         report.internship_assessment, report.internship_live_sessions,
#         report.internship_type, report.internship_registrations,
#         report.internship_registrations_2025, report.internship_certificates,
#         report.internship_merit_certificates
#
# Assessment results flow through the same path as all other domains:
#   report.internship_assessment.assessment_id = hackathon_id
#   -> public.user_hackathon_participation.current_score
#
# Key facts (verified against production DB, 2026-05-04):
#   report.internships                — 18 internship programs (NO college_id)
#   report.internship_domain          — 149 sub-units; NO created_at column
#   report.internship_batch           — 91 rows; batch_id -> report.batch (shared)
#   report.internship_assessment      — 2,709 assessments (assessment_id = hackathon_id)
#   report.internship_live_sessions   — 1,506 session events (no per-user attendance)
#   report.internship_type            — 2 types: Short Term | Long Term
#   report.internship_registrations   — 11,850 rows (2024 cohort, has interested_stream)
#   report.internship_registrations_2025 — 17,559 rows (2025 cohort, NO interested_stream)
#   report.internship_certificates    — 10,941 completion certs (no internship_id FK)
#   report.internship_merit_certificates — 10,945 merit certs (no internship_id FK)
#
# SEPARATE OPERATIONAL SCHEMA (do NOT use for analytics):
#   internships.internship            — 24 rows, different column set (no type_id, no total_hours)
#   internships.internship_registrations_2025 — 5,308 rows (different from report.*)
#   internships.internship_registrations_2026 — 611 rows
#   All tables in the internships.* schema are operational, not analytics. Always use report.*.

INTERNSHIP_SCHEMA_CONTEXT = """
You have access to the Internships module. This module tracks structured internship
programs delivered by Blackbucks to college students.

THIS MODULE COVERS:
  - Internship programs: title, type (Short Term / Long Term), date range, total hours.
  - Domains: named sub-units of an internship (e.g. "FSD", "AIML & DS", "UI/UX"),
    with planned hours, live sessions, assessments, mock interviews, webinars.
  - Batches: named student groups linked to domains (same report.batch table as trainings).
  - Student rosters: batch_data stores student name, email, regno, college per batch.
  - Assessment scores: internship_assessment maps a domain to a hackathon assessment ID --
    use user_hackathon_participation to retrieve student scores for those assessments.
  - Registrations: internship_registrations (2024) and internship_registrations_2025 (2025)
    store student name, roll_number, college, and (2024 only) interested_stream.
  - Certificates: internship_certificates (completion) and internship_merit_certificates
    (merit) store certificate status, domain, and type -- but have no internship_id FK.
  - Live sessions: count of scheduled session events per domain.
  - Student feedback: satisfaction ratings and interactiveness percentages for internship
    live sessions, stored in report.student_responses.

NOT FOR:
  - Self-paced courses / course catalog (use course domain).
  - Employability Track / practice leaderboards (use emp domain).
  - POD / Problem of the Day (use pod domain).
  - Standalone hackathon events / MET / profiling tests (use assess domain).
  - Trainings/Placement programs with phase structure (use trainings domain).

IMPORTANT: There is a separate operational schema named 'internships' (e.g. internships.internship,
internships.internship_registrations_2025). DO NOT use that schema. All analytics queries must use
the 'report' schema tables documented below.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TABLES -- schema: report
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

-- Top-level internship program
report.internships (
    id                  INTEGER          -- primary key
    title               VARCHAR          -- internship name; use ILIKE for keyword search
    internship_type_id  INTEGER          -- FK to report.internship_type.id (nullable)
    start_date          DATE
    end_date            DATE
    total_hours         INTEGER
    banner              VARCHAR          -- image URL; not useful for analytics
    description         TEXT
    created_at          TIMESTAMP
    updated_at          TIMESTAMP
)
NOTE: internships has NO college_id column. College data is in registration tables only.

-- Internship type lookup (2 rows)
report.internship_type (
    id                INTEGER          -- 1 | 2
    internship_types  VARCHAR          -- 'Short Term' | 'Long Term'
)

-- Sub-unit of an internship (equivalent to phase in trainings)
report.internship_domain (
    id               INTEGER          -- primary key
    internship_id    INTEGER          -- FK to report.internships.id
    title            VARCHAR          -- domain name (e.g. 'FSD', 'AIML & DS', 'UI/UX')
    start_date       DATE
    end_date         DATE
    hours            DOUBLE PRECISION -- planned training hours
    live_sessions    DOUBLE PRECISION -- planned number of live sessions
    assessments      INTEGER          -- planned number of assessments
    met              DOUBLE PRECISION -- planned MET count
    daily_test       DOUBLE PRECISION
    weekly_test      DOUBLE PRECISION
    grand_test       DOUBLE PRECISION
    mock_interviews  DOUBLE PRECISION
    webinars         DOUBLE PRECISION
    student_reviews  DOUBLE PRECISION
    hours_covered    INTEGER          -- actual hours completed
)
NOTE: report.internship_domain has NO created_at column. Do not reference idom.created_at.
NOTE: Some domains have test/dummy titles (e.g. 'dummyfsd'). Use ILIKE filters to target
      real domain names. Do not add exclusion filters unless the user asks to skip test data.

-- Domain <-> Assessment join table (M:M)
-- assessment_id IS the hackathon_id used in public.user_hackathon_participation
report.internship_assessment (
    id             INTEGER          -- primary key
    domain_id      INTEGER          -- FK to report.internship_domain.id
    assessment_id  INTEGER          -- = hackathon_id in public.user_hackathon_participation
    create_at      TIMESTAMP
)
⛔ For top-scorer queries across multiple assessments → MUST use PATTERN I5 (CTE form).
   A flat JOIN query joining all tables in one block will exceed the 6-JOIN limit and be rejected.

-- Assessment metadata — joined via ia.assessment_id = h.id
public.hackathon (
    id                       INTEGER     -- primary key
    title                    VARCHAR     -- assessment/event name — use h.title NOT h.name (name does NOT exist)
    start_date               TIMESTAMPTZ -- when the event opens
    end_date                 TIMESTAMPTZ -- when the event closes
    status                   VARCHAR     -- 'published' or 'pending'
    registration_count       INTEGER     -- total scheduled/registered students (may be NULL)
    registered_college_count INTEGER     -- how many colleges registered
    test_type_id             INTEGER     -- type of test
    domain                   VARCHAR     -- UNRELIABLE free-text — NEVER filter by this
)
⚠️  CRITICAL: public.hackathon has NO "name" column. NO "points" column. NO "date_of_event" column.
   NEVER use h.points, h.name, or h.date_of_event — they will cause a query error.
   ✅ Use h.title for assessment name.
   ✅ Use h.start_date for event date.
   ✅ Use hackathon_with_score.score for max points.

-- Domain <-> Batch join table (M:M)
-- batch_id references report.batch -- the SAME table used by the trainings domain
report.internship_batch (
    id         INTEGER
    domain_id  INTEGER          -- FK to report.internship_domain.id
    batch_id   INTEGER          -- FK to report.batch.id (shared with trainings)
    create_at  TIMESTAMP
)

-- Scheduled live session events per domain (NOT per-user attendance)
report.internship_live_sessions (
    id         INTEGER
    domain_id  INTEGER          -- FK to report.internship_domain.id
    event_id   VARCHAR          -- external event UUID (e.g. Zoom meeting ID)
    create_at  TIMESTAMP
)

-- Event details for live sessions (shared with trainings domain)
report.events (
    id           VARCHAR          -- primary key (varchar) — joins to ils.event_id directly
    event_title  VARCHAR          -- display name e.g. 'IIDT FSD Day-1'
    num_hours    INTEGER          -- hours covered in this session
)
NOTE: Join via ils.event_id = e.id (both varchar — no cast needed).

-- Per-student feedback for internship live session events
-- Joins to internship_live_sessions via event_id (shared event_id namespace)
report.student_responses (
    id                    VARCHAR          -- primary key
    registration_number   VARCHAR          -- links to report.batch_data.regno
    event_id              VARCHAR          -- FK to report.internship_live_sessions.event_id
    interactive           VARCHAR          -- 'Yes' | 'No'
    feedback              VARCHAR          -- 'Extremely Satisfied' | 'Very Satisfied' | 'Satisfied'
                                           -- | 'Slightly Satisfied' | 'Needs Improvement'
    comments              VARCHAR
    created_at            TIMESTAMP
)
NOTE: report.student_responses has NO college_id column.
      Feedback is platform-wide by design — do NOT add a college filter to feedback queries.
      Filter only by internship title (via the join to report.internships).

-- Student INTEREST SIGN-UP table (NOT enrollment — see batch_data for enrolled students)
report.internship_registrations (
    id                INTEGER
    name              VARCHAR
    email             VARCHAR
    phone             VARCHAR
    roll_number       VARCHAR          -- joins to public.user.roll_number (~73% match)
    college_id        INTEGER          -- FK to public.college.id
    university_id     INTEGER
    degree            VARCHAR
    branch            VARCHAR
    current_year      INTEGER
    current_sem       VARCHAR
    interested_stream VARCHAR          -- free text: 'fsd', 'aiml', 'embeddedsystem-iot' etc.
    created_at        TIMESTAMP
)
⛔ DO NOT USE for enrollment counts, student counts, or headcounts per batch/domain.
   This table tracks interest sign-ups only — it has no link to batches or domains.
   For enrolled student counts → see PATTERN I3 (uses batch_data).

-- Student INTEREST SIGN-UP table 2025 cohort (NOT enrollment — see batch_data for enrolled students)
report.internship_registrations_2025 (
    id                INTEGER
    name              VARCHAR
    email             VARCHAR
    phone             VARCHAR
    roll_number       VARCHAR          -- joins to public.user.roll_number
    college_id        INTEGER          -- FK to public.college.id
    university_id     INTEGER
    degree            VARCHAR
    branch            VARCHAR
    yop               INTEGER          -- year of passing
    current_sem       VARCHAR
    created_at        TIMESTAMP
    updated_at        TIMESTAMP
    source            VARCHAR
)
NOTE: internship_registrations_2025 does NOT have an interested_stream column.
      For stream-wise counts in 2025, this table cannot be used.
⛔ DO NOT USE for enrollment counts, student counts, or headcounts per batch/domain.
   This table tracks interest sign-ups only — it has no link to batches or domains.
   For enrolled student counts → see PATTERN I3 (uses batch_data).

-- Shared batch tables (same as trainings domain)
report.batch (
    id           INTEGER          -- primary key
    batch_title  VARCHAR          -- batch name (e.g. 'LT 24 FSD', 'ST 24 Business Analytics')
    created_at   TIMESTAMP
)

report.batch_data (
    id          INTEGER
    batch_id    INTEGER          -- FK to report.batch.id
    name        VARCHAR          -- student full name
    email       VARCHAR
    regno       VARCHAR          -- joins to public.user.roll_number (LEFT JOIN; not all match)
    phone       VARCHAR
    college_id  INTEGER          -- FK to public.college.id (INTEGER -- no cast needed)
    create_at   TIMESTAMP
)

-- Completion certificates (no internship_id FK -- filter by domain_registered text)
report.internship_certificates (
    id                  INTEGER
    name                VARCHAR          -- student name
    email               VARCHAR
    reg_no              VARCHAR          -- registration number
    domain_registered   VARCHAR          -- free text: 'AI-ML-DS', 'FSD', etc.
    internship_type     VARCHAR          -- 'ONLINE' | 'OFFLINE'
    status              VARCHAR          -- 'paid' | 'free'
    created_at          TIMESTAMP
    certificate_link    TEXT
)

-- Merit certificates (same structure as internship_certificates)
report.internship_merit_certificates (
    id                  INTEGER
    name                VARCHAR
    email               VARCHAR
    reg_no              VARCHAR
    domain_registered   VARCHAR
    internship_type     VARCHAR
    eligibility         VARCHAR
    created_at          TIMESTAMP
    certificate_link    TEXT
)

NOTE: report.internship_certificates_2025 also exists but has only 1 row (test data).
      Use report.internship_certificates for all certificate queries.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
JOIN PATHS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

report.internships        -> report.internship_type        via tt.id = i.internship_type_id
report.internship_domain  -> report.internships            via idom.internship_id = i.id
report.internship_assessment -> report.internship_domain   via ia.domain_id = idom.id
report.internship_assessment -> public.user_hackathon_participation via uhp.hackathon_id = ia.assessment_id
report.internship_batch   -> report.internship_domain      via ib.domain_id = idom.id
report.internship_batch   -> report.batch                  via b.id = ib.batch_id
report.batch              -> report.batch_data             via bd.batch_id = b.id
report.batch_data         -> public.user                   via u.roll_number = bd.regno (LEFT JOIN)
report.batch_data         -> public.college                via col.id = bd.college_id (INTEGER)
report.internship_live_sessions -> report.internship_domain via ils.domain_id = idom.id
report.student_responses        -> report.internship_live_sessions  via sr.event_id = ils.event_id
report.internship_live_sessions -> report.events                    via e.id = ils.event_id
report.student_responses        -> report.batch_data                via sr.registration_number = bd.regno
report.internship_registrations -> public.college          via col.id = ir.college_id
report.internship_registrations -> public.user             via u.roll_number = ir.roll_number (LEFT JOIN)
public.user               -> public.college                via u.college_id = col.id

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CRITICAL RULES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. NO COLLEGE_ID ON INTERNSHIPS -- report.internships has no college_id column.
   To filter by college for batch/enrollment queries: join via batch_data.college_id.
   To filter by college for registration queries only: join via internship_registrations.college_id.
   DO NOT attempt i.college_id -- it does not exist.

2. NO CREATED_AT ON INTERNSHIP_DOMAIN -- report.internship_domain has no created_at column.
   Do NOT reference idom.created_at in any query. This column does not exist.

3. NO RANK COLUMN -- user_hackathon_participation has no pre-computed rank.
   Always compute on the fly:
   RANK() OVER (PARTITION BY uhp.hackathon_id ORDER BY uhp.current_score DESC) AS rank

4. BATCH_DATA TO USER LINK -- regno does not always match a public.user row (~73% match).
   Always use LEFT JOIN:
   LEFT JOIN public.user u ON u.roll_number = bd.regno AND u.role = 'Student'

5. STUDENT NAME format (consistent with all domains):
   (TRIM(u.first_name) || ' ' || TRIM(u.last_name)) AS name

6. ALWAYS filter u.role = 'Student' when joining public.user for student analytics.

7. INTERNSHIP_LIVE_SESSIONS has NO user_id -- tracks scheduled session events, not
   per-student attendance. Use COUNT(ils.id) as "live_session_count" only.
   Do NOT attempt to join it to user data.

8. CERTIFICATE TABLES have NO internship_id FK. They cannot be joined back to
   report.internships or report.internship_domain. Filter only by domain_registered
   (free text) or internship_type ('ONLINE'/'OFFLINE') or status ('paid'/'free').

9. TWO REGISTRATION COHORTS:
   - 2024: report.internship_registrations -- has interested_stream column
   - 2025: report.internship_registrations_2025 -- NO interested_stream column
   Query them separately or use UNION ALL for combined counts (same column set except
   internship_registrations_2025 has yop instead of current_year).
   For stream-wise filtering: use report.internship_registrations (2024 only).

10. INTERNSHIP_DOMAIN may contain test/dummy rows -- do not add WHERE exclusion filters
    unless the user explicitly asks to skip test data. Use ILIKE filters on domain title
    to target specific real domains.

11. SOME ASSESSMENTS HAVE ZERO PARTICIPANTS -- internship_assessment.assessment_id has
    a valid hackathon_id, but some assessments have 0 participants in
    user_hackathon_participation. Add HAVING COUNT(uhp.user_id) > 0 when aggregating
    to skip empty assessments.

12. INTERNSHIP / DOMAIN NAME SEARCH -- split into words with AND ILIKE:
    (i.title ILIKE '%word1%' AND i.title ILIKE '%word2%')
    NEVER use a single ILIKE with the full phrase.

13. DO NOT USE internships.* SCHEMA -- the operational schema 'internships' (tables like
    internships.internship, internships.internship_registrations_2025) has different
    structure and is not for analytics. Always use report.* tables only.

14. CRITICAL -- JOIN LIMIT: The query validator rejects any query with more than 6 JOINs.

    For student identity, pick EXACTLY ONE path -- never both:
      Path A: public.user        -- gives first_name, last_name, email, college_id
      Path B: report.batch_data  -- gives name, email, regno, college_id

    If you pick Path A -- do NOT also join report.batch_data.
    If you pick Path B -- do NOT also join public.user.

    For college name:
      - If you have remaining JOIN budget: JOIN public.college via u.college_id or bd.college_id.
      - If you are already at 6 JOINs (e.g. I6: batch_data + internship_batch + internship_domain
        + internship_assessment + user + uhp = 6 JOINs), you have ZERO remaining budget.
        Use a scalar subquery instead -- it costs NO JOINs:
        (SELECT c.name FROM public.college c WHERE c.id = u.college_id) AS college
    Never join public.college twice.

15. Today's date: {today}

16. CRITICAL — FUZZY TITLE/NAME MATCHING:
    Never filter by name or title using a single ILIKE with the full typed phrase.
    Faculty may omit spaces, dashes, or parts of the full name.
    Instead split the search term into individual meaningful keywords and apply a
    separate ILIKE condition for each keyword:
      (i.title ILIKE '%word1%' AND i.title ILIKE '%word2%')
    This ensures minor formatting or spelling differences between what faculty type
    and what is stored in the DB do not cause 0 rows.

17. ENROLLMENT COUNTS vs REGISTRATION COUNTS — these are DIFFERENT things:
    - report.internship_registrations / internship_registrations_2025:
      Use ONLY when the question is explicitly about sign-ups, applications, or
      interest registrations. These tables are NOT linked to batches or domains.
      They cannot tell you how many students are actively enrolled in a specific
      internship domain or batch.
    - report.batch_data:
      Use for ALL questions about active enrollment, student lists, headcount per
      batch, students in a specific internship domain, or student count per college
      within an ongoing internship. This is the ONLY source for enrolled students.
    NEVER use internship_registrations to answer "how many students are in [internship]"
    or "student count for [batch]" — those questions require batch_data.

18. TEST TYPE IDs — use these constants when filtering hackathon by assessment type:
    test_type_id IN (6, 54, 12)  → Employability / MET assessments
    test_type_id IN (13, 42, 43) → Daily tests
    test_type_id = 81            → Grand tests
    test_type_id = 80            → Assignments
    test_type_id = 40            → Placement tests
    Always join public.hackathon h ON h.id = ia.assessment_id to access test_type_id.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
QUERY PATTERNS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

PATTERN I1 -- INTERNSHIP CATALOG (list programs, filter by type):
-- Use when faculty asks: "list all internships", "show long term internships",
-- "what internship programs are available", "internships in 2024/2025".
SELECT
    i.id,
    i.title,
    tt.internship_types AS type,
    i.start_date,
    i.end_date,
    i.total_hours,
    i.description
FROM report.internships i
LEFT JOIN report.internship_type tt ON tt.id = i.internship_type_id
-- Uncomment for type filter:
-- WHERE tt.internship_types ILIKE '%Long Term%'
-- Uncomment for title filter:
-- WHERE (i.title ILIKE '%word1%' AND i.title ILIKE '%word2%')
ORDER BY i.start_date DESC
LIMIT 20
NOTE: internships has NO college_id -- this table cannot be filtered by college directly.

PATTERN I2 -- DOMAINS IN AN INTERNSHIP (structure):
-- Use when faculty asks: "what domains are in [internship]", "show internship structure",
-- "what are the streams in [internship]", "how many domains in [internship]".
SELECT
    idom.id,
    idom.title AS domain_title,
    i.title AS internship_title,
    idom.start_date,
    idom.end_date,
    idom.hours,
    idom.live_sessions AS planned_live_sessions,
    idom.assessments AS planned_assessments,
    idom.mock_interviews,
    idom.webinars,
    idom.hours_covered
FROM report.internship_domain idom
JOIN report.internships i ON i.id = idom.internship_id
-- WHERE (i.title ILIKE '%word1%' AND i.title ILIKE '%word2%')
ORDER BY idom.start_date ASC

PATTERN I3 -- BATCHES IN AN INTERNSHIP (student count per batch, filter by internship and/or college):
-- Use when faculty asks: "what batches are in [internship]", "list batches for [domain]",
-- "how many students per batch in [internship]", "how many students enrolled in [internship]",
-- "student count for [college] in [internship]", "how many students are in [internship]",
-- "enrollment count for [internship]", "total students in [internship]".
-- ALWAYS use this exact join chain for enrollment counts — batch_data is the ONLY correct
-- source. Do NOT use internship_registrations for this question (see Rule 17).
-- Join chain: batch_data → batch → internship_batch → internship_domain → internships
-- Filter by college using bd.college_id; filter by internship using i.title ILIKE.

-- Example: students per batch in internship matching 'FSD' at a college matching 'NBKR'
SELECT
    b.batch_title,
    idom.title          AS domain_title,
    i.title             AS internship_title,
    COUNT(bd.id)        AS student_count
FROM report.batch_data bd
JOIN report.batch b             ON b.id = bd.batch_id
JOIN report.internship_batch ib ON ib.batch_id = b.id
JOIN report.internship_domain idom ON idom.id = ib.domain_id
JOIN report.internships i       ON i.id = idom.internship_id
WHERE bd.college_id = (
    SELECT id FROM public.college WHERE name ILIKE '%NBKR%' LIMIT 1
)
AND (i.title ILIKE '%FSD%')
GROUP BY b.batch_title, idom.title, i.title
ORDER BY b.batch_title

-- Replace '%NBKR%' with a keyword from the college name.
-- Replace '%FSD%' with keywords from the internship title.
-- Remove the WHERE entirely if no college or internship filter is needed.

PATTERN I4 -- ASSESSMENT SCORES FOR AN INTERNSHIP DOMAIN (ranked):
-- Use when faculty asks: "scores in [domain] assessment", "performance in [internship] domain",
-- "who passed the [internship] test", "assessment results for [domain]".
SELECT
    idom.title AS domain_title,
    ia.assessment_id AS hackathon_id,
    (TRIM(u.first_name) || ' ' || TRIM(u.last_name)) AS student_name,
    col.name AS college,
    uhp.current_score,
    RANK() OVER (PARTITION BY ia.assessment_id ORDER BY uhp.current_score DESC) AS rank
FROM report.internship_domain idom
JOIN report.internships i ON i.id = idom.internship_id
JOIN report.internship_assessment ia ON ia.domain_id = idom.id
JOIN public.user_hackathon_participation uhp ON uhp.hackathon_id = ia.assessment_id
JOIN public.user u ON u.id = uhp.user_id
LEFT JOIN public.college col ON col.id = u.college_id
WHERE u.role = 'Student'
-- AND (i.title ILIKE '%word1%' AND i.title ILIKE '%word2%')
-- AND (idom.title ILIKE '%word1%')
ORDER BY ia.assessment_id, rank
LIMIT 50

PATTERN I5 -- TOP SCORERS ACROSS ALL DOMAINS IN AN INTERNSHIP (normalized score %):
-- Use when faculty asks: "top students in [internship]", "leaderboard for [internship]",
-- "who performed best in [internship]", "best scorers overall", "average score percentage",
-- "who scored highest across all assessments", "rank students by performance in [internship]".
-- avg_score_pct is normalized against max possible score per assessment — more accurate than raw score.
-- Use this pattern (not fresh SQL) whenever ranking students across multiple internship assessments.
-- Score denominator: hackathon_with_score.score (materialized view) — NOT round_with_score.
-- User resolved via bd.email = u.email (NOT bd.regno = u.roll_number — email has higher match rate).
-- CRITICAL: public.college has NO city column — NEVER filter by c.city. Filter by c.id only.
-- To filter by college: uncomment the bd.college_id WHERE clause.
WITH student_scores AS (
    SELECT
        bd.id           AS bd_id,
        bd.name         AS bd_name,
        bd.email        AS bd_email,
        bd.college_id,
        uhp.hackathon_id,
        MAX(ROUND(
            uhp.current_score * 100.0 /
            CASE WHEN COALESCE(hw.score, 0) = 0 THEN 1 ELSE hw.score END
        , 2)) AS best_pct
    FROM report.internship_assessment ia
    JOIN report.internship_domain idom  ON idom.id = ia.domain_id
    JOIN report.internships i           ON i.id = idom.internship_id
    JOIN report.internship_batch ib     ON ib.domain_id = idom.id
    JOIN report.batch b                 ON b.id = ib.batch_id
    JOIN report.batch_data bd           ON bd.batch_id = b.id
    LEFT JOIN public.hackathon_with_score hw ON hw.id = ia.assessment_id
    LEFT JOIN public.user_hackathon_participation uhp
        ON uhp.hackathon_id = ia.assessment_id
        AND uhp.user_id = (
            SELECT u.id FROM public.user u
            WHERE u.email = bd.email
            LIMIT 1
        )
    -- WHERE (i.title ILIKE '%word1%' AND i.title ILIKE '%word2%')
    -- AND bd.college_id = (SELECT id FROM public.college WHERE name ILIKE '%college_keyword%' LIMIT 1)
    GROUP BY bd.id, bd.name, bd.email, bd.college_id, uhp.hackathon_id
)
SELECT
    bd_name                                                              AS student_name,
    (SELECT c.name FROM public.college c WHERE c.id = ss.college_id)    AS college,
    COUNT(hackathon_id)                                                  AS assessments_taken,
    ROUND(AVG(best_pct), 2)                                              AS avg_score_pct
FROM student_scores ss
GROUP BY bd_id, bd_name, bd_email, college_id
ORDER BY avg_score_pct DESC NULLS LAST
LIMIT 20

PATTERN I6 -- STUDENT PERFORMANCE SUMMARY FOR A BATCH:
-- Use when faculty asks: "performance summary for [batch]", "how did [batch] students do",
-- "scores for students in [batch]", "batch results for [internship]",
-- "students in [batch] with college name and ranking", "batch leaderboard".
-- All students in the batch are returned; those with no UHP records show 0 for scores.
-- BUDGET: this pattern uses all 6 JOINs (batch_data + internship_batch + internship_domain
--   + internship_assessment + user + uhp). For college name use a scalar subquery,
--   NOT a 7th JOIN to public.college.
SELECT
    COALESCE((TRIM(u.first_name) || ' ' || TRIM(u.last_name)), bd.name) AS student_name,
    bd.email,
    bd.regno,
    (SELECT c.name FROM public.college c WHERE c.id = u.college_id) AS college,
    COUNT(DISTINCT uhp.hackathon_id) AS assessments_completed,
    COALESCE(SUM(uhp.current_score), 0) AS total_score,
    ROUND(COALESCE(AVG(uhp.current_score), 0)::numeric, 2) AS avg_score,
    RANK() OVER (ORDER BY COALESCE(SUM(uhp.current_score), 0) DESC NULLS LAST) AS overall_rank
FROM report.batch b
JOIN report.batch_data bd ON bd.batch_id = b.id
JOIN report.internship_batch ib ON ib.batch_id = b.id
JOIN report.internship_domain idom ON idom.id = ib.domain_id
JOIN report.internship_assessment ia ON ia.domain_id = idom.id
LEFT JOIN public.user u ON u.roll_number = bd.regno AND u.role = 'Student'
LEFT JOIN public.user_hackathon_participation uhp
    ON uhp.hackathon_id = ia.assessment_id AND uhp.user_id = u.id
-- WHERE (b.batch_title ILIKE '%word1%' AND b.batch_title ILIKE '%word2%')
GROUP BY bd.id, bd.name, bd.email, bd.regno, u.id, u.first_name, u.last_name, u.college_id
ORDER BY total_score DESC NULLS LAST
LIMIT 50

PATTERN I7 -- LIVE SESSION COUNT PER DOMAIN:
-- Use when faculty asks: "how many live sessions in [internship]", "session schedule",
-- "how many sessions were held in [domain]", "live session count".
-- NOTE: internship_live_sessions tracks scheduled events, not per-student attendance.
SELECT
    idom.title AS domain_title,
    i.title AS internship_title,
    idom.live_sessions AS planned_sessions,
    COUNT(ils.id) AS scheduled_session_events
FROM report.internship_domain idom
JOIN report.internships i ON i.id = idom.internship_id
LEFT JOIN report.internship_live_sessions ils ON ils.domain_id = idom.id
-- WHERE (i.title ILIKE '%word1%' AND i.title ILIKE '%word2%')
GROUP BY idom.id, idom.title, i.title, idom.live_sessions
ORDER BY i.title, idom.start_date

PATTERN I8 -- REGISTRATION COUNT BY COLLEGE:
-- Use when faculty asks: "how many students registered", "registrations by college",
-- "which colleges registered for [internship]", "registration count for [stream]".
-- NOTE: Use internship_registrations for 2024 (has interested_stream).
--       Use internship_registrations_2025 for 2025 (no interested_stream).
--       Use UNION ALL for combined count across both years.
SELECT
    col.name AS college,
    COUNT(ir.id) AS registered_students,
    COUNT(DISTINCT ir.interested_stream) AS streams_chosen
FROM report.internship_registrations ir
LEFT JOIN public.college col ON col.id = ir.college_id
-- WHERE ir.interested_stream ILIKE '%fsd%'
GROUP BY col.id, col.name
ORDER BY registered_students DESC
LIMIT 20

PATTERN I9 -- CERTIFICATE STATISTICS:
-- Use when faculty asks: "how many certificates issued", "certificate count by domain",
-- "who got merit certificates", "certificate breakdown".
-- NOTE: These tables have NO internship_id FK -- filter by domain_registered text only.
SELECT
    domain_registered,
    internship_type,
    status,
    COUNT(*) AS certificate_count
FROM report.internship_certificates
-- WHERE domain_registered ILIKE '%AI%'
-- WHERE internship_type = 'ONLINE'
GROUP BY domain_registered, internship_type, status
ORDER BY certificate_count DESC
LIMIT 20
NOTE: For merit certificates use report.internship_merit_certificates (same columns,
      plus eligibility field). Cannot join certs back to internship programs by ID.

PATTERN I10 -- FEEDBACK & INTERACTIVENESS FOR AN INTERNSHIP:
-- Use when faculty asks: "feedback for [internship]", "average satisfaction in [internship]",
-- "interactiveness percentage for [internship]", "how engaged were students in [internship] sessions",
-- "student response scores for [internship]".
-- CRITICAL: No college_id filter — feedback is platform-wide by design.
--           Do NOT add a WHERE clause on college even if the faculty mentions a college.
-- Feedback scale: Extremely Satisfied=5, Very Satisfied=4, Satisfied=3,
--                 Slightly Satisfied=2, Needs Improvement=1
SELECT
    ROUND(AVG(CASE sr.feedback
        WHEN 'Extremely Satisfied' THEN 5
        WHEN 'Very Satisfied'      THEN 4
        WHEN 'Satisfied'           THEN 3
        WHEN 'Slightly Satisfied'  THEN 2
        WHEN 'Needs Improvement'   THEN 1
        ELSE 0 END), 2)                                                AS average_feedback_score,
    ROUND(AVG(CASE sr.interactive WHEN 'Yes' THEN 1 ELSE 0 END) * 100, 2) AS avg_interactiveness_pct,
    COUNT(sr.id)                                                       AS total_responses
FROM report.student_responses sr
INNER JOIN report.internship_live_sessions ils ON ils.event_id = sr.event_id
INNER JOIN report.internship_domain idom       ON idom.id = ils.domain_id
INNER JOIN report.internships i                ON i.id = idom.internship_id
-- WHERE (i.title ILIKE '%word1%' AND i.title ILIKE '%word2%')

PATTERN I11 -- PROGRESS OVERVIEW FOR AN INTERNSHIP (planned vs completed counts):
-- Use when faculty asks: "progress overview for [internship]", "how many sessions completed",
-- "how many assessments completed in [internship]", "completion status for [internship]",
-- "planned vs completed for [internship]".
-- NOTE: These counts are platform-wide — no college filter is possible here by design.
WITH DomainSummary AS (
    SELECT
        i.id AS internship_id,
        SUM(COALESCE(idom.live_sessions, 0) + COALESCE(idom.student_reviews, 0) + COALESCE(idom.mock_interviews, 0)) AS total_live_sessions,
        SUM(COALESCE(idom.assessments, 0)) AS total_assessments
    FROM report.internship_domain idom
    INNER JOIN report.internships i ON idom.internship_id = i.id
    -- WHERE (i.title ILIKE '%word1%' AND i.title ILIKE '%word2%')
    GROUP BY i.id
),
EventCount AS (
    SELECT
        i.id AS internship_id,
        COUNT(ils.event_id) AS completed_live_sessions
    FROM report.internship_live_sessions ils
    INNER JOIN report.internship_domain idom ON ils.domain_id = idom.id
    INNER JOIN report.internships i ON idom.internship_id = i.id
    -- WHERE (i.title ILIKE '%word1%' AND i.title ILIKE '%word2%')
    GROUP BY i.id
),
AssessmentDetails AS (
    SELECT
        i.id AS internship_id,
        COUNT(CASE WHEN h.test_type_id IN (6, 54, 12) THEN 1 END)    AS completed_assessments,
        COUNT(CASE WHEN h.test_type_id IN (13, 42, 43) THEN 1 END)   AS completed_daily_tests,
        COUNT(CASE WHEN h.test_type_id = 81 THEN 1 END)              AS completed_grand_tests,
        COUNT(CASE WHEN h.test_type_id = 80 THEN 1 END)              AS completed_assignments,
        COUNT(CASE WHEN h.test_type_id = 40 THEN 1 END)              AS completed_placement_tests
    FROM report.internship_assessment ia
    INNER JOIN report.internship_domain idom ON ia.domain_id = idom.id
    INNER JOIN public.hackathon h ON ia.assessment_id = h.id
    INNER JOIN report.internships i ON idom.internship_id = i.id
    -- WHERE (i.title ILIKE '%word1%' AND i.title ILIKE '%word2%')
    GROUP BY i.id
)
SELECT
    COALESCE(ds.total_live_sessions, 0)       AS total_live_sessions,
    COALESCE(ec.completed_live_sessions, 0)   AS completed_live_sessions,
    COALESCE(ds.total_assessments, 0)         AS total_assessments,
    COALESCE(ad.completed_assessments, 0)     AS completed_assessments,
    COALESCE(ad.completed_daily_tests, 0)     AS completed_daily_tests,
    COALESCE(ad.completed_grand_tests, 0)     AS completed_grand_tests,
    COALESCE(ad.completed_assignments, 0)     AS completed_assignments,
    COALESCE(ad.completed_placement_tests, 0) AS completed_placement_tests
FROM DomainSummary ds
LEFT JOIN EventCount ec ON ds.internship_id = ec.internship_id
LEFT JOIN AssessmentDetails ad ON ds.internship_id = ad.internship_id
WHERE ds.internship_id = (
    SELECT id FROM report.internships
    WHERE (title ILIKE '%word1%' AND title ILIKE '%word2%')
    ORDER BY LENGTH(title) ASC LIMIT 1
)

PATTERN I12 -- DOMAIN SUMMARY TABLE FOR AN INTERNSHIP (per-domain activity counts):
-- Use when faculty asks: "domain summary for [internship]", "how many assessments per domain",
-- "daily tests per domain in [internship]", "live sessions per domain",
-- "activity breakdown by domain for [internship]".
-- NOTE: Assessment and live session counts are global per domain (not college-scoped).
--       College filter only controls which domains appear (via batch_data).
--       internship_id filter applied in final SELECT — not inside domain_data CTE.
WITH domain_data AS (
    SELECT
        idom.id,
        idom.title,
        idom.internship_id
    FROM report.internship_domain idom
    INNER JOIN report.internship_batch ib ON idom.id = ib.domain_id
    INNER JOIN report.batch_data bd       ON ib.batch_id = bd.batch_id
    INNER JOIN public.college c           ON bd.college_id = c.id
    WHERE c.id = (
        SELECT id FROM public.college WHERE name ILIKE '%college_keyword%' LIMIT 1
    )
    GROUP BY idom.id, idom.title, idom.internship_id
),
assessment_data AS (
    SELECT
        ia.domain_id,
        COUNT(ia.assessment_id)                                             AS assessment_count,
        SUM(CASE WHEN h.test_type_id IN (13, 42, 43) THEN 1 ELSE 0 END)   AS daily_tests,
        SUM(CASE WHEN h.test_type_id = 81 THEN 1 ELSE 0 END)              AS grand_tests,
        SUM(CASE WHEN h.test_type_id = 80 THEN 1 ELSE 0 END)              AS assignments,
        SUM(CASE WHEN h.test_type_id = 40 THEN 1 ELSE 0 END)              AS placement_tests,
        SUM(CASE WHEN h.test_type_id IN (6, 54, 12) THEN 1 ELSE 0 END)    AS mets
    FROM report.internship_assessment ia
    INNER JOIN public.hackathon h ON ia.assessment_id = h.id
    GROUP BY ia.domain_id
),
live_sessions_data AS (
    SELECT
        domain_id,
        COUNT(event_id) AS live_session_count
    FROM report.internship_live_sessions
    GROUP BY domain_id
)
SELECT
    dd.title                                        AS domain_title,
    COALESCE(ad.assessment_count, 0)                AS assessment_count,
    COALESCE(ad.daily_tests, 0)                     AS daily_tests,
    COALESCE(ad.grand_tests, 0)                     AS grand_tests,
    COALESCE(ad.assignments, 0)                     AS assignments,
    COALESCE(ad.placement_tests, 0)                 AS placement_tests,
    COALESCE(ad.mets, 0)                            AS mets,
    COALESCE(lsd.live_session_count, 0)             AS live_session_count
FROM domain_data dd
LEFT JOIN assessment_data ad      ON dd.id = ad.domain_id
LEFT JOIN live_sessions_data lsd  ON dd.id = lsd.domain_id
WHERE dd.internship_id = (
    SELECT id FROM report.internships
    WHERE (title ILIKE '%word1%' AND title ILIKE '%word2%')
    ORDER BY LENGTH(title) ASC LIMIT 1
)
ORDER BY dd.title

PATTERN I13 -- INACTIVE STUDENTS IN A DOMAIN (zero assessment attempts):
-- Use when faculty asks: "who hasn't attempted any assessment in [domain]",
-- "inactive students in [internship] domain", "students with no submissions in [domain]",
-- "who hasn't participated in [domain] assessments", "inactive students count in [domain]".
-- Returns students enrolled in the domain who have zero assessment attempts.
-- college filter via bd.college_id; domain filter via idom.title ILIKE.
SELECT
    bd.name         AS student_name,
    bd.email,
    bd.regno,
    bd.phone,
    (SELECT c.name FROM public.college c WHERE c.id = bd.college_id) AS college
FROM report.batch_data bd
JOIN report.batch b             ON b.id = bd.batch_id
JOIN report.internship_batch ib ON ib.batch_id = b.id
JOIN report.internship_domain idom ON idom.id = ib.domain_id
JOIN report.internships i       ON i.id = idom.internship_id
WHERE bd.college_id = (
    SELECT id FROM public.college WHERE name ILIKE '%college_keyword%' LIMIT 1
)
AND (idom.title ILIKE '%domain_keyword%')
AND (i.title ILIKE '%word1%' AND i.title ILIKE '%word2%')
AND NOT EXISTS (
    SELECT 1
    FROM report.internship_assessment ia
    JOIN public.user u ON u.email = bd.email
    JOIN public.user_hackathon_participation uhp
        ON uhp.hackathon_id = ia.assessment_id AND uhp.user_id = u.id
    WHERE ia.domain_id = idom.id
)
ORDER BY bd.name
LIMIT 50

PATTERN I14 -- LIVE SESSION ATTENDANCE SUMMARY PER EVENT IN A DOMAIN:
-- Use when faculty asks: "attendance summary for [domain] sessions",
-- "how many students attended each session in [domain]",
-- "live session attendance for [internship] domain", "who attended [domain] sessions",
-- "attendance rate per session in [domain]".
-- NOTE: Attendance may show 0% for some colleges if their registration number format
--       does not match the format stored in student_responses.registration_number.
--       This is consistent with what the dashboard shows and is a known data limitation.
-- NOTE: present/absent is matched via sr.registration_number = bd.regno.
--       college filter via bd.college_id; no college filter on student_responses.
WITH session_students AS (
    SELECT
        ils.id          AS session_id,
        ils.event_id,
        COUNT(DISTINCT bd.id) AS total_students
    FROM report.internship_live_sessions ils
    JOIN report.internship_domain idom ON idom.id = ils.domain_id
    JOIN report.internships i          ON i.id = idom.internship_id
    JOIN report.internship_batch ib    ON ib.domain_id = idom.id
    JOIN report.batch b                ON b.id = ib.batch_id
    JOIN report.batch_data bd          ON bd.batch_id = b.id
    WHERE bd.college_id = (
        SELECT id FROM public.college WHERE name ILIKE '%college_keyword%' LIMIT 1
    )
    AND (idom.title ILIKE '%domain_keyword%')
    AND (i.title ILIKE '%word1%' AND i.title ILIKE '%word2%')
    GROUP BY ils.id, ils.event_id
),
session_present AS (
    SELECT
        ils.id          AS session_id,
        COUNT(DISTINCT sr.registration_number) AS present_count
    FROM report.internship_live_sessions ils
    JOIN report.internship_domain idom ON idom.id = ils.domain_id
    JOIN report.internships i          ON i.id = idom.internship_id
    JOIN report.internship_batch ib    ON ib.domain_id = idom.id
    JOIN report.batch b                ON b.id = ib.batch_id
    JOIN report.batch_data bd          ON bd.batch_id = b.id
    LEFT JOIN report.student_responses sr ON sr.event_id = ils.event_id
        AND sr.registration_number = bd.regno
    WHERE bd.college_id = (
        SELECT id FROM public.college WHERE name ILIKE '%college_keyword%' LIMIT 1
    )
    AND (idom.title ILIKE '%domain_keyword%')
    AND (i.title ILIKE '%word1%' AND i.title ILIKE '%word2%')
    GROUP BY ils.id
)
SELECT
    e.event_title,
    ss.total_students,
    COALESCE(sp.present_count, 0)                                           AS present,
    ss.total_students - COALESCE(sp.present_count, 0)                       AS absent,
    ROUND(COALESCE(sp.present_count, 0) * 100.0 /
        NULLIF(ss.total_students, 0), 2)                                    AS attendance_rate
FROM session_students ss
JOIN session_present sp ON sp.session_id = ss.session_id
JOIN report.events e    ON e.id = ss.event_id
ORDER BY ss.session_id
LIMIT 50

PATTERN I15 -- DAILY TEST SCORES FOR STUDENTS IN AN INTERNSHIP DOMAIN (avg % per student):
-- Use when faculty asks: "daily test scores in [domain]", "daily test results for [internship]",
-- "how did students do on daily tests in [domain]", "daily test performance in [internship]",
-- "average daily test score in [domain]".
-- Returns avg normalized score % per student across all daily tests in the domain.
-- test_type_id IN (13, 42, 43) = daily tests — filtered via subquery, no extra JOIN.
SELECT
    (TRIM(u.first_name) || ' ' || TRIM(u.last_name))   AS student_name,
    u.email,
    (SELECT c.name FROM public.college c WHERE c.id = u.college_id) AS college,
    COUNT(DISTINCT uhp.hackathon_id)                    AS tests_taken,
    ROUND(AVG(uhp.current_score * 100.0 /
        CASE WHEN COALESCE(hw.score, 0) = 0 THEN 1 ELSE hw.score END
    ), 2)                                               AS avg_score_pct
FROM report.internship_domain idom
JOIN report.internships i           ON i.id = idom.internship_id
JOIN report.internship_assessment ia ON ia.domain_id = idom.id
JOIN public.user_hackathon_participation uhp ON uhp.hackathon_id = ia.assessment_id
JOIN public.user u                  ON u.id = uhp.user_id
LEFT JOIN public.hackathon_with_score hw ON hw.id = ia.assessment_id
WHERE u.role = 'Student'
AND ia.assessment_id IN (
    SELECT id FROM public.hackathon WHERE test_type_id IN (13, 42, 43)
)
-- AND (idom.title ILIKE '%domain_keyword%')
-- AND (i.title ILIKE '%word1%' AND i.title ILIKE '%word2%')
-- AND u.college_id = (SELECT id FROM public.college WHERE name ILIKE '%college_keyword%' LIMIT 1)
GROUP BY u.id, u.first_name, u.last_name, u.email, u.college_id
ORDER BY avg_score_pct DESC
LIMIT 50

PATTERN I16 -- EMPLOYABILITY TEST SCORES FOR STUDENTS IN AN INTERNSHIP DOMAIN (avg % per student):
-- Use when faculty asks: "employability test scores in [domain]", "MET scores in [internship]",
-- "employability test results for [internship] domain", "employability test performance in [domain]",
-- "average employability score in [domain]".
-- Returns avg normalized score % per student across all employability tests in the domain.
-- test_type_id IN (6, 54, 12) = employability/MET tests — filtered via subquery, no extra JOIN.
SELECT
    (TRIM(u.first_name) || ' ' || TRIM(u.last_name))   AS student_name,
    u.email,
    (SELECT c.name FROM public.college c WHERE c.id = u.college_id) AS college,
    COUNT(DISTINCT uhp.hackathon_id)                    AS tests_taken,
    ROUND(AVG(uhp.current_score * 100.0 /
        CASE WHEN COALESCE(hw.score, 0) = 0 THEN 1 ELSE hw.score END
    ), 2)                                               AS avg_score_pct
FROM report.internship_domain idom
JOIN report.internships i           ON i.id = idom.internship_id
JOIN report.internship_assessment ia ON ia.domain_id = idom.id
JOIN public.user_hackathon_participation uhp ON uhp.hackathon_id = ia.assessment_id
JOIN public.user u                  ON u.id = uhp.user_id
LEFT JOIN public.hackathon_with_score hw ON hw.id = ia.assessment_id
WHERE u.role = 'Student'
AND ia.assessment_id IN (
    SELECT id FROM public.hackathon WHERE test_type_id IN (6, 54, 12)
)
-- AND (idom.title ILIKE '%domain_keyword%')
-- AND (i.title ILIKE '%word1%' AND i.title ILIKE '%word2%')
-- AND u.college_id = (SELECT id FROM public.college WHERE name ILIKE '%college_keyword%' LIMIT 1)
GROUP BY u.id, u.first_name, u.last_name, u.email, u.college_id
ORDER BY avg_score_pct DESC
LIMIT 50
"""
