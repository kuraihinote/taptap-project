# schema_trainings.py — Trainings domain schema context for LLM SQL generation
#
# Covers the training programs module under schema: report
# Tables: report.trainings, report.phase, report.batch, report.batch_data,
#         report.phase_batch, report.phase_assessment, report.training_type,
#         report.phase_live_sessions
#
# Assessment results are fetched through the same path as all other domains:
#   report.phase_assessment.assessment_id = hackathon_id
#   -> public.user_hackathon_participation.current_score
#
# Key facts (verified against production DB, 2026-05-04):
#   report.trainings          — 14 training programs
#   report.phase              — 44 phases across all trainings
#   report.batch              — 162 named student groups
#   report.batch_data         — 50,350 student roster entries
#   report.phase_assessment   — 137 assessments (assessment_id = hackathon_id)
#   report.phase_live_sessions — 449 session events (no per-user attendance)
#   report.training_type      — 3 types: Python Trainings | Placement Program | C&DS
#   report.user_trainings     — 703 rows, denormalized (batch_assigned is free text) — skip

TRAININGS_SCHEMA_CONTEXT = """
You have access to the Trainings module. This module tracks structured training
programs delivered by Blackbucks to college students.

THIS MODULE COVERS:
  - Session attendance: present/absent counts and attendance rate per live session event
    within a training phase.
  - Training programs: title, college, type (Python/Placement/C&DS), date range, hours.
  - Phases: named sub-units of a training (e.g. "MBA-Aptitude Training"), with planned
    hours, live sessions, assessments, mock interviews, webinars.
  - Batches: named groups of students (e.g. "POWER 100 NBKR"), linked to phases.
  - Student rosters: batch_data stores student name, email, regno, college per batch.
  - Assessment scores: phase_assessment maps a phase to a hackathon assessment ID —
    use user_hackathon_participation to retrieve student scores for those assessments.
  - Live sessions: count of scheduled session events per phase.

NOT FOR:
  - Self-paced courses / course catalog (use course domain).
  - Employability Track / practice leaderboards (use emp domain).
  - POD / Problem of the Day (use pod domain).
  - Standalone hackathon events / MET / profiling tests (use assess domain).
  - Internships (use internship domain).

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TABLES — schema: report
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

-- Top-level training program
report.trainings (
    id                      INTEGER          -- primary key
    title                   VARCHAR(255)     -- training name; use ILIKE for keyword search
    college_id              VARCHAR(255)     -- STORED AS TEXT — join via: public.college c ON c.id::text = t.college_id
    start_date              DATE
    end_date                DATE
    trainings_type_id       INTEGER          -- FK to report.training_type.id (nullable)
    total_training_hours    INTEGER
    description             TEXT
    created_at              TIMESTAMP
    updated_at              TIMESTAMP
)

-- Training type lookup (3 rows)
report.training_type (
    id                INTEGER          -- 1 | 2 | 3
    training_types    VARCHAR          -- 'Python Trainings' | 'Placement Program' | 'C&DS'
)

-- Phase: a named sub-unit of a training
report.phase (
    id               INTEGER          -- primary key
    training_id      INTEGER          -- FK to report.trainings.id
    title            VARCHAR(255)     -- phase name (e.g. 'MBA-Aptitude Training')
    start_date       DATE
    end_date         DATE
    hours            DOUBLE PRECISION -- planned training hours for this phase
    live_sessions    DOUBLE PRECISION -- planned number of live sessions
    assessments      INTEGER          -- planned number of assessments
    mock_interviews  DOUBLE PRECISION
    webinars         DOUBLE PRECISION
    student_reviews  DOUBLE PRECISION
    created_at       TIMESTAMP
)

-- Named student group
report.batch (
    id           INTEGER          -- primary key
    batch_title  VARCHAR          -- batch name (e.g. 'POWER 100 NBKR', 'POWER 100 SRKR')
    created_at   TIMESTAMP
)

-- Phase <-> Batch join table (M:M)
report.phase_batch (
    id        INTEGER
    phase_id  INTEGER          -- FK to report.phase.id
    batch_id  INTEGER          -- FK to report.batch.id
    create_at TIMESTAMP
)

-- Student roster per batch
report.batch_data (
    id          INTEGER          -- primary key
    batch_id    INTEGER          -- FK to report.batch.id
    name        VARCHAR(255)     -- student full name
    email       VARCHAR(255)
    regno       VARCHAR(255)     -- registration number; joins to public.user.roll_number
                                 -- NOTE: not all regnos have a matching public.user row
    phone       VARCHAR(20)
    college_id  INTEGER          -- FK to public.college.id (INTEGER here, unlike trainings.college_id)
    create_at   TIMESTAMP
    update_at   TIMESTAMP
)

-- Phase <-> Assessment join table (M:M)
-- assessment_id IS the hackathon_id used in public.user_hackathon_participation
report.phase_assessment (
    id             INTEGER          -- primary key
    phase_id       INTEGER          -- FK to report.phase.id
    assessment_id  INTEGER          -- = hackathon_id in public.user_hackathon_participation
    create_at      TIMESTAMP
)

-- Scheduled live session events per phase (NOT per-user attendance)
report.phase_live_sessions (
    id        INTEGER
    phase_id  INTEGER          -- FK to report.phase.id
    event_id  VARCHAR          -- FK to report.events.id (external event UUID)
    create_at TIMESTAMP
)

-- report.phase_live_sessions
--   id          INTEGER
--   phase_id    INTEGER  → report.phase.id
--   event_id    VARCHAR  → report.events.id
--   create_at   TIMESTAMP

-- Student survey responses for live session events
report.student_responses (
    id                    VARCHAR          -- primary key
    registration_number   VARCHAR          -- links to report.batch_data.regno
    event_id              VARCHAR          -- FK to report.events.id (via phase_live_sessions.event_id)
    interactive           VARCHAR          -- 'Yes' | 'No'
    learn_today           VARCHAR
    feedback              VARCHAR          -- 'Extremely Satisfied' | 'Very Satisfied' | 'Satisfied'
                                           -- | 'Slightly Satisfied' | 'Needs Improvement'
    comments              VARCHAR
    created_at            TIMESTAMP
    feedback_name         VARCHAR
    feedback_email        VARCHAR
    feedback_college_name VARCHAR
)

-- Live session event metadata (source for session title and duration)
report.events (
    id            VARCHAR          -- primary key; matches phase_live_sessions.event_id
    event_title   VARCHAR          -- session name (e.g. 'Session 01', 'Day 3 Morning')
    num_hours     NUMERIC          -- session duration in hours
    program_id    VARCHAR
    program_type  VARCHAR
    created_at    TIMESTAMP
    updated_at    TIMESTAMP
)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
JOIN PATHS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

report.trainings       -> report.training_type          via tt.id = t.trainings_type_id
report.trainings       -> public.college                via c.id::text = t.college_id   <- VARCHAR cast required
report.phase           -> report.trainings              via p.training_id = t.id
report.phase_batch     -> report.phase                  via pb.phase_id = p.id
report.phase_batch     -> report.batch                  via pb.batch_id = b.id
report.batch_data      -> report.batch                  via bd.batch_id = b.id
report.batch_data      -> public.college                via col.id = bd.college_id      <- INTEGER (no cast)
report.batch_data      -> public.user                   via u.roll_number = bd.regno    <- LEFT JOIN; not all regnos match
report.phase_assessment -> report.phase                 via pa.phase_id = p.id
report.phase_assessment -> public.user_hackathon_participation via uhp.hackathon_id = pa.assessment_id
report.phase_live_sessions -> report.phase              via pls.phase_id = p.id
report.student_responses   -> report.phase_live_sessions via sr.event_id = pls.event_id
report.student_responses   -> report.events             via sr.event_id = e.id
report.events              -> report.phase_live_sessions via pls.event_id = e.id
public.user            -> public.college                via u.college_id = col.id

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CRITICAL RULES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. COLLEGE JOIN from trainings — trainings.college_id is VARCHAR. Cast required:
   JOIN public.college c ON c.id::text = t.college_id
   DO NOT write: ON c.id = t.college_id  (type mismatch, query will fail)

2. TRAINING / PHASE NAME SEARCH — split into words with AND ILIKE:
   (t.title ILIKE '%word1%' AND t.title ILIKE '%word2%')
   NEVER use a single ILIKE with the full phrase.

3. BATCH_DATA TO USER LINK — regno does not always match a public.user row.
   Always use LEFT JOIN; add DISTINCT to handle the rare case of duplicate roll_numbers:
   LEFT JOIN public.user u ON u.roll_number = bd.regno AND u.role = 'Student'

4. NO RANK COLUMN — user_hackathon_participation has no pre-computed rank.
   Always compute on the fly:
   RANK() OVER (PARTITION BY uhp.hackathon_id ORDER BY uhp.current_score DESC) AS rank

5. STUDENT NAME format (consistent with all domains):
   (TRIM(u.first_name) || ' ' || TRIM(u.last_name)) AS name

6. ALWAYS filter u.role = 'Student' when joining public.user for student analytics.

7. PHASE_LIVE_SESSIONS has NO user_id — it tracks scheduled session events, not
   per-student attendance. Use COUNT(pls.id) as "live_session_count" only.
   Do NOT attempt to join it to user data.

8. USER_TRAININGS table is denormalized (batch_assigned is free text like "Phase 2 Batch 1")
   with no FK links. Do NOT use it for queries — use batch_data instead.

9. SOME ASSESSMENTS HAVE ZERO PARTICIPANTS — phase_assessment.assessment_id always has
   a valid hackathon_id, but some hackathons have 0 participants in
   user_hackathon_participation. Add HAVING COUNT(uhp.user_id) > 0 when aggregating
   to skip empty assessments.

10. CRITICAL — JOIN LIMIT: The query validator rejects any query with more than 6 JOINs.

    For student identity, pick EXACTLY ONE path — never both:
      Path A: public.user        → gives first_name, last_name, email, college_id
      Path B: report.batch_data  → gives name, email, regno, college_id

    If you pick Path A — do NOT also join report.batch_data.
    If you pick Path B — do NOT also join public.user.

    For college name:
      - If you have remaining JOIN budget: JOIN public.college via u.college_id or bd.college_id.
      - If you are already at 6 JOINs (e.g. T12: batch_data + phase_batch + phase +
        phase_assessment + user + uhp = 6 JOINs), you have ZERO remaining budget.
        Use a scalar subquery instead — it costs NO JOINs:
        (SELECT c.name FROM public.college c WHERE c.id = u.college_id) AS college
    Never join public.college twice.

11. Today's date: {today}

12. CRITICAL — FUZZY TITLE/NAME MATCHING:
    Never filter by name or title using a single ILIKE with the full typed phrase.
    Faculty may omit spaces, dashes, or parts of the full name.
    Instead split the search term into individual meaningful keywords and apply a
    separate ILIKE condition for each keyword:
      (t.title ILIKE '%word1%' AND t.title ILIKE '%word2%')
    This ensures minor formatting or spelling differences between what faculty type
    and what is stored in the DB do not cause 0 rows.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
QUERY PATTERNS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

PATTERN T1 — TRAINING CATALOG (list trainings, filter by college/type):
-- Use when faculty asks: "what trainings are available", "list all placement programs",
-- "trainings for [college]", "show Python training programs".
SELECT
    t.id,
    t.title,
    c.name AS college,
    tt.training_types AS type,
    t.start_date,
    t.end_date,
    t.total_training_hours,
    t.description
FROM report.trainings t
LEFT JOIN public.college c ON c.id::text = t.college_id
LEFT JOIN report.training_type tt ON tt.id = t.trainings_type_id
-- Uncomment for type filter:
-- WHERE tt.training_types ILIKE '%Placement%'
-- Uncomment for college filter:
-- WHERE (c.name ILIKE '%word1%' AND c.name ILIKE '%word2%')
ORDER BY t.start_date DESC
LIMIT 20
NOTE: trainings.college_id is VARCHAR — always join via c.id::text = t.college_id.

PATTERN T2 — PHASES IN A TRAINING (training structure):
-- Use when faculty asks: "what are the phases of [training]", "show training structure",
-- "how many phases in [training]", "what does [training] include".
SELECT
    p.id,
    p.title AS phase_title,
    t.title AS training_title,
    p.start_date,
    p.end_date,
    p.hours,
    p.live_sessions AS planned_live_sessions,
    p.assessments AS planned_assessments,
    p.mock_interviews,
    p.webinars
FROM report.phase p
JOIN report.trainings t ON t.id = p.training_id
-- WHERE (t.title ILIKE '%word1%' AND t.title ILIKE '%word2%')
ORDER BY p.start_date ASC

# CRITICAL — ENROLLMENT COUNT:
# Use COUNT(bd.id) not COUNT(DISTINCT bd.id) for total enrollment.
# A student enrolled in multiple phases appears once per phase in batch_data.
# Total enrollment = sum of all batch_data rows across all phases,
# which matches what the dashboard displays.
# For overall training enrollment, SUM the student_count across all batches.
PATTERN T3 — BATCHES IN A TRAINING / PHASE (with student count):
-- Use when faculty asks: "what batches are in [training]", "list batches for [phase]",
-- "how many students per batch in [training]", "how many students enrolled in [training]".
SELECT
    b.id,
    b.batch_title,
    p.title AS phase_title,
    t.title AS training_title,
    COUNT(bd.id) AS student_count
FROM report.batch b
JOIN report.phase_batch pb ON pb.batch_id = b.id
JOIN report.phase p ON p.id = pb.phase_id
JOIN report.trainings t ON t.id = p.training_id
LEFT JOIN report.batch_data bd ON bd.batch_id = b.id
-- WHERE (t.title ILIKE '%word1%' AND t.title ILIKE '%word2%')
GROUP BY b.id, b.batch_title, p.title, t.title
ORDER BY b.batch_title

PATTERN T4 — STUDENTS IN A BATCH (roster):
-- Use when faculty asks: "who is in [batch]", "list students in [batch]",
-- "students enrolled in [training] batch", "batch roster".
SELECT
    bd.name,
    bd.email,
    bd.regno,
    col.name AS college
FROM report.batch_data bd
JOIN report.batch b ON b.id = bd.batch_id
LEFT JOIN public.college col ON col.id = bd.college_id
-- WHERE (b.batch_title ILIKE '%word1%' AND b.batch_title ILIKE '%word2%')
ORDER BY bd.name
LIMIT 50
NOTE: batch_data.college_id is INTEGER — no cast needed here (unlike trainings.college_id).

# CRITICAL — AVERAGE SCORE AS PERCENTAGE:
# To calculate avg score as a percentage (matching dashboard display):
# Use: AVG(uhp.current_score * 100.0 / rws.max_score)
# Where max_score comes from:
#   SELECT hackathon_id, SUM(score) AS max_score
#   FROM public.round_with_score
#   GROUP BY hackathon_id
# Never use raw AVG(uhp.current_score) for percentage display —
# that returns raw points, not percentage.
PATTERN T5 — ASSESSMENT SCORES IN A PHASE (ranked results):
-- Use when faculty asks: "scores in [phase] assessment", "how did students perform in [phase]",
-- "assessment results for [phase]", "who passed the [training] test".
SELECT
    p.title AS phase_title,
    pa.assessment_id AS hackathon_id,
    (TRIM(u.first_name) || ' ' || TRIM(u.last_name)) AS student_name,
    col.name AS college,
    uhp.current_score,
    RANK() OVER (PARTITION BY pa.assessment_id ORDER BY uhp.current_score DESC) AS rank
FROM report.phase p
JOIN report.trainings t ON t.id = p.training_id
JOIN report.phase_assessment pa ON pa.phase_id = p.id
JOIN public.user_hackathon_participation uhp ON uhp.hackathon_id = pa.assessment_id
JOIN public.user u ON u.id = uhp.user_id
LEFT JOIN public.college col ON col.id = u.college_id
WHERE u.role = 'Student'
-- AND (t.title ILIKE '%word1%' AND t.title ILIKE '%word2%')
-- AND (p.title ILIKE '%word1%')
ORDER BY pa.assessment_id, rank
LIMIT 50

PATTERN T6 — TOP SCORERS ACROSS ALL ASSESSMENTS IN A TRAINING:
-- Use when faculty asks: "top students in [training]", "leaderboard for [training]",
-- "who performed best overall in [training]", "average score percentage".
-- avg_score_pct scoped to this training's assessments only — more accurate than dashboard.
-- college name via scalar subquery — do NOT add a separate JOIN to public.college
SELECT
    bd.name AS student_name,
    (SELECT c.name FROM public.college c WHERE c.id = u.college_id) AS college,
    bd.regno AS registration_number,
    b.batch_title,
    COUNT(DISTINCT uhp.hackathon_id) AS assessments_taken,
    ROUND(AVG(uhp.current_score * 100.0 / NULLIF(
        (SELECT SUM(score) FROM public.round_with_score WHERE hackathon_id = uhp.hackathon_id), 0
    )), 2) AS avg_score_pct
FROM report.trainings t
JOIN report.phase_batch pb ON pb.phase_id IN (
    SELECT id FROM report.phase WHERE training_id = t.id
)
JOIN report.batch b ON b.id = pb.batch_id
JOIN report.batch_data bd ON bd.batch_id = b.id
JOIN public.user u ON u.email = bd.email
JOIN public.user_hackathon_participation uhp ON uhp.user_id = u.id
WHERE uhp.hackathon_id IN (
    SELECT pa.assessment_id FROM report.phase_assessment pa
    JOIN report.phase p2 ON p2.id = pa.phase_id
    WHERE p2.training_id = t.id
)
-- AND (t.title ILIKE '%word1%' AND t.title ILIKE '%word2%')
GROUP BY bd.name, bd.email, bd.regno, b.batch_title, u.college_id
ORDER BY avg_score_pct DESC
LIMIT 20

PATTERN T7 — FEEDBACK AND INTERACTIVENESS PER PHASE:
-- Use when faculty asks: "feedback for [training]", "interactiveness for [phase]",
-- "how satisfied were students in [training]", "phase summary metrics".
SELECT
    p.title AS phase_title,
    ROUND(AVG(
        CASE sr.feedback
            WHEN 'Extremely Satisfied' THEN 5
            WHEN 'Very Satisfied' THEN 4
            WHEN 'Satisfied' THEN 3
            WHEN 'Slightly Satisfied' THEN 2
            WHEN 'Needs Improvement' THEN 1
            ELSE 0
        END
    ), 2) AS avg_feedback,
    ROUND(AVG(
        CASE sr.interactive WHEN 'Yes' THEN 1 ELSE 0 END
    ) * 100, 2) AS interactiveness_pct
FROM report.trainings t
JOIN report.phase p ON p.training_id = t.id
JOIN report.phase_live_sessions pls ON pls.phase_id = p.id
JOIN report.student_responses sr ON sr.event_id = pls.event_id
-- AND (t.title ILIKE '%word1%' AND t.title ILIKE '%word2%')
GROUP BY p.id, p.title
ORDER BY p.title

PATTERN T8 — OVERALL FEEDBACK AND INTERACTIVENESS FOR A TRAINING:
-- Use when faculty asks: "overall feedback for [training]",
-- "average interactiveness", "overall satisfaction for [training]".
SELECT
    ROUND(AVG(
        CASE sr.feedback
            WHEN 'Extremely Satisfied' THEN 5
            WHEN 'Very Satisfied' THEN 4
            WHEN 'Satisfied' THEN 3
            WHEN 'Slightly Satisfied' THEN 2
            WHEN 'Needs Improvement' THEN 1
            ELSE 0
        END
    ), 2) AS avg_feedback,
    ROUND(AVG(
        CASE sr.interactive WHEN 'Yes' THEN 1 ELSE 0 END
    ) * 100, 2) AS interactiveness_pct
FROM report.trainings t
JOIN report.phase p ON p.training_id = t.id
JOIN report.phase_live_sessions pls ON pls.phase_id = p.id
JOIN report.student_responses sr ON sr.event_id = pls.event_id
-- AND (t.title ILIKE '%word1%' AND t.title ILIKE '%word2%')

PATTERN T9 — LIVE SESSION COUNT PER PHASE:
-- Use when faculty asks: "how many live sessions in [training]", "session schedule for [phase]",
-- "how many sessions were held", "live session count".
-- NOTE: phase_live_sessions tracks scheduled events, not per-student attendance.
SELECT
    p.title AS phase_title,
    t.title AS training_title,
    p.live_sessions AS planned_sessions,
    COUNT(pls.id) AS scheduled_session_events
FROM report.phase p
JOIN report.trainings t ON t.id = p.training_id
LEFT JOIN report.phase_live_sessions pls ON pls.phase_id = p.id
-- WHERE (t.title ILIKE '%word1%' AND t.title ILIKE '%word2%')
GROUP BY p.id, p.title, t.title, p.live_sessions
ORDER BY t.title, p.start_date

PATTERN T9b — SESSION ATTENDANCE PER LIVE SESSION IN A PHASE:
-- Use ONLY when faculty asks about attendance, present/absent counts,
-- or who attended sessions. Do NOT use for avg score queries.
-- UNSUPPORTED: avg score per session cannot be combined with attendance
-- in a single query. If faculty asks for both, return attendance only
-- and tell them to ask about scores separately.
WITH TotalStudents AS (
    SELECT pls.event_id, COUNT(DISTINCT bd.email) AS total_students
    FROM report.phase p
    INNER JOIN report.phase_batch pb ON p.id = pb.phase_id
    INNER JOIN report.batch_data bd ON pb.batch_id = bd.batch_id
    INNER JOIN report.phase_live_sessions pls ON p.id = pls.phase_id
    WHERE bd.email IS NOT NULL
    AND p.id = (
        SELECT p2.id FROM report.phase p2
        JOIN report.trainings t ON t.id = p2.training_id
        WHERE (t.title ILIKE '%word1%') AND (p2.title ILIKE '%word2%')
        LIMIT 1
    )
    GROUP BY pls.event_id
),
EventAttendance AS (
    SELECT pls.event_id, COUNT(DISTINCT bd.email) AS present_students
    FROM report.student_responses sr
    INNER JOIN report.phase_live_sessions pls
        ON sr.event_id::text = pls.event_id::text
    INNER JOIN report.phase p ON p.id = pls.phase_id
    INNER JOIN report.phase_batch pb ON p.id = pb.phase_id
    INNER JOIN report.batch_data bd ON pb.batch_id = bd.batch_id
        AND LOWER(TRIM(sr.registration_number::text)) = LOWER(TRIM(bd.regno::text))
    WHERE p.id = (
        SELECT p2.id FROM report.phase p2
        JOIN report.trainings t ON t.id = p2.training_id
        WHERE (t.title ILIKE '%word1%') AND (p2.title ILIKE '%word2%')
        LIMIT 1
    )
    GROUP BY pls.event_id
)
SELECT
    e.event_title,
    ts.total_students,
    COALESCE(ea.present_students, 0) AS present_students,
    ts.total_students - COALESCE(ea.present_students, 0) AS absent_students,
    e.num_hours AS hours_covered,
    COALESCE(ROUND(COALESCE(ea.present_students, 0) * 100.0 
        / NULLIF(ts.total_students, 0)), 0) AS attendance_rate
FROM TotalStudents ts
LEFT JOIN EventAttendance ea ON ts.event_id = ea.event_id
INNER JOIN report.events e ON ts.event_id = e.id
WHERE ts.event_id IN (
    SELECT event_id FROM report.phase_live_sessions
    WHERE phase_id = (
        SELECT p2.id FROM report.phase p2
        JOIN report.trainings t ON t.id = p2.training_id
        WHERE (t.title ILIKE '%word1%') AND (p2.title ILIKE '%word2%')
        LIMIT 1
    )
);
-- Replace %word1% with training title keywords, %word2% with phase title keywords

PATTERN T10 — STUDENT PERFORMANCE SUMMARY ACROSS ALL PHASES IN A TRAINING:
-- Use when faculty asks: "how did students do across the whole [training]",
-- "overall performance in [training]", "student summary for [training]".
WITH training_assessments AS (
    SELECT pa.assessment_id
    FROM report.trainings t
    JOIN report.phase p ON p.training_id = t.id
    JOIN report.phase_assessment pa ON pa.phase_id = p.id
    WHERE (t.title ILIKE '%word1%' AND t.title ILIKE '%word2%')
)
SELECT
    (TRIM(u.first_name) || ' ' || TRIM(u.last_name)) AS student_name,
    col.name AS college,
    COUNT(DISTINCT uhp.hackathon_id) AS assessments_completed,
    SUM(uhp.current_score) AS total_score,
    ROUND(AVG(uhp.current_score), 2) AS avg_score
FROM training_assessments ta
JOIN public.user_hackathon_participation uhp ON uhp.hackathon_id = ta.assessment_id
JOIN public.user u ON u.id = uhp.user_id
LEFT JOIN public.college col ON col.id = u.college_id
WHERE u.role = 'Student'
GROUP BY u.id, u.first_name, u.last_name, col.name
ORDER BY total_score DESC
LIMIT 20

PATTERN T10b — ASSESSMENT PERFORMANCE SUMMARY PER ASSESSMENT IN A PHASE:
-- Use when faculty asks: "show attendance and avg score for each session/assessment",
-- "assessment performance details for [phase]", "present absent and scores per assessment".
-- NOTE: Each row = one assessment (hackathon). Session names come from hackathon titles.
WITH TotalStudents AS (
    SELECT
        pa.assessment_id,
        COUNT(DISTINCT bd.regno) AS total_students
    FROM report.phase p
    INNER JOIN report.phase_batch pb ON p.id = pb.phase_id
    INNER JOIN report.batch_data bd ON pb.batch_id = bd.batch_id
    INNER JOIN report.phase_assessment pa ON p.id = pa.phase_id
    WHERE p.id = (
        SELECT p2.id FROM report.phase p2
        JOIN report.trainings t ON t.id = p2.training_id
        WHERE (t.title ILIKE '%word1%') AND (p2.title ILIKE '%word2%')
        LIMIT 1
    )
    GROUP BY pa.assessment_id
),
AssessmentAttendance AS (
    SELECT
        pa.assessment_id,
        COUNT(DISTINCT uhp.user_id) AS present_students,
        ROUND(AVG(uhp.current_score * 100.0 / NULLIF(
            (SELECT SUM(score) FROM public.round_with_score WHERE hackathon_id = pa.assessment_id), 0
        )), 2) AS avg_score_pct
    FROM public.user_hackathon_participation uhp
    INNER JOIN report.phase_assessment pa ON uhp.hackathon_id = pa.assessment_id
    INNER JOIN report.phase p ON pa.phase_id = p.id
    INNER JOIN public.user u ON uhp.user_id = u.id
    INNER JOIN report.phase_batch pb ON p.id = pb.phase_id
    INNER JOIN report.batch_data bd ON u.email = bd.email AND pb.batch_id = bd.batch_id
    WHERE p.id = (
        SELECT p2.id FROM report.phase p2
        JOIN report.trainings t ON t.id = p2.training_id
        WHERE (t.title ILIKE '%word1%') AND (p2.title ILIKE '%word2%')
        LIMIT 1
    )
    GROUP BY pa.assessment_id
)
SELECT
    h.title AS assessment_title,
    ts.total_students,
    COALESCE(aa.present_students, 0) AS present_students,
    ts.total_students - COALESCE(aa.present_students, 0) AS absent_students,
    ROUND(COALESCE(aa.present_students, 0) * 100.0 / NULLIF(ts.total_students, 0), 2) AS attendance_rate,
    aa.avg_score_pct
FROM TotalStudents ts
LEFT JOIN AssessmentAttendance aa ON ts.assessment_id = aa.assessment_id
INNER JOIN public.hackathon h ON ts.assessment_id = h.id
INNER JOIN report.phase_assessment pa ON ts.assessment_id = pa.assessment_id
WHERE pa.phase_id = (
    SELECT p2.id FROM report.phase p2
    JOIN report.trainings t ON t.id = p2.training_id
    WHERE (t.title ILIKE '%word1%') AND (p2.title ILIKE '%word2%')
    LIMIT 1
)
-- Replace %word1% with training title keywords, %word2% with phase title keywords

PATTERN T11 — TRAINING OVERVIEW BY COLLEGE:
-- Use when faculty asks: "which colleges have trainings", "training programs by college",
-- "how many trainings does [college] have".
SELECT
    c.name AS college,
    COUNT(t.id) AS total_trainings,
    STRING_AGG(DISTINCT tt.training_types, ', ') AS training_types,
    MIN(t.start_date) AS earliest_start,
    MAX(t.end_date) AS latest_end,
    SUM(t.total_training_hours) AS total_hours
FROM report.trainings t
LEFT JOIN public.college c ON c.id::text = t.college_id
LEFT JOIN report.training_type tt ON tt.id = t.trainings_type_id
GROUP BY c.id, c.name
ORDER BY total_trainings DESC
LIMIT 20

PATTERN T12 — STUDENT PERFORMANCE SUMMARY FOR A BATCH:
-- Use when faculty asks: "performance summary for [batch]", "how did [batch] students do",
-- "scores for students in [batch]", "batch results", "show performance for [batch]",
-- "students in [batch] with college name and ranking", "batch leaderboard".
-- Use when the identifier matches a batch name (e.g. "POWER 100 NBKR", "AI Agent Internship 2026").
-- batch_data.regno links to public.user.roll_number — LEFT JOIN as not all regnos match.
-- All students in the batch are returned; those with no UHP records show 0 for score/count.
-- BUDGET: this pattern uses all 6 JOINs (batch_data + phase_batch + phase + phase_assessment
--   + user + uhp). For college name use a scalar subquery, NOT a 7th JOIN to public.college.
SELECT
    COALESCE((TRIM(u.first_name) || ' ' || TRIM(u.last_name)), bd.name) AS student_name,
    bd.email,
    bd.regno,
    (SELECT c.name FROM public.college c WHERE c.id = u.college_id) AS college,
    COUNT(DISTINCT uhp.hackathon_id) AS assessments_completed,
    COALESCE(SUM(uhp.current_score), 0) AS total_score,
    ROUND(COALESCE(AVG(uhp.current_score), 0), 2) AS avg_score,
    RANK() OVER (ORDER BY COALESCE(SUM(uhp.current_score), 0) DESC NULLS LAST) AS overall_rank
FROM report.batch b
JOIN report.batch_data bd ON bd.batch_id = b.id
JOIN report.phase_batch pb ON pb.batch_id = b.id
JOIN report.phase p ON p.id = pb.phase_id
JOIN report.phase_assessment pa ON pa.phase_id = p.id
LEFT JOIN public.user u ON u.roll_number = bd.regno AND u.role = 'Student'
LEFT JOIN public.user_hackathon_participation uhp
    ON uhp.hackathon_id = pa.assessment_id AND uhp.user_id = u.id
-- WHERE (b.batch_title ILIKE '%word1%' AND b.batch_title ILIKE '%word2%')
GROUP BY bd.id, bd.name, bd.email, bd.regno, u.id, u.first_name, u.last_name, u.college_id
ORDER BY total_score DESC NULLS LAST
LIMIT 50

PATTERN T13 — SUBDOMAIN ANALYSIS FOR AN ASSESSMENT IN A TRAINING PHASE:
-- Use when faculty asks: "what topics are students failing in [phase/assessment]",
-- "strong and weak areas in [assessment]", "which subdomains need improvement",
-- "what should students work on in [training]".
-- Specify session name (e.g. "Session 02") to scope to a specific assessment.
WITH cohort AS (
    SELECT DISTINCT u.id AS user_id
    FROM report.batch_data bd
    INNER JOIN report.batch b ON bd.batch_id = b.id
    INNER JOIN report.phase_batch pb ON bd.batch_id = pb.batch_id
    INNER JOIN report.phase p ON pb.phase_id = p.id
    INNER JOIN public.user u ON bd.email = u.email
    WHERE p.id = (
        SELECT p2.id FROM report.phase p2
        JOIN report.trainings t ON t.id = p2.training_id
        WHERE (t.title ILIKE '%word1%') AND (p2.title ILIKE '%word2%')
        LIMIT 1
    )
    AND bd.email IS NOT NULL
),
round_info AS (
    SELECT id AS round_id, LOWER(skill) AS skill
    FROM public.round_with_score
    WHERE hackathon_id = (
        SELECT pa.assessment_id FROM report.phase_assessment pa
        JOIN report.phase p2 ON p2.id = pa.phase_id
        JOIN report.trainings t ON t.id = p2.training_id
        JOIN public.hackathon h ON h.id = pa.assessment_id
        WHERE (t.title ILIKE '%word1%') AND (p2.title ILIKE '%word2%')
          AND (h.title ILIKE '%word3%')
        LIMIT 1
    )
),
expanded_questions AS (
    SELECT
        uhp.user_id,
        (qr -> 'report' ->> 'status') AS status,
        jsonb_array_elements_text(
            COALESCE(qr -> 'report' -> 'subDomain', '[]'::jsonb)
        ) AS subdomain,
        (qr -> 'report' ->> 'roundId')::int AS round_id
    FROM public.user_hackathon_participation uhp
    INNER JOIN cohort c ON c.user_id = uhp.user_id
    CROSS JOIN LATERAL jsonb_array_elements(
        COALESCE(uhp.report -> 'questionReports', '[]'::jsonb)
    ) AS qr
    WHERE uhp.hackathon_id = (
        SELECT pa.assessment_id FROM report.phase_assessment pa
        JOIN report.phase p2 ON p2.id = pa.phase_id
        JOIN report.trainings t ON t.id = p2.training_id
        JOIN public.hackathon h ON h.id = pa.assessment_id
        WHERE (t.title ILIKE '%word1%') AND (p2.title ILIKE '%word2%')
          AND (h.title ILIKE '%word3%')
        LIMIT 1
    )
),
tagged_questions AS (
    SELECT eq.*, ri.skill
    FROM expanded_questions eq
    INNER JOIN round_info ri ON eq.round_id = ri.round_id
),
subdomain_stats AS (
    SELECT
        skill,
        subdomain,
        COUNT(DISTINCT user_id) AS attempted_count,
        COUNT(DISTINCT CASE WHEN status = 'pass' THEN user_id END) AS passed_count
    FROM tagged_questions
    GROUP BY skill, subdomain
)
SELECT
    skill,
    subdomain,
    attempted_count,
    passed_count,
    ROUND(passed_count * 100.0 / NULLIF(attempted_count, 0), 2) AS accuracy_percent,
    CASE
        WHEN ROUND(passed_count * 100.0 / NULLIF(attempted_count, 0), 2) > 80 THEN 'Strong'
        WHEN ROUND(passed_count * 100.0 / NULLIF(attempted_count, 0), 2) >= 50 THEN 'Developing'
        ELSE 'Needs Improvement'
    END AS area_category
FROM subdomain_stats
WHERE attempted_count >= 2
ORDER BY skill, accuracy_percent DESC
-- word1 = training title keyword, word2 = phase title keyword,
-- word3 = session/assessment title keyword (e.g. 'Session 02')

PATTERN T14 — NOT ATTEMPTED STUDENTS FOR AN ASSESSMENT IN A TRAINING PHASE:
-- Use when faculty asks: "who hasn't attempted [assessment] in [phase]",
-- "students who didn't take the test in [training]", "absentees for [assessment]".
-- Specify session name (e.g. "Session 02") to scope to a specific assessment.
WITH cohort AS (
    SELECT DISTINCT ON (bd.email)
        bd.email,
        bd.regno,
        bd.name,
        b.batch_title,
        u.id AS user_id
    FROM report.batch_data bd
    INNER JOIN report.batch b ON bd.batch_id = b.id
    INNER JOIN report.phase_batch pb ON bd.batch_id = pb.batch_id
    INNER JOIN report.phase p ON pb.phase_id = p.id
    LEFT JOIN public.user u ON bd.email = u.email
    WHERE p.id = (
        SELECT p2.id FROM report.phase p2
        JOIN report.trainings t ON t.id = p2.training_id
        WHERE (t.title ILIKE '%word1%') AND (p2.title ILIKE '%word2%')
        LIMIT 1
    )
    AND bd.email IS NOT NULL
    ORDER BY bd.email
),
attempted AS (
    SELECT c.email
    FROM cohort c
    INNER JOIN public.user u ON u.id = c.user_id
    INNER JOIN public.user_hackathon_participation uhp
        ON u.id = uhp.user_id
        AND uhp.hackathon_id = (
            SELECT pa.assessment_id FROM report.phase_assessment pa
            JOIN report.phase p2 ON p2.id = pa.phase_id
            JOIN report.trainings t ON t.id = p2.training_id
            JOIN public.hackathon h ON h.id = pa.assessment_id
            WHERE (t.title ILIKE '%word1%') AND (p2.title ILIKE '%word2%')
              AND (h.title ILIKE '%word3%')
            LIMIT 1
        )
    GROUP BY c.email
)
SELECT c.batch_title, c.name, c.email, c.regno
FROM cohort c
WHERE NOT EXISTS (SELECT 1 FROM attempted a WHERE a.email = c.email)
ORDER BY c.batch_title NULLS LAST, c.name
LIMIT 50
-- word1 = training title keyword, word2 = phase title keyword,
-- word3 = session/assessment title keyword (e.g. 'Session 02')

PATTERN T15 — STUDENTS WHO HAVEN'T ATTEMPTED ANY ASSESSMENT IN A PHASE:
-- Use when faculty asks: "who hasn't attempted any test in [phase]",
-- "inactive students in [training]", "students with zero attempts in [phase]".
WITH cohort AS (
    SELECT DISTINCT ON (bd.email)
        bd.name,
        bd.email,
        bd.regno,
        b.batch_title
    FROM report.batch_data bd
    INNER JOIN report.phase_batch pb ON bd.batch_id = pb.batch_id
    INNER JOIN report.phase p ON pb.phase_id = p.id
    INNER JOIN report.batch b ON b.id = bd.batch_id
    WHERE p.id = (
        SELECT p2.id FROM report.phase p2
        JOIN report.trainings t ON t.id = p2.training_id
        WHERE (t.title ILIKE '%word1%') AND (p2.title ILIKE '%word2%')
        LIMIT 1
    )
    AND bd.email IS NOT NULL
    AND bd.name IS NOT NULL
    ORDER BY bd.email
),
attempted AS (
    SELECT DISTINCT u.email
    FROM public.user u
    INNER JOIN public.user_hackathon_participation uhp ON u.id = uhp.user_id
    WHERE uhp.hackathon_id IN (
        SELECT pa.assessment_id FROM report.phase_assessment pa
        JOIN report.phase p2 ON p2.id = pa.phase_id
        JOIN report.trainings t ON t.id = p2.training_id
        WHERE (t.title ILIKE '%word1%') AND (p2.title ILIKE '%word2%')
    )
)
SELECT c.batch_title, c.name, c.email, c.regno
FROM cohort c
WHERE c.email NOT IN (SELECT email FROM attempted)
ORDER BY c.batch_title, c.name
LIMIT 50
-- Replace %word1% with training title keywords, %word2% with phase title keywords

PATTERN T16 — STUDENTS WHO HAVEN'T ATTENDED ANY LIVE SESSION IN A PHASE:
-- Use when faculty asks: "who hasn't attended any session in [phase]",
-- "students with zero session attendance in [training]",
-- "who has never shown up to a live session in [phase]".
SELECT
    bd.name,
    bd.regno,
    bd.email,
    b.batch_title
FROM report.phase p
INNER JOIN report.phase_live_sessions ls ON p.id = ls.phase_id
INNER JOIN report.phase_batch pb ON p.id = pb.phase_id
INNER JOIN report.batch b ON b.id = pb.batch_id
INNER JOIN report.batch_data bd ON pb.batch_id = bd.batch_id
LEFT JOIN report.student_responses sr ON bd.regno = sr.registration_number
    AND ls.event_id::text = sr.event_id::text
WHERE p.id = (
    SELECT p2.id FROM report.phase p2
    JOIN report.trainings t ON t.id = p2.training_id
    WHERE (t.title ILIKE '%word1%') AND (p2.title ILIKE '%word2%')
    LIMIT 1
)
GROUP BY bd.name, bd.regno, bd.email, b.batch_title
HAVING COUNT(sr.registration_number) = 0
ORDER BY bd.name NULLS LAST
LIMIT 50
-- Replace %word1% with training title keywords, %word2% with phase title keywords

PATTERN T17 — DAILY/WEEKLY/GRAND/EMPLOYABILITY TEST SCORES FOR STUDENTS IN A PHASE:
-- Use when faculty asks: "daily test scores in [phase]", "grand test results for [training]",
-- "weekly test performance in [phase]", "employability test scores in [phase]",
-- "how did students do on daily/weekly/grand/employability tests in [training]".
-- test_type_id: 13 = daily test, 43 = weekly test, 81 = grand test, 6 = employability test
WITH student_data AS (
    SELECT bd.name, bd.email, bd.regno
    FROM report.batch_data bd
    INNER JOIN report.phase_batch pb ON bd.batch_id = pb.batch_id
    INNER JOIN report.phase p ON pb.phase_id = p.id
    WHERE p.id = (
        SELECT p2.id FROM report.phase p2
        JOIN report.trainings t ON t.id = p2.training_id
        WHERE (t.title ILIKE '%word1%') AND (p2.title ILIKE '%word2%')
        LIMIT 1
    )
),
hackathon_scores AS (
    SELECT
        bd.email,
        ROUND(AVG(uhp.current_score * 100.0 / NULLIF(
            (SELECT SUM(score) FROM public.round_with_score WHERE hackathon_id = h.id), 0
        )), 2) AS avg_score_pct,
        COUNT(DISTINCT h.id) AS tests_attempted
    FROM report.batch_data bd
    LEFT JOIN public.user u ON bd.email = u.email
    LEFT JOIN public.user_hackathon_participation uhp ON u.id = uhp.user_id
    INNER JOIN public.hackathon h ON uhp.hackathon_id = h.id
    INNER JOIN report.phase_assessment pa ON pa.assessment_id = h.id
        AND pa.phase_id = (
            SELECT p2.id FROM report.phase p2
            JOIN report.trainings t ON t.id = p2.training_id
            WHERE (t.title ILIKE '%word1%') AND (p2.title ILIKE '%word2%')
            LIMIT 1
        )
    WHERE h.test_type_id = 13
    -- Change test_type_id for other test types:
    -- 13 = daily test, 43 = weekly test, 81 = grand test, 6 = employability test
    GROUP BY bd.email
)
SELECT
    sd.name,
    sd.email,
    sd.regno,
    COALESCE(hs.avg_score_pct, 0) AS avg_score_pct,
    COALESCE(hs.tests_attempted, 0) AS tests_attempted
FROM student_data sd
LEFT JOIN hackathon_scores hs ON sd.email = hs.email
ORDER BY avg_score_pct DESC NULLS LAST
LIMIT 50
-- Replace %word1% with training title keywords, %word2% with phase title keywords
-- Change test_type_id = 13 for daily, 43 for weekly, 81 for grand test

PATTERN T18 — OVERALL LIVE SESSION SUMMARY FOR A PHASE:
-- Use when faculty asks: "overall session attendance for [phase]",
-- "how many sessions in [phase]", "total hours and attendance rate for [phase]",
-- "session summary for [training] phase".
WITH TotalStudents AS (
    SELECT
        pb.phase_id,
        COUNT(DISTINCT bd.email) AS total_students
    FROM report.phase p
    INNER JOIN report.phase_batch pb ON p.id = pb.phase_id
    INNER JOIN report.batch_data bd ON pb.batch_id = bd.batch_id
    WHERE bd.email IS NOT NULL
    AND p.id = (
        SELECT p2.id FROM report.phase p2
        JOIN report.trainings t ON t.id = p2.training_id
        WHERE (t.title ILIKE '%word1%') AND (p2.title ILIKE '%word2%')
        LIMIT 1
    )
    GROUP BY pb.phase_id
),
PhaseAttendance AS (
    SELECT
        pls.phase_id,
        COUNT(DISTINCT sr.registration_number) AS present_students
    FROM report.student_responses sr
    INNER JOIN report.phase_live_sessions pls ON sr.event_id = pls.event_id
    INNER JOIN report.phase p ON pls.phase_id = p.id
    INNER JOIN report.phase_batch pb ON p.id = pb.phase_id
    INNER JOIN report.batch_data bd ON pb.batch_id = bd.batch_id
        AND sr.registration_number = bd.regno
    WHERE p.id = (
        SELECT p2.id FROM report.phase p2
        JOIN report.trainings t ON t.id = p2.training_id
        WHERE (t.title ILIKE '%word1%') AND (p2.title ILIKE '%word2%')
        LIMIT 1
    )
    GROUP BY pls.phase_id
),
LiveSessionHours AS (
    SELECT
        p.id,
        SUM(e.num_hours) AS total_hours,
        COUNT(ls.event_id) AS number_of_live_sessions
    FROM report.phase p
    INNER JOIN report.phase_live_sessions ls ON p.id = ls.phase_id
    INNER JOIN report.events e ON ls.event_id = e.id
    WHERE p.id = (
        SELECT p2.id FROM report.phase p2
        JOIN report.trainings t ON t.id = p2.training_id
        WHERE (t.title ILIKE '%word1%') AND (p2.title ILIKE '%word2%')
        LIMIT 1
    )
    GROUP BY p.id
)
SELECT
    p.title AS phase_title,
    lsh.number_of_live_sessions,
    lsh.total_hours,
    ts.total_students,
    COALESCE(pa.present_students, 0) AS present_students,
    ts.total_students - COALESCE(pa.present_students, 0) AS absent_students,
    ROUND(COALESCE(pa.present_students, 0) * 100.0 / NULLIF(ts.total_students, 0)) AS attendance_rate,
    ROUND(AVG(
        CASE sr.feedback
            WHEN 'Extremely Satisfied' THEN 5
            WHEN 'Very Satisfied'      THEN 4
            WHEN 'Satisfied'           THEN 3
            WHEN 'Slightly Satisfied'  THEN 2
            WHEN 'Needs Improvement'   THEN 1
            ELSE 0
        END), 2) AS average_feedback,
    ROUND(AVG(
        CASE sr.interactive WHEN 'Yes' THEN 1 ELSE 0 END
    ) * 100, 2) AS avg_interactiveness_pct
FROM TotalStudents ts
LEFT JOIN PhaseAttendance pa ON ts.phase_id = pa.phase_id
INNER JOIN LiveSessionHours lsh ON ts.phase_id = lsh.id
INNER JOIN report.phase p ON ts.phase_id = p.id
INNER JOIN report.phase_live_sessions pls ON ts.phase_id = pls.phase_id
INNER JOIN report.student_responses sr ON pls.event_id = sr.event_id
WHERE p.id = (
    SELECT p2.id FROM report.phase p2
    JOIN report.trainings t ON t.id = p2.training_id
    WHERE (t.title ILIKE '%word1%') AND (p2.title ILIKE '%word2%')
    LIMIT 1
)
GROUP BY p.title, ts.total_students, pa.present_students,
         lsh.total_hours, lsh.number_of_live_sessions
-- Replace %word1% with training title keywords, %word2% with phase title keywords
"""
