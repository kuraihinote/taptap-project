# llm.py — TapTap Analytics Chatbot (LLM Query Generation approach)
# Node 1: classify_node  — determines domain (pod/emp/assess/unknown/ambiguous)
# Node 2: execute_node   — calls domain dispatcher which generates + runs SQL
# Node 3: format_node    — LLM narrates the SQL results

import json
import decimal
from datetime import datetime, date
from typing import Any

from langchain_openai import AzureChatOpenAI
from langgraph.graph import StateGraph, END

from constants import (
    LLM_TEMPERATURE, LLM_MAX_TOKENS,
    INTENT_POD, INTENT_EMP, INTENT_ASSESS, INTENT_UNKNOWN, INTENT_AMBIGUOUS,
    SQL_MAX_CHAIN,
)
from models import GraphState
from tool import TOOL_MAP
from logger import logger

from models import gpt_4o_mini_llm as _llm


# ── JSON helper ───────────────────────────────────────────────────────────────

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


# ── Intent → tool mapping ─────────────────────────────────────────────────────

INTENT_TO_TOOL = {
    INTENT_POD:    "pod_data_tool",
    INTENT_EMP:    "emp_data_tool",
    INTENT_ASSESS: "assess_data_tool",
}


# ══════════════════════════════════════════════════════════════════════════════
# CLASSIFICATION PROMPT
# ══════════════════════════════════════════════════════════════════════════════

CLASSIFY_SYSTEM = """You are an intent classifier for a college faculty analytics chatbot.
Faculty ask questions about POD (Problem of the Day), Employability Track, and Assessments.

Your ONLY job: return which domain the question belongs to.

RULES:
RULE 1 — Return exactly one intent: "pod", "emp", "assess", "unknown", or "ambiguous".
RULE 2 — "emp" = Employability Track questions (domains, scores, pass rates, student performance in practice questions).
         Keywords: "employability", "domain", "pass rate for [topic]", "top scorers in employability", "practice questions"
         If the query mentions "employability" anywhere → always return "emp".
RULE 3 — "pod" = Problem of the Day questions (daily coding/aptitude/verbal challenges, streaks, badges, coins).
         Keywords: "POD", "streak", "badge", "coin", "today's question", "problem of the day"
RULE 4 — "assess" = Formal company assessment questions (shortlisted, submitted, passed assessments).
         Keywords: "shortlisted", "assessment", "who didn't submit", "who passed the [job title] assessment"
         Job title assessments: "Backend Developer", "Frontend Developer", "Angular", "Java Developer",
         "Web Developer", "Smart Interview", "Flutter Developer", "Unity", "Laravel" → always "assess"
RULE 4b — EMP vs ASSESS distinction for "pass rate for X":
         Academic/CS topics → "emp": Data Structures, DSA, Algorithms, Python, Java, ML, SQL, Aptitude
         Job title assessments → "assess": Backend Developer, Frontend Developer, Angular, Web Developer
RULE 5 — "unknown" = Nothing to do with any of the three modules.
RULE 6 — "ambiguous" = No module keyword present AND could apply to both POD and Employability.
         EXAMPLES that are ambiguous: "Who is the top student?", "Show me the leaderboard",
         "Who scored highest?", "Top students from CMR", "Who are the top students from [college]?"
         NOT ambiguous: anything with "employability", "POD", "streak", "badge", "assessment"
RULE 7 — Named student queries with no module → "ambiguous" (ask faculty which module they mean).
         e.g. "Show Pranith's profile" → ambiguous
         e.g. "Show Pranith's employability profile" → emp
RULE 8 — Follow-up questions inherit the module from prior context.
         When prior questions establish a clear module AND the current message refines or filters
         that query — return that SAME module. NEVER return unknown or ambiguous for these.
         CRITICAL EXAMPLES:
           prior: "Show employability top scorers from CMR"
           current: "Filter to only hard difficulty" → emp (NOT unknown)
           current: "Show only students who passed" → emp (NOT ambiguous)
           current: "Only Python language" → emp
           current: "Narrow to this week" → emp
         KEY FOLLOW-UP SIGNALS (inherit module when you see these):
         "filter to", "filter by", "show only", "only from", "only students", "only those",
         "just show", "hard only", "only hard", "narrow down", "refine",
         "what about", "how about", "and the", "same query", "his ", "her "

Respond ONLY with valid JSON:
{"intent": "<pod|emp|assess|unknown|ambiguous>"}
"""


