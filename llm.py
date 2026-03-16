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
    INTENT_POD_WEEKLY_BADGE_EARNERS, INTENT_POD_STUDENT_PROFILE,
    INTENT_EMP_TOP_SCORERS, INTENT_EMP_DIFFICULTY_STATS,
    INTENT_EMP_LANGUAGE_STATS, INTENT_EMP_DOMAIN_BREAKDOWN,
    INTENT_EMP_SUBDOMAIN_BREAKDOWN, INTENT_EMP_QUESTION_TYPE_STATS,
    INTENT_EMP_MOST_SOLVED, INTENT_EMP_RECENT_ACTIVITY,
    INTENT_EMP_HARDEST_QUESTIONS, INTENT_EMP_DAILY_TREND,
    INTENT_EMP_PASS_RATE, INTENT_EMP_USER_PROFILE,
    INTENT_ASSESS_LIST, INTENT_ASSESS_OVERVIEW,
    INTENT_ASSESS_STUDENT_RESULT, INTENT_ASSESS_TOP_SCORERS,
    INTENT_ASSESS_PASS_RATE, INTENT_ASSESS_SKILL_BREAKDOWN,
    INTENT_ASSESS_DIFFICULTY_BREAKDOWN, INTENT_ASSESS_COMPLETION_RATE,
    INTENT_ASSESS_RECENT, INTENT_ASSESS_STUDENT_ATTEMPTS,
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
    # POD
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
    INTENT_POD_STUDENT_PROFILE:      "pod_student_profile_tool",
    # Employability
    INTENT_EMP_TOP_SCORERS:          "emp_top_scorers_tool",
    INTENT_EMP_DIFFICULTY_STATS:     "emp_difficulty_stats_tool",
    INTENT_EMP_LANGUAGE_STATS:       "emp_language_stats_tool",
    INTENT_EMP_DOMAIN_BREAKDOWN:     "emp_domain_breakdown_tool",
    INTENT_EMP_SUBDOMAIN_BREAKDOWN:  "emp_subdomain_breakdown_tool",
    INTENT_EMP_QUESTION_TYPE_STATS:  "emp_question_type_stats_tool",
    INTENT_EMP_MOST_SOLVED:          "emp_most_solved_tool",
    INTENT_EMP_RECENT_ACTIVITY:      "emp_recent_activity_tool",
    INTENT_EMP_HARDEST_QUESTIONS:    "emp_hardest_questions_tool",
    INTENT_EMP_DAILY_TREND:          "emp_daily_trend_tool",
    INTENT_EMP_PASS_RATE:            "emp_pass_rate_tool",
    INTENT_EMP_USER_PROFILE:         "emp_user_profile_tool",
    # Assess
    INTENT_ASSESS_LIST:              "assess_list_tool",
    INTENT_ASSESS_OVERVIEW:          "assess_overview_tool",
    INTENT_ASSESS_STUDENT_RESULT:    "assess_student_result_tool",
    INTENT_ASSESS_TOP_SCORERS:       "assess_top_scorers_tool",
    INTENT_ASSESS_PASS_RATE:         "assess_pass_rate_tool",
    INTENT_ASSESS_SKILL_BREAKDOWN:   "assess_skill_breakdown_tool",
    INTENT_ASSESS_DIFFICULTY_BREAKDOWN: "assess_difficulty_breakdown_tool",
    INTENT_ASSESS_COMPLETION_RATE:   "assess_completion_rate_tool",
    INTENT_ASSESS_RECENT:            "assess_recent_tool",
    INTENT_ASSESS_STUDENT_ATTEMPTS:  "assess_student_attempts_tool",
}


# ── Classification prompt ─────────────────────────────────────────────────────

