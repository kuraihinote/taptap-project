# analytics.py — TapTap Analytics Chatbot (LLM Query Generation approach)
# Three domain dispatchers — synchronous, matching original project pattern.
# Each feeds a curated schema context + faculty question to the LLM which
# generates SQL, then we validate and execute it.

import decimal
import re
from datetime import datetime, date
from typing import Any
from sqlalchemy import text
from db import get_db
from logger import logger
from constants import SQL_MAX_ROWS
from models import gpt_4o_llm as _llm



# ══════════════════════════════════════════════════════════════════════════════
# CURATED SCHEMA CONTEXT
# Only business-relevant columns. No internal ops, no passwords, no scaling tables.
# ══════════════════════════════════════════════════════════════════════════════



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
8. For questions about students scoring above or below a percentage threshold on employability (e.g. less than 50%, more than 20%, above 80%), always use Pattern 6 from the schema context. Never return UNSUPPORTED for percentage threshold questions.
9. For any question that mentions a percentage, score threshold, or employability score filter, attempt to write SQL using SUM(obtained_score) * 100.0 / NULLIF(SUM(points), 0) grouped by student — do not return UNSUPPORTED.
10. For relative date expressions ("today", "this week", "this month", "last month", etc.),
    use PostgreSQL date functions (DATE_TRUNC, CURRENT_DATE, INTERVAL) to compute the
    correct date range dynamically. Never hardcode specific dates.
11. Return UNSUPPORTED ONLY if the question requires data, columns, or tables that
    genuinely do not exist anywhere in the schema provided.
    NEVER return UNSUPPORTED because no pattern matches the query shape — if the columns
    exist to answer the question, reason from the schema directly and write the SQL.
    Absence of a matching pattern is NOT a reason to return UNSUPPORTED.
    For questions asking for recommendations, action plans, or next steps based on
    performance — fetch topic/subdomain-level weak area data so recommendations can
    reference specific topics (e.g. Array, Essay Writing) rather than broad skills.
    Never return UNSUPPORTED for action/recommendation questions — always fetch
    the most granular performance data available to generate specific advice.
12. Never expose passwords, tokens, or internal system columns.
13. CRITICAL PERFORMANCE RULE — hackathon_final_attempt_submission (~24M rows):
    If a query uses public.hackathon_final_attempt_submission, it MUST include:
        WHERE f.hackathon_id = (subquery)
    A query without this condition is INVALID and must be rewritten.
    DO NOT:
    - JOIN public.hackathon in the outer query to filter by title
    - Apply h.title ILIKE in the outer WHERE clause
    - Use a CTE or JOIN to pass hackathon_id
    This rule applies ONLY to hackathon_final_attempt_submission.
    JOIN-based filtering is allowed for other tables (A3, A4, A5 etc.).
    SELF-CHECK: before returning SQL, verify — if hackathon_final_attempt_submission
    is used, ensure f.hackathon_id = (subquery) is present. If not, rewrite.

CRITICAL — STANDARD PATTERNS:
The schema context contains STANDARD QUERY PATTERNS. These are fast-lane templates,
not a whitelist. Use them as follows:
- If the faculty question matches a known pattern → use that pattern as your base,
  substituting only the specific filters/values.
- If NO pattern matches → reason from the schema columns directly and write correct
  SQL from scratch. Use any valid PostgreSQL features the schema supports (UNNEST for
  arrays, CTEs, window functions, JSONB operators, etc.).
DO NOT invent a different SQL structure when a matching pattern exists.
DO NOT return UNSUPPORTED just because no pattern matches — write the SQL yourself.
CRITICAL — PATTERN OVERRIDE: When a documented pattern explicitly states which table
to use or explicitly prohibits a specific table, that instruction takes absolute
priority over your own table selection. Do NOT substitute a different table even if
it sounds more semantically correct. Trust the documented pattern — it has been
validated against the actual database.
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


def _extract_select_blocks(sql: str) -> list[str]:
    """
    Split a SQL string into independent SELECT blocks for per-block JOIN validation.

    For a plain SELECT (no CTEs): returns [whole_sql].
    For a WITH query: returns [cte1_body, cte2_body, ..., main_select].

    Uses a paren-depth character walker — not regex — so nested subqueries
    inside CTEs are captured whole and don't create spurious extra blocks.
    """
    stripped = sql.strip()
    upper = stripped.upper().lstrip()

    # Plain SELECT — no CTE splitting needed
    if not upper.startswith("WITH"):
        return [stripped]

    blocks: list[str] = []
    i = 0
    n = len(stripped)

    # Walk over "WITH name AS (...), name AS (...), ..." collecting CTE bodies
    # State: we are between CTEs when depth == 0
    depth = 0
    cte_body_start = -1  # char index of the opening '(' of a CTE body

    while i < n:
        ch = stripped[i]

        if ch == '(':
            if depth == 0:
                # Opening paren of a CTE body — record start (content after '(')
                cte_body_start = i + 1
            depth += 1

        elif ch == ')':
            depth -= 1
            if depth == 0 and cte_body_start != -1:
                # Closing paren of a CTE body — extract content
                blocks.append(stripped[cte_body_start:i])
                cte_body_start = -1

                # Check if more CTEs follow (next non-whitespace char is ',')
                j = i + 1
                while j < n and stripped[j] in (' ', '\t', '\n', '\r'):
                    j += 1
                if j < n and stripped[j] == ',':
                    # Another CTE — skip past the comma; outer loop continues
                    i = j  # will be incremented below
                else:
                    # No more CTEs — everything after this is the main SELECT
                    main_select = stripped[i + 1:].strip()
                    if main_select:
                        blocks.append(main_select)
                    break  # done

        i += 1

    # Fallback: if WITH parse found nothing (malformed SQL), return whole string
    if not blocks:
        return [stripped]

    return blocks


