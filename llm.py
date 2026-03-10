# llm.py — TapTap POD Analytics Chatbot
# Contains:
#   - Azure OpenAI LLM setup
#   - Classification prompt
#   - Format prompt
#   - LangGraph 3-node pipeline: classify → execute → format
#   - build_graph() called once at startup

import json
import decimal
import datetime
import inspect
import os
from typing import Any

from dotenv import load_dotenv
from langchain_openai import AzureChatOpenAI
from langgraph.graph import StateGraph, END

load_dotenv()

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
)
from models import GraphState
from tool import TOOL_MAP
from logger import logger


# ── Azure OpenAI LLM setup ────────────────────────────────────────────────────

_llm = AzureChatOpenAI(
    azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o-mini"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2025-01-01-preview"),
    temperature=LLM_TEMPERATURE,
    max_tokens=LLM_MAX_TOKENS,
)


# ── JSON helper — handles Decimal and asyncpg int types from PostgreSQL ───────

class _SafeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, decimal.Decimal):
            return float(obj)
        if isinstance(obj, (datetime.datetime, datetime.date)):
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
}


# ── Classification prompt ─────────────────────────────────────────────────────

CLASSIFY_SYSTEM = f"""You are an intent classifier for a college faculty analytics chatbot focused on POD (Problem of the Day).
Classify the user message into ONE of these intents:
{json.dumps(ALL_INTENTS, indent=2)}

Also extract any relevant parameters. Possible parameters:
- college_name (str): college name mentioned or implied
- limit (int): number of results requested, default 10
- date_filter (str): use "today" if user says today/right now, or "YYYY-MM-DD" for a specific date, omit otherwise
- min_streak (int): minimum streak length mentioned, default 3

Respond ONLY with valid JSON in this exact shape:
{{
  "intent": "<intent_label>",
  "params": {{}}
}}
Do NOT include explanation or markdown fences.
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
        # FIX: filter params to only what this tool's function actually accepts.
        # classify_node injects college_name into ALL params, but some tools
        # (e.g. pod_question_today_tool) take zero arguments — passing extra
        # kwargs causes a TypeError. inspect.signature filters them safely.
        sig = inspect.signature(tool_fn.coroutine)
        filtered_params = {k: v for k, v in params.items() if k in sig.parameters}
        logger.info(f"[execute] filtered_params={filtered_params}")

        result = await tool_fn.coroutine(**filtered_params)
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
- If data is empty or [], say "No data found for that query."
- Do NOT invent values not present in the data.
- Refer to columns naturally — e.g. "streak_count" -> "streak", "obtained_score" -> "score".
"""


async def format_node(state: GraphState) -> dict[str, Any]:
    # Skip formatting if answer was already set by execute (error or unknown intent)
    if state.get("answer"):
        return {}
    if state.get("error") and not state.get("data"):
        return {}

    data = state.get("data") or []
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