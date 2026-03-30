# streamlit_app.py — TapTap POD Analytics Chatbot Frontend

import os
import requests
import pandas as pd
import streamlit as st

API_BASE = os.getenv("TAPTAP_API_URL", "http://localhost:8000")

st.set_page_config(
    page_title="TapTap Analytics",
    page_icon="🧩",
    layout="wide",
)


# ── Chart helper ──────────────────────────────────────────────────────────────

def _render_chart(df: pd.DataFrame, intent: str) -> None:
    try:
        if intent == "pod_difficulty_breakdown" and "difficulty" in df.columns:
            st.bar_chart(df.set_index("difficulty")["students_attempted"])
        elif intent == "pod_language_breakdown" and "language" in df.columns:
            st.bar_chart(df.set_index("language")["students"])
        elif intent in ("pod_top_passers", "pod_top_scorers", "pod_top_coins") and "name" in df.columns:
            score_col = (
                "questions_passed" if "questions_passed" in df.columns
                else "total_score" if "total_score" in df.columns
                else "total_coins" if "total_coins" in df.columns
                else None
            )
            if score_col:
                st.bar_chart(df.set_index("name")[score_col])
        elif intent in ("pod_longest_streak", "pod_active_streaks") and "streak_count" in df.columns:
            st.bar_chart(df.set_index("name")["streak_count"])
        elif intent == "pod_pass_rate" and "pass_rate_percent" in df.columns:
            st.bar_chart(df.set_index("college")["pass_rate_percent"])
        elif intent == "emp_top_scorers" and "name" in df.columns and "total_score" in df.columns:
            st.bar_chart(df.set_index("name")["total_score"])
        elif intent == "emp_most_solved" and "name" in df.columns and "solved_count" in df.columns:
            st.bar_chart(df.set_index("name")["solved_count"])
        elif intent == "emp_difficulty_stats" and "difficulty" in df.columns and "pass_rate_percent" in df.columns:
            st.bar_chart(df.set_index("difficulty")["pass_rate_percent"])
        elif intent == "emp_language_stats" and "language" in df.columns and "total_submissions" in df.columns:
            st.bar_chart(df.set_index("language")["total_submissions"])
        elif intent == "emp_domain_breakdown" and "domain" in df.columns and "total_submissions" in df.columns:
            st.bar_chart(df.set_index("domain")["total_submissions"])
        elif intent == "emp_pass_rate" and "college" in df.columns and "pass_rate_percent" in df.columns:
            st.bar_chart(df.set_index("college")["pass_rate_percent"])
        elif intent == "emp_daily_trend" and "submission_date" in df.columns and "total_submissions" in df.columns:
            st.line_chart(df.set_index("submission_date")["total_submissions"])
        elif intent == "emp_hardest_questions" and "title" in df.columns and "pass_rate_percent" in df.columns:
            st.bar_chart(df.set_index("title")["pass_rate_percent"])
        elif intent == "emp_subdomain_breakdown" and "sub_domain" in df.columns and "total_submissions" in df.columns:
            st.bar_chart(df.set_index("sub_domain")["total_submissions"])
        elif intent == "emp_question_type_stats" and "question_type" in df.columns and "total_submissions" in df.columns:
            st.bar_chart(df.set_index("question_type")["total_submissions"])
        elif intent == "emp_recent_activity" and "name" in df.columns:
            counts = df.groupby("name").size().sort_values(ascending=False).head(20)
            st.bar_chart(counts)
        elif intent == "assess_top_scorers" and "name" in df.columns and "total_score" in df.columns:
            st.bar_chart(df.set_index("name")["total_score"])
        elif intent == "assess_pass_rate" and "assessment" in df.columns and "pass_rate_percent" in df.columns:
            st.bar_chart(df.set_index("assessment")["pass_rate_percent"])
        elif intent == "assess_skill_breakdown" and "skill" in df.columns and "pass_rate_percent" in df.columns:
            st.bar_chart(df.set_index("skill")["pass_rate_percent"])
        elif intent == "assess_difficulty_breakdown" and "difficulty" in df.columns and "pass_rate_percent" in df.columns:
            st.bar_chart(df.set_index("difficulty")["pass_rate_percent"])
        elif intent == "assess_completion_rate" and "assessment" in df.columns and "completion_rate_percent" in df.columns:
            st.bar_chart(df.set_index("assessment")["completion_rate_percent"])
        elif intent == "assess_list" and "title" in df.columns and "shortlisted_count" in df.columns:
            st.bar_chart(df.set_index("title")["shortlisted_count"])
    except Exception:
        pass  # Charts are best-effort


