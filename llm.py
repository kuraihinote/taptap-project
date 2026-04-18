# llm.py — TapTap Analytics Chatbot (Explicit Supervisor Workflow)
#
# Architecture: 3-node LangGraph pipeline
#   supervisor_node  → decides domain OR answers directly
#   sql_node         → picks schema, calls analytics._generate_and_run()
#   formatter_node   → turns raw DB rows into a clean faculty-friendly answer
#
# Why the rewrite:
#   The old create_supervisor() black-box made it impossible to see WHERE a
#   failure happened (wrong domain? bad SQL? empty DB result?). Every node
#   now logs its input and output so the terminal tells you exactly what went wrong.

import json
from typing import Any, Literal, Optional, TypedDict, Annotated, Sequence

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_core.output_parsers.json import parse_json_markdown
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from models import gpt_4o_mini_llm
from analytics import _generate_and_run
from schema_emp      import EMP_SCHEMA_CONTEXT
from schema_pod      import POD_SCHEMA_CONTEXT
from schema_assess   import ASSESS_SCHEMA_CONTEXT
from schema_hackathon import HACKATHON_SCHEMA_CONTEXT
from constants import CHECKPOINT_DB_URL
from logger import logger


# ══════════════════════════════════════════════════════════════════════════════
# STATE
# ══════════════════════════════════════════════════════════════════════════════

class TapTapState(TypedDict):
    # Current faculty question
    user_query:       str
    # Conversation history
    messages:         Annotated[Sequence[BaseMessage], add_messages]
    # Supervisor decision
    domain:           Optional[Literal["pod", "assess", "emp", "direct", "advice", "hackathon"]]
    direct_answer:    Optional[str]
    # SQL node output
    sql_query:        Optional[str]
    sql_result:       Optional[Any]
    sql_error:        Optional[str]
    # Summary of previous turn's question + 4 sample rows — passed to sql_node as context
    sql_data_summary: Optional[str]
    # Final formatted answer
    final_answer:     Optional[str]


# ══════════════════════════════════════════════════════════════════════════════
# SCHEMA MAP
# ══════════════════════════════════════════════════════════════════════════════

DOMAIN_SCHEMAS: dict[str, str] = {
    "emp":       EMP_SCHEMA_CONTEXT,
    "pod":       POD_SCHEMA_CONTEXT,
    "assess":    ASSESS_SCHEMA_CONTEXT,
    "hackathon": HACKATHON_SCHEMA_CONTEXT,
}


# ══════════════════════════════════════════════════════════════════════════════
# NODE 1 — SUPERVISOR
# Reads question + history, returns domain or a direct answer.
# ══════════════════════════════════════════════════════════════════════════════

_SUPERVISOR_BASE = """You are a routing assistant for a college faculty analytics chatbot.
Faculty ask questions about student performance across three modules.

Here is what each module handles:

emp — Employability Track: individual practice questions organised by subject domain
(Data Structures, Algorithms, Python, Java, SQL, DBMS, OOP, Operating Systems etc.),
difficulty levels, programming languages, pass rates on topics, employability score
percentages, submission counts, top scorers, and student profiles.

pod — Problem of the Day: daily challenges, who solved today, streaks, streak history,
who lost their streak, badges, coins, fastest solver, difficulty levels (easy/medium/hard),
POD types (coding/aptitude/verbal), college rankings by POD activity.

assess — Formal Assessments: ONLY for specific named tests with formal titles
(e.g. "Backend Developer - DSA in C", "TCS NQT", "MET Round 1"). If the question
mentions a subject like Data Structures, Python, or Algorithms without a formal test
name → it is emp, not assess. Use for: shortlisted students, submission results for
a specific named test, MET (Monthly Employability Test), profiling tests, skill tests,
completion rates.

hackathon — Hackathon / Skill Tests: named hackathon events, skill assessments,
employability tests, placement mock tests (e.g. TCS Placement Mock, Autosprint
Employability Test, Monthly Hackathon, MERN Stack Grand Test), profiling tests.
Use for: top scorers in a specific named test, subject-level performance (verbal,
aptitude, MCQ, coding), student score in a named test, completion rates for a test.
NOT for: POD challenges (use pod), domain practice questions (use emp), formal
recruitment assessments in gest schema (use assess).
NOTE: TCS Placement Mock Tests exist here. TCS NQT does NOT exist in the DB at all.

Your only job: read the question AND the conversation history, then return which
module it belongs to. Use the conversation history to understand follow-up questions
that may lack explicit context on their own. If the latest question is a short follow-up
or refinement with no clear module signal, look at the previous assistant response in
the history to determine which module was last active and route to that same module.

IMPORTANT: the key must always be "direct_answer" — never "direct", never "answer"

NEVER use "direct" for anything about student performance, scores, submissions,
assessments, or analytics — always route those to emp, pod, or assess.
When in doubt, always pick the most likely module.
If the previous domain is known, short follow-ups with no competing module signal
should route to the previous domain — never direct.
"""

