# llm.py — TapTap Analytics Chatbot
# Contains:
#   - Azure OpenAI LLM setup
#   - Classification prompt (3 domain intents + query_type param)
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
    INTENT_POD, INTENT_EMP, INTENT_ASSESS, INTENT_UNKNOWN, INTENT_AMBIGUOUS,
)
from models import GraphState
from tool import TOOL_MAP
from logger import logger


# ── LLM — imported from models.py ────────────────────────────────────────────
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


# ── Domain intent → tool name mapping (3 entries) ────────────────────────────

INTENT_TO_TOOL: dict[str, str] = {
    INTENT_POD:    "pod_data_tool",
    INTENT_EMP:    "emp_data_tool",
    INTENT_ASSESS: "assess_data_tool",
}


# ── Classification prompt ─────────────────────────────────────────────────────

CLASSIFY_SYSTEM = """You are an intent classifier for a college faculty analytics chatbot.
Faculty ask questions about POD (Problem of the Day), Employability Track, and Assessments.

Your job: return ONE domain intent and a params object that fully describes what data to fetch.
The params object MUST always include a "query_type" field that specifies the exact sub-query.

════════════════════════════════════════════════════════
CRITICAL RULES — READ THESE FIRST
════════════════════════════════════════════════════════

RULE 1 — SINGLE INTENT ONLY:
Return exactly one of: "pod", "emp", "assess", "unknown".
If the user mentions two modules, pick the primary one (mentioned first or with more detail).

RULE 2 — COLLEGE NAME vs STUDENT NAME vs BRANCH:
College names (SRM, VIT, Anna University, CMRIT, Geethanjali…) → college_name param.
Student names (individual people like "Rahul", "Priya") → student_name param.
NEVER put a college name into student_name.
IMPORTANT: Extract only the college keyword, not the full phrase.
"from Annamacharya college" → college_name="Annamacharya" (not "Annamacharya college")
"from CMR college" → college_name="CMR" (not "CMR college")
"from VIT university" → college_name="VIT" (not "VIT university")

RULE 3 — DO NOT HALLUCINATE PARAMS:
Only extract params the user explicitly mentioned. Never infer or assume unstated values.
STRICT: Every param you return MUST appear word-for-word in the CURRENT message.
If college_name, student_name, limit, or any other param is not in the CURRENT message, do NOT include it.
Do NOT borrow params from previous questions in history under any circumstances.
Example: if history has "from CMR" but the current message does not mention CMR, do NOT add college_name="CMR".
Example: "Who lost their streak recently?" — no college mentioned → do NOT add college_name.
Example: "Show me the top scorers" — no college, no limit → params should only contain query_type.
If you are unsure whether a param was mentioned, leave it out. Omission is always safer than hallucination.

RULE 4 — STUDENT PROFILE DEFAULT:
If the user asks about a named student with NO module mentioned ("how is [name] doing?",
"[name]'s performance"), default to intent="pod", query_type="pod_student_profile".
Only use emp with query_type="emp_user_profile" when "employability" is explicitly stated.

RULE 5 — DOMAIN QUERIES:
"pass rate for Data Structures", "how are students doing in Algorithms" →
intent="emp", query_type="emp_domain_breakdown", domain_name set.

RULE 6 — WEAKEST STUDENTS IN [DOMAIN]:
"weakest students in Algorithms", "who struggles with Data Structures" →
intent="emp", query_type="emp_subdomain_breakdown", domain_name set.

RULE 7 — emp_user_profile NEVER uses info_type:
emp_user_profile always returns all sections. Do NOT add info_type for emp_user_profile.
info_type only applies to pod_student_profile.

RULE 8 — ASSESS vs EMP DOMAIN:
When the query contains "top scorers for", "skill breakdown for", "difficulty breakdown for",
"pass rate for", "completion rate for", or "overview of" followed by a name that looks like
a job title or assessment (e.g. "Backend Developer", "Angular", "Web Developer",
"Smart Interview", "DSA in c", "Java Developer", "Frontend Developer") →
use the matching assess_* query_type. NOT emp_domain_breakdown.
emp_domain_breakdown is for broad CS academic topics and domain names including:
"Data Structures", "DSA", "Algorithms", "Mathematics", "Machine Learning", "ML",
"Python", "Java", "SQL", "Aptitude", "Quantitative Aptitude", "Dynamic Programming", "DP",
"Networking", "Cyber Security", "Data Science", "Full Stack Development".
These are always emp_domain_breakdown regardless of phrasing.
EXAMPLES:
  "pass rate for Backend Developer" → assess_pass_rate, assessment_title="Backend Developer"
  "skill breakdown for angular" → assess_skill_breakdown, assessment_title="angular"
  "top scorers for Java Developer" → assess_top_scorers, assessment_title="Java Developer"
  "pass rate for DSA" → emp_domain_breakdown, domain_name="DSA"
  "pass rate for Data Structures" → emp_domain_breakdown, domain_name="Data Structures"
  "pass rate for ML" → emp_domain_breakdown, domain_name="ML"
  "pass rate for Python" → emp_domain_breakdown, domain_name="Python"

════════════════════════════════════════════════════════
DOMAIN INTENTS AND QUERY TYPES
════════════════════════════════════════════════════════

━━━ INTENT: "pod" ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


query_type: "pod_who_solved_today"
  params: college_name (str, optional)
  use for: "who solved today's POD", "who passed today"

query_type: "pod_attempt_count_today"
  params: college_name (str, optional)
  use for: "how many attempted POD today", "attempt count today"

query_type: "pod_question_today"
  params: (none)
  use for: "what is today's POD", "today's question"

query_type: "pod_fastest_solver"
  params: college_name (str, optional), limit (int, default 10)
  use for: "who solved POD fastest", "quickest solver today"

query_type: "pod_not_attempted_today"
  params: college_name (str, optional), limit (int, default 20)
  use for: "who hasn't attempted POD", "students who skipped today"

query_type: "pod_pass_fail_summary"
  params: college_name (str, optional), date_filter (str, optional — "today" or "YYYY-MM-DD"), limit (int, default 20)
  use for: "pass fail summary", "how many passed vs failed"

query_type: "pod_pass_rate"
  params: college_name (str, optional)
  use for: "POD pass rate", "what % pass POD", "overall pass rate for POD"
  NOTE: for employability pass rate use emp with query_type="emp_pass_rate"

query_type: "pod_top_passers"
  params: college_name (str, optional), limit (int, default 10)
  use for: "top passers", "who passed the most PODs"

query_type: "pod_never_passed"
  params: college_name (str, optional), limit (int, default 20)
  use for: "students who never passed", "zero pass students"

query_type: "pod_weekly_passers"
  params: college_name (str, optional), limit (int, default 20)
  use for: "who passed this week", "weekly passers"

query_type: "pod_difficulty_breakdown"
  params: college_name (str, optional)
  use for: "POD difficulty breakdown", "easy vs medium vs hard pass rate"

query_type: "pod_language_breakdown"
  params: college_name (str, optional)
  use for: "which languages are students using", "POD language stats"

query_type: "pod_hard_solvers"
  params: college_name (str, optional), limit (int, default 20)
  use for: "who solved hard PODs", "hard difficulty solvers"

query_type: "pod_longest_streak"
  params: college_name (str, optional), limit (int, default 10)
  use for: "longest streak", "who has the best streak"

query_type: "pod_active_streaks"
  params: college_name (str, optional), min_streak (int, default 3), limit (int, default 20)
  use for: "active streaks", "who currently has a streak"

query_type: "pod_lost_streak"
  params: college_name (str, optional), limit (int, default 20)
  use for: "who lost their streak", "broken streaks recently"

query_type: "pod_top_coins"
  params: college_name (str, optional), limit (int, default 10)
  use for: "most coins", "top coin earners", "who has the most coins"

query_type: "pod_total_points_today"
  params: college_name (str, optional)
  use for: "total points today", "points earned today"

query_type: "pod_top_scorers"
  params: college_name (str, optional), limit (int, default 10),
          days (int, optional — number of days to look back, e.g. 30 for "last 30 days"),
          week_filter (bool, optional — true if "this week", maps to days=7)
  use for: "POD leaderboard", "top scorers", "highest scoring students", "most points overall"
  EXAMPLES:
    "top 10 scorers in the last 30 days" → limit=10, days=30
    "top scorers this week" → week_filter=true (or days=7)
    "top scorers in the last 7 days" → days=7
    "top POD scorers" → no days filter

query_type: "pod_badge_earners"
  params: college_name (str, optional), limit (int, default 20)
  use for: "who earned badges", "badge earners"

query_type: "pod_weekly_badge_earners"
  params: college_name (str, optional), limit (int, default 20)
  use for: "who earned badges this week", "badges this week"

query_type: "pod_daily_trend"
  params: college_name (str, optional), days (int, default 30)
  use for: "POD daily trend", "average students attempting POD", "POD activity over last N days",
           "how many students attempted POD each day", "POD participation trend"
  EXAMPLES:
    "average students attempting POD in the last 10 days" → days=10
    "POD activity over the last 30 days" → days=30
    "daily POD trend" → days=30 (default)
    "POD trend for last 2 weeks" → days=14

query_type: "pod_student_profile"
  params: student_name (str, required), college_name (str, optional),
          date_filter (str, optional — "today" or "YYYY-MM-DD"),
          info_type (str, optional — "submissions"/"streaks"/"badges"/"coins"/"all", default "all"),
          language (str, optional), week_filter (bool, optional), pod_type (str, optional — "coding"/"aptitude"/"verbal")
  use for: "[name]'s POD profile", "how is [name] doing" (no module), "[name]'s streaks/badges"
  DEFAULT: if no module mentioned and a student name given, use this
  EXTRACTION EXAMPLES:
    "coding submissions" / "coding POD" → pod_type="coding"
    "aptitude submissions" → pod_type="aptitude"
    "verbal submissions" → pod_type="verbal"
    "this week" / "weekly" → week_filter=true
    "in python" / "using java" → language="python"/"java"
    "submissions only" → info_type="submissions"
    "streaks" → info_type="streaks"
    "badges" → info_type="badges"
    "streak and badge history" / "streaks and badges" → info_type="streaks, badges"
    "submissions and streaks" → info_type="submissions, streaks"
    CRITICAL — pod_type + info_type interaction:
    When the query mentions a pod_type (coding/aptitude/verbal) AND the word "submissions" or "questions",
    set info_type="submissions". The pod_type filter only applies to the submissions section.
    When the query mentions a pod_type but asks for "streak", "badges", "coins", or "profile",
    do NOT set info_type — leave it as "all" so all sections are returned.
    EXAMPLES:
      "Show Pranith's coding submissions" → pod_type="coding", info_type="submissions"
      "Show Pranith's aptitude submissions this week" → pod_type="aptitude", info_type="submissions", week_filter=true
      "Show Pranith's streak in coding" → pod_type="coding", info_type="streaks"
      "Show Pranith's coding profile" → pod_type="coding" only, no info_type (returns all)
      "Show Pranith's coding badges" → pod_type="coding", info_type="badges"

━━━ INTENT: "emp" ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

query_type: "emp_top_scorers"
  params: college_name (str, optional), limit (int, default 10), week_filter (bool, optional)
  use for: "employability top scorers", "highest score in employability", "employability leaderboard"

query_type: "emp_most_solved"
  params: college_name (str, optional), limit (int, default 20)
  use for: "who solved the most employability questions"

query_type: "emp_difficulty_stats"
  params: college_name (str, optional)
  use for: "employability difficulty breakdown", "easy vs hard in employability"

query_type: "emp_pass_rate"
  params: college_name (str, optional)
  use for: "employability pass rate", "employability success rate"

query_type: "emp_domain_students"
  params: domain_name (str, required), college_name (str, optional), limit (int, default 10)
  use for: "who passed in [domain]", "top students in [domain]", "show students in [domain]",
           "who are the best in [domain]", "students who passed DSA", "list students in Python domain"
  NOTE: domain_name is required. Always set it. Use _normalize_domain logic — DSA → Data Structures etc.
  EXAMPLES:
    "who passed in DSA" → domain_name="DSA"
    "top students in Data Structures" → domain_name="Data Structures"
    "show students in Python domain from CMR" → domain_name="Python", college_name="CMR"

query_type: "emp_language_stats"
  params: college_name (str, optional)
  use for: "employability language breakdown", "python vs java in employability"

query_type: "emp_domain_breakdown"
  params: college_name (str, optional), domain_name (str, optional — set for specific CS domain)
  use for: "employability by domain", "pass rate for Data Structures", "performance in Algorithms"
  EXAMPLES: "pass rate for Data Structures" → domain_name="Data Structures"
            "which domain has most submissions" → no domain_name

query_type: "emp_subdomain_breakdown"
  params: college_name (str, optional), domain_name (str, optional), limit (int, default 20)
  use for: "subtopic breakdown", "weakest students in [domain]", "who struggles with [domain]"

query_type: "emp_question_type_stats"
  params: college_name (str, optional)
  use for: "employability question types", "performance by question type"

query_type: "emp_hardest_questions"
  params: college_name (str, optional), limit (int, default 20), difficulty (str, optional — ONLY if explicitly stated)
  use for: "hardest employability questions", "which questions do students fail most"
  WARNING: only set difficulty if user explicitly states it

query_type: "emp_recent_activity"
  params: college_name (str, optional), limit (int, default 20), date_filter (str, optional),
          days (int, optional), difficulty (str, optional), language (str, optional)
  use for: "recent employability activity", "latest submissions", "submissions from [college] in last N days"
  CRITICAL: college names like "SRM", "VIT" → college_name, NEVER student_name
  EXTRACTION EXAMPLES:
    "today" / "submitted today" / "questions today" → date_filter="today"
    "yesterday" → date_filter="yesterday"
    "last 7 days" / "past week" → days=7
    "last 30 days" → days=30

query_type: "emp_daily_trend"
  params: college_name (str, optional), days (int, default 30)
  use for: "employability trend", "submissions per day", "daily employability activity"

query_type: "emp_user_profile"
  params: student_name (str, required), college_name (str, optional),
          difficulty (str, optional), language (str, optional), date_filter (str, optional)
  use for: "[name]'s employability profile", "[name] in employability"
  ONLY when user explicitly mentions "employability" + a person's name
  DO NOT add info_type — always returns all sections
  EXTRACTION EXAMPLES:
    "hard questions only" → difficulty="hard"
    "medium difficulty" → difficulty="medium"
    "in python" → language="python"

━━━ INTENT: "assess" ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

IMPORTANT — ASSESSMENT TITLE EXTRACTION:
Always extract the FULL assessment title verbatim. Do NOT truncate.
"Web Developer - Angular - Smart Interview" → assessment_title="Web Developer - Angular - Smart Interview"
Do NOT extract just "Smart Interview" from the above.

query_type: "assess_list"
  params: assessment_title (str, optional — keyword filter)
  use for: "list all assessments", "show assessments for java developer"

query_type: "assess_recent"
  params: limit (int, default 10)
  use for: "recent assessments", "latest assessments", "newest assessments"

query_type: "assess_overview"
  params: assessment_title (str, optional)
  use for: "[assessment] overview", "details for [assessment]", "shortlisted vs submitted"

query_type: "assess_top_scorers"
  params: assessment_title (str, optional), limit (int, default 10)
  use for: "top scorers in [assessment]", "who scored highest in [assessment]"

query_type: "assess_pass_rate"
  params: assessment_title (str, optional)
  use for: "pass rate for [assessment]", "how many passed [assessment]"
  NOTE: for POD pass rate use pod with query_type="pod_pass_rate"
        for employability pass rate use emp with query_type="emp_pass_rate"

query_type: "assess_skill_breakdown"
  params: assessment_title (str, optional)
  use for: "skill breakdown for [assessment]", "which skills did students struggle with"

query_type: "assess_difficulty_breakdown"
  params: assessment_title (str, optional)
  use for: "difficulty breakdown for [assessment]", "easy vs hard in [assessment]"

query_type: "assess_completion_rate"
  params: assessment_title (str, optional)
  use for: "how many completed [assessment]", "completion rate", "who didn't attempt [assessment]"

query_type: "assess_student_result"
  params: student_name (str, required), assessment_title (str, optional)
  use for: "[name]'s result in [assessment]", "how did [name] do in [assessment]",
           "how did [name] do in assessments", "[name]'s assessment results"
  Use when a student name is present AND "assessment" or a specific title is mentioned.
  If no specific title given, omit assessment_title — returns all assessments for that student.

query_type: "assess_student_attempts"
  params: student_name (str, required)
  use for: "[name]'s assessment history", "all assessments taken by [name]"

query_type: "assess_shortlisted_not_submitted"
  params: assessment_title (str, optional), limit (int, default 10)
  use for: "who didn't submit [assessment]", "shortlisted students who didn't attempt",
           "which students were shortlisted but didn't submit", "who was shortlisted but absent"
  EXAMPLES:
    "who didn't submit the Backend Developer assessment" → assessment_title="Backend Developer"
    "show shortlisted students who haven't submitted" → no assessment_title

query_type: "assess_passed_students"
  params: assessment_title (str, optional), limit (int, default 10)
  use for: "who passed [assessment]", "students who passed [assessment]",
           "list of students who cleared [assessment]", "which students passed"
  EXAMPLES:
    "who passed the Backend Developer assessment" → assessment_title="Backend Developer"
    "show students who passed Angular assessment" → assessment_title="Angular"
    "which students cleared the assessment" → no assessment_title

━━━ INTENT: "unknown" ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

use ONLY when the question has nothing to do with POD, Employability, or Assessments
(e.g. weather, jokes, general coding questions).
Do NOT use unknown for multi-module queries — pick the primary intent.

━━━ INTENT: "ambiguous" ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

use when ALL of these are true:
1. No module keyword present (no "POD", "employability", "assessment", "streak", "badge", "coin")
2. No student name present (named student queries default to pod_student_profile per Rule 4)
3. The query is aggregate/leaderboard style and could genuinely apply to BOTH POD and Employability

AMBIGUOUS EXAMPLES (use intent="ambiguous"):
  "Who is the top student today?" → ambiguous (top in POD or Employability?)
  "Who scored the highest?" → ambiguous
  "Show me the leaderboard" → ambiguous (POD or Employability leaderboard?)
  "Show the leaderboard" → ambiguous
  "Leaderboard" → ambiguous
  "What's the pass rate?" → ambiguous
  "Who performed best this week?" → ambiguous
  "Show me recent activity" → ambiguous
  "Who has the most points?" → ambiguous (could be POD score or Employability score)
  "Top students" → ambiguous
  "Who is performing best?" → ambiguous

NOT AMBIGUOUS — do NOT use ambiguous for these:
  "Who solved today's POD?" → clearly pod
  "Who has the longest streak?" → clearly pod (streaks are POD-only)
  "Show me badge earners" → clearly pod (badges are POD-only)
  "Show me employability top scorers" → clearly emp
  "List all assessments" → clearly assess
  "Show Pranith's profile" → pod (Rule 4 — named student defaults to pod)
  "Who solved hard problems?" → clearly pod

When intent is "ambiguous", return NO params — just the intent:
{ "intent": "ambiguous", "params": {} }

════════════════════════════════════════════════════════
OUTPUT FORMAT
════════════════════════════════════════════════════════

Respond ONLY with valid JSON — no explanation, no markdown:
{
  "intent": "<pod|emp|assess|unknown>",
  "params": {
    "query_type": "<exact_query_type_string>",
    "college_name": "...",
    "limit": 10
  }
}
Only include params the user explicitly mentioned. Always include query_type (except for unknown).
"""


