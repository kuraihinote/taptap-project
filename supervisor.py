# supervisor.py — TapTap Analytics Chatbot v3

import json
import decimal
import os
from typing import Any

from dotenv import load_dotenv
from langchain_openai import AzureChatOpenAI
from langgraph.graph import StateGraph, END

load_dotenv()

from constants import (
    LLM_TEMPERATURE, LLM_MAX_TOKENS,
    INTENT_TOP_STUDENTS, INTENT_BOTTOM_STUDENTS,
    INTENT_BAND_DISTRIBUTION, INTENT_COLLEGE_SUMMARY,
    INTENT_DEPARTMENT_SUMMARY, INTENT_HACKATHON_PERFORMANCE,
    INTENT_POD_PERFORMANCE, INTENT_STUDENT_PROFILE,
    INTENT_SCORE_DISTRIBUTION, INTENT_UNKNOWN, ALL_INTENTS,
)
from models import GraphState
from tools import TOOL_MAP
from logger import logger


# ── LLM setup ─────────────────────────────────────────────────────────────────

_llm = AzureChatOpenAI(
    azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o-mini"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2025-01-01-preview"),
    temperature=LLM_TEMPERATURE,
    max_tokens=LLM_MAX_TOKENS,
)


# ── JSON helper — handles Decimal, asyncpg int types ─────────────────────────

class _SafeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, decimal.Decimal):
            return float(obj)
        if hasattr(obj, '__int__') and not isinstance(obj, (bool, float, str)):
            try:
                return int(obj)
            except Exception:
                pass
        return super().default(obj)

def _safe_json(data: Any) -> str:
    return json.dumps(data, indent=2, cls=_SafeEncoder)


# ── Intent → tool name mapping ────────────────────────────────────────────────

INTENT_TO_TOOL: dict[str, str] = {
    INTENT_TOP_STUDENTS:          "top_students_tool",
    INTENT_BOTTOM_STUDENTS:       "bottom_students_tool",
    INTENT_BAND_DISTRIBUTION:     "band_distribution_tool",
    INTENT_COLLEGE_SUMMARY:       "college_summary_tool",
    INTENT_DEPARTMENT_SUMMARY:    "department_summary_tool",
    INTENT_HACKATHON_PERFORMANCE: "hackathon_performance_tool",
    INTENT_POD_PERFORMANCE:       "pod_performance_tool",
    INTENT_STUDENT_PROFILE:       "student_profile_tool",
    INTENT_SCORE_DISTRIBUTION:    "score_distribution_tool",
}


# ── Classification prompt ─────────────────────────────────────────────────────

CLASSIFY_SYSTEM = f"""You are an intent classifier for a college analytics chatbot.
Classify the user message into ONE of these intents:
{json.dumps(ALL_INTENTS, indent=2)}

Also extract any relevant parameters from the message. Possible parameters:
- limit (int): number of students requested, default 10
- college_name (str): name of the college mentioned
- department (str): department/branch name mentioned
- band (str): employability band — one of High, Medium, Low, Very Low
- hackathon_name (str): name of the hackathon mentioned
- reg_no (str): student registration number mentioned
- bucket_size (int): histogram bucket size, default 10
- date_filter (str): date context for pod queries — use "today" if user says "today/right now/this moment", or "YYYY-MM-DD" for a specific date, omit if no date mentioned

Respond ONLY with valid JSON in this exact shape:
{{
  "intent": "<intent_label>",
  "params": {{
    "limit": 10
  }}
}}
Do NOT include any explanation or markdown fences.
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

        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        parsed = json.loads(raw)
        intent = parsed.get("intent", INTENT_UNKNOWN)
        params: dict[str, Any] = parsed.get("params", {})

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
            "answer": "I'm sorry, I didn't understand that question. Could you rephrase it?",
        }

    tool_name = INTENT_TO_TOOL.get(intent)
    if not tool_name or tool_name not in TOOL_MAP:
        logger.warning(f"[execute] no tool for intent={intent}")
        return {"data": None, "answer": "I can't answer that type of question yet."}

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
You will receive a user question and a JSON data payload.
Write a clear, concise natural-language summary based only on the data provided.

Rules:
- NEVER reconstruct or redraw the data as a table — the UI already shows the full table to the user.
- Instead write 2-5 bullet points highlighting the key insights (e.g. top performer, score range, standout patterns).
- Round numbers to 2 decimal places.
- If data is empty or [], say "No data found for that query."
- Do NOT invent or assume any values not present in the data.
- Do NOT mention column names directly — describe them naturally (e.g. "employabilityScore" → "employability score").
"""

async def format_node(state: GraphState) -> dict[str, Any]:
    if state.get("answer"):
        return {}
    if state.get("error") and not state.get("data"):
        return {}

    data = state.get("data") or []
    # FIX: use _safe_json instead of json.dumps — handles Decimal from PostgreSQL
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
        return {"answer": f"I retrieved the data but couldn't format the response: {exc}"}


# ── Router ────────────────────────────────────────────────────────────────────

def route_after_execute(state: GraphState) -> str:
    if state.get("answer"):
        return "end"
    return "format"


# ── Graph builder ─────────────────────────────────────────────────────────────

def build_graph() -> Any:
    """Build and compile the LangGraph supervisor. Called once at startup."""
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
    logger.info("LangGraph supervisor compiled successfully.")
    return graph