_SUPERVISOR_WITH_DATA = """
Data context from a previous query is available. The faculty has just seen student data.

Return ONLY valid JSON — no markdown, no explanation:

  {"domain": "emp"}
  {"domain": "pod"}
  {"domain": "assess"}
  {"domain": "hackathon"}
  {"domain": "advice"}

Route to "advice" if the faculty is asking what to do, how to help, how to improve,
or what actions to take based on the data they just saw.
Route to the appropriate data domain if they are asking a new data question.
"""

_SUPERVISOR_NO_DATA = """
No data context from a previous query is available.

Return ONLY valid JSON — no markdown, no explanation:

  {"domain": "emp"}
  {"domain": "pod"}
  {"domain": "assess"}
  {"domain": "hackathon"}
  {"domain": "direct", "direct_answer": "<your answer here>"}

Route to "direct" ONLY when the question is clearly outside student analytics:

  ANSWER directly (helpful and concise) if the question is educational or technical:
  - General knowledge, science, academic concepts: "what is ML", "explain p-value"
  - Technology, programming, computer science: "what is recursion", "explain REST APIs"
  - Career or industry concepts: "what is agile", "what does a data scientist do"

  DECLINE politely if the question is about entertainment or recreation:
  - Movies, music, TV shows, celebrities, sports, games
"""

def supervisor_node(state: TapTapState) -> dict:
    """
    Reads conversation history + latest question.
    Decides: answer directly OR route to a domain for SQL lookup.
    """
    prev_domain = state.get("domain")
    logger.info(f"[supervisor] Received query: '{state['user_query'][:120]}' | prev_domain='{prev_domain}'")

    # Build conversation context from history
    history_lines = []
    for msg in state["messages"]:
        if isinstance(msg, HumanMessage):
            history_lines.append(f"Faculty: {msg.content}")
        elif isinstance(msg, AIMessage):
            history_lines.append(f"Assistant: {msg.content}")
    history_text = "\n".join(history_lines) if history_lines else "(no prior conversation)"

    # Extract the first 600 chars of each schema — captures the full THIS MODULE COVERS
    # and NOT FOR boundary declarations at the top of each schema file.
    # Supervisor reads this dynamically so routing stays in sync with the schemas.
    module_context = (
        f"emp: {EMP_SCHEMA_CONTEXT[:600]}\n\n"
        f"pod: {POD_SCHEMA_CONTEXT[:600]}\n\n"
        f"assess: {ASSESS_SCHEMA_CONTEXT[:600]}\n\n"
        f"hackathon: {HACKATHON_SCHEMA_CONTEXT[:600]}\n\n"
    )

    prev_domain = state.get("domain")
    prev_domain_text = f"Previous domain used: {prev_domain}\n" if prev_domain else ""

    has_data_context = "yes" if state.get("sql_data_summary") else "no"

    user_text = (
        f"Available modules and what they cover:\n{module_context}\n"
        f"{prev_domain_text}"
        f"Data context from previous result available: {has_data_context}\n"
        f"Conversation so far:\n{history_text}\n\n"
        f"Latest question: {state['user_query']}"
    )

    system_prompt = _SUPERVISOR_BASE + (_SUPERVISOR_WITH_DATA if has_data_context == "yes" else _SUPERVISOR_NO_DATA)

    try:
        response = gpt_4o_mini_llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_text),
        ])
        raw = response.content.strip()
        logger.info(f"[supervisor] Raw LLM response: {raw}")

        parsed = parse_json_markdown(raw)
        domain: str = parsed.get("domain", "direct")
        direct_answer: str = parsed.get("direct_answer") or parsed.get("direct", "")

    except Exception as e:
        logger.error(f"[supervisor] Failed to parse LLM response: {e}")
        domain = "direct"
        direct_answer = "I'm sorry, I couldn't process that request. Please try rephrasing your question."

    logger.info(f"[supervisor] Decision → domain='{domain}'")

    updates: dict[str, Any] = {"domain": domain, "direct_answer": direct_answer}

    if domain == "direct":
        updates["final_answer"] = direct_answer
        updates["messages"] = [AIMessage(content=direct_answer)]
        updates["sql_data_summary"] = None
    elif prev_domain and prev_domain not in ("direct", "advice") and domain != prev_domain and domain != "advice":
        # Domain changed between turns — sql_data_summary is from a different schema.
        # Clear it so sql_node doesn't pass stale assess/emp/pod context to the wrong LLM.
        # Exception: routing to "advice" must preserve sql_data_summary — advice node needs it.
        updates["sql_data_summary"] = None
        logger.info(f"[supervisor] Domain changed '{prev_domain}' → '{domain}' — clearing stale sql_data_summary")

    return updates