def _validate_sql(sql: str) -> tuple[bool, str]:
    """Returns (is_valid, validated_sql_or_error)."""
    sql = sql.strip()

    if sql == "UNSUPPORTED":
        return False, "UNSUPPORTED"

    sql_upper = sql.upper().lstrip()
    if not (sql_upper.startswith("SELECT") or sql_upper.startswith("WITH")):
        return False, "Only SELECT queries are allowed."

    if _FORBIDDEN.search(sql):
        return False, "Query contains forbidden keywords."

    # ── JOIN sanity checks (per-block — CTE bodies validated independently) ───
    # Each CTE body and the final main SELECT are checked separately so a
    # legitimate 3-CTE query with 3 JOINs per CTE is not rejected for having
    # 9 JOINs "total". The 6-JOIN limit applies within each independent block.
    for block in _extract_select_blocks(sql):
        block_upper = block.upper()
        block_join_count  = len(re.findall(r'\bJOIN\b',  block_upper))
        block_on_count    = len(re.findall(r'\bON\b',    block_upper))
        block_using_count = len(re.findall(r'\bUSING\b', block_upper))

        if block_join_count > 6:
            return False, (
                f"Query rejected: too many JOINs ({block_join_count}) in a single query block. "
                "Maximum allowed is 6 per block."
            )

        # Cartesian product guard — each JOIN should have a matching ON/USING clause.
        # Allow a tolerance of 1 (e.g. CROSS JOIN intentionally has no ON).
        block_on_using = block_on_count + block_using_count
        if block_join_count > 0 and (block_join_count - block_on_using) > 1:
            return False, (
                f"Query rejected: {block_join_count} JOIN(s) but only {block_on_using} "
                "ON/USING clause(s) in a query block. "
                "Possible cartesian product — ensure every JOIN has an ON or USING condition."
            )

    # ── Large table scan guard ────────────────────────────────────────────────
    # hackathon_final_attempt_submission has ~24M rows.
    # Any query against it without a hackathon_id or test_type_id filter will time out.
    # Detect this and return a scoping error so the formatter can ask faculty to narrow down.
    sql_normalized = sql.upper().replace(" ", "").replace("\n", "")
    if "HACKATHON_FINAL_ATTEMPT_SUBMISSION" in sql_normalized:
        # Keyword presence check — robust to aliasing and formatting differences
        has_hackathon_id_subquery = "HACKATHON_ID" in sql_normalized and "(SELECT" in sql_normalized
        has_participation_filter = "USER_HACKATHON_PARTICIPATION" in sql_normalized
        has_having = "HAVING" in sql_normalized
        has_proper_subquery = has_hackathon_id_subquery and has_participation_filter and has_having
        has_test_type_id_filter = "TEST_TYPE_ID" in sql_normalized
        if not has_proper_subquery and not has_test_type_id_filter:
            logger.warning(
                f"[validate_sql] Rejected — hackathon_final_attempt_submission queried "
                f"without proper hackathon_id subquery | sql_preview={sql[:120]}"
            )
            return False, (
                "INVALID_QUERY_PATTERN: Queries on hackathon_final_attempt_submission "
                "must use hackathon_id subquery with participation filter. "
                "Do not use JOIN-based title filtering on this table."
            )

    # Inject LIMIT if missing
    if "LIMIT" not in sql.upper():
        sql = sql.rstrip(";") + f" LIMIT {SQL_MAX_ROWS}"

    return True, sql


# ══════════════════════════════════════════════════════════════════════════════
# CORE: GENERATE SQL + EXECUTE
# ══════════════════════════════════════════════════════════════════════════════

def _rows_to_dicts(rows) -> list[dict]:
    result = []
    for r in rows:
        row = {}
        for k, v in r._mapping.items():
            if isinstance(v, decimal.Decimal):
                v = float(v)
            elif isinstance(v, (datetime, date)):
                v = v.isoformat()
            row[k] = v
        result.append(row)
    return result


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
        logger.warning(f"[validate_sql] Rejected | reason={result[:80]} | sql_preview={raw_sql[:80]}")
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
        # ── College disambiguation short-circuit ─────────────────────────────
        # If the college name subquery matched multiple colleges, PostgreSQL raises
        # "more than one row returned by a subquery used as an expression".
        # We must catch this BEFORE the self-heal retry — otherwise the LLM will
        # silently fix it by adding LIMIT 1, picking the wrong college.
        if "more than one row returned by a subquery" in str(first_err).lower():
            logger.warning(
                f"[sql_exec] Ambiguous college name — subquery returned multiple rows. "
                f"Returning AMBIGUOUS_COLLEGE error | sql_preview={validated_sql[:120]}"
            )
            db.rollback()
            return {"data": [], "sql": validated_sql, "error": "AMBIGUOUS_COLLEGE"}

        logger.warning(f"[sql_exec] DB error — attempting self-heal: {first_err}")
        db.rollback()  # clear aborted transaction so the retry can execute cleanly
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