# schema_course.py — Courses domain schema context for LLM SQL generation
#
# Covers the course platform under schema: course
# Tables: course, course_allowed_colleges, college_batch, course_chapter,
#         course_domain, course_sub_domain, chapter_activity, attendance
#
# Assessment results are fetched through the same path as all other domains:
#   chapter_activity (type='assessment') -> hackathon_id -> public.user_hackathon_participation
#
# Key facts (verified against production DB):
#   course.course              — 267 courses
#   course.course_chapter      — 2,162 chapters
#   course.chapter_activity    — 9,408 activities (1,094 are assessments, 919 unique hackathon_ids)
#   course.attendance          — 27,657 records (17 courses, 170 unique roll_numbers)
#   course.course_allowed_colleges — 2,782 rows (many colleges per course)
#   course.college_batch       — 8 rows
#   course.course_domain       — 5 domains
#   course.course_sub_domain   — 3,350 sub-domains

COURSE_SCHEMA_CONTEXT = """
You have access to the Courses module. This module tracks self-paced and
instructor-led courses offered to college students through the platform.

THIS MODULE COVERS:
  - Course catalog: course names, levels (beginner/intermediate/advanced), domains,
    sub-domains, enrollment counts, registration, hours, publish status.
  - Course structure: chapters per course, activities per chapter (pages, videos,
    resources, assessments, links).
  - Assessment results: chapter activities of type 'assessment' carry a hackathon_id —
    use user_hackathon_participation to retrieve student scores for those assessments.
  - Attendance: per-student daily attendance records linked to courses by roll_number.
  - College access: which colleges have access to which courses via course_allowed_colleges.

NOT FOR:
  - Employability Track / practice leaderboards (use emp domain).
  - POD / Problem of the Day (use pod domain).
  - Standalone hackathon events / MET / profiling tests (use assess domain).
  - Trainings (use trainings domain). Internships (use internship domain).
  - Training live session attendance (present/absent per live session) — use trainings domain.
    Course attendance tracks daily class attendance via course.attendance table only.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TABLES — schema: course
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

-- Top-level course catalog
course.course (
    id                             INTEGER          -- primary key
    course_title                   VARCHAR          -- course name; use ILIKE for keyword search
    course_description             TEXT
    course_domain_id               INTEGER          -- FK to course.course_domain.id
    course_sub_domain_id           INTEGER          -- FK to course.course_sub_domain.id
    course_level                   TEXT             -- 'beginner' | 'intermediate' | 'advanced'
    course_category                TEXT             -- always 'both' currently
    course_hours                   DOUBLE PRECISION -- total duration in hours
    registration_count             INTEGER          -- GLOBAL all-time registration total (pre-aggregated,
                                                   --   matches COUNT(DISTINCT user_id) in course_registration).
                                                   --   NOT per-batch. NOT per-college. Do NOT use for
                                                   --   "how many students are in [batch]" questions.
    view_count                     INTEGER          -- total views
    is_paid                        BOOLEAN          -- is this a paid course?
    is_certificate_available       BOOLEAN          -- is a certificate offered?
    is_published                   TIMESTAMPTZ      -- NULL = not published; NOT NULL = published
    allow_enrollment               BOOLEAN          -- is enrollment open?
    is_locked                      BOOLEAN          -- is it coin-locked?
    coins_to_unlock                DOUBLE PRECISION -- coins needed to unlock (if locked)
    create_at                      TIMESTAMPTZ
    update_at                      TIMESTAMPTZ
)

-- Domain taxonomy (5 domains)
course.course_domain (
    id        INTEGER
    name      VARCHAR  -- 'Role Wise' | 'Technologies' | 'Skills Wise'
                       -- | 'Business and Management' | 'Customized Lesson Plan'
)

-- Sub-domain taxonomy (3,350 sub-domains)
course.course_sub_domain (
    id        INTEGER
    name      VARCHAR  -- e.g. 'MERN Stack Developer', 'Data Scientist', 'Full Stack Java Developer'
    domain_id INTEGER  -- FK to course.course_domain.id
)

-- Chapters inside each course (ordered)
course.course_chapter (
    id                   INTEGER
    chapter_title        VARCHAR
    course_id            INTEGER          -- FK to course.course.id
    order                INTEGER          -- display order within the course
    duration_in_seconds  INTEGER          -- chapter length in seconds
)

-- Activities within each chapter
-- type values: 'page' | 'assessment' | 'resource' | 'video' | 'link' | 'feedbackLink'
-- IMPORTANT: hackathon_id is only populated when type = 'assessment'
course.chapter_activity (
    id                    INTEGER
    course_chapter_id     INTEGER          -- FK to course.course_chapter.id
    type                  TEXT             -- 'page' | 'assessment' | 'resource' | 'video' | 'link' | 'feedbackLink'
    title                 VARCHAR          -- activity title (e.g. 'Assessment 4', 'Introduction Video')
    hackathon_id          INTEGER          -- ONLY set when type = 'assessment'
                                           -- use this to join user_hackathon_participation for scores
    order                 INTEGER          -- display order within the chapter
    video_count           INTEGER
    resource_count        INTEGER
    is_chat_bot_required  BOOLEAN
)

-- College access control (many-to-many: course ↔ college)
course.course_allowed_colleges (
    course_id   INTEGER   -- FK to course.course.id
    college_id  INTEGER   -- FK to public.college.id
)
NOTE: This table tells you which colleges have access to a course.
      It does NOT track enrollment — use course.registration_count or
      user_hackathon_participation for per-student participation data.

-- College-level student batch groupings (for colleges that use batch management)
course.college_batch (
    id          INTEGER
    batch_name  VARCHAR          -- e.g. 'ECE - II_II', 'II CSE'
    college_id  INTEGER          -- FK to public.college.id
    branch      VARCHAR          -- branch/department name
    created_by  VARCHAR          -- faculty email who created the batch
    created_at  TIMESTAMPTZ
    updated_at  TIMESTAMPTZ
)
NOTE: college_batch is used for batch-level grouping within a college.
      It does NOT directly link to course.attendance — attendance links via roll_number to public.user.
NOTE: college_batch has NO course_id column. It links to courses via course_batch_assignment.

-- Roster of students in a college_batch (actual assigned enrollment per batch)
-- COUNT(DISTINCT cbs.id) gives actual batch enrollment — use this instead of registration_count.
course.college_batch_students (
    id           INTEGER
    batch_id     INTEGER          -- FK to course.college_batch.id
    name         VARCHAR          -- student full name
    email        VARCHAR
    roll_number  VARCHAR          -- joins to public.user.roll_number
    created_at   TIMESTAMPTZ
    updated_at   TIMESTAMPTZ
)

-- M:M join between a course and a college_batch
-- A course can be assigned to multiple batches; a batch can have multiple courses.
course.course_batch_assignment (
    id           INTEGER
    course_id    INTEGER          -- FK to course.course.id
    batch_id     INTEGER          -- FK to course.college_batch.id
    assigned_by  VARCHAR          -- faculty email who made the assignment
    assigned_at  TIMESTAMPTZ
)

-- Global enrollment record: one row per student-course registration
-- COUNT(DISTINCT user_id) = global enrollment total (same as registration_count on course.course)
-- Not per-batch. Not per-college.
course.course_registration (
    id                   INTEGER
    user_id              VARCHAR          -- FK to public.user.id
    course_id            INTEGER          -- FK to course.course.id
    is_legacy_completion BOOLEAN
    create_at            TIMESTAMPTZ
    update_at            TIMESTAMPTZ
)

-- Per-student daily attendance records
course.attendance (
    id                   INTEGER
    course_id            INTEGER   -- FK to course.course.id
    attendance_date      DATE      -- the date of attendance
    roll_number          VARCHAR   -- student roll number; join to public.user.roll_number
    status               BOOLEAN   -- TRUE = present | FALSE = absent
    marked_at            TIMESTAMPTZ
    marked_by            VARCHAR   -- faculty email who marked the attendance
    marked_as_role       VARCHAR   -- 'original' | 'substitute'
    is_substitute        BOOLEAN   -- was this a substitute session?
    substitute_course_id INTEGER   -- FK to course.course.id (only when substitute)
)
NOTE: roll_number links to public.user.roll_number — use this to get student name/email/college.
NOTE: marked_by is a faculty email — do NOT use to identify students.
NOTE: Only 17 courses have attendance data (27,657 records, 170 unique students).
NOTE: For attendance percentage: COUNT(CASE WHEN status = true THEN 1 END) / COUNT(*) * 100.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ASSESSMENT RESULTS — HOW TO FETCH SCORES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Each course chapter can have activities of type 'assessment'. These activities
store a hackathon_id which maps directly to public.user_hackathon_participation.
The same rules and tables as the assess domain apply for results.

CHAIN (course → assessment scores):
  course.course
    -> course.course_chapter         (via cc.course_id = c.id)
    -> course.chapter_activity       (via ca.course_chapter_id = cc.id, WHERE ca.type = 'assessment')
    -> public.user_hackathon_participation  (via p.hackathon_id = ca.hackathon_id)
    -> public.user                   (via u.id = p.user_id)
    -> public.college                (via c.id = u.college_id)

CHAIN (course → detailed question-level scores):
  Same as above but replace user_hackathon_participation with
  public.hackathon_final_attempt_submission:
    -> public.hackathon_final_attempt_submission (via f.hackathon_id = ca.hackathon_id)

NOTE: public.hackathon_final_attempt_submission has 24M rows.
      ALWAYS filter by hackathon_id = ca.hackathon_id — never query it without a hackathon filter.
NOTE: ca.hackathon_id from chapter_activity is equivalent to h.id in public.hackathon.
      You do NOT need to join public.hackathon unless you need the hackathon title or metadata.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SHARED REFERENCE TABLES (public schema)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

public.user (
    id           VARCHAR   -- primary key (UUID format)
    first_name   VARCHAR
    last_name    VARCHAR
    email        VARCHAR
    role         TEXT      -- always filter role = 'Student' for students
    college_id   INTEGER   -- FK to public.college.id
    roll_number  VARCHAR   -- use this to join course.attendance.roll_number
)

public.college (
    id   INTEGER
    name VARCHAR
)

-- Per-student total score per assessment (hackathon)
public.user_hackathon_participation (
    id            INTEGER
    hackathon_id  INTEGER     -- equals ca.hackathon_id from chapter_activity
    user_id       VARCHAR     -- FK to public.user.id
    current_score INTEGER     -- pre-aggregated total score; USE for leaderboards — no SUM needed
    start_time    TIMESTAMPTZ
    end_time      TIMESTAMPTZ
    create_at     TIMESTAMPTZ
)

-- Per-question submission detail (use for skill/difficulty breakdown)
-- PERFORMANCE WARNING: 24M rows — always filter by hackathon_id
public.hackathon_final_attempt_submission (
    id                   INTEGER
    user_id              VARCHAR
    hackathon_id         INTEGER
    obtained_score       NUMERIC
    question_score       NUMERIC
    status               TEXT        -- 'pass' | 'fail'
    question_type        TEXT        -- 'mcq' | 'coding' | 'subjective'
    skill                TEXT        -- 'Aptitude' | 'Coding' | 'English'
    question_sub_domain  TEXT[]      -- expand with UNNEST(), NOT jsonb_array_elements
    difficulty           TEXT        -- 'easy' | 'medium' | 'hard'
)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
KEY RELATIONSHIPS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

course.course           -> course.course_domain       via c.course_domain_id = d.id
course.course           -> course.course_sub_domain   via c.course_sub_domain_id = sd.id
course.course_chapter   -> course.course              via cc.course_id = c.id
course.chapter_activity -> course.course_chapter      via ca.course_chapter_id = cc.id
course.chapter_activity -> user_hackathon_participation via p.hackathon_id = ca.hackathon_id
                                                        (ONLY when ca.type = 'assessment')
course.course_allowed_colleges -> course.course       via cac.course_id = c.id
course.course_allowed_colleges -> public.college      via cac.college_id = col.id
course.course_batch_assignment -> course.course       via cba.course_id = c.id
course.course_batch_assignment -> course.college_batch via cb.id = cba.batch_id
course.college_batch_students  -> course.college_batch via cbs.batch_id = cb.id
course.college_batch_students  -> public.user          via u.roll_number = cbs.roll_number (LEFT JOIN)
course.course_registration     -> course.course        via cr.course_id = c.id
course.course_registration     -> public.user          via u.id = cr.user_id
course.attendance       -> course.course              via a.course_id = c.id
course.attendance       -> public.user                via u.roll_number = a.roll_number
public.user             -> public.college             via u.college_id = col.id

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CRITICAL RULES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. COURSE NAME SEARCH — always split into words with AND ILIKE:
   (c.course_title ILIKE '%word1%' AND c.course_title ILIKE '%word2%')
   NEVER use a single ILIKE with the full phrase — it will fail on punctuation.

2. ASSESSMENT FILTER — always add WHERE ca.type = 'assessment' before using ca.hackathon_id.
   Other activity types (page, video, resource, link) do NOT have a hackathon_id.

3. PUBLISHED FILTER — if faculty asks for published/live/active courses:
   WHERE c.is_published IS NOT NULL

4. COLLEGE ACCESS — to find courses for a specific college:
   JOIN course.course_allowed_colleges cac ON cac.course_id = c.id
   JOIN public.college col ON col.id = cac.college_id
   WHERE cac.college_id = (
       SELECT id FROM public.college
       WHERE name ILIKE '%word1%' AND name ILIKE '%word2%'
   )
   Split the faculty's college name into meaningful words and combine with AND ILIKE.
   DO NOT add LIMIT or ORDER BY to the subquery — if multiple colleges match, the system
   will ask the faculty to be more specific. Never silently pick one college over another.

5. STUDENT NAME from attendance — attendance stores roll_number, not user_id.
   To get student names: JOIN public.user u ON u.roll_number = a.roll_number AND u.role = 'Student'
   NOTE: One roll_number may map to multiple user rows (duplicate accounts) — use DISTINCT.

6. ATTENDANCE PERCENTAGE formula:
   ROUND(COUNT(CASE WHEN a.status = true THEN 1 END) * 100.0 / NULLIF(COUNT(*), 0), 2)

7. NEVER join public.hackathon to get assessment title — use ca.title from chapter_activity.
   The hackathon_id in chapter_activity is just the scoring mechanism — the assessment is
   named by ca.title, not by hackathon.title.

8. STUDENT NAME format (consistent with all other domains):
   (TRIM(u.first_name) || ' ' || TRIM(u.last_name)) AS name

9. Always filter u.role = 'Student' when joining public.user for student analytics.

10. Today's date: {today}

11. CRITICAL — TWO DIFFERENT ENROLLMENT NUMBERS:
    The platform has two distinct enrollment concepts — do NOT mix them up:

    A) GLOBAL REGISTRATION TOTAL — use course.course.registration_count (or COUNT from
       course_registration). This is the all-time total across ALL colleges and ALL batches.
       Use for: "how many students have ever registered for [course]", "top courses by enrollment",
       "registration stats". Do NOT use for "how many students in my batch/college".

    B) BATCH-SPECIFIC ENROLLED COUNT — use course_batch_assignment → college_batch_students.
       This is the actual roster for a specific batch at a specific college.
       Use for: "how many students are enrolled in [batch]", "students in ECE batch",
       "enrolled count for [college]'s batch". Pattern: C10.

    RULE: If faculty says "enrolled students in [course]" without specifying a batch/college,
    use the GLOBAL count (registration_count). If they mention a batch name or college, use
    the BATCH count (course_batch_assignment → college_batch_students).

12. CRITICAL — TWO DIFFERENT COURSE LISTS:
    Faculty ask about courses in two distinct ways — match the table to their intent:

    A) "Available courses" / "what courses can [college] access" / "courses for [college]"
       → use course_allowed_colleges
       These are courses the college has been granted access to (may or may not be actively used).
       Pattern: C8, C9.

    B) "Assigned courses" / "my students' courses" / "what are students currently doing"
       / "which courses are active for [college]" / "courses in use by [college]'s batches"
       → use course_batch_assignment JOIN college_batch WHERE college_id = X
       These are courses actively assigned to a college's student batches.
       Pattern: C10.

    NEVER use course_allowed_colleges to answer "what courses are my students assigned to" —
    access ≠ assignment. A college may have access to 200 courses but students only in 3.

13. CRITICAL -- JOIN LIMIT: The query validator rejects any query with more than 6 JOINs.
    Never join more tables than necessary in a single query.
    When you need student name/email -- use public.user only.
    When you need regno/batch info only -- use batch_data only.
    Never use both in the same query. Choose one path and stay on it.

    ASSESSMENT QUERIES WITH COLLEGE FILTER -- special budget rule:
    Pattern C3 uses 4 JOINs (chapter_activity + UHP + user + college).
    course_chapter is NOT a JOIN in C3 -- it is embedded as a subquery inside the
    chapter_activity JOIN condition. Never add course_chapter as an explicit 5th JOIN.
    For a college name filter: use a scalar subquery on u.college_id:
      AND u.college_id = (SELECT id FROM public.college WHERE name ILIKE '%name%')
    Do NOT add course_allowed_colleges as a JOIN on assessment queries --
    college is already accessible via the joined public.user.college_id.

14. CRITICAL — FUZZY TITLE/NAME MATCHING:
    Never filter by name or title using a single ILIKE with the full typed phrase.
    Faculty may omit spaces, dashes, or parts of the full name.
    Instead split the search term into individual meaningful keywords and apply a
    separate ILIKE condition for each keyword:
      (c.course_title ILIKE '%word1%' AND c.course_title ILIKE '%word2%')
    This ensures minor formatting or spelling differences between what faculty type
    and what is stored in the DB do not cause 0 rows.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
QUERY PATTERNS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

PATTERN C1 — COURSE CATALOG: LIST COURSES (optionally by domain/level/college):
-- Use when faculty asks: "what courses are available", "list all beginner courses",
-- "show courses for [college]", "courses in [domain/sub-domain]".
SELECT
    c.id,
    c.course_title,
    d.name AS domain,
    sd.name AS sub_domain,
    c.course_level,
    c.course_hours,
    c.registration_count AS total_enrolled,
    CASE WHEN c.is_published IS NOT NULL THEN 'Published' ELSE 'Unpublished' END AS status
FROM course.course c
JOIN course.course_domain d ON d.id = c.course_domain_id
JOIN course.course_sub_domain sd ON sd.id = c.course_sub_domain_id
-- Uncomment for college filter:
-- JOIN course.course_allowed_colleges cac ON cac.course_id = c.id
-- JOIN public.college col ON col.id = cac.college_id
-- WHERE col.name ILIKE '%keyword%'
-- Uncomment for level filter:
-- WHERE c.course_level = 'beginner'   -- or 'intermediate' / 'advanced'
-- Uncomment for domain filter:
-- WHERE d.name ILIKE '%keyword%'
ORDER BY c.registration_count DESC
LIMIT 50
NOTE: course_category is always 'both' — do not filter by it.
NOTE: course_level values are lowercase: 'beginner', 'intermediate', 'advanced'.

PATTERN C2 — ENROLLMENT COUNT / MOST POPULAR COURSES:
-- Use when faculty asks: "most enrolled courses", "how many students in [course]",
-- "top courses by enrollment", "registration count for [course]".
SELECT
    c.course_title,
    d.name AS domain,
    c.course_level,
    c.registration_count AS total_enrolled,
    c.course_hours
FROM course.course c
JOIN course.course_domain d ON d.id = c.course_domain_id
WHERE c.is_published IS NOT NULL
  -- AND (c.course_title ILIKE '%word1%' AND c.course_title ILIKE '%word2%')
ORDER BY c.registration_count DESC
LIMIT 20
NOTE: registration_count is the GLOBAL all-time total across all colleges/batches.
      Do NOT use this for "how many students are in [batch]" — use C10 for that.

PATTERN C3 — ASSESSMENT SCORES IN A COURSE (top scorers per course assessment):
-- Use when faculty asks: "who scored highest in [course] assessments",
-- "top students in [course]", "assessment results for [course]",
-- "assessment scores for [course] at [college]".
-- BUDGET: 4 JOINs (chapter_activity + UHP + user + college).
--   course_chapter is embedded in the JOIN condition — NOT an explicit JOIN.
--   For college filter: use WHERE u.college_id = (subquery) — NOT a new JOIN.
--   Do NOT add course_allowed_colleges as a JOIN here.
SELECT
    c.course_title,
    ca.title AS assessment_name,
    (TRIM(u.first_name) || ' ' || TRIM(u.last_name)) AS student_name,
    col.name AS college,
    p.current_score
FROM course.course c
JOIN course.chapter_activity ca
    ON ca.course_chapter_id IN (
        SELECT cc.id FROM course.course_chapter cc WHERE cc.course_id = c.id
    )
    AND ca.type = 'assessment'
JOIN public.user_hackathon_participation p ON p.hackathon_id = ca.hackathon_id
JOIN public.user u ON u.id = p.user_id
LEFT JOIN public.college col ON col.id = u.college_id
WHERE u.role = 'Student'
  AND (c.course_title ILIKE '%word1%' AND c.course_title ILIKE '%word2%')
-- For college filter (do NOT add a JOIN -- use scalar subquery):
-- AND u.college_id = (SELECT id FROM public.college WHERE name ILIKE '%college_name%')
ORDER BY p.current_score DESC
LIMIT 50

PATTERN C4 — ASSESSMENT SUMMARY PER COURSE (avg score, participation per assessment):
-- Use when faculty asks: "assessment performance in [course]",
-- "how did students do in [course] assessments", "average scores per assessment".
SELECT
    ca.title AS assessment_name,
    ca.hackathon_id,
    COUNT(DISTINCT p.user_id) AS students_attempted,
    ROUND(AVG(p.current_score), 2) AS avg_score,
    MAX(p.current_score) AS highest_score,
    MIN(p.current_score) AS lowest_score
FROM course.course c
JOIN course.course_chapter cc ON cc.course_id = c.id
JOIN course.chapter_activity ca ON ca.course_chapter_id = cc.id
LEFT JOIN public.user_hackathon_participation p ON p.hackathon_id = ca.hackathon_id
WHERE ca.type = 'assessment'
  AND (c.course_title ILIKE '%word1%' AND c.course_title ILIKE '%word2%')
GROUP BY ca.id, ca.title, ca.hackathon_id, ca.order
ORDER BY ca.order

PATTERN C5 — ATTENDANCE SUMMARY FOR A COURSE:
-- Use when faculty asks: "attendance for [course]", "who has low attendance in [course]",
-- "attendance percentage per student in [course]", "absentees in [course]".
-- NOT FOR: training live session attendance — that uses trainings domain.
SELECT
    (TRIM(u.first_name) || ' ' || TRIM(u.last_name)) AS student_name,
    u.email,
    col.name AS college,
    COUNT(*) AS total_days,
    COUNT(CASE WHEN a.status = true THEN 1 END) AS days_present,
    COUNT(CASE WHEN a.status = false THEN 1 END) AS days_absent,
    ROUND(COUNT(CASE WHEN a.status = true THEN 1 END) * 100.0 / NULLIF(COUNT(*), 0), 2) AS attendance_pct
FROM course.attendance a
JOIN course.course c ON c.id = a.course_id
JOIN public.user u ON u.roll_number = a.roll_number AND u.role = 'Student'
LEFT JOIN public.college col ON col.id = u.college_id
WHERE (c.course_title ILIKE '%word1%' AND c.course_title ILIKE '%word2%')
GROUP BY u.id, u.first_name, u.last_name, u.email, col.name
ORDER BY attendance_pct ASC
LIMIT 50
NOTE: ORDER ASC surfaces lowest attendance first — flip to DESC if faculty wants best attendance.
NOTE: One roll_number may have multiple user rows. Use DISTINCT on u.id in GROUP BY to be safe.
NOTE: Substitute sessions (a.is_substitute = true) are included by default. Add
      WHERE a.is_substitute = false if faculty wants only original sessions.

PATTERN C6 — DAILY ATTENDANCE FOR A COURSE ON A DATE / DATE RANGE:
-- Use when faculty asks: "who was absent on [date] in [course]", 
-- "attendance on [date] for [course]", "show attendance for [month] in [course]".
-- NOT FOR: training live session attendance — that uses trainings domain.
SELECT
    a.attendance_date,
    (TRIM(u.first_name) || ' ' || TRIM(u.last_name)) AS student_name,
    u.email,
    a.roll_number,
    CASE WHEN a.status = true THEN 'Present' ELSE 'Absent' END AS status
FROM course.attendance a
JOIN course.course c ON c.id = a.course_id
JOIN public.user u ON u.roll_number = a.roll_number AND u.role = 'Student'
WHERE (c.course_title ILIKE '%word1%' AND c.course_title ILIKE '%word2%')
  -- AND a.attendance_date = '2025-12-29'        -- uncomment for a specific date
  -- AND a.attendance_date BETWEEN '2025-12-01' AND '2025-12-31'  -- uncomment for date range
  -- AND a.status = false                         -- uncomment to show only absences
ORDER BY a.attendance_date, student_name
LIMIT 50

PATTERN C7 — COURSE STRUCTURE: CHAPTERS AND ACTIVITIES IN A COURSE:
-- Use when faculty asks: "what chapters does [course] have", "how many assessments in [course]",
-- "list the content of [course]", "activity breakdown for [course]".
SELECT
    cc.chapter_title,
    cc.order AS chapter_order,
    COUNT(ca.id) AS total_activities,
    COUNT(CASE WHEN ca.type = 'assessment' THEN 1 END) AS assessments,
    COUNT(CASE WHEN ca.type = 'video' THEN 1 END) AS videos,
    COUNT(CASE WHEN ca.type = 'page' THEN 1 END) AS pages,
    COUNT(CASE WHEN ca.type = 'resource' THEN 1 END) AS resources,
    ROUND(cc.duration_in_seconds / 3600.0, 2) AS chapter_hours
FROM course.course c
JOIN course.course_chapter cc ON cc.course_id = c.id
LEFT JOIN course.chapter_activity ca ON ca.course_chapter_id = cc.id
WHERE (c.course_title ILIKE '%word1%' AND c.course_title ILIKE '%word2%')
GROUP BY cc.id, cc.chapter_title, cc.order, cc.duration_in_seconds
ORDER BY cc.order

PATTERN C8 — COLLEGES WITH ACCESS TO A COURSE:
-- Use when faculty asks: "which colleges have access to [course]",
-- "how many colleges are enrolled in [course]".
SELECT
    col.name AS college_name,
    COUNT(DISTINCT cac.course_id) AS courses_accessible
FROM course.course_allowed_colleges cac
JOIN course.course c ON c.id = cac.course_id
JOIN public.college col ON col.id = cac.college_id
WHERE (c.course_title ILIKE '%word1%' AND c.course_title ILIKE '%word2%')
GROUP BY col.id, col.name
ORDER BY col.name
NOTE: For the reverse — "what courses does [college] have access to" — filter by col.name ILIKE and remove course filter.

PATTERN C9 — COURSES ACCESSIBLE TO A SPECIFIC COLLEGE:
-- Use when faculty asks: "what courses are available to [college]",
-- "show all courses for [college]".
SELECT
    c.course_title,
    d.name AS domain,
    c.course_level,
    c.course_hours,
    c.registration_count AS total_enrolled,
    CASE WHEN c.is_published IS NOT NULL THEN 'Published' ELSE 'Unpublished' END AS status
FROM course.course_allowed_colleges cac
JOIN course.course c ON c.id = cac.course_id
JOIN course.course_domain d ON d.id = c.course_domain_id
JOIN public.college col ON col.id = cac.college_id
WHERE cac.college_id = (
    SELECT id FROM public.college
    WHERE name ILIKE '%word1%' AND name ILIKE '%word2%'
)
ORDER BY c.registration_count DESC
LIMIT 50

PATTERN C10 — BATCH-SPECIFIC ENROLLED STUDENT COUNT FOR A COURSE:
-- Use when faculty asks: "how many students are enrolled in [batch] for [course]",
-- "students in ECE batch", "enrolled count for [college]'s batch",
-- "how many students are in [batch_name]", "show me students in [batch]".
-- This returns the actual batch roster, NOT the global registration_count.
-- Two colleges may share the same batch_name — filter by college if specified.
SELECT
    cb.batch_name,
    cb.branch,
    (SELECT col.name FROM public.college col WHERE col.id = cb.college_id) AS college,
    COUNT(cbs.id) AS enrolled_students
FROM course.course c
JOIN course.course_batch_assignment cba ON cba.course_id = c.id
JOIN course.college_batch cb ON cb.id = cba.batch_id
LEFT JOIN course.college_batch_students cbs ON cbs.batch_id = cb.id
-- Filter by course name:
-- WHERE (c.course_title ILIKE '%word1%' AND c.course_title ILIKE '%word2%')
-- Filter by batch name (if faculty mentions batch):
-- AND (cb.batch_name ILIKE '%word1%' AND cb.batch_name ILIKE '%word2%')
-- Filter by college (if faculty mentions their college):
-- AND cb.college_id = (SELECT id FROM public.college WHERE name ILIKE '%word1%')
GROUP BY cb.id, cb.batch_name, cb.branch, cb.college_id
ORDER BY enrolled_students DESC
LIMIT 20
NOTE: Use a scalar subquery for college name (not a JOIN) to stay within the 6-JOIN limit.
NOTE: college_batch_students.id counts the actual roster rows — do NOT use registration_count here.

PATTERN C10b — STUDENT LIST FOR A BATCH:
-- Use when faculty asks: "list all students in [batch]", "who is in [batch]",
-- "show me the roster for [batch]".
SELECT
    cbs.name AS student_name,
    cbs.email,
    cbs.roll_number,
    cb.batch_name,
    (SELECT col.name FROM public.college col WHERE col.id = cb.college_id) AS college
FROM course.college_batch cb
JOIN course.college_batch_students cbs ON cbs.batch_id = cb.id
-- Filter by batch name:
-- WHERE (cb.batch_name ILIKE '%word1%' AND cb.batch_name ILIKE '%word2%')
-- Filter by course (if faculty mentions course):
-- AND cb.id IN (SELECT cba.batch_id FROM course.course_batch_assignment cba
--               JOIN course.course c ON c.id = cba.course_id
--               WHERE c.course_title ILIKE '%word1%')
ORDER BY cbs.name
LIMIT 50
"""
