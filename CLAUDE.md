# TapTap Analytics Chatbot — Supervisor Architecture Branch

## Project Overview
Internal analytics chatbot for college faculty to ask natural language questions about student performance. Faculty type plain English questions and get instant answers.

## Stack
- FastAPI (port 8000) — backend
- Streamlit (port 8501) — frontend chat UI
- PostgreSQL on Azure — database (read-only)
- Azure OpenAI GPT-4o mini — LLM
- `langgraph-supervisor` (`create_supervisor`) — pipeline orchestration

## Branch Context
This is the `supervisor-architecture` branch. The original working implementation is in `llm-query-generation` branch. The refactor from a 3-node LangGraph pipeline (classify → execute → format) to a supervisor pattern using `langgraph-supervisor` is **complete**.

## Database
- Host: blackbuck-prod.postgres.database.azure.com
- User: bb_team_read_access (READ-ONLY — SELECT only, no INSERT/UPDATE/DELETE)
- Schemas in use: `employability_track`, `pod`, `gest`, `public`
- .env is one level up: `../.env` (load_dotenv("../.env") in constants.py)

## Three Modules
1. **POD (Problem of the Day)** — daily coding/aptitude/verbal challenges, streaks, badges
2. **Employability Track** — domain-based practice questions, pass rates, scores
3. **Assessments** — formal company assessments, shortlisted students, submissions

## File Structure
- `main.py` — FastAPI server, POST /chat endpoint; builds HumanMessage/AIMessage list from history, invokes graph with `{"messages": messages}`, extracts answer from last AIMessage and data/sql from ToolMessage in result
- `llm.py` — ~50 lines; `create_supervisor` from `langgraph-supervisor` with `SUPERVISOR_PROMPT`, `build_supervisor_graph()` returns compiled graph
- `analytics.py` — SQL generation, validation, execution for all 3 modules
- `schema_emp.py` — Employability schema context + mandatory SQL patterns
- `schema_pod.py` — POD schema context + mandatory SQL patterns
- `schema_assess.py` — Assessment schema context + mandatory SQL patterns
- `tool.py` — @tool wrappers connecting supervisor to analytics dispatchers
- `models.py` — Pydantic models: ChatRequest, ChatResponse (GraphState removed; last_sql/sql_chain_count/previous_intent fields in ChatRequest are now unused)
- `constants.py` — Intent constants, SQL_MAX_ROWS=50, SQL_MAX_CHAIN=3
- `db.py` — SQLAlchemy database connection
- `streamlit_app.py` — Streamlit chat UI (mostly unchanged; still sends history)

## Current Architecture (this branch)
Supervisor pattern using `create_supervisor` from `langgraph-supervisor`:
- Single supervisor LLM with tool-calling (~50 lines in llm.py)
- Tools: `emp_data_tool`, `pod_data_tool`, `assess_data_tool` from tool.py
- Supervisor handles routing, follow-up detection, and summarization
- No `create_react_agent`, no separate classify/execute/format nodes
- No manual `last_sql`, `sql_chain_count`, or `previous_intent` state — follow-up context comes from message history passed as LangChain message objects

## Original Architecture (llm-query-generation branch, for reference)
Three LangGraph nodes:
1. `classify_node` — LLM call, returns intent (pod/emp/assess/ambiguous/unknown) + is_followup flag
2. `execute_node` — deterministic routing, SQL chain management, module switch detection
3. `format_node` — LLM call, narrates DB results in 2-5 bullets

## Key Features (preserved in analytics.py / tool.py)
1. **SQL generation** — LLM generates SQL from schema context in analytics.py — DO NOT CHANGE
2. **SQL validation** — SELECT/WITH only, forbidden keywords, JOIN sanity checks, LIMIT injection — DO NOT CHANGE
3. **Self-healing retry** — DB error → LLM fixes SQL once → retry with rollback — DO NOT CHANGE
4. **Ambiguous name guard** — multiple students matching a name → list names and ask for full name — handled in supervisor response rules
5. **TRIM fix** — already in schema contexts, no change needed

Note: SQL chain drift control (sql_chain_count), follow-up SQL threading (last_sql), and module switch detection (previous_intent) are no longer manually managed — the supervisor handles follow-ups via conversation history.

## State / API Contract
Sent from Streamlit each turn (ChatRequest):
- `message` — current faculty question
- `college_name` — optional sidebar filter
- `history` — last 2 prior exchanges as list of strings
- `last_sql`, `sql_chain_count`, `previous_intent` — still in ChatRequest but no longer used by the supervisor

Returned to Streamlit after each turn (ChatResponse):
- `answer` — 2-5 bullet narrative
- `sql` — generated SQL (extracted from ToolMessage)
- `data` — raw DB rows for the expandable table
- `intent` — display label shown in UI
- `sql_chain_count`, `previous_intent` — still in ChatResponse for backwards compatibility but not meaningful

## SQL Safety Rules (in analytics.py _validate_sql())
- Must start with SELECT or WITH (CTEs allowed)
- No INSERT/UPDATE/DELETE/DROP/CREATE/ALTER/TRUNCATE/GRANT/REVOKE
- JOIN count must not exceed 6
- JOIN count must not significantly exceed ON/USING count (cartesian product guard)
- LIMIT 50 auto-injected if missing

## Known Data Issues
- department_id backfilled as 'other' for all students — branch filtering won't work
- Assessment status values: pass/fail/partiallyCorrect/underReview (not just pass/fail)

## What NOT to Change
- `analytics.py` — SQL generation logic, all 3 dispatchers, validation, self-healing
- `schema_emp.py`, `schema_pod.py`, `schema_assess.py` — schema contexts and query patterns
- `streamlit_app.py` — UI and session state management
- `constants.py` — all constants
- `db.py` — database connection
- `models.py` ChatRequest and ChatResponse — API contract with Streamlit must stay the same
- `tool.py` — @tool wrappers; tools call analytics dispatchers directly, no agent wrapping

## Logging & Debuggability Standard (MANDATORY)

Every node, function, and decision point must be logged clearly enough that 
any developer can debug a production issue from terminal logs alone — without 
needing Claude or any external help.

Rules for every code change:
- Every node must log what it RECEIVED at the start
- Every node must log what DECISION it made
- Every node must log what it RETURNED at the end
- Every branch/condition must have a log explaining which path was taken and why
- Errors must log the full context — what was being attempted, what failed, what the input was

Log format already in use:
  [node_name] Description — key=value | key=value

Examples of good logs:
  [supervisor] Received query: '...' | history_length=3 | prev_domain='emp'
  [supervisor] Decision → domain='emp'
  [sql_node] Fresh question — no history context
  [sql_node] Follow-up detected — passing conversation history (1243 chars)
  [sql_gen] SQL: SELECT ...
  [sql_exec] 50 rows returned | error=None
  [formatter] Formatting answer | domain='emp' | rows=50 | error=None
  [formatter] Final answer (first 200 chars): ...

Bad logs (never do this):
  logger.info("processing")
  logger.info(f"done: {result}")
  logger.error(f"error: {e}")

This standard applies to ALL future code written for this project.