# ── Node 1: classify ──────────────────────────────────────────────────────────

async def classify_node(state: GraphState) -> dict[str, Any]:
    logger.info(f"[classify] message='{state['message'][:80]}'")
    try:
        prior = [
            m["content"] for m in (state.get("history") or [])
            if m["role"] == "user"
        ]

        # Only send history if the current message contains a follow-up reference.
        # Standalone questions must never receive history to avoid param bleed.
        followup_triggers = ("his ", "her ", "their ", "them", "that ", "the same",
                             "this student", "first person", "second person", "above",
                             "previous", "same assessment", "same student",
                             # assessment follow-ups
                             "skill breakdown", "difficulty breakdown", "completion rate",
                             "what about", "for it", "for that", "for this",
                             "same one", "that one", "how about", "and the")
        needs_context = any(t in state["message"].lower() for t in followup_triggers)

        def _build_messages(include_ctx):
            msgs = [{"role": "system", "content": CLASSIFY_SYSTEM}]
            if include_ctx and prior and needs_context:
                # Only inject prior user questions as a context block — never as
                # full conversation history — so the LLM cannot copy params from them.
                ctx_lines = chr(10).join(f"- {q}" for q in prior[-4:])
                ctx = f"Previous questions in this session (use ONLY to resolve the reference in the next question — do NOT copy any params from these into the response):{chr(10)}{ctx_lines}"
                msgs.append({"role": "user", "content": ctx})
                msgs.append({"role": "assistant", "content": "Understood. I will use this only to resolve the reference, not to copy params."})
            # Always send only the current message — never the full role-alternating
            # message history — to prevent the LLM from bleeding params across turns.
            msgs.append({"role": "user", "content": state["message"]})
            return msgs

        try:
            response = await _llm.ainvoke(_build_messages(True))
        except Exception as exc_cf:
            if "content_filter" in str(exc_cf) and prior:
                logger.warning("[classify] content filter with history — retrying without")
                response = await _llm.ainvoke(_build_messages(False))
            else:
                raise
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

        # Strip empty string params the LLM sometimes returns instead of omitting
        params = {k: v for k, v in params.items() if v != "" and v is not None}

        # Auto-inject college_name from session if LLM didn't extract one
        college_name = state.get("college_name")
        if college_name and "college_name" not in params:
            params["college_name"] = college_name

        # Post-classification fix: when pod_type is set (coding/aptitude/verbal),
        # always derive info_type from the message text — the LLM is unreliable
        # at handling the pod_type + info_type interaction correctly.
        if (params.get("query_type") == "pod_student_profile"
                and params.get("pod_type")):
            msg_lower = state["message"].lower()
            if any(w in msg_lower for w in ("submission", "question", "solved", "attempted")):
                params["info_type"] = "submissions"
            elif any(w in msg_lower for w in ("streak",)):
                params["info_type"] = "streaks"
            elif any(w in msg_lower for w in ("badge",)):
                params["info_type"] = "badges"
            elif any(w in msg_lower for w in ("coin",)):
                params["info_type"] = "coins"
            else:
                # "profile" or no specific keyword → remove any LLM-set info_type
                # so all sections are returned
                params.pop("info_type", None)

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

    if intent == INTENT_AMBIGUOUS:
        return {
            "data": None,
            "answer": (
                "Could you clarify which module you mean?\n\n"
                "- **POD (Problem of the Day)** — daily coding/aptitude/verbal challenges\n"
                "- **Employability Track** — domain-based practice questions\n"
                "- **Assessments** — formal company assessments\n\n"
                "For example:\n"
                "- *Who is the top scorer in POD?*\n"
                "- *Who are the top employability scorers?*\n"
                "- *Who scored highest in the Backend Developer assessment?*"
            ),
        }

    tool_name = INTENT_TO_TOOL.get(intent)
    if not tool_name or tool_name not in TOOL_MAP:
        logger.warning(f"[execute] no tool mapped for intent={intent}")
        return {"data": None, "answer": "I don't have a handler for that question yet."}

    tool_fn = TOOL_MAP[tool_name]
    logger.info(f"[execute] calling tool={tool_name} query_type={params.get('query_type')} params={params}")

    try:
        result = await tool_fn.ainvoke({"params": params})
        return {"data": result}
    except Exception as exc:
        logger.error(f"[execute] tool error: {exc}")
        return {"data": None, "error": str(exc), "answer": f"Database error: {exc}"}