CLASSIFY_SYSTEM = """You are an intent classifier for a college faculty analytics chatbot.
Faculty ask questions about POD (Problem of the Day) and Employability Track student activity.

════════════════════════════════════════════════════════
CRITICAL RULES — READ THESE FIRST BEFORE CLASSIFYING
════════════════════════════════════════════════════════

RULE 1 — SINGLE INTENT ONLY:
You can only return ONE intent per message. If the user asks about both POD and Employability
in one sentence (e.g. "Compare POD vs employability"), pick the PRIMARY module they mentioned
first or the one with more detail. Never return "unknown" just because two modules are mentioned.

RULE 2 — COLLEGE NAME vs STUDENT NAME:
College names: SRM, VIT, Anna University, CMRIT, Geethanjali, etc. → use college_name param.
Student names: individual person names like "Rahul", "Priya", "Rentachintala PRIYANKA" → use student_name param.
NEVER put a college name into student_name. If a query says "from SRM students", that is college_name="SRM".

RULE 3 — DO NOT HALLUCINATE PARAMS:
Only extract params the user explicitly mentioned. If the user says "weakest students in Algorithms"
they did NOT mention difficulty — do NOT add difficulty="hard". Extract only what is stated.

RULE 4 — STUDENT PROFILE MODULE DEFAULT:
If a user asks "how is [name] doing?" or "[name]'s performance" with NO module mentioned,
default to pod_student_profile. Only use emp_user_profile if the user explicitly says
"employability" or "employability track".

RULE 5 — DOMAIN QUERIES GO TO emp_domain_breakdown:
"pass rate for Data Structures", "how are students doing in Algorithms", "performance in Mathematics"
→ these are emp_domain_breakdown with domain_name set. NOT unknown. NOT emp_subdomain_breakdown.

RULE 6 — "WEAKEST STUDENTS IN [DOMAIN]":
"weakest students in Algorithms", "who struggles with Data Structures" → emp_subdomain_breakdown
with domain_name set. This shows per-topic pass rates within that domain.
Do NOT use emp_hardest_questions for student-focused weakness queries.

RULE 7 — emp_user_profile NEVER uses info_type:
emp_user_profile always returns all sections (summary, submissions, question status).
Do NOT extract info_type, streaks, badges etc. for emp_user_profile. Those params only apply
to pod_student_profile.

RULE 8 — ASSESS PASS RATE vs EMP DOMAIN BREAKDOWN:
"pass rate for [name]" where name looks like a job title or assessment
(e.g. "Backend Developer", "Web Developer", "Frontend Developer", "Smart Interview", "DSA in c")
→ use assess_pass_rate with assessment_title set. NOT emp_domain_breakdown.
Only use emp_domain_breakdown when the subject is a CS topic like "Data Structures", "Algorithms", "Mathematics".

════════════════════════════════════════════════════════
INTENT DEFINITIONS
════════════════════════════════════════════════════════

--- POD: DAILY ACTIVITY ---
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

--- POD: PASS / FAIL ---
pod_pass_fail_summary
  params: college_name (str, optional), date_filter (str, optional — "today" or "YYYY-MM-DD"), limit (int, default 20)

pod_pass_rate
  params: college_name (str, optional)
  use for: "POD pass rate", "what % pass POD", "college pass rate"
  NOTE: for employability pass rate, use emp_pass_rate instead

pod_top_passers
  params: college_name (str, optional), limit (int, default 10)

pod_never_passed
  params: college_name (str, optional), limit (int, default 20)

pod_weekly_passers
  params: college_name (str, optional), limit (int, default 20)

--- POD: DIFFICULTY & LANGUAGE ---
pod_difficulty_breakdown
  params: college_name (str, optional)

pod_language_breakdown
  params: college_name (str, optional)

pod_hard_solvers
  params: college_name (str, optional), limit (int, default 20)

--- POD: STREAKS ---
pod_longest_streak
  params: college_name (str, optional), limit (int, default 10)

pod_active_streaks
  params: college_name (str, optional), min_streak (int, default 3), limit (int, default 20)

pod_lost_streak
  params: college_name (str, optional), limit (int, default 20)

--- POD: POINTS & COINS ---
pod_top_coins
  params: college_name (str, optional), limit (int, default 10)

pod_total_points_today
  params: college_name (str, optional)

pod_top_scorers — students ranked by total POD score
  params: college_name (str, optional), limit (int, default 10), week_filter (bool, optional — true if user says "this week")
  use for: "POD leaderboard", "top scorers", "who has the most points", "highest scoring students"

--- POD: BADGES ---
pod_badge_earners
  params: college_name (str, optional), limit (int, default 20)

pod_weekly_badge_earners
  params: college_name (str, optional), limit (int, default 20)

--- POD: STUDENT PROFILE ---
pod_student_profile
  params: student_name (str, required), college_name (str, optional), date_filter (str, optional — "today" or "YYYY-MM-DD"), info_type (str, optional — "submissions"/"streaks"/"badges"/"coins"/"all", default "all"), language (str, optional — e.g. "python", "java", "cpp"), week_filter (bool, optional — true if user says "this week"), pod_type (str, optional — "coding"/"aptitude"/"verbal")
  use for: "[name]'s POD profile", "how is [name] doing" (no module specified), "[name]'s streaks/badges/submissions"
  DEFAULT: if no module is mentioned and a student name is given, use this intent
  PARAM EXTRACTION EXAMPLES — always extract these:
    "coding submissions" / "coding questions" / "coding POD" → pod_type = "coding"
    "aptitude submissions" / "aptitude questions" / "aptitude POD" → pod_type = "aptitude"
    "verbal submissions" / "verbal questions" / "verbal POD" → pod_type = "verbal"
    "this week" / "past week" / "weekly" → week_filter = true
    "in python" / "python submissions" / "using java" → language = "python"/"java"/etc
    "submissions only" / "only submissions" → info_type = "submissions"
    "streaks" / "streak history" → info_type = "streaks"
    "badges" / "badge history" → info_type = "badges"

--- EMPLOYABILITY: LEADERBOARDS ---
emp_top_scorers
  params: college_name (str, optional), limit (int, default 10), week_filter (bool, optional — true if user says "this week")
  use for: "employability top scorers", "employability leaderboard", "highest score in employability", "top employability scorers this week"

emp_most_solved
  params: college_name (str, optional), limit (int, default 20)
  use for: "who solved the most employability questions", "most questions solved in employability"

--- EMPLOYABILITY: PERFORMANCE STATS ---
emp_difficulty_stats
  params: college_name (str, optional)
  use for: "employability difficulty breakdown", "pass rate by difficulty in employability", "easy vs hard in employability"

emp_pass_rate
  params: college_name (str, optional)
  use for: "employability pass rate", "employability success rate", "college-wise employability performance"

emp_language_stats
  params: college_name (str, optional)
  use for: "employability language breakdown", "which language in employability", "python vs java in employability"

emp_domain_breakdown
  params: college_name (str, optional), domain_name (str, optional — set when user asks about a specific domain e.g. "Data Structures", "Algorithms", "Mathematics")
  use for: "employability by domain", "pass rate for [domain]", "performance in [domain]", "how are students doing in [domain]"
  EXAMPLES: "pass rate for Data Structures" → domain_name="Data Structures"
            "Algorithms performance" → domain_name="Algorithms"
            "which domain has most submissions" → no domain_name (returns all)

emp_subdomain_breakdown
  params: college_name (str, optional), domain_name (str, optional), limit (int, default 20)
  use for: "subtopic breakdown", "topic-wise employability", "weakest students in [domain]", "who struggles with [domain]"
  NOTE: "weakest in Algorithms" → domain_name="Algorithms" (see RULE 6 above)

emp_question_type_stats
  params: college_name (str, optional)
  use for: "employability question types", "performance by question type"

emp_hardest_questions
  params: college_name (str, optional), limit (int, default 20), difficulty (str, optional — ONLY set if user explicitly says "hard", "easy", or "medium")
  use for: "hardest employability questions", "which questions do students fail most", "lowest pass rate questions"
  WARNING: only set difficulty if the user explicitly states it. Do not infer or assume difficulty.

--- EMPLOYABILITY: ACTIVITY & TRENDS ---
emp_recent_activity
  params: college_name (str, optional), limit (int, default 20), date_filter (str, optional — "today" or "YYYY-MM-DD"), days (int, optional — e.g. 7 for "last 7 days"), difficulty (str, optional), language (str, optional)
  use for: "recent employability activity", "latest submissions", "submissions from [college] in last N days", "[difficulty] [language] submissions from [college]"
  CRITICAL: college names like "SRM", "VIT" go into college_name — NEVER into student_name

emp_daily_trend
  params: college_name (str, optional), days (int, default 30)
  use for: "employability trend", "submissions per day", "daily employability activity"

--- EMPLOYABILITY: STUDENT PROFILE ---
emp_user_profile
  params: student_name (str, required), college_name (str, optional), difficulty (str, optional), language (str, optional), date_filter (str, optional)
  use for: "[name]'s employability profile", "[name] in employability", "employability history for [name]"
  ONLY use when user explicitly mentions "employability" + a person's name
  DO NOT extract info_type — this intent always returns all sections
  PARAM EXTRACTION EXAMPLES — always extract these:
    "hard questions only" / "only hard" / "hard difficulty" → difficulty = "hard"
    "medium questions" / "medium difficulty" → difficulty = "medium"
    "easy questions" / "easy difficulty" → difficulty = "easy"
    "in python" / "python only" / "using java" → language = "python"/"java"/etc

--- ASSESS: ASSESSMENTS MODULE ---
IMPORTANT — ASSESSMENT TITLE EXTRACTION:
When a user mentions an assessment title, always extract the FULL title verbatim as the user typed it.
Assessment titles are multi-word names like "Web Developer - Angular - Smart Interview" or
"Backend Developer - Dsa in c". Do NOT truncate to just the last part (e.g. do NOT extract
"Smart Interview" from "Web Developer - Angular - Smart Interview" — extract the full string).

assess_list
  params: assessment_title (str, optional — set when user filters by role/keyword e.g. "java", "angular")
  use for: "list all assessments", "show all assessments", "show assessments for java developer",
           "what assessments are there for [role]"

assess_recent
  params: limit (int, default 10)
  use for: "recent assessments", "latest assessments", "newest assessments"

assess_overview
  params: assessment_title (str, optional — set when user names a specific assessment)
  use for: "[assessment name] overview", "details for [assessment]", "how did [assessment] go",
           "shortlisted vs submitted for [assessment]"
  If no title given, returns overview of all assessments.

assess_top_scorers
  params: assessment_title (str, optional), limit (int, default 10)
  use for: "top scorers in [assessment]", "who scored highest in [assessment]", "assessment leaderboard"

assess_pass_rate
  params: assessment_title (str, optional)
  use for: "pass rate for [assessment]", "how many passed [assessment]", "assessment pass rate"
  NOTE: this is for recruiter assessments only — for employability pass rate use emp_pass_rate,
        for POD pass rate use pod_pass_rate

assess_skill_breakdown
  params: assessment_title (str, optional)
  use for: "skill breakdown for [assessment]", "which skills did students struggle with",
           "performance by skill/topic in [assessment]"

assess_difficulty_breakdown
  params: assessment_title (str, optional)
  use for: "difficulty breakdown for [assessment]", "easy vs hard in [assessment]",
           "performance by difficulty in [assessment]"

assess_completion_rate
  params: assessment_title (str, optional)
  use for: "how many completed [assessment]", "completion rate for [assessment]",
           "who didn't attempt [assessment]", "shortlisted vs submitted"

assess_student_result
  params: student_name (str, required), assessment_title (str, optional)
  use for: "[name]'s result in [assessment]", "how did [name] do in [assessment]",
           "[name]'s assessment score", "[name] assessment performance"
  ONLY use when a student name AND the word "assessment" or a specific assessment title is present.
  If just a name is given with no assessment context, default to pod_student_profile.

assess_student_attempts
  params: student_name (str, required)
  use for: "[name]'s assessment history", "all assessments taken by [name]",
           "[name]'s attempt history across assessments"

--- FALLBACK ---
unknown
  params: (none)
  use ONLY when the question has absolutely nothing to do with POD, Employability, or Assessments
  (e.g. weather, jokes, general coding questions)
  DO NOT use unknown for multi-module queries — pick the primary intent instead

════════════════════════════════════════════════════════
OUTPUT FORMAT
════════════════════════════════════════════════════════

Respond ONLY with valid JSON — no explanation, no markdown:
{
  "intent": "<intent_label>",
  "params": { "college_name": "...", "limit": 10 }
}
Only include params the user explicitly mentioned. Omit everything else.
"""


