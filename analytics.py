# analytics.py — TapTap Analytics Chatbot (LLM Query Generation approach)
# Three domain dispatchers — synchronous, matching original project pattern.
# Each feeds a curated schema context + faculty question to the LLM which
# generates SQL, then we validate and execute it.

import re
from datetime import date
from typing import Any
from sqlalchemy import text
from db import get_db
from logger import logger
from constants import SQL_MAX_ROWS, SQL_MAX_CHAIN
from models import gpt_4o_mini_llm as _llm
from schema_pod import POD_SCHEMA_CONTEXT
from schema_assess import ASSESS_SCHEMA_CONTEXT



# ══════════════════════════════════════════════════════════════════════════════
# CURATED SCHEMA CONTEXT
# Only business-relevant columns. No internal ops, no passwords, no scaling tables.
# ══════════════════════════════════════════════════════════════════════════════

_EMP_SCHEMA_CONTEXT = """
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

# POD and Assess schema contexts — pending Abdul granting access
_POD_SCHEMA_CONTEXT    = None
_ASSESS_SCHEMA_CONTEXT = None


# ══════════════════════════════════════════════════════════════════════════════
# SQL GENERATION PROMPT
# ══════════════════════════════════════════════════════════════════════════════

_SQL_SYSTEM = """You are a PostgreSQL SQL expert for a college analytics chatbot.
Faculty ask questions about student performance and you generate SQL to answer them.

RULES:
1. Return ONLY the raw SQL query — no explanation, no markdown, no backticks.
2. Always use SELECT — never INSERT, UPDATE, DELETE, DROP, CREATE, or any DDL/DML.
3. Always add LIMIT {{max_rows}} unless the faculty explicitly asked for all records.
4. Use ILIKE for all text filtering (case-insensitive).
5. Always use table aliases for readability.
6. Round decimal results to 2 places using ROUND(..., 2).
7. For pass rates: ROUND(COUNT(CASE WHEN status = 'pass' THEN 1 END) * 100.0 / NULLIF(COUNT(*), 0), 2)
8. If the question cannot be answered from the given schema, return exactly: UNSUPPORTED
9. Never expose passwords, tokens, or internal system columns.

CRITICAL — STANDARD PATTERNS:
The schema context contains STANDARD QUERY PATTERNS. These are mandatory templates.
If the faculty question matches one of these patterns (profile, top scorers, pass rate, recent activity),
you MUST use that exact pattern as your base — only substitute the specific filters/values.
DO NOT invent a different SQL structure for these known query types.
"""

_SQL_USER_TEMPLATE = """Schema:
{schema}

Faculty question: {question}

