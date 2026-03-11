# llm.py — TapTap POD Analytics Chatbot
# Contains:
#   - Azure OpenAI LLM setup
#   - Classification prompt
#   - Format prompt
#   - LangGraph 3-node pipeline: classify → execute → format
#   - build_graph() called once at startup

import json
import decimal
from datetime import datetime, date
from typing import Any

from langchain_openai import AzureChatOpenAI
from langgraph.graph import StateGraph, END

from constants import (
    LLM_TEMPERATURE, LLM_MAX_TOKENS,
    ALL_INTENTS, INTENT_UNKNOWN,
    INTENT_POD_WHO_SOLVED_TODAY, INTENT_POD_ATTEMPT_COUNT_TODAY,
    INTENT_POD_QUESTION_TODAY, INTENT_POD_FASTEST_SOLVER,
    INTENT_POD_NOT_ATTEMPTED_TODAY, INTENT_POD_PASS_FAIL_SUMMARY,
    INTENT_POD_PASS_RATE, INTENT_POD_TOP_PASSERS,
    INTENT_POD_NEVER_PASSED, INTENT_POD_WEEKLY_PASSERS,
    INTENT_POD_DIFFICULTY_BREAKDOWN, INTENT_POD_LANGUAGE_BREAKDOWN,
    INTENT_POD_HARD_SOLVERS, INTENT_POD_LONGEST_STREAK,
    INTENT_POD_ACTIVE_STREAKS, INTENT_POD_LOST_STREAK,
    INTENT_POD_TOP_COINS, INTENT_POD_TOTAL_POINTS_TODAY,
    INTENT_POD_TOP_SCORERS, INTENT_POD_BADGE_EARNERS,
    INTENT_POD_WEEKLY_BADGE_EARNERS,
    INTENT_POD_STUDENT_PROFILE,
)
from models import GraphState
from tool import TOOL_MAP
from logger import logger


# ── LLM — imported from models.py (matches reference project pattern) ─────────
from models import gpt_4o_mini_llm as _llm


# ── JSON helper — handles Decimal and asyncpg int types from PostgreSQL ───────

class _SafeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, decimal.Decimal):
            return float(obj)
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        if hasattr(obj, "__int__") and not isinstance(obj, (bool, float, str)):
            try:
                return int(obj)
            except Exception:
                pass
        return super().default(obj)


def _safe_json(data: Any) -> str:
    return json.dumps(data, indent=2, cls=_SafeEncoder)


# ── Intent → Tool name mapping ────────────────────────────────────────────────

INTENT_TO_TOOL: dict[str, str] = {
    INTENT_POD_WHO_SOLVED_TODAY:     "pod_who_solved_today_tool",
    INTENT_POD_ATTEMPT_COUNT_TODAY:  "pod_attempt_count_today_tool",
    INTENT_POD_QUESTION_TODAY:       "pod_question_today_tool",
    INTENT_POD_FASTEST_SOLVER:       "pod_fastest_solver_tool",
    INTENT_POD_NOT_ATTEMPTED_TODAY:  "pod_not_attempted_today_tool",
    INTENT_POD_PASS_FAIL_SUMMARY:    "pod_pass_fail_summary_tool",
    INTENT_POD_PASS_RATE:            "pod_pass_rate_tool",
    INTENT_POD_TOP_PASSERS:          "pod_top_passers_tool",
    INTENT_POD_NEVER_PASSED:         "pod_never_passed_tool",
    INTENT_POD_WEEKLY_PASSERS:       "pod_weekly_passers_tool",
    INTENT_POD_DIFFICULTY_BREAKDOWN: "pod_difficulty_breakdown_tool",
    INTENT_POD_LANGUAGE_BREAKDOWN:   "pod_language_breakdown_tool",
    INTENT_POD_HARD_SOLVERS:         "pod_hard_solvers_tool",
    INTENT_POD_LONGEST_STREAK:       "pod_longest_streak_tool",
    INTENT_POD_ACTIVE_STREAKS:       "pod_active_streaks_tool",
    INTENT_POD_LOST_STREAK:          "pod_lost_streak_tool",
    INTENT_POD_TOP_COINS:            "pod_top_coins_tool",
    INTENT_POD_TOTAL_POINTS_TODAY:   "pod_total_points_today_tool",
    INTENT_POD_TOP_SCORERS:          "pod_top_scorers_tool",
    INTENT_POD_BADGE_EARNERS:        "pod_badge_earners_tool",
    INTENT_POD_WEEKLY_BADGE_EARNERS: "pod_weekly_badge_earners_tool",
    INTENT_POD_STUDENT_PROFILE:       "pod_student_profile_tool",
}