# ══════════════════════════════════════════════════════════════════════════════
# FORMAT PROMPT
# ══════════════════════════════════════════════════════════════════════════════

FORMAT_SYSTEM = """You are a helpful analytics assistant for college faculty.
You will receive a JSON data payload from a database query about student activity.

Rules:
- Write 2-5 concise bullet points highlighting the key insights.
- Mention specific names, numbers, and percentages where available.
- Round numbers to 2 decimal places.
- Do NOT invent or speculate about values not in the data.
- Do NOT mention the SQL query or database internals.
- For averages, always state the number clearly e.g. "average of 77 students per day".
"""

# Query-type specific format overrides
_FORMAT_OVERRIDES: dict[str, str] = {
    "trend": (
        "Summarise this daily trend data in 2-5 bullet points. "
        "Lead with the average per day first, then highlight peak and lowest days."
    ),
    "average": (
        "Summarise this data in 2-5 bullet points. "
        "Lead with the average figure the faculty asked for."
    ),
}


# ══════════════════════════════════════════════════════════════════════════════
# NODE 1: CLASSIFY
# ══════════════════════════════════════════════════════════════════════════════

async def classify_node(state: GraphState) -> dict[str, Any]:
    logger.info(f"[classify] message='{state['message'][:80]}'")
    try:
        prior = [
            m["content"] for m in (state.get("history") or [])
            if m["role"] == "user"
        ]

        followup_triggers = (
            "his ", "her ", "their ", "them", "that ", "the same",
            "this student", "above", "previous", "same assessment", "same student",
            "skill breakdown", "difficulty breakdown", "completion rate",
            "what about", "for it", "for that", "for this",
            "same one", "that one", "how about", "and the",
            "filter to", "filter by", "show only", "only from",
            "only students", "only those", "just show", "hard only",
            "only hard", "narrow down", "refine", "same query"
        )
        needs_context = any(t in state["message"].lower() for t in followup_triggers)

        def _build_messages(include_ctx):
            msgs = [{"role": "system", "content": CLASSIFY_SYSTEM}]
            if include_ctx and prior and needs_context:
                ctx_lines = "\n".join(f"- {q}" for q in prior[-4:])
                ctx = (
                    f"Previous questions (use ONLY to resolve references — do NOT copy params):\n"
                    f"{ctx_lines}"
                )
                msgs.append({"role": "user",      "content": ctx})
                msgs.append({"role": "assistant",  "content": "Understood."})
            msgs.append({"role": "user", "content": state["message"]})
            return msgs

        try:
            response = await _llm.ainvoke(_build_messages(True))
        except Exception as exc_cf:
            if "content_filter" in str(exc_cf) and prior:
                logger.warning("[classify] content filter — retrying without history")
                response = await _llm.ainvoke(_build_messages(False))
            else:
                raise

        raw = response.content.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        parsed = json.loads(raw)
        intent = parsed.get("intent", INTENT_UNKNOWN)

        # Strip empty string params just in case
        params: dict[str, Any] = {k: v for k, v in parsed.get("params", {}).items()
                                   if v != "" and v is not None}

        # Auto-inject college_name from sidebar if set
        college_name = state.get("college_name")
        if college_name and "college_name" not in params:
            params["college_name"] = college_name

        logger.info(f"[classify] intent={intent}")
        return {"intent": intent, "params": params}

    except Exception as exc:
        logger.error(f"[classify] failed: {exc}")
        return {"intent": INTENT_UNKNOWN, "params": {}, "error": str(exc)}


# ══════════════════════════════════════════════════════════════════════════════
# NODE 2: EXECUTE
# ══════════════════════════════════════════════════════════════════════════════