# ── Node 3: format answer ─────────────────────────────────────────────────────

FORMAT_SYSTEM = """You are a helpful analytics assistant for college faculty.
You will receive a data label and a JSON data payload about student activity.

Rules:
- NEVER reconstruct or redraw the data as a table — the UI already shows the full table.
- Write 2-5 concise bullet points highlighting the key insights from the data provided.
- When data contains student names, mention specific names (top performers, notable cases).
- Round numbers to 2 decimal places.
- Do NOT invent, assume, or speculate about values not present in the data payload.
- Do NOT mention or comment on data that is missing — only summarise what IS in the data.
- Refer to columns naturally — e.g. "streak_count" → "streak", "obtained_score" → "score", "pass_rate_percent" → "pass rate".
- For employability data, refer to it as "Employability Track" not "POD".
"""


# ── No-data suggestions — shown when SQL returns 0 rows ──────────────────────
# Each message tells the faculty exactly what they need to provide.

_NO_DATA_SUGGESTIONS: dict[str, str] = {
    # ── POD ───────────────────────────────────────────────────────────────────
    "pod_who_solved_today": (
        "No students found who solved today's POD with those filters. "
        "Try removing the college filter, or check that the college name matches your DB "
        "(e.g. 'Who solved today's POD from CMR Technical Campus?')."
    ),
    "pod_attempt_count_today": (
        "No attempt data found for today. "
        "Try without a college filter: 'How many students attempted POD today?'"
    ),
    "pod_question_today": (
        "No POD question found for today. The problem of the day may not have been set yet."
    ),
    "pod_fastest_solver": (
        "No completed attempts found for today's POD. "
        "Try: 'Who solved the POD fastest today?' without a college filter."
    ),
    "pod_not_attempted_today": (
        "No students found who haven't attempted today's POD with those filters. "
        "Try: 'Which students haven't attempted POD today?' without a college filter."
    ),
    "pod_pass_fail_summary": (
        "No pass/fail data found. Try specifying a date or removing the college filter, "
        "e.g. 'Show me the pass fail summary for today'."
    ),
    "pod_pass_rate": (
        "No pass rate data found. Try: 'What is the overall POD pass rate?' without filters."
    ),
    "pod_top_passers": (
        "No passers found with those filters. "
        "Try: 'Show me the top 10 passers' without a college filter."
    ),
    "pod_never_passed": (
        "No students found who never passed POD with those filters. "
        "Either all students from that college have passed, or the college name didn't match. "
        "Try: 'Which students have never passed a single POD?' without a college filter."
    ),
    "pod_weekly_passers": (
        "No students passed POD this week with those filters. "
        "Try: 'Who passed POD this week?' without a college filter."
    ),
    "pod_difficulty_breakdown": (
        "No difficulty data found. Try: 'Show me the POD difficulty breakdown' without filters."
    ),
    "pod_language_breakdown": (
        "No language data found. Try: 'Which languages are students using for POD?'"
    ),
    "pod_hard_solvers": (
        "No students found who solved hard PODs with those filters. "
        "Try: 'Who solved hard PODs?' without a college filter."
    ),
    "pod_longest_streak": (
        "No streak data found. Try: 'Who has the longest POD streak?'"
    ),
    "pod_active_streaks": (
        "No active streaks found with those filters. "
        "Try lowering the minimum streak, e.g. 'Who has active streaks of at least 3 days?'"
    ),
    "pod_lost_streak": (
        "No lost streaks found recently. Try: 'Who lost their streak recently?' without filters."
    ),
    "pod_top_coins": (
        "No coin data found. Try: 'Who has the most POD coins?' without a college filter."
    ),
    "pod_total_points_today": (
        "No points earned today with those filters. "
        "Try: 'Total points earned today' without a college filter."
    ),
    "pod_top_scorers": (
        "No scorers found with those filters. "
        "Try: 'Who are the top POD scorers?' without a college or week filter."
    ),
    "pod_badge_earners": (
        "No badge earners found. Try: 'Who earned POD badges?' without a college filter."
    ),
    "pod_weekly_badge_earners": (
        "No badges earned this week with those filters. "
        "Try: 'Who earned badges this week?' without a college filter."
    ),
    "pod_daily_trend": (
        "No POD trend data found for that period. "
        "Try: 'Show me the POD daily trend for the last 30 days'."
    ),
    "pod_student_profile": (
        "No student found matching that name. "
        "Make sure to use the full name, e.g. 'Show me Pranith Kumar Navath\'s profile'. "
        "If you used a partial name, try the full name."
    ),
    # ── Employability ─────────────────────────────────────────────────────────
    "emp_top_scorers": (
        "No employability scorers found with those filters. "
        "Try: 'Show me the top 10 employability scorers' without a college or week filter."
    ),
    "emp_most_solved": (
        "No data found. Try: 'Who solved the most employability questions?' without filters."
    ),
    "emp_difficulty_stats": (
        "No difficulty data found. Try: 'Show me employability difficulty stats' without filters."
    ),
    "emp_pass_rate": (
        "No pass rate data found. Try: 'What is the employability pass rate?' without filters."
    ),
    "emp_language_stats": (
        "No language data found. Try: 'Show me employability language stats' without filters."
    ),
    "emp_domain_breakdown": (
        "No domain data found. The domain name may not match exactly. "
        "Try: 'Show me the employability domain breakdown' to see all available domains."
    ),
    "emp_subdomain_breakdown": (
        "No subdomain data found for that domain. "
        "Try: 'Show me the subdomain breakdown' without a domain filter to see all subdomains."
    ),
    "emp_question_type_stats": (
        "No question type data found. Try: 'Show me employability question type stats' without filters."
    ),
    "emp_hardest_questions": (
        "No questions found with those filters. "
        "Try: 'Which employability questions have the lowest pass rate?' without a difficulty filter."
    ),
    "emp_recent_activity": (
        "No recent employability activity found with those filters. "
        "Try a broader time range, e.g. 'Show me recent employability submissions in the last 30 days'."
    ),
    "emp_daily_trend": (
        "No daily trend data found. Try: 'Show me the employability daily trend for the last 30 days'."
    ),
    "emp_domain_students": (
        "No students found for that domain. The domain name may not match exactly. "
        "Try: 'Show me the employability domain breakdown' to see all available domains, "
        "then use the exact domain name e.g. 'Who passed in Data Structures?'"
    ),
    "emp_user_profile": (
        "No student found matching that name in the Employability Track. "
        "Make sure to use the full name and include 'employability', "
        "e.g. 'Show me Pranith Kumar Navath\'s employability profile'."
    ),
    # ── Assessments ───────────────────────────────────────────────────────────
    "assess_list": (
        "No assessments found matching that title. "
        "Try: 'List all assessments' to see everything, or use a broader keyword."
    ),
    "assess_recent": (
        "No recent assessments found. Try: 'Show me recent assessments'."
    ),
    "assess_overview": (
        "No assessment found with that title. "
        "Try: 'List all assessments' to find the exact title, "
        "then use the full title e.g. 'Show me the overview of Web Developer - Angular - Smart Interview'."
    ),
    "assess_top_scorers": (
        "No scorers found for that assessment. "
        "The assessment may have no submissions yet. "
        "Try: 'Show me the overview of [assessment title]' to check submission count first."
    ),
    "assess_pass_rate": (
        "No pass rate data found for that assessment. "
        "Try: 'List all assessments' to find the exact title, "
        "then: 'What is the pass rate for [full assessment title]?'"
    ),
    "assess_skill_breakdown": (
        "No skill breakdown data found. The assessment may have no submissions yet. "
        "Try: 'Show me the overview of [assessment title]' to verify submissions exist first."
    ),
    "assess_difficulty_breakdown": (
        "No difficulty breakdown found. The assessment may have no submissions yet. "
        "Try: 'Show me the overview of [assessment title]' to verify submissions exist first."
    ),
    "assess_completion_rate": (
        "No completion rate data found for that assessment. "
        "Try: 'List all assessments' to find the exact title."
    ),
    "assess_student_result": (
        "No assessment results found for that student. "
        "They may not have taken any assessments yet, or try a different assessment title."
    ),
    "assess_student_attempts": (
        "No assessment attempts found for that student. "
        "They may not have taken any assessments yet."
    ),
    "assess_shortlisted_not_submitted": (
        "No shortlisted students found who haven't submitted. "
        "Either all shortlisted students have submitted, or the assessment title didn't match. "
        "Try: 'List all assessments' to find the exact title."
    ),
    "assess_passed_students": (
        "No students found who passed that assessment. "
        "The assessment may have no passing submissions yet. "
        "Try: 'Show me the overview of [assessment title]' to check submission count first."
    ),
    # ── Default ───────────────────────────────────────────────────────────────
    "default": (
        "No data found for that query. Try being more specific — "
        "include a college name, student full name, or time period. "
        "You can also ask 'List all assessments' or 'Show me the POD leaderboard' to explore."
    ),
}


