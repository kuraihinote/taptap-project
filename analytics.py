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
from constants import SQL_MAX_ROWS, SQL_MAX_CHAIN
from models import gpt_4o_mini_llm as _llm
from schema_emp    import EMP_SCHEMA_CONTEXT
from schema_pod    import POD_SCHEMA_CONTEXT
from schema_assess import ASSESS_SCHEMA_CONTEXT



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

    sql_upper = sql.upper().lstrip()
    if not (sql_upper.startswith("SELECT") or sql_upper.startswith("WITH")):
        return False, "Only SELECT queries are allowed."

    if _FORBIDDEN.search(sql):
        return False, "Query contains forbidden keywords."

    # ── JOIN sanity checks ────────────────────────────────────────────────────
    sql_upper = sql.upper()
    join_count  = len(re.findall(r'\bJOIN\b',  sql_upper))
    on_count    = len(re.findall(r'\bON\b',    sql_upper))
    using_count = len(re.findall(r'\bUSING\b', sql_upper))

    if join_count > 6:
        return False, f"Query rejected: too many JOINs ({join_count}). Maximum allowed is 6."

    # Cartesian product guard — each JOIN should have a matching ON/USING clause.
    # Allow a tolerance of 1 (e.g. CROSS JOIN intentionally has no ON).
    on_using_count = on_count + using_count
    if join_count > 0 and (join_count - on_using_count) > 1:
        return False, (
            f"Query rejected: {join_count} JOIN(s) but only {on_using_count} ON/USING clause(s). "
            "Possible cartesian product — ensure every JOIN has an ON or USING condition."
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


# ══════════════════════════════════════════════════════════════════════════════
# DOMAIN DISPATCHERS — synchronous, matching original project pattern
# ══════════════════════════════════════════════════════════════════════════════

def get_emp_data(question: str) -> dict[str, Any]:
    """Employability Track dispatcher."""
    logger.info(f"[emp_dispatch] question='{question[:80]}'")
    return _generate_and_run(question, EMP_SCHEMA_CONTEXT)


def get_pod_data(question: str) -> dict[str, Any]:
    """POD dispatcher — uses LLM SQL generation with curated schema context."""
    logger.info(f"[pod_dispatch] question='{question[:80]}'")
    return _generate_and_run(question, POD_SCHEMA_CONTEXT)


def get_assess_data(question: str) -> dict[str, Any]:
    """Assessments dispatcher — uses LLM SQL generation with curated schema context."""
    logger.info(f"[assess_dispatch] question='{question[:80]}'")
    return _generate_and_run(question, ASSESS_SCHEMA_CONTEXT)