# ── Node 1: classify ──────────────────────────────────────────────────────────

async def classify_node(state: GraphState) -> dict[str, Any]:
    logger.info(f"[classify] message='{state['message'][:80]}'")
    try:
        messages = []
        for h in state.get("history", []):
            messages.append({"role": h["role"], "content": h["content"]})
        messages.append({"role": "user", "content": state["message"]})

        response = await _llm.ainvoke([
            {"role": "system", "content": CLASSIFY_SYSTEM},
            *messages
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
                "I can answer questions about **POD (Problem of the Day)**, **Employability Track**, and **Assessments**.\n\n"
                "Some things you can ask:\n"
                "- *Who solved today's POD?*\n"
                "- *Show employability top scorers*\n"
                "- *What's the pass rate for Data Structures?*\n"
                "- *List all assessments*\n"
                "- *Show [student name]'s profile*\n\n"
                "If you asked about multiple modules in one question, try splitting it into separate questions."
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
You will receive a faculty question and a JSON data payload about student activity — either POD (Problem of the Day) or Employability Track.

Rules:
- NEVER reconstruct or redraw the data as a table — the UI already shows the full table.
- Write 2-5 concise bullet points highlighting the key insights from the data provided.
- Round numbers to 2 decimal places.
- Do NOT invent, assume, or speculate about values not present in the data payload.
- Do NOT mention or comment on data that is missing (e.g. "no employability data was provided") — only summarise what IS in the data.
- If the question asked about two modules but only one module's data is present, summarise only what you have without apologising for the missing part.
- Refer to columns naturally — e.g. "streak_count" → "streak", "obtained_score" → "score", "pass_rate_percent" → "pass rate".
- For employability data, refer to it as "Employability Track" not "POD".
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
    intent = state.get("intent", "")

    # For profile dict, log section sizes; for lists, log row count
    if isinstance(data, dict):
        section_info = ", ".join(f"{k}: {len(v) if isinstance(v, list) else 1} rows" for k, v in data.items())
        logger.info(f"[format] The data is a profile dict with sections — {section_info}.")
    else:
        logger.info(f"[format] formatting {len(data)} rows")

    # Strip the original question from the formatter — use a neutral instruction
    # so the LLM doesn't try to address parts of the question not covered by the data
    format_instruction = (
        f"Summarise the following {intent.replace('_', ' ').upper()} data in 2-5 concise bullet points. "
        f"Only describe what is in the data. Do not mention anything not present in the payload."
    )

    try:
        response = await _llm.ainvoke([
            {"role": "system", "content": FORMAT_SYSTEM},
            {"role": "user",   "content": f"{format_instruction}\n\nData:\n{data_str}"},
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