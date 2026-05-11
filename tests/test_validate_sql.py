# tests/test_validate_sql.py
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from analytics import _extract_select_blocks

def test_plain_select_returns_one_block():
    sql = "SELECT id FROM public.user WHERE role = 'Student'"
    blocks = _extract_select_blocks(sql)
    assert len(blocks) == 1
    assert "public.user" in blocks[0]

def test_single_cte_returns_two_blocks():
    sql = """
    WITH active AS (
        SELECT id FROM public.user WHERE role = 'Student'
    )
    SELECT * FROM active
    """
    blocks = _extract_select_blocks(sql)
    assert len(blocks) == 2
    assert "public.user" in blocks[0]   # CTE body
    assert "active" in blocks[1]        # main SELECT

def test_two_ctes_returns_three_blocks():
    sql = """
    WITH a AS (
        SELECT id FROM t1 JOIN t2 ON t1.id = t2.id
    ), b AS (
        SELECT x FROM t3 JOIN t4 ON t3.x = t4.x JOIN t5 ON t4.y = t5.y
    )
    SELECT * FROM a JOIN b ON a.id = b.x
    """
    blocks = _extract_select_blocks(sql)
    assert len(blocks) == 3
    # First CTE has 1 JOIN
    assert blocks[0].upper().count("JOIN") == 1
    # Second CTE has 2 JOINs
    assert blocks[1].upper().count("JOIN") == 2
    # Main SELECT has 1 JOIN
    assert blocks[2].upper().count("JOIN") == 1

def test_nested_subquery_in_cte_not_split():
    # Subquery inside a CTE should NOT produce extra blocks
    sql = """
    WITH ranked AS (
        SELECT id, RANK() OVER (ORDER BY score DESC) AS r
        FROM (SELECT id, SUM(score) AS score FROM t GROUP BY id) sub
    )
    SELECT * FROM ranked WHERE r <= 10
    """
    blocks = _extract_select_blocks(sql)
    assert len(blocks) == 2   # CTE body + main SELECT

def test_plain_select_with_subquery_returns_one_block():
    # A subquery in the FROM clause of a plain SELECT — not a CTE
    sql = """
    SELECT *
    FROM (SELECT id FROM t1 JOIN t2 ON t1.id = t2.id) sub
    JOIN t3 ON sub.id = t3.id
    """
    blocks = _extract_select_blocks(sql)
    assert len(blocks) == 1


from analytics import _validate_sql

# ── Existing flat behaviour preserved ────────────────────────────────────────

def test_plain_select_7_joins_rejected():
    # 7 JOINs in a flat SELECT — must still be rejected
    sql = (
        "SELECT * FROM t1 "
        "JOIN t2 ON t1.a=t2.a "
        "JOIN t3 ON t2.b=t3.b "
        "JOIN t4 ON t3.c=t4.c "
        "JOIN t5 ON t4.d=t5.d "
        "JOIN t6 ON t5.e=t6.e "
        "JOIN t7 ON t6.f=t7.f "
        "JOIN t8 ON t7.g=t8.g"
    )
    valid, msg = _validate_sql(sql)
    assert not valid
    assert "too many JOINs" in msg

def test_plain_select_6_joins_allowed():
    sql = (
        "SELECT * FROM t1 "
        "JOIN t2 ON t1.a=t2.a "
        "JOIN t3 ON t2.b=t3.b "
        "JOIN t4 ON t3.c=t4.c "
        "JOIN t5 ON t4.d=t5.d "
        "JOIN t6 ON t5.e=t6.e "
        "JOIN t7 ON t6.f=t7.f"
    )
    valid, _ = _validate_sql(sql)
    assert valid

# ── CTE queries that were previously (wrongly) rejected ──────────────────────

def test_cte_3x3_joins_allowed():
    # 3 CTEs × 3 JOINs each = 9 total, but max per block is 3 — must PASS
    sql = """
    WITH a AS (
        SELECT * FROM t1
        JOIN t2 ON t1.id=t2.id
        JOIN t3 ON t2.id=t3.id
        JOIN t4 ON t3.id=t4.id
    ), b AS (
        SELECT * FROM t5
        JOIN t6 ON t5.id=t6.id
        JOIN t7 ON t6.id=t7.id
        JOIN t8 ON t7.id=t8.id
    ), c AS (
        SELECT * FROM t9
        JOIN t10 ON t9.id=t10.id
        JOIN t11 ON t10.id=t11.id
        JOIN t12 ON t11.id=t12.id
    )
    SELECT * FROM a JOIN b ON a.id=b.id JOIN c ON b.id=c.id
    """
    valid, msg = _validate_sql(sql)
    assert valid, f"Expected valid but got: {msg}"

def test_cte_single_block_7_joins_rejected():
    # One CTE with 7 JOINs in it — must be REJECTED even though it's a CTE
    sql = """
    WITH fat AS (
        SELECT * FROM t1
        JOIN t2 ON t1.a=t2.a
        JOIN t3 ON t2.b=t3.b
        JOIN t4 ON t3.c=t4.c
        JOIN t5 ON t4.d=t5.d
        JOIN t6 ON t5.e=t6.e
        JOIN t7 ON t6.f=t7.f
        JOIN t8 ON t7.g=t8.g
    )
    SELECT * FROM fat
    """
    valid, msg = _validate_sql(sql)
    assert not valid
    assert "too many JOINs" in msg