async def format_node(state: GraphState) -> dict[str, Any]:
    # Skip formatting if answer was already set by execute (error or unknown intent)
    if state.get("answer"):
        return {}
    if state.get("error") and not state.get("data"):
        return {}

    data = state.get("data") or []

    # Check empty in code — never let the LLM decide if data exists or not
    if not data:
        qt = (state.get("params") or {}).get("query_type", "")
        suggestion = _NO_DATA_SUGGESTIONS.get(qt, _NO_DATA_SUGGESTIONS["default"])
        return {"answer": suggestion}

    # Ambiguous name guard — if profile intent matched multiple students, ask for full name
    qt = (state.get("params") or {}).get("query_type", "")
    if qt in ("pod_student_profile", "emp_user_profile") and isinstance(data, dict):
        # pod_student_profile: use coins (1 row per matched student)
        # emp_user_profile: use summary (1 row per matched student)
        if qt == "pod_student_profile":
            anchor_rows = data.get("coins", [])
        else:
            anchor_rows = data.get("summary", [])
        if len(anchor_rows) > 1:
            names = ", ".join(r.get("name", "?") for r in anchor_rows[:5])
            more = f" and {len(anchor_rows) - 5} more" if len(anchor_rows) > 5 else ""
            return {"answer": (
                f"Found {len(anchor_rows)} students matching that name: {names}{more}. "
                f"Please use the full name to get a specific profile."
            )}

    data_str = _safe_json(data)

    # Use query_type for the format instruction label (matches old intent name)
    params    = state.get("params", {})
    qt        = params.get("query_type", state.get("intent", ""))
    label     = qt.replace("_", " ").upper()

    if isinstance(data, dict):
        section_info = ", ".join(f"{k}: {len(v) if isinstance(v, list) else 1} rows" for k, v in data.items())
        logger.info(f"[format] profile dict — {section_info}")
    else:
        logger.info(f"[format] formatting {len(data)} rows for {qt}")

    format_instruction = (
        f"Summarise the following {label} data in 2-5 concise bullet points. "
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
    logger.info("LangGraph pipeline compiled successfully.")
    return graph