async def execute_node(state: GraphState) -> dict[str, Any]:
    intent          = state.get("intent", INTENT_UNKNOWN)
    message         = state.get("message", "")
    college_name    = state.get("college_name")
    last_sql        = state.get("last_sql")         # ← SQL from prior turn
    sql_chain_count = state.get("sql_chain_count", 0)  # ← how many modifications in a row

    # ── SQL chain drift control ────────────────────────────────────────────────
    # If SQL has been modified too many times, force a fresh regeneration
    # to prevent stacking conflicting filters and compounding errors.
    if sql_chain_count >= SQL_MAX_CHAIN:
        logger.info(f"[execute] SQL chain limit reached ({sql_chain_count}) — forcing fresh generation")
        last_sql = None
        sql_chain_count = 0

    if intent == INTENT_UNKNOWN:
        return {
            "data": None, "sql": None, "sql_chain_count": 0,
            "answer": (
                "I can answer questions about **POD (Problem of the Day)**, "
                "**Employability Track**, and **Assessments**.\n\n"
                "Some things you can ask:\n"
                "- *Who are the top employability scorers?*\n"
                "- *What is the pass rate for Data Structures?*\n"
                "- *Show me recent employability activity*\n"
                "- *Who solved the most questions in Python?*"
            ),
        }

    if intent == INTENT_AMBIGUOUS:
        return {
            "data": None, "sql": None, "sql_chain_count": 0,
            "answer": (
                "Could you clarify which module you mean?\n\n"
                "- **POD (Problem of the Day)** — daily coding/aptitude/verbal challenges\n"
                "- **Employability Track** — domain-based practice questions\n"
                "- **Assessments** — formal company assessments\n\n"
                "For example:\n"
                "- *Who are the top POD scorers?*\n"
                "- *Who are the top employability scorers?*\n"
                "- *Show [name]\'s employability profile*"
            ),
        }

    # POD and Assess pending schema access
    if intent in (INTENT_POD, INTENT_ASSESS):
        module = "POD" if intent == INTENT_POD else "Assessments"
        return {
            "data": None, "sql": None, "sql_chain_count": 0,
            "answer": (
                f"{module} data is not yet available in this version. "
                f"Please try an Employability Track question for now."
            ),
        }

    tool_name = INTENT_TO_TOOL.get(intent)
    if not tool_name or tool_name not in TOOL_MAP:
        return {"data": None, "sql": None, "sql_chain_count": 0, "answer": "No handler found for that question."}

    tool_fn = TOOL_MAP[tool_name]

    # ── Build enriched question ───────────────────────────────────────────────
    # KEY FIX: if we have the last executed SQL, pass it as a concrete base
    # for the SQL generator to modify — not natural language history.
    # This prevents the LLM from generating two separate SELECT statements.

    followup_triggers = (
        "his ", "her ", "their ", "them", "that ", "the same",
        "this student", "above", "previous", "same assessment", "same student",
        "what about", "for it", "for that", "for this",
        "same one", "that one", "how about", "and the",
        "filter to", "filter by", "show only", "only from", "only students",
        "only those", "narrow down", "just show", "hard only", "only hard",
        "refine", "same query"
    )
    is_followup = any(t in message.lower() for t in followup_triggers)

    if is_followup and last_sql:
        # Pass the previous SQL as the base — LLM modifies it, not regenerates
        # Increment chain count to track drift
        sql_chain_count += 1
        logger.info(f"[execute] SQL follow-up chain count: {sql_chain_count}/{SQL_MAX_CHAIN}")
        enriched_question = (
            f"The following SQL query was previously executed successfully. "
            f"Modify it to satisfy the new request. "
            f"Return exactly ONE SELECT statement — do not generate a separate query.\n\n"
            f"PREVIOUS SQL:\n{last_sql}\n\n"
            f"New request: {message}"
        )
    elif is_followup and not last_sql:
        # Fallback: no SQL available yet, use NL history but limit to last 1 prior question
        prior = [
            m["content"] for m in (state.get("history") or [])
            if m["role"] == "user"
        ]
        if prior:
            enriched_question = (
                f"Previous question for context (resolve any references from it): "
                f"{prior[-1]}\n\nCurrent question: {message}"
            )
        else:
            enriched_question = message
    else:
        # Fresh question — no context injection needed
        enriched_question = message

    # Always append college scope if set
    if college_name:
        enriched_question = f"{enriched_question} (filter to college: {college_name})"

    logger.info(f"[execute] tool={tool_name} enriched='{enriched_question[:120]}'")

    try:
        result = await tool_fn.ainvoke({"question": enriched_question})

        if result.get("error") == "UNSUPPORTED":
            return {
                "data": [], "sql": result.get("sql"),
                "answer": (
                    "I couldn't find a way to answer that question from the available data. "
                    "Try rephrasing or asking about a specific domain, student, or college."
                ),
            }

        if result.get("error") == "SCHEMA_PENDING":
            return {
                "data": [], "sql": None,
                "sql_chain_count": 0,
                "answer": "Schema access for this module is pending. Please try an Employability question.",
            }

        if result.get("error"):
            logger.error(f"[execute] analytics error: {result['error']}")
            return {
                "data": [], "sql": result.get("sql"),
                "answer": (
                    "There was an error retrieving that data. "
                    "Try rephrasing your question or being more specific."
                ),
            }

        return {"data": result.get("data", []), "sql": result.get("sql"), "sql_chain_count": sql_chain_count}

    except Exception as exc:
        logger.error(f"[execute] tool error: {exc}")
        return {"data": None, "sql": None, "sql_chain_count": 0, "error": str(exc),
                "answer": f"Unexpected error: {exc}"}