# ── Data renderer — handles both list and dict (student profile) ──────────────

def _render_data(data, intent: str) -> None:
    if not data:
        return
    if isinstance(data, dict):
        section_labels = {
            "submissions":     "📝 Submissions",
            "streaks":         "🔥 Streaks",
            "badges":          "🏅 Badges",
            "coins":           "🪙 Coins",
            "summary":         "📊 Performance Summary",
            "question_status": "✅ Question Status",
        }
        for key, label in section_labels.items():
            rows = data.get(key, [])
            if rows:
                st.markdown(f"**{label}**")
                df = pd.DataFrame(rows)
                st.dataframe(df, use_container_width=True)
                csv = df.to_csv(index=False)
                st.download_button(
                    f"⬇️ Download {label} CSV",
                    data=csv,
                    file_name=f"pod_{key}.csv",
                    mime="text/csv",
                    key=f"dl_{key}_{id(data)}",
                )
    else:
        df = pd.DataFrame(data)
        st.dataframe(df, use_container_width=True)
        _render_chart(df, intent)
        csv = df.to_csv(index=False)
        st.download_button(
            "⬇️ Download CSV",
            data=csv,
            file_name="pod_result.csv",
            mime="text/csv",
            key=f"dl_list_{id(data)}",
        )


# ── Session state ─────────────────────────────────────────────────────────────

if "messages" not in st.session_state:
    st.session_state.messages = []

if "college_name" not in st.session_state:
    st.session_state.college_name = ""

if "last_sql" not in st.session_state:
    st.session_state.last_sql = None        # ← stores SQL from last successful response
if "sql_chain_count" not in st.session_state:
    st.session_state.sql_chain_count = 0    # ← tracks SQL modification chain depth
if "previous_intent" not in st.session_state:
    st.session_state.previous_intent = None # ← module from last turn (for switch detection)


# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("## ⚙️ Settings")
    college_input = st.text_input(
        "Your College Name",
        value=st.session_state.college_name,
        placeholder="e.g. Mahindra University",
        help="Automatically scopes every query to your college.",
    )
    st.session_state.college_name = college_input.strip()

    st.divider()
    st.markdown("### 💡 Example Questions")
    examples = [
        # ── POD ───────────────────────────────────────────────────────────────
        "Who solved today's POD?",
        "Who solved the POD fastest today?",
        "Who has the longest streak?",
        "Who lost their streak recently?",
        "Show me the top 10 POD scorers this week",
        "Show Pranith Kumar Navath's profile",
        # ── POD follow-ups (conversational history) ───────────────────────────
        "What about his streaks only?",
        "What about his badges?",
        # ── Employability ──────────────────────────────────────────────────────
        "Show employability top scorers",
        "What is the pass rate for Data Structures?",
        "Show me the subdomain breakdown for Algorithms",
        "Show Pranith Kumar Navath's employability profile",
        # ── Employability follow-up ────────────────────────────────────────────
        "What about hard questions only?",
        # ── Assessments ────────────────────────────────────────────────────────
        "List all assessments",
        "Show recent assessments",
        "What is the pass rate for Backend Developer - DSA in C?",
        # ── Assessment follow-ups ──────────────────────────────────────────────
        "What about the difficulty breakdown?",
        "What about the skill breakdown?",
    ]
    for ex in examples:
        if st.button(ex, use_container_width=True):
            st.session_state["_prefill"] = ex

    st.divider()
    if st.button("🗑️ Clear Chat", use_container_width=True):
        st.session_state.messages = []
        st.session_state.last_sql = None        # ← reset SQL context on clear
        st.session_state.sql_chain_count = 0    # ← reset chain count on clear
        st.session_state.previous_intent = None # ← reset module context on clear
        st.rerun()

    st.markdown("---")
    st.caption("TapTap POD Analytics · FastAPI + LangGraph + SQLAlchemy")