# ══════════════════════════════════════════════════════════════════════════════
# NODE 2 — SQL NODE
# Picks schema for the chosen domain, calls analytics._generate_and_run().
# analytics.py already handles: LLM SQL gen → validation → DB execution → self-heal retry
# ══════════════════════════════════════════════════════════════════════════════

def sql_node(state: TapTapState) -> dict:
    """
    Uses the domain chosen by the supervisor to pick the right schema,
    then delegates to analytics._generate_and_run() for SQL generation + execution.
    """
    domain = state["domain"]
    question = state["user_query"]
    schema = DOMAIN_SCHEMAS[domain]

    logger.info(f"[sql_node] domain='{domain}' | question='{question[:120]}'")

    # Use sql_data_summary from previous turn as context if available.
    # sql_data_summary contains: previous question + 4 sample rows.
    # Generated by formatter_node at end of each turn.
    sql_data_summary = state.get("sql_data_summary") or ""

    if sql_data_summary:
        context_question = (
            f"Context from previous question and results:\n{sql_data_summary}\n\n"
            f"Current question: {question}"
        )
        logger.info(f"[sql_node] Using sql_data_summary as context ({len(sql_data_summary)} chars)")
    else:
        context_question = question
        logger.info(f"[sql_node] Fresh question — no previous context")

    result = _generate_and_run(context_question, schema)

    sql   = result.get("sql")
    data  = result.get("data", [])
    error = result.get("error")

    logger.info(f"[sql_node] SQL generated: {str(sql)[:200]}")
    logger.info(f"[sql_node] Rows returned: {len(data)} | Error: {error}")

    return {
        "sql_query":  sql,
        "sql_result": data,
        "sql_error":  error,
    }


# ══════════════════════════════════════════════════════════════════════════════
# NODE 3 — FORMATTER NODE
# Calls LLM to turn raw DB rows into a clean, faculty-friendly answer.
# ══════════════════════════════════════════════════════════════════════════════