Generate the SQL query:"""


# ══════════════════════════════════════════════════════════════════════════════
# SQL VALIDATION
# ══════════════════════════════════════════════════════════════════════════════

_FORBIDDEN = re.compile(
    r'\b(INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|TRUNCATE|GRANT|REVOKE|EXEC|EXECUTE)\b',
    re.IGNORECASE
)


def _validate_sql(sql: str) -> tuple[bool, str]:
    """Returns (is_valid, validated_sql_or_error)."""
    sql = sql.strip()

    if sql == "UNSUPPORTED":
        return False, "UNSUPPORTED"

    if not sql.upper().lstrip().startswith("SELECT"):
        return False, "Only SELECT queries are allowed."

    if _FORBIDDEN.search(sql):
        return False, "Query contains forbidden keywords."

    # Inject LIMIT if missing
    if "LIMIT" not in sql.upper():
        sql = sql.rstrip(";") + f" LIMIT {SQL_MAX_ROWS}"

    return True, sql


# ══════════════════════════════════════════════════════════════════════════════
# CORE: GENERATE SQL + EXECUTE
# ══════════════════════════════════════════════════════════════════════════════

def _rows_to_dicts(rows) -> list[dict]:
    return [dict(r._mapping) for r in rows]


def _generate_and_run(question: str, schema_context: str) -> dict[str, Any]:
    """
    Synchronous: generate SQL via LLM, validate, execute, return results.
    Includes:
      - SQL chain drift control: regenerates from scratch after SQL_MAX_CHAIN follow-ups
      - Self-healing retry: if DB execution fails, LLM attempts to fix the SQL once
    Returns: { "data": [...], "sql": "...", "error": None }
          or { "data": [], "sql": "...", "error": "message" }
    """
    schema_with_date = schema_context.format(today=date.today().isoformat())

    # Step 1: Generate SQL (synchronous LLM call)
    try:
        response = _llm.invoke([
            {"role": "system", "content": _SQL_SYSTEM.format(max_rows=SQL_MAX_ROWS)},
            {"role": "user",   "content": _SQL_USER_TEMPLATE.format(
                schema=schema_with_date,
                question=question
            )},
        ])
        raw_sql = response.content.strip()
        # Strip markdown fences if LLM wraps output
        if raw_sql.startswith("```"):
            raw_sql = re.sub(r"^```(?:sql)?|```$", "", raw_sql, flags=re.MULTILINE).strip()
        logger.info(f"[sql_gen] SQL: {raw_sql[:200]}")
    except Exception as e:
        logger.error(f"[sql_gen] LLM error: {e}")
        return {"data": [], "sql": None, "error": str(e)}

    # Step 2: Validate
    is_valid, result = _validate_sql(raw_sql)
    if not is_valid:
        return {"data": [], "sql": raw_sql, "error": result}

    validated_sql = result

    # Step 3: Execute — with self-healing retry on DB error
    db = next(get_db())
    try:
        rows = db.execute(text(validated_sql)).fetchall()
        data = _rows_to_dicts(rows)
        logger.info(f"[sql_exec] {len(data)} rows returned")
        return {"data": data, "sql": validated_sql, "error": None}
    except Exception as first_err:
        logger.warning(f"[sql_exec] DB error — attempting self-heal: {first_err}")
        # Self-healing retry: ask LLM to fix the syntax error only
        try:
            fix_response = _llm.invoke([
                {"role": "system", "content": _SQL_SYSTEM.format(max_rows=SQL_MAX_ROWS)},
                {"role": "user", "content": (
                    f"The following SQL query failed with this error:\n"
                    f"Error: {first_err}\n\n"
                    f"SQL:\n{validated_sql}\n\n"
                    f"Fix ONLY the syntax or structural error. "
                    f"Keep the logic and filters identical. "
                    f"Return only the corrected SQL — no explanation."
                )},
            ])
            fixed_sql = fix_response.content.strip()
            if fixed_sql.startswith("```"):
                fixed_sql = re.sub(r"^```(?:sql)?|```$", "", fixed_sql, flags=re.MULTILINE).strip()

            is_valid2, fixed_result = _validate_sql(fixed_sql)
            if not is_valid2:
                raise Exception(f"Fixed SQL failed validation: {fixed_result}")

            rows = db.execute(text(fixed_result)).fetchall()
            data = _rows_to_dicts(rows)
            logger.info(f"[sql_exec] self-heal succeeded — {len(data)} rows returned")
            return {"data": data, "sql": fixed_result, "error": None}
        except Exception as second_err:
            logger.error(f"[sql_exec] self-heal failed: {second_err}")
            return {"data": [], "sql": validated_sql, "error": str(first_err)}


# ══════════════════════════════════════════════════════════════════════════════
# DOMAIN DISPATCHERS — synchronous, matching original project pattern
# ══════════════════════════════════════════════════════════════════════════════

def get_emp_data(question: str) -> dict[str, Any]:
    """Employability Track dispatcher."""
    logger.info(f"[emp_dispatch] question='{question[:80]}'")
    return _generate_and_run(question, _EMP_SCHEMA_CONTEXT)


def get_pod_data(question: str) -> dict[str, Any]:
    """POD dispatcher — uses LLM SQL generation with curated schema context."""
    logger.info(f"[pod_dispatch] question='{question[:80]}'")
    # TODO: uncomment when grants pod schema access
    # return _generate_and_run(question, POD_SCHEMA_CONTEXT)
    return {"data": [], "sql": None, "error": "SCHEMA_PENDING"}


def get_assess_data(question: str) -> dict[str, Any]:
    """Assessments dispatcher — uses LLM SQL generation with curated schema context."""
    logger.info(f"[assess_dispatch] question='{question[:80]}'")
    # TODO: uncomment when grants gest schema access
    # return _generate_and_run(question, ASSESS_SCHEMA_CONTEXT)
    return {"data": [], "sql": None, "error": "SCHEMA_PENDING"}