# ── Header ────────────────────────────────────────────────────────────────────

st.title("🧩 TapTap POD Analytics")
st.markdown("Ask any question about student Problem of the Day activity.")

if st.session_state.college_name:
    st.info(f"📍 College context: **{st.session_state.college_name}**", icon="🏫")
else:
    st.warning("Set your college name in the sidebar to scope results to your college.", icon="⚠️")

st.divider()


# ── Chat history ──────────────────────────────────────────────────────────────

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("data"):
            with st.expander("📊 View raw data"):
                _render_data(msg["data"], msg.get("intent", ""))
        if msg.get("intent"):
            st.caption(f"Intent: `{msg['intent']}`")


# ── Chat input ────────────────────────────────────────────────────────────────

prefill    = st.session_state.pop("_prefill", None)
user_input = st.chat_input("Ask about POD or Employability activity…")
query      = prefill or user_input

if query:
    st.session_state.messages.append({"role": "user", "content": query})
    with st.chat_message("user"):
        st.markdown(query)

    with st.chat_message("assistant"):
        with st.spinner("Analysing…"):
            try:
                # Build history from session — user messages only.
                # Assistant answers are excluded to avoid Azure content filter
                # false positives on data-heavy answers (student names, scores etc.)
                # The LLM only needs prior user messages to resolve follow-ups.
                history = [
                    {"role": msg["role"], "content": msg["content"]}
                    for msg in st.session_state.messages[:-1]
                    if msg["role"] == "user" and msg.get("content")
                ]

                payload = {
                    "message":      query,
                    "college_name": st.session_state.college_name or None,
                    "history":      history,
                    "last_sql":        st.session_state.last_sql,        # ← send last SQL as context
                    "sql_chain_count": st.session_state.sql_chain_count, # ← send chain depth
                    "previous_intent": st.session_state.previous_intent, # ← send prior module
                }
                resp = requests.post(
                    f"{API_BASE}/chat",
                    json=payload,
                    timeout=30,
                )
                resp.raise_for_status()
                result = resp.json()

                answer = result.get("answer") or "No answer returned."
                intent = result.get("intent", "")
                data   = result.get("data") or []
                error  = result.get("error")
                sql    = result.get("sql")

                # ← persist the returned SQL and chain count for the next follow-up turn
                if sql:
                    st.session_state.last_sql = sql
                # Always persist chain count and previous_intent regardless of whether SQL was returned
                st.session_state.sql_chain_count = result.get("sql_chain_count", 0)
                if result.get("previous_intent"):
                    st.session_state.previous_intent = result["previous_intent"]

                st.markdown(answer)

                if data:
                    with st.expander("📊 View raw data"):
                        _render_data(data, intent)

                if error:
                    st.error(f"Backend error: {error}")

                if intent:
                    st.caption(f"Intent: `{intent}`")

                st.session_state.messages.append({
                    "role":    "assistant",
                    "content": answer,
                    "data":    data,
                    "intent":  intent,
                })

            except requests.exceptions.ConnectionError:
                msg = "❌ Cannot connect to the backend. Is uvicorn running on port 8000?"
                st.error(msg)
                st.session_state.messages.append({"role": "assistant", "content": msg})
            except requests.exceptions.Timeout:
                msg = "⏳ Request timed out. Please try again."
                st.error(msg)
                st.session_state.messages.append({"role": "assistant", "content": msg})
            except Exception as exc:
                msg = f"❌ Unexpected error: {exc}"
                st.error(msg)
                st.session_state.messages.append({"role": "assistant", "content": msg})