_FORMATTER_SYSTEM = """You are a helpful assistant for college faculty at an edtech platform.
You have the faculty's original question and raw database results.
Write a clear, concise, human-friendly answer.

RULES:
- Use 2–5 bullet points for multiple rows. For a single value, one sentence is fine.
- If the database result has zero rows, say: "No data found. Try being more specific or check the filters."
- CRITICAL: If the database result has more than 0 rows, you MUST present the data regardless of what the values look like. Never say "No data found" when rows are present. Zero scores, null values, empty strings — all must be presented as-is.
- Never mention SQL, databases, tables, or technical details.
- Never say "course" — say "difficulty level".
- Round all numbers to 2 decimal places.
- Never list more than 10 items — summarise the rest as "...and N more".
- GROUPING — only group rows when a column in the data explicitly supports it:
  - If rows contain an 'assessment_title' column with multiple distinct values, group by assessment title.
  - If rows contain a 'college' or 'collegeName' column and grouping makes the answer clearer, group by college.
  - If rows contain a 'track' or 'domain' column with multiple values, group by that.
  - NEVER invent group headers like "Assessment 1", "Group A", or "Category 1" that are not in the data.
  - If no grouping column clearly applies, just list the rows in order.
- When grouping is applied, the 10-item limit applies per group, not across all rows combined.
- Never invent data that isn't in the results.
"""

def formatter_node(state: TapTapState) -> dict:
    """
    Takes raw DB rows + original question, asks LLM to write a faculty-friendly answer.
    """
    question   = state["user_query"]
    data       = state.get("sql_result") or []
    sql_error  = state.get("sql_error")
    domain     = state.get("domain", "")

    logger.info(f"[formatter] Formatting answer for domain='{domain}' | rows={len(data)} | error={sql_error}")

    if sql_error == "UNSUPPORTED":
        answer = (
            "I couldn't generate a query for that question. "
            "Try rephrasing — for example, be more specific about "
            "the module (employability, POD, assessments, or hackathons) "
            "or the metric you're looking for."
        )
        logger.info(f"[formatter] UNSUPPORTED query — returning guidance message | domain='{domain}'")
        return {
            "final_answer":     answer,
            "sql_data_summary": "",
            "messages":         [AIMessage(content=answer)],
        }

    # Serialise rows for the LLM (already Decimal/datetime-safe from _rows_to_dicts)
    data_text = json.dumps(data, indent=2) if data else "[]"

    user_text = (
        f"Faculty question: {question}\n\n"
        f"Database result ({len(data)} rows):\n{data_text}"
    )
    if sql_error:
        user_text += f"\n\nNote: A database error occurred — {sql_error}"

    try:
        response = gpt_4o_mini_llm.invoke([
            SystemMessage(content=_FORMATTER_SYSTEM),
            HumanMessage(content=user_text),
        ])
        answer = response.content.strip()
    except Exception as e:
        logger.error(f"[formatter] LLM error: {e}")
        answer = "I retrieved the data but couldn't format the answer. Please try again."

    logger.info(f"[formatter] Final answer (first 200 chars): {answer[:200]}")

    # Generate sql_data_summary for next turn's sql_node context.
    # Contains: previous question + 4 sample rows from current result.
    # Kept small to avoid token bloat in sql_node.
    if data:
        sample_rows = data[:4]
        sql_data_summary = (
            f"Previous question: {question}\n"
            f"Previous result sample (4 rows):\n{json.dumps(sample_rows, indent=2)}"
        )
        logger.info(f"[formatter] Generated sql_data_summary ({len(sql_data_summary)} chars)")
    else:
        sql_data_summary = ""
        logger.info(f"[formatter] No data — sql_data_summary cleared")

    return {
        "final_answer":     answer,
        "sql_data_summary": sql_data_summary,
        "messages":         [AIMessage(content=answer)],
    }


# ══════════════════════════════════════════════════════════════════════════════
# NODE 4 — ADVICE NODE
# Uses previous SQL result summary to give faculty practical, actionable advice.
# ══════════════════════════════════════════════════════════════════════════════

_ADVICE_SYSTEM = """You are an academic advisor for college faculty at an edtech platform.
The faculty has just seen data about their students and is asking for advice or guidance.

Use the provided data context to give specific, practical advice tailored to what the data shows.

RULES:
- Give 4–6 concise bullet points of actionable advice
- Base every point on the data provided — do not invent situations
- Speak directly to the faculty: "Consider...", "You may want to...", "Students who..."
- Never mention SQL, databases, tables, or technical details
- Never say "course" — say "difficulty level"
- Be encouraging and constructive
"""