# ══════════════════════════════════════════════════════════════════════════════
# NODE 3: FORMAT
# ══════════════════════════════════════════════════════════════════════════════

async def format_node(state: GraphState) -> dict[str, Any]:
    if state.get("answer"):
        return {}
    if state.get("error") and not state.get("data"):
        return {}

    data = state.get("data") or []

    if not data:
        return {
            "answer": (
                "No data found for that query. Try being more specific — "
                "include a college name, student name, domain, or time period."
            )
        }

    # Ambiguous student name guard
    msg_lower = state.get("message", "").lower()
    is_profile_query = (
        any(w in msg_lower for w in ("profile", "how is", "how did", "show me")) and
        not any(w in msg_lower for w in ("top", "leaderboard", "scorers", "best", "all students", "list"))
    )
    if is_profile_query:
        names = list(dict.fromkeys(
            r.get("first_name", "") + " " + r.get("last_name", "")
            if "first_name" in r
            else r.get("name", "")
            for r in data
        ))
        names = [n.strip() for n in names if n.strip()]
        unique_names = list(dict.fromkeys(names))
        if len(unique_names) > 1:
            names_str = ", ".join(unique_names[:5])
            more = f" and {len(unique_names) - 5} more" if len(unique_names) > 5 else ""
            return {
                "answer": (
                    f"Found {len(unique_names)} students matching that name: "
                    f"{names_str}{more}. "
                    f"Please use the full name to get a specific profile."
                )
            }

    data_str = _safe_json(data)
    logger.info(f"[format] formatting {len(data)} rows")

    if any(w in msg_lower for w in ("trend", "daily", "per day", "each day")):
        instruction = _FORMAT_OVERRIDES["trend"]
    elif any(w in msg_lower for w in ("average", "avg", "mean")):
        instruction = _FORMAT_OVERRIDES["average"]
    else:
        instruction = (
            "Summarise the following data in 2-5 concise bullet points. "
            "Only describe what is in the data."
        )

    try:
        response = await _llm.ainvoke([
            {"role": "system", "content": FORMAT_SYSTEM},
            {"role": "user",   "content": f"{instruction}\n\nData:\n{data_str}"},
        ])
        return {"answer": response.content.strip()}
    except Exception as exc:
        logger.error(f"[format] failed: {exc}")
        return {"answer": f"Data retrieved but could not format response: {exc}"}


# ══════════════════════════════════════════════════════════════════════════════
# ROUTER + GRAPH
# ══════════════════════════════════════════════════════════════════════════════

def route_after_execute(state: GraphState) -> str:
    if state.get("answer"):
        return "end"
    return "format"


def build_graph() -> Any:
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
    logger.info("LangGraph pipeline compiled successfully.")
    return graph