# ── Classification prompt ─────────────────────────────────────────────────────

CLASSIFY_SYSTEM = """You are an intent classifier for a college faculty analytics chatbot.
Faculty ask questions about POD (Problem of the Day) student activity.

Classify the message into ONE of these intents and extract the relevant parameters listed for each:

--- DAILY ACTIVITY ---
pod_who_solved_today
  params: college_name (str, optional)

pod_attempt_count_today
  params: college_name (str, optional)

pod_question_today
  params: (none)

pod_fastest_solver
  params: college_name (str, optional), limit (int, default 10)

pod_not_attempted_today
  params: college_name (str, optional), limit (int, default 20)

--- PASS / FAIL PERFORMANCE ---
pod_pass_fail_summary
  params: college_name (str, optional), date_filter (str, optional — use "today" if user says today, or "YYYY-MM-DD" for a specific date), limit (int, default 20)

pod_pass_rate
  params: college_name (str, optional)

pod_top_passers
  params: college_name (str, optional), limit (int, default 10)

pod_never_passed
  params: college_name (str, optional), limit (int, default 20)

pod_weekly_passers
  params: college_name (str, optional), limit (int, default 20)

--- DIFFICULTY & LANGUAGE ---
pod_difficulty_breakdown
  params: college_name (str, optional)

pod_language_breakdown
  params: college_name (str, optional)

pod_hard_solvers
  params: college_name (str, optional), limit (int, default 20)

--- STREAKS & CONSISTENCY ---
pod_longest_streak
  params: college_name (str, optional), limit (int, default 10)

pod_active_streaks
  params: college_name (str, optional), min_streak (int, default 3 — minimum streak length to include), limit (int, default 20)

pod_lost_streak
  params: college_name (str, optional), limit (int, default 20)

--- POINTS & COINS ---
pod_top_coins
  params: college_name (str, optional), limit (int, default 10)

pod_total_points_today
  params: college_name (str, optional)

pod_top_scorers — students ranked by total POD score/points earned overall
  params: college_name (str, optional), limit (int, default 10)
  use this for: "who has the most points", "show leaderboard", "top students by score", "highest scoring students", "who scored the most", "points leaderboard", "overall points ranking", "most points overall"

--- BADGES ---
pod_badge_earners
  params: college_name (str, optional), limit (int, default 20)

pod_weekly_badge_earners
  params: college_name (str, optional), limit (int, default 20)

--- STUDENT PROFILE ---
pod_student_profile
  params: student_name (str, required — full or partial name of the student), college_name (str, optional), date_filter (str, optional — "today" or "YYYY-MM-DD"), info_type (str, optional — "submissions", "streaks", "badges", "coins", or "all" — default "all")

--- FALLBACK ---
unknown
  params: (none) — use when the question is not related to POD

Respond ONLY with valid JSON in this exact shape — no explanation, no markdown:
{
  "intent": "<intent_label>",
  "params": {
    "college_name": "...",
    "limit": 10
  }
}
Only include params that are relevant to the detected intent. Omit params not mentioned by the user.
"""


# ── Node 1: classify ──────────────────────────────────────────────────────────