def test_cartesian_guard_per_block():
    # Main SELECT has 3 JOINs but only 1 ON — cartesian product guard must fire
    sql = """
    WITH ok AS (
        SELECT * FROM t1 JOIN t2 ON t1.id=t2.id
    )
    SELECT * FROM ok JOIN t3 JOIN t4 JOIN t5 ON t3.id=t4.id
    """
    valid, msg = _validate_sql(sql)
    assert not valid
    assert "cartesian" in msg.lower() or "ON/USING" in msg

def test_unsupported_still_rejected():
    valid, msg = _validate_sql("UNSUPPORTED")
    assert not valid
    assert msg == "UNSUPPORTED"

def test_forbidden_keyword_rejected():
    valid, msg = _validate_sql("DROP TABLE public.user")
    assert not valid

def test_limit_injected_when_missing():
    sql = "SELECT id FROM public.user WHERE role = 'Student'"
    valid, result_sql = _validate_sql(sql)
    assert valid
    assert "LIMIT" in result_sql.upper()

def test_limit_not_duplicated_when_present():
    sql = "SELECT id FROM public.user LIMIT 10"
    valid, result_sql = _validate_sql(sql)
    assert valid
    assert result_sql.upper().count("LIMIT") == 1


# ── advice_node state tests ──────────────────────────────────────────────────

import json as _json

def test_tapTapState_has_advice_data_field():
    """TapTapState must accept advice_data as a key."""
    from llm import TapTapState
    state: TapTapState = {
        "user_query": "test",
        "messages": [],
        "domain": None,
        "direct_answer": None,
        "sql_query": None,
        "sql_result": None,
        "sql_error": None,
        "sql_data_summary": None,
        "advice_data": [{"topic": "Sorting", "pass_rate": 0.3}],
        "final_answer": None,
    }
    assert state["advice_data"][0]["topic"] == "Sorting"

def test_formatter_node_populates_advice_data():
    """formatter_node must include advice_data = full data list in its return dict."""
    from unittest.mock import patch, MagicMock
    from llm import formatter_node

    fake_data = [{"topic": f"T{i}", "pass_rate": i * 0.1} for i in range(10)]

    state = {
        "user_query": "show weak topics",
        "sql_result": fake_data,
        "sql_error": None,
        "domain": "emp",
        "sql_data_summary": None,
    }

    fake_response = MagicMock()
    fake_response.content = "Here are the results."

    with patch("llm.gpt_4o_mini_llm") as mock_llm:
        mock_llm.invoke.return_value = fake_response
        result = formatter_node(state)

    assert "advice_data" in result
    assert result["advice_data"] == fake_data

def test_formatter_node_advice_data_is_full_not_truncated():
    """advice_data must contain ALL rows, not just 4."""
    from unittest.mock import patch, MagicMock
    from llm import formatter_node

    fake_data = [{"topic": f"T{i}", "pass_rate": i * 0.05} for i in range(20)]

    state = {
        "user_query": "weak areas",
        "sql_result": fake_data,
        "sql_error": None,
        "domain": "emp",
        "sql_data_summary": None,
    }

    fake_response = MagicMock()
    fake_response.content = "Results formatted."

    with patch("llm.gpt_4o_mini_llm") as mock_llm:
        mock_llm.invoke.return_value = fake_response
        result = formatter_node(state)

    assert len(result["advice_data"]) == 20

def test_advice_node_uses_full_data_in_user_text():
    """advice_node must include all advice_data rows in the user_text sent to LLM."""
    from unittest.mock import patch, MagicMock
    from llm import advice_node

    full_data = [{"subdomain": f"Topic{i}", "pass_rate": 0.1 * i} for i in range(8)]

    state = {
        "user_query": "what should students study?",
        "sql_data_summary": "Previous question: weak topics\nPrevious result sample (4 rows):\n[]",
        "advice_data": full_data,
    }

    fake_response = MagicMock()
    fake_response.content = "Topic0 — 0% pass rate → assign practice"

    with patch("llm.gpt_4o_mini_llm") as mock_llm:
        mock_llm.invoke.return_value = fake_response
        advice_node(state)

    call_args = mock_llm.invoke.call_args
    messages = call_args[0][0]
    human_content = messages[1].content
    assert "8 rows" in human_content
    assert "Topic7" in human_content

def test_advice_node_falls_back_when_advice_data_missing():
    """advice_node must not crash when advice_data is absent from state."""
    from unittest.mock import patch, MagicMock
    from llm import advice_node

    state = {
        "user_query": "what should students study?",
        "sql_data_summary": "Previous question: weak topics",
    }

    fake_response = MagicMock()
    fake_response.content = "Some advice."

    with patch("llm.gpt_4o_mini_llm") as mock_llm:
        mock_llm.invoke.return_value = fake_response
        result = advice_node(state)

    assert "final_answer" in result