def advice_node(state: TapTapState) -> dict:
    """
    Uses sql_data_summary from the previous turn to give faculty actionable advice.
    """
    question         = state["user_query"]
    sql_data_summary = state.get("sql_data_summary") or ""

    logger.info(f"[advice] Received question: '{question[:120]}' | sql_data_summary_len={len(sql_data_summary)}")

    user_text = (
        f"Faculty question: {question}\n\n"
        f"Data context:\n{sql_data_summary}"
    )

    try:
        response = gpt_4o_mini_llm.invoke([
            SystemMessage(content=_ADVICE_SYSTEM),
            HumanMessage(content=user_text),
        ])
        answer = response.content.strip()
    except Exception as e:
        logger.error(f"[advice] LLM error — question='{question[:120]}' | sql_data_summary_len={len(sql_data_summary)} | error={e}")
        answer = "I couldn't generate advice at this time. Please try again."

    logger.info(f"[advice] Final answer (first 200 chars): {answer[:200]}")

    return {
        "final_answer":     answer,
        "sql_data_summary": sql_data_summary,  # preserve for further follow-ups
        "messages":         [AIMessage(content=answer)],
    }


# ══════════════════════════════════════════════════════════════════════════════
# ROUTING — after supervisor
# ══════════════════════════════════════════════════════════════════════════════

def _route_after_supervisor(state: TapTapState) -> str:
    domain = state.get("domain")
    if domain == "direct":
        logger.info("[route] supervisor answered directly → END")
        return END
    if domain == "advice":
        logger.info("[route] routing to advice_node — data context available")
        return "advice_node"
    logger.info(f"[route] routing to sql_node for domain='{domain}'")
    return "sql_node"


# ══════════════════════════════════════════════════════════════════════════════
# GRAPH ASSEMBLY
# ══════════════════════════════════════════════════════════════════════════════

async def build_supervisor_graph() -> tuple[Any, Any]:
    """
    Builds and compiles the LangGraph supervisor workflow.

    Checkpointing strategy:
      - If CHECKPOINT_DB_URL is set (stage DB creds in .env) → AsyncPostgresSaver
        LangGraph auto-creates its tables on first run via checkpointer.setup().
      - If not set (local dev) → MemorySaver fallback. Fully functional for
        testing; history resets on server restart.

    Returns (graph, pg_ctx) so main.py can close the async Postgres context on
    shutdown. pg_ctx is None when using MemorySaver.
    """
    workflow = StateGraph(TapTapState)

    workflow.add_node("supervisor",  supervisor_node)
    workflow.add_node("sql_node",    sql_node)
    workflow.add_node("formatter",   formatter_node)
    workflow.add_node("advice_node", advice_node)

    workflow.set_entry_point("supervisor")

    workflow.add_conditional_edges(
        "supervisor",
        _route_after_supervisor,
        {
            "sql_node":   "sql_node",
            "advice_node": "advice_node",
            END: END,
        },
    )

    workflow.add_edge("sql_node",   "formatter")
    workflow.add_edge("formatter",  END)
    workflow.add_edge("advice_node", END)

    if CHECKPOINT_DB_URL:
        logger.info("[checkpointer] Using AsyncPostgresSaver (stage DB)")
        pg_ctx = AsyncPostgresSaver.from_conn_string(CHECKPOINT_DB_URL)
        checkpointer = await pg_ctx.__aenter__()
        # Creates checkpoint tables if they don't exist yet
        await checkpointer.setup()
        graph = workflow.compile(checkpointer=checkpointer)
        logger.info("Supervisor graph compiled with Postgres checkpointer.")
        return graph, pg_ctx
    else:
        logger.warning(
            "[checkpointer] CHECKPOINT_DB_URL not set — using MemorySaver. "
            "Add stage DB credentials to .env to enable persistent history."
        )
        graph = workflow.compile(checkpointer=MemorySaver())
        logger.info("Supervisor graph compiled with in-memory checkpointer.")
        return graph, None