async def classify_node(state: GraphState) -> dict[str, Any]:
    logger.info(f"[classify] message='{state['message'][:80]}'")
    try:
        response = await _llm.ainvoke([
            {"role": "system", "content": CLASSIFY_SYSTEM},
            {"role": "user",   "content": state["message"]},
        ])
        raw = response.content.strip()

        # Strip markdown fences if LLM wraps in ```json
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        parsed = json.loads(raw)
        intent = parsed.get("intent", INTENT_UNKNOWN)
        params: dict[str, Any] = parsed.get("params", {})

        # Auto-inject college_name from session if LLM didn't extract one
        college_name = state.get("college_name")
        if college_name and "college_name" not in params:
            params["college_name"] = college_name

        logger.info(f"[classify] intent={intent} params={params}")
        return {"intent": intent, "params": params}

    except Exception as exc:
        logger.error(f"[classify] failed: {exc}")
        return {"intent": INTENT_UNKNOWN, "params": {}, "error": str(exc)}


# ── Node 2: execute tool ──────────────────────────────────────────────────────

async def execute_node(state: GraphState) -> dict[str, Any]:
    intent = state.get("intent", INTENT_UNKNOWN)
    params = state.get("params", {})

    if intent == INTENT_UNKNOWN:
        return {
            "data": None,
            "answer": (
                "I can only answer questions about POD (Problem of the Day) activity. "
                "Try asking things like: 'Who solved today's POD?', "
                "'Show me the pass/fail summary', or 'Who has the longest streak?'"
            ),
        }

    tool_name = INTENT_TO_TOOL.get(intent)
    if not tool_name or tool_name not in TOOL_MAP:
        logger.warning(f"[execute] no tool mapped for intent={intent}")
        return {"data": None, "answer": "I don't have a handler for that question yet."}

    tool_fn = TOOL_MAP[tool_name]
    logger.info(f"[execute] calling tool={tool_name} params={params}")

    try:
        result = await tool_fn.ainvoke(params)
        return {"data": result}
    except Exception as exc:
        logger.error(f"[execute] tool error: {exc}")
        return {"data": None, "error": str(exc), "answer": f"Database error: {exc}"}


# ── Node 3: format answer ─────────────────────────────────────────────────────

FORMAT_SYSTEM = """You are a helpful analytics assistant for college faculty.
You will receive a faculty question and a JSON data payload about POD (Problem of the Day) activity.

Rules:
- NEVER reconstruct or redraw the data as a table — the UI already shows the full table.
- Write 2-5 concise bullet points highlighting the key insights.
- Round numbers to 2 decimal places.
- Do NOT invent values not present in the data.
- Refer to columns naturally — e.g. "streak_count" → "streak", "obtained_score" → "score".
"""


async def format_node(state: GraphState) -> dict[str, Any]:
    # Skip formatting if answer was already set by execute (error or unknown intent)
    if state.get("answer"):
        return {}
    if state.get("error") and not state.get("data"):
        return {}

    data = state.get("data") or []

    # Check empty in code — never let the LLM decide if data exists or not
    if not data:
        return {"answer": "No data found for that query."}

    data_str = _safe_json(data)
    logger.info(f"[format] formatting {len(data)} rows")

    try:
        response = await _llm.ainvoke([
            {"role": "system", "content": FORMAT_SYSTEM},
            {"role": "user",   "content": f"Question: {state['message']}\n\nData:\n{data_str}"},
        ])
        return {"answer": response.content.strip()}
    except Exception as exc:
        logger.error(f"[format] failed: {exc}")
        return {"answer": f"Data retrieved but could not format response: {exc}"}


# ── Router ────────────────────────────────────────────────────────────────────

def route_after_execute(state: GraphState) -> str:
    """If execute already set an answer (error/unknown), skip format and end."""
    if state.get("answer"):
        return "end"
    return "format"


# ── Graph builder ─────────────────────────────────────────────────────────────

def build_graph() -> Any:
    """Build and compile the LangGraph pipeline. Called once at startup."""
    builder = StateGraph(GraphState)

    builder.add_node("classify", classify_node)
    builder.add_node("execute",  execute_node)
    builder.add_node("format",   format_node)

    builder.set_entry_point("classify")
    builder.add_edge("classify", "execute")
    builder.add_conditional_edges(
        "execute",
        route_after_execute,
        {"format": "format", "end": END},
    )
    builder.add_edge("format", END)

    graph = builder.compile()
    logger.info("LangGraph POD supervisor compiled successfully.")
    return graph